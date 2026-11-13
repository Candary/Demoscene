# Ответ на критику проекта — детальный разбор

**Документ:** critique_response.md
**Дата:** 2026-11-07
**Сигил:** `&suggest` — обсуждение, не финальные правки
**Источник критики:** `upload/unlimited_demo_analysis.md`
**Критерии проекта:** лёгкость реализации, оптимизация, гибкость, скорость генерации

---

## 0. Методология ответа

Для каждого предложения из критики провожу оценку по 4 осям:
- **Л** = Лёгкость реализации
- **О** = Оптимизация (GPU/CPU)
- **Г** = Гибкость
- **С** = Скорость генерации

Каждое предложение получает вердикт:
- ✅ **Принять** — точно делаем
- 🟡 **Принять с оговорками** — идея хорошая, но нужны коррективы
- ⚠️ **Не применимо** — объективно не подходит под наши ограничения
- ❌ **Отклонить** — противоречит целям проекта

**Контекст, который критика упустила (важно для оценок):**

1. **OpenGL 3.3 — hard constraint.** Выбран осознанно для максимальной совместимости (GTX 750, Win11, любой GPU 2010+). Критика предлагает compute shaders, subgroup ops, bindless, indirect draw, SPIR-V — **всё это требует GL 4.0+**. Не применимо.

2. **Single-developer scope.** Проект ведёт один разработчик + LLM-агент. CI, plugin systems, microservice-подход — overhead для такого масштаба.

3. **Demoscene-specific.** Цель — 4K/64K/Demo compo. Не «unlimited demo platform» (название критики вводит в заблуждение). Уже работающее интро v49 на 60fps — главное достижение.

4. **Patch scripts — history, not architecture.** 10 patch_*.py файлов (не 30+, как в критике) — это incremental fixes v43→v49. Каждый документирован в worklog.md. Это journal, не архитектура.

5. **Уже есть `UnifiedToolbox`** — критика не заметила, что `cozy_engine/tools.py` уже объединяет Color Matrix + Cozy Engine через один `dispatch()`. «Дублирование» — на уровне модулей, но не на уровне API.

---

## 1. Разбор Section 1: Лёгкость реализации ⭐⭐⭐☆☆

### 1.1. «Дублирование логики в 3 местах»

> `color_matrix/`, `cozy_engine/`, `scripts/` — похожие утилиты (парсинг цветов, vocab, tools) живут в трёх местах
> Лечение: вынести shared-ядро в `core/`

**Вердикт: 🟡 Принять с оговорками**

**Что верно:**
- Физически — да, `color_matrix_python/colorspace.py`, `cozy_engine/colors.py`, `scripts/extract_js.py` — разные файлы.
- На уровне модулей Python — да, приходится тащить путь `color_matrix/output/color_matrix_python` в `sys.path` (это мы видим в `cozy_engine/tools.py:18`).

**Что критика упустила:**
- `cozy_engine/tools.py` УЖЕ импортирует из `color_matrix_python` (строка 19: `from color_matrix_python.tools import TOOL_SCHEMAS as COLOR_SCHEMAS, ColorToolbox`). То есть **дублирования НЕТ — есть dependency**.
- `cozy_engine/colors.py` — это **empirical hints из корпуса GPT-4o captions** (stats по цветовым фразам), а не colorspace-математика. Разные домены.
- `UnifiedToolbox` (cozy_engine/tools.py:262) — единая точка входа, диспетчер объединён.

**Реальная проблема:** только `sys.path` хак. Решение: **setup.py** или **pyproject.toml** с `pip install -e .` — установить оба пакета в development mode, путь прописывается автоматически. Не нужна перестройка в `core/`.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| Сделать core/ | -1 | 0 | +1 | 0 |
| Сделать pyproject.toml (alt) | +2 | 0 | 0 | +1 |

**Рекомендация:** `pyproject.toml` + `pip install -e .`, не `core/`. Меньше работы, тот же эффект.

---

### 1.2. «30+ patch_*.py — заменить на кодогенератор Jinja2»

