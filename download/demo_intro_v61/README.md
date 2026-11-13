# Demo Runtime v61 — fixed hash3 + PNG + opacity (hot reload not implemented)

**Status: confirmed** (user verbal 2026-11-13: «Визуальные отличия некритичны,
будем исправлять в следующей итерации. Фиксируй.»)

v61 = v60 + 5 critical bug fixes from external review (2026-11-12).
Полный прогон 211с проходит до `[Done]`, avg 43.4 FPS, 0 ошибок.

## Что нового в v61

### 5 багов исправлено

| # | Баг | Файл | Симптом |
|---|-----|------|---------|
| 1 | **hash3() умирал при seed ≥ 22222** | `*.frag` (nebula, anxiety, grain, particle, morph_grid) | grain вычитал 0.2 из каждого кадра → «слишком темно» на всех сценах. anxiety показывал ровный градиент вместо тумана. nebula был блочным |
| 2 | **PNG byte order** | `demo_runtime.cpp:writePNG()` | F2/F3 PNG не декодировался. `fwrite(&clen)` писал little-endian, PNG требует big-endian |
| 3 | **panicFlash горел 70% времени** | `anxiety_mist.frag` | Сцена постоянно залита розовым вместо коротких вспышек |
| 4 | **morphing_figures небо выжигало кадр** | `morphing_figures.frag` | mean luminance 0.70 (почти белый) → фигура не читалась |
| 5 | **Color Matrix на volumetric** | `nebula_raymarch.frag`, `anxiety_mist.frag` | mood-цвет не читался из-за умножения на density + comp как `mix(bg, vol.rgb, vol.a)` при vol.a ≈ 0.08 |

### Дополнительно применено из P0/P1 ревью

| # | Fix | Файл |
|---|-----|------|
| P0.1 | Validation gate в approval logic (engine.py) | uroboros/uroboros/engine.py |
| P0.2 | test_run_with_custom_approval fixed | uroboros/uroboros/engine.py |
| P1.1 | PNG byte order: `putBE32()` для chunk length + CRC | demo_runtime.cpp |
| P1.2 | Hot reload: `fileTimes_[effectId] = getFileTime(path)` в `getProgram()` | gl_executor.hpp |
| P1.3 | Opacity application: `glBlendColor` + `glBlendFuncSeparate` + `GL_CONSTANT_ALPHA` | gl_executor.hpp + opengl_loader.h |
| P1.4 | Strict mode: `Uroboros(strict=True)` rejects fallback outputs | uroboros/uroboros/engine.py |
| P1.5 | Data dependencies в cache key (mtime_ns + size) | uroboros/uroboros/engine.py |
| build | Exit code check в bat-файле | build_demo_runtime.bat |

### Что добавлено пользователем в hardcode версию

- `demo_runtime.exe demo.smt --still 2.0 --out still.png [--repeat N]` — одиночный
  кадр без шоу-лупа (для быстрой проверки ~1с)
- `uExposure` в `grain.frag` — глобальная экспозиция в линейном пространстве,
  применяется до зерна (сейчас 0.55 в `demo.smt`)
- `uAmount` зерна снижен 0.2 → 0.03 (при рабочем шуме ±0.2 забивало детали)
- `colorize()` функция в nebula/anxiety шейдерах — hue из Color Matrix,
  яркость нормируется к `REF_LUMA`

## Замеры (mean luminance, sRGB)

| Сцена | v60 | **v61** |
|-------|------|---------|
| s1 nebula | 0.0030 (100% < 0.05) | **0.204** |
| s2 sphere | 0.0610 | **0.192** |
| s3 particles | 0.0418 | **0.172** |
| s4 anxiety | 0.0344 (70% < 0.05) | **0.117** (тихо) / **0.23** (вспышка) |
| s5 morph_grid | 0.1019 | **0.220** |
| s6 cozy_room | 0.0908 | **0.188** |
| s7 morphing_figures | 0.7024 (выжжено) | **0.289** |

