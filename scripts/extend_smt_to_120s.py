#!/usr/bin/env python3
"""v52 Iteration 1: extend demo.smt from 60s to 120s.

Preserves all shader uniforms and programs; only updates:
- meta duration
- audio energy array (expanded to cover 120s with variation)
- sections
- clip timing fields (eff_start/eff_end/nom_start/nom_dur/prewarm)
- segment boundaries
- finish event time
"""
import re
import sys
from pathlib import Path

# Target timing for v52 (120s).
NEW_DURATION = 120.0
NEW_SECTIONS = [0.0, 27.0, 67.0]   # 3 sections matching scene boundaries
NEW_ENERGY_RATE = 0.25             # sample every 4s → 30 samples for 120s
NEW_ENERGY = [
    # 0-40s: buildup (intro + early nebula)
    0.05, 0.10, 0.20, 0.30, 0.40,
    0.50, 0.60, 0.70, 0.80, 0.90,
    # 40-60s: nebula climax + transition to sphere
    1.00, 1.00, 0.95, 0.85, 0.75,
    # 60-80s: sphere + flash transition to particle
    0.85, 0.95, 1.00, 1.00, 0.95,
    # 80-100s: particle_swarm peak then decline
    0.85, 0.75, 0.65, 0.55, 0.45,
    # 100-120s: fade out
    0.40, 0.35, 0.30, 0.25, 0.20,
]
assert len(NEW_ENERGY) == 30

# Clip timing updates (id → (eff_start, eff_end, nom_start, nom_dur, prewarm))
CLIP_TIMING = {
    "s1":  (0.0,   27.0,  0.0,  25.0, 0.0),   # nebula
    "t1":  (23.0,  27.0,  23.0, 4.0,  0.0),   # crossfade centered on T=25
    "s2":  (23.0,  67.0,  25.0, 40.0, 2.0),   # sphere
    "t2":  (63.0,  67.0,  63.0, 4.0,  0.0),   # flash centered on T=65
    "s3":  (63.0,  120.0, 65.0, 55.0, 2.0),   # particle_swarm
    "vig": (0.0,   120.0, 0.0,  120.0, 0.0),  # vignette all-show
    "fin": (120.0, 120.0, 0.0,  0.0,  0.0),   # finish event
}

# New segments (5 segments, same structure as before but extended)
NEW_SEGMENTS = [
    # (start, end, cost, fbos, ops_list)
    (0.0,  23.0,  3, 1, [
        ("RENDER", "s1", "-",   "fbo0", "-", "-"),
        ("POST",   "vig", "fbo0", "screen", "-", "-"),
        ("PRESENT","-",    "screen","-",     "-", "-"),
    ]),
    (23.0, 27.0,  5, 3, [
        ("RENDER",     "s1", "-",       "fbo0", "-", "-"),
        ("RENDER",     "s2", "-",       "fbo1", "-", "-"),
        ("TRANSITION", "t1", "fbo0,fbo1","fbo2","-", "-"),
        ("POST",       "vig","fbo2",    "screen","-","-"),
        ("PRESENT",    "-",  "screen",  "-",    "-", "-"),
    ]),
    (27.0, 63.0,  3, 1, [
        ("RENDER", "s2", "-",   "fbo0", "-", "-"),
        ("POST",   "vig","fbo0","screen","-", "-"),
        ("PRESENT","-",  "screen","-",   "-", "-"),
    ]),
    (63.0, 67.0,  5, 3, [
        ("RENDER",     "s2", "-",       "fbo0", "-", "-"),
        ("RENDER",     "s3", "-",       "fbo1", "-", "-"),
        ("TRANSITION", "t2", "fbo0,fbo1","fbo2","-", "-"),
        ("POST",       "vig","fbo2",    "screen","-","-"),
        ("PRESENT",    "-",  "screen",  "-",    "-", "-"),
    ]),
    (67.0, 120.0, 3, 1, [
        ("RENDER", "s3", "-",   "fbo0", "-", "-"),
        ("POST",   "vig","fbo0","screen","-", "-"),
        ("PRESENT","-",  "screen","-",   "-", "-"),
    ]),
]


