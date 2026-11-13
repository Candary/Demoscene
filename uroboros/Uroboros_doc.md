# Uroboros — документация

**Версия:** 0.3.0
**Формат патча:** `uroboros.patch/2`
**Python:** ≥ 3.10

---

## Содержание

1. [Что такое Uroboros](#1-что-такое-uroboros)
2. [Установка](#2-установка)
3. [Архитектура](#3-архитектура)
4. [Быстрый старт](#4-быстрый-старт)
5. [Концепции](#5-концепции)
   - 5.1 [План](#51-план)
   - 5.2 [Патч](#52-патч)
   - 5.3 [Итерация](#53-итерация)
   - 5.4 [Одобрение](#54-одобрение)
   - 5.5 [Обратная связь](#55-обратная-связь)
6. [API Reference](#6-api-reference)
   - 6.1 [`Uroboros`](#61-uroboros)
   - 6.2 [`FileMemory`](#62-filememory)
   - 6.3 [`PatchRegistry`](#63-patchregistry)
   - 6.4 [Модуль `formats`](#64-модуль-formats)
   - 6.5 [Модуль `plan`](#65-модуль-plan)
   - 6.6 [Модуль `adapters`](#66-модуль-adapters)
   - 6.7 [Модуль `glm`](#67-модуль-glm)
7. [Как писать патчи](#7-как-писать-патчи)
8. [Командная строка](#8-командная-строка)
9. [Интеграция с Color Matrix и Cozy Engine](#9-интеграция-с-color-matrix-и-cozy-engine)
10. [Хранилище данных](#10-хранилище-данных)
11. [Примеры](#11-примеры)
12. [Диагностика и типичные ошибки](#12-диагностика-и-типичные-ошибки)
13. [Безопасность](#13-безопасность)
14. [FAQ](#14-faq)

---

## 1. Что такое Uroboros

Uroboros — это **движок итеративного пайплайна**, в котором каждый шаг работы описан объектом `patch` (JSON), а каждый вызов исполняется изолированным Python-скриптом из папки `patches/`. У движка четыре идеи:

1. **Patch-driven.** Единый формат (`uroboros.patch/2`) описывает и операцию, и обратную связь, и одобрение, и запись в память. Никаких разных схем для разных стадий.
2. **File-backed.** Всё состояние — в `.uroboros/`: content-addressed blobs (sha256), кеш по ключу, журнал событий в `memory.jsonl`, история запусков. Нет БД, нет SQLite.
3. **DAG-исполнение.** План — это DAG из узлов с зависимостями (`needs`). Независимые узлы одного слоя выполняются параллельно (`workers`).
4. **Обязательное одобрение.** Движок никогда не считает результат одобренным молча. Если явного `approval` нет — запуск заканчивается в статусе `awaiting_approval`.

Uroboros не зависит от Color Matrix, Cozy Engine или Scene Manager. Если они доступны — патчи `color.palette`, `color.describe`, `cozy.plan_room` вызывают их; если нет — возвращают fallback с явным `source: "fallback_hardcoded"`.

---

## 2. Установка

```bash
# минимально
pip install -e .

# с тестами
pip install -e ".[test]"

# с GLM-обратной связью
pip install -e ".[glm]"
```

Проверка:

```bash
python -m uroboros patches
pytest -q
```

---

## 3. Архитектура

```
         ┌──────────────────────────────────────────┐
         │                Uroboros                  │
         │                                          │
         │  plan ──▶ run() ──▶ iterations[] ──▶  ★  │
         │            │                              │
         │            ├─▶ PatchRegistry.apply()      │
         │            │       │                      │
         │            │       └─▶ patches/*.py       │
         │            │                              │
         │            ├─▶ FileMemory.cache_get()     │
         │            ├─▶ FileMemory.cache_put()     │
         │            ├─▶ FileMemory.event()         │
         │            └─▶ approval(result)           │
         │                                          │
         └──────────────────────────────────────────┘
                          │
                          ▼
                  .uroboros/
                  ├── blobs/           (sha256)
                  ├── cache/           (по ключу)
                  ├── runs/            (история)
                  ├── pipeline_cache/  (по отпечатку плана)
                  └── memory.jsonl     (append-only)
```

Компоненты:

| Слой | Файл | Что делает |
|---|---|---|
| Формат | `formats.py` | `FORMAT`, `canonical`, `digest`, `PatchError` |
| Память | `memory.py` | blobs, cache, runs, journal |
| Реестр | `registry.py` | загрузка `patches/*.py`, `apply()` |
| Движок | `engine.py` | DAG-исполнение, кеш, approval-gate |
| Планы | `plan.py` | генераторы/сериализация планов |
| Адаптеры | `adapters.py` | мосты в Color Matrix / Cozy Engine |
| GLM | `glm.py` | OpenAI-совместимый клиент для feedback |
| CLI | `cli.py` | `example / patches / run / inspect / cache-stats / clean` |

---

## 4. Быстрый старт

```bash
# 1. Сгенерировать пример
python -m uroboros example --kind validation --out plan.json

# 2. Посмотреть, какие патчи есть
python -m uroboros patches
#   color.describe             script sha256: ...
#   color.palette              script sha256: ...
#   cozy.plan_room             script sha256: ...
#   geometry.generate          script sha256: ...
#   scene.compose              script sha256: ...
#   validate.scene             script sha256: ...

# 3. Запустить с автоодобрением (CI)
python -m uroboros run --plan plan.json --auto-approve
# {
#   "run": "9f0d...",
#   "status": "approved",
#   "iterations": 1,
#   "approved": true,
#   "pipeline_cache_key": "b4..."
# }

# 4. Посмотреть сохранённый run
python -m uroboros inspect --run 9f0d...

# 5. Статистика
python -m uroboros cache-stats
```

---

## 5. Концепции

### 5.1 План

**План** — JSON с полями `format`, `name`, `nodes`. Каждый узел описывает один шаг.

```json
{
  "format": "uroboros.patch/2",
  "name": "simple_room",
  "nodes": [
    {"id": "geometry", "target": "scene", "operation": "geometry.generate",
     "params": {"width": 5.0, "depth": 4.0}},
    {"id": "palette", "target": "color", "operation": "color.palette",
     "params": {"mood": "quiet_warm", "scheme": "analogous", "size": 5}},
    {"id": "compose", "target": "scene", "operation": "scene.compose",
     "needs": ["geometry", "palette"], "params": {"lighting": "soft_indirect"}}
  ]
}
```

Поля узла:

| Поле | Обязательно | Описание |
|---|---|---|
| `id` | да | Уникальный идентификатор узла |
| `target` | да | Логическая цель (`scene`, `color`, ...) — для отпечатка кеша |
| `operation` | да | Имя патча; должно быть в `PatchRegistry.ops` |
| `params` | нет | Параметры патча (dict) |
| `needs` | нет | Список `id`-зависимостей |

**Правила:**
- `id` уникальны в плане.
- `needs` ссылаются только на существующие `id`.
- DAG не должен содержать циклов (проверяется на исполнении, `PatchError`).

### 5.2 Патч

**Патч** — конкретный вызов одного узла с параметрами. Создаётся движком `make_patch()`:

```python
{
  "format": "uroboros.patch/2",
  "id": "<uuid4>",
  "parent": null,
  "run": "<run_id>",
  "iteration": 0,
  "target": "scene",
  "operation": "geometry.generate",
  "inputs": {"<dep_id>": <output_dep_id>, ...},
  "params": {"width": 5.0, "depth": 4.0},
  "outputs": {},                # заполняется после исполнения
  "status": "proposed",         # → "executed" | "cache_hit" | ...
  "approval": "pending",
  "metrics": {},                # {"cache_hit": bool, "elapsed_ms": float}
  "memory": {}                  # {"cache_key": "..."}
}
```

### 5.3 Итерация

**Итерация** — один полный проход всех узлов плана. Результат итерации:

```python
{
  "iteration": 0,
  "result": {
    "outputs": {"geometry": {...}, "palette": {...}, "compose": {...}},
    "patches": [<patch>, <patch>, <patch>]
  },
  "checklist": {
    "iteration": 0,
    "all_operations_succeeded": true,
    "cache_hits": 0,
    "execution_count": 3,
    "patch_ids": ["...", "...", "..."],
    "approval_required": true,
    "notes": [...]
  }
}
```

Все итерации копятся в `state["iterations"]`. После каждой:

1. вызывается `approval(result)`;
2. если `True` — статус `approved`, цикл завершается;
3. если `False` — вызывается `feedback(result, iteration)`; если feedback вернул изменения, `params` узлов обновляются, начинается следующая итерация.

### 5.4 Одобрение

Одобрение — **жёсткий гейт**. Поведение зависит от аргументов:

| `approval` передан | `require_approval` | Поведение |
|---|---|---|
| да | любой | вызывается `approval(result)`; цикл идёт пока `False`, при `True` — стоп |
| нет | `True` | результата `approved=False`, статус `awaiting_approval` |
| нет | `False` | всё одобряется автоматически (для CI) |

**Пример интерактивного одобрения:**

```python
def approve(result):
    summary = {
        node: list(out.keys()) if isinstance(out, dict) else type(out).__name__
        for node, out in result["outputs"].items()
    }
    print(summary)
    answer = input("approve? [y/N] ").strip().lower()
    return answer == "y"

state = u.run(plan, approval=approve)
```

**Пример программного одобрения с условием:**

```python
def approve(result):
    # одобряем, только если валидация прошла
    validate = result["outputs"].get("validate") or {}
    return bool(validate.get("ok"))

state = u.run(plan, approval=approve, max_iterations=3)
```

### 5.5 Обратная связь

**Feedback** — это callable `feedback(result, iteration) -> dict | None`. Возвращает либо `None` (движок останавливается в `awaiting_approval`), либо валидный объект `feedback.apply`:

```python
{
  "format": "uroboros.patch/2",
  "operation": "feedback.apply",
  "params": {
    "changes": {
      "palette": {"params": {"mood": "energetic"}},
      "geometry": {"width": 6.0}
    },
    "reason": "слишком бледно"
  }
}
```

Движок применит `changes` к `params` соответствующих узлов. Ключи вне плана вызовут `PatchError`.

**Пример ручного feedback:**

```python
def feedback(result, iteration):
    if iteration == 0:
        return u.make_feedback(
            {"palette": {"params": {"mood": "calm"}}},
            reason="первый вариант слишком тёплый",
        )
    return None
```

**Пример с GLM:** см. [`glm.py`](#67-модуль-glm) — `make_glm_proposer()` возвращает готовый callable, совместимый с `feedback`.

---

## 6. API Reference

### 6.1 `Uroboros`

```python
from uroboros import Uroboros

u = Uroboros(
    root=".uroboros",            # каталог данных
    patches="patches",           # каталог скриптов
    glm_propose=None,            # callable(result, iteration) -> proposal
    workers=4,                   # параллелизм внутри слоя DAG
)
```

#### `run(plan, *, max_iterations=4, require_approval=True, approval=None, feedback=None)`

Выполнить план. Возвращает `state`:

```python
{
  "format": "uroboros.patch/2",
  "run": "<run_id>",
  "name": "simple_room",
  "status": "approved" | "awaiting_approval" | "failed",
  "approved": bool,
  "iterations": [...],
  "final": {"outputs": {...}, "patches": [...]} | None,
  "mental_checklist": [...],
  "pipeline_cache_key": "<sha256>",
  "error": "..."  # только при failed
}
```

**Исключения:**
- `PatchError` — битый формат, дубликат `id`, неизвестная зависимость, цикл, неизвестная `operation`.

#### `make_patch(target, operation, inputs=None, params=None, **meta)`

Создать объект патча вручную (для собственных циклов).

#### `make_feedback(changes, *, run=None, iteration=0, parent=None, reason="")`

Создать объект `feedback.apply`. Эквивалентно тому, что должен вернуть `feedback`-callable.

**Пример: цикл с логами**

```python
from uroboros import Uroboros, simple_room_plan

u = Uroboros(root="/tmp/urob", patches="patches")
plan = simple_room_plan(width=4.0, depth=3.0, mood="calm")

state = u.run(
    plan,
    max_iterations=3,
    approval=lambda result: result["outputs"]["validate"]["ok"],
    feedback=lambda result, it: u.make_feedback(
        {"palette": {"params": {"mood": "calm" if it == 0 else "quiet_warm"}}},
        reason=f"iteration {it}",
    ),
)
print(state["status"], len(state["iterations"]))
```

### 6.2 `FileMemory`

```python
from uroboros import FileMemory
m = FileMemory("/tmp/urob")
```

| Метод | Возвращает | Описание |
|---|---|---|
| `put_blob(data: bytes)` | `{"hash", "path", "size"}` | content-addressed, sha256 |
| `get_blob(ref: dict)` | `bytes` | проверяет хеш перед возвратом |
| `event(ev: dict)` | — | append-only в `memory.jsonl`, потокобезопасно |
| `cache_get(key: str)` | `dict \| None` | проверяет blob-ссылки перед возвратом |
| `cache_put(key: str, record: dict)` | — | атомарная запись |
| `save_run(run_id, record)` | — | атомарная запись |
| `load_run(run_id)` | `dict \| None` | |
| `save_pipeline_trace(key, run_id, record)` | — | не перезаписывает прошлые run'ы |
| `load_pipeline_trace(key)` | `list[dict]` | |
| `stats()` | `dict` | сводка по `blobs / cache / runs / journal` |

**Пример:**

```python
m = FileMemory("/tmp/urob")
ref = m.put_blob(b"payload")
assert m.get_blob(ref) == b"payload"

m.cache_put("k1", {"outputs": {"x": 1}, "blob_refs": [], "operation": "op"})
assert m.cache_get("k1")["outputs"]["x"] == 1

print(m.stats())
# {'root': '/tmp/urob', 'blobs': 1, 'blob_size_bytes': 7,
#  'cache_entries': 1, 'runs': 0, 'journal_lines': 0}
```

### 6.3 `PatchRegistry`

```python
from uroboros import PatchRegistry
r = PatchRegistry("patches")
```

| Метод / атрибут | Описание |
|---|---|
| `.ops` | `dict[str, Callable]` — операция → функция |
| `.versions` | `dict[str, str]` — операция → sha256 скрипта |
| `.reload()` | перечитать папку (полезно после правки скрипта) |
| `.apply(name, context, params)` | вызвать патч; бросает `PatchError` если нет операции |

**Требования к файлу в `patches/`:**
- имя файла не начинается с `_`;
- атрибут `OP` (str, опционально — по умолчанию имя файла);
- функция `apply(context, params) -> dict`.

### 6.4 Модуль `formats`

```python
from uroboros.formats import FORMAT, canonical, digest, PatchError

FORMAT                 # "uroboros.patch/2"
canonical({"b": 2, "a": 1})   # b'{"a":1,"b":2}'
digest({"a": 1})              # sha256-строка
digest(b"hello")
```

`canonical()` использует `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`. Гарантия: одинаковый dict → одинаковые байты → одинаковый `digest`.

### 6.5 Модуль `plan`

```python
from uroboros.plan import simple_room_plan, full_plan, load_plan, save_plan

simple_room_plan(width=5.0, depth=4.0, mood="quiet_warm")
# → dict с узлами geometry / palette / compose

full_plan(width=5.0, depth=4.0, mood="quiet_warm",
         with_validation=True, with_cozy=False)
# → добавляет validate.scene и (опц.) cozy.plan_room

load_plan("plan.json")        # читает JSON
save_plan(plan, "out.json")   # пишет JSON
```

### 6.6 Модуль `adapters`

Мосты в подсистемы. Каждый «пробует импортировать» и кеширует результат.

| Функция | Что делает |
|---|---|
| `color_matrix_available() -> bool` | импортируется ли `color_matrix_python` |
| `cozy_engine_available() -> bool` | импортируется ли `cozy_engine` |
| `get_color_toolbox()` | `ColorToolbox` или `None` (нужен `UROBOROS_COLOR_MATRIX_NPZ`) |
| `get_cozy_toolbox()` | `CozyToolbox` или `None` (нужен `UROBOROS_COZY_MATRIX_NPZ`) |
| `build_palette_via_matrix(mood, scheme, size)` | `{ok, base, palette, profiles, checks}` |
| `describe_color_via_matrix(color)` | `{ok, ...describe_color}` |
| `plan_room_via_cozy(room, count)` | `{ok, ...cozy_scene_plan}` |

Поиск пакета идёт по:
1. `UROBOROS_COLOR_MATRIX_PATH` / `UROBOROS_COZY_PATH`;
2. `<project_root>/color_matrix_python/` и `<project_root>/Color matrix/`;
3. `<project_root>/cozy_engine/` и `<project_root>/Cozy Engine/`.

**Пример:**

```python
from uroboros.adapters import build_palette_via_matrix
res = build_palette_via_matrix("quiet_warm", "analogous", 5)
if res["ok"]:
    print("matrix:", res["palette"])
else:
    print("fallback:", res["error"])
```

### 6.7 Модуль `glm`

```python
from uroboros.glm import make_glm_proposer

propose = make_glm_proposer()  # вернёт None, если нет GLM_API_KEY
u = Uroboros(glm_propose=propose)
state = u.run(plan, require_approval=False, max_iterations=4)
```

Использует OpenAI-совместимый API по умолчанию: `base_url="https://open.bigmodel.cn/api/paas/v4/"`, `model="glm-4-flash"`. Промпт жёсткий: только JSON, только `feedback.apply`, только существующие `node_id`. Невалидный ответ → `None` (движок остановится).

**Пример с кастомной моделью:**

```python
import os
os.environ["GLM_API_KEY"] = "..."
propose = make_glm_proposer(model="glm-4-plus", max_retries=3)
```

---

## 7. Как писать патчи

### 7.1 Минимальный патч

`patches/hello.py`:

```python
OP = "hello.world"

def apply(context, params):
    return {"message": f"hello, {params.get('name', 'world')}"}
```

Зарегистрируется автоматически. Проверить:

```bash
python -m uroboros patches
#   hello.world               script sha256: ...
```

### 7.2 Что приходит в `context`

```python
{
  "run": "<run_id>",
  "iteration": 0,
  "upstream": {<node_id>: <output_dep_id>, ...},  # результаты всех needs
  "inputs":   {<node_id>: <output_dep_id>, ...},  # то же, что upstream (дублирование для совместимости)
  "patch":    {...},                              # весь объект патча
}
```

### 7.3 Что можно вернуть

Только `dict`. Правила:

- ключи `str`;
- значения — JSON-сериализуемые;
- `bytes` автоматически сохраняются как content-addressed blob: в выходе будет `{"$blob": {"hash", "path", "size"}}`.

```python
def apply(context, params):
    return {"image": b"\x89PNG..."}   # автоматически превратится в blob-ref
```

### 7.4 Патч с ошибкой

Не бросайте исключения «молча». Два способа:

**Способ 1 — вернуть `ok: False`:**

```python
def apply(context, params):
    if not params.get("width"):
        return {"ok": False, "error": "width is required"}
    return {"ok": True, "asset": {...}}
```

**Способ 2 — бросить `PatchError`** (движок сохранит `state["error"]` и re-raise):

```python
from uroboros.formats import PatchError

def apply(context, params):
    if params.get("width", 0) <= 0:
        raise PatchError(f"invalid width: {params.get('width')!r}")
    return {"asset": {...}}
```

### 7.5 Патч с зависимостями

`patches/compose.py`:

```python
def apply(context, params):
    upstream = context["upstream"]
    geometry = upstream["geometry"]["asset"]
    palette  = upstream["palette"]["palette"]
    return {"scene": {"geometry": geometry, "palette": palette}}
```

Параметр `needs` в узле плана:

```json
{"id": "compose", "needs": ["geometry", "palette"], "operation": "scene.compose"}
```

---

## 8. Командная строка

Общие флаги (`uroboros --root X --patches Y cmd ...`):

| Флаг | По умолчанию | Описание |
|---|---|---|
| `--root` | `.uroboros` | каталог данных |
| `--patches` | `patches` | каталог скриптов |

### `uroboros example`

```bash
python -m uroboros example --kind {simple,validation,cozy} [--out FILE]
```

### `uroboros patches`

Печатает список установленных операций с sha256 первых 12 символов.

### `uroboros run`

```bash
python -m uroboros run --plan plan.json \
    [--auto-approve] [--yes] \
    [--max-iterations 4] [--workers 4] \
    [--glm-feedback]
```

- `--auto-approve` — принудительно `approval=True` (CI).
- `--yes` — не спрашивать интерактивно.
- `--glm-feedback` — включить `make_glm_proposer()` (нужен `GLM_API_KEY`).

Код возврата: `0` если `status == "approved"`, иначе `1`.

### `uroboros inspect`

```bash
python -m uroboros inspect --run <run_id>
```

Печатает сохранённый `state` в JSON.

### `uroboros cache-stats`

```bash
python -m uroboros cache-stats
```

### `uroboros clean`

```bash
python -m uroboros clean --yes
```

Удаляет `--root` целиком. Без `--yes` отказывается.

---

## 9. Интеграция с Color Matrix и Cozy Engine

Uroboros самодостаточен, но умеет использовать подсистемы. Включение — переменные окружения:

```bash
export UROBOROS_COLOR_MATRIX_PATH=/path/to/parent/of/color_matrix_python
export UROBOROS_COLOR_MATRIX_NPZ=/path/to/color_matrix.npz

export UROBOROS_COZY_PATH=/path/to/parent/of/cozy_engine
export UROBOROS_COZY_MATRIX_NPZ=/path/to/cozy_matrix.npz

export GLM_API_KEY=...   # для --glm-feedback
```

После этого:

- `patches/palette.py` → `source: "color_matrix"` (вместо `fallback_hardcoded`);
- `patches/color_matrix.py` → полный профиль цвета;
- `patches/cozy_scene.py` → реальный план комнаты.

Если подсистема недоступна — патч **не падает**, а возвращает явный статус:

```json
{
  "palette": ["#e6d7c3", ...],
  "source": "fallback_hardcoded",
  "reason": "Color Matrix not available (set UROBOROS_COLOR_MATRIX_NPZ)"
}
```

Это видно в `outputs`, что важно: не выдавайте fallback за результат матрицы.

**Проверка доступности:**

```python
from uroboros.adapters import color_matrix_available, cozy_engine_available
print(color_matrix_available(), cozy_engine_available())
```

---

## 10. Хранилище данных

`.uroboros/` — обычная папка, её можно удалить (`uroboros clean`) или заархивировать.

| Путь | Формат | Назначение |
|---|---|---|
| `blobs/<xx>/<sha256>` | bytes | content-addressed; используется для `bytes`-выходов |
| `cache/<xx>/<key>.json` | JSON | по ключу `(target, op, script_sha, params, input_hash)` |
| `runs/<run_id>.json` | JSON | полный `state` одного запуска |
| `pipeline_cache/<xx>/<key>/<run_id>.json` | JSON | все запуски по отпечатку плана; не перезаписывается |
| `memory.jsonl` | JSONL | append-only: `patch`, `feedback`, `approval`, `run_finished`, `run_failed` |

**Пример журнала `memory.jsonl`:**

```jsonl
{"type":"patch","run":"9f0d...","iteration":0,"patch":{...}}
{"type":"patch","run":"9f0d...","iteration":0,"patch":{...}}
{"type":"approval","run":"9f0d...","iteration":0,"approved":true}
{"type":"run_finished","run":"9f0d...","status":"approved","iterations":1}
```

---

## 11. Примеры

### 11.1 Простой план (validate + approve)

`examples/plan_with_validation.json`:

```json
{
  "format": "uroboros.patch/2",
  "name": "full_room",
  "nodes": [
    {"id": "geometry", "target": "scene", "operation": "geometry.generate",
     "params": {"width": 5.0, "depth": 4.0, "height": 2.7}},
    {"id": "palette", "target": "color", "operation": "color.palette",
     "params": {"mood": "quiet_warm", "scheme": "analogous", "size": 5}},
    {"id": "compose", "target": "scene", "operation": "scene.compose",
     "needs": ["geometry", "palette"], "params": {"lighting": "soft_indirect"}},
    {"id": "validate", "target": "scene", "operation": "validate.scene",
     "needs": ["compose"], "params": {}}
  ]
}
```

Запуск с условием «одобрять только если валидация зелёная»:

```python
import json
from uroboros import Uroboros, load_plan

u = Uroboros(patches="patches", workers=4)
plan = load_plan("examples/plan_with_validation.json")

state = u.run(
    plan,
    max_iterations=3,
    approval=lambda r: r["outputs"]["validate"]["ok"],
)
print("final:", state["final"]["outputs"]["validate"]["scene_summary"])
```

### 11.2 Свой патч `palette_from_image`

`patches/palette_from_image.py`:

```python
"""Извлечь палитру из байтов изображения (демо: без зависимостей).

В реальном проекте здесь был бы PIL/numpy — для примера считаем, что
в params.image_base64 уже лежит RGB-строка, и возвращаем её как есть.
"""
import base64
import json

OP = "palette.from_image"


def apply(context, params):
    raw = params.get("image_base64", "")
    if not raw:
        return {"ok": False, "error": "image_base64 is empty"}
    try:
        data = base64.b64decode(raw)
    except Exception as exc:
        return {"ok": False, "error": f"base64: {exc}"}
    # здесь бы был реальный анализ; для демо — заглушка
    return {
        "ok": True,
        "palette": ["#000000", "#ffffff"],
        "image_bytes": len(data),   # это число, не bytes — не станет blob'ом
    }
```

Использование в плане:

```json
{"id": "pal", "target": "color", "operation": "palette.from_image",
 "params": {"image_base64": "..."}}
```

### 11.3 Программный запуск с кастомным approval и логами

```python
from uroboros import Uroboros, full_plan

def approve(result):
    check = result["outputs"].get("validate", {})
    print(f"validate.ok={check.get('ok')}  problems={check.get('problems')}")
    return bool(check.get("ok"))

u = Uroboros(root="./.uroboros", patches="./patches", workers=2)
plan = full_plan(with_validation=True, mood="quiet_warm")

state = u.run(plan, max_iterations=3, approval=approve)
print(json.dumps({
    "status": state["status"],
    "iterations": len(state["iterations"]),
    "final_summary": state["final"]["outputs"]["validate"]["scene_summary"] if state["final"] else None,
}, indent=2))
```

### 11.4 Feedback через GLM

```python
import os
from uroboros import Uroboros, full_plan
from uroboros.glm import make_glm_proposer

os.environ["GLM_API_KEY"] = "..."

propose = make_glm_proposer(model="glm-4-flash")
u = Uroboros(patches="patches", glm_propose=propose, workers=2)

state = u.run(
    full_plan(with_validation=True),
    max_iterations=3,
    approval=lambda r: r["outputs"]["validate"]["ok"],
)
```

### 11.5 Пакетный обход конфигураций

```python
from uroboros import Uroboros, simple_room_plan

u = Uroboros(patches="patches", workers=4)
for width, depth in [(3, 2), (4, 3), (6, 5)]:
    plan = simple_room_plan(width=width, depth=depth)
    s = u.run(plan, max_iterations=1, require_approval=False)
    scene = s["final"]["outputs"]["compose"]["scene"]
    print(f"{width}x{depth}: geom={scene['geometry']['kind']}, "
          f"palette={len(scene['palette'])}, mood={scene['mood']}")
```

---

## 12. Диагностика и типичные ошибки

| Симптом | Причина | Что делать |
|---|---|---|
| `PatchError: Unknown patch operation: 'x.y'` | патч не найден | `python -m uroboros patches`; проверьте `OP` и имя файла |
| `PatchError: Duplicate node id` | одинаковые `id` в плане | уберите дубликаты |
| `PatchError: Unknown dependency 'z' in 'a'` | `needs: ["z"]`, узла `z` нет | исправьте `needs` |
| `PatchError: Pipeline contains a dependency cycle` | циклические `needs` | разорвите цикл |
| `PatchError: x must return dict, got list` | патч вернул не dict | поправьте `apply()` |
| `status=awaiting_approval` | нет `approval` и `require_approval=True` | передайте `approval` или `require_approval=False` |
| `status=failed` + `error` | патч бросил исключение | см. `state["error"]` в `inspect --run` |
| `pytest` не видит пакеты | не установлен | `pip install -e ".[test]"` |

**Полезный трюк — пересмотреть последний неудачный run:**

```bash
python -m uroboros inspect --run $(ls -t .uroboros/runs | head -1 | sed 's/.json$//')
```

**Сбросить кеш для конкретного патча:** удалить `cache/` целиком или конкретный файл по ключу (последний виден в `patch.memory.cache_key`).

---

## 13. Безопасность

- **Патчи — это произвольный Python.** `PatchRegistry` использует `exec_module`; запускайте только из доверенной папки. Не кладите туда ничего из ненадёжных источников.
- **`memory.jsonl` — append-only.** Ротацию делайте вручную, если файл слишком большой.
- **Blobs проверяются по sha256 при чтении.** Это не защищает от подмены злоумышленником с доступом к файловой системе, но ловит случайную порчу.
- **`pipeline_cache/` не перезаписывается.** Каждый запуск с тем же `pipeline_key` добавляет новый файл.
- **GLM**: ключ читается из `GLM_API_KEY`; в коде не храните. Промпт жёсткий — только JSON `feedback.apply`.
- **Одобрение молча не подставляется.** Без `approval` и без `require_approval=False` запуск останется `awaiting_approval`.

---

## 14. FAQ

**Можно ли добавить патч без перезапуска процесса?**
Да: `u.patches.reload()`. Файлы перечитываются, `versions` обновляются, кеш от этого не инвалидируется (ключ содержит sha, так что старые записи не будут использованы).

**Как сделать патч, который пишет большие файлы?**
Верните `bytes` — движок сохранит их как blob и в `outputs` будет `{"$blob": {"hash", "path", "size"}}`. Прочитать: `u.memory.get_blob(ref)`.

**Как посмотреть, что лежит в blob'е?**
`ref["path"]` относительный от `.uroboros/`; откройте `u.memory.root / ref["path"]`.

**Чем `pipeline_cache` отличается от `runs`?**
`runs/<run_id>` — один запуск. `pipeline_cache/<pipeline_key>/<run_id>` — все запуски с тем же отпечатком `(plan, patch_versions)`; полезно, чтобы отслеживать эволюцию одного пайплайна.

**Можно ли параллелить итерации?**
Нет, итерации последовательны (approval/feedback между ними). Параллелятся только независимые узлы внутри одной итерации (`--workers`).

**Как остановить пайплайн досрочно?**
`approval` вернул `True` — стоп с `approved`. `feedback` вернул `None` — стоп с `awaiting_approval`.

**Что если `feedback` вернул `changes` для несуществующего узла?**
`PatchError: Feedback references unknown node: ...`. Run сохраняется со `status="failed"`.

**Что если патч возвращает не-JSON-сериализуемое?**
`cache_put` упадёт при попытке сохранить. Держите `outputs` простыми: числа, строки, списки, dict, `bytes`.

**Можно ли отключить кеш?**
Сейчас нет явного флага. Обходной путь: удалять `cache/` перед запуском. При необходимости — `memory.cache_get`/`cache_put` можно переопределить в подклассе.

**Поддерживается ли Python 3.9?**
Нет, требуется ≥ 3.10 (используются `X | Y` в аннотациях и `match`-подобные выражения в `plan`/`cli`).

---

## Лицензия

MIT (см. `pyproject.toml`).