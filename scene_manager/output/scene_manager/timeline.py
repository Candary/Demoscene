"""Компилятор показа: файл *.show.json -> ResolvedShow (абсолютные времена, программы uniform'ов, замечания).

Формат (scene-manager/1), коротко:
  meta      {title, duration | "auto", resolution, fps, seed, budget}
  audio     {file, bpm, offset, beats_per_bar, markers:[{name, time|bar,beat}], analysis}
  palettes  {имя: {роль: "#hex"}}                     — закреплённые (pinned) цвета, обычно из Color Matrix
  looks     {имя: {atoms:{...}, palette:"имя"}}       — повторно используемые «настроения»
  tracks    [{id, order, sparse?}]                    — слои; чем больше order, тем выше
  clips     [{id, track, kind, effect, start, duration|end, atoms, map, palette, look, opacity, blend, curves...}]
Время клипа задаётся ЯКОРЯМИ, а не только секундами: см. _time_anchor. Переходы — связи {between:[a,b]}, а не клипы на таймлайне:
менеджер сам продлевает A и B на время перехода (как в видеоредакторе).

Семантика времени клипа: номинальное окно [nom_start, nom_end) — то, что задал автор; эффективное [eff_start, eff_end) — с учётом
подводки переходов. t в выражениях — секунды от НОМИНАЛЬНОГО начала (на подводке < 0), p = t / длительность (не ограничен).
Стандартная униформа uTime — секунды от эффективного начала (>= 0), uProgress = clamp(p) (у перехода — с кривой).
"""
from __future__ import annotations

import math
import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from .audio import AudioMap
from .effects import STANDARD_UNIFORMS, TYPES, Effect, EffectCatalog
from .expr import Compiled, ExprError, compile_expr, eval_rpn, fold_constant

FORMAT = "scene-manager/1"
ID_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
BLENDS = ("normal", "add", "screen", "multiply")
RESERVED_VARS = {"t", "p", "dur", "time"}
AUDIO_VARS = {"audio.beat", "audio.beat_phase", "audio.bar", "audio.bar_phase", "audio.energy", "audio.section"}
BASE_VARS = RESERVED_VARS | AUDIO_VARS
EASINGS = {"linear": "clamp({x},0,1)", "smoothstep": "smoothstep(0,1,{x})", "ease_in": "clamp({x},0,1)*clamp({x},0,1)",
           "ease_out": "1-(1-clamp({x},0,1))*(1-clamp({x},0,1))", "hold": "step(1,{x})"}
MAX_GENERATED_TOKENS = 40000   # ≈ 1400 ключей на кривую (каждый ключ ≈ 27 токенов исходного выражения)
EPS = 1e-9


@dataclass
class Issue:
    level: str      # error | warning | info
    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.code} {self.path}: {self.message}"

    def to_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "path": self.path, "message": self.message}


@dataclass
class RClip:
    id: str
    track: str
    track_order: int
    kind: str
    effect: str
    nom_start: float
    nom_end: float
    eff_start: float
    eff_end: float
    blend: str = "normal"
    opacity: Compiled | None = None
    progress: Compiled | None = None
    seed: int = 0
    inputs: tuple = ()                           # у перехода: (id A, id B)
    uniforms: dict = field(default_factory=dict)  # имя -> (type, [Compiled, ...])
    status: str = "accepted"
    locked: bool = False
    prewarm_start: float = 0.0
    order_in_show: int = 0
    arrays: dict = field(default_factory=dict)    # имя -> [float, ...] (константные массивы, например примитивы сцены)

    @property
    def nom_dur(self) -> float:
        return self.nom_end - self.nom_start


@dataclass
class ResolvedShow:
    meta: dict
    audio: AudioMap
    tracks: dict[str, int]
    clips: list[RClip]
    palettes: dict
    issues: list[Issue]
    duration: float

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    def clip(self, id_: str) -> RClip:
        for c in self.clips:
            if c.id == id_:
                return c
        raise KeyError(id_)

    def env_at(self, c: RClip, T: float) -> dict:
        """Окружение выражений для клипа в момент T (эталон для runtime)."""
        a = self.audio
        if c.kind == "transition":
            dur = c.nom_dur
        else:
            dur = c.nom_dur
        t = T - c.nom_start
        return {"t": t, "p": (t / dur) if dur > 0 else 0.0, "dur": dur, "time": T,
                "audio.beat": a.beat(T), "audio.beat_phase": a.beat_phase(T), "audio.bar": a.bar(T),
                "audio.bar_phase": a.bar_phase(T), "audio.energy": a.energy_at(T), "audio.section": float(a.section_index(T))}

    def active(self, T: float) -> list[RClip]:
        return [c for c in self.clips if c.eff_start - EPS <= T < c.eff_end - EPS or (c.kind == "event" and T >= c.eff_start)]