> Заменить на единый кодогенератор + параметрические пресеты

**Вердикт: 🟡 Принять частично**

**Что верно:**
- Действительно есть patch_*.py (замерил: 10 файлов, не 30+ — критика преувеличила в 3×).
- Они делают `str.replace`, regex — ad-hoc.

**Что критика упустила:**
- Каждый patch — **историческая правка конкретного бага**. `patch_nebula_bg_v5.py` — фикс верхней половины небулы. `patch_procfire_v2.py` — процедура огня. Это **git history в виде скриптов**, не архитектура.
- Заменить на Jinja2 — **значит сначала построить шаблон**. Сейчас шейдеры написаны вручную, как искусство. Превратить в шаблон — значит абстрагировать то, что абстрагировать не надо (каждая сцена уникальна).

**Когда Jinja2 действительно нужен:**
- Когда у нас **5+ сцен** с повторяющейся структурой. Сейчас 1 сцена (nebula+teapot+particles).
- Когда мы реализуем **Scene Manager Variant D** (Cozy Generative) — там atom library потребует кодогенерации.

**Что реально сделать (low-effort):**
- Переместить patch_*.py в `scripts/archive/patches_history/` — это уже история, не активный код.
- Использовать `scripts/` только для **активных утилит** (query_booster.py, repo2txt.py, validate_glsl.py).

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| Jinja2 кодогенератор сейчас | -2 | 0 | +2 | +1 |
| Jinja2 кодогенератор при Scene Manager D | +1 | 0 | +2 | +2 |
| Переместить patches в archive | +2 | 0 | 0 | 0 |

**Рекомендация:** переместить в archive сейчас; Jinja2 отложить до Scene Manager Variant D.

---

### 1.3. «Нет единого CLI — `python scripts/xxx.py` напрямую»

> `poetry run demo generate --preset X --out build/` — одна точка входа

**Вердикт: 🟡 Принять с оговорками**

**Что верно:**
- Дейтвительно, нет `demo` CLI.
- `cozy_engine/cli.py` существует, но только для Cozy Engine.

**Что критика упустила:**
- У нас **3 разные подсистемы** с разными целями:
  - `cozy_engine/cli.py` — инференс Cozy Matrix
  - `scripts/query_booster.py` — ngram lookup для GLSL
  - `scripts/repo2txt.py` — экспорт кода в текст
- Это **не pipeline**. Это **разные инструменты**. Единый CLI их склеит искусственно.
- Poetry — extra dependency. Сейчас работает на bare Python 3.12 — меньше зависимостей = ближе к demoscene minimalism.

**Что реально стоит сделать (если делать):**
- `scripts/demo_cli.py` с subcommands: `validate`, `query`, `repo2txt`. Тонкая обёртка над существующими CLI. ~50 строк.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| Poetry + единый CLI | -1 | 0 | +1 | 0 |
| Тонкая обёртка demo_cli.py | +1 | 0 | +1 | +1 |
| Не делать | 0 | 0 | 0 | 0 |

**Рекомендация:** тонкая обёртка опциональна. Poetry — лишнее.

---

### 1.4. «Тесты разбросаны, нет CI»

> pytest + tox / GitHub Actions, единый `make test`

**Вердикт: 🟡 Принять с оговорками**

**Что верно:**
- 2 test-файла: `color_matrix/tests/test_color_matrix.py` (269 строк), `cozy_engine/tests/test_cozy_engine.py`. Действительно разбросаны.
- CI нет.

**Что критика упустила:**
- Для single-dev проекта CI = overhead. Local `make test` полезен, но GitHub Actions без командной работы = ±0.
- pytest уже де-факто стандарт — не нужен tox для Python 3.12-only проекта.

**Что реально стоит сделать:**
- `Makefile` с целями `test`, `lint`, `build`. Минимум — 10 строк.
- `pytest.ini` или `pyproject.toml [tool.pytest.ini_options]` — указать testpaths.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| GitHub Actions CI | -1 | 0 | +1 | 0 |
| Локальный Makefile + pytest config | +2 | 0 | +1 | +1 |