def build_smt(src_path: Path) -> str:
    """Read original .smt, extract per-clip uniform blocks, reassemble with new timings."""
    lines = src_path.read_text().splitlines()

    # Collect clip bodies (between 'clip' and 'endclip').
    clip_bodies = {}  # id → list of lines (prog/uni/arr)
    cur_id = None
    cur_lines = []
    for line in lines:
        parts = line.split()
        if not parts:
            continue
        k = parts[0]
        if k == "clip":
            cur_id = parts[1]
            cur_lines = []
        elif k == "endclip":
            clip_bodies[cur_id] = cur_lines
            cur_id = None
        elif cur_id is not None and k in ("prog", "uni", "arr"):
            cur_lines.append(line)

    out = []
    out.append("SMT 1")
    out.append(f"meta {NEW_DURATION:.1f} 60 1280 720 2026")
    out.append(
        f"audio 128.0 0.0 4 {NEW_ENERGY_RATE} {len(NEW_ENERGY)} " +
        " ".join(f"{e:.2f}" for e in NEW_ENERGY)
    )
    out.append(f"sections {len(NEW_SECTIONS)} " + " ".join(f"{s:.1f}" for s in NEW_SECTIONS))

    # Clip order matches original: s1, s2, s3, t1, t2, vig, fin
    clip_order = ["s1", "s2", "s3", "t1", "t2", "vig", "fin"]
    # Original clip metadata (everything except timing fields)
    clip_static = {
        "s1":  ("10", "scene",      "nebula_raymarch", "normal", "11111", "-", "-", "s2"),
        "s2":  ("10", "scene",      "sphere_scene",    "normal", "22222", "-", "-", "t1"),
        "s3":  ("10", "scene",      "particle_swarm",  "normal", "33333", "-", "-", "t2"),
        "t1":  ("10", "transition", "crossfade",       "normal", "10101", "s1", "s2", "-"),
        "t2":  ("10", "transition", "flash",           "normal", "20202", "s2", "s3", "-"),
        "vig": ("25", "post",       "vignette",        "normal", "99001", "-", "-", "-"),
        "fin": ("30", "event",      "finish",          "normal", "77777", "-", "-", "-"),
    }
    # Original in_a/in_b for transitions:
    # t1: in_a=s1, in_b=s2 ; t2: in_a=s2, in_b=s3
    clip_in = {
        "s1": ("-", "-"), "s2": ("-", "-"), "s3": ("-", "-"),
        "t1": ("s1", "s2"), "t2": ("s2", "s3"),
        "vig": ("-", "-"), "fin": ("-", "-"),
    }

    for cid in clip_order:
        track, kind, effect, blend, seed, _, _, _ = clip_static[cid]
        in_a, in_b = clip_in[cid]
        es, ee, ns, nd, pw = CLIP_TIMING[cid]
        out.append(
            f"clip {cid} {track} {kind} {effect} "
            f"{es:.1f} {ee:.1f} {ns:.1f} {nd:.1f} {blend} {seed} {in_a} {in_b} {pw:.1f}"
        )
        for body_line in clip_bodies.get(cid, []):
            out.append(body_line)
        out.append("endclip")

    # Segments
    for seg in NEW_SEGMENTS:
        start, end, cost, fbos, ops = seg
        out.append(f"seg {start:.1f} {end:.1f} {cost} {fbos} {len(ops)}")
        for op in ops:
            out.append(f"op {op[0]} {op[1]} {op[2]} {op[3]} {op[4]} {op[5]}")
        out.append("endseg")

    out.append("end")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    src = Path("/home/z/my-project/download/demo_intro_v51_clean/demo.smt")
    dst = Path("/home/z/my-project/download/demo_intro_v51_clean/demo.smt")
    # Backup original first
    backup = Path("/home/z/my-project/download/demo_intro_v51_clean/demo_v51_60s.smt.bak")
    if not backup.exists():
        backup.write_text(src.read_text())
        print(f"[Backup] saved original 60s .smt to {backup.name}")

    new_text = build_smt(src)
    dst.write_text(new_text)
    print(f"[OK] wrote new 120s demo.smt to {dst}")
    print(f"     {len(new_text.splitlines())} lines, {len(new_text)} bytes")

    # Sanity: count clips/segments
    clip_count = sum(1 for l in new_text.splitlines() if l.startswith("clip "))
    seg_count = sum(1 for l in new_text.splitlines() if l.startswith("seg "))
    print(f"     clips={clip_count}, segments={seg_count}")
