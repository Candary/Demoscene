# SMT format + Scene Manager concept — финальная оценка

**Документ:** smt_format_and_concept_review.md
**Дата:** 2026-11-08
**Сигил:** `&suggest` — мнение о концепции + расчёт времени внедрения
**Источник:** `upload/SMT_FORMAT.md` + предыдущий `color_matrix_scene_new.zip`
**Контекст:** после разбора `scene_manager_new_response.md`

---

## 1. Мнение о концепции — TL;DR

**Это genuinely impressive engineering.** После прочтения SMT_FORMAT.md концепция стала ещё сильнее, чем в моём первом разборе. Несколько вещей, которые я оценил:

### Что в концепции выше моего уровня design

**1. SMT формат — блестящий выбор**

Текстовый, single-space separator, no JSON parser в C++. Решает сразу 3 проблемы:
- Размер: 56KB на 6-мин шоу (vs 77KB JSON)
- Parsing speed: токены split'ятся по пробелу, no nested structures
- Determinism: всё pre-resolved, рантайм не принимает решений

Грамматика строгая (`meta → audio → sections → clip* → seg* → end`), unknown records = ошибка для валидатора. C++ loader проще, чем JSON parser.

**2. Тотальные функции (`fin()`)**

```cpp
inline double fin(double x) { return std::isfinite(x) ? x : 0.0; }
```

После каждого оператора/функции результат проходит `fin()` — NaN и ±∞ превращаются в 0. Это означает:
- Runtime deterministic на любой T
- Любой T можно "перемотать"
- Нет NaN-инфекции в рендере
- C++ и Python parity проще (нет edge case divergence)

Это **should be в нашем `shaders.h` тоже**. Сейчас `Palette(t)` cos() не clamp'ится. Если t будет NaN — вся палитра NaN.

**3. RPN для expressions — элегантнее чем AST**

Стековая машина ~110 строк C++. Выражение `0.4 + 0.8*audio.energy` компилируется в:
```
n:0.4 n:0.8 v:audio.energy o:* o:+
```

7 токенов, выполняется за 5 stack ops. Vs AST eval — recursive, ~300 строк, harder to verify.

Mutation testing нашёл 2 "equivalent mutants" (pow для neg base и div/0) — эквивалентны именно потому, что `fin()` превращает NaN в 0. **То есть `fin()` упрощает не только runtime, но и testing.**

**4. Effect manifest `bind` поле**

```json
"uMotionSpeed": {
  "type": "float",
  "bind": "0.6 + energy*0.8"
}
```

Клип не указывает uniform — берётся bind по умолчанию. Это означает:
- Клип в show.json — 5-6 строк (только id, effect, start, end, look)
- Manifest — единственный source of truth для uniform'ов
- Новый эффект = новый manifest, без правки C++

**5. Direct_blend флаг**

Эффекты с `direct_blend: true` (particles, flash, titles) рисуются в накопитель с GL blend, **без своего FBO**. В примере 6-мин демо: peak 3 FBO, не 5-7. Это умная оптимизация, которой у меня в Variant E не было.

**6. "Pinned palettes"**

Цвета **закрепляются** в показе с `_source` (версия Color Matrix + запросы). Рантайм Color Matrix не знает. Это решает проблему детерминизма, которую я упустил в Variant D.

**7. Явная дизамбигуация "atom"**

3 разных понятия:
- **Эффект** = шейдерная единица (`nebula_raymarch`)
- **Атом** = управляющий параметр (`feel`, `energy`, `temperature`)
- **Cozy atom** = объект интерьера (`sofa`, `rug`)

В моих variant docs я смешивал эти понятия. Это разделение — must adopt.

**8. Mutation testing для runtime**

9 намеренных порч C++:
- swap mix ↔ step
- swap mod semantics
- boundary clip/segment
- energy interpolation
- section index

