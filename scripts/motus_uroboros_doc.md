% Motus & Uroboros — Техническая документация
% Z.ai
% 2026-11-14

\newpage

# 1. Uroboros

Uroboros — patch-driven, file-backed итеративный pipeline с human approval. Пакет `uroboros` v0.3.0 предоставляет механизм: plan → patches → state mutations → memory → approval.

## 1.1 Архитектура

Uroboros работает по модели: план (JSON) → DAG узлов → исполнение патчей → кэширование → approval gate → memory journal. Каждый узел плана — операция с `target`, `operation`, `params`, `needs` (зависимости).

```json
{
  "format": "uroboros.patch/2",
  "name": "demo",
  "nodes": [
    {"id": "geometry", "target": "scene", "operation": "geometry.generate",
     "params": {"width": 5.0, "depth": 4.0}},
    {"id": "palette", "target": "color", "operation": "color.palette",
     "params": {"mood": "quiet_warm"}},
    {"id": "compose", "target": "scene", "operation": "scene.compose",
     "needs": ["geometry", "palette"]}
  ]
}
```

## 1.2 Ключевые модули

| Модуль | Ответственность |
|--------|----------------|
| `engine.py` | `Uroboros` class: `run()`, `_execute_one()`, `_checklist()`, approval logic |
| `registry.py` | `PatchRegistry`: загрузка `.py` патчей из директории, `apply()` |
| `memory.py` | `FileMemory`: blob storage, `cache_put`/`get`, `save_run`, event journal |
| `formats.py` | `FORMAT`, `PatchError`, `canonical`, `digest` — сериализация |
| `plan.py` | `simple_room_plan`, `full_plan`, `load_plan`, `save_plan` |
| `adapters.py` | Мосты к Color Matrix, Cozy Engine, motus |
| `cyclic.py` | `CyclicPipeline`: iterative solver с convergence detection |
| `feedback.py` | `ConvergenceChecker` + `FeedbackProposer` |
| `intro_cache.py` | `IntroCache`: итерации, metrics, deltas, blobs |
| `gpu_eval.py` | `GPUEvaluator`: demo_runtime.exe → BMP → CV analysis |
| `smt_patch.py` | `inject_params`: `.smt` param injection |

## 1.3 Approval gate (P0 fix)

После внешнего ревью (2026-11-12) добавлен validation gate: `_checklist()` сканирует outputs патчей на `{"ok": false}`. `require_approval=False` больше не активируется при провале валидации.

Три независимых состояния:

| Состояние | Значения |
|-----------|----------|
| `execution_status` | `succeeded` \| `failed` |
| `validation_status` | `passed` \| `failed` \| `not_checked` |
| `approval_status` | `pending` \| `approved` \| `rejected` |

## 1.4 Strict mode (P1.4)

`Uroboros(strict=True)` — патчи с output `{"_fallback": True}` вызывают `PatchError`. Demo mode (default) — fallback принимается. Запрещает маскирование неработающих интеграций fallback-поведением.

## 1.5 Data dependencies в кэше (P1.5)

`params.data_dependencies: list[str]` — пути к внешним файлам. `mtime_ns + size` включаются в cache key. Замена `.npz` матрицы вызывает cache miss → пересчёт.

\newpage

# 2. Motus

Motus v0.1.0 — детерминированный motion-core, управляемый текстовым запросом. `submit(text)` → events with absolute time → `frame(t)` replays from scratch. Ядро — только stdlib. numpy — опционально для частиц. Рендер вне пакета: `FramePlan` — данные.

## 2.1 Инварианты (I1–I10)

| # | Инвариант | Формулировка |
|---|-----------|-------------|
| I1 | Determinism | `frame(t)` дважды даёт идентичный план |
| I2 | Purity | процедурный шум зависит только от `(t, seed)` |
| I3 | Framerate | значения при 60 и 240 fps совпадают |
| I4 | Boundaries | `t` вне диапазона, NaN, ±inf, пустой трек — clamp |
| I5 | Identity | scale `(1,1,1)`, rot `(0,0,0,1)`, pos `(0,0,0)` |
| I6 | Blend | `weight=0` — базовая поза; фазы REPLACE→ADD→MUL |
| I7 | Hierarchy | preorder O(N) совпадает с перемножением родителей |
| I8 | Replay | перемотка назад переигрывает события |
| I9 | Offline | offline-сетка и realtime дают один результат |
| I10 | Quat | slerp по кратчайшей дуге, результат нормализован |

