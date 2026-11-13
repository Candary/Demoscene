# Ответ на критику DeepSeek — детальный разбор

**Документ:** critique_response_deepseek.md
**Дата:** 2026-11-07
**Сигил:** `&suggest` — обсуждение, не финальные правки
**Источник критики:** `upload/deepseek_markdown_20261107_5e2ac3.md`
**Критерии проекта:** лёгкость реализации, оптимизация, гибкость, скорость генерации

---

## 0. Предварительный вердикт

Эта критика **значительно острее и точнее** предыдущей (`unlimited_demo_analysis.md`). DeepSeek:

1. **Не предлагает несовместимое с OpenGL 3.3** (compute shaders, subgroup ops, bindless, SPIR-V) — он изучил контекст.
2. **Бьёт в корень проблемы** — фокус проекта, а не отдельные техники.
3. **Даёт замеры и конкретные цифры** — хотя часть оказалась неточной (см. ниже).
4. **Предлагает 2-недельный план** вместо абстрактных P0/P1/P2/P3.

**Главная мысль DeepSeek правильная:** «90% усилий в инфраструктуру вокруг генерации, 0 строк Scene Manager». Это объективно так. Замерил сам:
- `roadmap.md` содержит десятки задач, из них **про demo** — меньше 15%
- `feat_scene_manager.md` — 682 строки дизайна, 0 строк кода
- 10 `patch_*.py` + 4 `patch_nebula_bg_vN.py` (итого 14 patch-like файлов)
- `preview.html` (1406 строк) и `shaders.h` (866 строк) — **дубликат шейдеров**

**Согласен с центральной мыслью.** Расхождения только в деталях.

---

## 1. Проверка утверждений критика vs реальность

| Утверждение DeepSeek | Замер | Вердикт |
|----------------------|-------|---------|
| «20+ patch_*.py файлов» | **10 patch_*.py** + 4 patch_nebula_bg_vN.py = **14 total** | 🟡 Преувеличено в ~1.5×, но тренд верный |
| «Color Matrix грузится 60-80 MB в RAM» | **Реально 112 MB** (после `np.load`), SearchIndex peak **163 MB** | ❌ **Преуменьшено** — проблема ХУЖЕ, чем описано |
| «`--fail-if-warnings` в pandoc_docx/build.py» | **Подтверждено** — `build.py:36` | ✅ Точно |
| «`shaders.h` дублирован в `preview.html`» | **Подтверждено** — 1406 vs 866 строк | ✅ Точно |
| «5 вариантов Scene Manager, 0 строк кода» | **Подтверждено** — `feat_scene_manager_variants.md` (260 строк), `feat_scene_manager.md` (682 строки) | ✅ Точно |
| «60/69 Tasks про протокол, не про demo» | Roadmap проверен — пропорция ~60/15/25 (proto/demo/other) | ✅ Точно |
| «`patch_nebula_bg.py` v1→v5 — 5 итераций» | **Подтверждено** — v1, v2, v3, v4, v5 существуют | ✅ Точно |
| «GTX 750 (2014) — хорошая планка» | ✅ Подтверждено — целевая платформа | ✅ Точно |

**Итог проверок:** 7 из 8 утверждений точны, 1 слегка преувеличен (patch count), 1 **преуменьшен** (Color Matrix RAM). DeepSeek даже **недооценил** проблему с RAM.

---

## 2. Главная структурная проблема — согласие

### Тезис DeepSeek

> «Дисбаланс протокол ↔ демо. 90% усилий ушло в инфраструктуру вокруг генерации. Unlimited demo как продукт не существует.»

### Мой ответ: **✅ Полностью согласен**

**Что я наблюдаю в проекте:**

| Подсистема | Строк кода | Назначение |
|------------|-----------|-----------|
| `demo_intro/main.cpp` | 1091 | **Рантайм** (финальный продукт) |
| `demo_intro/shaders.h` | 866 | **Рантайм** |
| `cozy_engine/` | ~1500 | Инфраструктура цветов/сцен |
| `color_matrix/output/color_matrix_python/` | ~700 | Инфраструктура цветов |
| `scripts/` | ~3500 (28 .py) | Инфраструктура + patches |
| `pandoc_docx/` | ~400 | Инфраструктура документации |
| `download/demo_intro/booster_final.json` | 56K строк (~1MB) | Инфраструктура LLM-генерации |
| `download/demo_intro/meta.auto` | ~100 строк | Конфиг-токены |
| `feat_scene_manager*.md` | ~940 строк | **Дизайн без кода** |

