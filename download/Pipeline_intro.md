# Demoscene Compo Intro — Pipeline Analysis & Comparison

**Документ:** Pipeline_intro.md
**Дата:** 2026-11-05
**Контекст:** `&plan detailed` — анализ порядка построения demoscene compo intro и сравнение с нашим проектом
**Проект:** demo_intro v49 + Color Matrix v11 + Cozy Engine v1.2

---

## 1. Что такое compo intro (стандартный pipeline)

```
┌──────────────────────────────────────────────────────────────────┐
│  DEMOSCENE COMPO INTRO — СТАНДАРТНЫЙ ПРОЦЕСС                     │
│                                                                   │
│  ЭТАП 0: ВЫБОР КОМПО                                              │
│  ├── 4K intro (4096 байт .exe, всё процедурное)                  │
│  ├── 64K intro (65536 байт .exe, всё процедурное)                │
│  └── Demo (без лимита, но обычно <100 МБ)                        │
│                                                                   │
│  ЭТАП 1: КОНЦЕПЦИЯ                                                │
│  ├── Жанр: abstract / raymarch / 2D / hybrid                     │
│  ├── Настроение: dark/cyber/dreamy/aggressive                    │
│  ├── Музыка: acid/trance/ambient/breakcore                       │
│  └── Структура: 4-8 сцен, 3-8 минут                              │
│                                                                   │
│  ЭТАП 2: TOOLCHAIN                                                │
│  ├── Язык: C/C++/asm (для 4K — asm обязательно)                 │
│  ├── API: OpenGL 3.3+ или D3D11 или Vulkan                       │
│  ├── Сжатие: Crinkler (4K) / kkrunchy / UPX                     │
│  ├── Звук: 4Klang / C99 / Ronan / self-synth                    │
│  └── Сборка: однопроходная, single .exe                          │
│                                                                   │
│  ЭТАП 3: CORE ENGINE                                              │
│  ├── Окно: fullscreen, 1920x1080, vsync                          │
│  ├── Контекст: OpenGL 3.3 core / D3D11                           │
│  ├── Таймер: GetTickCount / QueryPerformanceCounter              │
│  ├── Аудио: WASAPI / DirectSound, buffer fill                   │
│  ├── Scene manager: switch by time                               │
│  └── Input: ESC to exit (компо правило)                         │
│                                                                   │
│  ЭТАП 4: КОНТЕНТ — ШЕЙДЕРЫ                                        │
│  ├── Сцена 1: intro/title (0:00-0:30)                           │
│  ├── Сцена 2: build-up (0:30-1:15)                              │
│  ├── Сцена 3: main raymarch (1:15-2:30)                         │
│  ├── Сцена 4: 2D effects (2:30-3:15)                            │
│  ├── Сцена 5: climax (3:15-4:00)                                │
│  └── Сцена 6: outro/credits (4:00-4:30)                         │
│                                                                   │
│  ЭТАП 5: КОНТЕНТ — МУЗЫКА                                         │
│  ├── Композиция: 4-8 минут, BPM 120-174                          │
│  ├── Трекер или soft synth                                       │
│  ├── Синхронизация: sync points → scene changes                  │
│  └── Beat detection → visual triggers                            │
│                                                                   │
│  ЭТАП 6: POST-PROCESSING                                          │
│  ├── Bloom (HDR → bright pass → blur → combine)                 │
│  ├── Tone mapping (ACES / filmic)                                │
│  ├── Chromatic aberration                                        │
│  ├── Film grain                                                  │
│  ├── Vignette                                                    │
│  └── Color grading (LUT)                                         │
│                                                                   │
│  ЭТАП 7: ОПТИМИЗАЦИЯ                                              │
│  ├── Size: Crinkler compress → target size                       │
│  ├── Perf: 60fps, GPU profiling per scene                       │
│  ├── Shader: instruction count, register pressure                │
│  └── Audio: latency < 50ms                                       │
│                                                                   │
│  ЭТАП 8: ПОЛИРОВКА                                                │
│  ├── Transitions: crossfade, wipe, flash                         │
│  ├── Pacing: fast→slow→fast                                      │
│  ├── Greetz/credits в outro                                      │
│  └── Final color grade                                           │
│                                                                   │
│  ЭТАП 9: РЕЛИЗ                                                    │
│  ├── Single .exe (no DLLs except system)                        │
│  ├── Тест на competition hardware (обычно GTX 1060+)             │
│  ├── Сабмишн на party (файл + metadata)                         │
│  └── Post-party: Pouet.net, Scene.org                            │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Сравнение: стандарт vs наш проект

| Этап | Стандарт | Наш проект (v49) | Gap |
|------|---------|------------------|-----|
| **0** | Compo выбран | ❌ не выбран | Решить: 4K / 64K / Demo |
| **1** | Концепция: 4-8 сцен, настроение | «nebula background» (1 сцена) | Концепция |
| **2** | C++ + OpenGL + Crinkler + звук | ✅ C++ MSVC x64 + OpenGL 3.3 | Звук: ❌ нет, Сжатие: ❌ нет |
| **3** | Window + GL + Audio + Timer + SceneMgr + Input | ✅ Window + ✅ OpenGL + ✅ Timer + ✅ Input | Audio: ❌, SceneMgr: ❌ (спроектирован) |
| **4** | 4-8 шейдерных сцен | 1 шейдер (nebula) + 1 fire shader | +3-7 сцен |
| **5** | Музыка 4-8 мин + sync | ❌ нет музыки | Полностью отсутствует |
| **6** | Bloom + ACES + grain + aberration + grade | Vignette (в шейдере) + ACES (uniform) | +bloom, +grain, +aberration |
| **7** | Crinkler → 4K/64K, 60fps profiling | 171 КБ .exe, ~60fps GTX 750 | Сжатие для compo |
| **8** | Transitions + pacing + greetz | ❌ нет transitions, ❌ нет credits | +crossfade, +credits |
| **9** | Single .exe + multi-hardware | Multiple files, GTX 750 only | Packaging |

---

## 3. Gap analysis: что предстоит сделать

### Критичное (блокирует compo submission)

| # | Компонент | Статус | Средство | Усилие |
|---|-----------|--------|---------|--------|
| **G1** | Compo category | ❌ не выбран | Решение пользователя: 4K / 64K / Demo | 0 мин |
| **G2** | Music | ❌ отсутствует | 4Klang (4K) / C99 (64K) / собственного soft synth | 4-8 часов |
| **G3** | Scene Manager | спроектирован (feat_scene_manager.md) | C++ реализация | 3 часа |
| **G4** | Multiple scenes | 1 шейдер | 3-7 дополнительных шейдеров | 4-6 часов |
| **G5** | Single .exe packaging | Multiple files | Inline shaders + crinkler/UPX | 1 час |
| **G6** | Fixed duration + ending | Бесконечный цикл | Timer + ending fade | 30 мин |

### Важное (улучшает качество)

| # | Компонент | Статус | Средство | Усилие |
|---|-----------|--------|---------|--------|
| **G7** | Transitions | ❌ нет | FBO crossfade в Scene Manager | 1.5 часа |
| **G8** | Post-processing | Vignette only | Bloom FBO + grain + aberration | 2 часа |
| **G9** | Sync (music→visual) | ❌ нет | Timeline + beat detection | 2 часа |
| **G10** | Credits/greetz | ❌ нет | Text rendering (freetype) или procedural font | 1 час |

### Опциональное (полировка)

| # | Компонент | Статус | Средство | Усилие |
|---|-----------|--------|---------|--------|
| **G11** | Size optimization | 171 КБ | Crinkler (4K) / UPX (64K) | 1 час |
| **G12** | Multi-hardware test | GTX 750 | Тест на другом GPU | зависит |
| **G13** | Color grading LUT | нет | 3D texture LUT в post-process | 1 час |
| **G14** | Camera paths | нет | Timeline keyframes | 1 час |

---

## 4. Средства для каждого gap

### G1: Compo category

```
4K intro:
  + Престижно, сложно
  + Crinkler compresses C++ to ~3.5K
  - Assembly для OpenGL init
  - 4Klang для музыки (tracker format, ~1K)
  - Очень ограниченный shader
  - Наш .exe: 171 КБ → нужно сжать ×42

