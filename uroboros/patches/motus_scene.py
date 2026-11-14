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

OP = "motus.scene"


def apply(context, params):
    query = params.get("query")
    if not query or not isinstance(query, str):
        return {"ok": False, "source": "fallback", "error": "query is required (str)"}

    times = params.get("times", [0.0])
    if not isinstance(times, (list, tuple)):
        return {"ok": False, "source": "fallback", "error": "times must be a list"}

    try:
        from uroboros.adapters import motus_scene
    except ImportError as exc:
        return {"ok": False, "source": "fallback",
                "error": f"adapter import failed: {exc}"}

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
        upstream = context.get("upstream") or {}
        res["upstream_keys"] = sorted(upstream.keys()) if isinstance(upstream, dict) else []
    return res
