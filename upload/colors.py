"""Связь Cozy Engine с Color Matrix на уровне данных.

Подпись сцены называет цвета словами («dark blue blanket», «beige carpet»). Здесь они превращаются в RGB-прототипы,
затем для каждого прототипа берётся профиль из Color Matrix (empathy, intensity, температура, OKLCH), и из этого
собираются отклики группы color_* (vocab.RESPONSE_GROUPS['color']).

ЧЕСТНО ОБ ОГРАНИЧЕНИЯХ:
  * RGB-прототипы слов («beige» -> один конкретный цвет) — допущение; реальный бежевый сильно варьируется;
  * профиль в Color Matrix — prior-модель (формулы по тону/насыщенности/светлоте), не измерение людей;
  * поэтому color_* — описательные признаки сцены «по тексту», а не доказательство того, что цвет вызывает уют.
    Корреляция color_* с cozy_kw проверяет согласованность двух гипотез, а не причину.
При обновлении Color Matrix (новая версия, crowd-данные) color_* нужно пересчитать: версия записывается в info матрицы.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from . import vocab

# color_matrix_python лежит рядом (output/color_matrix_python); путь добавляет вызывающий код или тест.
from color_matrix_python.colorspace import lab_to_lch, oklch_to_rgb, rgb_to_oklab, to_hex  # noqa: E402

# Прототипы названий цветов (sRGB). Подбирались как типичные цвета интерьерных поверхностей, а не «чистые» цвета.
PROTOTYPES: dict[str, tuple[int, int, int]] = {
    "white": (240, 240, 238), "ivory": (250, 245, 225), "cream": (245, 235, 205), "beige": (220, 200, 165),
    "tan": (200, 165, 120), "khaki": (190, 175, 120), "brown": (120, 80, 55), "copper": (170, 100, 60),
    "bronze": (140, 110, 60), "black": (30, 30, 30), "charcoal": (60, 60, 64), "gray": (135, 135, 135),
    "grey": (135, 135, 135), "silver": (190, 190, 195), "blue": (50, 100, 185), "navy": (25, 40, 95),
    "teal": (30, 125, 130), "turquoise": (60, 190, 185), "green": (60, 130, 75), "olive": (110, 115, 50),
    "red": (180, 45, 45), "maroon": (110, 25, 35), "burgundy": (110, 25, 45), "orange": (225, 125, 45),
    "yellow": (235, 205, 70), "gold": (210, 170, 55), "golden": (210, 170, 55), "pink": (235, 150, 170),
    "purple": (115, 70, 150), "lavender": (180, 160, 215),
}
# Модификаторы: преобразования в OKLCH (L, C) — эвристика.
MODIFIERS = {
    "dark": (0.72, 1.0, 0.0), "deep": (0.85, 1.1, 0.0), "light": (1.0, 0.8, 0.40), "pale": (1.0, 0.6, 0.50),
    "bright": (1.0, 1.25, 0.0), "vivid": (1.0, 1.35, 0.0), "muted": (1.0, 0.6, 0.0), "pastel": (1.0, 0.55, 0.45),
}  # (множитель L, множитель C, доля приближения L к 1)

_RX = re.compile(r"\b(?:(%s)[ -])?(%s)\b" % ("|".join(MODIFIERS), "|".join(sorted(PROTOTYPES, key=len, reverse=True))))


def phrase_rgb(modifier: str, word: str) -> tuple[int, int, int]:
    base = PROTOTYPES[word]
    if not modifier:
        return base
    L, C, h = (float(v) for v in lab_to_lch(rgb_to_oklab(np.array(base, dtype=float))))
    mL, mC, toward = MODIFIERS[modifier]
    L2 = L * mL
    L2 = L2 + (1.0 - L2) * toward
    return oklch_to_rgb(min(max(L2, 0.0), 1.0), C * mC, h)


def extract_phrases(text: str) -> list[tuple[str, str]]:
    """[(phrase, word)] — уникальные цветовые фразы в порядке появления: «dark blue» -> ('dark blue', 'blue')."""
    seen, out = set(), []
    for mod, word in _RX.findall(str(text).lower()):
        phrase = f"{mod} {word}".strip()
        if phrase not in seen:
            seen.add(phrase)
            out.append((phrase, word))
    return out


@dataclass(frozen=True)
class ColorProfile:
    phrase: str
    rgb: tuple[int, int, int]
    hex: str
    empathy: float        # -100..100 (Color Matrix)
    empathy_label: str
    intensity: float      # 0..100 (Color Matrix 'entropy')
    temperature: int      # 0 cold .. 4 hot
    L: float
    C: float
    h: float


class ColorLink:
    """Мост к Color Matrix. reader — color_matrix_python.reader.FullRGBMatrixReader (v11 рекомендуется)."""

    def __init__(self, reader):
        self.reader = reader
        self._cache: dict[str, ColorProfile] = {}

    @property
    def color_matrix_version(self) -> str:
        return self.reader.dataset_version

    def profile(self, phrase: str) -> ColorProfile:
        if phrase in self._cache:
            return self._cache[phrase]
        parts = phrase.split(" ")
        mod, word = (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])
        rgb = phrase_rgb(mod, word)
        cell = self.reader.get_cell(rgb)
        p = ColorProfile(phrase, rgb, to_hex(rgb), cell.empathy.score, cell.empathy.label, cell.entropy.score,
                         int(cell.synesthesia_tags[0]["value"]), cell.oklch[0], cell.oklch[1], cell.oklch[2])
        self._cache[phrase] = p
        return p

    def features(self, text: str) -> tuple[dict[str, float], list[str]]:
        """Отклики color_* и список фраз. Если в тексте нет цветов, возвращает {} (значения НЕИЗВЕСТНЫ, а не нули)."""
        phrases = [p for p, _ in extract_phrases(text)]
        return self.features_from_phrases(phrases), phrases

    def features_from_phrases(self, phrases: list[str]) -> dict[str, float]:
        if not phrases:
            return {}
        ps = [self.profile(p) for p in phrases]
        emp = np.array([p.empathy for p in ps]); inten = np.array([p.intensity for p in ps])
        C = np.array([p.C for p in ps]); L = np.array([p.L for p in ps]); T = np.array([p.temperature for p in ps])
        lab = np.array([vocab_idx(p.empathy_label) for p in ps])
        return {
            "color_empathy_mean": float(((emp + 100) / 200).mean()), "color_empathy_min": float(((emp + 100) / 200).min()),
            "color_intensity_mean": float((inten / 100).mean()), "color_intensity_max": float((inten / 100).max()),
            "color_chroma_mean": float(np.clip(C / vocab.CHROMA_MAX, 0, 1).mean()), "color_lightness_mean": float(L.mean()),
            "color_warm_fraction": float((T >= 3).mean()), "color_cold_fraction": float((T <= 1).mean()),
            "color_tension_fraction": float((lab <= 1).mean()), "color_positive_fraction": float((lab >= 3).mean()),
            "color_n_colors": float(len(ps)), "color_dark_fraction": float((L < 0.45).mean()),
        }


def vocab_idx(empathy_label: str) -> int:
    return ["anxiety", "tension", "neutral", "warmth", "delight"].index(empathy_label)