64K intro:
  + Реалистично для нашего уровня
  + kkrunchy compresses to ~60K
  + Полный C++ + OpenGL
  + C99 или собственного synth для музыки
  + Multiple scenes possible
  + Наш .exe: 171 КБ → нужно сжать ×2.5

Demo (unlimited):
  + Без лимита размера
  + Полная свобода
  + Внешние ассеты разрешены
  + Но: больше конкуренции по качеству
  + Наш .exe: 171 КБ → вписывается без сжатия
```

### G2: Music

```
4Klang:
  - Tracker-based synth, ~1K binary
  - Compose in tracker UI → export .h
  - 8 channels, basic waveforms
  - Для 4K compo

C99 / Cosine:
  - Modular synth, ~4K binary
  - MIDI input
  - Better sound quality
  - Для 64K compo

Self-synth (procedural):
  - Код генерации музыки в main.cpp
  - No external tool
  - Ограниченная сложность
  - ~2K кода

BASSMOD / XM play:
  - Pre-composed .xm module
  - Встроить как resource
  - Простота, но не «procedural»
  - Для Demo compo
```

### G3: Scene Manager

```
Уже спроектирован (feat_scene_manager.md):
  - Scene struct (shader, timing, colors, params)
  - SceneManager class (add/update/render/transition)
  - Crossfade FBO transitions
  - Per-scene uniforms

