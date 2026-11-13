"""Обратный поиск: «хочу такое ощущение + такие ограничения» -> список реальных RGB-цветов из матрицы.

Ищем не по всем 16.7 млн ячеек, а по сетке с шагом `stride` (по умолчанию 4: 65^3 = 274 625 цветов).
Все возвращаемые цвета — настоящие ячейки матрицы, для них доступен полный профиль через reader.get_cell().
"""
from __future__ import annotations

import numpy as np

from . import vocab
from .vocab import normalize_empathy, normalize_temperature
from .colorspace import (contrast_ratio, delta_e_ok, lab_to_lch, relative_luminance, rgb_to_oklab, to_hex,
                         parse_color, RGB)
from .reader import FullRGBMatrixReader

TEMP_ALIASES = {"cold": [0], "cool": [1], "neutral": [2], "warm": [3], "hot": [4],
                "warmish": [3, 4], "coolish": [0, 1]}
TEMP_WORDS = vocab.SYNESTHESIA["temperature"]["words"]
WEIGHT_WORDS = vocab.SYNESTHESIA["weight"]["words"]


def _norm_list(value):
    if value is None:
        return None
    return [value] if isinstance(value, (str, int)) else list(value)


def _temp_levels(values) -> list[int]:
    out: list[int] = []
    for v in _norm_list(values) or []:
        key = str(v).lower()
        if key == "warm_side":
            out += [3, 4]
        elif key == "cool_side":
            out += [0, 1]
        elif key in TEMP_ALIASES:
            out += TEMP_ALIASES[key]
        else:
            raise ValueError(f"temperature: неизвестное значение {v!r}; допустимо {TEMP_WORDS + ['warm_side', 'cool_side']}")
    return sorted(set(out))


def _intensity_levels(values) -> list[int]:
    out = []
    for v in _norm_list(values) or []:
        if v in vocab.ENTROPY_INTENSITY:
            out.append(vocab.ENTROPY_INTENSITY.index(v))
        elif v in vocab.ENTROPY_LEGACY:
            out.append(vocab.ENTROPY_LEGACY.index(v))
        else:
            raise ValueError(f"intensity: неизвестное значение {v!r}; допустимо {vocab.ENTROPY_INTENSITY}")
    return sorted(set(out))


