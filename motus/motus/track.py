"""Типизированные треки. Семплирование безопасно на любых t, включая NaN и ±inf."""
from __future__ import annotations

import math
from bisect import bisect_right
from enum import Enum
from typing import Any, Iterable, List, Optional, Tuple

from .core import MotusError, Registry
from .mathx import QID, ONE, ZERO, clamp01, qnorm, qslerp, vec


class Kind(Enum):
    FLOAT = "float"
    VEC3 = "vec3"
    QUAT = "quat"


IDENTITY = {Kind.FLOAT: 0.0, Kind.VEC3: ZERO, Kind.QUAT: QID}
WIDTH = {Kind.FLOAT: 1, Kind.VEC3: 3, Kind.QUAT: 4}

EASINGS = Registry("easing")
EASINGS.add("linear", lambda u: u)
EASINGS.add("smooth", lambda u: u * u * (3.0 - 2.0 * u))
EASINGS.add("in", lambda u: u * u)
EASINGS.add("out", lambda u: 1.0 - (1.0 - u) * (1.0 - u))
EASINGS.add("inout", lambda u: 2.0 * u * u if u < 0.5 else 1.0 - 2.0 * (1.0 - u) ** 2)
EASINGS.add("step", lambda u: 0.0)  # step — это просто easing, отдельная ветка не нужна


def kind_of(value: Any) -> Kind:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return Kind.FLOAT
    n = len(value)
    if n == 3:
        return Kind.VEC3
    if n == 4:
        return Kind.QUAT
    raise MotusError(f"не удалось определить тип значения {value!r}")


def coerce(kind: Kind, value: Any) -> Any:
    if kind is Kind.FLOAT:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MotusError(f"ожидалось число, получено {value!r}")
        v = float(value)
        if not math.isfinite(v):
            raise MotusError("число должно быть конечным")
        return v
    try:
        out = vec(value, WIDTH[kind])
    except (TypeError, ValueError) as exc:
        raise MotusError(str(exc)) from exc
    return qnorm(out) if kind is Kind.QUAT else out


def blend_value(kind: Kind, a: Any, b: Any, u: float) -> Any:
    if kind is Kind.FLOAT:
        return a + (b - a) * u
    if kind is Kind.VEC3:
        return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u)
    return qslerp(a, b, u)


class Track:
    """Ключи по возрастанию t. Вне диапазона — clamp. Пустой трек — identity.

    sample() логически const: результат не зависит от порядка вызовов.
    Внутренний курсор `_i` — только оптимизация (O(1) при монотонном t).
    Не thread-safe: на поток нужен свой Track или внешняя блокировка.
    """

    __slots__ = ("kind", "ease", "_t", "_v", "_i", "_default", "_ease_fn")

    def __init__(self, kind, *, ease: str = "linear", default: Optional[Any] = None):
        self.kind = kind if isinstance(kind, Kind) else Kind(kind)
        self.ease = ease
        self._ease_fn = EASINGS.get(ease)
        self._t: List[float] = []
        self._v: List[Any] = []
        self._i = 0
        self._default = IDENTITY[self.kind] if default is None else coerce(self.kind, default)

    def key(self, t: float, value: Any) -> "Track":
        t = float(t)
        if not math.isfinite(t):
            raise MotusError("время ключа должно быть конечным")
        if self._t and t <= self._t[-1]:
            raise MotusError("времена ключей должны строго возрастать")
        self._t.append(t)
        self._v.append(coerce(self.kind, value))
        return self

    def keys(self, pairs: Iterable[Tuple[float, Any]]) -> "Track":
        for t, v in pairs:
            self.key(t, v)
        return self

    @property
    def span(self) -> Tuple[float, float]:
        return (self._t[0], self._t[-1]) if self._t else (0.0, 0.0)

    def __len__(self) -> int:
        return len(self._t)

    def sample(self, t: float) -> Any:
        ts = self._t
        if not ts:
            return self._default
        if not (t > ts[0]):          # ловит NaN, -inf и t <= first
            return self._v[0]
        if t >= ts[-1]:              # ловит +inf и t >= last
            return self._v[-1]
        i = self._i
        if i + 1 >= len(ts) or not (ts[i] <= t < ts[i + 1]):
            i = bisect_right(ts, t) - 1
            self._i = i
        u = (t - ts[i]) / (ts[i + 1] - ts[i])
        return blend_value(self.kind, self._v[i], self._v[i + 1], self._ease_fn(clamp01(u)))