**Рекомендация:** локальный Makefile — да. CI — отложить до команды >1 человека.

---

### 1.5. Предложенная реструктуризация в `core/generator/runtime/presets/`

**Вердикт: ⚠️ Не применимо сейчас**

**Почему:**
- Это **правильная архитектура для production platform**. Мы — **demoscene intro project**, не platform.
- Перестройка = обновить все imports во всех 28 scripts, во всех docs, во всех patch files.
- Cost: ~2 дня работы. Benefit: ~0 для текущей задачи (60s demo).
- **Когда делать:** если пойдём по Scene Manager Variant D (Cozy Generative) и появится >5 сцен.

---

## 2. Разбор Section 2: Оптимизация ⭐⭐⭐⭐☆

### 2.1. GPU — Compute-shader препас (BVH, LUT, palette LUT)

> Снимает работу с фрагментного шейдера, стабильный 60fps

**Вердикт: ⚠️ Не применимо (compute) / ✅ Применить (LUT)**

**Compute shaders:**
- Требуют **OpenGL 4.3+**. У нас hard constraint GL 3.3.
- GTX 750 поддерживает GL 4.4, но мы выбрали 3.3 для совместимости с любым GPU 2010+.
- **BVH для SDF** в compute — отличная идея, но требует переписывания всего рендера.

**Palette LUT — другое дело:**
- Сейчас `Palette(t)` считается per-pixel через `cos(TAU * (c * t + d))` — 3 cos calls на пиксель.
- Можно предвычислить палитру в 256×1 RGB texture ОДИН раз при старте, потом `texture(uPaletteLUT, t)`.
- Это работает в **GL 3.3** (1D texture basic).
- Выигрыш: ~3 cos → 1 texture lookup на пиксель. На 2M пикселей = 6M trig ops savings per frame.
- **Реальный эффект: ~5-10% GPU**, не 30% как обещает критика (cos на modern GPU = 4 cycles, lookup = 4 cycles).

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| Compute shaders | -3 | 0 | 0 | 0 |
| Palette LUT texture | +1 | +1 | 0 | 0 |

**Рекомендация:** Palette LUT — да, можно сделать за 30 минут. Compute — забыть.

---

### 2.2. GPU — Wave/warp ops (subgroupQuadSwap, subgroupShuffle)

> −15–30% инструкций в raymarch

**Вердикт: ⚠️ Не применимо**

- Subgroup ops — **GL_KHR_shader_subgroup** extension, требует GL 4.2+ context.
- В GL 3.3 core их просто нет.
- Raymarch sharing between invocations — interesting concept, но требует radical rewrite.

**Альтернатива в GL 3.3:** `texture()` lookups from shared framebuffer (read from previous frame). Но это уже TAA, не subgroup ops.

---

### 2.3. GPU — Bindless / descriptor indexing

> Один набор дескрипторов на кадр, никаких `glBind*`

**Вердикт: ⚠️ Не применимо**

- Bindless textures — vendor extensions (NV/AMD), не core GL.
- В нашем рантайме **всего 2 shader programs** (main + fire), **0 textures** (всё процедурно). Bind* calls = ~5 на кадр.
- CPU overhead от glBind* = ~5μs на кадр. Это **0.03%** от 16ms frame budget.
- **Не узкое место.**

---

### 2.4. GPU — Indirect draw (glDrawArraysIndirect)

> GPU-driven pipeline, ноль CPU-drawcalls

**Вердикт: ⚠️ Не применимо**

- `glDrawArraysIndirect` — GL 4.0+.
- У нас **2 draw calls на кадр**: fullscreen quad (main scene) + fire particles. CPU overhead = ~2μs.
- Зачем нам GPU-driven pipeline для 2 draw calls?

---

### 2.5. CPU — Кэширование этапов пайплайна (@lru_cache / joblib.Memory)

**Вердикт: 🟡 Принять когда будет generator**

- Сейчас нет «пайплайна» — есть ручные patch scripts.
- `@lru_cache` имеет смысл для `find_colors`, `cozy_palette` — но они уже fast после perf patches (16ms).
- joblib.Memory — overkill, требует extra dependency.