# ======================================================================================================================
def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _seed(show_seed, clip_id) -> int:
    return zlib.crc32(f"{show_seed}:{clip_id}".encode()) & 0xFFFFFF   # 24 бита: точно представимо в float32


def curve_expr(keys: list, var: str = "t") -> str:
    """Ключевые кадры [[t, v, 'ease'?], ...] -> выражение без вложенности: v0 + sum(dv_i * ease_i(clamp((t-t_{i-1})/dt_i)))."""
    if not isinstance(keys, list) or len(keys) < 1:
        raise ExprError("curve: нужен непустой список ключей [[t, value, ease?], ...]")
    ks = []
    for k in keys:
        if not (isinstance(k, (list, tuple)) and 2 <= len(k) <= 3 and _num(k[0]) and _num(k[1])):
            raise ExprError(f"curve: ключ должен быть [t, value] или [t, value, ease], получено {k!r}")
        ease = k[2] if len(k) == 3 else "linear"
        if ease not in EASINGS:
            raise ExprError(f"curve: неизвестная кривая {ease!r}; допустимо {sorted(EASINGS)}")
        ks.append((float(k[0]), float(k[1]), ease))
    for a, b in zip(ks, ks[1:]):
        if b[0] <= a[0]:
            raise ExprError("curve: времена ключей должны строго возрастать")
    terms = [repr(ks[0][1])]
    for (t0, v0, _), (t1, v1, ease) in zip(ks, ks[1:]):
        x = f"(({var}-({t0!r}))/{t1 - t0!r})"
        terms.append(f"({v1 - v0!r})*({EASINGS[ease].format(x=x)})")
    return " + ".join(terms)


def _inline(c: Compiled, defs: dict[str, tuple]) -> Compiled:
    """Подставить определения атомов (их RPN) вместо переменных; затем свернуть константы."""
    if not (c.names & set(defs)):
        return fold_constant(c)
    out, names = [], set()
    for tok in c.rpn:
        if tok[0] == "v" and tok[1] in defs:
            out.extend(defs[tok[1]])
        else:
            out.append(tok)
    for tok in out:
        if tok[0] == "v":
            names.add(tok[1])
    return fold_constant(Compiled(c.source, tuple(out), frozenset(names)))


# ======================================================================================================================
class _Ctx:
    def __init__(self, show: dict, catalog: EffectCatalog, base_dir):
        self.show, self.cat, self.base_dir = show, catalog, base_dir
        self.issues: list[Issue] = []
        self.clips_raw: dict[str, dict] = {}
        self.times: dict[str, tuple[float, float]] = {}
        self.stack: list[str] = []
        self.audio = AudioMap()
        self.broken: set[str] = set()

    def err(self, code, path, msg):
        self.issues.append(Issue("error", code, path, msg))

    def warn(self, code, path, msg):
        self.issues.append(Issue("warning", code, path, msg))

    def info(self, code, path, msg):
        self.issues.append(Issue("info", code, path, msg))

    # ---- якоря времени ----------------------------------------------------------------------------------------------
    def _offsets(self, a: dict) -> float:
        a_ = self.audio
        return float(a.get("offset", 0.0)) + float(a.get("offset_beats", 0.0)) * a_.spb + float(a.get("offset_bars", 0.0)) * a_.spb * a_.beats_per_bar

    def time_anchor(self, a, path: str) -> float:
        if _num(a):
            return float(a)
        if not isinstance(a, dict):
            raise ValueError(f"{path}: якорь времени — число или объект, получено {a!r}")
        keys = [k for k in ("time", "marker", "bar", "end_of", "after", "start_of", "with") if k in a]
        if len(keys) != 1:
            raise ValueError(f"{path}: в якоре ровно один из time/marker/bar/end_of(after)/start_of(with), найдено {keys or 'ничего'}")
        k = keys[0]
        off = self._offsets({x: a[x] for x in ("offset", "offset_beats", "offset_bars") if x in a})
        if k == "time":
            return float(a["time"]) + off
        if k == "marker":
            try:
                return self.audio.marker(a["marker"]) + off
            except KeyError as e:
                raise ValueError(f"{path}: {e.args[0]}") from None
        if k == "bar":
            return self.audio.time_of(float(a["bar"]), float(a.get("beat", 1))) + off
        ref = a[k]
        if ref not in self.clips_raw:
            raise ValueError(f"{path}: ссылка на несуществующий клип {ref!r}")
        s, e = self.clip_times(ref)
        return (e if k in ("end_of", "after") else s) + off

    def duration_value(self, d, path) -> float:
        if _num(d):
            return float(d)
        if isinstance(d, dict) and "beats" in d:
            return float(d["beats"]) * self.audio.spb
        if isinstance(d, dict) and "bars" in d:
            return float(d["bars"]) * self.audio.spb * self.audio.beats_per_bar
        raise ValueError(f"{path}: длительность — секунды, {{beats:n}}, {{bars:n}} или {{until: якорь}}")

    def clip_times(self, id_: str) -> tuple[float, float]:
        if id_ in self.times:
            return self.times[id_]
        if id_ in self.stack:
            cyc = " -> ".join(self.stack[self.stack.index(id_):] + [id_])
            raise ValueError(f"циклическая зависимость времён: {cyc}")
        self.stack.append(id_)
        try:
            c = self.clips_raw[id_]
            p = f"clips[{id_}]"
            if c.get("kind") == "transition":
                raise ValueError(f"{p}: на переход нельзя ссылаться как на якорь (его окно вычисляется из between)")
            if "start" not in c:
                raise ValueError(f"{p}.start обязателен")
            s = self.time_anchor(c["start"], f"{p}.start")
            if "end" in c:
                e = self.time_anchor(c["end"], f"{p}.end")
            elif isinstance(c.get("duration"), dict) and "until" in c["duration"]:
                e = self.time_anchor(c["duration"]["until"], f"{p}.duration.until")
            elif "duration" in c:
                e = s + self.duration_value(c["duration"], f"{p}.duration")
            elif c.get("kind") == "event":
                e = s
            else:
                raise ValueError(f"{p}: нужен duration или end")
            if e < s - EPS:
                raise ValueError(f"{p}: конец ({e:.3f}) раньше начала ({s:.3f})")
            self.times[id_] = (s, e)
            return s, e
        finally:
            self.stack.pop()