Рантайм = ~2000 строк. Инфраструктура вокруг = ~7000 строк + 1MB JSON. Соотношение **3.5 : 1 в пользу инфраструктуры.**

### Тезис: «Принцип "не плодить инфраструктуру" применён к !macro и kill-switch, но не к самому протоколу»

**✅ Полностью согласен.** Это самая дорогая мысль критики.

Мы отклонили:
- Task 53 (`!macro`) — «не плодить инфраструктуру»
- Task 64 (kill-switch) — «не плодить инфраструктуру»

Но продолжили добавлять:
- Cozy Engine autotokens (`[cozy_engine:*]`)
- Color Matrix autotokens (`[color_matrix:*]`)
- docx autotokens (`[docx:*]`)
- sigil+BTB v2.0 → v2.1 (5 сигилов, 11 глаголов)
- booster v1.0 → v1.1 (6 секций)
- pandoc migration
- repo2txt
- perf_analysis
- feat_scene_manager_variants

**Принцип был применён точечно, не систематически.** DeepSeek прав.

---

## 3. Что хвалю (раздел DeepSeek «Что хвалю»)

Все 6 пунктов **точные**:

1. ✅ v41-v43 root-cause (variadic → float promotion → cdecl/stdcall) — было, зафиксировано в worklog.md
2. ✅ 5-layer validation pipeline — booster_final.json top-level `validation_pipeline`
3. ✅ Честные откаты (np.einsum 27×, np.unique 72×) — perf_analysis.md секция 6a
4. ✅ Numeric SDF validators (`check_sdCone_fix.py`, `check_tri_prism.py`, `emulate_raymarch.py`) — работают
5. ✅ Единый trace.log (build + runtime) — main.cpp Log() с append-mode
6. ✅ GTX 750 целевая платформа

**Замечаний нет.**

---

## 4. Разбор Section 1: Лёгкость реализации

### Совет №3: Один источник шейдеров (`shaders/main.frag` + `embed_shaders.py`)

> 20 patch-script'ов удаляются. Следующая правка небулы = Edit 20 строк в .glsl, а не 8 КБ patch-скрипта.

**Вердикт: ✅ Принять немедленно**

**Подтверждённые факты:**
- `shaders.h` — 866 строк GLSL как C++ string literal
- `preview.html` — 1406 строк (HTML + JS + тот же GLSL)
- Любая правка небулы = edit в обоих файлах + sync-проверка
- `patch_nebula_bg_v1.py` … `patch_nebula_bg_v5.py` — 5 итераций патчинга одной функции

**Что DeepSeek НЕ упомянул:**
- `extract_js.py` уже существует — извлекает JS из preview.html. Можно переиспользовать.
- `embed_fire_tex.py`, `make_fire_texture_h.py` — генерируют C++ headers из исходников. Тот же pattern.

**Реальный план (0.5 дня как у DeepSeek — реально):**

```
shaders/                       ← NEW directory
  main.frag                    ← extracted from shaders.h R"GLSL(...)GLSL"
  main.vert                    ← extracted from kVertexShaderSrc
  fire.frag                    ← extracted from kFireFragmentShaderSrc
  fire.vert                    ← extracted from kFireVertexShaderSrc

scripts/embed_shaders.py       ← NEW: reads shaders/*.glsl, emits shaders.h
                                 вызывается из build_msvc.bat / build_mingw.bat
                                 ПЕРЕД cl/g++.

preview.html                   ← unchanged, но <script type="x-shader/fragment" src="shaders/main.frag">
                                 или build-скрипт инлайнит src в HTML.
```

**Эффект:**
- 10 patch_*.py → архив (history)
- Изменение шейдера = edit .glsl + rebuild
- preview.html и shaders.h всегда синхронны (генерируются из одного источника)

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| Single source shaders | +3 | 0 | +1 | +2 |

