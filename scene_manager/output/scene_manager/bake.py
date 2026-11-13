"""Запекание: ResolvedShow + план графа -> demo.baked.json (канон) и demo.smt (плоский текст для C++ без JSON-библиотек).

В запечённом файле нет ни атомов, ни палитр, ни якорей, ни ссылок на маркеры: только абсолютные времена, константы и RPN-программы
от переменных t, p, dur, time, audio.*. Поэтому рантайм детерминирован, seek точен для любого T, и Python/LLM в рантайме не нужны.
Эталонный вычислитель evaluate_frame() — «золотой» источник значений: C++ реализация (runtime_ref) обязана совпасть с ним.
"""
from __future__ import annotations

import hashlib
import json

from .audio import ENERGY_RATE
from .effects import EffectCatalog
from .expr import eval_rpn, rpn_to_tokens
from .graph import Segment, plan
from .timeline import EPS, RClip, ResolvedShow

BAKED_FORMAT = "scene-manager-baked/1"


def source_hash(show: dict) -> str:
    return hashlib.sha256(json.dumps(show, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def bake(res: ResolvedShow, cat: EffectCatalog, show: dict | None = None, segs: list[Segment] | None = None) -> dict:
    if res.errors:
        raise ValueError("нельзя запечь показ с ошибками: " + "; ".join(str(e) for e in res.errors[:5]))
    segs = segs if segs is not None else plan(res, cat)
    a = res.audio
    clips = []
    for c in res.clips:
        ef = cat.get(c.effect)
        clips.append({
            "id": c.id, "track_order": c.track_order, "kind": c.kind, "effect": c.effect,
            "eff_start": c.eff_start, "eff_end": c.eff_end, "nom_start": c.nom_start, "nom_dur": c.nom_dur,
            "blend": c.blend, "seed": c.seed, "inputs": list(c.inputs), "prewarm_start": c.prewarm_start,
            "opacity": rpn_to_tokens(c.opacity.rpn) if c.opacity else ["n:1.0"],
            "progress": rpn_to_tokens(c.progress.rpn),
            "uniforms": [{"name": n, "type": t, "programs": [rpn_to_tokens(x.rpn) for x in comps]} for n, (t, comps) in c.uniforms.items()],
            "arrays": [{"name": n, "values": v} for n, v in c.arrays.items()],
        })
    used = sorted({c.effect for c in res.clips})
    return {
        "format": BAKED_FORMAT,
        "source_hash": source_hash(show) if show is not None else None,
        "meta": {"title": res.meta.get("title"), "duration": res.duration, "fps": res.meta.get("fps", 60),
                 "resolution": res.meta.get("resolution", [1920, 1080]), "seed": res.meta.get("seed", 0)},
        "audio": {"file": a.file, "bpm": a.bpm, "offset": a.offset, "beats_per_bar": a.beats_per_bar, "energy_rate": ENERGY_RATE,
                  "energy": [] if a.energy is None else [float(x) for x in a.energy],   # без округления: C++ обязан совпасть с Python при любых данных
                  "section_starts": [s["start"] for s in a.sections]},
        "effects": {e: {"kind": cat.get(e).kind, "shader": cat.get(e).shader, "cost": cat.get(e).cost} for e in used},
        "clips": clips,
        "segments": [{"start": s.start, "end": s.end, "cost": s.cost, "fbos": s.n_physical, "ops": s.physical_ops()} for s in segs],
        "provenance": {"palettes": res.palettes},
    }


def _num(x: float) -> str:
    return repr(float(x))


def to_smt(b: dict) -> str:
    """Плоский текстовый формат для C++ (строки из токенов без пробелов внутри)."""
    L = ["SMT 1"]
    m, a = b["meta"], b["audio"]
    L.append(f"meta {_num(m['duration'])} {m['fps']} {m['resolution'][0]} {m['resolution'][1]} {m['seed']}")
    L.append(f"audio {_num(a['bpm'])} {_num(a['offset'])} {a['beats_per_bar']} {_num(a['energy_rate'])} {len(a['energy'])} " + " ".join(_num(x) for x in a["energy"]))
    L.append(f"sections {len(a['section_starts'])} " + " ".join(_num(x) for x in a["section_starts"]))
    for c in b["clips"]:
        ins = (c["inputs"] + ["-", "-"])[:2] if c["inputs"] else ["-", "-"]
        L.append(f"clip {c['id']} {c['track_order']} {c['kind']} {c['effect']} {_num(c['eff_start'])} {_num(c['eff_end'])} {_num(c['nom_start'])} "
                 f"{_num(c['nom_dur'])} {c['blend']} {c['seed']} {ins[0]} {ins[1]} {_num(c['prewarm_start'])}")
        L.append(f"prog opacity {len(c['opacity'])} " + " ".join(c["opacity"]))
        L.append(f"prog progress {len(c['progress'])} " + " ".join(c["progress"]))
        for u in c["uniforms"]:
            L.append(f"uni {u['name']} {u['type']} {len(u['programs'])}")
            for p in u["programs"]:
                L.append(f"prog {len(p)} " + " ".join(p))
        for ar in c["arrays"]:
            L.append(f"arr {ar['name']} {len(ar['values'])} " + " ".join(_num(x) for x in ar["values"]))
        L.append("endclip")
    for s in b["segments"]:
        L.append(f"seg {_num(s['start'])} {_num(s['end'])} {s['cost']} {s['fbos']} {len(s['ops'])}")
        for o in s["ops"]:
            reads = ",".join(o.get("reads", [])) or "-"
            L.append(f"op {o['op']} {o.get('clip', '-')} {reads} {o.get('write', '-')} {o.get('dest', '-')} {o.get('blend', '-')}")
        L.append("endseg")
    L.append("end")
    return "\n".join(L) + "\n"


# ---- эталонное вычисление кадра -----------------------------------------------------------------------------------------
def _tokens_to_rpn(tokens: list[str]):
    out = []
    for t in tokens:
        k, v = t.split(":", 1)
        out.append((k, float(v) if k == "n" else v))
    return tuple(out)


def evaluate_frame(res: ResolvedShow, T: float) -> dict[str, dict]:
    """{clip_id: {uTime, uProgress, opacity, uniforms:{имя:[значения]}}} для всех активных в момент T клипов."""
    out = {}
    for c in res.active(T):
        env = res.env_at(c, T)
        out[c.id] = {
            "uTime": T - c.eff_start, "uProgress": eval_rpn(c.progress.rpn, env),
            "opacity": eval_rpn(c.opacity.rpn, env) if c.opacity else 1.0,
            "uniforms": {n: [eval_rpn(x.rpn, env) for x in comps] for n, (t, comps) in c.uniforms.items()},
        }
    return out


def segment_at(segs: list[Segment], T: float) -> Segment | None:
    for s in segs:
        if s.start - EPS <= T < s.end - EPS:
            return s
    return segs[-1] if segs and abs(T - segs[-1].end) < EPS else None


def golden_lines(res: ResolvedShow, segs: list[Segment], times: list[float]) -> str:
    """Текст для сверки с C++: по каждому T — активные клипы со значениями и план сегмента. Формат фиксирован."""
    L = []
    for T in times:
        L.append(f"T {T!r}")
        fr = evaluate_frame(res, T)
        for cid in sorted(fr):
            f = fr[cid]
            u = " ".join(f"{n}=" + ",".join(f"{v:.9g}" for v in vals) for n, vals in sorted(f["uniforms"].items()))
            L.append(f"clip {cid} uTime={f['uTime']:.9g} uProgress={f['uProgress']:.9g} opacity={f['opacity']:.9g} {u}".rstrip())
            for an, av in sorted(res.clip(cid).arrays.items()):
                L.append(f"arr {cid} {an} n={len(av)} sum={sum(av):.9g}")
        s = segment_at(segs, T)
        if s:
            L.append(f"plan fbos={s.n_physical}")
            for o in s.physical_ops():
                L.append("  op " + " ".join(f"{o.get('op')} {o.get('clip', '-')} {','.join(o.get('reads', [])) or '-'} {o.get('write', '-')} {o.get('dest', '-')} {o.get('blend', '-')}".split()))
    return "\n".join(L) + "\n"