## 2.2 Модули

| Файл | Ответственность |
|------|----------------|
| `core.py` | `MotusError`, `QueryError`, `Registry` |
| `mathx.py` | vec3/quat/mat4, slerp, `hash01` (column-major) |
| `clock.py` | `Transport` (bpm/beats_per_bar), `fixed_frames`, `LiveClock` |
| `track.py` | `Track` (keyframes), `EASINGS`, safe sampling |
| `scene.py` | `Scene`, `Entity`, `Transform`, preorder, dirty flags |
| `anim.py` | `Animator`, `Binding`, `CHANNELS`, `PROCS`, `Mode` |
| `effects.py` | `EffectSpec`, `Emitter`, `compute_field` (closed-form) |
| `query.py` | Lexer, DSL, free language, mode router |
| `runtime.py` | `Runtime`: `submit()`, `frame()` → `FramePlan` |
| `bake.py` | `Playback` (mmap), `bake()` |
| `glsl.py` | Опциональные шейдеры 330 core |

## 2.3 DSL синтаксис

```
new ball pos=(0,0,0) param.color=(1.0,0.6,0.2)
anim ball.position from=(0,0,0) to=(3,0,0) over=2 ease=smooth
proc ball.rotation spin rate=180
fx burst on=ball at=2 for=1.5 count=600 seed=7
```

## 2.4 Free language

Rules-based, не NLU. Сегментация по найденным глаголам. RU+EN. Case-insensitive fuzzy matching (LCP≥4, ≥60%). Неизвестная фраза → `QueryError` с подсказками. Атомарность: любой issue → весь запрос отклонён.

## 2.5 Исправленные баги (5)

| # | Баг | Исправление |
|---|-----|-------------|
| 1 | `field` name collision (dataclass vs effects) | Rename `field()` → `compute_field()` |
| 2 | `_static` class-level (shared state) | Move to `__init__` as `self._static` |
| 3 | No `pyproject.toml` | Created with setuptools + packages.find |
| 4 | Uppercase Cyrillic stripped by regex | `[а-я]` → `[а-яА-Яa-zA-Z]`, case-insensitive `_fuzzy` |
| 5 | Test expects entity before `frame()` | Added `rt.frame(0.0)` before assertion |

\newpage

# 3. Интеграция Uroboros + Motus

## 3.1 Adapter pattern

motus не вторгается в Uroboros core. Добавляется как операция `motus.scene` через `patches/motus_scene.py`. Adapter в `uroboros/adapters.py`: `motus_available()`, `motus_scene(query, times)` → JSON frames. Optional dependency: fallback если motus не установлен.

## 3.2 Контракт motus.scene

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `query` | str | (обязательный) | Текст motus DSL/free |
| `times` | list[float] | `[0.0]` | Моменты кадров |
| `particles` | bool | `false` | Считать ли частицы (нужен numpy) |
| `bpm` | float | `120.0` | Музыкальная сетка |
| `mode` | str | `auto` | `dsl` \| `free` \| `auto` |
| `include_upstream` | bool | `true` | Добавить `upstream_keys` |

## 3.3 Pipeline

```
Uroboros plan
  geometry.generate → room dims
  color.palette → mood colors (Color Matrix)
  scene.compose → scene graph
  cozy.plan_room → room primitives
  motus.scene → JSON frame snapshots
  validate.scene → check
```

Data flow:

- Color Matrix → `color.palette` → palette colors
- Cozy Engine → `cozy.plan_room` → uPrimitives
- Scene Manager → `scene.compose` → scene graph
- motus → `motus.scene` → JSON frames (entities, transforms, particles)

\newpage

# 4. Cyclic Pipeline

Превращение линейного пайплайна в циклический feedback-loop. Iterative solver: forward → evaluate → decide → delta → repeat until convergence.

## 4.1 Phase 1: Python-side loop

`IntroCache` stores iterations (`meta.json` + `frames.bin`). `ConvergenceChecker`: tolerance, max_iterations, oscillation detection, insufficient improvement. `FeedbackProposer`: brightness → uIntensity delta with damping factor 0.5.

```
CyclicPipeline.run(forward_fn, evaluate_fn, initial_params)
  for iteration in 0..max:
    1. FORWARD:   forward_fn(params) → state
    2. EVALUATE:  evaluate_fn(state) → List[SceneMetric]
    3. DECIDE:    ConvergenceChecker → approve | feedback | abort
    4. CACHE:     IntroCache.save_iteration(record)
    5. DELTA:     FeedbackProposer → param deltas → apply
```

