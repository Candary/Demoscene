"""Каталог эффектов. Эффект = шейдер + манифест (контракт интерфейса). Новый эффект не требует правки C++:
положите <id>.effect.json (+ <id>.frag) в каталог эффектов — менеджер и GLM увидят его, его параметры и допустимые диапазоны.

Виды (kind):
  scene       — рисует картинку сама (0 входов);
  overlay     — рисует поверх (титры, вспышка), 0 входов, обычно direct_blend;
  transition  — 2 входа (A, B) и прогресс 0..1;
  post        — 1 вход (всё, что ниже по слоям), пост-обработка;
  event       — без рендера: управляющее событие (finish).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("scene", "overlay", "transition", "post", "event")
TYPES = {"float": 1, "int": 1, "bool": 1, "vec2": 2, "vec3": 3, "vec4": 4, "farray": 0}   # farray — константный массив float (данные, не выражение)
INPUTS = {"scene": 0, "overlay": 0, "transition": 2, "post": 1, "event": 0}

# Униформы, которые движок задаёт сам (их нельзя назначать в map): время, прогресс, аудио, служебное.
STANDARD_UNIFORMS = {
    "uTime": "секунды с начала показа клипа (>= 0)", "uClipTime": "секунды от номинального начала клипа (может быть < 0 на подводке)",
    "uProgress": "прогресс клипа 0..1 (у перехода — с применённой кривой)", "uGlobalTime": "время демо, с",
    "uResolution": "vec2, пиксели", "uSeed": "детерминированное зерно клипа (float)",
    "uBeat": "дробный номер доли", "uBeatPhase": "фаза доли 0..1", "uBarPhase": "фаза такта 0..1", "uEnergy": "энергия музыки 0..1",
}


@dataclass(frozen=True)
class UniformSpec:
    name: str
    type: str = "float"
    default: tuple | float | int | bool | None = None
    min: float | None = None
    max: float | None = None
    space: str = "srgb"        # для vec3-цветов: srgb | linear (перевод делает baker)
    role: str | None = None    # 'color' — vec3 это цвет
    doc: str = ""
    required: bool = False
    bind: str | dict | None = None   # привязка по умолчанию: выражение от атомов, 'palette.<роль>' или {color: ...}; клип переопределяет через map

    @property
    def size(self) -> int:
        return TYPES[self.type]


@dataclass(frozen=True)
class Effect:
    id: str
    kind: str
    uniforms: dict[str, UniformSpec] = field(default_factory=dict)
    shader: str | None = None
    suits: dict = field(default_factory=dict)      # подсказки подбора: {"feel": [...], "energy": [lo, hi]}
    cost: int = 1                                  # 1..5 — условная нагрузка на GPU
    direct_blend: bool = False                     # можно рисовать прямо в накопитель с GL-смешиванием (без своего FBO)
    reads_background: bool = False                 # читает то, что под ним (требует пинг-понг)
    text: bool = False                             # рисует текст (линт проверяет контраст)
    uses_random: bool = False
    doc: str = ""
    tags: tuple = ()
    atoms: dict = field(default_factory=dict)      # значения атомов по умолчанию (клип/look их переопределяют)

    @property
    def inputs(self) -> int:
        return INPUTS[self.kind]

    def describe(self) -> dict:
        return {"id": self.id, "kind": self.kind, "doc": self.doc, "cost": self.cost, "suits": self.suits,
                "direct_blend": self.direct_blend, "text": self.text, "tags": list(self.tags), "atoms": self.atoms,
                "uniforms": {n: {"type": u.type, "default": u.default, "min": u.min, "max": u.max, "role": u.role,
                                 "space": u.space if u.type == "vec3" else None, "required": u.required, "bind": u.bind, "doc": u.doc}
                             for n, u in self.uniforms.items()}}


def _u(name, type="float", default=None, min=None, max=None, role=None, doc="", required=False, space="srgb", bind=None):
    if isinstance(default, list):
        default = tuple(default)
    return UniformSpec(name, type, default, min, max, space, role, doc, required, bind)


def effect_from_dict(d: dict) -> Effect:
    if d.get("kind") not in KINDS:
        raise ValueError(f"effect {d.get('id')!r}: kind должен быть одним из {KINDS}")
    uni = {}
    for name, spec in (d.get("uniforms") or {}).items():
        t = spec.get("type", "float")
        if t not in TYPES:
            raise ValueError(f"effect {d['id']!r}, uniform {name!r}: неизвестный тип {t!r}")
        uni[name] = _u(name, t, spec.get("default"), spec.get("min"), spec.get("max"), spec.get("role"), spec.get("doc", ""),
                       bool(spec.get("required", False)), spec.get("space", "srgb"), spec.get("bind"))
        if uni[name].default is not None and t != "farray":
            n = len(uni[name].default) if isinstance(uni[name].default, tuple) else 1
            if n != TYPES[t]:
                raise ValueError(f"effect {d['id']!r}, uniform {name!r}: default не соответствует типу {t}")
    return Effect(d["id"], d["kind"], uni, d.get("shader"), d.get("suits", {}), int(d.get("cost", 1)), bool(d.get("direct_blend", False)),
                  bool(d.get("reads_background", False)), bool(d.get("text", False)), bool(d.get("uses_random", False)),
                  d.get("doc", ""), tuple(d.get("tags", [])), dict(d.get("atoms", {})))


_COLOR = dict(type="vec3", role="color")
BUILTIN: list[dict] = [
    # --- переходы (контракт: шейдер получает uA, uB, uProgress)
    {"id": "cut", "kind": "transition", "doc": "Жёсткая склейка (без шейдера).", "cost": 1},
    {"id": "crossfade", "kind": "transition", "doc": "Плавное смешивание A и B.", "cost": 1},
    {"id": "fade_to_black", "kind": "transition", "doc": "A гаснет до цвета, затем B проявляется из него.", "cost": 1,
     "uniforms": {"uColor": {**_COLOR, "default": [0, 0, 0]}}},
    {"id": "wipe", "kind": "transition", "doc": "Шторка под углом с мягким краем.", "cost": 1,
     "uniforms": {"uAngle": {"type": "float", "default": 0.0, "min": -3.1416, "max": 3.1416, "doc": "радианы"},
                  "uSoftness": {"type": "float", "default": 0.05, "min": 0, "max": 1}}},
    {"id": "flash", "kind": "transition", "doc": "Вспышка на стыке: A -> белое -> B.", "cost": 1,
     "uniforms": {"uColor": {**_COLOR, "default": [1, 1, 1]}, "uPeak": {"type": "float", "default": 1.0, "min": 0, "max": 2}}},
    {"id": "glitch", "kind": "transition", "doc": "Цифровой сбой: блочные смещения и RGB-расщепление.", "cost": 2, "uses_random": True,
     "uniforms": {"uAmount": {"type": "float", "default": 0.5, "min": 0, "max": 1}}},
    # --- пост-обработка
    {"id": "bloom", "kind": "post", "doc": "Свечение ярких областей.", "cost": 3,
     "uniforms": {"uThreshold": {"type": "float", "default": 0.8, "min": 0, "max": 2}, "uIntensity": {"type": "float", "default": 0.6, "min": 0, "max": 3},
                  "uRadius": {"type": "float", "default": 1.0, "min": 0.1, "max": 4}}},
    {"id": "grain", "kind": "post", "doc": "Плёночное зерно.", "cost": 1, "uses_random": True,
     "uniforms": {"uAmount": {"type": "float", "default": 0.05, "min": 0, "max": 0.5}}},
    {"id": "vignette", "kind": "post", "doc": "Затемнение краёв.", "cost": 1,
     "uniforms": {"uStrength": {"type": "float", "default": 0.4, "min": 0, "max": 1}, "uSoftness": {"type": "float", "default": 0.5, "min": 0.05, "max": 1}}},
    {"id": "chromatic_aberration", "kind": "post", "doc": "Хроматическая аберрация к краям.", "cost": 1,
     "uniforms": {"uAmount": {"type": "float", "default": 0.003, "min": 0, "max": 0.05}}},
    # --- события
    {"id": "finish", "kind": "event", "doc": "Конец показа: движок останавливает рендер и завершает работу.", "cost": 1},
]


class EffectCatalog:
    def __init__(self):
        self.effects: dict[str, Effect] = {}
        self.dir: Path | None = None
        for d in BUILTIN:
            self.add(effect_from_dict(d))

    def add(self, e: Effect) -> None:
        if e.id in self.effects:
            raise ValueError(f"эффект {e.id!r} уже определён")
        self.effects[e.id] = e

    @classmethod
    def from_dir(cls, path: str | Path | None) -> "EffectCatalog":
        cat = cls()
        if path:
            p = Path(path)
            cat.dir = p
            for f in sorted(p.glob("*.effect.json")):
                cat.add(effect_from_dict(json.loads(f.read_text(encoding="utf-8"))))
        return cat

    def get(self, id_: str) -> Effect:
        if id_ not in self.effects:
            raise KeyError(f"неизвестный эффект {id_!r}; доступно: {sorted(self.effects)}")
        return self.effects[id_]

    def search(self, kind: str | None = None, feel: str | None = None, max_cost: int | None = None, text: str | None = None) -> list[Effect]:
        out = []
        for e in self.effects.values():
            if kind and e.kind != kind:
                continue
            if feel and feel not in e.suits.get("feel", []):
                continue
            if max_cost is not None and e.cost > max_cost:
                continue
            if text and text.lower() not in (e.id + " " + e.doc + " " + " ".join(e.tags)).lower():
                continue
            out.append(e)
        return out

    def missing_shaders(self) -> list[str]:
        """Эффекты, у которых объявлен shader, но файла нет (нужен каталог на диске)."""
        if self.dir is None:
            return []
        return sorted(e.id for e in self.effects.values() if e.shader and not (self.dir / e.shader).exists())
