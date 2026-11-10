# Demo Runtime — project artifacts

This repo collects the milestones of a C++/OpenGL 3.3 demoscene intro project,
developed on Windows 11 with NVIDIA GeForce GTX 750.

## Milestones

| Version | Duration | Scenes | Key feature |
|---------|----------|--------|-------------|
| v51 | 60 s | 3 | baseline (no post-effects) |
| v52 | 120 s | 3 | + bloom + vignette + grain |
| v58 | 211 s | 7 | + 6 scenes + morphing_figures finale |

Each milestone folder contains the full source: `demo_runtime.cpp`,
`gl_executor.hpp`, `sm_runtime.hpp`, `opengl_loader.h`, `demo.smt`,
`shaders/*.frag`, `build_demo_runtime.bat`, `README.md`, `MILESTONE.txt`.

## Latest milestone: v58

- 7 scenes × 211 seconds @ 81.7 FPS avg on GTX 750
- F1 toggles FPS counter (with min/max/avg) in window title
- `[Stats]` block written to trace.log at end of show
- See `milestone_v58_stable/MILESTONE.txt` for full architecture & timeline

## Build & run (Windows + MSVC)

```
cd milestone_v58_stable
build_demo_runtime.bat
demo_runtime.exe
```

Controls: ESC = quit, F1 = toggle FPS display.

## Repository layout

```
milestone_v51_stable/    v51 source (60 s baseline)
milestone_v51_stable.zip v51 zip archive
milestone_v52_stable/    v52 source (120 s + post-chain)
milestone_v52_stable.zip v52 zip archive
milestone_v58_stable/    v58 source (211 s, 7 scenes, finale)  ★ latest
milestone_v58_stable.zip v58 zip archive
demo_intro_v58/          working directory used to develop v58
scripts/                 Python utilities (smt parsing, scene generation)
```

## Tech stack

- C++17, OpenGL 3.3 core (no external libraries)
- Win32 API for window/context
- MSVC build via `cl /std:c++17 /EHsc /O2`
- Custom SMT format for scene timeline (parsed by `sm_runtime.hpp`)
- FBO-based post-processing chain (bloom → vignette → grain)

## License

Personal demoscene project.