## 4.2 Phase 2: GPU-side loop

`GPUEvaluator`: вызывает `demo_runtime.exe --still T` → BMP → PIL CV analysis → `SceneMetric[]`. `smt_patch.inject_params`: `.smt` param injection (find clip/uniform/prog, replace value). `create_gpu_forward_fn`: factory function for `CyclicPipeline`.

## 4.3 intro_cache формат

| Формат | Скорость | Zero-copy | Зависимости |
|--------|----------|-----------|-------------|
| Custom binary + mmap + JSON | Good | mmap | 0 (stdlib) |
| FlatBuffers | OK | read | +200KB |
| Cap'n Proto | Excellent | full | +500KB |
| LMDB | Good | mmap | +100KB lib |

Выбран: **Hybrid** (JSON metadata + content-addressed binary blobs). Причины: demoscene binary budget, уже доказано в motus `bake.py`, reuses Uroboros `FileMemory` blob storage, diff-friendly JSON.

\newpage

# 5. Тесты и верификация

| Suite | Passed | Failed | Skipped |
|-------|--------|--------|---------|
| Uroboros engine | 8 | 0 | 0 |
| Uroboros formats | 3 | 0 | 0 |
| Uroboros memory | 5 | 0 | 0 |
| Uroboros patches | 6 | 0 | 0 |
| Uroboros registry | 3 | 0 | 0 |
| P0/P1 fixes | 8 | 0 | 0 |
| Motus adapter | 10 | 0 | 3 |
| Cyclic pipeline | 22 | 0 | 0 |
| GPU evaluation | 18 | 0 | 0 |
| Motus selfcheck | 15 | 0 | 0 |
| **Итого** | **98** | **0** | **3** |

## 5.1 Инвариантные тесты motus

- I1 Determinism: `frame(t)` дважды — идентичный результат
- I2 Hash purity: `hash01(seed, i)` не зависит от истории вызовов
- I3 Framerate independence: 60fps == 240fps в общих точках
- I4 Boundaries: NaN, ±inf, пустой трек — clamp, не падение
- I8 Replay: scrub назад переигрывает события с нуля

## 5.2 Cyclic pipeline тесты

- Converges in 1 iteration (metrics already at target)
- Converges in 2 iterations (feedback adjusts params)
- Aborts on max_iterations (never converges)
- Forward failure → abort with error
- Oscillation detection (sign flips in deltas)
- Insufficient improvement detection
- Cache records all iterations + final marker
- Params updated between iterations (damping applied)

\newpage

# 6. API Reference

## 6.1 Uroboros

```python
from uroboros import Uroboros, FORMAT, PatchError

u = Uroboros(root=".uroboros", patches="patches", workers=2)
state = u.run(plan, max_iterations=3, require_approval=False)
```

## 6.2 Motus

```python
from motus import Runtime, Transport

rt = Runtime(Transport(bpm=120), mode="dsl", particles=False)
report = rt.submit("new ball\nanim ball.position from=(0,0,0) to=(3,0,0) over=2")
plan = rt.frame(1.0)
```

## 6.3 Adapter

```python
from uroboros.adapters import motus_scene

res = motus_scene("new ball\nanim ball.position from=(0,0,0) to=(1,0,0) over=1",
                   [0.0, 0.5, 1.0], particles=False, mode="dsl")
```

## 6.4 Cyclic Pipeline

```python
from uroboros.cyclic import CyclicPipeline, CyclicConfig
from uroboros.gpu_eval import GPUEvaluator, create_gpu_forward_fn

config = CyclicConfig(max_iterations=5, tolerance=0.005, damping=0.5)
pipe = CyclicPipeline(config)
forward = create_gpu_forward_fn("demo.smt", "/tmp/work")
evaluator = GPUEvaluator(smt_path="demo.smt")
result = pipe.run(forward_fn=forward, evaluate_fn=evaluator.evaluate,
                  initial_params={"s1.uIntensity": 1.5})
```

## 6.5 .smt param injection

```python
from uroboros.smt_patch import extract_params, inject_params

params = extract_params("demo.smt")
# {"s1.uIntensity": 0.8, "s4.uIntensity": 1.2, ...}
inject_params("demo.smt", {"s1.uIntensity": 1.5}, "modified.smt")
```
