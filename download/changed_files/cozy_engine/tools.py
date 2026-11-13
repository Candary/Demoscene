"""Инструменты Cozy Engine для LLM + единый набор с инструментами Color Matrix.

Разделение труда:
  Cozy Engine  -> ЧТО поставить в сцену: объекты (по ассоциациям с «уютом» в корпусе) и их примитивы (из чего собрать);
  Color Matrix -> КАКОГО ЦВЕТА: цвета, empathy, intensity, температура, контраст, дальтонизм.
Связка — материальные слоты объектов (primitives.SLOT_ROLE) <-> цветовые роли палитры (cozy_palette).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from . import primitives as prim
from . import vocab
from .matrix import CozyMatrix, MIN_PAIR_SUPPORT

# color_matrix_python лежит рядом (output/color_matrix_python)
from color_matrix_python.tools import TOOL_SCHEMAS as COLOR_SCHEMAS, ColorToolbox  # noqa: E402
# perf C-01: импорты colorspace на уровне модуля (раньше были в _delta — 4 dict lookup на вызов)
from color_matrix_python.colorspace import delta_e_ok, parse_color, rgb_to_oklab  # noqa: E402

ARCHITECTURE = {"door", "window"}      # не «мебель»: в рекомендации объектов не попадают
SUGGEST_GROUPS = ("object",)

PROVENANCE_COZY = ("Объекты: ассоциации в подписях GPT-4o к кадрам ScanNet (слово 'cozy' и родственные), это НЕ оценки людей и не причинные "
                   "эффекты. Lift посчитан внутри комнаты данного типа, поправка на скан (кадры одной комнаты не независимы). "
                   "Размеры примитивов — типичные бытовые, не из корпуса.")

_ROOM = {"type": "string", "enum": vocab.ROOMS, "description": "Room type from the Cozy Engine vocabulary."}

COZY_SCHEMAS: list[dict] = [
    {"type": "function", "function": {
        "name": "cozy_scene_plan",
        "description": ("One-call plan for a cozy room: ranks objects by how strongly they go with 'cozy' captions INSIDE this room type "
                        "(Cozy Engine), attaches primitive recipes for building them, and picks a palette for the material slots "
                        "with the Color Matrix (empathy/intensity/temperature + contrast checks). Use it first; then refine with the "
                        "other tools. Never present the result as human-validated: evidence is caption-based."),
        "parameters": {"type": "object", "properties": {
            "room": _ROOM, "count": {"type": "integer", "minimum": 3, "maximum": 14, "default": 8},
            "avoid": {"type": "array", "items": {"type": "string"}, "description": "Object atoms to exclude."},
            "must_have": {"type": "array", "items": {"type": "string"}, "description": "Object atoms that must be included."},
            "include_parts": {"type": "boolean", "default": False, "description": "Include full part lists of every recipe."}},
            "required": ["room"]}}},
    {"type": "function", "function": {
        "name": "cozy_suggest_objects",
        "description": ("Rank objects for a room type by lift of the cozy response within that room (n_eff_scans = support in independent rooms). "
                        "Also returns atmosphere hints: lights/materials/qualities that go with cozy captions in the same room."),
        "parameters": {"type": "object", "properties": {
            "room": _ROOM, "count": {"type": "integer", "default": 8}, "avoid": {"type": "array", "items": {"type": "string"}},
            "ascending": {"type": "boolean", "default": False, "description": "True: objects that go with NON-cozy captions (what to avoid)."}},
            "required": ["room"]}}},
    {"type": "function", "function": {
        "name": "cozy_evidence",
        "description": ("Evidence for one atom or a pair of atoms (e.g. ['sofa'] or ['sofa','rug']): frames, effective independent scans, "
                        "mean and shrunk estimate of the response, lift vs global mean. Low n_eff_scans means do not draw conclusions."),
        "parameters": {"type": "object", "properties": {
            "atoms": {"type": "array", "items": {"type": "string", "enum": vocab.ATOMS}, "minItems": 1, "maxItems": 2}},
            "required": ["atoms"]}}},
    {"type": "function", "function": {
        "name": "get_primitives",
        "description": ("Primitive recipe (boxes/cylinders/spheres with sizes in meters, positions, axes and material slots) for an object "
                        "atom, so the object can be built without external models. Origin: floor center, +y up, front +z."),
        "parameters": {"type": "object", "properties": {"object": {"type": "string", "enum": vocab.OBJECTS}}, "required": ["object"]}}},
    {"type": "function", "function": {
        "name": "instantiate_object",
        "description": "Place an object: returns its parts in world coordinates (rotation about y, scale, per-slot colors, wall/surface elevation).",
        "parameters": {"type": "object", "properties": {
            "object": {"type": "string", "enum": vocab.OBJECTS}, "x": {"type": "number", "default": 0}, "z": {"type": "number", "default": 0},
            "rotation_y_deg": {"type": "number", "default": 0}, "scale": {"type": "number", "default": 1},
            "elevation": {"type": "number", "description": "Height of the object's base above the floor (m), e.g. a lamp on a table."},
            "colors": {"type": "object", "additionalProperties": {"type": "string"}, "description": "{slot or role: '#hex'}"}},
            "required": ["object"]}}},
    {"type": "function", "function": {
        "name": "cozy_palette",
        "description": ("Palette for the six color roles of a cozy room (wall, floor, textile_main, textile_accent, wood, light) chosen with "
                        "the Color Matrix (warm, low-intensity, gamut-safe), plus empirical color hints from the caption corpus. "
                        "Returns slot->hex ready for instantiate_object. The six roles come from fixed design constraints, so the palette is the same for every room; `room` only selects the empirical hints."),
        "parameters": {"type": "object", "properties": {"room": _ROOM}, "required": ["room"]}}},
]

# Цветовые роли -> запросы к Color Matrix (find_colors). Это эвристики дизайна «уютной» палитры, а не данные корпуса.
ROLE_QUERIES: dict[str, dict] = {
    # hue_range — OKLCH-тон в градусах (красный ~25, оранжевый ~60, жёлтый ~100). Тона заданы дизайнерски: стена/пол/дерево
    # в «земляной» зоне, иначе поиск по одним лишь эмпатии/температуре возвращал, например, фиолетовый пол.
    "wall": dict(hue_range=[40, 110], lightness_range=[0.72, 0.93], min_chroma=0.01, max_chroma=0.06, feel="warmth"),
    "floor": dict(hue_range=[35, 85], lightness_range=[0.30, 0.55], min_chroma=0.04, max_chroma=0.10),
    "textile_main": dict(feel="warmth", lightness_range=[0.40, 0.72], min_chroma=0.04, max_chroma=0.13,
                         intensity=["very_low", "low", "medium"], temperature=["warm", "hot", "neutral"]),
    "textile_accent": dict(feel="delight", lightness_range=[0.45, 0.78], min_chroma=0.08, max_chroma=0.16,
                           intensity=["low", "medium", "high"]),
    "wood": dict(hue_range=[45, 80], lightness_range=[0.32, 0.62], min_chroma=0.05, max_chroma=0.13),
    "light": dict(hue_range=[70, 105], lightness_range=[0.88, 0.97], min_chroma=0.04, max_chroma=0.16),
}
ROLE_FALLBACKS = (  # если запрос пуст: ослабляем в таком порядке
    ("intensity", None), ("feel", None), ("temperature", None), ("min_chroma", None))


class CozyToolbox:
    def __init__(self, matrix: CozyMatrix, color_toolbox: ColorToolbox, color_stats: dict | None = None):
        self.m, self.color, self.color_stats = matrix, color_toolbox, color_stats or {}
        self._tools = {"cozy_scene_plan": self.cozy_scene_plan, "cozy_suggest_objects": self.cozy_suggest_objects,
                       "cozy_evidence": self.cozy_evidence, "get_primitives": self.get_primitives,
                       "instantiate_object": self.instantiate_object, "cozy_palette": self.cozy_palette}

    @classmethod
    def from_dir(cls, data_dir: str | Path, color_toolbox: ColorToolbox) -> "CozyToolbox":
        d = Path(data_dir)
        stats = json.loads((d / "cozy_color_stats.json").read_text(encoding="utf-8")) if (d / "cozy_color_stats.json").exists() else {}
        return cls(CozyMatrix.load(d / "cozy_matrix.npz"), color_toolbox, stats)

    # -- какой отклик считать «уютом» ---------------------------------------------------------------------------------
    def _response(self) -> tuple[str, str]:
        if self.m.has_evidence("cozy_human", 200):
            return "cozy_human", "survey"
        return "cozy_kw", "caption_keywords"

    @staticmethod
    def _check_room(room: str) -> None:
        if room not in vocab.ROOMS:
            raise ValueError(f"room: неизвестное значение {room!r}; допустимо {vocab.ROOMS}")

    @staticmethod
    def _check_objects(names) -> list[str]:
        names = list(names or [])
        bad = [n for n in names if n not in vocab.OBJECTS]
        if bad:
            raise ValueError(f"неизвестные объекты {bad}; допустимо {vocab.OBJECTS}")
        return names

    def dispatch(self, name: str, arguments: str | dict | None = None) -> dict:
        try:
            args = json.loads(arguments) if isinstance(arguments, str) and arguments.strip() else (arguments or {})
            if not isinstance(args, dict):
                raise ValueError("arguments должны быть JSON-объектом")
            fn = self._tools.get(name)
            if fn is None:
                return {"error": f"неизвестный инструмент {name!r}", "available": sorted(self._tools)}
            return fn(**args)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    # -- инструменты --------------------------------------------------------------------------------------------------
    def cozy_evidence(self, atoms: list[str]) -> dict:
        if not 1 <= len(atoms) <= 2:
            raise ValueError("нужен 1 или 2 атома")
        for a in atoms:
            if a not in vocab.ATOM_INDEX:
                raise ValueError(f"неизвестный атом {a!r}")
        resp, src = self._response()
        a, b = atoms[0], atoms[-1]
        c = self.m.cell(a, b, resp)
        c["label_source"] = src
        c["enough_support"] = c["n_eff_scans"] >= MIN_PAIR_SUPPORT
        c["provenance"] = PROVENANCE_COZY
        return c

    def cozy_suggest_objects(self, room: str, count: int = 8, avoid: list[str] | None = None, ascending: bool = False) -> dict:
        self._check_room(room)
        avoid = set(self._check_objects(avoid)) | ARCHITECTURE
        resp, src = self._response()
        ranked = [x for x in self.m.lifts_within(room, resp, group="object", top=64, ascending=ascending) if x["a"] not in avoid]
        if not ranked:
            return {"room": room, "error": "для этой комнаты недостаточно данных (n_eff_scans < порога)", "label_source": src}
        objs = []
        for x in ranked[:max(1, min(int(count), 20))]:
            rs = prim.recipes_for_atom(x["a"])
            objs.append({"object": x["a"], "lift_within_room": round(x["lift_within_context"], 4), "estimate": round(x["estimate"], 4),
                         "n_frames": x["n_frames"], "n_eff_scans": x["n_eff_scans"],
                         "recipes": [{"id": r.id, "size_m": list(r.size), "mount": r.mount, "tags": list(r.tags)} for r in rs]})
        room_cell = self.m.cell(room, room, resp)
        hints = {g: [{"atom": h["a"], "lift_within_room": round(h["lift_within_context"], 4), "n_eff_scans": h["n_eff_scans"]}
                     for h in self.m.lifts_within(room, resp, group=g, top=3, ascending=ascending)]
                 for g in ("light", "material", "quality")}
        return {"room": room, "response": resp, "label_source": src, "room_baseline": round(room_cell["estimate"], 4),
                "objects": objs, "atmosphere_hints": hints, "provenance": PROVENANCE_COZY}

    def get_primitives(self, object: str) -> dict:  # noqa: A002
        self._check_objects([object])
        rs = prim.recipes_for_atom(object)
        return {"object": object, "recipes": [prim.describe(r) for r in rs], "slot_roles": prim.SLOT_ROLE,
                "note": "Координаты локальные: начало в центре основания, +y вверх, лицо +z. Для настенных объектов mount_height — высота нижнего края."}

    def instantiate_object(self, object: str, x: float = 0.0, z: float = 0.0, rotation_y_deg: float = 0.0,  # noqa: A002
                           scale: float = 1.0, elevation: float | None = None, colors: dict | None = None) -> dict:
        self._check_objects([object])
        rs = prim.recipes_for_atom(object)
        parts = prim.instantiate(rs[0].id, x, z, rotation_y_deg, scale, colors, elevation)
        return {"object": object, "recipe": rs[0].id, "parts": parts}

    def cozy_palette(self, room: str) -> dict:
        self._check_room(room)
        chosen: dict[str, dict] = {}
        # perf S-02: кэш LAB-координат уже выбранных цветов.
        # Раньше для каждого кандидата × каждой роли вызывался Python-цикл с _delta
        # против already-chosen (до 6×8×5 = 240 _delta вызовов = ~720 delta_e в Python).
        # Теперь одна broadcasted delta_e_ok (8, M) в C через numpy.
        chosen_labs: list[np.ndarray] = []
        for role, q in ROLE_QUERIES.items():
            cand, used_relax = None, None
            query = dict(q)
            for relax in [None] + [r[0] for r in ROLE_FALLBACKS]:
                if relax:
                    query.pop(relax, None)
                used_relax = relax
                res = self.color.dispatch("find_colors", {**query, "count": 8, "min_delta_e": 0.03})
                if res.get("error"):
                    raise ValueError(f"{role}: {res['error']}")
                cands = res["candidates"]
                if not cands:
                    continue
                if chosen_labs:
                    # Пакетная проверка: delta_e от каждого кандидата ко всем выбранным.
                    # cand_lab shape (8, 3) → (8, 1, 3) для broadcasting
                    # chosen_lab shape (M, 3) → (1, M, 3)
                    # delta_e_ok broadcasting → (8, M), min по axis=1 → (8,) — мин. расстояние
                    cand_rgb = np.array([parse_color(c["hex"]) for c in cands], dtype=float)
                    cand_lab = rgb_to_oklab(cand_rgb)                       # (8, 3)
                    chosen_lab_arr = np.array(chosen_labs)                  # (M, 3)
                    # broadcasting: (8, 1, 3) vs (1, M, 3) → (8, M, 3) → norm axis=-1 → (8, M)
                    dists = delta_e_ok(cand_lab[:, None, :], chosen_lab_arr[None, :, :])  # (8, M)
                    min_dists = dists.min(axis=1)                            # (8,)
                    ok_mask = min_dists >= 0.05
                    if ok_mask.any():
                        # Первый подходящий кандидат (в порядке ранжирования от find_colors).
                        cand_idx = int(np.argmax(ok_mask))
                        cand = cands[cand_idx]
                else:
                    # Первый выбор — просто берём первый кандидат (проверять не с чем).
                    cand = cands[0]
                if cand:
                    break
            if cand is None:
                raise ValueError(f"не удалось подобрать цвет для роли {role!r}")
            prof = self.color.dispatch("describe_color", {"color": cand["hex"]})
            chosen[role] = {"hex": cand["hex"], "empathy": prof["empathy"]["score"], "empathy_label": prof["empathy"]["label"],
                            "intensity": prof["intensity"]["score"], "temperature": prof["synesthesia"]["temperature"]["word"],
                            "oklch": prof["oklch"], "constraint_relaxed": used_relax}
            # Сохраняем LAB для следующих ролей (broadcasting в batched delta_e).
            chosen_labs.append(rgb_to_oklab(np.array(parse_color(cand["hex"]), dtype=float)))
        slot_colors = {prim_slot: chosen[role]["hex"] for prim_slot, role in prim.SLOT_ROLE.items() if role in chosen}
        slot_colors.update({s: prim.DEFAULT_ROLE_COLORS[r] for s, r in prim.SLOT_ROLE.items() if r in prim.DEFAULT_ROLE_COLORS})
        check = self.color.dispatch("check_palette", {"colors": [v["hex"] for v in chosen.values()], "min_delta_e": 0.04})
        return {"room": room, "roles": chosen, "slot_colors": slot_colors,
                "defaults_not_from_color_matrix": sorted(prim.DEFAULT_ROLE_COLORS),
                "distinguishability_ok": check.get("distinguishability", {}).get("normal", {}).get("min_delta_e"),
                "empirical_hints": self._empirical_hints(room),
                "provenance": ("Роли wall/floor/textile_*/wood/light выбраны Color Matrix (prior-модель; запросы-эвристики 'тёплое, "
                               "малоинтенсивное'). Остальные слоты — нейтральные цвета материалов, не из матрицы. "
                               "empirical_hints — названия цветов из подписей GPT-4o, не измерения.")}

    def cozy_scene_plan(self, room: str, count: int = 8, avoid: list[str] | None = None, must_have: list[str] | None = None,
                        include_parts: bool = False) -> dict:
        must = self._check_objects(must_have)
        sug = self.cozy_suggest_objects(room, count=max(count, 3), avoid=avoid)
        if sug.get("error"):
            return sug
        objs = sug["objects"][:count]
        have = {o["object"] for o in objs}
        for m_ in must:
            if m_ not in have:
                objs.append({"object": m_, "forced": True, "recipes": [{"id": r.id, "size_m": list(r.size), "mount": r.mount,
                                                                        "tags": list(r.tags)} for r in prim.recipes_for_atom(m_)]})
        pal = self.cozy_palette(room)
        if include_parts:
            for o in objs:
                o["parts"] = [prim.describe(prim.RECIPES[r["id"]])["parts"] for r in o["recipes"]]
        return {"room": room, "objects": objs, "atmosphere_hints": sug["atmosphere_hints"], "palette": pal["roles"],
                "slot_colors": pal["slot_colors"], "empirical_color_hints": pal["empirical_hints"],
                "label_source": sug["label_source"], "how_to_build": "get_primitives/instantiate_object(object, colors=slot_colors)",
                "provenance": PROVENANCE_COZY + " " + pal["provenance"]}

    # -- вспомогательное ----------------------------------------------------------------------------------------------
    # perf C-01: импорты вынесены на уровень модуля (numpy, colorspace) — раньше реимпортировались при каждом вызове
    @staticmethod
    def _delta(h1: str, h2: str) -> float:
        return float(delta_e_ok(rgb_to_oklab(np.array(parse_color(h1), dtype=float)), rgb_to_oklab(np.array(parse_color(h2), dtype=float))))

    def _empirical_hints(self, room: str) -> list[dict]:
        by_room = (self.color_stats.get("by_room") or {}).get(room, {}).get("phrases", {})
        glob = self.color_stats.get("phrases", {})
        rows = [(p, v["lift_in_room"], v["n_frames"]) for p, v in by_room.items() if p in glob and v["n_frames"] >= 200]
        rows.sort(key=lambda r: -r[1])
        return [{"phrase": p, "hex": glob[p]["hex"], "lift_in_room": l, "n_frames": n,
                 "color_matrix": glob[p]["color_matrix"]} for p, l, n in rows[:5]]


class UnifiedToolbox:
    """Единая точка входа для агента: инструменты Color Matrix + Cozy Engine. Имена не пересекаются."""

    def __init__(self, color: ColorToolbox, cozy: CozyToolbox):
        self.color, self.cozy = color, cozy
        self.schemas = COLOR_SCHEMAS + COZY_SCHEMAS
        assert len({s["function"]["name"] for s in self.schemas}) == len(self.schemas)

    def dispatch(self, name: str, arguments: str | dict | None = None) -> dict:
        target = self.cozy if name in self.cozy._tools else self.color
        return target.dispatch(name, arguments)