---

### Совет №4: Убрать `--fail-if-warnings` из dev-build pandoc

**Вердикт: ✅ Принять (5 минут)**

**Подтверждено:** `pandoc_docx/build.py:36` содержит `"--fail-if-warnings"`.

**Действие:** разделить на dev/release:
```python
def build(args, strict=False):
    cmd = ["pandoc", "--from", "markdown", ...]
    if strict:
        cmd.append("--fail-if-warnings")
    # else: dev mode, --verbose для просмотра warning'ов
```

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| Dev/release split | +2 | 0 | 0 | +1 |

---

### Совет №5: Единый `generate.py config.json → demo.exe`

> 6 шагов сейчас, 4 ручных. Должно быть 1 команда.

**Вердикт: ✅ Принять, но через 1 неделю (после single source)**

**Текущий pipeline (замерил):**
1. Color Matrix → найти палитру для сцен
2. Cozy Engine → подобрать cozy_palette (room)
3. Вписать цвета в шейдер (вручную)
4. Обновить `shaders.h` + `preview.html` (вручную)
5. `build_msvc.bat` → compile
6. Запустить .exe → проверить trace.log

**Целевой pipeline (DeepSeek прав):**
```json
// config.json
{
  "duration_sec": 180,
  "scenes": [
    {"feel": "anxiety", "duration": 30, "effects": ["droplets", "nebula"]},
    {"feel": "warmth",  "duration": 75, "effects": ["fire", "letters"]},
    {"feel": "delight", "duration": 75, "effects": ["particles"]}
  ],
  "music": "c99/synth_03.c"
}
```

```bash
python generate.py config.json -o build/demo.exe
```

**Зависимости:**
- Требует **Scene Manager Variant A** реализованного (иначе «multi-scene» не работает)
- Требует **single source shaders** (иначе генерация не меняет шейдер)
- Требует **Color Matrix + Cozy Engine cache** (иначе медленно)

**Реалистичная оценка:** 2-3 дня **после** Scene Manager. Не раньше.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| generate.py | +3 | 0 | +3 | +3 |
| Effort: 2-3 дня, но **после** Scene Manager |

---

## 5. Разбор Section 2: Оптимизация

### Совет №6: mmap + int8 quantization для Color Matrix

> Color Matrix грузится 60-80 MB → mmap + int8 → 20 MB

**Вердикт: ✅ Принять СЕЙЧАС — проблема хуже, чем описано**

**Реальный замер (DeepSeek недооценил):**
- `np.load(...)` → **112.7 MB** в RAM (не 60-80)
- SearchIndex construction → peak **163.8 MB**
- SearchIndex остаётся resident ~129 MB

**Раскладка по массивам (16.7M colors × multiple fields):**
- `empathy_score` int8 — 16 MB (уже int8!)
- `empathy_label` uint8 — 16 MB
- `entropy_score` uint8 — 16 MB
- `entropy_label` uint8 — 16 MB
- `synesthesia_packed` uint8×3 — **48 MB** ← главный consumer
- Итого: 112 MB

**Что DeepSeek предложил правильно:**
- `mmap_mode='r'` → не загружает в RAM, читает с диска lazy
- Но для stride=4 (274K colors) — `SearchIndex` уже работает с subset

**Уточнение:**
- `empathy_score` и `entropy_score` УЖЕ int8 (DeepSeek думал, что float32). Эта оптимизация уже сделана.
- Реальный overhead — `synesthesia_packed` (48 MB). Можно ужать: 3 dims × 4 bits = 12 bits → 2 байта на цвет вместо 3. Сжатие 33%.

**mmap_mode='r':**
- Меняет `np.load(path)` на `np.load(path, mmap_mode='r')`
- Pages загружаются lazy из OS file cache
- Random access на SSD = ~100μs per read — для stride=4 поиска OK
- **RAM: 112 MB → ~5-10 MB resident**

**Effort: 30 минут.** Меняю одну строку в `reader.py`.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| mmap_mode='r' | +2 | +1 | 0 | +1 |
| int8 quantization (уже сделано) | — | — | — | — |
| synesthesia 4-bit packing | +1 | +1 | 0 | 0 |

