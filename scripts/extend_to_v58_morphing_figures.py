#!/usr/bin/env python3
"""v58: extend v55 (6 scenes 180s) with morphing_figures scene (30s) + 1s crossfade.

New timeline (211s total):
  T=0-180    existing v55 demo (6 scenes + transitions + post)
  T=180-181  t6 crossfade (1s, cozy_room → morphing_figures)
  T=181-211  s7 morphing_figures (30s, ported from preview.html)

All v55 scenes (s1-s6) keep their timing. We only:
- Extend post clips (blm, vig, grn) from 180s to 211s
- Extend s6 (cozy_room_sdf) eff_end from 180 to 181 (for crossfade overlap)
- Add t6 crossfade clip (1s duration, centered on T=180.5)
- Add s7 morphing_figures clip (30s, no custom uniforms)
- Update fin event to T=211
- Add 2 new segments (transition + simple for s7)
- Extend energy array from 45 to 53 samples (211s / 4s per sample)
"""
from pathlib import Path

NEW_DURATION = 211.0
NEW_SECTIONS = [0.0, 27.0, 77.0, 127.0, 181.0]  # +181 for new scene boundary
NEW_ENERGY_RATE = 0.25  # 4s per sample → 53 samples for 211s (211/4 = 52.75)
# 53 samples covering 211s (45 from v55 + 8 new for 31 extra seconds)
NEW_ENERGY = [
    # 0-28s: nebula intro buildup (7 samples)
    0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.55,
    # 28-52s: sphere growing (6 samples)
    0.60, 0.70, 0.78, 0.82, 0.85, 0.88,
    # 52-76s: particle_swarm peak (6 samples)
    0.92, 0.98, 1.00, 1.00, 0.98, 0.92,
    # 76-100s: anxiety_mist sustained high (6 samples)
    0.85, 0.90, 0.95, 0.92, 0.88, 0.85,
    # 100-124s: morph_grid peak (6 samples)
    0.92, 1.00, 1.00, 0.98, 0.92, 0.85,
    # 124-176s: cozy_room fadeout (13 samples, was 14 — trimmed by 1)
    0.78, 0.70, 0.62, 0.55, 0.48, 0.40,
    0.33, 0.27, 0.22, 0.18, 0.15, 0.12, 0.10,
    # 176-180s: cozy_room tail (1 sample)
    0.08,
    # 180-211s: morphing_figures finale — gradual build to mid-energy (8 samples)
    0.20, 0.30, 0.40, 0.50, 0.55, 0.50, 0.45, 0.40,
]
assert len(NEW_ENERGY) == 53, f"energy length {len(NEW_ENERGY)}, expected 53"

# Clip timing (id → eff_start, eff_end, nom_start, nom_dur, prewarm, in_a, in_b)
CLIP_TIMING = {
    # v55 scenes (unchanged except s6 eff_end extended by 1s for crossfade)
    "s1":  (0.0,   27.0,  0.0,   25.0, 0.0, "-",  "-"),
    "t1":  (23.0,  27.0,  23.0,  4.0,  0.0, "s1", "s2"),
    "s2":  (23.0,  52.0,  25.0,  25.0, 2.0, "-",  "-"),
    "t2":  (48.0,  52.0,  48.0,  4.0,  0.0, "s2", "s3"),
    "s3":  (48.0,  77.0,  50.0,  25.0, 2.0, "-",  "-"),
    "t3":  (73.0,  77.0,  73.0,  4.0,  0.0, "s3", "s4"),
    "s4":  (73.0,  102.0, 75.0,  25.0, 2.0, "-",  "-"),
    "t4":  (98.0,  102.0, 98.0,  4.0,  0.0, "s4", "s5"),
    "s5":  (98.0,  127.0, 100.0, 25.0, 2.0, "-",  "-"),
    "t5":  (123.0, 127.0, 123.0, 4.0,  0.0, "s5", "s6"),
    "s6":  (123.0, 181.0, 125.0, 55.0, 2.0, "-",  "-"),   # eff_end extended 180→181
    # v58 new: t6 crossfade (1s) + s7 morphing_figures (30s)
    "t6":  (180.0, 181.0, 180.0, 1.0,  0.0, "s6", "s7"),  # 1s crossfade
    "s7":  (180.0, 211.0, 181.0, 30.0, 1.0, "-",  "-"),   # 30s new scene
    # Post chain (extended 180→211)
    "vig": (0.0,   211.0, 0.0,   211.0, 0.0, "-", "-"),
    "blm": (0.0,   211.0, 0.0,   211.0, 0.0, "-", "-"),
    "grn": (0.0,   211.0, 0.0,   211.0, 0.0, "-", "-"),
    "fin": (211.0, 211.0, 0.0,   0.0,   0.0, "-", "-"),
}

