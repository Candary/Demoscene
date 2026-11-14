"""Эффекты. Частицы считаются в закрытой форме от (t, seed) — без интегрирования.

Следствие: перемотка, offline-рендер и повтор дают идентичный результат,
а история вызовов не влияет на кадр.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .core import MotusError, QueryError, Registry
from .mathx import TAU, Vec3, translation
from .track import Kind, Track, coerce
from .anim import ProcCall


@dataclass(frozen=True)
class ParamSpec:
    name: str
    type: str = "float"          # float | int | vec3
    default: Any = 0.0
    low: Optional[float] = None
    high: Optional[float] = None

    def clean(self, value: Any) -> Any:
        if self.type == "int":
            v = int(value)
        elif self.type == "vec3":
            v = coerce(Kind.VEC3, value)
        else:
            v = float(value)
        if self.low is not None and self.type != "vec3":
            v = max(self.low, v)
        if self.high is not None and self.type != "vec3":
            v = min(self.high, v)
        return v


@dataclass
class EffectSpec:
    name: str
    kind: str                    # emitter | post | surface
    params: Tuple[ParamSpec, ...] = ()
    glsl: str = ""
    proc: str = ""               # для surface: какая процедура модифицирует param
    channel: str = ""

    def defaults(self) -> Dict[str, Any]:
        return {p.name: p.default for p in self.params}

    def clean(self, values: Dict[str, Any]) -> Dict[str, Any]:
        known = {p.name: p for p in self.params}
        for k in values:
            if k not in known:
                raise QueryError(f"эффект '{self.name}' не знает параметр '{k}'",
                                 hints=sorted(known))
        out = self.defaults()
        for k, v in values.items():
            out[k] = known[k].clean(v)
        return out


EFFECTS = Registry("effect")

EFFECTS.add("burst", EffectSpec("burst", "emitter", (
    ParamSpec("speed", "float", 6.0, 0.0),
    ParamSpec("spread", "float", 0.35, 0.0, 1.0),
    ParamSpec("life", "float", 1.4, 0.05),
    ParamSpec("gravity", "float", 4.5),
    ParamSpec("size", "float", 0.06, 0.001),
    ParamSpec("shrink", "float", 0.7, 0.0, 1.0),
    ParamSpec("fade", "float", 1.6, 0.1),
    ParamSpec("color_a", "vec3", (1.0, 0.85, 0.4)),
    ParamSpec("color_b", "vec3", (1.0, 0.25, 0.1)),
), glsl="particle"))

EFFECTS.add("fountain", EffectSpec("fountain", "emitter", (
    ParamSpec("speed", "float", 5.0, 0.0),
    ParamSpec("spread", "float", 0.25, 0.0, 1.0),
    ParamSpec("life", "float", 1.1, 0.05),
    ParamSpec("gravity", "float", 9.0),
    ParamSpec("size", "float", 0.04, 0.001),
    ParamSpec("shrink", "float", 0.4, 0.0, 1.0),
    ParamSpec("fade", "float", 1.2, 0.1),
    ParamSpec("color_a", "vec3", (0.6, 0.9, 1.0)),
    ParamSpec("color_b", "vec3", (0.1, 0.3, 0.9)),
), glsl="particle"))

EFFECTS.add("spiral", EffectSpec("spiral", "emitter", (
    ParamSpec("radius", "float", 1.2, 0.0),
    ParamSpec("turns", "float", 3.0),
    ParamSpec("rise", "float", 2.0),
    ParamSpec("life", "float", 1.8, 0.05),
    ParamSpec("size", "float", 0.05, 0.001),
    ParamSpec("shrink", "float", 0.5, 0.0, 1.0),
    ParamSpec("fade", "float", 1.0, 0.1),
    ParamSpec("color_a", "vec3", (0.4, 1.0, 0.9)),
    ParamSpec("color_b", "vec3", (0.9, 0.3, 1.0)),
), glsl="particle"))

EFFECTS.add("shockwave", EffectSpec("shockwave", "post", (
    ParamSpec("radius", "float", 0.4, 0.0, 4.0),
    ParamSpec("width", "float", 0.08, 0.001, 1.0),
    ParamSpec("strength", "float", 0.05, 0.0, 1.0),
    ParamSpec("center", "vec3", (0.5, 0.5, 0.0)),
), glsl="post"))

EFFECTS.add("vignette", EffectSpec("vignette", "post", (
    ParamSpec("amount", "float", 0.35, 0.0, 1.0),
), glsl="post"))

EFFECTS.add("grain", EffectSpec("grain", "post", (
    ParamSpec("amount", "float", 0.04, 0.0, 1.0),
), glsl="post"))

EFFECTS.add("pulse", EffectSpec("pulse", "surface", (), proc="pulse",
                                channel="param.glow"))


@dataclass
class Emitter:
    iid: int
    effect: str
    origin: Vec3
    start: float
    duration: float
    count: int
    seed: int
    params: Dict[str, Any]
    attach: Optional[str] = None

    def active(self, t: float) -> bool:
        return self.start <= t < self.start + self.duration + self.params.get("life", 1.0)


@dataclass
class PostFx:
    effect: str
    start: float
    duration: float
    params: Dict[str, Any]

    def active(self, t: float) -> bool:
        return self.start <= t and (self.duration <= 0.0 or t < self.start + self.duration)

    def evaluate(self, t: float) -> Dict[str, Any]:
        out = {}
        for k, v in self.params.items():
            out[k] = v.sample(t - self.start) if isinstance(v, (Track, ProcCall)) else v
        return out


@dataclass
class Field:
    """GPU-ready результат: pos(N,3) f32, color(N,4) f32, size(N) f32."""
    pos: Any
    color: Any
    size: Any
    alive: int

    def interleaved(self) -> bytes:
        """pos3 + rgba4 + size1 = 8 float32 на частицу, stride 32 байта."""
        import numpy as np
        n = self.pos.shape[0]
        buf = np.empty((n, 8), dtype=np.float32)
        buf[:, 0:3] = self.pos
        buf[:, 3:7] = self.color
        buf[:, 7] = self.size
        return buf.tobytes()


def _np():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise MotusError("для частиц нужен numpy: pip install numpy") from exc
    return np


def _mix_np(np, x):
    m = np.uint64(0xFFFFFFFF)
    x = x & m
    x = x ^ (x >> np.uint64(16))
    x = (x * np.uint64(0x7FEB352D)) & m
    x = x ^ (x >> np.uint64(15))
    x = (x * np.uint64(0x846CA68B)) & m
    x = x ^ (x >> np.uint64(16))
    return x


def compute_field(em: Emitter, t: float) -> Field:
    """Чистая функция (em, t). Совпадает с scalar-версией mathx.hash01 бит-в-бит."""
    np = _np()
    n = max(0, int(em.count))
    i = np.arange(n, dtype=np.uint64)
    base = _mix_np(np, np.uint64(em.seed & 0xFFFFFFFF))

    def h(k: int):
        v = _mix_np(np, base ^ _mix_np(np, i + np.uint64(0x9E3779B9 + k)))
        return v.astype(np.float64) / 4294967295.0

    p = em.params
    life = np.maximum(1e-3, p.get("life", 1.0)) * (0.7 + 0.6 * h(5))
    if em.effect == "fountain":
        birth = em.start + h(6) * max(1e-6, em.duration)
    else:
        birth = em.start + h(6) * p.get("spread", 0.0) * 0.25
    age = t - birth
    k = np.clip(age / life, 0.0, 1.0)
    live = (age >= 0.0) & (age < life)

    if em.effect == "spiral":
        ang = TAU * (h(1) + p["turns"] * k)
        rad = p["radius"] * (0.25 + 0.75 * h(2)) * (0.3 + 0.7 * k)
        pos = np.stack([rad * np.cos(ang), p["rise"] * k, rad * np.sin(ang)], axis=1)
    else:
        cos_t = 2.0 * h(1) - 1.0
        if em.effect == "fountain":
            cos_t = np.abs(cos_t) * (1.0 - p.get("spread", 0.25)) + p.get("spread", 0.25)
        sin_t = np.sqrt(np.maximum(0.0, 1.0 - cos_t * cos_t))
        phi = TAU * h(2)
        d = np.stack([sin_t * np.cos(phi), cos_t, sin_t * np.sin(phi)], axis=1)
        speed = p["speed"] * (0.55 + 0.9 * h(3))
        g = -float(p.get("gravity", 0.0))
        a = np.maximum(age, 0.0)
        pos = d * (speed * a)[:, None]
        pos[:, 1] += 0.5 * g * a * a

    pos = pos + np.asarray(em.origin, dtype=np.float64)[None, :]
    ca = np.asarray(p.get("color_a", (1.0, 1.0, 1.0)), dtype=np.float64)
    cb = np.asarray(p.get("color_b", (1.0, 1.0, 1.0)), dtype=np.float64)
    rgb = ca[None, :] * (1.0 - k)[:, None] + cb[None, :] * k[:, None]
    alpha = np.power(1.0 - k, p.get("fade", 1.0)) * live
    color = np.concatenate([rgb, alpha[:, None]], axis=1)
    size = np.full(n, p.get("size", 0.05)) * (1.0 - p.get("shrink", 0.0) * k) * live
    return Field(pos.astype(np.float32), color.astype(np.float32),
                 size.astype(np.float32), int(live.sum()))


class EffectSystem:
    def __init__(self, max_particles: int = 200_000):
        self.max_particles = int(max_particles)
        self.emitters: List[Emitter] = []
        self.posts: List[PostFx] = []
        self._next = 0

    def spawn(self, effect: str, *, origin=(0.0, 0.0, 0.0), start: float = 0.0,
              duration: float = 2.0, count: int = 400, seed: int = 1,
              attach: Optional[str] = None, **params) -> Emitter:
        spec = EFFECTS.get(effect)
        if spec.kind != "emitter":
            raise QueryError(f"эффект '{effect}' не эмиттер (kind={spec.kind})")
        count = max(0, min(int(count), self.max_particles))
        em = Emitter(self._next, effect, coerce(Kind.VEC3, origin), float(start),
                     max(0.0, float(duration)), count, int(seed), spec.clean(params), attach)
        self._next += 1
        self.emitters.append(em)
        return em

    def post(self, effect: str, *, start: float = 0.0, duration: float = 0.0,
             **params) -> PostFx:
        spec = EFFECTS.get(effect)
        if spec.kind != "post":
            raise QueryError(f"эффект '{effect}' не post (kind={spec.kind})")
        fx = PostFx(effect, float(start), max(0.0, float(duration)), spec.clean(params))
        self.posts.append(fx)
        return fx

    def active_emitters(self, t: float) -> List[Emitter]:
        return [e for e in self.emitters if e.active(t)]

    def active_posts(self, t: float) -> List[PostFx]:
        return [p for p in self.posts if p.active(t)]