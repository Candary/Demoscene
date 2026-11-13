"""cozy.plan_room — план уютной комнаты через Cozy Engine (если настроен)."""
from __future__ import annotations

from uroboros.adapters import plan_room_via_cozy

OP = "cozy.plan_room"


def apply(context, params):
    room = str(params.get("room", "living_room"))
    count = int(params.get("count", 6))
    return plan_room_via_cozy(room, count)