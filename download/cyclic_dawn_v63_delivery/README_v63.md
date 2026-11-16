# Cyclic Dawn v63 — 45s Demo

Pipeline: **Uroboros → Scene Manager → motus → Cozy Engine → Color Matrix**

## Timeline

| Scene | Time       | Shader                 | Visual                          |
|-------|------------|------------------------|---------------------------------|
| dawn  | 0.0-12.0   | dawn.frag              | FBM domain-warp, amber→yellow   |
| t1    | 12.0-16.5  | crossfade.frag         | dawn → spire crossfade          |
| spire | 16.5-28.5  | spire.frag             | triangle grid, acid-green glow  |
| t2    | 28.5-33.0  | bloom_transition.frag  | bloom flash white-out           |
| fall  | 33.0-45.0  | fall.frag              | 6-layer stratified ember field  |

## Verified on Linux (software GL — llvmpipe)

```
[GL] llvmpipe (LLVM 19.1.7, 256 bits) / 4.5 (Core Profile) Mesa 25.0.7-2+deb13u1
[OK] 11 shader programs compiled
[OK] SMT loaded: duration=45.0s, 12 clips, 5 segments
[Done] T=45.05s frames=354
[Stats] FPS over 45.05s: avg=7.88 (llvmpipe software)
```

Captures (640×360 BMP):
- `shot_dawn.bmp` — T=3s, avg RGB (185,161,60) warm amber
- `shot_spire.bmp` — T=18s, avg RGB (31,50,24) dark green with neon edges
- `shot_transition_bloom.bmp` — T=22s, avg RGB (251,252,251) white-out peak
- `shot_fall.bmp` — T=38s, avg RGB (55,40,21) dark with ember orange

## Windows Build

### Option A — MinGW + GLFW (recommended for cross-platform)

1. Install GLFW 3.4 binaries from https://www.glfw.org/download.html
2. Place `glfw3.h`, `glfw3native.h` in `include/GLFW/`
3. Place `glfw3.lib` (or `glfw3dll.lib`) in `lib/`
4. Build:

```cmd
cl /std:c++17 /EHsc /O2 /MT /D_CRT_SECURE_NO_WARNINGS /DWIN32_LEAN_AND_MEAN ^
   /I include glfw_runtime.cpp /link ^
   glfw3.lib opengl32.lib user32.lib gdi32.lib shell32.lib /OUT:demo_v63.exe
```

`glfw_runtime.cpp` uses `#ifdef _WIN32` to switch between the Windows opengl_loader.h
(wglGetProcAddress) and the Linux `opengl_loader_linux.h` (GL_GLEXT_PROTOTYPES).
On Windows it requires the original `opengl_loader.h` from `demo_intro_v61/`
on github main (HEAD `fe690ab`).

### Option B — Pure Win32 (no GLFW dependency)

Use `demo_runtime_v63.cpp` + `build_v63.bat` instead — this is the v61.2 runtime
with updated `g_scenes[]` for the 45s timeline. No GLFW needed, uses wglCreateContext
directly. See `build_v63.bat` for the MSVC command line.

## Linux Build (for testing only)

```bash
# Requires: g++, mesa-common-dev, libglfw3-dev, xvfb (for offscreen)
g++ -std=c++17 -O2 -Wall glfw_runtime.cpp -o demo_v63_glfw \
    $(pkg-config --cflags --libs glfw3 gl) -ldl -lpthread

# Offscreen render with software GL:
LIBGL_ALWAYS_SOFTWARE=1 xvfb-run -a ./demo_v63_glfw demo_v63.smt

# Single still frame:
LIBGL_ALWAYS_SOFTWARE=1 xvfb-run -a ./demo_v63_glfw \
    --still 6.0 --out shot.png --repeat 1 demo_v63.smt
```

## File Map

```
cyclic_dawn_v63/
├── demo_v63.smt                 # 45s timeline (12 clips, 5 segments)
├── glfw_runtime.cpp             # Cross-platform runtime (Linux + Windows)
├── demo_runtime_v63.cpp         # Windows-only Win32 runtime (v61.2 + g_scenes update)
├── opengl_loader_linux.h        # Linux GL prototypes (GL_GLEXT_PROTOTYPES)
├── sm_runtime.hpp               # SMT parser (from v61.2, unchanged)
├── gl_executor.hpp              # GL executor (from v61.2, unchanged)
├── build_v63.bat                # Windows MSVC build for demo_runtime_v63.cpp
├── shaders/
│   ├── dawn.frag                # NEW
│   ├── spire.frag               # NEW
│   ├── fall.frag                # NEW
│   ├── bloom_transition.frag    # NEW (3-phase bloom envelope)
│   ├── crossfade.frag           # REUSED from demo_intro_v61/
│   ├── bloom_bright.frag        # REUSED
│   ├── bloom_blur.frag          # REUSED
│   ├── passthrough.frag         # REUSED
│   ├── vignette.frag            # REUSED
│   ├── grain.frag               # REUSED
│   └── flash.frag               # REUSED (not used in v63 smt, kept for parity)
├── demo_v63_glfw                # Linux x86_64 binary (proof of build)
├── trace.log                    # Successful 45s run log
└── shot_*.bmp                   # 4 captured frames from the 45s run
```

## Key Fixes vs v61.2

- v63 uses GLFW for windowing (cross-platform testable), v61.2 uses Win32 only
- 4 new shaders (dawn, spire, fall, bloom_transition) — all `glslangValidator` PASS
- `bloom_transition.frag`: 3-phase envelope (grow 0-0.3, peak 0.3-0.7, recede 0.7-1.0)
- `aces_safe()` in every shader: pre-clamps negative channels to avoid NaN
- FBM capped at 4 octaves (register spill prevention on older GPUs)

## Not Tested

- Windows MSVC build (no Windows in CI) — `build_v63.bat` uses same flags as v61.2
- GPU acceleration (llvmpipe is software, ~8 FPS) — real GPU should hit 60+ FPS
- demo_runtime_v63.exe (Win32 variant) — same code path as v61.2, lower risk
