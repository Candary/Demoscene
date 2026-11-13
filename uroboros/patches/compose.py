"""scene.compose — собрать итоговую сцену из geometry + palette."""
from __future__ import annotations

OP = "scene.compose"


def apply(context, params):
    upstream = context["upstream"]
    geometry = upstream["geometry"]["asset"]
    palette = upstream["palette"]["palette"]
    mood = upstream["palette"].get("mood", params.get("mood", "quiet_warm"))
    palette_source = upstream["palette"].get("source", "unknown")

    return {
        "scene": {
            "geometry": geometry,
            "palette": palette,
            "mood": mood,
            "lighting": params.get("lighting", "soft_indirect"),
            "provenance": {
                "geometry_source": geometry.get("source"),
                "palette_source": palette_source,
            },
        }
    }