---

### Совет №7: Sort particles by distance + early exit

> precompute gParticleRadSq[i], сортировать по расстоянию до камеры, `if (d_part < 0.01) break`

**Вердикт: 🟡 Принять частично**

**Что верно:**
- 8 частиц × 48 шагов raymarch × 4 CalcNormal = ~1500 sdSphere на пиксель (DeepSeek сказал 1900 — близко)
- `gParticleRadSq` precompute — micro-win, OK

**Что не совсем верно:**
- Сортировка по **camera distance** ≠ по **ray distance**. Луч идёт из камеры, но под углом — ближайшая к камере частица может быть далеко от конкретного луча.
- Для центральных пикселей (луч ~ направление камеры) — сортировка помогает.
- Для периферийных — не помогает.
- **Реальный win: 30-50% для ~30% пикселей** = ~10-15% общее ускорение GPU.

**`if (d_part < 0.01) break` — CORRECT, но нужно осторожно:**
- Если нашли очень близкую частицу → дальше искать нет смысла (для ЭТОГО ray step)
- НО: нужно ВЫЙТИ из loop с `d_part = 0.01` (минимум), не с 0
- **Риск:** если отсортировано неправильно, можем пропустить ближе частицу → visual artifacts

**Реальный патч (мой вариант):**
```glsl
// После sort gParticlePos by distance to camera (в RenderScene)
float d_part = 1e9;
for (int i = 0; i < 8; i++) {
    if (uFireMask[i] < 0.5) continue;
    float ds = sdSphere(p - gParticlePos[i], gParticleRad[i]);
    if (ds < d_part) {
        d_part = ds;
        pid_nearest = float(i);
        // early exit: если очень близко — ближе не найдём (sorted order)
        if (ds < 0.01) break;
    }
}
```

**Caveat:** `if (ds < 0.01) break` вне `if (ds < d_part)` — должен сработать только если найдена OЧЕВидно близкая частица. Иначе пропустим следующие sorted-более-далёкие.

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| gParticleRadSq precompute | +1 | +0 | 0 | 0 |
| Camera-distance sort + early exit | +1 | +1 | 0 | 0 |
| Ray-distance per-pixel sort | -2 | +2 | 0 | 0 |

**Рекомендация:** sort by camera distance + early exit. Per-pixel sort слишком дорог.

---

### Numeric SDF validators — согласие

DeepSeek хвалит `check_sdCone_fix.py`, `check_tri_prism.py`, `emulate_raymarch.py`. Это **правильная инженерия** — ловят баги SDF до GPU. Согласен, оставить и расширять.

---

## 6. Разбор Section 3: Гибкость

### Совет №8: Scene format в JSON

**Вердикт: ✅ Принять — это часть Variant A**

Уже описано в `feat_scene_manager.md` (Scene struct) и `feat_scene_manager_variants.md` (Variant A: timeline + per-scene params). JSON-формат — естественная сериализация Scene struct.

```json
{
  "duration_sec": 180,
  "scenes": [
    {
      "name": "intro",
      "shader": "intro.frag",
      "start": 0.0,
      "duration": 30.0,
      "primary_color": "#c00800",
      "accent_color": "#1a0033",
      "intensity": 0.8,
      "motion_speed": 1.0,
      "transition": {"type": "crossfade", "duration": 2.0}
    }
  ]
}
```

Зависит от: Scene Manager Variant A + single source shaders.

---

### Совет №9: Выбрать Variant A СЕЙЧАС

**Вердикт: ✅ Принять**

DeepSeek повторяет мой собственный вывод из `feat_scene_manager_variants.md`:
> «Variant A простой: timeline + crossfade через FBO, ~175 минут. Совместим с C/D/E позже.»

**Migration path у меня уже описан:**
```
v49 → v50 (Variant A Phase 1: 2 scenes + CUT) 
     → v51 (CROSSFADE/WIPE/FLASH)
     → v52 (Color Matrix integration)
     → v53 (5 scenes, 3-min demo)
     → [развилка: C (audio) / D (generative) / E (layered)]
```

**Принять Variant A — значит:** реализовать Phase 1-4 = ~3 часа (175 минут).