7 пойманы, 2 "не пойманы" — эквивалентные мутанты (потому что fin() сглаживает NaN). Это **rare engineering practice** — большинство разработчиков не делают mutation testing.

### Что в концепции слабо

**1. Audio analysis — не проверен на реальной музыке**

> "пороги подбирались, пока синтетическая структура не восстановилась, на реальной музыке это не проверено"

Это **значительный риск**. Реальный трек с:
- Variable tempo (electronic music часто 125→130→125 BPM)
- Complex structure (не стандартные 8-bar sections)
- Polyrhythms (drum & bass, IDM)
- Long ambient sections (no energy delta)

— может дать неправильные markers. Нужно слепое тестирование на 10+ реальных треках разных жанров.

**2. 5 open questions без решений**

Эти блокируют интеграцию:
1. `.smt` vs JSON loader в рантайме
2. String parameters (титры) — нет в v1
3. Variable tempo — постоянный BPM + ручные markers достаточно?
4. Transition junction convention — по началу B или концу A?
5. Terminology — согласны с "эффект / атом / примитив"?

Без ответов — интеграция не начнётся.

**3. GL/GLSL shaders не включены**

7 `.effect.json` манифестов есть, сами `.frag` шейдеры — **0**. Это ~10-15 дней работы шейдер-писателя.

Часть есть в `shaders.h` (nebula, particles, droplets) — нужно извлечь и адаптировать. Но anxiety_mist, morph_grid, cozy_room_sdf, sphere_scene, credits — писать с нуля.

**4. GLM behavior не тестировался**

12 инструментов function-calling готовы, но **модель не запускалась**. Возможные проблемы:
- GLM может выбрать неподходящий эффект (suits не работает как expected)
- GLM может неправильно интерпретировать feel vs temperature
- GLM может злоупотреблять undo/redo
- Lint messages могут быть для GLM непонятны

Нужно 10-20 слепых заданий «собери демо под этот MP3».

**5. MSVC/Windows не проверен**

Мы на Windows 11 + MSVC. Эталон компилировался только g++ 13 на Linux. C++17 standard library должен работать, но:
- `<filesystem>` may differ
- `std::stod` exception handling
- Warning levels different

Нужно проверить и зафиксировать.

**6. String parameters нет — блокирует titles**

В v1 нет строковых параметров. Для `credits` effect нужно:
- Asset-texture (atlas glyphs)
- Или runtime text rendering (freetype / SDF text)

Это **блокирующий пункт** для credits effect. Без этого 6-мин demo example не соберётся полностью.

### Итоговая оценка концепции

| Критерий | Оценка | Комментарий |
|----------|--------|-------------|
| **Архитектура** | ⭐⭐⭐⭐⭐ | SMT + RPN + manifest + total functions — production-grade |
| **Тестируемость** | ⭐⭐⭐⭐⭐ | 71 тест + mutation + fuzzing + independent validator |
| **Документация** | ⭐⭐⭐⭐⭐ | SMT_FORMAT.md — best spec в проекте, с 4 worked examples |
| **Реализованность** | ⭐⭐⭐⭐☆ | Python 100%, C++ 100%, GL 0%, shaders 0%, GLM 0% |
| **Готовность к интеграции** | ⭐⭐⭐☆☆ | 5 open questions, MSVC TBD, real music TBD |
| **Принцип "не плодить инфраструктуру"** | ⭐⭐⭐⭐⭐ | Не создаёт новой инфраструктуры — заменяет мою |

**Вердикт: ✅ Принять концепцию целиком.** Это leap forward от моего `feat_scene_manager_variants.md`. Особенно SMT format и `fin()` semantic — must adopt.

---

## 2. Расчёт времени внедрения

### Decomposition работы

