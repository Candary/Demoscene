"""Helpers to build and (de)serialize Uroboros plans."""
from __future__ import annotations

import json
from pathlib import Path

from .formats import FORMAT


def simple_room_plan(width: float = 5.0, depth: float = 4.0, mood: str = "quiet_warm") -> dict:
    return {
        "format": FORMAT,
        "name": "simple_room",
        "nodes": [
            {"id": "geometry", "target": "scene", "operation": "geometry.generate",
             "params": {"width": width, "depth": depth}},
            {"id": "palette", "target": "color", "operation": "color.palette",
             "params": {"mood": mood, "scheme": "analogous", "size": 5}},
            {"id": "compose", "target": "scene", "operation": "scene.compose",
             "needs": ["geometry", "palette"], "params": {"lighting": "soft_indirect", "mood": mood}},
        ],
    }


def full_plan(width: float = 5.0, depth: float = 4.0, mood: str = "quiet_warm",
              with_validation: bool = True, with_cozy: bool = False) -> dict:
    plan = simple_room_plan(width, depth, mood)
    if with_validation:
        plan["nodes"].append({
            "id": "validate", "target": "scene", "operation": "validate.scene",
            "needs": ["compose"], "params": {},
        })
    if with_cozy:
        plan["nodes"].append({
            "id": "cozy", "target": "scene", "operation": "cozy.plan_room",
            "params": {"room": "living_room", "count": 6},
        })
    plan["name"] = "full_room" if not with_cozy else "cozy_room"
    return plan


def load_plan(path: str | Path) -> dict:
    return json.loads(Path(path).read_text("utf-8"))


def save_plan(plan: dict, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p