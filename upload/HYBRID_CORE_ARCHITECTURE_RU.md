# Uroboros v0.4 — Hybrid Core Architecture

**Статус:** реализованный локальный прототип поверх v0.3  
**Профиль:** Hybrid / Balanced  
**Протоколы:** `uroboros.patch/2`, `uroboros.exchange/1`, `uroboros.hybrid/0.4`  
**Хранилище:** файловое JSON/JSONL + SHA-256 blobs; SQLite не используется.

## 1. Назначение

v0.4 объединяет три равноправных механизма:

1. **Data Exchange** — общий envelope и маршрутизация сообщений между компонентами.
2. **BTB** — обучение сигнатурам запросов и прогнозирование ресурсов. По умолчанию `shadow`: прогнозы измеряются, но не меняют обязательный pipeline.
3. **Cyclic Processing** — ограниченные итерации feedback поверх существующего patch/DAG executor. Повторно вычисляются только операции, чьи cache keys изменились.

GLM остаётся внешним decision maker. Uroboros принимает от него декларативные параметры/feedback, но не исполняет код, сгенерированный моделью.

## 2. Границы ответственности

| Часть | Ответственность |
|---|---|
| GLM-5.2 | Смысл задачи, творческие решения, feedback |
| Sigil | Компактное описание intent, компонентов и ограничений |
| HybridCore | Связывает BTB, Exchange и существующий исполнитель |
| Data Exchange | Envelope, валидация базовой структуры, in-process routing |
| BTB | Сигнатуры, статистика попаданий/промахов, prefetch prediction |
| Patch/DAG engine | Исполнение доверенных Python patches, кеш, snapshots, циклы |
| Cozy / Color / Scene Manager | Специализированные операции, не дублируемые ядром |

Uroboros не вызывается в per-frame render loop. C++ Runtime получает подготовленные артефакты; его телеметрия может импортироваться после профилирования.

## 3. Sigil

Sigil — не язык программирования. Это декларативный intent-блок. Допускаются JSON и компактный `key: value` синтаксис.

```text
@uroboros
intent: generate_scene
use: [cozy, color_matrix, scene_manager]
target: atmospheric_demo
constraints:
  mood: cozy
  lighting: cinematic
execution:
  cache: auto
  cycle: adaptive
```

Поддерживаемые поля верхнего уровня: `intent`, `use`, `target`, `constraints`, `execution`, `cache`, `cycle`, `metadata`. Значения списков/объектов задаются JSON-совместимыми значениями. Парсер отклоняет неизвестные верхнеуровневые поля. Для машинной интеграции предпочтителен JSON.

API:

```python
from uroboros.sigil import parse
intent = parse(sigil_text)
```

## 4. Unified Data Exchange

Envelope `uroboros.exchange/1`:

```json
{
  "protocol": "uroboros.exchange/1",
  "message_id": "uuid",
  "correlation_id": "run-id",
  "message_type": "REQUEST",
  "source": "glm",
  "target": "cozy",
  "operation": "plan_scene",
  "created_at": 1794000000.0,
  "payload": {"room": "living_room"},
  "metadata": {"trace_id": "trace-id"}
}
```

Типы сообщений v0.4: `REQUEST`, `RESPONSE`, `FEEDBACK`, `PREFETCH`, `EVENT`. Router — локальный in-process dispatcher; сетевой RPC и брокер сообщений не входят в v0.4.

```python
from uroboros.exchange import Router, envelope
router = Router()
router.register("cozy", lambda payload, message: {"plan": "..."})
request = envelope("glm", "cozy", "REQUEST", {"room": "living_room"})
response = router.dispatch(request)
```

## 5. BTB

Файл: `.uroboros_memory/btb/btb_stats.json`.

Сигнатура формируется из `intent | use[] | target`. В BTB хранятся ресурсы, счётчики hits/misses, накопленные использования и waste. Ресурсы ограничены top-32 для одной сигнатуры.

Режимы:

- `shadow` — только прогноз и измерение, без автоматического вмешательства;
- `prefetch` — разрешает выдавать уже доступные ресурсы как prefetched, если confidence выше порога.

`prefetch` в этой версии не запускает произвольную загрузку файлов. Он выбирает только совпадения из переданного `available_resources`. Реальное I/O-prefetch должно быть реализовано адаптером ресурса и отдельно профилироваться.

Холодный цикл обучения: первый запрос собирает фактически использованные ресурсы; следующий прогноз проверяется в shadow; после подтверждённых попаданий режим может стать eligible. Недостаточная статистика не должна считаться доказанной точностью.

```python
from uroboros.btb import BTB
btb = BTB(".uroboros_memory/btb", mode="shadow")
prediction = btb.predict("generate_scene|cozy|color_matrix", {"palette": data})
btb.observe("generate_scene|cozy|color_matrix", prediction["resources"], ["palette"])
```

## 6. Cyclic Processing и кеш

Внутри одной итерации используется DAG: циклические рёбра запрещены. Feedback начинает следующую итерацию, а не вызывает рекурсивное выполнение узла.

Каждая операция кешируется по fingerprint операции, версии patch-скрипта, runtime fingerprint, параметрам и upstream данным. При изменении параметров узла меняется ключ этой операции и downstream операций; независимые ветви сохраняют cache hits.

