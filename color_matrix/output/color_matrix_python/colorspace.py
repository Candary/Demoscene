"""Цветовые утилиты: sRGB <-> OKLab/OKLCH, WCAG-контраст, симуляция дальтонизма, разбор ввода.

Всё векторизовано (numpy) там, где это нужно для поиска по матрице.
"""
from __future__ import annotations

import colorsys
import math
import re
from typing import Iterable, Sequence

import numpy as np

RGB = tuple[int, int, int]

# --- sRGB <-> linear -------------------------------------------------------

def srgb_to_linear(c):
    """c в диапазоне 0..1 (любая форма массива)."""
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)


# --- OKLab / OKLCH (Björn Ottosson) -----------------------------------------

def rgb_to_oklab(rgb, dtype=np.float64):
    """rgb: массив (..., 3), значения 0..255 -> (..., 3) = L, a, b."""
    x = srgb_to_linear(np.asarray(rgb, dtype=np.float64) / 255.0)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    l = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return np.stack([L, a, bb], axis=-1).astype(dtype, copy=False)


def oklab_to_linear_rgb(lab):
    lab = np.asarray(lab, dtype=np.float64)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    g = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    bl = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
    return np.stack([r, g, bl], axis=-1)


def lab_to_lch(lab):
    lab = np.asarray(lab, dtype=np.float64)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    return np.stack([L, np.hypot(a, b), np.degrees(np.arctan2(b, a)) % 360.0], axis=-1)


def rgb_to_oklch(rgb) -> tuple[float, float, float]:
    """Скаляр: (L, C, h) с тем же округлением, что в v10-ридере."""
    L, C, h = lab_to_lch(rgb_to_oklab(np.asarray(rgb, dtype=np.float64)))
    return (round(float(L), 4), round(float(C), 4), round(float(h), 2))


def in_gamut(lin, eps=1e-6):
    lin = np.asarray(lin)
    return np.all((lin >= -eps) & (lin <= 1 + eps), axis=-1)


def oklch_to_rgb(L: float, C: float, h: float) -> RGB:
    """OKLCH -> sRGB (0..255). Если цвет вне гаммы, уменьшаем chroma (тон и светлота сохраняются)."""
    L = float(min(max(L, 0.0), 1.0))
    lo, hi = 0.0, max(float(C), 0.0)

    def lin_for(c):
        hr = math.radians(h)
        return oklab_to_linear_rgb(np.array([L, c * math.cos(hr), c * math.sin(hr)]))

    if not in_gamut(lin_for(hi)):
        for _ in range(30):
            mid = (lo + hi) / 2
            if in_gamut(lin_for(mid)):
                lo = mid
            else:
                hi = mid
        lin = lin_for(lo)
    else:
        lin = lin_for(hi)
    srgb = linear_to_srgb(np.clip(lin, 0, 1)) * 255.0
    return tuple(int(round(float(v))) for v in srgb)  # type: ignore[return-value]


def delta_e_ok(lab1, lab2):
    """Евклидово расстояние в OKLab (ΔE_OK). ~0.02 — едва заметно, ~0.1 — уверенно различимо."""
    return np.linalg.norm(np.asarray(lab1, dtype=np.float64) - np.asarray(lab2, dtype=np.float64), axis=-1)


# --- WCAG --------------------------------------------------------------------

def relative_luminance(rgb):
    x = srgb_to_linear(np.asarray(rgb, dtype=np.float64) / 255.0)
    return 0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2]


def contrast_ratio(rgb1, rgb2):
    y1, y2 = relative_luminance(rgb1), relative_luminance(rgb2)
    hi, lo = np.maximum(y1, y2), np.minimum(y1, y2)
    return (hi + 0.05) / (lo + 0.05)


WCAG_THRESHOLDS = {
    "AA_normal_text": 4.5,
    "AA_large_text": 3.0,
    "AAA_normal_text": 7.0,
    "non_text_ui": 3.0,
}


def fix_contrast(fg: RGB, bg: RGB, target: float = 4.5) -> RGB | None:
    """Подвигать светлоту fg (в OKLCH), сохранив тон и chroma, пока контраст с bg не достигнет target.
    Возвращает ближайший по светлоте цвет, прошедший порог, либо None."""
    L0, C0, h0 = lab_to_lch(rgb_to_oklab(np.asarray(fg, dtype=np.float64)))
    best, best_d = None, 9.0
    for L in np.linspace(0.0, 1.0, 201):
        cand = oklch_to_rgb(float(L), float(C0), float(h0))
        if float(contrast_ratio(cand, bg)) >= target and abs(L - L0) < best_d:
            best, best_d = cand, abs(L - L0)
    return best


# --- Дальтонизм (Machado et al. 2009, severity 1.0, в линейном RGB) ---------

CVD_MATRICES = {
    "protan": np.array([[0.152286, 1.052583, -0.204868],
                        [0.114503, 0.786281, 0.099216],
                        [-0.003882, -0.048116, 1.051998]]),
    "deutan": np.array([[0.367322, 0.860646, -0.227968],
                        [0.280085, 0.672501, 0.047413],
                        [-0.011820, 0.042940, 0.968881]]),
    "tritan": np.array([[1.255528, -0.076749, -0.178779],
                        [-0.078411, 0.930809, 0.147602],
                        [0.004733, 0.691367, 0.303900]]),
}


def simulate_cvd(rgb, kind: str):
    """Приближённая симуляция полной дихромазии. rgb (...,3) 0..255 -> (...,3) 0..255 (float)."""
    if kind not in CVD_MATRICES:
        raise ValueError(f"unknown CVD kind {kind!r}; use one of {list(CVD_MATRICES)}")
    lin = srgb_to_linear(np.asarray(rgb, dtype=np.float64) / 255.0)
    out = np.clip(lin @ CVD_MATRICES[kind].T, 0.0, 1.0)
    return linear_to_srgb(out) * 255.0


# --- HSL / hex / разбор ввода -------------------------------------------------

def rgb_to_hsl(rgb: Sequence[int]):
    r, g, b = [c / 255 for c in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return (round(h * 360, 2), round(s * 100, 2), round(l * 100, 2))


def hsl_to_rgb(h, s, l) -> RGB:
    r, g, b = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
    return (round(r * 255), round(g * 255), round(b * 255))


def to_hex(rgb: Iterable[int]) -> str:
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def parse_color(value) -> RGB:
    """Принимает '#2563eb', '2563eb', '#26e', [37,99,235] или {'r':..,'g':..,'b':..}."""
    if isinstance(value, str):
        m = _HEX.match(value.strip())
        if not m:
            raise ValueError(f"не удалось разобрать цвет {value!r}; ожидается hex вида #rrggbb")
        h = m.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    if isinstance(value, dict):
        value = [value.get("r"), value.get("g"), value.get("b")]
    try:
        r, g, b = (int(v) for v in value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"не удалось разобрать цвет {value!r}") from exc
    if not all(0 <= v <= 255 for v in (r, g, b)):
        raise ValueError(f"компоненты RGB должны быть в 0..255, получено {(r, g, b)}")
    return (r, g, b)
