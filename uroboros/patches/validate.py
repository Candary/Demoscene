"""validate.scene — базовые проверки собранной сцены."""
from __future__ import annotations

_HEX_LEN = (4, 7)

OP = "validate.scene"


def apply(context, params):
    upstream = context["upstream"]
    compose_out = upstream.get("compose") or {}
    scene = compose_out.get("scene") or {}

    problems: list[str] = []

    geom = scene.get("geometry") or {}
    for key in ("width", "depth", "height"):
        v = geom.get(key)
        if not isinstance(v, (int, float)) or v <= 0:
            problems.append(f"geometry.{key} missing or non-positive: {v!r}")

    palette = scene.get("palette") or []
    if not (2 <= len(palette) <= 12):
        problems.append(f"palette size {len(palette)} not in [2, 12]")
    for c in palette:
        if not (isinstance(c, str) and c.startswith("#") and len(c) in _HEX_LEN):
            problems.append(f"bad color: {c!r}")

    mood = scene.get("mood")
    if not isinstance(mood, str) or not mood:
        problems.append(f"bad mood: {mood!r}")

    return {
        "ok": not problems,
        "problems": problems,
        "scene_summary": {
            "width": geom.get("width"),
            "depth": geom.get("depth"),
            "height": geom.get("height"),
            "palette_size": len(palette),
            "mood": mood,
            "geometry_source": (scene.get("provenance") or {}).get("geometry_source"),
            "palette_source": (scene.get("provenance") or {}).get("palette_source"),
        },
    }