# Clip static metadata (track_order, kind, effect, blend, seed)
CLIP_STATIC = {
    "s1":  (10, "scene",      "nebula_raymarch", "normal", "11111"),
    "s2":  (10, "scene",      "sphere_scene",    "normal", "22222"),
    "s3":  (10, "scene",      "particle_swarm",  "normal", "33333"),
    "s4":  (10, "scene",      "anxiety_mist",    "normal", "44444"),
    "s5":  (10, "scene",      "morph_grid",      "normal", "55555"),
    "s6":  (10, "scene",      "cozy_room_sdf",   "normal", "66666"),
    "s7":  (10, "scene",      "morphing_figures","normal", "77777"),  # NEW
    "t1":  (10, "transition", "crossfade",       "normal", "10101"),
    "t2":  (10, "transition", "flash",           "normal", "20202"),
    "t3":  (10, "transition", "crossfade",       "normal", "30303"),
    "t4":  (10, "transition", "flash",           "normal", "40404"),
    "t5":  (10, "transition", "crossfade",       "normal", "50505"),
    "t6":  (10, "transition", "crossfade",       "normal", "60606"),  # NEW
    "vig": (25, "post",       "vignette",        "normal", "99001"),
    "blm": (24, "post",       "bloom",           "normal", "77007"),
    "grn": (26, "post",       "grain",           "normal", "88008"),
    "fin": (30, "event",      "finish",          "normal", "77777"),
}

# Per-clip uniform definitions (same as v55 for s1-s6, empty for s7).
CLIP_UNIFORMS = {
    "s1": [
        ("uPrimaryColor", "vec3", ["0.05", "0.10", "0.30"]),
        ("uAccentColor",  "vec3", ["0.20", "0.60", "0.90"]),
        ("uIntensity",    "float", ["0.8"]),
        ("uMotionSpeed",  "float", ["1.0"]),
        ("uPulse",        "float", ["0.0"]),
    ],
    "s2": [
        ("uColor",  "vec3", ["0.1", "0.5", "0.8"]),
        ("uGlow",   "float", ["1.2"]),
        ("uOrbit",  "float", ["0.0"]),
    ],
    "s3": [
        ("uColor",    "vec3", ["0.95", "0.2", "0.55"]),
        ("uSwarm",    "float", ["0.7"]),
        ("uBeatKick", "float", ["0.0"]),
    ],
    "s4": [
        ("uPrimaryColor", "vec3", ["0.25", "0.05", "0.10"]),
        ("uAccentColor",  "vec3", ["0.80", "0.15", "0.10"]),
        ("uIntensity",    "float", ["1.2"]),
        ("uMotionSpeed",  "float", ["1.5"]),
        ("uWarmth",       "float", ["0.85"]),
    ],
    "s5": [
        ("uColor",  "vec3", ["0.30", "0.60", "0.90"]),
        ("uMorph",  "float", ["0.5"]),
        ("uSpeed",  "float", ["1.0"]),
    ],
    "s6": [
        ("uLightColor", "vec3", ["1.0", "0.85", "0.6"]),
        ("uCamAngle",   "float", ["0.4"]),
    ],
    "s7": [],  # morphing_figures — no custom uniforms (uses only standard ones)
    "t1": [], "t2": [], "t3": [], "t4": [], "t5": [], "t6": [],
    "vig": [
        ("uStrength", "float", ["0.35"]),
        ("uSoftness", "float", ["0.5"]),
    ],
    "blm": [
        ("uThreshold", "float", ["0.6"]),
        ("uIntensity", "float", ["1.0"]),
        ("uRadius",    "float", ["4.0"]),
    ],
    "grn": [
        ("uAmount", "float", ["0.20"]),
    ],
    "fin": [],
}

