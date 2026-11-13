# Scene Manager — реальный расчёт времени внедрения (v2)

**Документ:** smt_implementation_time_v2.md
**Дата:** 2026-11-08
**Сигил:** `&suggest` — пересчёт времени с учётом self-shader-writing
**Контекст:** после SMT_FORMAT.md и scene_manager_new_response.md
**Без:** ссылок на DeepSeek critique

---

## 1. Может ли LLM написать frag-шейдеры самостоятельно?

**Да, может.** Я уже работал с GLSL на протяжении всего проекта:

| Что я уже делал | Доказательство |
|-----------------|----------------|
| Анализ `shaders.h` (866 строк GLSL) | perf_analysis.md — section 1.1, hot path analysis |
| Правки GLSL в patch_*.py | `patch_nebula_bg_v1.py` … `v5.py` — 5 итераций фикса небулы |
| Правки GLSL в `patch_shaders_optimize.py` | lazy SDF eval, bounding sphere, RayMarch 60→48 шагов |
| Правки GLSL в `patch_optimize_v1.py` | tetrahedron trick в CalcNormal |
| Правки GLSL в `patch_procfire_v2.py` | процедурный огонь, billboard партиклы |
| Design document для transitions | `feat_scene_manager.md` section 9 — crossfade/wipe/flash GLSL |
| Understanding SDF formulas | sdSphere, sdBox, sdTorus, sdOctahedron, sdTriPrism, sdCone, sdCapsule, sdTeapot, sdDodecahedron — все в shaders.h |
| Color palette (IQ formula) | `Palette(t)` функция в shaders.h |

### Что я МОГУ написать

| Тип шейдера | Сложность | Время (для меня) |
|-------------|-----------|-------------------|
| **Standard SDF scene** (sphere, box, torus morph) | Low | 30-60 мин |
| **Raymarch scene** (nebula, mist, abstract) | Medium | 1-2 часа |
| **Particles** (swarm, sparks) | Medium | 1 час (есть заготовка в shaders.h) |
| **Transitions** (crossfade, flash, wipe) | Low | 30 мин каждый (design уже есть) |
| **Post-processing** (bloom, grain, vignette) | Low-Medium | 30-60 мин каждый |
| **Cozy room SDF** (с uPrimitives farray) | Medium-High | 2-3 часа (новая интеграция) |
| **Text rendering** (credits via SDF atlas) | High | 4-8 часов (нужен atlas glyphs) |
| **Original creative** (anxiety_mist, morph_grid) | Medium-High | 1-2 часа каждый |

### Что мне ТРУДНЕЕ

1. **Visual iteration** — я не вижу результат рендера. Нужно:
   - `glslangValidator` для compile check
   - `preview.html` или аналог для visual check (user глядит)
   - Итерации по feedback от пользователя

2. **Tuning visual quality** — colors, motion curves, SDF parameters. Один проход даёт reasonable result, но polish требует 2-3 итерации по feedback.

3. **Performance tuning** — `glQueryCounter` profiling. Без GPU metrics сложно оптимизировать.

### Резюме: LLM способен писать shaders

**Производительность:** ~3-5× быстрее человека на standard SDF/post shaders, ~1× на original creative work.

**Для 10 shaders:** 8-15 часов работы (1-2 рабочих дня) vs 5-10 дней у человека.

---

## 2. Преимущества отдельных .frag файлов vs текущий shaders.h

### Текущий подход (shaders.h)

```cpp
static const char* kFragmentShaderSrc = R"GLSL(
#version 330 core
// 866 строк GLSL embedded as C++ string literal
...
)GLSL";
```

### Проблемы текущего подхода

| Проблема | Влияние |
|----------|---------|
| Нет syntax highlighting в C++ контексте | Медленнее разработка |
| Нет IDE support для GLSL | Нет autocomplete, no error squiggles |
| Duplicate в `preview.html` (1406 строк!) | Любая правка = sync 2 файлов |
| Можно валидировать только после C++ compile | Медленный feedback loop |
| Mix C++ и GLSL errors в одном log | Сложнее debug |
| Все shader'ы в одном файле = монолит | Нельзя переиспользовать отдельно |

