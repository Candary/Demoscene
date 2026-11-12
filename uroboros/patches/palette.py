"""color.palette — подобрать палитру.

Если Color Matrix настроена — использует её. Иначе — hardcoded fallback
по mood (с явным полем source, чтобы downstream знал, откуда цвет).
"""
from __future__ import annotations

from uroboros.adapters import build_palette_via_matrix

OP = "color.palette"

# fallback на случай, если Color Matrix не настроена
MOOD_FALLBACK = {
    "quiet_warm":    ["#e6d7c3", "#a8896c", "#7a5c43", "#f5f0e8", "#c9a882"],
    "energetic":     ["#ff6b6b", "#ffd93d", "#6bcb77", "#4d96ff", "#f5f0e8"],
    "calm":          ["#a8dadc", "#457b9d", "#1d3557", "#f1faee", "#e9c46a"],
    "tense":         ["#2b2d42", "#8d99ae", "#ef233c", "#edf2f4", "#d90429"],
    "anxious":       ["#22223b", "#4a4e69", "#9a8c98", "#c9ada7", "#f2e9e4"],
}


def apply(context, params):
    mood = str(params.get("mood", "quiet_warm"))
    scheme = str(params.get("scheme", "analogous"))
    size = int(params.get("size", 5))

    res = build_palette_via_matrix(mood, scheme, size)
    if res.get("ok"):
        return {
            "palette": res["palette"],
            "mood": mood,
            "source": "color_matrix",
            "profiles": res.get("profiles", []),
            "checks": res.get("checks", {}),
        }

    fallback = MOOD_FALLBACK.get(mood, MOOD_FALLBACK["quiet_warm"])
    return {
        "palette": fallback[:size],
        "mood": mood,
        "source": "fallback_hardcoded",
        "reason": res.get("error", "Color Matrix unavailable"),
    }