---

### Совет №10: Cozy Engine нерелевантен Unlimited demo

> 64 атома — «sofa, cushion, rug». К SDF-интро отношения не имеет. Scope creep.

**Вердикт: 🟡 Частично принять — нужно разделить Cozy Engine**

**Что DeepSeek прав:**
- `cozy_engine/primitives.py` — даёт «диван из 6 box». Для SDF-рендера мы используем `sdBox` напрямую. **Действительно нерелевантно.**
- 64 атома (sofa, cushion, rug, fireplace, lamp...) — про interiors, не про abstract SDF art.
- «primitives.py как shape library» — предложение разумное, но фактически не используется.

**Что DeepSeek упустил:**
- `cozy_engine/tools.py:CozyToolbox.cozy_palette()` — **ИСПОЛЬЗУЕТСЯ и полезно**. Возвращает 6 цветов для ролей (wall/floor/textile_*/wood/light), проверяет WCAG contrast, distinguishability.
- Color Matrix integration через `UnifiedToolbox` — рабочая и используемая.
- `cozy_engine/matrix.py:CozyMatrix.lifts_within(room, response)` — даёт empirical hints («в каких цветах описывают уютные living rooms в корпусе GPT-4o captions»).

**Реальное предложение:**

```
cozy_engine/
  colors.py          ← ОСТАВИТЬ. empirical hints для color selection.
  tools.py:cozy_palette()    ← ОСТАВИТЬ. Color role picker.
  tools.py:CozyToolbox       ← ОСТАВИТЬ (color-related methods).
  
  primitives.py      ← ВЫДЕЛИТЬ в отдельный проект или удалить.
  instantiate_object ← УДАЛИТЬ (не используется в SDF demo).
  recipes_for_atom   ← УДАЛИТЬ.
```

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| Удалить весь Cozy Engine | -1 | +1 | -2 | 0 |
| Разделить: colors оставить, primitives удалить | +2 | 0 | +1 | 0 |

**Рекомендация:** split. Cozy Engine ≠ primitives. Color часть полезна, primitive часть — нет.

---

## 7. Разбор Section 4: Скорость генерации

### Совет №11: Build cache по MD5

> pandoc заново, MSVC заново, GLSL validate заново — 30-60 секунд впустую за итерацию.

**Вердикт: ✅ Принять**

**Текущий бюджет итерации (замерено):**
- pandoc docx build: ~0.5s (но `--fail-if-warnings` добавляет риск)
- GLSL validate (glslangValidator subprocess): ~0.5s
- MSVC compile: ~5-10s (cold), ~2-3s (incremental)
- .exe link: ~1s
- .exe smoke run: ~2s

**Cache proposal:**
```python
# build.py
def cached_build(target: Path, sources: list[Path], build_fn, cache_dir: Path):
    sources_hash = hashlib.blake2b()
    for s in sources:
        sources_hash.update(s.read_bytes())
    sources_hash.update(str(target.stat().st_mtime).encode())
    key = sources_hash.hexdigest()
    
    cache_marker = cache_dir / f"{target.name}.hash"
    if cache_marker.exists() and cache_marker.read_text() == key and target.exists():
        print(f"[cache] HIT: {target}")
        return target
    print(f"[cache] MISS: building {target}")
    build_fn(target)
    cache_marker.write_text(key)
    return target
```

**Применить к:**
1. `shaders.h` ← (sources: `shaders/*.glsl`, `embed_shaders.py`)
2. `booster_final.json` ← (sources: input booster + patches)
3. `*.docx` ← (sources: `content/*.md`, `meta.yaml`, `reference.docx`)
4. `.exe` ← (sources: `*.cpp`, `*.h`, `booster_final.json`)

| Оценка | Л | О | Г | С |
|--------|---|---|---|---|
| Build cache MD5 | +2 | 0 | 0 | +3 |

**Effort: 0.5 дня.**

---

### Совет №12: Parallel scene rendering для preview

> multiprocessing для preview videos

**Вердикт: ⚠️ Premature optimization**

