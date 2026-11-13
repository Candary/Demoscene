from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import vocab
from .colorspace import RGB, hsl_to_rgb, rgb_to_hsl, rgb_to_oklch, parse_color, to_hex
from .vocab import DIMS, EMPATHY

# Реэкспорт для обратной совместимости с v10 (`from reader import EMPATHY, DIMS`).
ENTROPY = vocab.ENTROPY_LEGACY


@dataclass
class Profile:
    label: str
    score: float
    confidence: float
    description: str
    legacy_label: str | None = None


@dataclass
class Cell:
    rgb: RGB
    hsl: tuple
    oklch: tuple
    empathy: Profile
    entropy: Profile
    synesthesia_tags: list
    complements: list
    data_mode: str
    dataset_version: str
    source: str
    warnings: list = field(default_factory=list)

    @property
    def hex(self) -> str:
        return to_hex(self.rgb)


def wheel_opposite(rgb: RGB) -> RGB:
    h, s, l = rgb_to_hsl(rgb)
    return hsl_to_rgb((h + 180) % 360, s, l)


def contrast_safe(rgb: RGB) -> RGB:
    return (0, 0, 0) if 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2] > 128 else (255, 255, 255)


def unpack_synesthesia(packed: np.ndarray) -> np.ndarray:
    """(n, 3) uint8 -> (n, 6) uint8: по 3 бита на измерение, порядок vocab.DIMS."""
    p = np.asarray(packed)
    v = p[..., 0].astype(np.uint32) | (p[..., 1].astype(np.uint32) << 8) | (p[..., 2].astype(np.uint32) << 16)
    return np.stack([((v >> (3 * j)) & 7) for j in range(len(DIMS))], axis=-1).astype(np.uint8)


class FullRGBMatrixReader:
    """Читает полный NPZ (v10 или v11). Формат: индекс = r*65536 + g*256 + b."""

    def __init__(self, npz_path, dataset_version: str | None = None, entropy_labels: str = "intensity",
                 confidence: dict | None = None):
        if entropy_labels not in ("intensity", "legacy"):
            raise ValueError("entropy_labels должен быть 'intensity' или 'legacy'")
        d = np.load(Path(npz_path))
        self.es = d["empathy_score"]
        self.el = d["empathy_label"]
        self.ns = d["entropy_score"]
        self.nl = d["entropy_label"]
        self.syn = d["synesthesia_packed"]
        fv = str(d["format_version"]) if "format_version" in d.files else "10.0"
        self.format_version = fv
        self.dataset_version = dataset_version or f"prior-v{int(float(fv))}"
        self.entropy_labels = entropy_labels
        self.confidence = {**vocab.PRIOR_CONFIDENCE, **(confidence or {})}
        if self.es.shape[0] != 1 << 24:
            raise ValueError(f"ожидалось 16777216 ячеек, в файле {self.es.shape[0]}")

    # -- индексация ----------------------------------------------------------
    @staticmethod
    def index(rgb) -> int:
        r, g, b = parse_color(rgb)
        return r * 65536 + g * 256 + b

    # -- одна ячейка ---------------------------------------------------------
    def get_cell(self, rgb) -> Cell:
        rgb = parse_color(rgb)
        i = self.index(rgb)
        ei, ni = int(self.el[i]), int(self.nl[i])
        levels = unpack_synesthesia(self.syn[i:i + 1])[0]

        tags = []
        for j, dim in enumerate(DIMS):
            spec = vocab.SYNESTHESIA[dim]
            lv = int(levels[j])
            tag = {"dimension": dim, "value": lv, "max": spec["levels"] - 1, "driver": spec["driver"],
                   "word": spec["words"][lv] if spec["words"] and lv < len(spec["words"]) else None,
                   "word_status": spec["status"]}
            if spec.get("note"):
                tag["note"] = spec["note"]
            tags.append(tag)

        ent_label = vocab.ENTROPY_INTENSITY[ni]
        emp = Profile(EMPATHY[ei], float(self.es[i]), self.confidence["empathy"], vocab.EMPATHY_DESC[EMPATHY[ei]])
        ent = Profile(ent_label if self.entropy_labels == "intensity" else vocab.ENTROPY_LEGACY[ni],
                      float(self.ns[i]), self.confidence["entropy"], vocab.ENTROPY_DESC[ent_label],
                      legacy_label=vocab.ENTROPY_LEGACY[ni])

        oklch = rgb_to_oklch(rgb)
        warnings = []
        if abs(emp.score) == 100:
            warnings.append("empathy_at_scale_limit: оценка упирается в границу шкалы; такие цвета неразличимы по эмпатии")
        if oklch[1] < 0.03:
            warnings.append("low_chroma: цвет почти ахроматический, оттенок ненадёжен")

        return Cell(rgb, rgb_to_hsl(rgb), oklch, emp, ent, tags,
                    [{"strategy": "wheel_opposite", "rgb": wheel_opposite(rgb)},
                     {"strategy": "contrast_safe", "rgb": contrast_safe(rgb)}],
                    "prior", self.dataset_version, "procedural", warnings)

    # -- пакетный доступ -----------------------------------------------------
    def get_many(self, rgb_array) -> dict:
        """rgb_array (n, 3) -> словарь numpy-массивов (без объектов Cell)."""
        a = np.asarray(rgb_array, dtype=np.int64)
        idx = a[:, 0] * 65536 + a[:, 1] * 256 + a[:, 2]
        return {
            "index": idx,
            "empathy_score": self.es[idx], "empathy_label": self.el[idx],
            "entropy_score": self.ns[idx], "entropy_label": self.nl[idx],
            "synesthesia": unpack_synesthesia(self.syn[idx]),
        }
