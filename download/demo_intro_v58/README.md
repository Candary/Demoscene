# Demo Runtime v58 — + morphing_figures scene (211s)

v58 = v55 + новый неинтерактивный шейдер `morphing_figures.frag` (порт из `preview.html`)
+ 1-секундный crossfade после cozy_room_sdf + 30 секунд новой сцены.

Базируется на v55 stable (восстановлен из v53 baseline + применены v54+v55 патчи).

## Что нового в v58

| Параметр | v55 | v58 |
|----------|-----|-----|
| Длительность | 180 с | **211 с** (+31) |
| Сцен | 6 | **7** (+ morphing_figures) |
| Переходов | 5 | **6** (+ t6 crossfade 1с) |
| Клипов в .smt | 15 | **17** |
| Сегментов | 11 | **13** |
| Shader files | 11 | **12** (+ morphing_figures.frag) |
| Shader programs | 14 | **15** (+ morphing_figures) |

## Новый тайм-лайн (211 с)

```
T=0–180   v55 demo без изменений (6 сцен + 5 переходов + 3 post)
T=180–181 t6 crossfade (1 с)        ★ НОВОЕ — cozy_room → morphing_figures
T=181–211 s7 morphing_figures (30 с) ★ НОВОЕ — финал
T=0–211   blm + vig + grn           (post-effects на всех сценах, продлены до 211с)
```

## Новый шейдер `morphing_figures.frag`

Портирован из `preview.html` (WebGL2 → OpenGL 3.3 core):
- `#version 300 es` → `#version 330 core`
- Убраны `precision highp float/int` (не нужны в desktop GL)
- Убраны интерактивные фичи: zoom, mouse rotation, droplets, fire, applyToneMap toggle
- Убран fire mask (все 8 частиц всегда видны)
- Убран DropletEffect (всё стёклянных капель на экране)
- Зашиты константы: zoom=1.0, mouseRot=(0,0), applyToneMap=1, droplets=0

**Что осталось (анимация):**
- 9 SDF-фигур: сфера → куб → тор → октаэдр → треугольник → конус → капсула → чайник → додекаэдр (цикл 36 с)
- 8 объёмных частиц на орбитах (светящиеся и полупрозрачные)
- Орбитальная камера (период ~21 с)
- Звёздный фон + градиентное небо
- Neon magenta-cyan-lime палитра (`Palette(t) = a + b*cos(TAU*(c*t+d))`)
- ACES tonemap + gamma 2.2

**Стандартные uniforms (от рантайма):**
- uTime, uClipTime, uProgress, uGlobalTime, uResolution, uSeed
- uBeat, uBeatPhase, uBarPhase, uEnergy

**Кастомных uniforms нет** — шейдер полностью self-contained.

## Управление

| Клавиша | Действие |
|---------|----------|
| **ESC** | Выход |
| **F1**  | Toggle FPS в заголовке (min/max/avg накапливаются всегда) |

## Сборка и запуск

```bat
build_demo_runtime.bat
demo_runtime.exe
```

## Что должно произойти

1. T=0–180 — стандартный v55 demo (6 сцен, post-chain)
2. T=180 — резкий 1-секундный crossfade из cozy_room в morphing_figures
3. T=181–211 — morphing_figures: вращающаяся морфящаяся фигура (9 форм циклом) с орбитальными частицами и звёздным фоном
4. T=211 — завершение, `[Done]` + `[Stats]` блок

## trace.log

Ожидается:
```
[OK] 15 shader programs compiled   (было 14, +morphing_figures)
[Loop] First frame rendered, T=0.003s
[Loop] T=210.0Xs frames=~16000
[Done] Show finished at T=211.0Xs, frames=~16000
[Stats] FPS over 211.0s (~418 samples):
  sampled:     min=~22  max=~100  avg=~75  FPS
  ...
```

## Производительность

- `morphing_figures` — 48 шагов raymarch + 8 частиц в MapScene.
  Ожидается 30-50 FPS на GTX 750 (близко к cozy_room_sdf по cost).
- 1-секундный crossfade (`t6`) — оба шейдера рендерятся одновременно, но
  длительность короткая, заметной просадки не даст.

## Состав v58

```
demo_intro_v58/
├── README.md            (этот файл)
├── build_demo_runtime.bat
├── demo.smt             (211 с, 17 clips, 13 segments)
├── demo_runtime.cpp     (v54 stats + v58 version string)
├── gl_executor.hpp      (без изменений)
├── opengl_loader.h      (без изменений)
├── sm_runtime.hpp       (без изменений)
└── shaders/
    ├── morphing_figures.frag   ★ НОВОЕ (порт из preview.html)
    ├── anxiety_mist.frag       (v55, без sync с WebGL)
    ├── morph_grid.frag
    ├── cozy_room_sdf.frag      (v55 fix: b >= uPrimitivesCount)
    ├── nebula_raymarch.frag
    ├── sphere_scene.frag
    ├── particle_swarm.frag
    ├── crossfade.frag
    ├── flash.frag
    ├── vignette.frag
    ├── bloom.frag
    └── grain.frag
```

## Что дальше

Если v58 работает — фиксируем как milestone. Возможные расширения v59:
- Тюнинг morphing_figures (если нужна другая палитра или motion)
- Multi-pass bloom для premium-качества
- Audio-reactive (реальный PCM-файл)
- Fullscreen mode