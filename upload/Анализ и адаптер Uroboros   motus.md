
## Conversation

**Собственные правки**

**1. Обязательная правка A: `motus/runtime.py`**

В оригинале `_static` — атрибут класса. Исправление:

```python
# в Runtime.__init__, после self._free_state = {}
        self._static: List[Cmd] = []

# удалить строку уровня класса:
#     _static: List[Cmd] = []

# в frame() заменить выбор origin на:
            em_now = em if origin == em.origin else _with_origin(em, origin)
```

**2. Новый adapter в B: добавить в конец `uroboros/adapters.py`**

```python
# --- Motus adapter ---------------------------------------------------------

_MOTUS_CACHE: dict[str, object] = {}


def motus_available() -> bool:
    """Проверяет, импортируется ли пакет motus. Не падает при отсутствии."""
    if "motus_avail" not in _MOTUS_CACHE:
        try:
            import motus  # noqa: F401
            _MOTUS_CACHE["motus_avail"] = True
        except ImportError:
            _MOTUS_CACHE["motus_avail"] = False
    return bool(_MOTUS_CACHE["motus_avail"])


def _json_safe(value):
    """Приводит tuple/numpy-скаляры к JSON-совместимому виду."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    try:
        import numpy as np  # type: ignore
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    except ImportError:
        pass
    return repr(value)


def motus_scene(query: str, times: list[float], *, particles: bool = False,
                bpm: float = 120.0, mode: str = "auto") -> dict:
    """Выполняет motus-запрос и возвращает JSON-снимки кадров.

    Контракт:
      ok=True  -> {"ok": True, "source": "motus", "mode": ..., "frames": [...]}
      ok=False -> {"ok": False, "source": "fallback", "error": "..."}
    """
    if not motus_available():
        return {
            "ok": False,
            "source": "fallback",
            "error": "motus is not installed; add A to PYTHONPATH or pip install -e A",
        }
    from motus import Runtime, Transport

    rt = Runtime(Transport(bpm=float(bpm)), mode=str(mode), particles=bool(particles))
    report = rt.submit(str(query))
    if not report.ok:
        return {
            "ok": False,
            "source": "motus",
            "error": str(report),
            "issues": [str(i) for i in report.issues],
        }

    frames = []
    for t in times:
        plan = rt.frame(float(t))
        frames.append({
            "time": plan.time,
            "items": [
                {
                    "entity": it.entity,
                    "name": it.name,
                    "world": list(it.world),
                    "params": _json_safe(it.params),
                }
                for it in plan.items
            ],
            "batches": [
                {
                    "emitter": b.emitter,
                    "effect": b.effect,
                    "count": b.count,
                    "origin": list(b.origin),
                }
                for b in plan.batches
            ],
            "posts": [
                {"effect": p.effect, "params": _json_safe(p.params)}
                for p in plan.posts
            ],
            "stats": _json_safe(plan.stats),
        })
    return {
        "ok": True,
        "source": "motus",
        "mode": report.mode,
        "frames": frames,
    }
```

**3. Новый патч B: `patches/motus_scene.py`**

```python
"""motus.scene — выполнить motus-запрос и вернуть снимки кадров.

Параметры:
  query: str                 обязательный текст motus
  times: list[float]         моменты кадров, по умолчанию [0.0]
  particles: bool            включать ли частицы (нужен numpy)
  bpm: float                 музыкальная сетка
  mode: dsl|free|auto
  include_upstream: bool     добавить ключи upstream в результат
"""
from __future__ import annotations

from uroboros.adapters import motus_scene

OP = "motus.scene"


def apply(context, params):
    query = params.get("query")
    if not query or not isinstance(query, str):
        return {"ok": False, "source": "fallback", "error": "query is required"}

    times = params.get("times", [0.0])
    if not isinstance(times, (list, tuple)):
        return {"ok": False, "source": "fallback", "error": "times must be a list"}

    try:
        res = motus_scene(
            query,
            [float(t) for t in times],
            particles=bool(params.get("particles", False)),
            bpm=float(params.get("bpm", 120.0)),
            mode=str(params.get("mode", "auto")),
        )
    except Exception as exc:
        return {
            "ok": False,
            "source": "fallback",
            "error": f"{type(exc).__name__}: {exc}",
        }

    if params.get("include_upstream", True):
        res["upstream_keys"] = sorted((context.get("upstream") or {}).keys())
    return res
```

**4. Пример плана B: `examples/plan_motus.json`**

```json
{
  "format": "uroboros.patch/2",
  "name": "motus_room",
  "nodes": [
    {"id": "geometry", "target": "scene", "operation": "geometry.generate",
     "params": {"width": 5.0, "depth": 4.0, "height": 2.7}},
    {"id": "palette", "target": "color", "operation": "color.palette",
     "params": {"mood": "quiet_warm", "scheme": "analogous", "size": 5}},
    {"id": "compose", "target": "scene", "operation": "scene.compose",
     "needs": ["geometry", "palette"], "params": {"lighting": "soft_indirect"}},
    {"id": "motion", "target": "scene", "operation": "motus.scene",
     "needs": ["compose"],
     "params": {
       "mode": "auto",
       "bpm": 120.0,
       "times": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
       "query": "mode dsl\nnew ball pos=(0,0,0) param.color=(1.0,0.6,0.2)\nnew halo parent=ball pos=(0,0.6,0)\nanim ball.position from=(0,0,0) to=(3,0,0) over=2 ease=smooth\nproc ball.rotation spin rate=180\nproc halo.scale.uniform pulse base=1.0 amp=0.2 freq=2 mode=mul\nfx burst on=ball at=2 for=1.5 count=600 seed=7 speed=7\nfx vignette at=0 amount=0.4\n"
     }}
  ]
}
```