Остановка ограничена `max_iterations`. Пользовательское approval остаётся commit gate. `require_approval=False` предназначен для тестов и автоматизированного CI, а не для интерактивной творческой приёмки.

## 7. Memory

Сохраняются:

- `memory.jsonl` — append-only события;
- `blobs/` — неизменяемые SHA-256 payloads;
- `cache/` — результаты отдельных операций;
- `runs/` — полные snapshots;
- `pipeline_cache/` — история опыта pipeline;
- `btb/btb_stats.json` — статистика сигнатур BTB.

Это execution/design memory и контекст для mental checklist, а не автоматическое изменение весов GLM. Автоматическое обучение модели не входит в scope.

## 8. Метрики

`run()` добавляет агрегат `metrics`:

- `cache_hits`, `cache_misses`, `cache_hit_rate`;
- `processing_time_ms` — сумма измеренных elapsed patch time;
- `wall_time_ms` — время всего run в процессе Uroboros;
- `recalculation_ratio` — доля реально выполненных операций среди выполненных и cache-hit операций;
- `cycle_count` — число итераций;
- `glm_context_size_bytes` — `null`: core не видит реальный токенизатор/provider request.

Hybrid добавляет `btb_hit_rate`, `prefetch_waste`, `signatures`, `predictions`.

`data_read_time_ms` и `transfer_time_ms` оставлены `null`, пока адаптеры не предоставляют достоверные измерения. `prefetch_waste` является накопленным отношением неиспользованных предсказанных ресурсов к предсказанным и использованным ресурсам; это не миллисекунды.

Все метрики записываются в run snapshot и `memory.jsonl`. Не интерпретировать `null` как ноль.

## 9. Быстрый запуск

Python 3.10+, NumPy (для исходных Cozy/Color engines).

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m unittest discover -s engines/color_matrix/tests -q
python examples/run_hybrid.py
```

Встроенный пример использует реальный Cozy/Color pipeline и BTB в shadow mode. Первый запуск прогревает статистику сигнатур. Повторные запуски постепенно позволяют оценивать точность BTB.

## 10. Подключение GLM-5.2

Существующий `integration.glm.make_glm_feedback` сохраняется. Подключайте OpenAI-compatible client с вашим endpoint и ключом через переменные окружения/секреты. Модель возвращает только JSON-изменения параметров известных узлов. Не передавайте модели право писать Python patches или исполнять произвольные команды.

## 11. Обоснование оптимизаций

| Оптимизация | Практический эффект | Контроль риска |
|---|---|---|
| Общий Envelope | Один формат взаимодействия вместо парных форматов | Schema/contract tests |
| Lazy adapters из v0.3 | Не загружать движки до реального вызова | Измерять cold start |
| BTB shadow | Учить предсказания без риска вмешательства | Сравнивать прогноз с фактом |
| Delta-only resource set | Хранить только полезные ресурсы сигнатуры | Лимит top-32 |
| Content-addressed cache | Не повторять идентичные операции | Hash входов и версии |
| DAG + feedback cycles | Нет рекурсивного вызова, независимые узлы параллельны | Ограничение итераций |
| Incremental recalculation | Пересобирать только изменившиеся ветви | Тесты cache hits на независимых узлах |
| Append-only memory | Полная трассируемость и обучение на истории | Ротация/архивация — будущая функция |

## 12. Ограничения v0.4

1. BTB — локальный статистический предсказатель, не аппаратный CPU BTB и не ML-модель.
2. `prefetch` пока работает только с ресурсами, уже предоставленными вызывающей стороной; нет фоновой загрузки и I/O scheduler.
3. Router работает в одном процессе; нет IPC/RPC.
4. `data_read_time_ms`, `transfer_time_ms` и точный `glm_context_size_bytes` не измеряются ядром без адаптеров соответствующих систем.
5. Patch scripts — доверенный локальный код, не sandbox.
6. Реальный GLM endpoint не тестировался в рамках этой сборки.
7. Исходные данные Cozy/Color остаются в исходном NPZ; миграция HDF5 не выполняется.
8. Геометрические ограничения и Scene Manager capabilities остаются такими, как в v0.3.

## 13. Следующие этапы

1. Добавить schema validation для конкретных payload каждого Engine и версионирование адаптеров.
2. Подключить resource loader callbacks к BTB и измерить реальное время prefetch / waste.
3. Прокинуть таймеры чтения/передачи из Cozy, Color, Scene Manager и GLM provider.
4. Провести benchmark cold, warm, BTB shadow, BTB prefetch и incremental change на одинаковых данных.
5. После измерений решить, нужен ли отдельный scheduler или межпроцессный транспорт.

## 14. Критерии приёмки v0.4

- [x] Сохранена совместимость patch format v0.3.
- [x] Есть компактный Sigil parser.
- [x] Есть единый Exchange envelope и Router.
- [x] Есть файловый BTB в shadow/prefetch режимах.
- [x] Есть статистика hit rate и prefetch waste.
- [x] Существующий bounded cycle и cache reuse сохранены.
- [x] Метрики run сохраняются в snapshot.
- [x] Нет SQLite и сетевого брокера.
- [x] Оригинальные тесты Cozy/Color проходят.
- [ ] Реальный GLM endpoint и реальный I/O prefetch проверены на целевой машине.
