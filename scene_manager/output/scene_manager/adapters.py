"""Адаптеры к соседним системам проекта: Cozy Engine (объекты и примитивы) и Color Matrix (цвета).

Cozy Engine -> демо: примитивы объектов (box/cylinder/sphere) превращаются в массив чисел (ассет), который SDF-эффект читает как
uniform-массив farray и рисует рэймарчингом. Цвета слотов приходят из Color Matrix через cozy_palette(...).slot_colors.
Cozy Engine не выбирает шейдеры и не знает про «настроение» абстрактных эффектов: он отвечает только за объекты и их форму.
"""
from __future__ import annotations

import math
import re

SHAPE = {"box": 0, "cylinder": 1, "sphere": 2}
AXIS = {"x": 0, "y": 1, "z": 2}
LAYOUT = ["shape", "axis", "sx", "sy", "sz", "px", "py", "pz", "rot_y_rad", "r", "g", "b"]   # 12 чисел на примитив (shape: 0 box, 1 cylinder, 2 sphere)


def _prims():
    from cozy_engine import primitives   # лежит рядом (output/cozy_engine)
    return primitives


def _hex(h: str) -> tuple[float, float, float]:
    m = re.match(r"^#?([0-9a-fA-F]{6})$", h or "")
    if not m:
        return (0.5, 0.5, 0.5)
    v = m.group(1)
    return tuple(int(v[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _footprint(recipe, x: float, z: float, rot_deg: float, scale: float) -> tuple[float, float, float, float]:
    (lx, _, lz), (hx, _, hz) = recipe.bbox
    th = math.radians(rot_deg)
    c, s = math.cos(th), math.sin(th)
    xs, zs = [], []
    for px in (lx * scale, hx * scale):
        for pz in (lz * scale, hz * scale):
            xs.append(x + px * c + pz * s)
            zs.append(z - px * s + pz * c)
    return min(xs), max(xs), min(zs), max(zs)


def check_layout(placements: list[dict], room: tuple[float, float] | None = None, tolerance: float = 0.02) -> dict:
    """Проверка расстановки: выход за границы комнаты (x ∈ [-w/2, w/2], z ∈ [-d/2, d/2]) и пересечения напольных объектов в плане.
    Настенные и стоящие на поверхности объекты (elevation задан или mount != floor) в пересечениях не участвуют."""
    P = _prims()
    items, out_of, overlaps = [], [], []
    for i, p in enumerate(placements):
        rid = p.get("recipe") or (P.recipes_for_atom(p["object"])[0].id if P.recipes_for_atom(p["object"]) else None)
        if rid is None or rid not in P.RECIPES:
            raise ValueError(f"placements[{i}]: нет рецепта для {p.get('object')!r}")
        r = P.RECIPES[rid]
        fp = _footprint(r, p.get("x", 0.0), p.get("z", 0.0), p.get("rotation_y_deg", 0.0), p.get("scale", 1.0))
        items.append((i, rid, r, fp, p))
        if room and r.mount != "wall":
            w, d = room
            if fp[0] < -w / 2 - tolerance or fp[1] > w / 2 + tolerance or fp[2] < -d / 2 - tolerance or fp[3] > d / 2 + tolerance:
                out_of.append({"index": i, "object": rid, "footprint": [round(v, 2) for v in fp]})
    floor = [it for it in items if it[2].mount == "floor" and it[4].get("elevation") is None]
    for a in range(len(floor)):
        for b in range(a + 1, len(floor)):
            A, B = floor[a][3], floor[b][3]
            ox, oz = min(A[1], B[1]) - max(A[0], B[0]), min(A[3], B[3]) - max(A[2], B[2])
            if ox > tolerance and oz > tolerance:
                # ковёр лежит под мебелью — это нормально
                if "rug" in (floor[a][1], floor[b][1]):
                    continue
                overlaps.append({"a": floor[a][1], "b": floor[b][1], "indices": [floor[a][0], floor[b][0]], "overlap_m": [round(ox, 2), round(oz, 2)]})
    return {"ok": not out_of and not overlaps, "out_of_room": out_of, "overlaps": overlaps}


def cozy_asset(placements: list[dict], slot_colors: dict | None = None) -> dict:
    """placements: [{object | recipe, x, z, rotation_y_deg, scale, elevation, colors?}] -> ассет {layout, stride, count, floats, objects}."""
    P = _prims()
    floats: list[float] = []
    names: list[str] = []
    for i, p in enumerate(placements):
        rid = p.get("recipe") or (P.recipes_for_atom(p["object"])[0].id if P.recipes_for_atom(p["object"]) else None)
        if rid is None or rid not in P.RECIPES:
            raise ValueError(f"placements[{i}]: нет рецепта для {p.get('object')!r}")
        colors = {**(slot_colors or {}), **(p.get("colors") or {})}
        for part in P.instantiate(rid, p.get("x", 0.0), p.get("z", 0.0), p.get("rotation_y_deg", 0.0), p.get("scale", 1.0), colors, p.get("elevation")):
            r, g, b = _hex(part["color"])
            floats += [SHAPE[part["shape"]], AXIS[part["axis"]], *part["size"], *part["pos"], math.radians(part["rot_y_deg"]), r, g, b]
        names.append(rid)
    return {"layout": LAYOUT, "stride": len(LAYOUT), "count": len(floats) // len(LAYOUT), "floats": [round(float(v), 5) for v in floats],
            "objects": names, "source": "cozy_engine.primitives"}