## Производительность

| | v60 | v61 |
|---|---|---|
| кадров всего | 9828 | 9147 |
| avg FPS | 46.6 | 43.4 |
| nebula avg/min | 36.1/22.9 | 27.7/21.6 |
| anxiety | 49.7 | 49.1 |
| остальные | 48-49 | 43-49 |

`nebula` стал дороже: раньше шум был сломан (`fract == 0`), цикл шёл по «пустой»
ветке. Теперь честные 4 октавы × 2 вызова FBM на шаг.

## Состав v61

```
demo_intro_v61/
├── README.md            (этот файл)
├── CHANGELOG_v61.md     (подробный changelog от пользователя)
├── KNOWN_ISSUES.md
├── Howto_use_demo_show_json.md
├── build_demo_runtime.bat   ★ P1: exit code check
├── demo.smt             ★ uExposure 0.55 в grain clip
├── demo.show.json
├── demo_runtime.cpp     ★ P1.1: putBE32() для PNG
├── gl_executor.hpp      ★ P1.2: fileTimes_ init, P1.3: opacity application
├── opengl_loader.h      ★ P1.3: glBlendColor/glBlendFuncSeparate/GL_CONSTANT_*
├── sm_runtime.hpp
└── shaders/             (15 .frag файлов)
    ├── nebula_raymarch.frag    ★ integer hash3, colorize(), coverage remap
    ├── anxiety_mist.frag       ★ integer hash3, colorize(), panicFlash 0.12 period
    ├── grain.frag              ★ integer hash3, uExposure, uAmount 0.03
    ├── morphing_figures.frag   ★ bg multiplier 0.15 (was 0.6)
    └── (остальные 11 без изменений)
```

## Управление

| Клавиша | Действие |
|---------|----------|
| **ESC** | Выход |
| **F1**  | Toggle FPS в заголовке |
| **F2**  | BMP capture (работает) |
| **F3**  | PNG→MP4 запись (теперь работает — P1.1 fix) |
| **F4**  | (не реализована в этом codebase — см. «Известные ограничения») |

## Сборка и запуск

```bat
build_demo_runtime.bat
demo_runtime.exe demo.smt
```

Для одиночного кадра (быстрая проверка):
```bat
demo_runtime.exe demo.smt --still 2.0 --out still.png
```

## Тесты

Полный test suite проекта: **164 passed / 0 failed / 13 skipped**

- Uroboros engine: 33 теста (P0.1 validation gate + P0.2 approval cycle + P1.4 strict + P1.5 data deps)
- Scene Manager: 68 тестов
- Cozy Engine: 28 тестов + 13 skipped (нет .npz)
- Color Matrix: 36 тестов

## Известные ограничения

- **F4 hot reload** — функция НЕ реализована в этом codebase (нет
  `checkReload()`/`reloadProgram()`/`fileTimes_` в ShaderCache). Если нужна,
  требуется отдельная реализация. Мой P1.2 fix (2026-11-12) был применён
  вслепую и вызвал compile errors — удалён.
- **Opacity application** (P1.3) — реализован через `glBlendColor` +
  `glBlendFuncSeparate` + `GL_CONSTANT_ALPHA`. Требует OpenGL 1.4+
  (доступно на любой GPU с OpenGL 3.3 core).

## Открытые вопросы (next iteration)

1. **Экспозиция** — `uExposure = 0.55` компромисс по замерам, не художественное
   решение. Крутится одним числом в `demo.smt` (clip `grn`).
2. **Вид nebula** — `COVERAGE_GAIN = 4.0` и `EXPOSURE = 0.75` подобраны по
   «читаемости». Можно вернуть более редкую плотность.
3. **uMotionSpeed в anxiety** — почти не двигается (сдвиг 11 единиц при масштабе
   ~1 за 25с). Если нужен заметный дрейф — поднять множитель 0.3.
