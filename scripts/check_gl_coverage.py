#!/usr/bin/env python3
"""Verify all GL functions used in main.cpp are either declared in
opengl_loader.h or part of GL 1.1 (opengl32.dll exports them directly)."""
import re
from pathlib import Path

MAIN = Path("/home/z/my-project/download/demo_intro/main.cpp").read_text()
LOADER = Path("/home/z/my-project/download/demo_intro/opengl_loader.h").read_text()

# Functions declared in opengl_loader.h via DECL_GL_FN
declared = set(re.findall(r'DECL_GL_FN\([^,]+,\s*(\w+)\)', LOADER))
# Functions loaded via LOAD_GL_FN
loaded = set(re.findall(r'LOAD_GL_FN\((\w+)\)', LOADER))

# GL 1.1 functions exported by opengl32.dll (link via -lopengl32)
gl11 = {
    'glClearColor', 'glClear', 'glViewport', 'glDrawArrays', 'glEnable',
    'glDisable', 'glBlendFunc', 'glFlush', 'glFinish', 'glBegin', 'glEnd',
    'glGenTextures', 'glDeleteTextures', 'glBindTexture', 'glTexImage2D',
    'glTexParameteri', 'glGetString', 'glGetError', 'glMatrixMode',
    'glLoadIdentity', 'glOrtho', 'glFrustum',
}

# All gl* calls in main.cpp
used = set(re.findall(r'\b(gl[A-Z]\w*)\s*\(', MAIN))

print("=== Used GL functions ===")
missing = []
for fn in sorted(used):
    in_loader = fn in declared
    in_gl11 = fn in gl11
    status = "LOADER" if in_loader else ("GL1.1" if in_gl11 else "??? MISSING ???")
    if not in_loader and not in_gl11:
        missing.append(fn)
    print(f"  {fn:35s} {status}")

print(f"\nLoader declares {len(declared)}, loads {len(loaded)}")
if set(declared) != loaded:
    print("MISMATCH declared vs loaded:", declared ^ loaded)
if missing:
    print("\n!!! MISSING DECLARATIONS:", missing)
else:
    print("\nAll functions covered — C++ build should link.")