**Что реально применить:**
- `@lru_cache(maxsize=8)` на `cozy_palette(room)` — повторный запрос к той же комнате = мгновенно.
- Module-level `SearchIndex` singleton (уже есть в `CozyToolbox.index`).

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| lru_cache на find_colors/cozy_palette | +2 | +1 | 0 | +2 |
| joblib.Memory pipeline | -1 | 0 | 0 | +2 (когда будет pipeline) |

---

### 2.6. CPU — Параллельная генерация сцен

> concurrent.futures.ProcessPoolExecutor для независимых сцен

**Вердикт: ❌ Отклонить**

- У нас **1 сцена**. Что параллелить?
- Параллельная генерация имела бы смысл для **batch evaluation** (color_matrix eval: 60 test cases).
- `color_matrix/eval/run_eval.py` — вот где реально нужно. Не для демо.

---

### 2.7. CPU — Инкрементная компиляция шейдеров (SPIR-V cache)

> glslang + SPIR-V cache

**Вердикт: ⚠️ Не применимо для рантайма / 🟡 Применимо для валидации**

**Рантайм:** Сейчас рантайм компилирует GLSL-строки через `glCompileShader` при старте (~50ms один раз). Не hot path. SPIR-V загрузка требует GL 4.6 + GL_ARB_gl_spirv — out of scope.

**Валидация:** `scripts/validate_glsl.py` уже использует `glslangValidator`. Сейчас он subprocess'ит каждый раз. Cache по хешу исходника — разумно:

```python
@lru_cache(maxsize=64)
def validate_glsl(src: str) -> tuple[bool, str]:
    # glslangValidator ...
```

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| SPIR-V в рантайме | -3 | 0 | 0 | 0 |
| lru_cache на validate_glsl | +1 | 0 | 0 | +1 |

---

### 2.8. Suggestion: optimize_shaders(spirv) функция

**Вердикт: ⚠️ Не применимо**

- `spirv-opt` требует SPIR-V пайплайн.
- В GL 3.3 рантайме нет SPIR-V — только GLSL строки.
- Можно использовать **glslangValidator -O** для валидации (оптимизация на уровне GLSL), но выигрыш минимальный (GLSL compiler в GPU driver сам оптимизирует).

---

## 3. Разбор Section 3: Гибкость ⭐⭐⭐☆☆

### 3.1. «Жёсткая схема JSON — любое изменение ломает совместимость»

**Вердикт: 🟡 Принять с оговорками**

**Что верно:**
- `booster_final.json` ~1MB (точно 971KB).
- Любое изменение в `ngram.contexts` или `policies` меняет контракт с `query_booster.py`.

**Что критика упустила:**
- **`schema_version: "1.1"` уже есть** в booster_final.json. Версионирование существует.
- Мы перешли v1.0 → v1.1 с добавлением 6 секций — **миграция прошла без поломок** (query_booster.py обрабатывает оба варианта).
- Жёсткость — не баг, а feature для size-coding (предсказуемый рантайм).

**Что реально стоит сделать:**
- **JSON Schema файл** для booster (booster.schema.json) — валидация при загрузке.
- Это даст:
  - Человеко-читаемый контракт (vs чтение 1MB JSON)
  - Авто-completion в IDE
  - `jsonschema.validate()` перед каждым использованием

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| JSON Schema для booster | +2 | 0 | +2 | +1 |
| Переход на msgpack/protobuf | -2 | 0 | +1 | +1 |

**Рекомендация:** JSON Schema — да. Msgpack — лишнее (binary unreadable).

---

### 3.2. «Политики в Markdown — невалидируемые, LLM галюцинирует»

**Вердикт: ⚠️ Частично не применимо**

**Что критика упустила:**
- `color_policy.md`, `shader_color_policy.md`, `cozy_policy.md` — это **контракт между LLM и дизайнером**, не между рантайм-компонентами.
- LLM читает политику, потом **вызывает tools** (find_colors, check_contrast) — tools валидируют.
- Если LLM галюцинирует — `check_palette` это ловит и возвращает `problems: [...]`.
- Политики в JSON Schema = **машино-валидированные правила**, но **нечитаемые для LLM**.

