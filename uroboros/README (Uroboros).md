# Uroboros

Patch-driven, file-backed iterative pipeline with mandatory human approval.

Каждый шаг — это **patch**: JSON-объект формата `uroboros.patch/2`, который вызывает один Python-скрипт из `patches/` с параметрами. Результаты кешируются по (target, operation, версия скрипта, params, хеш входов). Цикл повторяется до одобрения человеком (или до `max_iterations`).

## Установка

```bash
pip install -e .
# опционально:
pip install -e ".[test]"
pip install -e ".[glm]"   # если нужен GLM-feedback
```

## Быстрый старт

```bash
# 1. Сгенерировать пример плана
python -m uroboros example --out plan.json

# 2. Посмотреть доступные патчи
python -m uroboros patches

# 3. Запустить (без автоприменения, интерактивно)
python -m uroboros run --plan plan.json

# 4. Или сразу с автоматическим одобрением (для CI)
python -m uroboros run --plan plan.json --auto-approve
```

## Команды

| Команда | Что делает |
|---|---|
| `uroboros example --out plan.json` | Сгенерировать пример плана |
| `uroboros patches` | Список установленных патчей |
| `uroboros run --plan plan.json` | Выполнить план |
| `uroboros run --plan plan.json --auto-approve` | Выполнить без интерактивного одобрения |
| `uroboros inspect --run <id>` | Показать сохранённый run |
| `uroboros cache-stats` | Статистика кеша и blob-хранилища |
| `uroboros clean --yes` | Удалить `.uroboros/` |

## Формат плана

```json
{
  "format": "uroboros.patch/2",
  "name": "simple_room",
  "nodes": [
    {"id": "geometry", "target": "scene", "operation": "geometry.generate",
     "params": {"width": 5.0, "depth": 4.0}},
    {"id": "palette", "target": "color", "operation": "color.palette",
     "params": {"mood": "quiet_warm"}},
    {"id": "compose", "target": "scene", "operation": "scene.compose",
     "needs": ["geometry", "palette"], "params": {"lighting": "soft_indirect"}}
  ]
}
```

`needs` задаёт DAG. Независимые узлы одного слоя выполняются параллельно (`--workers`).

## Как писать патч

Файл `patches/my_patch.py`:

```python
OP = "my.operation"

def apply(context, params):
    # context: {"run", "iteration", "upstream": {node_id: output}, "inputs", "patch"}
    return {"result": params.get("x", 0) * 2}
```

Регистрируется автоматически. Возвращаемое значение должно быть `dict`. `bytes` автоматически сохраняются как content-addressed blobs.

## Интеграция с Color Matrix и Cozy Engine

Uroboros не зависит от них, но если пакеты `color_matrix_python` / `cozy_engine` доступны (установлены или найдены по env var), патчи `color.palette` и `cozy.plan_room` используют их. Иначе — fallback на hardcoded.

Переменные окружения:

| Переменная | Что задаёт |
|---|---|
| `UROBOROS_COLOR_MATRIX_PATH` | Родитель папки `color_matrix_python/` |
| `UROBOROS_COLOR_MATRIX_NPZ` | Путь к `.npz` с матрицей (16.7M ячеек) |
| `UROBOROS_COZY_PATH` | Родитель папки `cozy_engine/` |
| `UROBOROS_COZY_MATRIX_NPZ` | Путь к `cozy_matrix.npz` |
| `GLM_API_KEY` | Ключ GLM для `--glm-feedback` |

## Одобрение

Без `--auto-approve` и без `GLM_API_KEY` движок выполнит один проход и остановится в статусе `awaiting_approval`. Это осознанно: **Uroboros никогда не считает сгенерированный результат одобренным молча**.

## Данные

Всё в `.uroboros/`:
- `blobs/` — content-addressed, sha256
- `cache/` — результаты по ключу (target, op, script_version, params, input_hash)
- `runs/` — история запусков
- `pipeline_cache/` — все запуски по отпечатку плана
- `memory.jsonl` — append-only журнал событий