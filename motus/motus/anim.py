"""Каналы, процедуры и биндинги. Один механизм для keyframe- и процедурной анимации."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .core import MotusError, QueryError, Registry
from .mathx import (QID, TAU, ONE, ZERO, Quat, Vec3, clamp01, hash_sym, qaxis, qmul,
                    qnorm, qslerp, vadd, vscale, vsub)
from .scene import Entity, Scene, Transform
from .track import IDENTITY, Kind, Track, blend_value, coerce


class Mode(Enum):
    REPLACE = "replace"
    ADD = "add"
    MUL = "mul"

    @property
    def phase(self) -> int:
        return _PHASE[self]


_PHASE = {Mode.REPLACE: 0, Mode.ADD: 1, Mode.MUL: 2}
LOOPS = ("hold", "repeat", "pingpong", "once")


# ---------------------------------------------------------------- каналы
@dataclass
class ChannelSpec:
    name: str
    kind: Kind
    get: Callable[[Transform], Any]
    put: Callable[[Transform, Any], None]
    add_identity: Any
    allow_mul: bool = False
    is_param: bool = False
    key: str = ""


CHANNELS = Registry("channel")


def _rot_put(tr: Transform, v: Quat) -> None:
    tr.rot = qnorm(v)


CHANNELS.add("position", ChannelSpec("position", Kind.VEC3,
             lambda t: t.pos, lambda t, v: setattr(t, "pos", v), ZERO))
for _i, _ax in enumerate("xyz"):
    def _mk(i: int):
        def put(tr: Transform, v: float) -> None:
            p = list(tr.pos)
            p[i] = v
            tr.pos = (p[0], p[1], p[2])
        return put
    CHANNELS.add(f"position.{_ax}", ChannelSpec(f"position.{_ax}", Kind.FLOAT,
                 (lambda i: (lambda t: t.pos[i]))(_i), _mk(_i), 0.0))
CHANNELS.add("rotation", ChannelSpec("rotation", Kind.QUAT,
             lambda t: t.rot, _rot_put, QID))
CHANNELS.add("scale", ChannelSpec("scale", Kind.VEC3,
             lambda t: t.scale, lambda t, v: setattr(t, "scale", v), ONE, allow_mul=True))
CHANNELS.add("scale.uniform", ChannelSpec("scale.uniform", Kind.FLOAT,
             lambda t: t.scale[0], lambda t, v: setattr(t, "scale", (v, v, v)), 0.0,
             allow_mul=True))

_PARAM_CACHE: Dict[Tuple[str, str], ChannelSpec] = {}


def resolve_channel(name: str, kind: Optional[Kind] = None) -> ChannelSpec:
    """`param.<имя>` — произвольный пользовательский канал (цвет, свечение, что угодно)."""
    if not name.startswith("param."):
        spec = CHANNELS.get(name)
        if kind is not None and kind is not spec.kind:
            raise QueryError(f"канал '{name}' ожидает {spec.kind.value}, получен {kind.value}")
        return spec
    key = name[6:]
    if not key:
        raise QueryError("канал 'param.' требует имени")
    k = kind or Kind.FLOAT
    ck = (key, k.value)
    spec = _PARAM_CACHE.get(ck)
    if spec is None:
        spec = ChannelSpec(name, k, lambda t: IDENTITY[k], lambda t, v: None,
                           IDENTITY[k], allow_mul=True, is_param=True, key=key)
        _PARAM_CACHE[ck] = spec
    return spec


def read_channel(e: Entity, spec: ChannelSpec) -> Any:
    return e.params.get(spec.key, spec.add_identity) if spec.is_param else spec.get(e.pose)


def write_channel(e: Entity, spec: ChannelSpec, value: Any) -> None:
    if spec.is_param:
        e.params[spec.key] = value
    else:
        spec.put(e.pose, value)


# ---------------------------------------------------------------- процедуры
@dataclass
class ProcSpec:
    name: str
    fn: Callable[[float, dict, int], Any]
    kinds: Tuple[Kind, ...]
    defaults: Dict[str, Any] = field(default_factory=dict)


PROCS = Registry("procedure")


def _p_orbit(t: float, p: dict, seed: int) -> Vec3:
    a = p["phase"] + t * p["speed"] * TAU
    r = p["radius"]
    c = p["center"]
    return (c[0] + r * math.cos(a),
            c[1] + p["bob"] * math.sin(a * 2.0),
            c[2] + r * math.sin(a))


def _p_spin(t: float, p: dict, seed: int) -> Quat:
    return qaxis(p["axis"], math.radians(p["rate"]) * t + p["phase"])


def _p_pulse(t: float, p: dict, seed: int) -> float:
    return p["base"] + p["amp"] * math.sin(TAU * p["freq"] * t + p["phase"])


def _p_drift(t: float, p: dict, seed: int) -> Vec3:
    """Гладкий детерминированный шум: сумма синусов с хэшированными фазами. Без состояния."""
    out = []
    for axis in range(3):
        s = 0.0
        for k in range(3):
            f = p["freq"] * (k + 1) * (0.7 + 0.6 * hash_sym(seed, axis, k))
            ph = TAU * hash_sym(seed, axis, k, 99)
            s += math.sin(TAU * f * t + ph) / (k + 1)
        out.append(p["base"][axis] + p["amp"] * s)
    return (out[0], out[1], out[2])


PROCS.add("orbit", ProcSpec("orbit", _p_orbit, (Kind.VEC3,),
          {"center": ZERO, "radius": 1.0, "speed": 0.25, "phase": 0.0, "bob": 0.0}))
PROCS.add("spin", ProcSpec("spin", _p_spin, (Kind.QUAT,),
          {"axis": (0.0, 1.0, 0.0), "rate": 90.0, "phase": 0.0}))
PROCS.add("pulse", ProcSpec("pulse", _p_pulse, (Kind.FLOAT,),
          {"base": 1.0, "amp": 0.15, "freq": 1.0, "phase": 0.0}))
PROCS.add("drift", ProcSpec("drift", _p_drift, (Kind.VEC3,),
          {"base": ZERO, "amp": 0.2, "freq": 0.35}))


@dataclass
class ProcCall:
    name: str
    params: Dict[str, Any] = field(default_factory=dict)
    seed: int = 1

    def __post_init__(self):
        spec = PROCS.get(self.name)
        merged = dict(spec.defaults)
        for k, v in self.params.items():
            if k not in merged:
                raise QueryError(f"процедура '{self.name}' не знает параметр '{k}'",
                                 hints=sorted(spec.defaults))
            merged[k] = v
        self.params = merged

    @property
    def kind(self) -> Kind:
        return PROCS.get(self.name).kinds[0]

    def sample(self, t: float) -> Any:
        return PROCS.get(self.name).fn(t, self.params, self.seed)


Source = Union[Track, ProcCall]


# ---------------------------------------------------------------- биндинги
@dataclass
class Binding:
    target: str
    channel: str
    source: Source
    mode: Mode = Mode.REPLACE
    weight: float = 1.0
    priority: int = 0
    start: float = 0.0
    duration: float = 0.0
    loop: str = "hold"
    seq: int = 0

    def __post_init__(self):
        if self.loop not in LOOPS:
            raise QueryError(f"неизвестный loop '{self.loop}'", hints=list(LOOPS))
        self.mode = self.mode if isinstance(self.mode, Mode) else Mode(self.mode)
        kind = self.source.kind
        self.spec = resolve_channel(self.channel, kind)
        if self.mode is Mode.MUL and not self.spec.allow_mul:
            raise QueryError(f"канал '{self.channel}' не поддерживает mode=mul")
        if not math.isfinite(self.start) or self.duration < 0:
            raise MotusError("start должен быть конечным, duration >= 0")
        self.weight = clamp01(float(self.weight))

    @property
    def kind(self) -> Kind:
        return self.source.kind

    def local_time(self, t: float) -> Optional[float]:
        if t < self.start:
            return None
        x = t - self.start
        d = self.duration
        if d <= 0.0:
            return x
        if self.loop == "repeat":
            return x % d
        if self.loop == "pingpong":
            k = x % (2.0 * d)
            return k if k <= d else 2.0 * d - k
        if self.loop == "once":
            return x if x <= d else None
        return min(x, d)


def _apply(e: Entity, spec: ChannelSpec, value: Any, mode: Mode, w: float) -> None:
    cur = read_channel(e, spec)
    k = spec.kind
    if mode is Mode.REPLACE:
        out = blend_value(k, cur, value, w)
    elif mode is Mode.ADD:
        if k is Kind.QUAT:
            out = qnorm(qmul(cur, qslerp(QID, value, w)))
        elif k is Kind.FLOAT:
            out = cur + (value - spec.add_identity) * w
        else:
            out = vadd(cur, vscale(vsub(value, spec.add_identity), w))
    else:  # MUL: нейтраль — 1.0 (масштабный множитель)
        if k is Kind.FLOAT:
            out = cur * (1.0 + (value - 1.0) * w)
        else:
            out = tuple(c * (1.0 + (v - 1.0) * w) for c, v in zip(cur, value))
    write_channel(e, spec, out)


class Animator:
    """Фиксированный порядок: REPLACE -> ADD -> MUL, внутри фазы — priority, затем seq.

    На каждом evaluate все анимируемые объекты сбрасываются в базовую позу.
    Статические объекты не затрачиваются вообще.
    """

    def __init__(self):
        self._bindings: List[Binding] = []
        self._sorted: List[Binding] = []
        self._targets: List[str] = []
        self._dirty = True
        self._seq = 0

    def __len__(self) -> int:
        return len(self._bindings)

    def add(self, b: Binding, *, stack: bool = False) -> Binding:
        if not stack:
            self._bindings = [x for x in self._bindings
                              if not (x.target == b.target and x.channel == b.channel
                                      and x.mode is b.mode)]
        self._seq += 1
        b.seq = self._seq
        self._bindings.append(b)
        self._dirty = True
        return b

    def clear_target(self, target: str) -> None:
        self._bindings = [b for b in self._bindings if b.target != target]
        self._dirty = True

    def _compile(self) -> None:
        self._sorted = sorted(self._bindings, key=lambda b: (b.mode.phase, b.priority, b.seq))
        seen: Dict[str, None] = {}
        for b in self._sorted:
            seen.setdefault(b.target, None)
        self._targets = list(seen)
        self._dirty = False

    def evaluate(self, t: float, scene: Scene) -> int:
        if self._dirty:
            self._compile()
        ids: Dict[str, int] = {}
        for name in self._targets:
            eid = scene.find(name)
            if eid is not None and scene.entity(eid).alive:
                ids[name] = eid
                scene.reset_pose(eid)
        applied = 0
        for b in self._sorted:
            eid = ids.get(b.target)
            if eid is None or b.weight == 0.0:
                continue
            lt = b.local_time(t)
            if lt is None:
                continue
            _apply(scene.entity(eid), b.spec, b.source.sample(lt), b.mode, b.weight)
            applied += 1
        return applied