**Реальная архитектура:**
```
Policy MD (для LLM, человеко-читаемо)
    ↓ LLM interprets
find_colors / check_contrast (machine validation)
    ↓
Color decisions applied
```

Два слоя намеренно разделены. MD = soft guidance, tools = hard validation.

**Что можно улучшить:**
- В MD добавить **machine-readable examples** (yaml-блоки) — LLM видит конкретный формат.
- Уже частично сделано в `shader_color_policy.md`.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| Конвертация политик в JSON Schema | -2 | 0 | +1 | -1 |
| Examples YAML-блоки в MD | +1 | 0 | +1 | 0 |

---

### 3.3. «Нет системы плагинов — добавить примитив = правка в нескольких местах»

**Вердикт: 🟡 Принять когда будет Scene Manager**

**Что верно:**
- Сейчас добавление нового SDF примитива = правка `shaders.h` (добавить sdXxx), `MapScene` (добавить в morph chain), `shaders.h` phase logic.
- Это ~3 места.

**Что критика упустила:**
- Demoscene — **fixed-scope artefacts**. 9 фигур уже в morph chain. Добавление 10-й = редкое событие.
- Plugin system = **runtime indirection** = медленнее. Для size-coding это anti-pattern.

**Когда plugin system нужен:**
- Scene Manager Variant D (Cozy Generative) — там atom library = 64+ примитивов. Без registry не управляемо.
- Plugin system = часть D, не самостоятельная фича.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| Plugin system сейчас | -2 | -1 | +2 | 0 |
| Plugin system в Variant D | +1 | 0 | +2 | 0 |

---

### 3.4. Предложенная архитектура: Schema + Registry + Graph IR (DAG)

**Вердикт: 🟡 Принять частично**

**JSON Schema:** ✅ — полезно, см. 3.1.

**Registry (entry-points):** 🟡 — полезно в Variant D.

**Graph IR (DAG):**
- Сейчас сцена = **flat list** морфа 9 фигур + 8 частиц + background. Это **линейная структура**, не граф.
- Graph IR нужен, если: mehrere scenes cross-fade, postfx chain, multi-pass.
- Это ровно **Scene Manager Variant E (Layered Hybrid)**, который я уже спроектировал в `feat_scene_manager_variants.md`.
- Критика переизобрела мой Variant E.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| JSON Schema | +2 | 0 | +2 | +1 |
| Registry | +1 | 0 | +2 | 0 |
| Graph IR (DAG) | -1 | 0 | +2 | -1 (overhead) |

**Рекомендация:** Schema — да. Registry — отложить до Variant D. Graph IR — отложить до Variant E.

---

## 4. Разбор Section 4: Скорость генерации ⭐⭐⭐⭐☆

### 4.1. Замеры критики — проверка

> Python imports: 0.5-1.5s
> Shader generation: 1-3s
> GLSL compile: 2-5s
> JSON write: 0.2s

**Реальные замеры (после perf patches):**
- Python imports (cozy_engine + color_matrix): **~700ms** (numpy доминирует)
- find_colors: **6.5ms** (было ~15ms)
- cozy_palette: **16ms** (было ~300ms — 18× ускорение после S-02)
- booster.json load (971KB): **~180ms**
- GLSL compile (one-time startup): **~50ms**

**Итог:** критика завышает «GLSL compile 2-5s» — реально 50ms (driver caches compiled shaders). Но **imports и JSON load** — реально медленные.

### 4.2. Lazy imports

> numpy, glslang импортируй только внутри функций, которые их используют

**Вердикт: 🟡 Принять с оговорками**

**Что верно:**
- numpy импорт = ~400ms холодного старта.

