#!/usr/bin/env python3
"""v52 Iteration 2: add grain post-effect after vignette.

Pipeline change:
  iter.1: RENDER→fbo0; POST vig fbo0→screen; PRESENT
  iter.2: RENDER→fbo0; POST vig fbo0→fbo1; POST grn fbo1→screen; PRESENT

Transition segments add fbo3:
  iter.1: RENDER s1→fbo0; RENDER s2→fbo1; TRANSITION→fbo2; POST vig fbo2→screen; PRESENT
  iter.2: RENDER s1→fbo0; RENDER s2→fbo1; TRANSITION→fbo2; POST vig fbo2→fbo3; POST grn fbo3→screen; PRESENT
"""
from pathlib import Path

# New grain clip definition (matched to vignette style).
GRAIN_CLIP_LINES = [
    "clip grn 26 post grain 0.0 120.0 0.0 120.0 normal 88008 - - 0.0",
    "prog 1 n:1.0",
    "prog 1 n:1.0",
    "uni uAmount float 1",
    "prog 1 n:0.08",
    "endclip",
]

# Updated segments: insert grain op before PRESENT, retarget vignette output.
# Format: (start, end, cost, fbos, ops_list)
NEW_SEGMENTS = [
    (0.0,  23.0,  4, 2, [
        ("RENDER",  "s1", "-",        "fbo0",  "-", "-"),
        ("POST",    "vig","fbo0",     "fbo1",  "-", "-"),   # was → screen
        ("POST",    "grn","fbo1",     "screen","-", "-"),   # NEW
        ("PRESENT", "-",  "screen",   "-",     "-", "-"),
    ]),
    (23.0, 27.0,  6, 4, [
        ("RENDER",     "s1", "-",        "fbo0",  "-", "-"),
        ("RENDER",     "s2", "-",        "fbo1",  "-", "-"),
        ("TRANSITION", "t1", "fbo0,fbo1","fbo2",  "-", "-"),
        ("POST",       "vig","fbo2",     "fbo3",  "-", "-"),   # was → screen
        ("POST",       "grn","fbo3",     "screen","-", "-"),   # NEW
        ("PRESENT",    "-",  "screen",   "-",     "-", "-"),
    ]),
    (27.0, 63.0,  4, 2, [
        ("RENDER",  "s2", "-",        "fbo0",  "-", "-"),
        ("POST",    "vig","fbo0",     "fbo1",  "-", "-"),
        ("POST",    "grn","fbo1",     "screen","-", "-"),
        ("PRESENT", "-",  "screen",   "-",     "-", "-"),
    ]),
    (63.0, 67.0,  6, 4, [
        ("RENDER",     "s2", "-",        "fbo0",  "-", "-"),
        ("RENDER",     "s3", "-",        "fbo1",  "-", "-"),
        ("TRANSITION", "t2", "fbo0,fbo1","fbo2",  "-", "-"),
        ("POST",       "vig","fbo2",     "fbo3",  "-", "-"),
        ("POST",       "grn","fbo3",     "screen","-", "-"),
        ("PRESENT",    "-",  "screen",   "-",     "-", "-"),
    ]),
    (67.0, 120.0, 4, 2, [
        ("RENDER",  "s3", "-",        "fbo0",  "-", "-"),
        ("POST",    "vig","fbo0",     "fbo1",  "-", "-"),
        ("POST",    "grn","fbo1",     "screen","-", "-"),
        ("PRESENT", "-",  "screen",   "-",     "-", "-"),
    ]),
]


def build_iter2(src_path: Path) -> str:
    """Read iter.1 .smt, insert grain clip before 'fin', rebuild segments.
    The original 'end' line is dropped and re-emitted AFTER new segments."""
    lines = src_path.read_text().splitlines()
    out = []
    inserted_grain = False
    skip_old_segments = False
    skip_original_end = False  # don't re-emit original 'end' until after new segments

    for line in lines:
        parts = line.split()
        if not parts:
            continue
        k = parts[0]

        if k == "seg":
            # Start skipping old segments.
            skip_old_segments = True
            continue
        if skip_old_segments and k in ("op", "endseg"):
            continue
        if skip_old_segments and k == "end":
            # Don't re-emit original 'end' yet; we'll append after segments.
            skip_old_segments = False
            skip_original_end = True
            continue

        # Insert grain clip right before 'fin' clip.
        if k == "clip" and len(parts) >= 2 and parts[1] == "fin" and not inserted_grain:
            out.extend(GRAIN_CLIP_LINES)
            inserted_grain = True

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
    backup = Path("/home/z/my-project/download/demo_intro_v51_clean/demo_v52_iter1_120s.smt.bak")
    if not backup.exists():
        backup.write_text(src.read_text())
        print(f"[Backup] saved iter.1 120s .smt to {backup.name}")

    new_text = build_iter2(src)
    src.write_text(new_text)
    print(f"[OK] wrote iter.2 demo.smt (grain post-effect added)")
    print(f"     {len(new_text.splitlines())} lines, {len(new_text)} bytes")

    # Sanity counts
    clip_count = sum(1 for l in new_text.splitlines() if l.startswith("clip "))
    seg_count = sum(1 for l in new_text.splitlines() if l.startswith("seg "))
    grain_ops = sum(1 for l in new_text.splitlines() if l.startswith("op POST grn"))
    print(f"     clips={clip_count} (was 7, now 8 with grain), segments={seg_count}, grain POST ops={grain_ops}")
