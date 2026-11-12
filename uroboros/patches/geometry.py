"""geometry.generate — построить геометрию комнаты.

Если Cozy Engine доступен и настроен — использует его примитивы.
Иначе — простой box-room.
"""
from __future__ import annotations

from uroboros.adapters import cozy_engine_available

OP = "geometry.generate"


def apply(context, params):
    width = float(params.get("width", 5.0))
    depth = float(params.get("depth", 4.0))
    height = float(params.get("height", 2.7))
    spacing = float(params.get("spacing", 1.0))

    if cozy_engine_available():
        # лёгкая проверка доступности — реальная сборка примитивов в cozy_scene.py
        return {
            "asset": {
                "kind": "room_geometry", "width": width, "depth": depth, "height": height,
                "spacing": spacing, "source": "cozy_engine_available",
            }
        }

    return {
        "asset": {
            "kind": "room_geometry", "width": width, "depth": depth, "height": height,
            "spacing": spacing, "source": "fallback_box",
        }
    }