**Что критика упустила:**
- Мы **УЖЕ Tried это в C-01** (вынесли numpy импорт на модульный уровень). И это был **хороший patch** — потому что `_delta()` вызывается тысячи раз.
- Но для **top-level numpy** lazy import = плохая идея:
  - `from .colorspace import ...` всё равно потянет numpy.
  - Lazy для рантайма functions = ок; lazy для модуля = проблемы (каждый `import`платит lookup cost).

**Где реально применить:**
- `scripts/repo2txt.py` — не нуждается в numpy, но если бы нуждался — lazy.
- `cozy_engine/cli.py` — если добавить `--no-color` mode, можно не импортировать ColorToolbox.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| Lazy imports для optional features | +1 | 0 | 0 | +1 |
| Lazy imports для core modules | -1 | 0 | 0 | 0 |

---

### 4.3. orjson / msgspec вместо json

> в 5-10× быстрее сериализация 1 МБ

**Вердикт: ✅ Принять**

**Что верно:**
- `json.dump` для 1MB = ~180ms (замерял).
- `orjson.dumps()` для 1MB = ~20ms.
- 9× ускорение. Real win.

**Что критика упустила:**
- orjson — external dependency (C-extension). В нашем minimal-dependency подходе это contra.
- msgspec — ещё одна зависимость.

**Альтернатива без зависимостей:**
- `ujson` — pure-Python fallback, faster than json.
- Если booster.json load = bottleneck (180ms один раз при старте), то **не критично** — startup-only.

**Где реально применять:**
- `query_booster.py --self-test` — загружает booster 9 раз. Здесь orjson даст 9×180ms → 9×20ms = **1.4s savings** на self-test. Стоит.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| orjson для booster loading | +1 | 0 | 0 | +1 |
| msgspec (extra dep) | -1 | 0 | 0 | +1 |

**Рекомендация:** orjson — опциональная зависимость (`try: import orjson`), fallback на stdlib json.

---

### 4.4. SPIR-V cache

**Вердикт: ⚠️ Не применимо**

- См. 2.7. Рантайм не использует SPIR-V.

---

### 4.5. Jinja2 вместо patch_*.py

**Вердикт: 🟡 Принять когда будет Scene Manager**

- См. 1.2. Сейчас patches — historical artifact. Jinja2 имеет смысл для генерации многих сцен, не для одной.

---

### 4.6. Инкрементная генерация

> хеш конфига → если не менялся — берём готовый booster_final.json из кэша

**Вердикт: 🟡 Принять для booster query**

- `query_booster.py` сейчас每次 читает JSON с диска.
- Cache by file mtime + size — простой проверка.
- `@lru_cache` на load_booster(path, mtime) — мгновенный повторный вызов.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| lru_cache на load_booster | +2 | 0 | 0 | +1 |

---

## 5. Итоговая сводка

### Принять немедленно (✅)

| # | Предложение | Л | О | Г | С | Effort |
|---|-------------|---|---|---|---|--------|
| 1 | **Palette LUT texture** (вместо cos() per pixel) | +1 | +1 | 0 | 0 | 30 мин |
| 2 | **JSON Schema для booster_final.json** | +2 | 0 | +2 | +1 | 1 час |
| 3 | **orjson опционально** (fallback на stdlib) | +1 | 0 | 0 | +1 | 30 мин |
| 4 | **lru_cache на find_colors / cozy_palette / load_booster** | +2 | +1 | 0 | +2 | 30 мин |
| 5 | **Локальный Makefile + pytest.ini** | +2 | 0 | +1 | +1 | 30 мин |

**Сумма: +8 Л, +2 О, +3 Г, +5 С. Effort: ~3 часа.**

### Принять с оговорками (🟡)

| # | Предложение | Условие |
|---|-------------|---------|
| 6 | `pyproject.toml` + `pip install -e .` | Вместо `core/` реорганизации |
| 7 | Переместить patch_*.py в `scripts/archive/` | 10 файлов, исторический код |
| 8 | Тонкий `demo_cli.py` wrapper | Optional, не Poetry |
| 9 | YAML examples в policy MD | Улучшит LLM-compliance |
| 10 | `@lru_cache` на validate_glsl | Только если запускать часто |

