#!/usr/bin/env python3
"""Boost saturation of color uniforms in .smt for demoscene look.

Color Matrix returns mood-appropriate but often muted colors.
Formula: new_channel = gray + (old - gray) * factor
  - Pure colors (1,0,0) stay pure (already saturated)
  - Muted colors (0.69, 0.60, 0.50) become more vivid
  - Gray (0.5, 0.5, 0.5) stays gray

Boosts: uPrimaryColor, uAccentColor, uColor, uLightColor (vec3 only)
Skips: uDirection, uCamAngle (not colors), flash uColor=(1,1,1) (already pure)
"""
from pathlib import Path
import re

SATURATION_FACTOR = 1.4
COLOR_UNIFORMS = {"uPrimaryColor", "uAccentColor", "uColor", "uLightColor"}
# Don't boost flash transitions (uColor=(1,1,1) is already pure white)
SKIP_CLIPS = {"t2", "t4"}

def boost_saturation(r, g, b, factor=1.4):
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    r2 = max(0.0, min(1.0, gray + (r - gray) * factor))
    g2 = max(0.0, min(1.0, gray + (g - gray) * factor))
    b2 = max(0.0, min(1.0, gray + (b - gray) * factor))
    return r2, g2, b2


def process_smt(smt_path):
    lines = Path(smt_path).read_text().splitlines()
    output = []
    current_clip = None
    in_color_uni = False
    color_name = None
    color_values = []
    color_value_idx = 0
    boosted = 0

    for line in lines:
        # Track current clip
        if line.startswith("clip "):
            current_clip = line.split()[1]
            in_color_uni = False
            output.append(line)
            continue

        if line == "endclip":
            current_clip = None
            in_color_uni = False
            output.append(line)
            continue

        # Detect color uniform declaration
        if line.startswith("uni ") and current_clip and current_clip not in SKIP_CLIPS:
            parts = line.split()
            if len(parts) >= 3 and parts[1] in COLOR_UNIFORMS and parts[2] == "vec3":
                in_color_uni = True
                color_name = parts[1]
                color_values = []
                color_value_idx = 0
                output.append(line)
                continue

        # If we're collecting color values
        if in_color_uni and line.startswith("prog 1 n:"):
            # Extract float value
            match = re.search(r'n:([0-9.eE+-]+)', line)
            if match:
                val = float(match.group(1))
                color_values.append(val)
                color_value_idx += 1

                # When we have all 3 values, boost and output
                if len(color_values) == 3:
                    r, g, b = color_values
                    r2, g2, b2 = boost_saturation(r, g, b, SATURATION_FACTOR)
                    # Output boosted values
                    output.append(f"prog 1 n:{r2!r}")
                    output.append(f"prog 1 n:{g2!r}")
                    output.append(f"prog 1 n:{b2!r}")
                    boosted += 1
                    # Log the change
                    print(f"  {current_clip}.{color_name}: ({r:.3f},{g:.3f},{b:.3f}) → ({r2:.3f},{g2:.3f},{b2:.3f})")
                    in_color_uni = False
                continue

        output.append(line)

    result = "\n".join(output) + "\n"
    Path(smt_path).write_text(result)
    return boosted


if __name__ == "__main__":
    smt_path = "/home/z/my-project/download/demo_intro_v60/demo.smt"

    # Backup
    backup = Path(smt_path + ".preboost.bak")
    if not backup.exists():
        backup.write_text(Path(smt_path).read_text())

    print(f"Boosting saturation ×{SATURATION_FACTOR} in {smt_path}\n")
    count = process_smt(smt_path)
    print(f"\n=== {count} colors boosted ===")
