# Demo Runtime v52 (Iteration 3) — Bloom post-effect

Итерация 3 v52: добавлен `bloom` post-effect **перед** vignette.
Код (`demo_runtime.cpp`, `gl_executor.hpp`, `sm_runtime.hpp`, `opengl_loader.h`) и
существующие шейдеры — **без изменений**. Изменена только `demo.smt`.

## Что изменилось относительно iter.2

| Параметр | iter.2 | iter.3 |
|----------|--------|--------|
| Клипов в .smt | 8 | **9** (добавлен `blm` post) |
| Shader programs (compiled) | 7 | **8** (+ bloom) |
| Pipeline пост-обработки | vig → grn | **blm → vig → grn** |
| FBOs per simple segment | 2 | 3 (+fbo2) |
| FBOs per transition segment | 4 | 5 (+fbo4) |
| Cost (ops) per simple segment | 4 | 5 |
| Cost (ops) per transition segment | 6 | 7 |

Новый clip `blm`:
```
clip blm 24 post bloom 0.0 120.0 0.0 120.0 normal 77007 - - 0.0
uni uThreshold float = 0.6    (порог яркости — catch highlights)
uni uIntensity float = 1.0    (сила bloom)
uni uRadius    float = 4.0    (радиус размытия в пикселях, max из рекомендуемых)
```

Shader `bloom.frag` — single-pass, 12 круговых семплов вокруг пикселя,
извлекает яркость выше threshold, усредняет, добавляет к оригиналу.

## Pipeline пост-обработки (iter.3)

**Simple segment** (1 сцена):
```
RENDER scene  → fbo0
POST blm      fbo0 → fbo1     (NEW: bloom на сырой сцене)
POST vig      fbo1 → fbo2     (был fbo0 → fbo1)
POST grn      fbo2 → screen   (был fbo1 → screen)
PRESENT       screen
```

**Transition segment** (2 сцены + переход):
```
RENDER s1     → fbo0
RENDER s2     → fbo1
TRANSITION    fbo0,fbo1 → fbo2
POST blm      fbo2 → fbo3     (NEW)
POST vig      fbo3 → fbo4     (был fbo2 → fbo3)
POST grn      fbo4 → screen   (был fbo3 → screen)
PRESENT       screen
```

## Порядок эффектов: почему именно blm → vig → grn

1. **Bloom первым** — на сырой сцене, чтобы vignette затемнение краёв
   не убивало bloom на ярких элементах у периферии.
2. **Vignette вторым** — затемняет края уже после того, как bloom сгенерировал
   свечение. Это создаёт «halo» эффект вокруг ярких областей у края.
3. **Grain последним** — добавляется поверх финального изображения,
   не размывается bloom'ом и не модулируется vignette.

## Состав (без изменений)

```
demo_intro_v51_clean/
├── README.md            (этот файл — обновлён для v52 iter.3)
├── build_demo_runtime.bat
├── demo.smt             (120 с, 9 клипов, 5 сегментов, +bloom post)
├── demo_v51_60s.smt.bak           (бэкап v51 60-секундной версии)
├── demo_v52_iter1_120s.smt.bak    (бэкап iter.1)
├── demo_v52_iter2_grain.smt.bak   (бэкап iter.2 с grain)
├── demo_runtime.cpp     (без изменений относительно v51)
├── gl_executor.hpp      (без изменений)
├── opengl_loader.h      (без изменений)
├── sm_runtime.hpp       (без изменений)
└── shaders/             (11 .frag файлов, без изменений)
```

## Сборка и запуск

```bat
build_demo_runtime.bat
demo_runtime.exe
```

ESC — выход. trace.log пишется в текущую папку.

## Что должно произойти

Визуально — то же 120-секундное демо что в iter.2, но с **bloom вокруг ярких
областей**. Особенно заметно на:
- `nebula_raymarch` (T=0–23) — свечение акцентных цветов
- `sphere_scene` (T=23–65) — glow вокруг сферы (shader уже имеет uGlow uniform)
- `flash` transition (T=63–67) — усиление вспышки
- `particle_swarm` (T=70–120) — яркие частицы «расплываются» в светящиеся пятна

В `trace.log` ожидается:
```
[OK] 8 shader programs compiled   (было 7, +bloom)
[Done] Show finished at T=120.0Xs, frames=~7000
```

**FPS предупреждение:** bloom — самый дорогой post-effect (12 texture samples
на пиксель = 1280×720×12 ≈ 11M семплов/кадр). На GTX 750 ожидается просадка
5–15 FPS, особенно на `particle_swarm` (много ярких пикселей). Бюджет 50 FPS
может быть нарушен — если упадёт ниже 45, уменьшим uRadius или снизим uIntensity.

## Параметры для тюнинга

Если bloom **слишком сильный** (всё светится):
- uThreshold: 0.6 → 0.8 (только очень яркие пиксели)
- uIntensity: 1.0 → 0.5 (слабее)

Если bloom **слишком слабый** (не видно):
- uThreshold: 0.6 → 0.4 (больше пикселей попадёт)
- uIntensity: 1.0 → 1.8 (сильнее)
- uRadius: 4.0 → 4.0 (max recommended, не трогать)

Если bloom **слишком узкий/точечный**:
- uRadius: 4.0 — это уже max рекомендуемого. Если нужно шире, придётся
  переписывать shader на multi-pass (separable Gaussian blur).