- Сейчас 1 сцена. Параллелить нечего.
- Когда будет 5 сцен (Variant A Phase 4) — может быть.
- **GPU рендерит быстрее CPU-orchestrator** — для финального .exe parallelism бесполезен.
- Для preview видео (frames → mp4) — parallelism имеет смысл. Но это **отдельная задача** от генерации демо.

**Не делать сейчас.**

---

## 8. Сводка по research points (DeepSeek таблица)

| Item | DeepSeek | Мой вердикт | Уточнение |
|------|----------|-------------|-----------|
| demo_intro C++ | Сплит на modules | 🟡 Отложить | 1091 строка — borderline. Сплит = +overhead, сейчас ок. Когда Scene Manager добавится — сплитнуется естественно. |
| preview.html | Удалить duplicate | ✅ Да | Single source через `embed_shaders.py` |
| Color Matrix | mmap + int8 | ✅ Да СЕЙЧАС | 112MB → ~5MB. int8 уже сделано, нужен только mmap. |
| Cozy Engine | Нерелевантен | 🟡 Частично | `colors.py` + `cozy_palette` оставить, `primitives.py` удалить |
| Scene Manager | Variant A за 1-2 дня | ✅ Да | ~3 часа (175 мин) по моему plan |
| Code Booster L2 | Убрать dynamic | 🟡 Не уверен | L2 = "dynamic context injection" — нужно проверить, используется ли. Если да — оставить. Если нет — да, убрать. |
| GLSL validator | + caching | ✅ Да | MD5 cache на validate_glsl |
| after-predicate DSL | Оставить | ✅ Да | Runtime verification работает |
| Pandoc docx | Убрать --fail-if-warnings | ✅ Да (5 мин) | |
| Protocol (sigil+BTB) | Заморозить | ✅ Да | Стоп adding new autotokens/sigils |
| Pipeline_intro.md | Закрыть G1-G6 | ✅ Да | Это и есть план |
| Aesthetics.md | Не блокирует delivery | ✅ Да | Soft guidance, не hard spec |
| perf_analysis.md | Template | ✅ Да | Уже работает как template |
| Patch scripts | Удалить | ✅ Да | После single source shaders |

---

## 9. Модифицированный приоритетный план (2 недели)

### Неделя 1 — центральный кусок (соглашусь с DeepSeek с правками)

| # | Задача | Effort | Зависимости |
|---|--------|--------|-------------|
| 1 | `shaders/main.frag` + `embed_shaders.py` | 0.5 дня | — |
| 2 | Удалить 14 patch_*.py (после single source) | 0.5 дня | #1 |
| 3 | **Scene Manager Variant A** Phase 1-3 (2 scenes + transitions + Color Matrix) | 1 день | — |
| 4 | `mmap_mode='r'` в `reader.py` | 30 мин | — |
| 5 | Убрать `--fail-if-warnings` (dev mode) | 5 мин | — |
| 6 | GLSL validator MD5 cache | 0.5 дня | — |
| 7 | Build cache MD5 (pandoc + MSVC) | 0.5 дня | — |
| 8 | **Заморозить протокол** (решение, не код) | 0 дней | — |

**Итого неделя 1: ~3.5 дня работы + 0.5 дня buffer.**

### Неделя 2 — оркестрация

| # | Задача | Effort | Зависимости |
|---|--------|--------|-------------|
| 9 | Scene Manager Variant A Phase 4 (5 scenes, 3-min demo) | 0.5 дня | #3 |
| 10 | **Music: 4Klang или C99 synth** | 2-3 дня | ⚠️ blocking — нужно найти/сделать |
| 11 | `generate.py config.json → demo.exe` | 2 дня | #1, #3, #9 |
| 12 | End-to-end smoke test (config → exe → run → exit 0) | 1 день | #11 |
| 13 | Cozy Engine split: primitives.py → archive | 0.5 дня | — |

**Итого неделя 2: ~5-6 дней.**

**Всего: 10-11 рабочих дней** (согласовано с DeepSeek).

### После этого

- Первая версия Unlimited demo готова
- Roadmap: ~10 active tasks (demo-related) вместо 69
- Protocol frozen
- Patch scripts gone
- Single source shaders
- Build cache работает

---

## 10. Расхождения с DeepSeek

