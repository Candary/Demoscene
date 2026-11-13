# Milestone v61 — CONFIRMED

**Date:** 2026-11-13
**Status:** confirmed (user `!milestone` 2026-11-13)
**Previous milestone:** v49 (2026-10-31, MD5 6539b1198d2210920ba121172d3f302a)

## Canonical artifact

- **File:** `download/milestone_v61_stable.zip` (frozen copy, NEVER overwrite)
- **MD5:** `f6eca3aca7c57058119368e52ceb4046`
- **Size:** 76098 bytes (76 KB)
- **Files inside:** 26 (4 C++/H sources, 15 .frag shaders, 2 .json, 5 .md, 1 .bat)

## Verification (trace.log 2026-11-13)

```
[Start] Demo Runtime — loading demo.smt
[OK] SMT loaded: duration=211.0s, 20 clips, 13 segments
[OK] 19 shader programs compiled
[Loop] First frame rendered, T=0.003s
[Quality] LOW (steps=24, FPS=23.8)  →  [Quality] HIGH (steps=40, FPS=47.4)
[Done] Show finished at T=211.01s, frames=8617
[Stats] FPS over 211.02s (413 samples):
  sampled:     min=23.32  max=55.36  avg=40.87  FPS
  theoretical: 8617 frames / 211.02s = 40.84 FPS
[Exit] Demo Runtime ended
```

**0 errors, 0 warnings, 0 crashes.** Full 211с demo completes successfully.

## What v61 fixes vs v60

| # | Bug | File | Impact |
|---|-----|------|--------|
| 1 | hash3() returned 0 for seed ≥ 22222 | shaders/*.frag | Root cause of «too dark»: grain.frag subtracted 0.2 from every frame |
| 2 | PNG byte order little-endian | demo_runtime.cpp | F2/F3 PNG captures undecodable |
| 3 | panicFlash burned 70% of time | anxiety_mist.frag | Scene constantly pink instead of brief flashes |
| 4 | morphing_figures sky burned frame | morphing_figures.frag | mean luminance 0.70 → figure invisible |
| 5 | Color Matrix invisible on volumetric | nebula/anxiety .frag | Mood colors not readable |
| P0.1 | Invalid scene auto-approved | uroboros/engine.py | Validation gate added |
| P0.2 | test_run_with_custom_approval failed | uroboros/engine.py | Approval cycle fixed |
| P1.3 | Opacity not applied in setBlendMode | gl_executor.hpp + opengl_loader.h | glBlendColor + glBlendFuncSeparate |
| P1.4 | Strict mode missing | uroboros/engine.py | Uroboros(strict=True) rejects fallback |
| P1.5 | Data deps not in cache key | uroboros/engine.py | mtime_ns + size folded into key |
| build | False «Build complete» on failure | build_demo_runtime.bat | Exit code check added |

## Brightness measurements (mean luminance sRGB)

| Scene | v60 | v61 |
|-------|------|------|
| s1 nebula | 0.0030 (100% < 0.05) | 0.204 |
| s2 sphere | 0.0610 | 0.192 |
| s3 particles | 0.0418 | 0.172 |
| s4 anxiety | 0.0344 (70% < 0.05) | 0.117 / 0.23 (flash) |
| s5 morph_grid | 0.1019 | 0.220 |
| s6 cozy_room | 0.0908 | 0.188 |
| s7 morphing_figures | 0.7024 (burned) | 0.289 |

## Tests

**164 passed / 0 failed / 13 skipped** (full project test suite)
- Uroboros: 33 tests (P0.1 validation gate + P0.2 approval + P1.4 strict + P1.5 data deps)
- Scene Manager: 68 tests
- Cozy Engine: 28 tests + 13 skipped (.npz missing)
- Color Matrix: 36 tests

## Known limitations

- **F4 hot reload** — NOT implemented in this codebase (no checkReload/reloadProgram/fileTimes_ in ShaderCache). If needed, requires separate feature implementation.
- **uExposure = 0.55** — compromise value, not artistic decision. Tunable via demo.smt (clip `grn`).
- **uMotionSpeed in anxiety** — slow drift (11 units over 25s at scale ~1). Tunable.

## Rollback

```
!revert lastgood   → restores v61 (this milestone)
!revert v60        → restores previous v60 baseline
```

## meta.auto update

```
[v:61]
[md5:v61] = f6eca3aca7c57058119368e52ceb4046
[md5:milestone] = f6eca3aca7c57058119368e52ceb4046
[lastgood] = v61
[status] = confirmed
```