# ======================================================================================================================
def compile_show(show: dict, catalog: EffectCatalog, base_dir: str | Path | None = None, *, strict: bool = False) -> ResolvedShow:
    """strict=True: клипы со status 'proposed' — ошибка (финальная сборка допускает только утверждённое)."""
    ctx = _Ctx(show, catalog, base_dir)
    meta = dict(show.get("meta") or {})
    if show.get("format") != FORMAT:
        ctx.err("E_FORMAT", "format", f"ожидалось {FORMAT!r}, получено {show.get('format')!r}")
    # --- аудио
    try:
        ctx.audio = AudioMap.from_show(show.get("audio"), Path(base_dir) if base_dir else None)
    except (ValueError, KeyError, TypeError) as exc:
        ctx.err("E_AUDIO", "audio", str(exc))
    # --- дорожки
    tracks: dict[str, int] = {}
    sparse: set[str] = set()
    for i, t in enumerate(show.get("tracks") or []):
        tid = t.get("id")
        if not isinstance(tid, str) or not ID_RE.match(tid):
            ctx.err("E_ID", f"tracks[{i}].id", f"некорректный id {tid!r}")
        elif tid in tracks:
            ctx.err("E_ID", f"tracks[{i}].id", f"дублируется id дорожки {tid!r}")
        else:
            tracks[tid] = int(t.get("order", i))
            if t.get("sparse"):
                sparse.add(tid)
    # --- клипы: id
    for i, c in enumerate(show.get("clips") or []):
        cid = c.get("id")
        if not isinstance(cid, str) or not ID_RE.match(cid):
            ctx.err("E_ID", f"clips[{i}].id", f"некорректный id {cid!r} (разрешены A-Z a-z 0-9 _ . -)")
        elif cid in ctx.clips_raw:
            ctx.err("E_ID", f"clips[{i}].id", f"дублируется id клипа {cid!r}")
        else:
            ctx.clips_raw[cid] = c
    palettes, looks = show.get("palettes") or {}, show.get("looks") or {}

    # --- номинальные времена (все клипы, кроме переходов)
    for cid, c in ctx.clips_raw.items():
        if c.get("kind") == "transition":
            continue
        try:
            ctx.clip_times(cid)
        except ValueError as exc:
            ctx.err("E_TIME", f"clips[{cid}]", str(exc))
            ctx.broken.add(cid)
        except (TypeError, KeyError) as exc:
            ctx.err("E_TIME", f"clips[{cid}]", f"{type(exc).__name__}: {exc}")
            ctx.broken.add(cid)
        c_eff = c.get("effect")
        if c_eff not in catalog.effects:
            ctx.err("E_EFFECT_REF", f"clips[{cid}].effect", f"неизвестный эффект {c_eff!r}; в каталоге: {sorted(catalog.effects)}")
            ctx.broken.add(cid)
        elif catalog.effects[c_eff].kind != c.get("kind"):
            ctx.err("E_KIND_MISMATCH", f"clips[{cid}].kind", f"эффект {c_eff!r} имеет kind={catalog.effects[c_eff].kind!r}, клип объявлен как {c.get('kind')!r}")
            ctx.broken.add(cid)
        if c.get("track") not in tracks:
            ctx.err("E_TRACK_REF", f"clips[{cid}].track", f"неизвестная дорожка {c.get('track')!r}; есть: {sorted(tracks)}")
            ctx.broken.add(cid)
        for key, table in (("look", looks), ("palette", palettes)):
            if c.get(key) is not None and c[key] not in table:
                ctx.err("E_REF", f"clips[{cid}].{key}", f"неизвестный {key} {c[key]!r}; есть: {sorted(table)}")

    # --- переходы: окна и подводка
    eff: dict[str, list[float]] = {cid: [*ctx.times[cid]] for cid in ctx.times}
    trans: dict[str, tuple[float, float, str, str, str]] = {}   # id -> (w0, w1, a, b, curve)
    for cid, c in ctx.clips_raw.items():
        if c.get("kind") != "transition":
            continue
        p = f"clips[{cid}]"
        btw = c.get("between")
        if not (isinstance(btw, list) and len(btw) == 2 and all(isinstance(x, str) for x in btw)):
            ctx.err("E_TRANSITION", f"{p}.between", "between должен быть списком из двух id клипов [A, B]")
            continue
        a_id, b_id = btw
        if c.get("effect") not in catalog.effects or catalog.effects[c["effect"]].kind != "transition":
            ctx.err("E_EFFECT_REF", f"{p}.effect", f"нужен эффект вида transition; в каталоге: {sorted(e.id for e in catalog.search(kind='transition'))}")
            continue
        bad = [x for x in (a_id, b_id) if x not in ctx.clips_raw or ctx.clips_raw[x].get("kind") != "scene" or x in ctx.broken]
        if bad:
            ctx.err("E_TRANSITION", f"{p}.between", f"клипы {bad} не найдены, повреждены или не являются сценами (kind=scene)")
            continue
        if ctx.clips_raw[a_id].get("track") != ctx.clips_raw[b_id].get("track"):
            ctx.err("E_TRANSITION", f"{p}.between", "A и B должны лежать на одной дорожке")
            continue
        try:
            d = ctx.duration_value(c.get("duration", 0.0), f"{p}.duration")
        except ValueError as exc:
            ctx.err("E_TRANSITION", f"{p}.duration", str(exc))
            continue
        (a0, a1), (b0, b1) = ctx.times[a_id], ctx.times[b_id]
        cut = b0
        if abs(a1 - b0) > 1e-3:
            ctx.warn("W_TRANSITION_CUT", p, f"A заканчивается в {a1:.3f}, B начинается в {b0:.3f}: стык берётся по началу B ({b0:.3f})")
        if c["effect"] == "cut" or d <= 0:
            ctx.info("I_CUT", p, "жёсткая склейка: окно перехода не создаётся")
            continue
        align = c.get("align", "center")
        if align not in ("center", "end", "start"):
            ctx.err("E_TRANSITION", f"{p}.align", "align: center | end | start")
            continue
        w0, w1 = {"center": (cut - d / 2, cut + d / 2), "end": (cut - d, cut), "start": (cut, cut + d)}[align]
        if w0 < a0 - EPS or w1 > b1 + EPS:
            ctx.err("E_TRANSITION_LONG", p, f"окно перехода [{w0:.3f}, {w1:.3f}] выходит за пределы клипов A [{a0:.3f}, {a1:.3f}] / B [{b0:.3f}, {b1:.3f}]")
            continue
        eff[a_id][1] = max(eff[a_id][1], w1)
        eff[b_id][0] = min(eff[b_id][0], w0)
        curve = c.get("curve", "smoothstep")
        if curve not in EASINGS:
            ctx.err("E_TRANSITION", f"{p}.curve", f"неизвестная кривая {curve!r}; допустимо {sorted(EASINGS)}")
            continue
        trans[cid] = (w0, w1, a_id, b_id, curve)

    # --- показать
    clips: list[RClip] = []
    seed = meta.get("seed", 0)
    order = 0
    for cid, c in ctx.clips_raw.items():
        order += 1
        if cid in ctx.broken or (c.get("kind") == "transition" and cid not in trans):
            continue
        ef = catalog.effects[c["effect"]]
        if c.get("kind") == "transition":
            w0, w1, a_id, b_id, curve = trans[cid]
            nom0, nom1, e0, e1, inputs = w0, w1, w0, w1, (a_id, b_id)
            progress = compile_expr(EASINGS[curve].format(x="p"), BASE_VARS)
        else:
            nom0, nom1 = ctx.times[cid]
            e0, e1 = eff[cid]
            inputs = ()
            progress = compile_expr("clamp(p,0,1)", BASE_VARS)
        track_id = ctx.clips_raw[inputs[0]]["track"] if inputs else c["track"]    # переход живёт на дорожке клипа A
        rc = RClip(cid, track_id, tracks[track_id], c["kind"], c["effect"], nom0, nom1, e0, e1, c.get("blend", "normal"),
                   None, progress, c.get("seed", _seed(seed, cid)), inputs, {}, c.get("status", "accepted"), bool(c.get("locked", False)),
                   max(0.0, e0 - float(meta.get("prewarm", 3.0))), order)
        if rc.blend not in BLENDS:
            ctx.err("E_BLEND", f"clips[{cid}].blend", f"blend: {BLENDS}")
        if rc.status not in ("accepted", "proposed"):
            ctx.err("E_STATUS", f"clips[{cid}].status", "status: accepted | proposed")
        if strict and rc.status == "proposed":
            ctx.err("E_PROPOSED", f"clips[{cid}]", "клип ещё не утверждён автором (status=proposed); утвердите или удалите перед финальной сборкой")
        _compile_uniforms(ctx, rc, c, ef, palettes, looks)
        clips.append(rc)

    clips.sort(key=lambda r: (r.track_order, r.eff_start, r.order_in_show))
    # --- длительность показа
    fin = [r.eff_start for r in clips if r.kind == "event" and r.effect == "finish"]
    md = meta.get("duration", "auto")
    if _num(md):
        duration = float(md)
    else:
        if md != "auto":
            ctx.err("E_META", "meta.duration", "число секунд или 'auto'")
        duration = min(fin) if fin else max([r.eff_end for r in clips if r.kind != "event"] or [0.0])
    res = ResolvedShow(meta, ctx.audio, tracks, clips, palettes, ctx.issues, duration)
    _lint(ctx, res, catalog, sparse)
    return res