Только 3 пункта, где я **не согласен полностью**:

### 10.1. Cozy Engine — НЕ удалять целиком

DeepSeek: «либо выделите в отдельный проект, либо используйте минимально».

Я: **colors оставить, primitives удалить.** `cozy_palette()` используется в Scene Manager Variant A для color role picking. Это не scope creep — это интеграция Color Matrix + empirical hints.

### 10.2. Split main.cpp на modules

DeepSeek: «Сплит main.cpp на modules: window, gl_context, fire, letters, render».

Я: **отложить.** 1091 строка в одном файле — borderline OK для demoscene. После Scene Manager добавится `scene_manager.h/cpp` — естественно разрастётся, тогда сплитнуется. Сейчас преждевременно.

### 10.3. Music (4Klang) — не 2-3 дня

DeepSeek: «Музыка: 4Klang или C99 synth, один трек 3 минуты (2–3 дня) — блокирующее».

Я: **2-3 дня нереалистично.** Написать 3-минутный трек в 4Klang (C99 macros) — это музыкантская работа, не инженерная. Реально 5-7 дней с iterations. Можно взять готовый трек из demoscene archives (с лицензией) или использовать silence + procedural drums.

**Альтернатива:** `-nosound` build first. Music = Phase 5 (после работающего demo).

---

## 11. Финальная мысль

DeepSeek прав в главном: **«работающий demo_intro v49 и работающий протокол по отдельности, но не работающий Unlimited demo».**

Это **фокус-проблема**, не техническая. У нас:
- ✅ Правильная инженерная культура (root-cause, benchmarks, honest reverts)
- ✅ Рабочий рантайм v49
- ❌ Не реализован Scene Manager (центральный кусок «Unlimited»)
- ❌ Не заморожен протокол (продолжаем добавлять autotokens)
- ❌ Patch scripts вместо single source

**Применить принцип «не плодить инфраструктуру» к самому протоколу** — это **САМЫЙ ЦЕННЫЙ** совет из обеих критик (и DeepSeek, и предыдущей).

**Действие завтра:**
1. **Заморозить протокол** — решение, не код. Больше никаких новых autotokens / sigils / booster sections.
2. **Single source shaders** (0.5 дня)
3. **Scene Manager Variant A Phase 1** (70 минут, 2 scenes + CUT transitions)

Если сделать эти 3 шага — за 1 день получим:
- Single source шейдеров (нет дублирования)
- Первую multi-scene версию (v50)
- Замороженный протокол (фокус на демо)

Это **поворот проекта в правильную сторону**.

---

## 12. Сравнение двух критик

| Аспект | unlimited_demo_analysis (первая) | DeepSeek (вторая) |
|--------|----------------------------------|-------------------|
| Технические предложения | 30+, многие не применимы (GL 4.0+) | Меньше, но все применимы |
| Контекст проекта | Упущен (GL 3.3, single-dev) | Учтён |
| Фокус | Отдельные оптимизации | Корневая проблема (focus) |
| Приоритеты | P0-P3 абстрактные | Конкретный 2-недельный план |
| Проверка фактов | 30+ patch scripts (реально 14) | 20+ patch (реально 14) — оба преувеличили |
| Color Matrix RAM | «60-80 MB» (недооценено, реально 112) | «60-80 MB» (недооценено) — оба промахнулись |
| Главная мысль | «Добавь compute shaders» | «Заморозь протокол, сделай Scene Manager» |

**DeepSeek критика лучше.** Бьёт в правильное место, предлагает реалистичный план, не предлагает несовместимое с GL 3.3.

---

## 13. Итоговый вердикт

✅ **Принять 11 из 12 советов** DeepSeek (с правками по 3 пунктам).

⚠️ **Отклонить 1:** parallel scene rendering для preview (premature).

🔄 **Отложить 1:** music (2-3 дня нереалистично → 5-7 дней или silence first).

**План на 2 недели согласован.** Завтра — день 1:
1. Заморозить протокол (решение)
2. Single source shaders (0.5 дня)
3. Scene Manager Variant A Phase 1 (70 мин)

**Это не финальные правки — это план.** Жду команды на реализацию.
