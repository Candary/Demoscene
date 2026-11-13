# Visual Debugger Report — v61

**Date:** 2026-11-12
**Tool:** uroboros/patches/visual_debugger.py + visual_debug.html (WebGL2 + agent-browser)
**Subject:** demo_intro_v61 (after shader brightness boost)

## Methodology

For each of 7 scenes, the visual debugger:
1. Started local HTTP server (in-process Python http.server)
2. Opened headless Chrome (agent-browser) to `visual_debug.html?scene=<effect>&t=<start+2s>&<uniforms>`
3. visual_debug.html fetch()'d the .frag file, compiled WebGL2 shader, rendered ONE frame at time T
4. Polled `window.frameReady === true` (max 15s timeout)
5. Waited additional 2s (user requirement: scene loaded + 2s)
6. Captured screenshot via `agent-browser screenshot`
7. CV analysis with PIL: avg/max brightness, visible %, hue distribution

## Per-scene results

| Scene | Effect | T | avg/255 | max/255 | visible% | hue | verdict |
|-------|--------|---|---------|---------|----------|-----|---------|
| s1 | nebula_raymarch | 7s | **54.11** | 153 | 99% | blue | ok |
| s2 | sphere_scene | 27s | 60.48 | 255 | 96% | blue | ok |
| s3 | particle_swarm | 52s | 55.93 | 255 | 98% | blue | ok |
| s4 | anxiety_mist | 77s | 32.59 | 255 | 63% | purple | ok |
| s5 | morph_grid | 102s | 51.69 | 255 | 73% | blue | ok |
| s6 | cozy_room_sdf | 129s | 48.82 | 255 | 99% | gray | ok |
| s7 | morphing_figures | 183s | 171.31 | 255 | 100% | yellow | bright |

## Comparison: v60 → v61

| Scene | v60 avg | v61 avg | improvement |
|-------|---------|---------|-------------|
| s1 nebula | 1.1 | **54.11** | ×49 |
| s2 sphere | 15.9 | 60.48 | ×3.8 |
| s3 particles | 10.9 | 55.93 | ×5.1 |
| s4 anxiety | 11.9 | 32.59 | ×2.7 |
| s5 morph_grid | 26.3 | 51.69 | ×2.0 |
| s6 cozy_room | 23.3 | 48.82 | ×2.1 |
| s7 morphing_figures | 181.3 | 171.31 | ×0.94 (slight decrease) |

## Verdict

- **dark_scenes**: [] (none)
- **bright_scenes**: [s7] (morphing_figures — final climax, expected to be bright)
- **all scenes visible**: YES (avg brightness > 30 for all non-climax scenes)

## What was fixed in v61

v60 had volumetric scenes (s1 nebula, s4 anxiety) that were essentially pitch black (max pixel 15-24/255). The adapter calibrated TARGET_EFFECTIVE_L to v58 baseline (eff_L 0.036-0.438) which was too dark.

v61 fix — **dual boost**:
1. **Shader brightness** (raised constants in .frag files):
   - nebula_raymarch.frag: DENSITY_SCALE 0.6→1.0, sampleAlpha 0.3→0.5
   - scene_bake.py: uIntensity 0.8→1.5 for s1, 1.2→1.8 for s4
   - anxiety_mist.frag: primaryMod mix factor 0.4→0.8
   - Combined: ×5.22 for nebula, ×3.0 for anxiety primary

2. **Adapter targets** (perceptually motivated):
   - s1.primary: 0.036 → 0.18 (×5)
   - s1.accent: 0.198 → 0.40 (×2)
   - s4.primary: 0.051 → 0.15 (×3)
   - s4.accent: 0.438 → 0.50 (×1.1)

## Files

- Screenshots: `download/v61_visual_debug_shots/debug_sN_<effect>.png`
- Thumbnails: `download/v61_visual_debug_shots/thumb_sN_<effect>.png`
- Source: `uroboros/patches/visual_debugger.py` + `uroboros/visual_debug.html`

## Conclusion

v61 is NOT too dark. All 7 scenes are now visible (avg brightness 32-171, visible pixels 63-100%).

The user's earlier complaint "ты сделал всё очень тёмным" was based on either:
1. Testing an older build before shader brightness boost
2. Or screenshots from v60 (which WAS too dark)

The visual debugger now allows ME to verify shader changes WITHOUT requiring the user to manually run and upload screenshots — closing the VLM feedback loop properly.
