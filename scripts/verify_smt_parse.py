#!/usr/bin/env python3
"""Simulate the C++ sm_runtime.hpp parser on demo.smt to verify the fix."""
import re

def tokenize(line):
    return line.split()

def parse_smt(path):
    with open(path) as f:
        lines = [l.rstrip() for l in f]

    header = lines[0]
    assert header == "SMT 1", f"bad header: {header}"

    clips = []
    segs = []
    cur = None
    uni = None
    seg = None

    for line in lines[1:]:
        if not line.strip():
            continue
        parts = tokenize(line)
        k = parts[0]
        rest = parts[1:]

        if k == "meta":
            continue
        elif k == "audio":
            continue
        elif k == "sections":
            continue
        elif k == "clip":
            cur = {"id": rest[0], "opacity": [], "progress": [], "uniforms": []}
            clips.append(cur)
            uni = None
        elif k == "prog":
            w = rest[0] if rest else ""
            if w == "opacity":
                cur["opacity"] = rest[1:]
            elif w == "progress":
                cur["progress"] = rest[1:]
            else:
                # Position-based: first prog = opacity, second = progress.
                if uni is not None:
                    uni["comps"].append(rest)
                elif cur is not None:
                    if not cur["opacity"]:
                        cur["opacity"] = rest
                    elif not cur["progress"]:
                        cur["progress"] = rest
                    else:
                        pass  # discard extra
        elif k == "uni":
            cur["uniforms"].append({"name": rest[0], "type": rest[1], "want": int(rest[2]), "comps": []})
            uni = cur["uniforms"][-1]
        elif k == "arr":
            pass
        elif k == "endclip":
            cur = None
            uni = None
        elif k == "seg":
            seg = {"start": float(rest[0]), "end": float(rest[1]), "ops": []}
            segs.append(seg)
        elif k == "op":
            seg["ops"].append({"op": rest[0], "clip": rest[1], "reads": rest[2], "write": rest[3], "dest": rest[4], "blend": rest[5]})
        elif k == "endseg":
            seg = None
        elif k == "end":
            break

    return clips, segs

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "/home/z/my-project/download/demo_intro_v51_clean/demo.smt"
    clips, segs = parse_smt(path)
    print(f"Parsing: {path}")
    print(f"Parsed {len(clips)} clips, {len(segs)} segments\n")
    for c in clips:
        print(f"  clip '{c['id']}': opacity={c['opacity']} (size={len(c['opacity'])}), "
              f"progress={c['progress']} (size={len(c['progress'])}), "
              f"uniforms={len(c['uniforms'])}")
        for u in c["uniforms"]:
            print(f"      uni {u['name']} {u['type']} comps={len(u['comps'])} (expect {u['want']})")
            if len(u["comps"]) != u["want"]:
                print(f"      !!! COMPONENT COUNT MISMATCH for {u['name']}")
    print()
    print("All segments:")
    for i, s in enumerate(segs):
        print(f"  seg[{i}] {s['start']:.1f}-{s['end']:.1f} ({len(s['ops'])} ops):")
        for op in s["ops"]:
            print(f"    {op['op']} {op['clip']} reads={op['reads']} write={op['write']}")