**5. Тест адаптера: `tests/test_motus_adapter.py`**

```python
def test_motus_adapter_fallback(monkeypatch):
    import uroboros.adapters as ad
    monkeypatch.setattr(ad, "motus_available", lambda: False)
    res = ad.motus_scene("new a", [0.0])
    assert res["ok"] is False
    assert res["source"] == "fallback"


def test_motus_patch_requires_query(patches_dir):
    from uroboros.registry import PatchRegistry
    r = PatchRegistry(patches_dir)
    out = r.apply("motus.scene", {"upstream": {}}, {})
    assert out["ok"] is False
    assert "query" in out["error"]


def test_motus_patch_with_query(patches_dir):
    from uroboros.registry import PatchRegistry
    r = PatchRegistry(patches_dir)
    out = r.apply(
        "motus.scene",
        {"upstream": {"compose": {}}},
        {
            "query": "new a\nanim a.position from=(0,0,0) to=(1,0,0) over=1\n",
            "times": [0.0, 0.5, 1.0],
            "particles": False,
        },
    )
    if out["ok"]:
        assert out["source"] == "motus"
        assert len(out["frames"]) == 3
        assert out["upstream_keys"] == ["compose"]
    else:
        assert out["source"] in ("fallback", "motus")
```

**6. Документация: `docs/MOTUS_ADAPTER.md`**

```markdown
# Motus adapter для Uroboros

## Что делает

Добавляет в Uroboros операцию `motus.scene`, которая:

1. принимает текст motus (`query`);
2. создаёт `motus.Runtime`;
3. вызывает `submit(query)`;
4. для каждого `t` из `times` вызывает `frame(t)`;
5. возвращает JSON-снимки: матрицы, параметры, эмиттеры, post-эффекты, статистику.

Uroboros при этом сохраняет кеш, approval, журнал и историю запусков.

## Установка

```bash
**A рядом с B**
export PYTHONPATH="$PWD/../motus:$PYTHONPATH"

**или установить A как пакет**
pip install -e ../motus

**B**
pip install -e .
python -m uroboros patches
```

В списке должен появиться `motus.scene`.

## Контракт

```python
motus_scene(query, times, *, particles=False, bpm=120.0, mode="auto") -> dict
```

Успех:

```json
{
  "ok": true,
  "source": "motus",
  "mode": "dsl",
  "frames": [
    {
      "time": 0.0,
      "items": [{"entity": 0, "name": "ball", "world": [16 чисел], "params": {}}],
      "batches": [],
      "posts": [],
      "stats": {"entities": 1, "drawn": 1, "bindings": 3}
    }
  ],
  "upstream_keys": ["compose"]
}
```

Ошибка:

```json
{
  "ok": false,
  "source": "fallback",
  "error": "motus is not installed; add A to PYTHONPATH or pip install -e A"
}
```

## Параметры `motus.scene`

| Параметр | Тип | По умолчанию | Смысл |
|---|---|---|---|
| `query` | str | — | текст motus, обязателен |
| `times` | list[float] | `[0.0]` | моменты кадров |
| `particles` | bool | `false` | считать ли частицы; требует numpy |
| `bpm` | float | `120.0` | музыкальная сетка |
| `mode` | str | `auto` | `dsl`, `free`, `auto` |
| `include_upstream` | bool | `true` | добавить `upstream_keys` |

## Запуск

```bash
python -m uroboros run --plan examples/plan_motus.json --auto-approve
python -m uroboros inspect --run <id>
```

## Ограничения

- `particles=false` по умолчанию: JSON не содержит массивов частиц.
- Если A не установлен — патч не падает, а возвращает `ok:false`.
- Матрицы column-major, 16 float.
- `motus.scene` не заменяет `scene.compose`, а дополняет его.
```

**7. Схема взаимодействия**

```text
Uroboros plan
  └─ node motion: operation="motus.scene"
        │
        ▼
PatchRegistry.apply("motus.scene")
        │
        ▼
patches/motus_scene.py :: apply(context, params)
        │
        ▼
uroboros.adapters.motus_scene(query, times, ...)
        │
        ├─ motus_available()? ── нет ──► {"ok": false, "source": "fallback"}
        │
        ▼ да
motus.Runtime(Transport(bpm), mode, particles)
        │
        ├─ submit(query)
        │     ├─ ok  ──► для каждого t: frame(t)
        │     └─ fail ──► {"ok": false, "issues": [...]}
        │
        ▼
JSON: frames[] + stats + upstream_keys
        │
        ▼
Uroboros engine
  ├─ cache_put(key, outputs)
  ├─ memory.event("patch")
  ├─ approval(result)
  └─ save_run(run_id, state)
```

**8. Пример использования из Python**

```python
from uroboros import Uroboros, load_plan

u = Uroboros(root=".uroboros", patches="patches", workers=2)
plan = load_plan("examples/plan_motus.json")

state = u.run(
    plan,
    max_iterations=2,
    approval=lambda r: r["outputs"]["motion"]["ok"],
)

if state["status"] == "approved":
    motion = state["final"]["outputs"]["motion"]
    for frame in motion["frames"]:
        print(frame["time"], [i["name"] for i in frame["items"]])
```

**9. Итог**