class SearchIndex:
    def __init__(self, reader: FullRGBMatrixReader, stride: int = 4):
        if not 1 <= stride <= 16:
            raise ValueError("stride должен быть в 1..16")
        self.reader = reader
        vals = np.unique(np.concatenate([np.arange(0, 256, stride), [255]]))
        r, g, b = np.meshgrid(vals, vals, vals, indexing="ij")
        self.rgb = np.stack([r.ravel(), g.ravel(), b.ravel()], axis=-1).astype(np.int16)
        many = reader.get_many(self.rgb)
        self.lab = rgb_to_oklab(self.rgb).astype(np.float32)
        lch = lab_to_lch(self.lab)
        self.L, self.C, self.h = lch[:, 0].astype(np.float32), lch[:, 1].astype(np.float32), lch[:, 2].astype(np.float32)
        self.Y = relative_luminance(self.rgb).astype(np.float32)
        self.emp = many["empathy_score"].astype(np.float32)
        self.emp_label = many["empathy_label"]
        self.ent = many["entropy_score"].astype(np.float32)
        self.ent_label = many["entropy_label"]
        syn = many["synesthesia"]
        self.temp, self.weight = syn[:, 0], syn[:, 1]
        self._tiebreak = np.random.default_rng(0).permutation(len(self.rgb))  # детерминированный «шум»

    def __len__(self):
        return len(self.rgb)

    # ------------------------------------------------------------------
    def find(self, *, feel: str | None = None, empathy_range=None, empathy_tolerance: float = 10.0,
             intensity=None, temperature=None, weight=None, hue_range=None, lightness_range=None,
             min_chroma: float | None = None, max_chroma: float | None = None,
             background=None, min_contrast: float | None = None,
             count: int = 5, min_delta_e: float = 0.06, random: bool = False) -> dict:
        count = int(min(max(count, 1), 12))
        mask = np.ones(len(self.rgb), dtype=bool)
        diag = [{"constraint": "all", "remaining": int(mask.sum())}]

        def apply(name, m):
            nonlocal mask
            mask = mask & m
            diag.append({"constraint": name, "remaining": int(mask.sum())})

        target = None
        if feel is not None:
            feel = normalize_empathy(feel)
            if feel not in vocab.EMPATHY:
                raise ValueError(f"feel: неизвестное значение {feel!r}; допустимо {vocab.EMPATHY}")
            lo, hi = vocab.EMPATHY_RANGES[feel]
            apply(f"feel={feel}", (self.emp >= lo) & (self.emp <= hi))
            target = vocab.EMPATHY_TARGET[feel]
        if empathy_range is not None:
            lo, hi = float(empathy_range[0]), float(empathy_range[1])
            if lo > hi:
                raise ValueError("empathy_range: нижняя граница больше верхней")
            apply(f"empathy_range=[{lo:g},{hi:g}]", (self.emp >= lo) & (self.emp <= hi))
            target = (lo + hi) / 2 if feel is None else target
        if intensity is not None:
            lv = _intensity_levels(intensity)
            apply(f"intensity={lv}", np.isin(self.ent_label, lv))
        if temperature is not None:
            lv = _temp_levels(temperature)
            apply(f"temperature={lv}", np.isin(self.temp, lv))
        if weight is not None:
            ws = [w for w in _norm_list(weight)]
            bad = [w for w in ws if w not in WEIGHT_WORDS]
            if bad:
                raise ValueError(f"weight: неизвестное значение {bad}; допустимо {WEIGHT_WORDS}")
            apply(f"weight={ws}", np.isin(self.weight, [WEIGHT_WORDS.index(w) for w in ws]))
        if hue_range is not None:
            a, b = float(hue_range[0]) % 360, float(hue_range[1]) % 360
            m = (self.h >= a) & (self.h <= b) if a <= b else (self.h >= a) | (self.h <= b)
            apply(f"hue_range=[{a:g},{b:g}]", m)
        if lightness_range is not None:
            apply("lightness_range", (self.L >= lightness_range[0]) & (self.L <= lightness_range[1]))
        if min_chroma is not None:
            apply(f"min_chroma={min_chroma:g}", self.C >= min_chroma)
        if max_chroma is not None:
            apply(f"max_chroma={max_chroma:g}", self.C <= max_chroma)

        bg_rgb = None
        if background is not None:
            bg_rgb = parse_color(background)
        if min_contrast is not None:
            if bg_rgb is None:
                raise ValueError("min_contrast требует background")
            ratio = contrast_ratio(self.rgb.astype(np.float64), np.array(bg_rgb, dtype=np.float64))
            apply(f"contrast_vs_background>={min_contrast:g}", ratio >= min_contrast)

        sel = np.flatnonzero(mask)
        n_matches = int(sel.size)
        if n_matches == 0:
            return {"n_matches": 0, "candidates": [], "diagnostics": diag,
                    "hint": "Ни один цвет не подошёл. Смотри diagnostics: ограничение, после которого remaining стало 0, слишком жёсткое."}

        if random:
            rng = np.random.default_rng()
            if n_matches <= count:
                chosen_pool = sel
            else:
                chosen_pool = rng.choice(sel, size=count, replace=False)
            chosen = list(chosen_pool)
        else:
            # ранжирование: внутри допуска по эмпатии цвета равноправны (разброс по тонам), дальше — детерминированный шум
            key = np.zeros(sel.size, dtype=np.float32)
            if target is not None:
                key = np.maximum(0.0, np.abs(self.emp[sel] - target) - empathy_tolerance)
            order = sel[np.lexsort((self._tiebreak[sel], key))][:5000]

            chosen: list[int] = []
            # perf S-01: mask-based ranking. Раньше на каждой из count итераций
            # вызывали np.flatnonzero(mind >= min_delta_e) — O(N) scan + новый alloc
            # массива N int64 на каждой итерации. Теперь переиспользуем boolean mask,
            # обновляем in-place через np.logical_and(..., out=eligible).
            N = order.size
            eligible = np.ones(N, dtype=bool)
            mind = np.full(N, np.inf, dtype=np.float32)
            while len(chosen) < count:
                # Найти первый eligible индекс. argmax на bool = первый True.
                # O(N), но без нового alloc (flatnonzero делал бы alloc N int64).
                if not eligible.any():           # O(1) early exit если mask пуст
                    break
                c = int(np.argmax(eligible))     # O(N), без alloc
                chosen.append(int(order[c]))

                # Обновить mind (delta_e от выбранного ко всем остальным).
                # Это O(N) и не оптимизируется — суть алгоритма.
                new_deltas = delta_e_ok(self.lab[order], self.lab[order[c]])
                np.minimum(mind, new_deltas, out=mind)

                # Update eligible: выкинуть слишком близкие + сам выбранный.
                # in-place: НЕ создаёт новый массив (старая версия делала mask & m → new array).
                np.logical_and(eligible, mind >= min_delta_e, out=eligible)
                eligible[c] = False

        return {"n_matches": n_matches, "candidates": [self._describe(i, bg_rgb) for i in chosen], "diagnostics": diag}

    # ------------------------------------------------------------------
    def _describe(self, i: int, bg_rgb: RGB | None) -> dict:
        rgb = tuple(int(v) for v in self.rgb[i])
        out = {
            "hex": to_hex(rgb), "rgb": list(rgb),
            "oklch": [round(float(self.L[i]), 3), round(float(self.C[i]), 3), round(float(self.h[i]), 1)],
            "empathy": {"label": vocab.EMPATHY[int(self.emp_label[i])], "score": int(self.emp[i])},
            "intensity": {"label": vocab.ENTROPY_INTENSITY[int(self.ent_label[i])], "score": int(self.ent[i])},
            "temperature": TEMP_WORDS[int(self.temp[i])],
            "weight": WEIGHT_WORDS[int(self.weight[i])],
        }
        if bg_rgb is not None:
            out["contrast_vs_background"] = round(float(contrast_ratio(np.array(rgb, dtype=np.float64),
                                                                        np.array(bg_rgb, dtype=np.float64))), 2)
        return out
