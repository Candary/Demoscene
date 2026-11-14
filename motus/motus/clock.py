"""Единственный источник времени. Ничего не накапливает: время задаётся извне."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Iterator

from .core import MotusError


@dataclass(frozen=True)
class Transport:
    """Музыкальная сетка. Позволяет писать at=beat:8 / bar:2 вместо секунд."""
    bpm: float = 120.0
    offset: float = 0.0
    beats_per_bar: int = 4

    def __post_init__(self):
        if self.bpm <= 0 or self.beats_per_bar <= 0:
            raise MotusError("Transport: bpm и beats_per_bar должны быть > 0")

    def beat(self, t: float) -> float:
        return max(0.0, t - self.offset) * (self.bpm / 60.0)

    def bar(self, t: float) -> float:
        return self.beat(t) / self.beats_per_bar

    def seconds(self, beats: float) -> float:
        return self.offset + beats * 60.0 / self.bpm


def fixed_frames(fps: float, duration: float, start: float = 0.0) -> Iterator[float]:
    """Offline-сетка. t = start + k/fps — ровно те же значения, что в realtime."""
    if fps <= 0:
        raise MotusError("fps должен быть > 0")
    n = int(math.floor(duration * fps)) + 1
    for k in range(n):
        yield start + k / fps


class LiveClock:
    """Настенные часы. evaluate() всё равно получает готовое t — детерминизм сохранён."""

    def __init__(self, source=time.monotonic):
        self._src = source
        self._t0 = source()
        self._bias = 0.0

    def now(self) -> float:
        return self._bias + (self._src() - self._t0)

    def seek(self, t: float) -> None:
        self._bias = float(t)
        self._t0 = self._src()