### Преимущества отдельных .frag файлов

| Преимущество | Эффект |
|--------------|--------|
| **Syntax highlighting** для GLSL в IDE | +30% скорость написания |
| **glslangValidator file.frag** напрямую | Compile check за 0.5с, без C++ build |
| **Single source** — preview.html и C++ используют тот же файл | Нет duplication |
| **Scene Manager manifest system** — каждый effect = `.frag` + `.effect.json` | Plug-in architecture |
| **Hot-reload** during development | Быстрая итерация |
| **Separate version control** | Чёткая history правок |
| **Reusable across projects** | atom library concept |
| **Independent testing** | unit test per shader |

### Конкретный пример

**Сейчас:** правка nebula
1. Открыть `shaders.h` (866 строк)
2. Найти `kFragmentShaderSrc` (nested R"GLSL()"")
3. Внести правку
4. Скопировать правку в `preview.html` (sync)
5. Compile C++ → запустить .exe → проверить визуально
6. Если ошибка — repeat

**С .frag:** правка nebula
1. Открыть `nebula_raymarch.frag` (single file, GLSL highlighting)
2. Внести правку
3. `glslangValidator nebula_raymarch.frag` — compile check за 0.5с
4. Hot-reload в preview (или Scene Manager debug mode)
5. Готово

**Speedup: 3-5×** на shader iteration.

---

## 3. Реальный расчёт времени внедрения

### Decomposition работы

| # | Задача | Я делаю | Время |
|---|--------|---------|-------|
| 1 | Ответить на 5 open questions | decision | 1h |
| 2 | MSVC build sm_runtime.hpp + conformance.cpp | я | 2-4h |
| 3 | GL binding layer (~400 строк C++) | я | 1-2 дня |
| 4 | Извлечь nebula из shaders.h → .frag + manifest | я | 1-2h |
| 5 | sphere_scene.frag (simple SDF) | я | 30-60 мин |
| 6 | particle_swarm.frag (reuse particles code) | я | 1 час |
| 7 | anxiety_mist.frag (original creative) | я | 1-2 часа |
| 8 | morph_grid.frag (original creative) | я | 1-2 часа |
| 9 | cozy_room_sdf.frag (uPrimitives integration) | я | 2-3 часа |
| 10 | credits.frag + string params design | я | 4-8 часов |
| 11 | crossfade.frag transition | я | 30 мин |
| 12 | flash.frag transition | я | 30 мин |
| 13 | bloom.frag post | я | 1 час |
| 14 | grain.frag post | я | 30 мин |
| 15 | vignette.frag post | я | 15 мин |
| 16 | Integration test: build_demo.py end-to-end | я | 1 день |
| 17 | Real music test (5-10 tracks) | я + user feedback | 1-2 дня |
| 18 | GLM behavior test (10 tasks) | я | 1-2 дня |

### Сценарий A: Sequential (только я, всё сам)

| Phase | Tasks | Время |
|-------|-------|-------|
| Setup | #1, #2, #3 | 2-3 дня |
| Pipeline validation | #4 | 1 час |
| Scene shaders (6 shaders) | #5-10 | 1.5-2 дня (8-15 часов) |
| Transitions (2) | #11, #12 | 1 час |
| Post (3) | #13, #14, #15 | 2 часа |
| Integration | #16 | 1 день |
| Real music test | #17 | 1-2 дня |
| GLM test | #18 | 1-2 дня |
| **TOTAL** | | **7-10 working days = 1.5-2 недели** |

С buffer 20%: **9-12 дней = ~2 недели**

### Сценарий B: 2 parallel agents (я + 1 shader writer)

| Agent | Tasks | Время |
|-------|-------|-------|
| Lead (я) | #1, #2, #3, #4, #16, #17, #18 | 5-7 дней |
| Shader writer | #5-15 (10 shaders) | 2-3 дня (parallel с Lead setup) |

**Critical path: max(Lead, Shader writer) = 5-7 дней**
С buffer: **6-9 дней = ~1.5 недели**

### Сценарий C: 3 parallel agents

| Agent | Tasks | Время |
|-------|-------|-------|
| Lead (я) | #1, #2, #3, #4, #16, #17, #18 | 5-7 дней |
| Shader writer 1 | #5, #6, #7, #11, #12, #13 (6 shaders) | 1.5 дня |
| Shader writer 2 | #8, #9, #10, #14, #15 (5 shaders) | 1.5-2 дня |

**Critical path: 5-7 дней (Lead bottleneck)**
С buffer: **6-9 дней = ~1.5 недели**

### Сценарий D: 5+ parallel agents

Каждый agent = 2 shaders. Shaders: 0.5-1 день.

**Critical path: setup + integration + testing = 5-7 дней**
**С buffer: 6-9 дней**

### Сравнение

| Сценарий | Agents | Время | Real saving |
|----------|--------|-------|-------------|
| A: Sequential | 1 (я) | 9-12 дней | baseline |
| B: 2 agents | 2 | 6-9 дней | 25% |
| C: 3 agents | 3 | 6-9 дней | 25-30% |
| D: 5+ agents | 5+ | 6-9 дней | 25-30% |

**Вывод: parallel agents дают только 25-30% saving**, потому что:
1. Lead work (setup, GL binding, integration, testing) — sequential, не параллелится
2. Shader writing — уже быстро у меня (1-2 дня на все 10)
3. Testing — sequential (нельзя тестировать то, чего нет)

**Bottleneck: Lead work (5-7 дней), не shader writing.**

---

## 4. Как ОПТИМИЗИРОВАТЬ время внедрения ещё

### Оптимизация 1: Минимальный v50 (3 сцены вместо 6)

Не строить все 7 эффектов сразу. **MVP: 3 сцены + 2 перехода + 3 post = 8 shaders вместо 13.**

| Шейдер | Время |
|--------|-------|
| nebula_raymarch.frag (extract from shaders.h) | 1 час |
| sphere_scene.frag (simple SDF) | 30 мин |
| particle_swarm.frag (reuse particles code) | 1 час |
| crossfade.frag | 30 мин |
| flash.frag | 30 мин |
| vignette.frag | 15 мин |
| grain.frag | 30 мин |
| bloom.frag | 1 час |

**Итого: 4-5 часов shader work** (vs 8-15 для full set)

v50 demo: 3 scenes, 2 transitions, 3 post, 60-90 секунд. Достаточно для Demo compo submission в минимальной категории.

v51, v52 добавляют: anxiety_mist, morph_grid, cozy_room_sdf, credits.

**Saving: -1 день на shader work.**

### Оптимизация 2: Отложить GLM behavior test

GLM behavior test — 1-2 дня, но не блокирует v50. Можно сделать после v50.

**Saving: -1-2 дня.**

### Оптимизация 3: Отложить real music test

В `examples/make_soundtrack.py` уже есть синтетический soundtrack generator. Для v50 — достаточно.

Real music test отложить до v51, когда pipeline stable.

**Saving: -1-2 дня.**

### Оптимизация 4: Отложить string params (credits)

Credits effect требует text rendering — 4-8 часов design + implementation. Для v50 — заменить на:
- Статический title overlay через HTML/CSS (в preview)
- Или пропустить credits полностью

**Saving: -4-8 часов.**

### Оптимизация 5: Reuse existing shaders.h code maximally

- nebula → nebula_raymarch.frag (extract, minimal adaptation)
- particles → particle_swarm.frag (есть код)
- droplets → может стать overlay effect

**Saving: -2-3 часа на rewrite.**

### Оптимизация 6: Параллельно GL binding + shader writing

GL binding (~1-2 дня) НЕ зависит от shaders. Можно делать параллельно:
- Я: GL binding
- Agent 1: 3-4 shaders

**Saving: -1 день через parallelism.**

### Оптимизация 7: Hot-reload в preview.html

Добавить в preview.html режим "load .frag file" (через fetch). Тогда:
- Правка .frag → Ctrl+F5 в браузере → сразу видно
- Не нужно перекомпилировать C++ для shader iteration

**Saving: -30 мин на каждую shader iteration × 10 shaders = 5 часов.**

### Оптимизация 8: v50 → v51 → v52 incremental

| Version | Что добавляется | Время |
|---------|----------------|-------|
| **v50** | Min set: nebula + sphere + particles + transitions + post | 5-7 дней |
| **v51** | anxiety_mist + morph_grid + cozy_room_sdf + credits + real music | +3-4 дня |
| **v52** | GLM behavior test + polish | +2-3 дня |

**v50 за 5-7 дней = 1 неделя.** Полный pipeline за 10-14 дней = 2 недели.

### Оптимизация 9: Pip install -e . для Python packages

Сейчас `sys.path.insert(0, "output")` hacks. Установить как editable packages:

```bash
pip install -e color_matrix/ -e cozy_engine/ -e scene_manager/
```

Это убирает sys.path manipulation, упрощает imports, даёт proper package structure.

**Saving: -30 мин setup + cleaner code.**

### Оптимизация 10: Pre-built glslangValidator в PATH

Сейчас `tools/glslang/` содержит .deb packages (Linux). Нужно:
- Скачать Windows binary glslangValidator.exe
- Положить в `tools/glslang/`
- Добавить в PATH

Тогда `glslangValidator nebula_raymarch.frag` работает из любой папки.

**Saving: -30 мин setup + reliable validation.**

---

## 5. Финальный оптимизированный план

### v50 — минимальный рабочий demo (5-7 дней)

**Day 1: Setup**
- Утро: ответить на 5 open questions (1h)
- День: MSVC build sm_runtime.hpp (2-4h)
- Вечер: начать GL binding layer

**Day 2: GL binding**
- Полный день: GL binding (~400 строк C++)
- FBO pool, shader loading, uniform binding, pass executor
- Параллельно: Agent 1 начинает писать 3 scene shaders

**Day 3: Pipeline validation**
- Утро: извлечь nebula из shaders.h → nebula_raymarch.frag (1-2h)
- День: minimal SMT test (1 clip, 1 seg) — должно рендерить nebula
- Вечер: hot-reload в preview.html для shader dev

**Day 4: Shader batch (parallel)**
- Я: transitions (crossfade, flash) + post (vignette, grain, bloom) = 3 часа
- Agent 1: sphere_scene + particle_swarm = 1.5 часа
- Вечер: integration test с 3-scene demo

**Day 5: End-to-end**
- Утро: build_demo.py на нашем проекте (адаптировать под min set)
- День: lint 0/0, sanity check
- Вечер: v50 snapshot + MD5

**Day 6-7: Buffer**
- Bug fixes
- Visual polish
- Documentation

**TOTAL v50: 5-7 дней = 1 неделя**

### v51 — full demo (после v50, +3-4 дня)

- anxiety_mist.frag (1-2 часа)
- morph_grid.frag (1-2 часа)
- cozy_room_sdf.frag (2-3 часа)
- credits.frag + string params (4-8 часов)
- Real music test (1-2 дня)

### v52 — GLM integration (+2-3 дня)

- GLM behavior test (10 tasks)
- Policy iteration
- Polish

---

## 6. Сводная таблица

| Сценарий | Время до v50 | Время до v52 (full) |
|----------|--------------|---------------------|
| Sequential, full set | 9-12 дней | 13-17 дней |
| Sequential, minimal v50 | **5-7 дней** | 10-14 дней |
| 2 agents, minimal v50 | 4-6 дней | 8-12 дней |
| 3 agents, minimal v50 | 4-6 дней | 8-12 дней |
| 5+ agents, minimal v50 | 4-5 дней | 8-11 дней |

**Recommended:** minimal v50 + 1 parallel agent (shader writer) = **4-6 дней до рабочего demo**.

---

## 7. Может ли LLM написать ВСЕ шейдеры?

**Да.** Оценка по конкретным шейдерам:

| Шейдер | Я пишу? | Время | Сложность |
|--------|---------|-------|-----------|
| nebula_raymarch.frag | ✅ | 1 час | Extract из shaders.h |
| sphere_scene.frag | ✅ | 30 мин | Standard SDF |
| particle_swarm.frag | ✅ | 1 час | Reuse из shaders.h |
| anxiety_mist.frag | ✅ | 1-2 часа | Original creative |
| morph_grid.frag | ✅ | 1-2 часа | Original creative |
| cozy_room_sdf.frag | ✅ | 2-3 часа | uPrimitives integration |
| credits.frag | ⚠️ | 4-8 часов | Text rendering (новое) |
| crossfade.frag | ✅ | 30 мин | Design есть |
| flash.frag | ✅ | 30 мин | Design есть |
| bloom.frag | ✅ | 1 час | Standard |
| grain.frag | ✅ | 30 мин | Standard |
| vignette.frag | ✅ | 15 мин | Trivial |

**Итого: 10-15 часов = 1.5-2 рабочих дня** для всех 12 shaders.

**Главное ограничение:** я не вижу визуальный результат. Нужно:
1. `glslangValidator` — compile check (0.5с)
2. `preview.html` с hot-reload — visual check
3. User feedback для polish

С этой петлёй обратной связи — могу писать shaders наравне с человеком, в 3-5× быстрее на standard work.

---

## 8. Итог

### Реалистичный timeline

**v50 (минимальный рабочий demo): 5-7 дней = 1 неделя**
- 3 scenes (nebula, sphere, particles)
- 2 transitions (crossfade, flash)
- 3 post (vignette, grain, bloom)
- Synthetic soundtrack
- Lint 0/0

**v51 (full demo): +3-4 дня**
- +4 scenes (anxiety_mist, morph_grid, cozy_room_sdf, credits)
- Real music test

**v52 (production): +2-3 дня**
- GLM behavior test
- Polish

**Total до production-ready: 10-14 дней = 2 недели** (sequential, я делаю всё)

### С parallel agents

| Config | v50 | Full |
|--------|-----|------|
| 1 (только я) | 5-7 дней | 10-14 дней |
| 2 agents | 4-6 дней | 8-12 дней |
| 3+ agents | 4-5 дней | 8-11 дней |

**Parallel saving: 20-30%.** Bottleneck — Lead work (setup + integration + testing), не shader writing.

### Может ли LLM писать shaders?

**Да, может.** Преимущества separate .frag файлов:
- Syntax highlighting
- glslangValidator directly
- Single source (no duplication)
- Hot-reload
- Scene Manager manifest compatible

**Скорость:** 10-15 часов на 12 shaders = 1.5-2 дня.

### Что ОПТИМИЗИРУЕТ время

1. **MVP v50** — 3 scenes вместо 7, остальное в v51
2. **Hot-reload в preview.html** — instant shader iteration
3. **Отложить GLM test** — не блокирует v50
4. **Отложить real music** — synthetic OK для v50
5. **Отложить credits/string params** — самое сложное, можно позже
6. **Reuse shaders.h code** — nebula, particles уже есть
7. **GL binding параллельно с shaders** — independent work
8. **pip install -e .** — cleaner Python setup
9. **Pre-built glslangValidator.exe в PATH** — reliable validation

**Комбинируя все оптимизации: v50 за 4-6 дней = ~1 неделя.**

### Финальная рекомендация

**Plan: minimal v50 → iterate.**

1. Day 1: setup (5 questions + MSVC + start GL binding)
2. Day 2: GL binding complete + 3 shaders parallel
3. Day 3: integration test с 3-scene demo
4. Day 4: post + transitions
5. Day 5: end-to-end build_demo.py + lint 0/0
6. Day 6-7: buffer + v50 snapshot

**Можно начать СЕГОДНЯ** — нужны только ответы на 5 open questions.
