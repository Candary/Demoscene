"""Инструменты Scene Manager для GLM (function calling) и общий набор с Color Matrix и Cozy Engine.

Дизайн набора: мало инструментов, но каждый даёт «всё нужное за один вызов».
  Смотреть:  show_overview, resolve_at, lint, list_effects, describe_effect
  Менять:    edit_show (пакет операций, атомарно), history (undo/redo)
  Помощники: analyze_audio, suggest_palette, suggest_transitions, build_cozy_asset
  Собрать:   bake
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapters import check_layout, cozy_asset
from .session import ShowSession

OPS_DOC = (
    "Операции (поле op): set_meta{values}, set_audio{values}, set_marker{name, time | bar[,beat]}, remove_marker{name}, "
    "add_track{id[,order,sparse]}, remove_track{id}, set_palette{name, colors{роль:#hex}[,source]}, set_look{name[,atoms,palette]}, "
    "set_asset{name,data}, add_clip{clip}, update_clip{id, patch (JSON merge-patch: объекты сливаются, null удаляет ключ)}, "
    "remove_clip{id[,cascade]}, move_clip{id, start (якорь)[,ripple]}, lock{id}, unlock{id}, accept{id | all:true}. "
    "Заблокированный клип правится только с force=true. Весь пакет применяется атомарно."
)
CLIP_DOC = (
    "Клип: {id, track, kind: scene|overlay|post|event|transition, effect, start, duration | end, atoms, map, palette, look, opacity, blend, "
    "curves через atoms:{имя:{keys:[[t,v,ease?],...]}}, status: accepted|proposed, locked}. Якорь времени: число | {marker,offset} | "
    "{bar,beat?,offset?} | {end_of|after: id,offset?} | {start_of|with: id,offset?}; offset_beats/offset_bars — в музыкальных единицах. "
    "duration: число | {beats:n} | {bars:n} | {until: якорь}. Переход: {id, kind:'transition', effect, between:[A,B], duration, align: center|end|start, curve}."
)

_T = lambda name, desc, props=None, req=None: {"type": "function", "function": {"name": name, "description": desc, "parameters": {
    "type": "object", "properties": props or {}, **({"required": req} if req else {})}}}  # noqa: E731

SHOW_SCHEMAS: list[dict] = [
    _T("show_overview", "Раскадровка показа (дорожки, клипы со временем и тактами, секции музыки, замечания) и сводка: длительность, память FBO, число клипов. "
       "Вызывайте после каждой серии правок, чтобы «увидеть» результат.", {"strict": {"type": "boolean", "default": False}}),
    _T("edit_show", "Пакет правок показа, применяется атомарно (ошибка в любой операции откатывает весь пакет). Возвращает новые замечания. " + OPS_DOC + " " + CLIP_DOC,
       {"ops": {"type": "array", "items": {"type": "object", "properties": {"op": {"type": "string", "enum": [
           "set_meta", "set_audio", "set_marker", "remove_marker", "add_track", "remove_track", "set_palette", "set_look", "set_asset",
           "add_clip", "update_clip", "remove_clip", "move_clip", "lock", "unlock", "accept"]}}, "required": ["op"], "additionalProperties": True}},
        "dry_run": {"type": "boolean", "default": False, "description": "Только проверить, ничего не менять."},
        "require_valid": {"type": "boolean", "default": False, "description": "Отклонить пакет, если он порождает ошибки."}}, ["ops"]),
    _T("lint", "Полная проверка показа: ошибки, предупреждения, справка. strict=true: клипы status=proposed считаются ошибкой (как при финальной сборке).",
       {"strict": {"type": "boolean", "default": False}}),
    _T("resolve_at", "Что на экране в момент t: активные клипы, их окна, значения uniform'ов, проходы рендера и число FBO; такт и фаза доли.",
       {"t": {"type": "number"}}, ["t"]),
    _T("list_effects", "Каталог доступных эффектов (сцены, оверлеи, переходы, post, события) с параметрами и допустимыми диапазонами. "
       "Используйте ТОЛЬКО эти эффекты и uniform'ы.",
       {"kind": {"type": "string", "enum": ["scene", "overlay", "transition", "post", "event"]}, "feel": {"type": "string", "description": "empathy-метка Color Matrix, для которой эффект подходит"},
        "max_cost": {"type": "integer"}, "text": {"type": "string", "description": "поиск по id/описанию/тегам"}}),
    _T("describe_effect", "Полный манифест эффекта: uniform'ы (тип, диапазон, значение по умолчанию, привязка bind), подсказки suits, стоимость.", {"id": {"type": "string"}}, ["id"]),
    _T("history", "Отмена и повтор правок.", {"action": {"type": "string", "enum": ["undo", "redo"]}}, ["action"]),
    _T("analyze_audio", "Анализ MP3/WAV: темп, первая доля, энергия, границы секций, предложенные маркеры (drop/breakdown/build). Результат — ОЦЕНКА: "
       "проверьте сетку на слух. add_markers=true записывает маркеры в показ.",
       {"path": {"type": "string"}, "add_markers": {"type": "boolean", "default": True}, "beats_per_bar": {"type": "integer", "default": 4}}, ["path"]),
    _T("suggest_palette", "Палитра ролей primary/accent/bg/text из Color Matrix для настроения feel (anxiety|tension|neutral|warmth|delight) с проверкой контраста. "
       "Это предложение: закрепите его командой edit_show/set_palette. ВНИМАНИЕ: feel — эмоциональная метка Color Matrix (prior), а НЕ температура цвета: feel=warmth может вернуть синий. Для тёплых/холодных тонов задайте temperature.",
       {"feel": {"type": "string", "enum": ["anxiety", "tension", "neutral", "warmth", "delight"]}, "background_hint": {"type": "string", "enum": ["dark", "light"], "default": "dark"},
        "temperature": {"type": "string", "enum": ["warm", "cool"], "description": "необязательно: ограничить тоном (тёплые/холодные)"}}, ["feel"]),
    _T("suggest_transitions", "Кандидаты перехода между сценами A и B по перепаду энергии музыки на стыке (эвристика; решает автор).",
       {"a": {"type": "string"}, "b": {"type": "string"}}, ["a", "b"]),
    _T("build_cozy_asset", "Собрать ассет из примитивов Cozy Engine по расстановке объектов (для SDF-эффекта через uniform-массив) и сохранить в показ. "
       "Проверяет границы комнаты и пересечения. Цвета слотов берите из cozy_palette(...).slot_colors.",
       {"name": {"type": "string"},
        "placements": {"type": "array", "items": {"type": "object", "properties": {
            "object": {"type": "string"}, "recipe": {"type": "string"}, "x": {"type": "number"}, "z": {"type": "number"},
            "rotation_y_deg": {"type": "number"}, "scale": {"type": "number"}, "elevation": {"type": "number"}}, "required": ["object"]}},
        "slot_colors": {"type": "object", "additionalProperties": {"type": "string"}},
        "room_size": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2, "description": "[ширина, глубина] в метрах"}},
       ["name", "placements"]),
    _T("bake", "Финальная сборка: demo.baked.json и demo.smt для рантайма. strict=true (по умолчанию) требует, чтобы все клипы были утверждены (accepted).",
       {"out_dir": {"type": "string"}, "name": {"type": "string", "default": "demo"}, "strict": {"type": "boolean", "default": True}}),
]


class ShowToolbox:
    def __init__(self, session: ShowSession, autosave: str | Path | None = None):
        self.s = session
        self.autosave = Path(autosave) if autosave else None
        self._tools = {
            "show_overview": self.show_overview, "edit_show": self.edit_show, "lint": self.lint, "resolve_at": self.resolve_at,
            "list_effects": self.list_effects, "describe_effect": self.describe_effect, "history": self.history,
            "analyze_audio": self.analyze_audio, "suggest_palette": self.suggest_palette, "suggest_transitions": self.suggest_transitions,
            "build_cozy_asset": self.build_cozy_asset, "bake": self.bake,
        }

    def _save(self) -> None:
        if self.autosave:
            self.s.save(self.autosave)

    def dispatch(self, name: str, arguments: str | dict | None = None) -> dict:
        try:
            args = json.loads(arguments) if isinstance(arguments, str) and arguments.strip() else (arguments or {})
            if not isinstance(args, dict):
                raise ValueError("arguments должны быть JSON-объектом")
            fn = self._tools.get(name)
            if fn is None:
                return {"error": f"неизвестный инструмент {name!r}", "available": sorted(self._tools)}
            return fn(**args)
        except (ValueError, TypeError, KeyError, FileNotFoundError, RuntimeError, json.JSONDecodeError) as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    # ---- смотреть -----------------------------------------------------------------------------------------------------
    def show_overview(self, strict: bool = False) -> dict:
        res = self.s.compile(strict)
        st = self.s.stats()
        return {"storyboard": self.s.storyboard(strict), "stats": st,
                "issues": {"errors": len(res.errors), "warnings": len([i for i in res.issues if i.level == "warning"])}}

    def lint(self, strict: bool = False) -> dict:
        return self.s.lint(strict)

    def resolve_at(self, t: float) -> dict:
        return self.s.resolve_at(float(t))

    def list_effects(self, kind: str | None = None, feel: str | None = None, max_cost: int | None = None, text: str | None = None) -> dict:
        es = self.s.catalog.search(kind, feel, max_cost, text)
        return {"count": len(es), "effects": [{"id": e.id, "kind": e.kind, "doc": e.doc, "cost": e.cost, "suits": e.suits, "text": e.text or None,
                                               "uniforms": {n: {"type": u.type, "range": [u.min, u.max] if (u.min is not None or u.max is not None) else None,
                                                                "default": u.default, "bind": u.bind, "required": u.required or None} for n, u in e.uniforms.items()}}
                                              for e in es]}

    def describe_effect(self, id: str) -> dict:  # noqa: A002
        return self.s.catalog.get(id).describe()

    # ---- менять -------------------------------------------------------------------------------------------------------
    def edit_show(self, ops: list[dict], dry_run: bool = False, require_valid: bool = False) -> dict:
        r = self.s.edit(ops, dry_run=dry_run, require_valid=require_valid)
        if r.get("ok") and not dry_run:
            self._save()
        return r

    def history(self, action: str) -> dict:
        r = self.s.undo() if action == "undo" else self.s.redo()
        if r.get("ok"):
            self._save()
        return r

    # ---- помощники ----------------------------------------------------------------------------------------------------
    def analyze_audio(self, path: str, add_markers: bool = True, beats_per_bar: int = 4) -> dict:
        r = self.s.import_audio(path, add_markers, beats_per_bar)
        self._save()
        r["sections"] = [{k: s[k] for k in ("start", "bars", "mean_energy", "label") if k in s} for s in r["sections"]]
        return r

    def suggest_palette(self, feel: str, background_hint: str = "dark", temperature: str | None = None) -> dict:
        return self.s.suggest_palette(feel, background_hint, temperature)

    def suggest_transitions(self, a: str, b: str) -> dict:
        return self.s.suggest_transitions(a, b)

    def build_cozy_asset(self, name: str, placements: list[dict], slot_colors: dict | None = None, room_size: list[float] | None = None) -> dict:
        lay = check_layout(placements, tuple(room_size) if room_size else None)
        asset = cozy_asset(placements, slot_colors)
        r = self.s.edit([{"op": "set_asset", "name": name, "data": asset}])
        if r.get("ok"):
            self._save()
        return {"ok": r.get("ok"), "asset": name, "parts": asset["count"], "floats": len(asset["floats"]), "objects": asset["objects"],
                "layout_check": lay, "use": f'map: {{"<uniform>": {{"asset": "{name}"}}}} у uniform типа farray'}

    def bake(self, out_dir: str | None = None, name: str = "demo", strict: bool = True) -> dict:
        out = out_dir or str(self.s.base_dir or ".")
        return self.s.bake(out, name, strict)


class FullToolbox:
    """Все инструменты проекта для одного агента: Color Matrix + Cozy Engine + Scene Manager. Имена не пересекаются."""

    def __init__(self, show: ShowToolbox, color=None, cozy=None):
        from color_matrix_python.tools import TOOL_SCHEMAS as COLOR_SCHEMAS   # noqa: PLC0415
        self.show, self.color, self.cozy = show, color, cozy
        self.schemas = list(SHOW_SCHEMAS)
        self._route: dict[str, Any] = {n: show for n in show._tools}
        if color is not None:
            self.schemas += COLOR_SCHEMAS
            self._route.update({s["function"]["name"]: color for s in COLOR_SCHEMAS})
        if cozy is not None:
            from cozy_engine.tools import COZY_SCHEMAS   # noqa: PLC0415
            self.schemas += COZY_SCHEMAS
            self._route.update({n: cozy for n in cozy._tools})
        names = [s["function"]["name"] for s in self.schemas]
        assert len(names) == len(set(names)), "пересечение имён инструментов"

    def dispatch(self, name: str, arguments: str | dict | None = None) -> dict:
        t = self._route.get(name)
        if t is None:
            return {"error": f"неизвестный инструмент {name!r}", "available": sorted(self._route)}
        return t.dispatch(name, arguments)