Реализация:
  - scene_manager.h + .cpp (~200 строк C++)
  - Изменение main.cpp (~30 строк)
  - 3-5 shader sources в shaders.h
```

### G4: Multiple scenes

```
Scene 1 (intro):     Title + logo (procedural text)
Scene 2 (build-up):  Raymarch SDF (Cozy Engine atoms → shapes)
Scene 3 (main):      Nebula (текущий v49, улучшенный)
Scene 4 (climax):    Particle bursts + multiple effects
Scene 5 (outro):     Credits + fade to black

Cozy Engine → shader mapping:
  sofa → sdRoundBox
  fireplace → flame particles
  warm_light → bloom
  → каждая сцена = набор cozy atoms
```

### G5: Single .exe

```
Текущие файлы:
  main.cpp        ~30 КБ
  shaders.h       ~35 КБ
  opengl_loader.h ~15 КБ
  build_msvc.bat  ~1 КБ

Для single .exe:
  1. Inline everything в main.cpp
  2. Static link (/MT вместо /MD)
  3. Strip debug info
  4. Compress:
     - UPX: ~50% сжатие (171К → ~85К)
     - Crinkler: ~70% сжатие (171К → ~50К)
     - kkrunchy: ~65% (171К → ~60К)
```

### G6: Fixed duration

```cpp
const float DEMO_DURATION = 180.0f; // 3 минуты
float elapsed = getTime() - startTime;
if (elapsed >= DEMO_DURATION) {
    float fade = clamp((elapsed - DEMO_DURATION) / 3.0f, 0.0f, 1.0f);
    // Multiply final color by (1 - fade)
    if (fade >= 1.0f) PostQuitMessage(0);
}
```

---

## 5. План внедрения (по приоритету)

### Фаза 1: Сценарий (1 час)
- Выбрать compo category
- Определить количество сцен (4-6)
- Описать каждую сцену (mood, colors, duration)
- Выбрать музыкальный стиль
- Нарисовать timeline

### Фаза 2: Scene Manager (3 часа)
- Реализовать scene_manager.h/.cpp
- Добавить 2 тестовые сцены
- CUT transitions (без crossfade)
- v50: multi-scene demo

### Фаза 3: Shader content (4-6 часов)
- Scene 1: title/intro shader
- Scene 2: raymarch SDF (Cozy Engine inspired)
- Scene 3: improved nebula (current v49)
- Scene 4: particle/climax effect
- Scene 5: outro/credits shader
- v51: full visual content

### Фаза 4: Music (4-8 часов)
- Выбрать инструмент (4Klang/C99/self-synth)
- Композиция 3-4 минуты
- Интеграция в main.cpp (audio callback)
- WASAPI/DirectSound output
- v52: music + visuals

### Фаза 5: Sync + transitions (2 часа)
- Timeline keyframes (camera, params)
- Crossfade transitions между сценами
- Beat-triggered events
- v53: synced demo

### Фаза 6: Post-processing (2 часа)
- Bloom (FBO bright pass + blur)
- Film grain (noise overlay)
- Chromatic aberration
- Final color grade
- v54: polished demo

### Фаза 7: Packaging (1 час)
- Inline all files в main.cpp
- Static link
- Strip debug
- Compress (UPX/Crinkler)
- v55: single .exe ready

### Фаза 8: Test + submit (1 час)
- Test на GTX 750 (60fps?)
- Test на другом GPU (если возможно)
- Fixed duration + ending
- Compo submission metadata
- v56: compo ready

**Итого: ~18-24 часа работы**

---

## 6. Матрица приоритетов

```
         Низкое усилие    Среднее усилие    Высокое усилие
         ───────────    ──────────────    ──────────────