# ======================================================================================================================
def _atom_defs(ctx: _Ctx, cid: str, atoms: dict) -> tuple[dict[str, tuple], dict[str, str]]:
    """Числовые атомы -> RPN (с подставленными зависимостями); категориальные (строки) отдельно."""
    numeric_names = {k for k, v in atoms.items() if not isinstance(v, str)}
    for k in atoms:
        if k in BASE_VARS or "." in k or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", k):
            ctx.err("E_ATOM_NAME", f"clips[{cid}].atoms.{k}", f"недопустимое имя атома {k!r} (зарезервировано или содержит точку)")
    allowed = BASE_VARS | numeric_names
    raw: dict[str, Compiled] = {}
    categ: dict[str, str] = {}
    for k, v in atoms.items():
        p = f"clips[{cid}].atoms.{k}"
        try:
            if isinstance(v, bool):
                raw[k] = compile_expr("1" if v else "0")
            elif _num(v):
                raw[k] = compile_expr(repr(float(v)))
            elif isinstance(v, str):
                categ[k] = v
            elif isinstance(v, dict) and set(v) == {"expr"}:
                raw[k] = compile_expr(v["expr"], allowed)
            elif isinstance(v, dict) and set(v) <= {"keys", "var"} and "keys" in v:
                raw[k] = compile_expr(curve_expr(v["keys"], v.get("var", "t")), allowed, max_tokens=MAX_GENERATED_TOKENS)
            else:
                raise ExprError("значение атома: число, bool, строка (категория), {expr: ...} или {keys: [[t, v, ease?], ...]}")
        except ExprError as exc:
            msg = str(exc) + ("; разбейте кривую на несколько клипов или упростите ключи" if "длиннее" in str(exc) else "")
            ctx.err("E_EXPR", p, msg)
            raw[k] = compile_expr("0")        # заглушка: ошибка уже учтена, зависимые выражения не должны сыпать каскад ложных ошибок
    defs: dict[str, tuple] = {}
    state: dict[str, int] = {}

    def resolve(name, chain):
        if name in defs:
            return
        if state.get(name) == 1:
            ctx.err("E_ATOM_CYCLE", f"clips[{cid}].atoms.{name}", "циклическая зависимость атомов: " + " -> ".join(chain + [name]))
            defs[name] = (("n", 0.0),)
            return
        state[name] = 1
        c = raw[name]
        for dep in c.names & set(raw):
            resolve(dep, chain + [name])
        defs[name] = _inline(c, {k: v for k, v in defs.items() if k in c.names}).rpn
        state[name] = 2

    for k in raw:
        resolve(k, [])
    return defs, categ


