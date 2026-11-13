"""color.describe — профиль цвета через Color Matrix (если настроена)."""
from __future__ import annotations

from uroboros.adapters import describe_color_via_matrix

OP = "color.describe"


def apply(context, params):
    color = str(params.get("color", "#2563eb"))
    return describe_color_via_matrix(color)