Критич.  G1 (compo cat)  G3 (SceneMgr)    G2 (Music)
         G6 (duration)   G5 (packaging)   G4 (Shaders)

Важно    G10 (credits)   G7 (transitions) G9 (Sync)
                         G8 (post-proc)

Опц.     G11 (compress)  G13 (LUT grade)  G12 (multi-GPU)
         G14 (camera)
```

---

## 7. Связь с существующими системами

| Система | Роль в compo intro |
|---------|-------------------|
| **demo_intro v49** | Base engine (window, GL, timer) |
| **Color Matrix v11** | Colors per scene (empathy-driven palette) |
| **Cozy Engine v1.2** | Scene content (atoms → objects → SDF shapes) |
| **Booster v1.1** | GLSL style hints (faster shader writing) |
| **glslangValidator** | Pre-delivery syntax check (blocking) |
| **Pandoc pipeline** | Documentation (design doc for compo) |
| **Scene Manager** (спроектирован) | Multi-scene orchestration |
| **aesthetics.md** | Principles (70/25/5, harmony, motion) |
| **scene_generator** (другая НС) | Cozy atoms → GLSL shader code |

---

## 8. Решения, которые нужно принять

### Compo category
- `#ok compo-4k` — 4K intro (престижно, сложно, Assembly)
- `#ok compo-64k` — 64K intro (реалистично, рекомендую)
- `#ok compo-demo` — Demo (без лимита, полная свобода)

### Музыкальный подход
- `#ok music-4klang` — tracker-based (4K compo)
- `#ok music-c99` — modular synth (64K compo)
- `#ok music-self` — procedural self-synth
- `#ok music-xm` — pre-composed module (Demo)

### Количество сцен
- `#ok scenes-4` — 4 сцены (минимум)
- `#ok scenes-6` — 6 сцен (стандарт)
- `#ok scenes-8` — 8 сцен (сложно)

### Рекомендация
`#ok compo-64k` + `#ok music-c99` + `#ok scenes-6` — реалистичный план для 64K compo с 6 сценами и modular synth музыкой. ~20 часов работы → готовый compo intro.
