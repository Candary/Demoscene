"""Библиотека примитивов: из чего собрать каждый объект словаря Cozy Engine (vocab.OBJECTS).

Система координат объекта: метры; начало — центр основания на полу (для настенных — центр нижнего края у плоскости стены);
+y вверх, лицевая сторона смотрит в +z. Часть (Part) — геометрический примитив: box / cylinder / sphere.
  size — габариты по осям (dx, dy, dz) ДО поворота (у цилиндра и сферы это размеры описанного бокса), pos — центр части,
  axis — ось цилиндра ('x' | 'y' | 'z'), slot — материальный слот, к которому потом привязывается цвет.
Размеры — типичные бытовые (ориентировочные, не из измерений корпуса).
Каждый объект — не «картинка», а набор частей, поэтому LLM может собрать сцену в Three.js/Blender/CSS без внешних моделей.

Связь с Color Matrix: слоты материалов -> цветовые роли (SLOT_ROLE). Цвета для ролей выбираются инструментами Color Matrix
(см. tools.CozyToolbox.cozy_palette), а не хранятся здесь.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from . import vocab


@dataclass(frozen=True)
class Part:
    name: str
    shape: str                       # 'box' | 'cylinder' | 'sphere'
    size: tuple[float, float, float]
    pos: tuple[float, float, float]
    slot: str
    axis: str = "y"


@dataclass(frozen=True)
class Recipe:
    id: str
    atom: str                        # атом словаря, который реализует рецепт
    parts: tuple[Part, ...]
    mount: str = "floor"             # 'floor' | 'wall' | 'surface'
    mount_height: float = 0.0        # для 'wall': высота нижнего края над полом (м)
    note: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def bbox(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        lo = [min(p.pos[i] - p.size[i] / 2 for p in self.parts) for i in range(3)]
        hi = [max(p.pos[i] + p.size[i] / 2 for p in self.parts) for i in range(3)]
        return tuple(lo), tuple(hi)  # type: ignore[return-value]

    @property
    def size(self) -> tuple[float, float, float]:
        lo, hi = self.bbox
        return tuple(round(h - l, 3) for l, h in zip(lo, hi))  # type: ignore[return-value]

    @property
    def slots(self) -> list[str]:
        return sorted({p.slot for p in self.parts})


def B(name, slot, size, pos):
    return Part(name, "box", size, pos, slot)


def C(name, slot, size, pos, axis="y"):
    return Part(name, "cylinder", size, pos, slot, axis)


def S(name, slot, size, pos):
    return Part(name, "sphere", size, pos, slot)


def _legs4(slot, d, h, x, z):
    return tuple(C(f"leg{i}", slot, (d, h, d), (sx * x, h / 2, sz * z)) for i, (sx, sz) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]))


_R: list[Recipe] = []


def _add(*a, **k):
    _R.append(Recipe(*a, **k))


_add("sofa", "sofa", _legs4("wood", 0.06, 0.10, 0.90, 0.38) + (
    B("base", "upholstery", (2.0, 0.30, 0.90), (0, 0.25, 0)),
    B("back", "upholstery", (2.0, 0.45, 0.22), (0, 0.625, -0.34)),
    B("arm_l", "upholstery", (0.20, 0.25, 0.68), (-0.90, 0.525, 0.11)),
    B("arm_r", "upholstery", (0.20, 0.25, 0.68), (0.90, 0.525, 0.11)),
    B("seat_l", "upholstery", (0.80, 0.12, 0.66), (-0.40, 0.46, 0.12)),
    B("seat_r", "upholstery", (0.80, 0.12, 0.66), (0.40, 0.46, 0.12))), tags=("seating", "anchor"))
_add("armchair", "armchair", _legs4("wood", 0.05, 0.12, 0.34, 0.34) + (
    B("base", "upholstery", (0.85, 0.28, 0.85), (0, 0.26, 0)),
    B("back", "upholstery", (0.85, 0.50, 0.20), (0, 0.65, -0.325)),
    B("arm_l", "upholstery", (0.16, 0.22, 0.65), (-0.345, 0.51, 0.10)),
    B("arm_r", "upholstery", (0.16, 0.22, 0.65), (0.345, 0.51, 0.10)),
    B("seat", "upholstery", (0.53, 0.12, 0.62), (0, 0.46, 0.105))), tags=("seating", "anchor"))
_add("ottoman", "ottoman", _legs4("wood", 0.05, 0.10, 0.20, 0.20) + (
    B("top", "upholstery", (0.5, 0.30, 0.5), (0, 0.25, 0)),), tags=("seating",))
_add("bed", "bed", (
    B("frame", "wood", (1.6, 0.25, 2.1), (0, 0.125, 0)),
    B("headboard", "wood", (1.6, 1.10, 0.10), (0, 0.55, -1.00)),
    B("mattress", "textile", (1.5, 0.22, 2.0), (0, 0.36, 0)),
    B("pillow_l", "textile", (0.55, 0.12, 0.35), (-0.35, 0.53, -0.75)),
    B("pillow_r", "textile", (0.55, 0.12, 0.35), (0.35, 0.53, -0.75)),
    B("duvet", "textile", (1.5, 0.06, 1.2), (0, 0.50, 0.35))), tags=("sleeping", "anchor"))
_add("cushion", "cushion", (B("pad", "textile", (0.45, 0.12, 0.45), (0, 0.06, 0)),), mount="surface", tags=("soft", "accent"))
_add("blanket", "blanket", (B("throw", "textile", (1.3, 0.04, 1.0), (0, 0.02, 0)),), mount="surface", tags=("soft", "accent"))
_add("rug", "rug", (B("rug", "textile", (2.4, 0.02, 1.6), (0, 0.01, 0)),), tags=("soft", "floor"))
_add("curtain", "curtain", (
    B("panel", "textile", (1.4, 2.2, 0.08), (0, 1.1, 0.05)),
    C("rod", "metal", (1.6, 0.03, 0.03), (0, 2.25, 0.05), axis="x")), mount="wall", tags=("soft",))
_add("table", "table", (B("top", "wood", (1.4, 0.04, 0.8), (0, 0.73, 0)),) + tuple(
    B(f"leg{i}", "wood", (0.06, 0.71, 0.06), (sx * 0.64, 0.355, sz * 0.34)) for i, (sx, sz) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)])), tags=("surface",))
_add("coffee_table", "coffee_table", (
    B("top", "wood", (1.0, 0.04, 0.55), (0, 0.40, 0)), B("shelf", "wood", (0.9, 0.02, 0.45), (0, 0.15, 0))) + tuple(
    B(f"leg{i}", "wood", (0.05, 0.38, 0.05), (sx * 0.44, 0.19, sz * 0.22)) for i, (sx, sz) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)])), tags=("surface", "anchor"))
_add("chair", "chair", (
    B("seat", "wood", (0.45, 0.04, 0.45), (0, 0.45, 0)), B("back", "wood", (0.45, 0.45, 0.04), (0, 0.675, -0.205))) + tuple(
    B(f"leg{i}", "wood", (0.04, 0.43, 0.04), (sx * 0.2, 0.215, sz * 0.2)) for i, (sx, sz) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)])), tags=("seating",))
_add("desk", "desk", (
    B("top", "wood", (1.4, 0.04, 0.65), (0, 0.73, 0)), B("side_l", "wood", (0.04, 0.71, 0.65), (-0.68, 0.355, 0)),
    B("side_r", "wood", (0.04, 0.71, 0.65), (0.68, 0.355, 0)), B("back", "wood", (1.32, 0.40, 0.02), (0, 0.50, -0.30))), tags=("surface",))
_add("bookshelf", "bookshelf", (
    B("side_l", "wood", (0.03, 1.8, 0.3), (-0.385, 0.9, 0)), B("side_r", "wood", (0.03, 1.8, 0.3), (0.385, 0.9, 0)),
    B("back", "wood", (0.8, 1.8, 0.01), (0, 0.9, -0.145))) + tuple(
    B(f"shelf{i}", "wood", (0.74, 0.03, 0.3), (0, y, 0)) for i, y in enumerate([0.015, 0.46, 0.91, 1.36, 1.785])), tags=("storage",))
_add("shelf", "shelf", (
    B("board", "wood", (0.9, 0.03, 0.22), (0, 0.135, 0)), B("bracket_l", "metal", (0.02, 0.12, 0.18), (-0.35, 0.06, -0.02)),
    B("bracket_r", "metal", (0.02, 0.12, 0.18), (0.35, 0.06, -0.02))), mount="wall", mount_height=1.3, tags=("storage",))
_add("cabinet", "cabinet", (
    B("plinth", "wood", (0.8, 0.10, 0.4), (0, 0.05, 0)), B("body", "wood", (0.9, 0.90, 0.45), (0, 0.55, 0)),
    B("handle_l", "metal", (0.02, 0.12, 0.02), (-0.06, 0.65, 0.235)), B("handle_r", "metal", (0.02, 0.12, 0.02), (0.06, 0.65, 0.235))), tags=("storage",))
_add("books", "books", (
    B("book1", "paper", (0.25, 0.04, 0.18), (0, 0.02, 0)), B("book2", "paper", (0.22, 0.04, 0.17), (0.01, 0.06, 0)),
    B("book3", "paper", (0.20, 0.04, 0.16), (-0.01, 0.10, 0))), mount="surface", tags=("accent",))
_add("lamp", "lamp", (
    C("base", "metal", (0.25, 0.03, 0.25), (0, 0.015, 0)), C("pole", "metal", (0.03, 1.2, 0.03), (0, 0.63, 0)),
    C("shade", "light", (0.35, 0.30, 0.35), (0, 1.40, 0))), note="торшер", tags=("light", "anchor"))
_add("lamp_table", "lamp", (
    C("base", "ceramic", (0.14, 0.25, 0.14), (0, 0.125, 0)), C("shade", "light", (0.30, 0.22, 0.30), (0, 0.36, 0))),
    mount="surface", note="настольная лампа", tags=("light", "accent"))
_add("fireplace", "fireplace", (
    B("surround_l", "stone", (0.25, 1.10, 0.4), (-0.575, 0.55, 0)), B("surround_r", "stone", (0.25, 1.10, 0.4), (0.575, 0.55, 0)),
    B("mantel", "wood", (1.4, 0.10, 0.45), (0, 1.15, 0.025)), B("firebox", "stone", (0.9, 0.70, 0.05), (0, 0.45, -0.175)),
    B("fire", "light", (0.5, 0.30, 0.05), (0, 0.25, -0.12))), tags=("light", "anchor"))
_add("candle", "candle", (
    C("wax", "ceramic", (0.07, 0.12, 0.07), (0, 0.06, 0)), S("flame", "light", (0.02, 0.03, 0.02), (0, 0.135, 0))),
    mount="surface", tags=("light", "accent"))
_add("plant", "plant", (
    C("pot", "ceramic", (0.25, 0.22, 0.25), (0, 0.11, 0)), C("stem", "foliage", (0.03, 0.35, 0.03), (0, 0.395, 0)),
    S("leaves", "foliage", (0.40, 0.50, 0.40), (0, 0.65, 0))), tags=("accent", "natural"))
_add("window", "window", (
    B("frame_bottom", "wood", (1.2, 0.05, 0.12), (0, 0.025, 0)), B("frame_top", "wood", (1.2, 0.05, 0.12), (0, 1.275, 0)),
    B("frame_l", "wood", (0.05, 1.2, 0.12), (-0.575, 0.65, 0)), B("frame_r", "wood", (0.05, 1.2, 0.12), (0.575, 0.65, 0)),
    B("glass", "glass", (1.1, 1.2, 0.01), (0, 0.65, 0))), mount="wall", mount_height=0.9, tags=("light", "natural"))
_add("door", "door", (
    B("leaf", "wood", (0.9, 2.05, 0.04), (0, 1.025, 0)), S("knob", "metal", (0.06, 0.06, 0.06), (0.35, 1.0, 0.05))), mount="wall", tags=())
_add("artwork", "artwork", (
    B("frame", "wood", (0.6, 0.8, 0.03), (0, 0.4, 0)), B("canvas", "paper", (0.52, 0.72, 0.01), (0, 0.4, 0.02))),
    mount="wall", mount_height=1.4, tags=("accent",))
_add("mirror", "mirror", (
    B("frame", "metal", (0.6, 1.0, 0.03), (0, 0.5, 0)), B("glass", "glass", (0.54, 0.94, 0.01), (0, 0.5, 0.02))),
    mount="wall", mount_height=1.0, tags=("accent",))
_add("basket", "basket", (C("body", "wicker", (0.4, 0.35, 0.4), (0, 0.175, 0)),), tags=("storage", "accent"))
_add("tv", "tv", (
    B("panel", "screen", (1.1, 0.62, 0.04), (0, 0.35, 0)), B("foot", "metal", (0.4, 0.04, 0.2), (0, 0.02, 0))), mount="surface", tags=())
_add("computer", "computer", (
    C("foot", "metal", (0.20, 0.02, 0.15), (0, 0.01, 0)), B("neck", "metal", (0.04, 0.14, 0.04), (0, 0.09, 0)),
    B("screen", "screen", (0.5, 0.30, 0.03), (0, 0.31, 0))), mount="surface", tags=())

RECIPES: dict[str, Recipe] = {r.id: r for r in _R}

# Слот материала -> цветовая роль. Роли wall/floor/textile_main/textile_accent/wood/light подбираются через Color Matrix.
SLOT_ROLE = {"wood": "wood", "upholstery": "textile_main", "textile": "textile_accent", "light": "light",
             "metal": "metal", "ceramic": "ceramic", "foliage": "foliage", "glass": "glass", "paper": "paper",
             "stone": "stone", "screen": "screen", "wicker": "wicker"}
COLOR_MATRIX_ROLES = ("wall", "floor", "textile_main", "textile_accent", "wood", "light")
# Нейтральные значения по умолчанию для слотов, которые Color Matrix не подбирает (обычные цвета материалов, не из матрицы).
DEFAULT_ROLE_COLORS = {"metal": "#6e6e73", "ceramic": "#e9e4da", "foliage": "#4a7c4f", "glass": "#bcd4dc", "paper": "#efe9dc",
                       "stone": "#8d8a85", "screen": "#161618", "wicker": "#b8905a"}


def recipes_for_atom(atom: str) -> list[Recipe]:
    return [r for r in RECIPES.values() if r.atom == atom]


def atoms_with_recipes() -> list[str]:
    return sorted({r.atom for r in RECIPES.values()}, key=vocab.ATOM_INDEX.get)


def describe(recipe: Recipe) -> dict:
    return {"id": recipe.id, "atom": recipe.atom, "size_m": list(recipe.size), "mount": recipe.mount,
            "mount_height_m": recipe.mount_height, "slots": {s: SLOT_ROLE[s] for s in recipe.slots}, "tags": list(recipe.tags),
            "note": recipe.note,
            "parts": [{"name": p.name, "shape": p.shape, "size": list(p.size), "pos": list(p.pos), "axis": p.axis, "slot": p.slot}
                      for p in recipe.parts]}


def instantiate(recipe_id: str, x: float = 0.0, z: float = 0.0, rotation_y_deg: float = 0.0, scale: float = 1.0,
                colors: dict[str, str] | None = None, elevation: float | None = None) -> list[dict]:
    """Части объекта в мировых координатах. Поворот вокруг оси y (против часовой, если смотреть сверху): позиции частей
    повёрнуты здесь, а размеры/ось оставлены локальными — рендерер поворачивает каждую часть на rot_y_deg вокруг её центра.
    colors: {роль или слот: '#hex'}; elevation — высота начала объекта над полом (для настенных и стоящих на поверхности)."""
    r = RECIPES[recipe_id]
    colors = colors or {}
    base_y = r.mount_height if (elevation is None and r.mount == "wall") else (elevation or 0.0)
    th = math.radians(rotation_y_deg)
    c, s = math.cos(th), math.sin(th)
    out = []
    for p in r.parts:
        px, py, pz = (v * scale for v in p.pos)
        wx = x + px * c + pz * s
        wz = z - px * s + pz * c
        role = SLOT_ROLE[p.slot]
        color = colors.get(p.slot) or colors.get(role) or DEFAULT_ROLE_COLORS.get(role)
        out.append({"object": recipe_id, "part": p.name, "shape": p.shape, "size": [round(v * scale, 4) for v in p.size],
                    "axis": p.axis, "pos": [round(wx, 4), round(py + base_y, 4), round(wz, 4)], "rot_y_deg": rotation_y_deg,
                    "slot": p.slot, "role": role, "color": color})
    return out


def validate_recipes() -> list[str]:
    """Проверки согласованности: покрытие словаря, положение на полу, форма примитивов. Возвращает список проблем."""
    problems = []
    objs = set(vocab.OBJECTS)
    have = set(atoms_with_recipes())
    if objs - have:
        problems.append(f"нет рецептов для атомов: {sorted(objs - have)}")
    if have - objs:
        problems.append(f"рецепты для неизвестных атомов: {sorted(have - objs)}")
    for r in RECIPES.values():
        lo, hi = r.bbox
        if abs(lo[1]) > 1e-6:
            problems.append(f"{r.id}: нижний край на y={lo[1]:.3f}, ожидалось 0")
        for p in r.parts:
            if p.slot not in SLOT_ROLE:
                problems.append(f"{r.id}/{p.name}: неизвестный слот {p.slot}")
            if p.shape not in ("box", "cylinder", "sphere") or any(v <= 0 for v in p.size):
                problems.append(f"{r.id}/{p.name}: плохая форма/размер")
            if p.shape == "cylinder" and p.axis not in ("x", "y", "z"):
                problems.append(f"{r.id}/{p.name}: ось цилиндра {p.axis}")
    return problems