| # | Задача | Зависимости | Тип |
|---|--------|-------------|-----|
| 1 | Ответить на 5 open questions | — | decision (1h) |
| 2 | MSVC build sm_runtime.hpp + conformance.cpp | #1 | sequential (2-4h) |
| 3 | GL binding layer (~400 строк C++) | #2 | sequential (1-2 дня) |
| 4 | Извлечь nebula из shaders.h → .frag + manifest adaptation | #3 | sequential (0.5 дня) |
| 5 | anxiety_mist.frag | #3 | parallel (4-8h) |
| 6 | morph_grid.frag | #3 | parallel (4-8h) |
| 7 | particle_swarm.frag | #3 | parallel (4-6h, есть particles в shaders.h) |
| 8 | cozy_room_sdf.frag | #3 | parallel (6-10h, новый — Cozy primitives rendering) |
| 9 | sphere_scene.frag | #3 | parallel (3-5h, простой SDF) |
| 10 | credits.frag + text rendering solution | #1 (string params) | parallel (8-16h, blocking) |
| 11 | crossfade.frag transition | #3 | parallel (2-4h, design есть в feat_scene_manager.md) |
| 12 | flash.frag transition | #3 | parallel (2-3h) |
| 13 | bloom.frag post | #3 | parallel (3-5h, standard) |
| 14 | grain.frag post | #3 | parallel (1-2h, простой noise) |
| 15 | vignette.frag post | #3 | parallel (1h, тривиальный) |
| 16 | Integration test: build_demo.py на нашем проекте | #4-15 | sequential (1 день) |
| 17 | Real music test (10+ tracks) | #16 | sequential (1-2 дня) |
| 18 | GLM behavior test (10-20 demo-building tasks) | #16 | sequential (1-2 дня) |
| 19 | String parameters design (decision 2) | #1 | parallel (1 день design) |

### Сценарий A: Sequential (без параллельных агентов)

| Phase | Tasks | Days |
|-------|-------|------|
| Setup | #1, #2, #3 | 2 дня |
| Pipeline validation | #4 | 0.5 дня |
| Scene shaders | #5, #6, #7, #8, #9, #10 (sequential) | 4-5 дней |
| Transitions | #11, #12 | 0.5-1 день |
| Post shaders | #13, #14, #15 | 0.5-1 день |
| String params design | #19 | 1 день (параллельно с shader work, но всё равно sequential в голове) |
| Integration | #16 | 1 день |
| Real music test | #17 | 1-2 дня |
| GLM test | #18 | 1-2 дня |
| **TOTAL** | | **11-14 working days** |

**С учётом непредвиденных проблем (integration bugs, MSVC quirks, shader debugging): +20% buffer**

**Realistic sequential: 13-17 working days = ~3 weeks**

### Сценарий B: Parallel agents (6-10 агентов)

| Agent | Tasks | Days |
|-------|-------|------|
| Agent 1 (main) | #1, #2, #3, #4, #16 | 3.5 дня (setup + integration) |
| Agent 2 | #5 anxiety_mist | 1 день |
| Agent 3 | #6 morph_grid | 1 день |
| Agent 4 | #7 particle_swarm | 0.5 дня (есть particles) |
| Agent 5 | #8 cozy_room_sdf | 1.5 дня (новый) |
| Agent 6 | #9 sphere_scene + #15 vignette | 0.5 дня |
| Agent 7 | #10 credits + #19 string params | 2 дня (blocking) |
| Agent 8 | #11 crossfade + #12 flash | 0.5 дня |
| Agent 9 | #13 bloom + #14 grain | 0.5 дня |
| Agent 10 (test) | #17, #18 (после #16) | 3 дня |

