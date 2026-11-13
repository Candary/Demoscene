# Changed Files — Bundle

**Generated:** 2026-11-07
**Context:** Updates from `&suggest` Scene Manager variants + `!fix perf-all` + `&Предлагаю repo2txt`

## Manifest

### Performance patches (`!fix perf-all`)

| File | Status | Bytes | Change |
|------|--------|-------|--------|
| `cozy_engine/tools.py` | ✅ Applied | 21602 | **C-01**: импорты `numpy`/`colorspace` вынесены на уровень модуля (раньше реимпорт в каждом `_delta`). **S-02**: `cozy_palette` использует broadcasted `delta_e_ok` (8, M) вместо Python-цикла. Эффект: `cozy_palette(living_room)` 300мс → **16мс** (18×) |
| `download/demo_intro/main.cpp` | ✅ Applied | 51521 | **C-03**: `SpawnFireIfNeeded` + `FireMaskValue` объединены в `UpdateFireState` с кэшем `g_fireMaskCache[8]`. Маска вычисляется за один проход по `g_fires`, не 8 раз |
| `color_matrix/output/color_matrix_python/search.py` | ✅ Applied | 10780 | **S-01**: ranking loop в `find()` использует boolean mask + `np.logical_and(out=eligible)` вместо `np.flatnonzero(mind...)` на каждой итерации |
| `cozy_engine/matrix.py` | ❌ Reverted | 11103 | **C-02** (`scan_weights` через `np.unique`) и **S-03** (`rebuild` через `np.einsum`) отменены — замеры показали 72× и 27× regression соответственно. Код возвращён к оригиналу, добавлены explanatory comments |

### New tools

| File | Bytes | Purpose |
|------|-------|---------|
| `scripts/repo2txt.py` | 26181 | Standalone Python script (stdlib only): обходит проект, фильтрует мусор (node_modules, binaries, archives, __pycache__, .venv, lock files, .env), собирает код в один .txt с разделителями `=== FILE: ... ===` / `=== END FILE ===` |
| `download/repo2txt_output.txt` | 4370823 | Демо-выход: 161 файл, 4.4 MB (отсканировано 417, отфильтровано 61%) |

### Documentation

| File | Bytes | Purpose |
|------|-------|---------|
| `download/perf_analysis.md` | 36941 | Performance analysis — обновлён после применения `!fix perf-all`. Включает фактические замеры (Section 6a), что сработало (4 patches) и что отменено (2 patches) с lessons learned |
| `download/feat_scene_manager_variants.md` | 23537 | Scene Manager — 5 архитектурных вариантов (Timeline / Uber Shader / Music-synced / Cozy Generative / Layered Hybrid) с comparison table и рекомендациями по compo category |

## Rollback

`download/archive/pre_perf_patches.zip` содержит оригиналы 4 файлов (до perf-патчей):
- `cozy_engine/tools.py`
- `cozy_engine/matrix.py`
- `color_matrix/output/color_matrix_python/search.py`
- `download/demo_intro/main.cpp`

Откат:
```bash
cd /home/z/my-project && unzip -o download/archive/pre_perf_patches.zip
```

## Apply order (если ставить на чистый проект)

1. C-01 + S-02 → `cozy_engine/tools.py`
2. C-03 → `download/demo_intro/main.cpp`
3. S-01 → `color_matrix/output/color_matrix_python/search.py`
4. matrix.py — НЕТ изменений (reverted, только comments)

Порядок независим — можно в любом.