DEFAULT_PROG_PROGRESS = [("v:p",), ("n:0.0",), ("n:1.0",), ("f:clamp",)]
TRANSITION_PROG_PROGRESS = [("n:0.0",), ("n:1.0",), ("v:p",), ("f:smoothstep",)]

# Cozy room primitives (10 prims × 12 floats = 120 floats).
COZY_PRIMITIVES = [
    (0, 0,  5.0, 0.1, 5.0,    0.0, -1.5,  0.0,  0.0,  0.80, 0.70, 0.50),
    (0, 0,  5.0, 3.0, 0.1,    0.0,  0.0, -2.5,  0.0,  0.40, 0.30, 0.25),
    (0, 0,  0.1, 3.0, 5.0,   -2.5,  0.0,  0.0,  0.0,  0.50, 0.35, 0.25),
    (0, 0,  0.1, 3.0, 5.0,    2.5,  0.0,  0.0,  0.0,  0.50, 0.35, 0.25),
    (0, 0,  1.5, 0.1, 1.0,    0.0, -0.5,  0.0,  0.0,  0.40, 0.25, 0.15),
    (1, 0,  0.20, 0.20, 0.20, 0.0,  0.10, 0.0,  0.0,  1.00, 0.85, 0.40),
    (2, 0,  0.08, 0.10, 0.08, 0.5, -0.42, 0.3,  0.0,  0.90, 0.90, 0.95),
    (0, 0,  0.30, 0.05, 0.40, -0.4, -0.43, 0.2,  0.3,  0.70, 0.20, 0.20),
    (2, 0,  0.15, 0.25, 0.15, -1.8, -1.20, 1.5,  0.0,  0.55, 0.30, 0.20),
    (0, 0,  1.5, 1.5, 0.05,    2.4,  0.30, -1.0, 0.0,  0.70, 0.85, 1.00),
]
assert len(COZY_PRIMITIVES) == 10
assert all(len(p) == 12 for p in COZY_PRIMITIVES)

# Segments (13 segments: 11 from v55 + 2 new for t6/s7)
NEW_SEGMENTS = []
seg_defs = [
    (0.0,   23.0,  "simple",     "s1", None),
    (23.0,  27.0,  "transition", "s1", "t1", "s2"),
    (27.0,  48.0,  "simple",     "s2", None),
    (48.0,  52.0,  "transition", "s2", "t2", "s3"),
    (52.0,  73.0,  "simple",     "s3", None),
    (73.0,  77.0,  "transition", "s3", "t3", "s4"),
    (77.0,  98.0,  "simple",     "s4", None),
    (98.0,  102.0, "transition", "s4", "t4", "s5"),
    (102.0, 123.0, "simple",     "s5", None),
    (123.0, 127.0, "transition", "s5", "t5", "s6"),
    (127.0, 180.0, "simple",     "s6", None),
    # v58 new:
    (180.0, 181.0, "transition", "s6", "t6", "s7"),   # 1s crossfade
    (181.0, 211.0, "simple",     "s7", None),          # 30s morphing_figures
]

