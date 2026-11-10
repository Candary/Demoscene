"""Пример: 6-минутное демо, собранное ТОЛЬКО через инструменты (так будет работать GLM).

Запуск из корня проекта:  python examples/build_demo.py
Нужны: output/color-matrix-full-rgb-v11.npz, output/cozy_data/ (Cozy Engine), ffmpeg (для синтетического саундтрека).
Результат в examples/out/: demo.show.json (исходник, его правят), demo.baked.json + demo.smt (для рантайма), storyboard.txt, report.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "output"))

from color_matrix_python.reader import FullRGBMatrixReader  # noqa: E402
from color_matrix_python.tools import ColorToolbox  # noqa: E402
from cozy_engine.tools import CozyToolbox  # noqa: E402
from scene_manager.effects import EffectCatalog  # noqa: E402
from scene_manager.session import ShowSession, empty_show  # noqa: E402
from scene_manager.tools import FullToolbox, ShowToolbox  # noqa: E402

OUT = ROOT / "examples" / "out"
OUT.mkdir(parents=True, exist_ok=True)


def call(tb, tool, /, **args):
    r = tb.dispatch(tool, args)
    if "error" in r or r.get("ok") is False:
        raise SystemExit(f"{tool} -> {json.dumps(r, ensure_ascii=False)[:600]}")
    return r


def main() -> dict:
    # --- подключение систем ---------------------------------------------------------------------------------------------
    color = ColorToolbox(FullRGBMatrixReader(ROOT / "output" / "color-matrix-full-rgb-v11.npz"))
    cozy = CozyToolbox.from_dir(ROOT / "output" / "cozy_data", color)
    session = ShowSession(empty_show("Directed Timeline — пример, 6 минут", resolution=(1920, 1080), fps=60, seed=2026),
                          EffectCatalog.from_dir(ROOT / "examples" / "effects"), OUT, color_toolbox=color)
    tb = FullToolbox(ShowToolbox(session, autosave=OUT / "demo.show.json"), color, cozy)
    print(f"Инструментов у агента: {len(tb.schemas)} (Scene Manager {len(tb.show._tools)} + Color Matrix + Cozy Engine)")

    # --- 1. музыка -------------------------------------------------------------------------------------------------------
    mp3 = OUT / "soundtrack.mp3"
    if not mp3.exists():
        subprocess.run([sys.executable, str(ROOT / "examples" / "make_soundtrack.py"), str(mp3)], check=True)
    an = call(tb, "analyze_audio", path=str(mp3), add_markers=False)
    print(f"Анализ: {an['bpm']} BPM (уверенность {an['bpm_confidence']}), первая доля {an['offset']} с, секций {len(an['sections'])}")
    print("  найденные секции:", [(s["start"], s.get("label")) for s in an["sections"]])

    # Опорные маркеры задаём по тактам (структуру автор знает); анализ служит проверкой.
    bars = {"intro": 1, "build1": 25, "drop1": 33, "breakdown": 73, "build2": 97, "drop2": 105, "climax": 153, "outro": 169, "end": 193}
    call(tb, "edit_show", ops=[{"op": "set_marker", "name": n, "bar": b} for n, b in bars.items()])
    spb = 60.0 / an["bpm"]
    found = {round((s["start"] - an["offset"]) / (4 * spb) + 1) for s in an["sections"]}
    print("  опорные маркеры подтверждены анализом:", sorted(b for b in bars.values() if b in found), "| не подтверждены:", sorted(b for b in bars.values() if b not in found and b not in (1, 193)))

    # --- 2. палитры через Color Matrix (закрепляем: pinned) -------------------------------------------------------------------
    pal_ops = []
    # feel — эмоциональная метка Color Matrix; тёплый/холодный тон автор задаёт отдельно (warmth ≠ тёплый цвет)
    for name, feel, temp in [("tense", "tension", "warm"), ("euphoric", "delight", None), ("cozy", "warmth", "warm"), ("calm", "neutral", "cool")]:
        p = call(tb, "suggest_palette", feel=feel, background_hint="dark", **({"temperature": temp} if temp else {}))
        pal_ops.append({"op": "set_palette", "name": name, "colors": p["palette"], "source": p["source"]})
        pr = p["primary_profile"]
        print(f"  палитра {name:9s} feel={feel:8s} temp={temp or '-':5s} primary={p['palette']['primary']} ({pr['temperature']}, hue {pr['oklch_hue']:.0f}°, empathy {pr['empathy']:.0f}) text/bg {p['checks']['text_on_bg_contrast']}:1")
    call(tb, "edit_show", ops=pal_ops + [
        {"op": "set_look", "name": "tense", "palette": "tense", "atoms": {"temperature": 3}},
        {"op": "set_look", "name": "euphoric", "palette": "euphoric", "atoms": {"temperature": 2}},
        {"op": "set_look", "name": "cozy", "palette": "cozy", "atoms": {"temperature": 3}},
        {"op": "set_look", "name": "calm", "palette": "calm", "atoms": {"temperature": 1}},
        {"op": "set_meta", "values": {"budget": 14}}])

    # --- 3. объекты и примитивы из Cozy Engine -> ассет для SDF-эффекта ----------------------------------------------------------
    plan = cozy.dispatch("cozy_scene_plan", {"room": "living_room", "count": 6})
    room_pal = cozy.dispatch("cozy_palette", {"room": "living_room"})
    placements = [
        {"object": "rug", "x": 0.0, "z": -0.4}, {"object": "sofa", "x": 0.0, "z": -1.7}, {"object": "coffee_table", "x": 0.0, "z": -0.4},
        {"object": "armchair", "x": -1.9, "z": -0.2, "rotation_y_deg": -65}, {"object": "lamp", "x": 1.9, "z": -1.9},
        {"object": "plant", "x": 2.1, "z": 1.2}, {"object": "bookshelf", "x": -2.05, "z": -1.95},
        {"object": "cushion", "x": -0.6, "z": -1.65, "elevation": 0.52}, {"object": "cushion", "x": 0.6, "z": -1.65, "elevation": 0.52, "rotation_y_deg": 20},
        {"recipe": "lamp_table", "object": "lamp", "x": 0.2, "z": -0.4, "elevation": 0.42}, {"object": "artwork", "x": 0.0, "z": -2.2},
    ]
    asset = call(tb, "build_cozy_asset", name="living_room", placements=placements, slot_colors=room_pal["slot_colors"], room_size=[5.0, 4.5])
    print(f"  Cozy Engine: объекты по ассоциациям с «cozy» в подписях: {[o['object'] for o in plan['objects']]}; ассет: {asset['parts']} примитивов, "
          f"проверка расстановки ok={asset['layout_check']['ok']}")

    # --- 4. дорожки и клипы (якоря: маркеры и такты, а не секунды) ------------------------------------------------------------------
    M = lambda n, **k: {"marker": n, **k}  # noqa: E731
    scenes = [  # id, effect, начало (якорь), конец (якорь), look, атомы, map
        ("intro", "anxiety_mist", 0, M("build1"), "tense", {"energy": {"expr": "0.25 + 0.6 * audio.energy"}}, {}),
        ("build1", "particle_swarm", M("build1"), M("drop1"), "tense", {"energy": {"keys": [[0, 0.3], [15, 1.0, "ease_in"]]}}, {}),
        ("drop1a", "nebula_raymarch", M("drop1"), M("drop1", offset_bars=20), "euphoric", {"energy": {"expr": "0.4 + 0.8 * audio.energy"}}, {}),
        ("drop1b", "morph_grid", {"end_of": "drop1a"}, M("breakdown"), "euphoric", {"energy": {"expr": "0.3 + audio.energy"}}, {}),
        ("room", "cozy_room_sdf", M("breakdown"), M("build2"), "cozy", {"energy": 0.3}, {"uPrimitives": {"asset": "living_room"}}),
        ("build2", "particle_swarm", M("build2"), M("drop2"), "tense", {"energy": {"keys": [[0, 0.4], [15, 1.0, "smoothstep"]]}}, {}),
        ("drop2a", "nebula_raymarch", M("drop2"), M("drop2", offset_bars=24), "euphoric", {"energy": {"expr": "0.5 + 0.8 * audio.energy"}}, {}),
        ("drop2b", "morph_grid", {"end_of": "drop2a"}, M("climax"), "euphoric", {"energy": {"expr": "0.4 + audio.energy"}}, {}),
        ("climax", "sphere_scene", M("climax"), M("outro"), "euphoric", {"energy": 1.0}, {}),
        ("outro", "nebula_raymarch", M("outro"), M("end"), "calm", {"energy": {"keys": [[0, 0.6], [45, 0.1, "smoothstep"]]}}, {}),
    ]
    ops = [{"op": "add_track", "id": "main", "order": 10}, {"op": "add_track", "id": "post", "order": 25}, {"op": "add_track", "id": "overlay", "order": 30}]
    for cid, eff, a, b, look, atoms, mp in scenes:
        ops.append({"op": "add_clip", "clip": {"id": cid, "track": "main", "kind": "scene", "effect": eff, "start": a, "end": b, "look": look, "atoms": atoms,
                                                  **({"map": mp} if mp else {})}})
    call(tb, "edit_show", ops=ops)

    # переходы: кандидаты по перепаду энергии на каждом стыке; автор (скрипт) берёт первый вариант, округляя до целых долей
    tr_ops, picks = [], []
    for (a_id, *_), (b_id, *_) in zip(scenes, scenes[1:]):
        sug = call(tb, "suggest_transitions", a=a_id, b=b_id)
        c = sug["candidates"][0]
        picks.append((a_id, b_id, c["effect"], c["duration_beats"]))
        tr_ops.append({"op": "add_clip", "clip": {"id": f"t_{a_id}_{b_id}", "kind": "transition", "effect": c["effect"], "between": [a_id, b_id],
                                                  "duration": {"beats": max(0, round(c["duration_beats"]))}, "status": "proposed"}})
    call(tb, "edit_show", ops=tr_ops)
    print("  переходы (предложены эвристикой по энергии):", [(f"{a}⇒{b}", e, d) for a, b, e, d in picks])

    # пост-обработка под титрами, титры сверху; конец показа — событие finish
    call(tb, "edit_show", ops=[
        {"op": "add_clip", "clip": {"id": "bloom", "track": "post", "kind": "post", "effect": "bloom", "start": 0, "end": M("end"), "map": {"uIntensity": "0.4 + 0.6 * audio.energy"}}},
        {"op": "add_clip", "clip": {"id": "grain", "track": "post", "kind": "post", "effect": "grain", "start": 0, "end": M("end")}},
        {"op": "add_clip", "clip": {"id": "vignette", "track": "post", "kind": "post", "effect": "vignette", "start": 0, "end": M("end")}},
        {"op": "add_clip", "clip": {"id": "credits", "track": "overlay", "kind": "overlay", "effect": "credits", "start": M("end", offset=-16), "end": M("end"), "palette": "calm"}},
        {"op": "add_clip", "clip": {"id": "finish", "track": "post", "kind": "event", "effect": "finish", "start": M("end")}}])

    # --- 5. проверка, утверждение, сборка --------------------------------------------------------------------------------------------
    lint = tb.dispatch("lint", {"strict": True})
    print("lint (strict, до утверждения):", [e["code"] for e in lint["errors"]][:3], "...", f"{len(lint['errors'])} ошибок (ожидаемо: переходы ещё proposed)")
    call(tb, "edit_show", ops=[{"op": "accept", "all": True}])
    lint = tb.dispatch("lint", {"strict": True})
    print("lint (strict, после утверждения): ошибок", len(lint["errors"]), "| предупреждений", len(lint["warnings"]), [w["code"] for w in lint["warnings"]])
    overview = call(tb, "show_overview")
    (OUT / "storyboard.txt").write_text(overview["storyboard"] + "\n", encoding="utf-8")
    baked = call(tb, "bake", out_dir=str(OUT), name="demo")
    print("bake:", {k: baked[k] for k in ("segments", "source_hash")}, "память:", baked["memory"]["peak_fbos"], "FBO,", baked["memory"]["peak_fbo_megabytes"], "МБ")

    # --- 6. гибкость: перемонтаж одной правкой ---------------------------------------------------------------------------------------
    before = {c: session.compile().clip(c).eff_start for c in ("drop1a", "drop1b", "room", "credits", "bloom")}
    call(tb, "edit_show", ops=[{"op": "set_marker", "name": "drop1", "bar": 37}])   # сдвинуть первый дроп на 4 такта позже
    after = {c: session.compile().clip(c).eff_start for c in before}
    print("\nПеремонтаж: drop1 с такта 33 на 37 (одна операция). Начала клипов:")
    for c in before:
        print(f"  {c:8s} {before[c]:7.2f} -> {after[c]:7.2f} с {'(следует за маркером)' if abs(before[c] - after[c]) > 1e-6 else '(не зависит от drop1)'}")
    call(tb, "history", action="undo")
    # смена настроения секции: другая палитра для look → перекрашиваются все клипы этого look
    cs = session.compile()
    c0 = cs.clip("room").uniforms["uLightColor"][1][0].rpn[0][1]
    call(tb, "edit_show", ops=[{"op": "set_look", "name": "cozy", "palette": "calm"}])
    c1 = session.compile().clip("room").uniforms["uLightColor"][1][0].rpn[0][1]
    print(f"Смена настроения: look 'cozy' -> палитра 'calm': uLightColor.r комнаты {c0:.3f} -> {c1:.3f}")
    call(tb, "history", action="undo")

    report = {"stats": session.stats(), "lint": lint, "transitions": picks, "audio": {k: an[k] for k in ("bpm", "offset", "bpm_confidence", "downbeat_confidence")}}
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    session.save(OUT / "demo.show.json")
    return report


if __name__ == "__main__":
    main()