**Critical path:**
- Setup (#1-3): 2 дня (Agent 1)
- Pipeline validation (#4): 0.5 дня (Agent 1, после #3)
- Parallel shader work (#5-15): max 2 дня (Agent 7 — string params — bottleneck)
- Integration (#16): 1 день (Agent 1, после всех shaders)
- Testing (#17, #18): 3 дня (Agent 10)

**Critical path total: 2 + 0.5 + 2 + 1 + 3 = 8.5 дней**

**С учётом координации (sync между агентами, code review, integration debugging): +20% buffer**

**Realistic parallel: 9-11 working days = ~2 weeks**

### Сценарий C: Hybrid (3 агента — recommended)

| Agent | Tasks | Days |
|-------|-------|------|
| Agent A (lead) | #1, #2, #3, #4, #16 | 3.5 дня |
| Agent B (shader writer 1) | #5, #6, #7, #11, #12, #13 | 2-3 дня sequential внутри агента |
| Agent C (shader writer 2) | #8, #9, #10, #14, #15, #19 | 2-3 дня sequential внутри агента |
| Test phase (Agent A) | #17, #18 | 3 дня |

**Critical path: 3.5 + 3 + 3 = 9.5 дней**

**С координацией: 10-12 working days = ~2 weeks**

### Сравнение сценариев

| Сценарий | Agents | Время | Saving | Coordination overhead |
|----------|--------|-------|--------|----------------------|
| Sequential | 1 | 13-17 дней | baseline | 0 |
| Hybrid (recommended) | 3 | 10-12 дней | 25% | низкая |
| Full parallel | 10 | 9-11 дней | 35% | высокая (sync, code review) |

### Почему не 80% saving при parallel?

Шейдеры — **творческая работа**, не mechanical. Каждый shader:
- SDF functions (unique per effect)
- Color logic (per mood)
- Animation curves (per atom)
- Validation (glslangValidator)
- Visual testing (preview.html)

Даже если 6 агентов пишут 6 shaders параллельно — каждый шейдер ~1 день работы. **Parallel даёт 6 дней → 1 день, но не 6 дней → 0.5 дня.**

Plus integration testing — sequential (нельзя тестировать то, чего ещё нет).

### Реалистичный план с buffer

| Phase | Days (sequential) | Days (3 agents) |
|-------|-------------------|------------------|
| Setup + decisions | 2 | 2 |
| Pipeline validation (nebula adapt) | 0.5 | 0.5 |
| Shader writing (10 shaders) | 5-7 | 2-3 (parallel) |
| Integration testing | 1 | 1 |
| Real music test | 1-2 | 1-2 |
| GLM behavior test | 1-2 | 1-2 |
| **Buffer 20%** | +2-3 | +1.5 |
| **TOTAL** | **13-17 дней (3 недели)** | **9-12 дней (2 недели)** |

---

## 3. Конкретный план внедрения (рекомендуемый)

### Week 1 (setup + critical path)

**Day 1:**
- Ответить на 5 open questions (1h decision time)
- MSVC build sm_runtime.hpp + conformance.cpp (verify на Windows 11)
- Если build fails — фикс warnings/quarks (2-4h)

**Day 2-3:**
- GL binding layer (~400 строк C++):
  - FBO pool (`fbo0`, `fbo1`, `fbo2`, `screen`)
  - Shader loading по effect ID (manifest → .frag mapping)
  - Uniform binding по name (reflection or explicit map)
  - Pass executor: CLEAR / RENDER / DRAW / COMPOSITE / TRANSITION / POST / PRESENT
  - Standard uniforms: uTime, uClipTime, uProgress, uGlobalTime, uResolution, uSeed, uBeat, uBeatPhase, uBarPhase, uEnergy

**Day 4:**
- Извлечь nebula из `shaders.h` → `nebula_raymarch.frag`
- Адаптировать uniforms под manifest (uPrimaryColor, uAccentColor, uIntensity, uMotionSpeed)
- Test: запустить минимальный SMT (1 clip, 1 seg) — должно рендерить nebula

**Day 5:**
- Transition shaders (crossfade, flash) — design есть в `feat_scene_manager.md`
- Post shaders (vignette, grain, bloom) — standard implementations
- Test: 2-scene demo with crossfade + vignette

### Week 2 (shader work, parallel)

**Day 6-7 (parallel if 3 agents):**
- Agent B: anxiety_mist, morph_grid, particle_swarm (3 shaders)
- Agent C: cozy_room_sdf, sphere_scene, credits (3 shaders)

**Day 8:**
- String parameters design (decision 2) — title rendering via SDF text или atlas
- Implement credits.frag с text support

**Day 9:**
- Integration test: запустить `examples/build_demo.py` на нашем проекте
- Verify: 6-min demo рендерится end-to-end
- Lint должен давать 0 errors / 0 warnings

### Week 3 (testing + iteration)

**Day 10-11:**
- Real music test: 5-10 tracks разных жанров
- Verify markers (drop, build, breakdown) на слух
- Iterate audio analysis thresholds если необходимо

**Day 12-13:**
- GLM behavior test: 10 demo-building tasks
- Evaluate tool-use patterns
- Iterate `policy/scene_policy.md` если GLM ошибается

**Day 14:**
- Финальная сборка: v50 multi-scene demo
- Snapshot, MD5, deliverable
- Documentation update

### Buffer (Day 15-17):
- Непредвиденные проблемы
- Visual polish
- Performance tuning

**TOTAL: 14-17 days = 3 weeks (sequential)**
**With 3 parallel agents: 10-12 days = 2 weeks**

---

## 4. Риски и mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| MSVC build fails | Medium | Low (2-4h fix) | Стандарт C++17, должен работать |
| GL binding complex | Medium | High (1-2 дня) | Use existing opengl_loader.h, gradual implementation |
| Shader writing slow | High | Medium (2-3 дня buffer) | Reuse shaders.h code where possible |
| Real music analysis fails | High | Medium (audio markers wrong) | Manual marker verification + iterate thresholds |
| GLM misuse tools | Medium | High (bad demos) | 10-20 blind tests, iterate policy |
| String params blocking | High | High (no credits) | Day 8 dedicated to design decision |
| Coordination overhead (parallel) | Medium | Medium (1 день) | Clear specs per agent, code review |

---

## 5. Финальная рекомендация

### Принять концепцию — да.

Это **лучший кусок инженерии в проекте**. SMT format, RPN expression language, mutation testing, effect manifest system — всё production-grade.

### Не пытаться улучшить — сначала интегрировать.

У меня есть 5 variant'ов в `feat_scene_manager_variants.md` — **все они inferior** к этому предложению. Не нужно их смешивать.

### Использовать 3-agent hybrid approach.

| Agent | Role |
|-------|------|
| Lead (я) | Setup, GL binding, integration, testing |
| Shader writer 1 | 3 scene shaders + transitions |
| Shader writer 2 | 3 scene shaders + post + string params |

Это даёт **25% saving vs sequential** при минимальной coordination overhead.

### Реалистичный timeline

- **Sequential (только я):** 3 недели (14-17 дней)
- **3 parallel agents:** 2 недели (10-12 дней)
- **10 parallel agents:** 2 недели (9-11 дней) — max parallel saving 35%, не больше

### Что делать СЕГОДНЯ

1. **Ответить на 5 open questions** (1h)
2. **Запустить MSVC build** sm_runtime.hpp (2-4h)
3. **Если build OK** — начать GL binding layer (day 2-3)

Если ответы на open questions даны и MSVC собирается — концепция готова к интеграции. Шейдеры — параллельная работа, можно начать на day 4.

---

## 6. Итог

**Концепция: ✅ Принять.** SMT format + RPN + manifest + total functions — это leap forward.

**Время внедрения:**
- **Sequential: 3 недели** (14-17 working days)
- **3 parallel agents: 2 недели** (10-12 working days, recommended)
- **10 parallel agents: 2 недели** (9-11 working days, max saving 35%)

**Координация parallel agents:**
- 3 agents — low overhead, 25% saving
- 10 agents — high overhead, 35% saving, complexity не стоит того

**Рекомендация:** 3-agent hybrid (Lead + 2 shader writers). 2 недели до рабочего multi-scene Demo compo-ready v50.
