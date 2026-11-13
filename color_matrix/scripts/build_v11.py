"""Строит color-matrix-full-rgb-v11.npz из v10.

Что меняется (и только это):
  temperature — в v10 зависит ТОЛЬКО от тона (hue). У ахроматических цветов тон не определён
  (или определяется шумом квантования), поэтому все 256 серых получали 'hot', а цвета с разбросом каналов
  в 1–2 единицы получали случайные 'cold'..'hot'.
  Правило v11 (по OKLCH chroma C):
      C <  0.01        -> neutral(2)                      (тон — шум квантования)
      0.01 <= C < 0.03 -> ограничить диапазоном [1..3]    (тёплый/холодный серый допустим, hot/cold — нет)
      C >= 0.03        -> без изменений
Все остальные массивы копируются байт-в-байт. format_version = 11.0, parent_version = 10.0.

Запуск:  python scripts/build_v11.py output/color-matrix-full-rgb-v10.npz output/color-matrix-full-rgb-v11.npz
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "output"))
from color_matrix_python.colorspace import lab_to_lch, rgb_to_oklab  # noqa: E402

N = 1 << 24
CHUNK = 1 << 20
C_NEUTRAL = 0.01
C_LIMIT = 0.03


def main(src: str, dst: str) -> dict:
    d = np.load(src)
    arrays = {k: d[k] for k in d.files}
    syn = arrays["synesthesia_packed"].copy()
    stats = {"neutralized": 0, "clamped": 0, "unchanged": 0, "by_old_temperature": {}}

    for start in range(0, N, CHUNK):
        idx = np.arange(start, start + CHUNK, dtype=np.int64)
        rgb = np.stack([(idx >> 16) & 255, (idx >> 8) & 255, idx & 255], axis=-1)
        C = lab_to_lch(rgb_to_oklab(rgb))[..., 1]

        p = syn[start:start + CHUNK]
        v = p[:, 0].astype(np.uint32) | (p[:, 1].astype(np.uint32) << 8) | (p[:, 2].astype(np.uint32) << 16)
        old = (v & 7).astype(np.int64)
        new = old.copy()
        low = C < C_NEUTRAL
        mid = (C >= C_NEUTRAL) & (C < C_LIMIT)
        new[low] = 2
        new[mid] = np.clip(old[mid], 1, 3)

        changed = new != old
        stats["neutralized"] += int((low & changed).sum())
        stats["clamped"] += int((mid & changed).sum())
        stats["unchanged"] += int((~changed).sum())
        for t, c in zip(*np.unique(old[changed], return_counts=True)):
            stats["by_old_temperature"][int(t)] = stats["by_old_temperature"].get(int(t), 0) + int(c)

        v = (v & ~np.uint32(7)) | new.astype(np.uint32)
        syn[start:start + CHUNK, 0] = (v & 255).astype(np.uint8)
        syn[start:start + CHUNK, 1] = ((v >> 8) & 255).astype(np.uint8)
        syn[start:start + CHUNK, 2] = ((v >> 16) & 255).astype(np.uint8)

    arrays["synesthesia_packed"] = syn
    arrays["format_version"] = np.array("11.0")
    arrays["parent_version"] = np.array("10.0")
    arrays["patch_notes"] = np.array("temperature: neutralized for OKLCH C<0.01, clamped to [1..3] for C<0.03; all else identical to v10")
    np.savez_compressed(dst, **arrays)
    return stats


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(json.dumps(main(sys.argv[1], sys.argv[2]), indent=2, ensure_ascii=False))
