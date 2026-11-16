# path: scripts/cyclic_dawn/pipeline_demo.py
"""Cyclic Dawn — 90s demo pipeline generator.

Build order (Uroboros → Scene Manager → motus → Cozy Engine → Color Matrix):
  1. motus.Runtime.submit(text)      — bake camera keyframes for each scene
  2. color_matrix.colorspace.rgb_to_oklch — derive accent hue from mood
  3. emit demo.smt                    — text-based scene graph for sm_runtime.hpp
  4. (C++ runtime reads demo.smt at boot, no Python needed at runtime)

Output: build/demo.smt + build/camera_bake.json (debug).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

# Real APIs in this repo:
# motus lives at /motus/motus/ — needs PYTHONPATH=/motus
# color_matrix package only exposes FullRGBMatrixReader in __init__; import colorspace directly.
import motus
from motus import LiveClock, Runtime, Transport
import importlib.util
import sys
from pathlib import Path

def _load_colorspace():
    """color_matrix package doesn't re-export colorspace; load module from path."""
    cs_path = Path(__file__).resolve().parents[2] / "color_matrix" / "output" / "color_matrix_python" / "colorspace.py"
    spec = importlib.util.spec_from_file_location("cm_colorspace", cs_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

cs = _load_colorspace()

# ─── Pipeline config ─────────────────────────────────────────────────────────
DEMO = dict(duration=90.0, fps=60, w=1280, h=720, seed=2026,
            bpm=128.0, offset=0.0, beats_per_bar=4, energy_rate=20)

@dataclass
class SceneSpec:
    sid: str
    shader: str
    start: float       # scene-only segment start (no transition overlap)
    end: float         # scene-only segment end (no transition overlap)
    mood: str
    base_rgb: Tuple[float, float, float]
    accent_rgb: Tuple[float, float, float]
    intensity: float = 1.0
    motion_speed: float = 0.8
    pulse: float = 0.0
    seed: int = 11111
    # eff_start / eff_end are computed at emit time to extend into adjacent transitions.

SCENES: List[SceneSpec] = [
    SceneSpec("dawn",  "fluid_dawn",   0.0,  33.0, "warm",
              base_rgb=(0.10, 0.05, 0.02),
              accent_rgb=(1.0,  0.55, 0.10),
              intensity=1.1, motion_speed=0.6, pulse=0.15, seed=11111),
    SceneSpec("spire", "neon_spire",  37.0,  68.0, "tense",
              base_rgb=(0.02, 0.05, 0.02),
              accent_rgb=(0.85, 1.0, 0.10),
              intensity=1.3, motion_speed=1.0, pulse=0.4, seed=33333),
    SceneSpec("fall",  "ember_fall",  72.0,  90.0, "warm",
              base_rgb=(0.03, 0.03, 0.04),
              accent_rgb=(1.0,  0.35, 0.05),
              intensity=1.0, motion_speed=0.5, pulse=0.2, seed=55555),
]

# Transitions: live in the 4s gap between scene-only segments.
# Each transition overlaps the two adjacent scenes (their clip eff_start/eff_end
# extend into the transition window so both are active during crossfade).
TRANSITIONS = [
    # (id, effect, start, end, src_a, src_b, seed)
    ("t1", "crossfade", 33.0, 37.0, "dawn",  "spire", 22222),
    ("t2", "flash",     68.0, 72.0, "spire", "fall",  44444),
]

# Post chain (same for all segments): bloom bright → blur H → blur V → add → vignette → grain
POST_CHAIN = [
    ("blm_bright", "bloom_bright", [("uThreshold", "float", [0.6]), ("uIntensity", "float", [1.0])]),
    ("blm_blurh",  "bloom_blur",   [("uDirection", "vec2",  [1.0, 0.0])]),
    ("blm_blurv",  "bloom_blur",   [("uDirection", "vec2",  [0.0, 1.0])]),
    ("blm_add",    "passthrough",  []),
    ("vig",        "vignette",     [("uStrength", "float", [0.35]), ("uSoftness", "float", [0.5])]),
    ("grn",        "grain",        [("uAmount", "float", [0.03]), ("uExposure", "float", [0.55])]),
]

OUT_DIR = Path(__file__).parent / "build"
OUT_DIR.mkdir(exist_ok=True)


# ─── 1. motus: bake camera pose per scene ────────────────────────────────────
def bake_camera() -> dict:
    """Submit a text query to motus.Runtime; sample poses at scene midpoints."""
    tr = Transport(bpm=DEMO["bpm"], offset=DEMO["offset"], beats_per_bar=DEMO["beats_per_bar"])
    rt = Runtime(transport=tr)
    # Each line: declarative motion DSL understood by motus.query.parse.
    # Syntax: anim <obj>.<channel> from=<vec> to=<vec> over=<seconds> [ease=<fn>]
    # Channels: position, position.x/y/z, rotation, scale, scale.uniform, param.<name>
    # Easings: linear, smooth, in, out, inout, step
    # motus Animator.add() defaults to stack=False — later binding on same channel
    # REPLACES earlier ones. To get sequential interpolation through multiple keyframes
    # we must use a SINGLE anim with k=<t>:<vec> keyframes (not multiple from/to anims).
    query = "\n".join([
        'new cam pos=(0,0,5) rot=(0,0,0,1)',
        # Single keyframed anim on cam.position covering the whole demo timeline.
        'anim cam.position k=0:(0,0,5) k=35:(0,1,8) k=70:(0,0.5,3) k=90:(0,0,5) ease=smooth',
        # FOV is not a built-in channel — use param.fov via keyframed anim.
        'anim cam.param.fov k=0:60 k=35:50 k=90:65 ease=smooth',
    ])
    report = rt.submit(query)
    if not report.ok:
        raise RuntimeError(f"motus submit failed: {report.issues}")

    baked = {}
    for s in SCENES:
        t_mid = (s.start + s.end) * 0.5
        plan = rt.frame(t_mid)
        cam_eid = rt.scene.find("cam")
        if cam_eid is None:
            raise RuntimeError("motus: 'cam' entity not found after submit")
        pose = rt.scene.entity(cam_eid).pose
        baked[s.sid] = {
            "t": t_mid,
            "pos": list(pose.pos),
            "rot": list(pose.rot),
            "scale": list(pose.scale),
            "items": len(plan.items),
        }
    return baked


# ─── 2. color_matrix: validate palettes via OKLch ────────────────────────────
def validate_palette(spec: SceneSpec) -> dict:
    """Confirm base/accent are in-gamut and have intended mood chroma."""
    L_base, C_base, h_base = cs.rgb_to_oklch(spec.base_rgb)
    L_acc,  C_acc,  h_acc  = cs.rgb_to_oklch(spec.accent_rgb)
    # rgb_to_oklch already returns h in DEGREES (0..360) — see lab_to_lch in colorspace.py.
    # Mood → expected hue band (degrees).
    mood_hue_band = {"warm": (20, 80), "tense": (90, 150), "melancholy": (200, 280)}
    lo, hi = mood_hue_band[spec.mood]
    in_band = lo <= h_acc <= hi
    return {
        "scene": spec.sid,
        "base_oklch":   [L_base, C_base, h_base],
        "accent_oklch": [L_acc,  C_acc,  h_acc],
        "accent_hue_deg": h_acc,
        "mood_in_band": in_band,
    }


# ─── 3. emit .smt (text format consumed by sm_runtime.hpp) ───────────────────
def fmt_float(x: float) -> str:
    """sm_runtime.hpp parses floats via std::stod; avoid scientific notation."""
    s = f"{x:.6f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _scene_eff_window(s: SceneSpec) -> Tuple[float, float]:
    """Compute clip eff_start/eff_end: scene-only window extended into adjacent transitions."""
    eff_start = s.start
    eff_end = s.end
    for tid, eff, st, en, a, b, sd in TRANSITIONS:
        if a == s.sid:
            # This scene is the source of a transition starting at st (after scene's end).
            eff_end = en
        if b == s.sid:
            # This scene is the destination of a transition ending at en (before scene's start).
            eff_start = st
    return eff_start, eff_end


def emit_clip_scene(s: SceneSpec) -> List[str]:
    eff_start, eff_end = _scene_eff_window(s)
    nom_start = s.start
    nom_dur = s.end - s.start
    L = [f"clip {s.sid} 10 scene {s.shader} {fmt_float(eff_start)} {fmt_float(eff_end)} "
         f"{fmt_float(nom_start)} {fmt_float(nom_dur)} normal {s.seed} - - 0.0"]
    L.append("prog opacity 1 n:1.0")
    L.append("prog progress 4 v:p n:0.0 n:1.0 f:clamp")
    # Pipeline uniforms (Color Matrix + motus + cyclic).
    L.append("uni uPrimaryColor vec3 3")
    L += [f"prog 1 n:{fmt_float(c)}" for c in s.base_rgb]
    L.append("uni uAccentColor vec3 3")
    L += [f"prog 1 n:{fmt_float(c)}" for c in s.accent_rgb]
    L.append(f"uni uIntensity float 1")
    L.append(f"prog 1 n:{fmt_float(s.intensity)}")
    L.append(f"uni uMotionSpeed float 1")
    L.append(f"prog 1 n:{fmt_float(s.motion_speed)}")
    L.append(f"uni uPulse float 1")
    L.append(f"prog 1 n:{fmt_float(s.pulse)}")
    L.append("endclip")
    return L


def emit_clip_transition(tid: str, effect: str, start: float, end: float,
                         src_a: str, src_b: str, seed: int) -> List[str]:
    L = [f"clip {tid} 10 transition {effect} {fmt_float(start)} {fmt_float(end)} "
         f"{fmt_float(start)} {fmt_float(end - start)} normal {seed} {src_a} {src_b} 0.0"]
    L.append("prog opacity 1 n:1.0")
    L.append("prog progress 4 n:0.0 n:1.0 v:p f:smoothstep")
    if effect == "flash":
        L.append("uni uColor vec3 3")
        L += [f"prog 1 n:1.0"] * 3
        L.append("uni uPeak float 1")
        L.append("prog 1 n:1.0")
    L.append("endclip")
    return L


def emit_clip_post(name: str, effect: str, uniforms: List[Tuple[str, str, List[float]]]) -> List[str]:
    L = [f"clip {name} 24 post {effect} 0.0 {fmt_float(DEMO['duration'])} "
         f"0.0 {fmt_float(DEMO['duration'])} normal 77000 - - 0.0"]
    L.append("prog opacity 1 n:1.0")
    L.append("prog progress 4 v:p n:0.0 n:1.0 f:clamp")
    for uname, utype, uvals in uniforms:
        L.append(f"uni {uname} {utype} {len(uvals)}")
        for v in uvals:
            L.append(f"prog 1 n:{fmt_float(v)}")
    L.append("endclip")
    return L


def emit_clip_fin() -> List[str]:
    L = [f"clip fin 30 event finish {fmt_float(DEMO['duration'])} "
         f"{fmt_float(DEMO['duration'])} {fmt_float(DEMO['duration'])} 0.0 0.0 normal 77777 - - 0.0"]
    L.append("prog opacity 1 n:1.0")
    L.append("prog progress 4 v:p n:0.0 n:1.0 f:clamp")
    L.append("endclip")
    return L


def emit_seg_scene_only(s: SceneSpec) -> List[str]:
    """Single-scene segment: RENDER scene → post chain → PRESENT."""
    L = [f"seg {fmt_float(s.start)} {fmt_float(s.end)} 8 2 5"]
    L.append(f"op RENDER {s.sid} - fbo0 - -")
    # Standard post chain.
    L.append("op POST blm_bright fbo0 fbo1 - -")
    L.append("op POST blm_blurh fbo1 fbo2 - -")
    L.append("op POST blm_blurv fbo2 fbo1 - -")
    L.append("op COMPOSITE blm_add fbo1 - fbo0 add")
    L.append("op POST vig fbo0 fbo1 - -")
    L.append("op POST grn fbo1 screen - -")
    L.append("op PRESENT - screen - - -")
    L.append("endseg")
    return L


def emit_seg_transition(tid: str, start: float, end: float,
                        src_a: str, src_b: str) -> List[str]:
    """Transition segment: RENDER both → TRANSITION → post chain → PRESENT."""
    L = [f"seg {fmt_float(start)} {fmt_float(end)} 13 3 7"]
    L.append(f"op RENDER {src_a} - fbo0 - -")
    L.append(f"op RENDER {src_b} - fbo1 - -")
    L.append(f"op TRANSITION {tid} fbo0,fbo1 fbo2 - -")
    L.append("op POST blm_bright fbo2 fbo0 - -")
    L.append("op POST blm_blurh fbo0 fbo1 - -")
    L.append("op POST blm_blurv fbo1 fbo0 - -")
    L.append("op COMPOSITE blm_add fbo0 - fbo2 add")
    L.append("op POST vig fbo2 fbo0 - -")
    L.append("op POST grn fbo0 screen - -")
    L.append("op PRESENT - screen - - -")
    L.append("endseg")
    return L


def emit_smt(camera_bake: dict) -> str:
    lines: List[str] = ["SMT 1"]
    # meta
    lines.append(f"meta {fmt_float(DEMO['duration'])} {DEMO['fps']} "
                 f"{DEMO['w']} {DEMO['h']} {DEMO['seed']}")
    # audio (bpm offset beats_per_bar energy_rate N energy_vals...)
    # For 90s @ 128bpm: ~192 beats. Use 30 sample points (energy_rate=20 → covers 1.5s of "energy" curve).
    energy = [0.10, 0.15, 0.30, 0.45, 0.55, 0.70, 0.80, 0.90, 1.00, 0.95,
              0.90, 0.85, 0.95, 1.00, 0.90, 0.80, 0.70, 0.55, 0.40, 0.30,
              0.50, 0.70, 0.85, 0.95, 1.00, 0.90, 0.75, 0.55, 0.35, 0.20]
    lines.append(f"audio {fmt_float(DEMO['bpm'])} {fmt_float(DEMO['offset'])} "
                 f"{DEMO['beats_per_bar']} {DEMO['energy_rate']} {len(energy)} "
                 + " ".join(fmt_float(e) for e in energy))
    # sections: scene start times
    section_times = [s.start for s in SCENES]
    lines.append(f"sections {len(section_times)} " + " ".join(fmt_float(t) for t in section_times))

    # clips: scenes
    for s in SCENES:
        lines += emit_clip_scene(s)
    # clips: transitions
    for tid, eff, st, en, a, b, sd in TRANSITIONS:
        lines += emit_clip_transition(tid, eff, st, en, a, b, sd)
    # clips: post
    for name, eff, uniforms in POST_CHAIN:
        lines += emit_clip_post(name, eff, uniforms)
    # clip: fin
    lines += emit_clip_fin()

    # segments: interleaved scene/transition
    # Build a sorted timeline of (start, end, kind, ref) events.
    timeline = []
    for s in SCENES:
        timeline.append((s.start, s.end, "scene", s))
    for tid, eff, st, en, a, b, sd in TRANSITIONS:
        timeline.append((st, en, "trans", (tid, a, b)))
    timeline.sort(key=lambda x: x[0])

    for st, en, kind, ref in timeline:
        if kind == "scene":
            lines += emit_seg_scene_only(ref)
        else:
            tid, a, b = ref
            lines += emit_seg_transition(tid, st, en, a, b)

    lines.append("end")
    return "\n".join(lines) + "\n"


# ─── 4. main ─────────────────────────────────────────────────────────────────
def main() -> int:
    camera = bake_camera()
    palettes = [validate_palette(s) for s in SCENES]

    # Sanity: all palettes must match their mood hue band.
    bad = [p for p in palettes if not p["mood_in_band"]]
    if bad:
        print(f"[WARN] {len(bad)} palettes outside mood band:")
        for p in bad:
            print(f"  {p['scene']}: hue={p['accent_hue_deg']:.1f}°")

    smt_text = emit_smt(camera)
    (OUT_DIR / "demo.smt").write_text(smt_text, encoding="utf-8")
    (OUT_DIR / "camera_bake.json").write_text(
        json.dumps({"camera": camera, "palettes": palettes, "demo": DEMO}, indent=2),
        encoding="utf-8")

    print(f"[OK] {OUT_DIR / 'demo.smt'} ({len(smt_text)} bytes)")
    print(f"[OK] {OUT_DIR / 'camera_bake.json'}")
    print(f"     scenes: {len(SCENES)}, transitions: {len(TRANSITIONS)}, "
          f"post-ops: {len(POST_CHAIN)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
