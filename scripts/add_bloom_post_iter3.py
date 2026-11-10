#!/usr/bin/env python3
"""v52 Iteration 3: add bloom post-effect BEFORE vignette (and before grain).

Pipeline change:
  iter.2: RENDER→fbo0; POST vig fbo0→fbo1; POST grn fbo1→screen; PRESENT
  iter.3: RENDER→fbo0; POST blm fbo0→fbo1; POST vig fbo1→fbo2; POST grn fbo2→screen; PRESENT

Order rationale: bloom first on raw scene (vignette darkening doesn't kill bloom),
vignette second, grain last (so noise isn't blurred by bloom).

Transition segments add fbo4 (bloom output before vignette):
  iter.2: RENDER s1→fbo0; RENDER s2→fbo1; TRANSITION→fbo2; POST vig fbo2→fbo3; POST grn fbo3→screen; PRESENT
  iter.3: RENDER s1→fbo0; RENDER s2→fbo1; TRANSITION→fbo2; POST blm fbo2→fbo3; POST vig fbo3→fbo4; POST grn fbo4→screen; PRESENT
"""
from pathlib import Path

# New bloom clip definition.
BLOOM_CLIP_LINES = [
    "clip blm 24 post bloom 0.0 120.0 0.0 120.0 normal 77007 - - 0.0",
    "prog 1 n:1.0",
    "prog 1 n:1.0",
    "uni uThreshold float 1",
    "prog 1 n:0.6",          # catch highlights above 0.6 brightness
    "uni uIntensity float 1",
    "prog 1 n:1.0",          # moderate bloom strength
    "uni uRadius float 1",
    "prog 1 n:4.0",          # 4-pixel radius (within shader's recommended range)
    "endclip",
]

# Updated segments: insert bloom op BEFORE vignette, retarget vignette/grain.
NEW_SEGMENTS = [
    (0.0,  23.0,  5, 3, [
        ("RENDER",  "s1", "-",        "fbo0",  "-", "-"),
        ("POST",    "blm","fbo0",     "fbo1",  "-", "-"),   # NEW bloom
        ("POST",    "vig","fbo1",     "fbo2",  "-", "-"),   # was fbo0→fbo1
        ("POST",    "grn","fbo2",     "screen","-", "-"),   # was fbo1→screen
        ("PRESENT", "-",  "screen",   "-",     "-", "-"),
    ]),
    (23.0, 27.0,  7, 5, [
        ("RENDER",     "s1", "-",        "fbo0",  "-", "-"),
        ("RENDER",     "s2", "-",        "fbo1",  "-", "-"),
        ("TRANSITION", "t1", "fbo0,fbo1","fbo2",  "-", "-"),
        ("POST",       "blm","fbo2",     "fbo3",  "-", "-"),   # NEW bloom
        ("POST",       "vig","fbo3",     "fbo4",  "-", "-"),   # was fbo2→fbo3
        ("POST",       "grn","fbo4",     "screen","-", "-"),   # was fbo3→screen
        ("PRESENT",    "-",  "screen",   "-",     "-", "-"),
    ]),
    (27.0, 63.0,  5, 3, [
        ("RENDER",  "s2", "-",        "fbo0",  "-", "-"),
        ("POST",    "blm","fbo0",     "fbo1",  "-", "-"),
        ("POST",    "vig","fbo1",     "fbo2",  "-", "-"),
        ("POST",    "grn","fbo2",     "screen","-", "-"),
        ("PRESENT", "-",  "screen",   "-",     "-", "-"),
    ]),
    (63.0, 67.0,  7, 5, [
        ("RENDER",     "s2", "-",        "fbo0",  "-", "-"),
        ("RENDER",     "s3", "-",        "fbo1",  "-", "-"),
        ("TRANSITION", "t2", "fbo0,fbo1","fbo2",  "-", "-"),
        ("POST",       "blm","fbo2",     "fbo3",  "-", "-"),
        ("POST",       "vig","fbo3",     "fbo4",  "-", "-"),
        ("POST",       "grn","fbo4",     "screen","-", "-"),
        ("PRESENT",    "-",  "screen",   "-",     "-", "-"),
    ]),
    (67.0, 120.0, 5, 3, [
        ("RENDER",  "s3", "-",        "fbo0",  "-", "-"),
        ("POST",    "blm","fbo0",     "fbo1",  "-", "-"),
        ("POST",    "vig","fbo1",     "fbo2",  "-", "-"),
        ("POST",    "grn","fbo2",     "screen","-", "-"),
        ("PRESENT", "-",  "screen",   "-",     "-", "-"),
    ]),
]


def build_iter3(src_path: Path) -> str:
    """Read iter.2 .smt, insert bloom clip before 'vig', rebuild segments.
    The original 'end' line is dropped and re-emitted AFTER new segments."""
    lines = src_path.read_text().splitlines()
    out = []
    inserted_bloom = False
    skip_old_segments = False

    for line in lines:
        parts = line.split()
        if not parts:
            continue
        k = parts[0]

        if k == "seg":
            skip_old_segments = True
            continue
        if skip_old_segments and k in ("op", "endseg"):
            continue
        if skip_old_segments and k == "end":
            skip_old_segments = False
            continue  # don't re-emit original 'end' until after new segments

        # Insert bloom clip right before 'vig' clip.
        if k == "clip" and len(parts) >= 2 and parts[1] == "vig" and not inserted_bloom:
            out.extend(BLOOM_CLIP_LINES)
            inserted_bloom = True

        # Re-emit original line.
        out.append(line)

    # Append new segments.
    for seg in NEW_SEGMENTS:
        start, end, cost, fbos, ops = seg
        out.append(f"seg {start:.1f} {end:.1f} {cost} {fbos} {len(ops)}")
        for op in ops:
            out.append(f"op {op[0]} {op[1]} {op[2]} {op[3]} {op[4]} {op[5]}")
        out.append("endseg")

    # Final end terminator.
    out.append("end")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    src = Path("/home/z/my-project/download/demo_intro_v51_clean/demo.smt")
    backup = Path("/home/z/my-project/download/demo_intro_v51_clean/demo_v52_iter2_grain.smt.bak")
    if not backup.exists():
        backup.write_text(src.read_text())
        print(f"[Backup] saved iter.2 .smt to {backup.name}")

    new_text = build_iter3(src)
    src.write_text(new_text)
    print(f"[OK] wrote iter.3 demo.smt (bloom post-effect added)")
    print(f"     {len(new_text.splitlines())} lines, {len(new_text)} bytes")

    clip_count = sum(1 for l in new_text.splitlines() if l.startswith("clip "))
    seg_count = sum(1 for l in new_text.splitlines() if l.startswith("seg "))
    bloom_ops = sum(1 for l in new_text.splitlines() if l.startswith("op POST blm"))
    print(f"     clips={clip_count} (was 8, now 9 with bloom), segments={seg_count}, bloom POST ops={bloom_ops}")