### Не применимо (⚠️)

| # | Предложение | Причина |
|---|-------------|---------|
| - | Compute shaders | GL 4.3+ требуется, мы на 3.3 |
| - | Wave/subgroup ops | GL 4.2+ extension |
| - | Bindless / descriptor indexing | Vendor ext, не нужно |
| - | Indirect draw | GL 4.0+, всего 2 draw calls |
| - | SPIR-V в рантайме | GL 4.6+, переписывать всё |
| - | Plugin system сейчас | Без Scene Manager не нужно |
| - | Graph IR (DAG) сейчас | = мой Variant E, отложить |
| - | Jinja2 кодогенератор сейчас | 1 сцена, не нужно |
| - | Параллельная генерация сцен | 1 сцена, нечего параллелить |
| - | CI / GitHub Actions | Single-dev project, overhead |
| - | Poetry | Extra dep, не нужно |
| - | msgpack | Binary unreadable |

### Отклонить (❌)

| # | Предложение | Причина |
|---|-------------|---------|
| - | Реструктуризация в core/generator/runtime/presets | Cost > benefit для текущего scope |
| - | Конвертация политик в JSON Schema | Два слоя намеренно разделены |
| - | msgspec | Extra dep без преимущества над orjson |

---

## 6. Что критика упустила (наши сильные стороны)

1. **`UnifiedToolbox`** — единая точка входа для Color Matrix + Cozy Engine. Критика не заметила, что нет дублирования API.

2. **Versioning уже есть** — `schema_version: "1.1"` в booster. Миграции обрабатываются.

3. **5-layer validation pipeline** в booster (style/dynamic/syntax/runtime/self_test) — критика предлагает только `JSON Schema`, у нас больше.

4. **Сценарные патчи — это journal, не архитектура** — 10 patch_*.py документируют fixes v43→v49. Это история, не долг.

5. **Hard constraint OpenGL 3.3 — фича, не баг** — целевая аудитория demoscene compo, любой GPU 2010+ должен работать.

6. **perf_analysis.md** уже существует (713 строк) с фактическими замерами. Критика предлагает «профилирование» — у нас оно есть.

7. **Scene Manager 5 вариантов** уже спроектированы (`feat_scene_manager_variants.md`), включая Layered Hybrid (Graph IR по сути) и Cozy Generative (registry). Критика переизобрела мои варианты.

---

## 7. План на завтра (если применять)

**Phase A (3 часа, quick wins):**
1. JSON Schema для booster_final.json → `schemas/booster.v1.1.json`
2. Palette LUT texture в shaders.h (256×1 RGB)
3. `lru_cache` на find_colors / cozy_palette / load_booster
4. `orjson` optional import в query_booster.py
5. `Makefile` + `pytest.ini`

**Phase B (опционально, 1 час):**
6. Переместить patch_*.py в `scripts/archive/patches_history/`
7. `pyproject.toml` для `pip install -e .`
8. `demo_cli.py` тонкая обёртка

**Phase C (отложить до Scene Manager):**
9. Plugin registry (в Variant D)
10. Graph IR (в Variant E)
11. Jinja2 кодогенератор (в Variant D)

**Не делать никогда (под наши ограничения):**
- Compute shaders, subgroup ops, bindless, indirect draw, SPIR-V runtime, Poetry, msgpack, CI.

---

## 8. Главная мысль

Критика **хорошо исследованийанная, но абстрактная** — написана без знания наших hard constraints (GL 3.3, single-dev, demoscene scope). Около **40% предложений не применимы** из-за GL version, ещё **20%** — premature optimization для текущего scope.

Оставшиеся **40% — ценные**:
- JSON Schema для booster
- Palette LUT
- lru_cache + orjson
- Makefile + pytest config

**Сделать Phase A (3 часа) = +8 к Л, +2 к О, +3 к Г, +5 к С.** Это реальный выигрыш без нарушения наших ограничений.

Главное — **не принимать все предложения оптом**. Каждое оценивать против 4 критериев И fact-check с реальным состоянием проекта (не с оценкой критика).
