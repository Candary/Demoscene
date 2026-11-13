#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_glsl.py — GLSL static validator для demo_intro shaders.h.
Извлекает все 4 шейдера, прогоняет glslangValidator (OpenGL режим), репортит pass/fail.
Task 59: code booster = GLSL validator pipeline (лечит bottleneck "не могу compile-test").
"""
import re, subprocess, sys, tempfile, os

SHADERS_H = "/home/z/my-project/download/demo_intro/shaders.h"
GLSLANG = "/home/z/my-project/tools/glslang/extract/usr/bin/glslangValidator"

STAGE = {
    "kVertexShaderSrc": "vert",
    "kFragmentShaderSrc": "frag",
    "kFireVertexShaderSrc": "vert",
    "kFireFragmentShaderSrc": "frag",
}

def extract_shaders(src):
    shaders = {}
    for name in STAGE:
        # raw-string-aware: match one-or-more R"GLSL(...)GLSL" chunks then ;
        m = re.search(rf'{name}\s*=\s*((?:R"GLSL\(.*?\)GLSL"\s*)+);', src, re.S)
        if not m:
            shaders[name] = None
            continue
        body = m.group(1)
        chunks = re.findall(r'R"GLSL\((.*?)\)GLSL"', body, re.S)
        shaders[name] = "".join(chunks)
    return shaders

def validate(name, source, stage):
    if not source:
        return ("MISSING", "shader not found in shaders.h")
    suffix = ".vert" if stage == "vert" else ".frag"
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as f:
        f.write(source)
        tmppath = f.name
    try:
        r = subprocess.run([GLSLANG, "-S", stage, "--glsl-version", "330", tmppath],
                           capture_output=True, text=True, timeout=30)
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0 and not out:
            return ("PASS", f"{len(source)} bytes, {source.count(chr(10))+1} lines")
        else:
            # filter: take first ~8 error lines
            errs = [l for l in out.split("\n") if "ERROR" in l or "WARNING" in l][:8]
            return ("FAIL", "\n  ".join(errs) if errs else out[:300])
    finally:
        os.unlink(tmppath)

def main():
    if not os.path.isfile(GLSLANG):
        print(f"FATAL: glslangValidator not found at {GLSLANG}")
        sys.exit(2)
    src = open(SHADERS_H, encoding="utf-8").read()
    shaders = extract_shaders(src)
    print(f"=== GLSL validation (glslangValidator 15.2.0, OpenGL mode) ===")
    print(f"shaders.h: {len(src)} bytes\n")
    allok = True
    for name, stage in STAGE.items():
        source = shaders[name]
        if source:
            status, detail = validate(name, source, stage)
        else:
            status, detail = "MISSING", "—"
        icon = "✓" if status == "PASS" else "✗"
        print(f"{icon} {name:28} [{stage}]  {status}")
        if status != "PASS":
            allok = False
            print(f"   {detail}\n")
    print(f"\n=== {'ALL PASS' if allok else 'HAS FAILURES — fix before !*shader* delivery'} ===")
    sys.exit(0 if allok else 1)

if __name__ == "__main__":
    main()