def _hex_to_rgb(h: str) -> tuple[float, float, float]:
    m = re.match(r"^#?([0-9a-fA-F]{6})$", h.strip())
    if not m:
        raise ValueError(f"не hex-цвет: {h!r}")
    v = m.group(1)
    return tuple(int(v[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _color_value(ref, palette: dict, space: str, path: str) -> tuple[float, float, float]:
    if isinstance(ref, str) and ref.startswith("palette."):
        role = ref.split(".", 1)[1]
        if not palette:
            raise ValueError(f"{path}: у клипа нет палитры (задайте palette или look с palette), а uniform привязан к {ref!r}")
        if role not in palette:
            raise ValueError(f"{path}: в палитре нет роли {role!r}; есть: {sorted(palette)}")
        rgb = _hex_to_rgb(palette[role])
    elif isinstance(ref, str):
        rgb = _hex_to_rgb(ref)
    elif isinstance(ref, (list, tuple)) and len(ref) == 3 and all(_num(x) for x in ref):
        rgb = tuple(float(x) for x in ref)
    else:
        raise ValueError(f"{path}: цвет — 'palette.<роль>', '#rrggbb' или [r,g,b] (0..1), получено {ref!r}")
    return tuple(_srgb_to_linear(x) for x in rgb) if space == "linear" else rgb  # type: ignore[return-value]


def _compile_uniforms(ctx: _Ctx, rc: RClip, c: dict, ef: Effect, palettes: dict, looks: dict) -> None:
    cid = rc.id
    look = looks.get(c.get("look"), {}) if c.get("look") else {}
    atoms = {**ef.atoms, **(look.get("atoms") or {}), **(c.get("atoms") or {})}
    pal_name = c.get("palette") or look.get("palette")
    palette = palettes.get(pal_name, {}) if pal_name else {}
    defs, _categ = _atom_defs(ctx, cid, atoms)
    allowed = BASE_VARS | set(defs)
    mp = c.get("map") or {}
    # v59-fix: handle clip-level arrays (e.g., uPrimitives for cozy_room_sdf)
    clip_arrays = c.get("arrays") or {}
    for arr_name, arr_values in clip_arrays.items():
        rc.arrays[arr_name] = [float(x) for x in arr_values]
    for k in mp:
        if k in STANDARD_UNIFORMS:
            ctx.err("E_UNIFORM_RESERVED", f"clips[{cid}].map.{k}", f"{k} задаёт движок ({STANDARD_UNIFORMS[k]}); его нельзя назначить")
        elif k not in ef.uniforms:
            near = [u for u in ef.uniforms if u.lower().startswith(k.lower()[:3])] or sorted(ef.uniforms)
            ctx.err("E_UNIFORM_UNKNOWN", f"clips[{cid}].map.{k}", f"эффект {ef.id!r} не имеет uniform {k!r}; есть: {near}")

    def comp(src, path) -> Compiled:
        if _num(src):
            return compile_expr(repr(float(src)))
        if isinstance(src, bool):
            return compile_expr("1" if src else "0")
        if isinstance(src, str):
            return _inline(compile_expr(src, allowed), defs)
        raise ExprError(f"{path}: ожидалось число или выражение, получено {src!r}")

    for name, spec in ef.uniforms.items():
        path = f"clips[{cid}].map.{name}"
        src = mp.get(name, None)
        origin = "map"
        if src is None:
            src, origin = spec.bind, "bind"
        if src is None:
            src, origin = spec.default, "default"
        if src is None:
            if spec.required:
                ctx.err("E_REQUIRED_UNIFORM", path, f"обязательный uniform {name!r} эффекта {ef.id!r} не задан (нет map, bind и default)")
            continue
        try:
            if spec.type == "farray":
                rc.arrays[name] = _array_value(ctx, src, spec, path)
                continue
            n = spec.size
            if n == 1:
                comps = [comp(src, path)]
            else:
                if isinstance(src, dict) and "vec" in src:
                    if not (isinstance(src["vec"], list) and len(src["vec"]) == n):
                        raise ExprError(f"{path}: vec должен содержать {n} элементов")
                    comps = [comp(x, path) for x in src["vec"]]
                elif isinstance(src, dict) and ("color" in src or "from" in src):
                    rgb = _color_value(src.get("color", src.get("from")), palette, spec.space, path)
                    comps = [compile_expr(repr(x)) for x in rgb] + ([compile_expr("1")] if n == 4 else [])
                elif isinstance(src, str) and (src.startswith("palette.") or src.startswith("#")):
                    rgb = _color_value(src, palette, spec.space, path)
                    comps = [compile_expr(repr(x)) for x in rgb] + ([compile_expr("1")] if n == 4 else [])
                elif isinstance(src, (list, tuple)) and len(src) == n:
                    comps = [comp(x, path) for x in src]
                else:
                    raise ExprError(f"{path}: для {spec.type} ожидалось {{color: ...}}, {{vec: [...]}} или список из {n} значений")
            rc.uniforms[name] = (spec.type, comps)
            _range_check(ctx, rc, spec, comps, path, origin)
        except (ExprError, ValueError) as exc:
            ctx.err("E_EXPR" if isinstance(exc, ExprError) else "E_COLOR", path, str(exc))
    op = c.get("opacity", 1.0)
    try:
        rc.opacity = comp(op, f"clips[{cid}].opacity")
    except ExprError as exc:
        ctx.err("E_EXPR", f"clips[{cid}].opacity", str(exc))
        rc.opacity = compile_expr("1")


def _array_value(ctx: _Ctx, src, spec, path: str) -> list[float]:
    """Константный массив: {asset: имя} (show.assets[имя].floats) или {array: [числа]}."""
    if isinstance(src, dict) and "asset" in src and "array" in src:
        raise ExprError(f"{path}: заданы и asset, и array — оставьте одно (merge-patch сливает вложенные объекты; удалите лишнее ключом null)")
    if isinstance(src, dict) and "asset" in src:
        a = (ctx.show.get("assets") or {}).get(src["asset"])
        if a is None:
            raise ExprError(f"{path}: нет ассета {src['asset']!r}; есть: {sorted(ctx.show.get('assets') or {})}")
        vals = a.get("floats")
    elif isinstance(src, dict) and "array" in src:
        vals = src["array"]
    else:
        raise ExprError(f"{path}: для farray нужен {{asset: имя}} или {{array: [...]}}")
    if not isinstance(vals, list) or not all(_num(v) for v in vals):
        raise ExprError(f"{path}: массив должен состоять из конечных чисел")
    if spec.max is not None and len(vals) > spec.max:
        raise ExprError(f"{path}: длина {len(vals)} > допустимой {int(spec.max)}")
    return [float(v) for v in vals]


def _range_check(ctx: _Ctx, rc: RClip, spec, comps: list[Compiled], path: str, origin: str) -> None:
    """Предупреждение, если значение uniform'а выходит за [min, max] манифеста (по выборке 33 точек клипа)."""
    if (spec.min is None and spec.max is None) or spec.size != 1 or spec.type == "farray":
        return
    c = comps[0]
    dur = max(rc.nom_dur, 1e-6)
    vals = []
    for i in range(33):
        T = rc.nom_start + dur * i / 32
        a = ctx.audio
        env = {"t": T - rc.nom_start, "p": (T - rc.nom_start) / dur, "dur": dur, "time": T, "audio.beat": a.beat(T),
               "audio.beat_phase": a.beat_phase(T), "audio.bar": a.bar(T), "audio.bar_phase": a.bar_phase(T),
               "audio.energy": a.energy_at(T), "audio.section": float(a.section_index(T))}
        try:
            vals.append(eval_rpn(c.rpn, env))
        except (KeyError, ExprError):
            return
    lo, hi = min(vals), max(vals)
    if (spec.min is not None and lo < spec.min - 1e-9) or (spec.max is not None and hi > spec.max + 1e-9):
        ctx.warn("W_RANGE", path, f"{spec.name} ∈ [{lo:.3g}, {hi:.3g}] выходит за допустимый [{spec.min}, {spec.max}] ({origin})")


# ======================================================================================================================
def _lint(ctx: _Ctx, res: ResolvedShow, cat: EffectCatalog, sparse: set[str]) -> None:
    D = res.duration
    layered = [c for c in res.clips if c.kind in ("scene", "overlay")]
    # перекрытия и пробелы на дорожке (после подводки переходов перекрытие A/B допустимо)
    by_track: dict[str, list[RClip]] = {}
    for c in res.clips:
        if c.kind == "scene":
            by_track.setdefault(c.track, []).append(c)
    trans_pairs = {frozenset(c.inputs) for c in res.clips if c.kind == "transition"}
    for tr, cs in by_track.items():
        cs.sort(key=lambda c: c.eff_start)
        for a, b in zip(cs, cs[1:]):
            if b.eff_start < a.eff_end - 1e-6 and frozenset((a.id, b.id)) not in trans_pairs and not ctx.clips_raw[b.id].get("allow_overlap"):
                ctx.warn("W_OVERLAP", f"clips[{b.id}]", f"перекрывается с {a.id!r} на дорожке {tr!r} ({b.eff_start:.2f} < {a.eff_end:.2f}) без перехода")
            elif b.eff_start > a.eff_end + 0.05 and tr not in sparse and not ctx.clips_raw[b.id].get("allow_gap"):
                ctx.warn("W_GAP", f"clips[{b.id}]", f"пробел {b.eff_start - a.eff_end:.2f} с между {a.id!r} и {b.id!r} на дорожке {tr!r} (чёрные кадры; allow_gap или track.sparse)")
    # покрытие демо сценами (любая дорожка)
    spans = sorted((c.eff_start, c.eff_end) for c in layered if c.kind == "scene")
    t = 0.0
    for s, e in spans:
        if s > t + 0.05 and t < D:
            ctx.warn("W_UNCOVERED", "clips", f"нет ни одной сцены в интервале [{t:.2f}, {min(s, D):.2f}] (чёрный экран)")
        t = max(t, e)
    if t < D - 0.05 and D > 0:
        ctx.warn("W_UNCOVERED", "clips", f"сцены заканчиваются в {t:.2f}, демо длится до {D:.2f}")
    # клипы за пределами показа / аудио
    for c in res.clips:
        if c.eff_start > D + 1e-6 and c.kind != "event":
            ctx.warn("W_OUTSIDE", f"clips[{c.id}]", f"клип начинается ({c.eff_start:.2f}) после конца показа ({D:.2f}) и не будет виден")
        elif c.eff_end > D + 1e-6 and c.kind != "event":
            ctx.warn("W_TRUNCATED", f"clips[{c.id}]", f"клип заканчивается ({c.eff_end:.2f}) после конца показа ({D:.2f}): хвост будет обрезан")
    if res.audio.duration and D > res.audio.duration + 0.05:
        ctx.warn("W_AUDIO_SHORT", "meta.duration", f"показ ({D:.2f} с) длиннее аудио ({res.audio.duration:.2f} с)")
    # бюджет по сегментам
    budget = res.meta.get("budget")
    if budget is not None:
        pts = sorted({0.0, D, *[x for c in res.clips for x in (c.eff_start, c.eff_end) if 0 <= x <= D]})
        worst = (0, 0.0)
        for a, b in zip(pts, pts[1:]):
            if b - a < 1e-6:
                continue
            m = (a + b) / 2
            cost = sum(cat.effects[c.effect].cost for c in res.clips if c.eff_start <= m < c.eff_end and c.kind != "event")
            if cost > worst[0]:
                worst = (cost, a)
        if worst[0] > budget:
            ctx.warn("W_BUDGET", "meta.budget", f"суммарная стоимость эффектов {worst[0]} > бюджета {budget} (первое превышение с t={worst[1]:.2f})")
    # читаемость текста: контраст text/bg палитры клипа
    for c in res.clips:
        ef = cat.effects[c.effect]
        if ef.text:
            raw = ctx.clips_raw[c.id]
            look = (ctx.show.get("looks") or {}).get(raw.get("look"), {})
            pal = res.palettes.get(raw.get("palette") or look.get("palette") or "", {})
            if "text" in pal and "bg" in pal:
                r = _contrast(pal["text"], pal["bg"])
                if r < 4.5:
                    ctx.warn("W_TEXT_CONTRAST", f"clips[{c.id}]", f"контраст text/bg палитры {r:.2f}:1 < 4.5:1 (текст эффекта {ef.id!r} трудно читать)")
            else:
                ctx.info("I_TEXT_PALETTE", f"clips[{c.id}]", "у текстового эффекта в палитре нет ролей text и bg: контраст не проверен")
    if not any(c.kind == "event" and c.effect == "finish" for c in res.clips):
        ctx.info("I_NO_FINISH", "clips", "нет события finish: показ закончится по длительности meta.duration/сцен")
    ms = cat.missing_shaders()
    if ms:
        ctx.info("I_SHADER_MISSING", "effects", f"нет файлов шейдеров для эффектов: {ms}")


def _contrast(h1: str, h2: str) -> float:
    def lum(h):
        r, g, b = (_srgb_to_linear(x) for x in _hex_to_rgb(h))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    a, b = lum(h1), lum(h2)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)
