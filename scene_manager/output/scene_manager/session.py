"""Сессия редактирования показа: удобство управления для человека и для GLM.

Принципы:
  * правки — пакеты операций (edit), применяются АТОМАРНО: либо все, либо ни одной; после пакета возвращается diff замечаний;
  * update_clip — JSON merge-patch (вложенные объекты сливаются, null удаляет ключ): правка одного атома — одна короткая операция;
  * undo/redo на любую глубину (разумный предел); блокировка (locked) защищает утверждённое автором от правок генератора;
  * предложения: клипы со status='proposed' (их создаёт генератор/GLM) утверждает автор (accept); финальная сборка требует утверждения;
  * «посмотреть» без GPU: storyboard (текстовая раскадровка с тактами и секциями) и resolve_at(t) (что на экране в момент t).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import numpy as np

from .audio import AudioMap, analyze_file
from .bake import bake, evaluate_frame, segment_at, source_hash, to_smt
from .effects import EffectCatalog
from .graph import memory_report, plan
from .timeline import FORMAT, ID_RE, Issue, ResolvedShow, compile_show

MAX_HISTORY = 200


class EditError(ValueError):
    pass


def merge_patch(target: dict, patch: dict) -> dict:
    """RFC 7386: вложенные объекты сливаются, null удаляет ключ, остальное заменяет."""
    out = dict(target)
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_patch(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def empty_show(title: str = "untitled", duration: float | str = "auto", resolution=(1920, 1080), fps: int = 60, seed: int = 0) -> dict:
    return {"format": FORMAT, "meta": {"title": title, "duration": duration, "resolution": list(resolution), "fps": fps, "seed": seed,
                                       "prewarm": 3.0},
            "audio": {"bpm": 120.0, "offset": 0.0, "beats_per_bar": 4, "markers": []},
            "palettes": {}, "looks": {}, "tracks": [], "clips": []}


def fmt_time(t: float) -> str:
    m, s = divmod(max(t, 0.0), 60.0)
    return f"{int(m)}:{s:04.1f}"


class ShowSession:
    def __init__(self, show: dict | None = None, catalog: EffectCatalog | None = None, base_dir: str | Path | None = None,
                 color_toolbox=None):
        self.show = show if show is not None else empty_show()
        self.catalog = catalog or EffectCatalog()
        self.base_dir = Path(base_dir) if base_dir else None
        self.color = color_toolbox
        self._undo: list[str] = []
        self._redo: list[str] = []
        self._cache: tuple[str, ResolvedShow] | None = None

    # ---- файл --------------------------------------------------------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path, catalog: EffectCatalog | None = None, color_toolbox=None) -> "ShowSession":
        p = Path(path)
        return cls(json.loads(p.read_text(encoding="utf-8")), catalog, p.parent, color_toolbox)

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.show, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return p

    # ---- компиляция ---------------------------------------------------------------------------------------------------
    def compile(self, strict: bool = False) -> ResolvedShow:
        key = json.dumps(self.show, sort_keys=True) + f"|{strict}"
        if self._cache and self._cache[0] == key:
            return self._cache[1]
        res = compile_show(self.show, self.catalog, self.base_dir, strict=strict)
        self._cache = (key, res)
        return res

    @staticmethod
    def _sig(issues: list[Issue]) -> set:
        return {(i.level, i.code, i.path, i.message) for i in issues}

    def lint(self, strict: bool = False) -> dict:
        res = self.compile(strict)
        by = {"error": [], "warning": [], "info": []}
        for i in res.issues:
            by[i.level].append(i.to_dict())
        return {"duration": round(res.duration, 3), "errors": by["error"], "warnings": by["warning"], "info": by["info"],
                "ok": not by["error"]}

    # ---- правка ---------------------------------------------------------------------------------------------------------
    def edit(self, ops: list[dict], dry_run: bool = False, require_valid: bool = False) -> dict:
        before_issues = self._sig(self.compile().issues)
        work = copy.deepcopy(self.show)
        log = []
        try:
            for i, op in enumerate(ops):
                try:
                    log.append(self._apply(work, op))
                except (EditError, KeyError, TypeError, ValueError) as exc:
                    raise EditError(f"операция #{i} ({op.get('op') if isinstance(op, dict) else op!r}): {type(exc).__name__}: {exc}") from None
        except EditError as exc:
            return {"ok": False, "applied": 0, "error": str(exc), "hint": "пакет отклонён целиком, состояние не изменено"}
        res = compile_show(work, self.catalog, self.base_dir)
        new = [i.to_dict() for i in res.issues if (i.level, i.code, i.path, i.message) not in before_issues and i.level != "info"]
        if require_valid and any(i["level"] == "error" for i in new):
            return {"ok": False, "applied": 0, "error": "правка породила ошибки (require_valid)", "new_issues": new}
        if not dry_run:
            self._undo.append(json.dumps(self.show))
            self._undo = self._undo[-MAX_HISTORY:]
            self._redo.clear()
            self.show = work
        return {"ok": True, "applied": len(log), "dry_run": dry_run, "log": log, "duration": round(res.duration, 3),
                "new_issues": new, "errors_total": len(res.errors), "warnings_total": len([i for i in res.issues if i.level == "warning"])}

    def undo(self) -> dict:
        if not self._undo:
            return {"ok": False, "error": "нечего отменять"}
        self._redo.append(json.dumps(self.show))
        self.show = json.loads(self._undo.pop())
        return {"ok": True, "undo_left": len(self._undo), "redo_left": len(self._redo)}

    def redo(self) -> dict:
        if not self._redo:
            return {"ok": False, "error": "нечего повторять"}
        self._undo.append(json.dumps(self.show))
        self.show = json.loads(self._redo.pop())
        return {"ok": True, "undo_left": len(self._undo), "redo_left": len(self._redo)}

    # ---- операции ------------------------------------------------------------------------------------------------------
    def _clip(self, show: dict, id_: str) -> dict:
        for c in show["clips"]:
            if c.get("id") == id_:
                return c
        raise EditError(f"клип {id_!r} не найден; есть: {[c.get('id') for c in show['clips']][:30]}")

    def _check_lock(self, c: dict, op: dict) -> None:
        if c.get("locked") and not op.get("force"):
            raise EditError(f"клип {c['id']!r} заблокирован автором (locked); для правки нужен явный force=true")

    def _apply(self, show: dict, op: dict) -> str:
        if not isinstance(op, dict) or "op" not in op:
            raise EditError("операция должна быть объектом с полем op")
        k = op["op"]
        if k == "set_meta":
            show["meta"] = merge_patch(show.get("meta", {}), op["values"])
        elif k == "set_audio":
            show["audio"] = merge_patch(show.get("audio", {}), op["values"])
        elif k == "set_marker":
            mk = {"name": op["name"], **({"time": op["time"]} if "time" in op else {"bar": op["bar"], "beat": op.get("beat", 1)})}
            if "time" not in op and "bar" not in op:
                raise EditError("set_marker: нужен time или bar")
            ms = [m for m in show["audio"].setdefault("markers", []) if m["name"] != op["name"]]
            show["audio"]["markers"] = ms + [mk]
        elif k == "remove_marker":
            show["audio"]["markers"] = [m for m in show["audio"].get("markers", []) if m["name"] != op["name"]]
        elif k == "add_track":
            if not ID_RE.match(op["id"]) or any(t["id"] == op["id"] for t in show["tracks"]):
                raise EditError(f"дорожка {op['id']!r}: некорректный или уже существует")
            show["tracks"].append({"id": op["id"], "order": op.get("order", len(show["tracks"]) * 10 + 10), **({"sparse": True} if op.get("sparse") else {})})
        elif k == "remove_track":
            if any(c.get("track") == op["id"] for c in show["clips"]):
                raise EditError(f"на дорожке {op['id']!r} остались клипы")
            show["tracks"] = [t for t in show["tracks"] if t["id"] != op["id"]]
        elif k == "set_palette":
            show["palettes"][op["name"]] = {**op["colors"], **({"_source": op["source"]} if op.get("source") else {})}
        elif k == "set_asset":
            show.setdefault("assets", {})[op["name"]] = copy.deepcopy(op["data"])
        elif k == "set_look":
            show["looks"][op["name"]] = merge_patch(show["looks"].get(op["name"], {}), {x: op[x] for x in ("atoms", "palette") if x in op})
        elif k == "add_clip":
            c = copy.deepcopy(op["clip"])
            if not isinstance(c.get("id"), str) or not ID_RE.match(c["id"]):
                raise EditError(f"некорректный id клипа {c.get('id')!r}")
            if any(x.get("id") == c["id"] for x in show["clips"]):
                raise EditError(f"клип {c['id']!r} уже существует (используйте update_clip)")
            show["clips"].append(c)
        elif k == "update_clip":
            c = self._clip(show, op["id"])
            self._check_lock(c, op)
            idx = show["clips"].index(c)
            show["clips"][idx] = merge_patch(c, op["patch"])
        elif k == "remove_clip":
            c = self._clip(show, op["id"])
            self._check_lock(c, op)
            refs = [x["id"] for x in show["clips"] if x is not c and (op["id"] in (x.get("between") or []) or op["id"] in json.dumps(x.get("start", "")) + json.dumps(x.get("end", "")) + json.dumps(x.get("duration", "")))]
            if refs and not op.get("cascade"):
                raise EditError(f"на клип {op['id']!r} ссылаются {refs}; удалите их или передайте cascade=true (ссылки перестанут работать)")
            show["clips"] = [x for x in show["clips"] if x is not c and not (op.get("cascade") and op["id"] in (x.get("between") or []))]
        elif k == "move_clip":
            return self._move(show, op)
        elif k in ("lock", "unlock"):
            self._clip(show, op["id"])["locked"] = (k == "lock")
        elif k == "accept":
            targets = show["clips"] if op.get("all") else [self._clip(show, op["id"])]
            n = 0
            for c in targets:
                if c.get("status") == "proposed":
                    c["status"] = "accepted"; n += 1
            return f"accept: утверждено {n}"
        else:
            raise EditError(f"неизвестная операция {k!r}")
        return k

    def _move(self, show: dict, op: dict) -> str:
        c = self._clip(show, op["id"])
        self._check_lock(c, op)
        res = compile_show(show, self.catalog, self.base_dir)
        try:
            old = res.clip(op["id"]).nom_start
        except KeyError:
            raise EditError(f"клип {op['id']!r} не удалось вычислить; сначала исправьте его ошибки") from None
        new_start = op["start"]
        c["start"] = new_start
        moved = [op["id"]]
        if op.get("ripple"):
            res2 = compile_show(show, self.catalog, self.base_dir)
            delta = res2.clip(op["id"]).nom_start - old
            if abs(delta) > 1e-9:
                for x in show["clips"]:
                    if x is c or x.get("track") != c.get("track") or x.get("kind") == "transition" or x.get("locked"):
                        continue
                    if isinstance(x.get("start"), (int, float)) and x["start"] >= old - 1e-9:
                        x["start"] = round(x["start"] + delta, 6); moved.append(x["id"])
        return f"move_clip: сдвинуты {moved} (клипы с якорями следуют за связанными автоматически)"

    # ---- «увидеть» показ без GPU ------------------------------------------------------------------------------------------
    def storyboard(self, strict: bool = False) -> str:
        res = self.compile(strict)
        a = res.audio
        L = [f"{res.meta.get('title', 'untitled')} — {fmt_time(res.duration)} ({res.duration:.1f} с), {a.bpm:g} BPM, {a.beats_per_bar}/4"]
        if a.sections:
            L.append("Секции музыки: " + ", ".join(f"{fmt_time(s['start'])}{'/' + s['label'] if s.get('label') else ''}" for s in a.sections))
        if a.markers:
            L.append("Маркеры: " + ", ".join(f"{n}={fmt_time(t)}" for n, t in sorted(a.markers.items(), key=lambda x: x[1])))
        for tid, order in sorted(res.tracks.items(), key=lambda x: -x[1]):
            cs = [c for c in res.clips if c.track == tid]
            L.append(f"\nДорожка {tid} (order {order}):" + ("  — пусто" if not cs else ""))
            for c in sorted(cs, key=lambda c: c.eff_start):
                bar0, bar1 = a.bar(c.eff_start) + 1, a.bar(c.eff_end) + 1
                tag = ("  [proposed]" if c.status == "proposed" else "") + ("  [locked]" if c.locked else "")
                extra = ""
                if c.kind == "transition":
                    extra = f"  {c.inputs[0]} ⇒ {c.inputs[1]}"
                elif (c.eff_start, c.eff_end) != (c.nom_start, c.nom_end):
                    extra = f"  (номинал {fmt_time(c.nom_start)}–{fmt_time(c.nom_end)}, подводка)"
                L.append(f"  {fmt_time(c.eff_start)}–{fmt_time(c.eff_end)}  такт {bar0:.1f}–{bar1:.1f}  {c.id}: {c.kind}/{c.effect}{extra}{tag}")
        iss = [i for i in res.issues if i.level != "info"]
        if iss:
            L.append("\nЗамечания:")
            L += [f"  {i}" for i in iss[:20]]
        return "\n".join(L)

    def resolve_at(self, t: float) -> dict:
        res = self.compile()
        segs = plan(res, self.catalog)
        fr = evaluate_frame(res, t)
        s = segment_at(segs, t)
        a = res.audio
        return {"t": t, "bar": round(a.bar(t) + 1, 3), "beat_phase": round(a.beat_phase(t), 3), "energy": round(a.energy_at(t), 3),
                "section": a.section_index(t),
                "active": {cid: {"effect": res.clip(cid).effect, "window": [round(res.clip(cid).eff_start, 3), round(res.clip(cid).eff_end, 3)],
                                 "uProgress": round(f["uProgress"], 4), "opacity": round(f["opacity"], 4),
                                 "uniforms": {n: [round(v, 4) for v in vals] for n, vals in f["uniforms"].items()}} for cid, f in fr.items()},
                "passes": s.physical_ops() if s else [], "fbos": s.n_physical if s else 0}

    def stats(self) -> dict:
        res = self.compile()
        segs = plan(res, self.catalog)
        w, h = res.meta.get("resolution", [1920, 1080])
        return {"duration": round(res.duration, 3), "clips": len(res.clips), "tracks": len(res.tracks),
                "effects_used": sorted({c.effect for c in res.clips}), "memory": memory_report(segs, w, h),
                "errors": len(res.errors), "proposed": len([c for c in res.clips if c.status == "proposed"])}

    # ---- музыка ---------------------------------------------------------------------------------------------------------
    def import_audio(self, path: str | Path, add_markers: bool = True, beats_per_bar: int = 4) -> dict:
        path = Path(path)
        an = analyze_file(path, beats_per_bar)
        out = (self.base_dir or Path(".")) / (path.stem + ".analysis.json")
        out.write_text(json.dumps(an, ensure_ascii=False) + "\n", encoding="utf-8")
        ops: list[dict] = [{"op": "set_audio", "values": {"file": str(path), "bpm": an["bpm"], "offset": an["offset"], "beats_per_bar": beats_per_bar,
                                                          "duration": an["duration"], "analysis": out.name}}]
        if add_markers:
            ops += [{"op": "set_marker", "name": m["name"], "time": m["time"]} for m in an["markers_suggested"]]
        r = self.edit(ops)
        return {"ok": r["ok"], "analysis_file": str(out), "bpm": an["bpm"], "bpm_confidence": an["bpm_confidence"], "offset": an["offset"],
                "downbeat_confidence": an["downbeat_confidence"], "sections": an["sections"], "markers_added": [m["name"] for m in an["markers_suggested"]] if add_markers else [],
                "caveats": an["caveats"]}

    # ---- помощники подбора (предложения, не решения) --------------------------------------------------------------------
    def suggest_palette(self, feel: str, background_hint: str = "dark", temperature: str | None = None) -> dict:
        """Палитра ролей primary/accent/bg/text через Color Matrix: feel -> primary, комплемент -> accent, тёмный bg, text с контрастом >= 7.
        ВАЖНО: feel — эмоциональная метка Color Matrix, а не температура цвета (warmth может дать синий). Тёплые/холодные тона задаёт temperature."""
        if temperature not in (None, "warm", "cool"):
            return {"error": "temperature: warm | cool | не задавать"}
        if self.color is None:
            return {"error": "Color Matrix не подключён к сессии (передайте color_toolbox)"}
        cm = self.color
        q = {"feel": feel, "min_chroma": 0.08, "lightness_range": [0.45, 0.75], "count": 1}
        if temperature:
            q["temperature"] = ["warm_side"] if temperature == "warm" else ["cool_side"]
        prim = cm.dispatch("find_colors", q)
        if prim.get("error") or not prim.get("candidates"):
            return {"error": f"для feel={feel!r} не нашлось цвета: {prim.get('error') or prim.get('diagnostics')}"}
        p = prim["candidates"][0]["hex"]
        pal = cm.dispatch("build_palette", {"base": p, "scheme": "complementary", "size": 2})
        acc = pal["colors"][1]["hex"]
        light = background_hint == "light"
        bg = cm.dispatch("find_colors", {"lightness_range": [0.93, 0.98] if light else [0.08, 0.18], "max_chroma": 0.03, "count": 1})["candidates"][0]["hex"]
        txt = cm.dispatch("find_colors", {"background": bg, "min_contrast": 7, "max_chroma": 0.03, "lightness_range": [0.05, 0.25] if light else [0.88, 0.98], "count": 1})
        text = txt["candidates"][0]["hex"] if txt.get("candidates") else ("#111111" if light else "#f5f5f5")
        prof = cm.dispatch("describe_color", {"color": p})
        c1 = cm.dispatch("check_contrast", {"foreground": p, "background": bg})
        return {"palette": {"primary": p, "accent": acc, "bg": bg, "text": text},
                "source": {"tool": "color_matrix", "dataset_version": prim.get("dataset_version"), "feel": feel, "temperature": temperature, "queries": ["find_colors(feel)", "build_palette(complementary)", "find_colors(bg)", "find_colors(text, min_contrast=7)"]},
                "primary_profile": {"empathy": prof["empathy"]["score"], "empathy_label": prof["empathy"]["label"], "intensity": prof["intensity"]["score"],
                            "temperature": prof["synesthesia"]["temperature"]["word"], "oklch_hue": prof["oklch"]["h"]},
                "checks": {"primary_on_bg_contrast": c1["ratio"], "text_on_bg_contrast": cm.dispatch("check_contrast", {"foreground": text, "background": bg})["ratio"]},
                "note": "Предложение: empathy в Color Matrix — prior-оценка, не измерение; закрепите палитру командой set_palette."}

    def suggest_transitions(self, a_id: str, b_id: str) -> dict:
        """Кандидаты перехода по эвристике: перепад энергии музыки на стыке и схожесть палитр. Решает автор."""
        res = self.compile()
        try:
            a, b = res.clip(a_id), res.clip(b_id)
        except KeyError as e:
            return {"error": f"клип {e.args[0]!r} не найден"}
        cut = b.nom_start
        ea = np.mean([res.audio.energy_at(cut - x) for x in (0.5, 1.0, 1.5)])
        eb = np.mean([res.audio.energy_at(cut + x) for x in (0.5, 1.0, 1.5)])
        de = float(eb - ea)
        cands = []
        if res.audio.energy is None:
            cands.append(("crossfade", 2.0, "нет анализа музыки: безопасный по умолчанию вариант"))
        elif de > 0.3:
            cands += [("flash", 0.3, f"энергия растёт на стыке ({ea:.2f}→{eb:.2f}): акцент вспышкой"), ("glitch", 0.5, "резкий подъём, удар"), ("cut", 0.0, "жёсткий монтаж на сильную долю")]
        elif de < -0.3:
            cands += [("fade_to_black", 2.5, f"энергия падает ({ea:.2f}→{eb:.2f}): затухание"), ("crossfade", 4.0, "длинное смешивание под спад")]
        else:
            cands += [("crossfade", 2.0, f"энергия почти не меняется ({ea:.2f}→{eb:.2f})"), ("wipe", 1.0, "мягкая шторка")]
        beat = res.audio.spb
        return {"cut_time": round(cut, 3), "energy_before_after": [round(float(ea), 3), round(float(eb), 3)],
                "candidates": [{"effect": e, "duration": d, "duration_beats": round(d / beat, 2), "why": w} for e, d, w in cands],
                "note": "Эвристика по перепаду энергии; монтажное решение остаётся за автором."}

    # ---- сборка ---------------------------------------------------------------------------------------------------------
    def bake(self, out_dir: str | Path, name: str = "demo", strict: bool = False) -> dict:
        res = self.compile(strict)
        if res.errors:
            return {"ok": False, "errors": [e.to_dict() for e in res.errors]}
        segs = plan(res, self.catalog)
        b = bake(res, self.catalog, self.show, segs)
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{name}.baked.json").write_text(json.dumps(b, ensure_ascii=False) + "\n", encoding="utf-8")
        (out / f"{name}.smt").write_text(to_smt(b), encoding="utf-8")
        w, h = res.meta.get("resolution", [1920, 1080])
        return {"ok": True, "files": [str(out / f"{name}.baked.json"), str(out / f"{name}.smt")], "source_hash": b["source_hash"],
                "segments": len(b["segments"]), "memory": memory_report(segs, w, h),
                "warnings": [i.to_dict() for i in res.issues if i.level == "warning"]}
