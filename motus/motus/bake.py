"""Опциональный кэш поз. Плоский файл + JSON-манифест, читается через mmap.

Это НЕ источник истины и НЕ .npz: zip нельзя отобразить в память, а здесь
один открытый файл и адресная арифметика. Только stdlib.
"""
from __future__ import annotations

import json
import mmap
import struct
from pathlib import Path
from typing import List, Tuple

from .clock import fixed_frames
from .core import MotusError

VERSION = 1
STRIDE = 40  # 10 float32: pos3, quat4, scale3


def bake(rt, *, fps: float, duration: float, out: str, start: float = 0.0) -> dict:
    rt.frame(start + duration)                     # материализуем все события
    n = len(rt.scene)
    names = [rt.scene.entity(i).name for i in range(n)]
    out_p = Path(out)
    out_p.mkdir(parents=True, exist_ok=True)
    frames = 0
    with open(out_p / "poses.f32", "wb") as fh:
        for t in fixed_frames(fps, duration, start):
            rt.frame(t)
            if len(rt.scene) != n:
                raise MotusError("bake требует стабильного набора объектов: "
                                 "все `new` должны быть на at<=start")
            buf = bytearray()
            for eid in range(n):
                p = rt.scene.entity(eid).pose
                buf += struct.pack("<10f", *p.pos, *p.rot, *p.scale)
            fh.write(buf)
            frames += 1
    manifest = {"version": VERSION, "fps": fps, "start": start, "frames": frames,
                "stride_bytes": STRIDE, "dtype": "float32", "byteorder": "little",
                "layout": "frame-major, entity-minor, pos3 quat4 scale3",
                "entities": names}
    (out_p / "manifest.json").write_text(json.dumps(manifest, indent=2), "utf-8")
    return manifest


class Playback:
    def __init__(self, path: str):
        p = Path(path)
        self.manifest = json.loads((p / "manifest.json").read_text("utf-8"))
        if self.manifest["version"] != VERSION:
            raise MotusError("неподдерживаемая версия кэша")
        self.entities: List[str] = self.manifest["entities"]
        self.n = len(self.entities)
        self.frames = self.manifest["frames"]
        self._fh = open(p / "poses.f32", "rb")
        self._mm = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)

    def pose(self, frame: int, index: int) -> Tuple[float, ...]:
        if not (0 <= frame < self.frames and 0 <= index < self.n):
            raise MotusError("индекс вне кэша")
        return struct.unpack_from("<10f", self._mm, (frame * self.n + index) * STRIDE)

    def close(self) -> None:
        self._mm.close()
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()