for seg in seg_defs:
    if seg[2] == "simple":
        start, end, _, scene_id, _ = seg
        ops = [
            ("RENDER",  scene_id, "-",        "fbo0",  "-", "-"),
            ("POST",    "blm",    "fbo0",     "fbo1",  "-", "-"),
            ("POST",    "vig",    "fbo1",     "fbo2",  "-", "-"),
            ("POST",    "grn",    "fbo2",     "screen","-", "-"),
            ("PRESENT", "-",      "screen",   "-",     "-", "-"),
        ]
        NEW_SEGMENTS.append((start, end, 5, 3, ops))
    else:
        start, end, _, scene_a, t_id, scene_b = seg
        ops = [
            ("RENDER",     scene_a, "-",        "fbo0",  "-", "-"),
            ("RENDER",     scene_b, "-",        "fbo1",  "-", "-"),
            ("TRANSITION", t_id,    "fbo0,fbo1","fbo2",  "-", "-"),
            ("POST",       "blm",   "fbo2",     "fbo3",  "-", "-"),
            ("POST",       "vig",   "fbo3",     "fbo4",  "-", "-"),
            ("POST",       "grn",   "fbo4",     "screen","-", "-"),
            ("PRESENT",    "-",     "screen",   "-",     "-", "-"),
        ]
        NEW_SEGMENTS.append((start, end, 7, 5, ops))


def emit_clip(cid):
    track, kind, effect, blend, seed = CLIP_STATIC[cid]
    es, ee, ns, nd, pw, in_a, in_b = CLIP_TIMING[cid]
    lines = [f"clip {cid} {track} {kind} {effect} "
             f"{es:.1f} {ee:.1f} {ns:.1f} {nd:.1f} {blend} {seed} {in_a} {in_b} {pw:.1f}"]
    lines.append(f"prog 1 n:1.0")  # opacity = 1.0
    if kind == "transition":
        toks = " ".join(t[0] for t in TRANSITION_PROG_PROGRESS)
        lines.append(f"prog {len(TRANSITION_PROG_PROGRESS)} {toks}")
    elif kind == "event":
        lines.append(f"prog 1 n:0.0")
    else:
        toks = " ".join(t[0] for t in DEFAULT_PROG_PROGRESS)
        lines.append(f"prog {len(DEFAULT_PROG_PROGRESS)} {toks}")
    for uname, utype, vals in CLIP_UNIFORMS[cid]:
        lines.append(f"uni {uname} {utype} {len(vals)}")
        for v in vals:
            lines.append(f"prog 1 n:{v}")
    if cid == "s6":
        flat = []
        for prim in COZY_PRIMITIVES:
            flat.extend(f"{x:.4f}" for x in prim)
        lines.append(f"arr uPrimitives {len(flat)} " + " ".join(flat))
    lines.append("endclip")
    return lines


def build_smt():
    out = ["SMT 1",
           f"meta {NEW_DURATION:.1f} 60 1280 720 2026",
           f"audio 128.0 0.0 4 {NEW_ENERGY_RATE} {len(NEW_ENERGY)} " +
           " ".join(f"{e:.2f}" for e in NEW_ENERGY),
           f"sections {len(NEW_SECTIONS)} " + " ".join(f"{s:.1f}" for s in NEW_SECTIONS)]
    clip_order = ["s1", "s2", "s3", "s4", "s5", "s6", "s7",
                  "t1", "t2", "t3", "t4", "t5", "t6",
                  "blm", "vig", "grn", "fin"]
    for cid in clip_order:
        out.extend(emit_clip(cid))
    for seg in NEW_SEGMENTS:
        start, end, cost, fbos, ops = seg
        out.append(f"seg {start:.1f} {end:.1f} {cost} {fbos} {len(ops)}")
        for op in ops:
            out.append(f"op {op[0]} {op[1]} {op[2]} {op[3]} {op[4]} {op[5]}")
        out.append("endseg")
    out.append("end")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    smt_text = build_smt()
    dst = Path("/home/z/my-project/download/demo_intro_v58/demo.smt")
    dst.write_text(smt_text)
    print(f"[OK] wrote v58 demo.smt (7 scenes, 211s, 17 clips, 13 segments)")
    print(f"     {len(smt_text.splitlines())} lines, {len(smt_text)} bytes")
    clip_count = sum(1 for l in smt_text.splitlines() if l.startswith("clip "))
    seg_count = sum(1 for l in smt_text.splitlines() if l.startswith("seg "))
    print(f"     clips={clip_count}, segments={seg_count}")
