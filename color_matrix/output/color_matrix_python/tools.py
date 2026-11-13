"""Инструменты для LLM (function calling). Схемы в формате OpenAI/GLM `tools=[{"type":"function",...}]`.

Принцип: матрица — только один из источников. Контраст, различимость и дальтонизм считаются детерминированно,
потому что их нельзя «прочувствовать» — их можно только измерить.
"""
from __future__ import annotations

import json
import math
from typing import Any

import numpy as np

from . import vocab
from .colorspace import (CVD_MATRICES, WCAG_THRESHOLDS, contrast_ratio, delta_e_ok, fix_contrast, lab_to_lch,
                         oklch_to_rgb, parse_color, rgb_to_oklab, simulate_cvd, to_hex)
from .reader import FullRGBMatrixReader
from .search import SearchIndex, TEMP_WORDS, WEIGHT_WORDS

PROVENANCE = ("prior-модель: значения заданы формулами, не измерены на людях. Эмпатия культурно-зависима; "
              "intensity не учитывает тон; различия эмпатии < ~15 пунктов не считать значимыми.")

_HEX = {"type": "string", "description": "Color as hex, e.g. '#2563eb'."}


def from_glsl(vec3_str):
    """Convert GLSL vec3 string to RGB tuple (0-255 int).
    Input: 'vec3(0.10, 0.40, 0.80)' or (0.10, 0.40, 0.80) tuple
    Output: (26, 102, 204)
    """
    import re
    if isinstance(vec3_str, str):
        m = re.match(r'vec3\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)', vec3_str.strip())
        if not m:
            raise ValueError(f"Cannot parse vec3: {vec3_str}")
        r, g, b = float(m.group(1)), float(m.group(2)), float(m.group(3))
    else:
        r, g, b = vec3_str[0], vec3_str[1], vec3_str[2]
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def to_glsl(rgb):
    """Convert RGB tuple (0-255) to GLSL vec3 string.
    Input: (26, 102, 204) or '#1a66cc'
    Output: 'vec3(0.102, 0.400, 0.800)'
    """
    if isinstance(rgb, str) and rgb.startswith('#'):
        rgb = parse_color(rgb)
    r, g, b = rgb[0], rgb[1], rgb[2]
    return f"vec3({r/255:.3f}, {g/255:.3f}, {b/255:.3f})"

TOOL_SCHEMAS: list[dict] = [
    {"type": "function", "function": {
        "name": "describe_color",
        "description": ("Look up the Color Matrix profile of one exact sRGB color: perceptual values (OKLCH), "
                        "empathy (emotional reaction, -100..100), intensity (visual load, 0..100), synesthesia levels, "
                        "WCAG contrast against white/black. Use it to ASSESS a color you are considering or that the user gave. "
                        "Values are a prior model, not measurements; they never override contrast or brand constraints."),
        "parameters": {"type": "object", "properties": {"color": _HEX}, "required": ["color"]}}},
    {"type": "function", "function": {
        "name": "find_colors",
        "description": ("Search the matrix for real colors that satisfy a desired feel AND hard constraints. "
                        "Returns up to `count` diverse candidates plus `diagnostics` showing how many colors remain after each "
                        "constraint (if 0 results, relax the constraint where 'remaining' collapses). "
                        "Prefer passing `background` + `min_contrast` whenever the color will carry text or an icon."),
        "parameters": {"type": "object", "properties": {
            "feel": {"type": "string", "enum": vocab.EMPATHY,
                     "description": "Target emotional reaction (empathy label)."},
            "intensity": {"type": "array", "items": {"type": "string", "enum": vocab.ENTROPY_INTENSITY},
                          "description": "Allowed visual-intensity levels. Note: intensity ignores hue."},
            "temperature": {"type": "array", "items": {"type": "string", "enum": TEMP_WORDS + ["warm_side", "cool_side"]}},
            "weight": {"type": "array", "items": {"type": "string", "enum": WEIGHT_WORDS},
                       "description": "light = bright colors, heavy = dark colors."},
            "hue_range": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2,
                          "description": "OKLCH hue [from, to] in degrees, wraps around 360. Red~25, orange~60, yellow~100, green~145, cyan~200, blue~260, purple~305, pink~350."},
            "lightness_range": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2,
                                "description": "OKLCH lightness [min, max] within 0..1."},
            "min_chroma": {"type": "number", "description": "OKLCH chroma lower bound (~0.03 grayish, ~0.1 clearly colored, ~0.2 vivid)."},
            "max_chroma": {"type": "number"},
            "background": {**_HEX, "description": "Background the color will be placed on."},
            "min_contrast": {"type": "number", "description": "Required WCAG contrast ratio against `background` (4.5 text, 3 large text/UI)."},
            "count": {"type": "integer", "minimum": 1, "maximum": 12, "default": 5},
            "min_delta_e": {"type": "number", "default": 0.06,
                            "description": "Minimum OKLab distance between returned candidates (variety)."}}}}},
    {"type": "function", "function": {
        "name": "check_contrast",
        "description": ("Compute the WCAG 2.x contrast ratio of a foreground color on a background and report AA/AAA pass/fail. "
                        "If it fails AA for normal text, returns `suggested_foreground`: the closest color with the same hue and "
                        "chroma that passes. Always use this before finalizing any text or icon color."),
        "parameters": {"type": "object", "properties": {
            "foreground": _HEX, "background": _HEX,
            "target": {"type": "number", "default": 4.5, "description": "Ratio to reach for the suggestion."}},
            "required": ["foreground", "background"]}}},
    {"type": "function", "function": {
        "name": "build_palette",
        "description": ("Generate a harmonic palette from a base color in OKLCH (gamut-safe). Each color comes with its matrix "
                        "profile, and the palette is automatically checked for distinguishability (incl. color-vision deficiency) "
                        "and for contrast with `background` if given."),
        "parameters": {"type": "object", "properties": {
            "base": _HEX,
            "scheme": {"type": "string", "enum": ["analogous", "complementary", "triadic", "split_complementary", "tonal"]},
            "size": {"type": "integer", "minimum": 2, "maximum": 10, "default": 5},
            "background": _HEX},
            "required": ["base", "scheme"]}}},
    {"type": "function", "function": {
        "name": "check_palette",
        "description": ("Check that colors in a palette are mutually distinguishable (normal vision + protan/deutan/tritan simulation) "
                        "and, if `background` is given, how each contrasts with it. Use for charts, status colors, tags."),
        "parameters": {"type": "object", "properties": {
            "colors": {"type": "array", "items": _HEX, "minItems": 2, "maxItems": 12},
            "background": _HEX,
            "min_delta_e": {"type": "number", "default": 0.06}},
            "required": ["colors"]}}},
    {"type": "function", "function": {
        "name": "check_palette_harmony",
        "description": ("Classify the color harmony of 2-6 colors (complementary / analogous / triadic / "
                        "split_complementary / none) by hue distance, with a 0..1 score. Use to validate that a palette "
                        "of independently chosen colors still reads as harmonic."),
        "parameters": {"type": "object", "properties": {
            "colors": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6,
                       "description": "Hex strings (e.g. '#1a66cc') or RGB tuples."}},
            "required": ["colors"]}}},
    {"type": "function", "function": {
        "name": "find_multi_colors",
        "description": ("Find multiple colors, each matching a different emotional `feel` and tagged with a role "
                        "(e.g. background / accent), then check the harmony between them. Returns one candidate per "
                        "target plus a harmony report."),
        "parameters": {"type": "object", "properties": {
            "targets": {"type": "array", "items": {"type": "object"}, "minItems": 2, "maxItems": 6,
                        "description": "List of {feel, role}. feel must be in vocab.EMPATHY."},
            "harmony": {"type": "string", "enum": ["complementary", "analogous", "triadic", "none"],
                         "default": "complementary"},
            "count": {"type": "integer", "minimum": 1, "maximum": 12, "default": 1},
            "random": {"type": "boolean", "default": False}},
            "required": ["targets"]}}},
    {"type": "function", "function": {
        "name": "find_animation_path",
        "description": ("Build a perceptually-uniform animation gradient from one emotional state to another: "
                        "pick endpoints by `feel`, then linearly interpolate in sRGB between them and label each "
                        "intermediate step with the matrix cell it lands on. Use for transitions, loaders, mood shifts."),
        "parameters": {"type": "object", "properties": {
            "from_state": {"type": "object", "description": "{'feel': <empathy label>}."},
            "to_state": {"type": "object", "description": "{'feel': <empathy label>}."},
            "steps": {"type": "integer", "minimum": 2, "maximum": 12, "default": 5}},
            "required": ["from_state", "to_state"]}}},
]


def _r(x, n=3):
    return round(float(x), n)


class ColorToolbox:
    def __init__(self, reader: FullRGBMatrixReader, index: SearchIndex | None = None):
        self.reader = reader
        self.index = index or SearchIndex(reader)
        self._tools = {
            "describe_color": self.describe_color, "find_colors": self.find_colors,
            "check_contrast": self.check_contrast, "build_palette": self.build_palette,
            "check_palette": self.check_palette,
            "check_palette_harmony": self.check_palette_harmony,
            "find_multi_colors": self.find_multi_colors,
            "find_animation_path": self.find_animation_path,
        }

    # -- диспетчер -----------------------------------------------------------
    def dispatch(self, name: str, arguments: str | dict | None = None) -> dict:
        try:
            args = json.loads(arguments) if isinstance(arguments, str) and arguments.strip() else (arguments or {})
            if not isinstance(args, dict):
                raise ValueError("arguments должны быть JSON-объектом")
            fn = self._tools.get(name)
            if fn is None:
                return {"error": f"неизвестный инструмент {name!r}", "available": sorted(self._tools)}
            return fn(**args)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    # -- инструменты ---------------------------------------------------------
    def describe_color(self, color) -> dict:
        rgb = parse_color(color)
        c = self.reader.get_cell(rgb)
        cr_w = float(contrast_ratio(rgb, (255, 255, 255)))
        cr_b = float(contrast_ratio(rgb, (0, 0, 0)))
        return {
            "hex": c.hex, "hsl": list(c.hsl), "oklch": {"L": c.oklch[0], "C": c.oklch[1], "h": c.oklch[2]},
            "empathy": {"label": c.empathy.label, "score": c.empathy.score, "confidence": c.empathy.confidence,
                        "meaning": c.empathy.description},
            "intensity": {"label": c.entropy.label, "score": c.entropy.score, "confidence": c.entropy.confidence,
                          "meaning": c.entropy.description},
            "synesthesia": {t["dimension"]: {"level": t["value"], "of": t["max"], "word": t["word"], "driver": t["driver"]}
                            for t in c.synesthesia_tags},
            "contrast": {"vs_white": _r(cr_w, 2), "vs_black": _r(cr_b, 2),
                         "best_text_color": "#ffffff" if cr_w >= cr_b else "#000000"},
            "warnings": c.warnings, "provenance": PROVENANCE, "dataset_version": c.dataset_version,
        }

    def find_colors(self, **kwargs) -> dict:
        res = self.index.find(**kwargs)
        res["provenance"] = PROVENANCE
        res["dataset_version"] = self.reader.dataset_version
        return res

    def check_contrast(self, foreground, background, target: float = 4.5) -> dict:
        fg, bg = parse_color(foreground), parse_color(background)
        ratio = float(contrast_ratio(fg, bg))
        out = {"foreground": to_hex(fg), "background": to_hex(bg), "ratio": _r(ratio, 2),
               "passes": {k: ratio >= v for k, v in WCAG_THRESHOLDS.items()}}
        if ratio < target:
            fixed = fix_contrast(fg, bg, target)
            out["suggested_foreground"] = to_hex(fixed) if fixed else None
            if fixed:
                out["suggested_ratio"] = _r(float(contrast_ratio(fixed, bg)), 2)
        return out

    def build_palette(self, base, scheme: str, size: int = 5, background=None) -> dict:
        size = int(min(max(size, 2), 10))
        rgb0 = parse_color(base)
        L0, C0, h0 = (float(v) for v in lab_to_lch(rgb_to_oklab(np.array(rgb0, dtype=np.float64))))
        sets = {"complementary": [0, 180], "triadic": [0, 120, 240], "split_complementary": [0, 150, 210]}
        lch: list[tuple[float, float, float]] = []
        if scheme == "tonal":
            lch = [(float(L), C0, h0) for L in np.linspace(0.95, 0.25, size)]
        elif scheme == "analogous":
            lch = [(L0, C0, (h0 + (i - size // 2) * 25) % 360) for i in range(size)]
        elif scheme in sets:
            hs = sets[scheme]
            for i in range(size):
                cycle = i // len(hs)
                dL = 0.0 if cycle == 0 else (0.12 * ((cycle + 1) // 2)) * (1 if cycle % 2 else -1)
                lch.append((min(0.95, max(0.2, L0 + dL)), C0, (h0 + hs[i % len(hs)]) % 360))
        else:
            raise ValueError(f"scheme: неизвестное значение {scheme!r}")

        colors = []
        for L, C, h in lch:
            rgb = oklch_to_rgb(L, C, h)
            cell = self.reader.get_cell(rgb)
            colors.append({"hex": to_hex(rgb), "oklch": [_r(L), _r(C), _r(h, 1)],
                           "empathy": {"label": cell.empathy.label, "score": cell.empathy.score},
                           "intensity": {"label": cell.entropy.label, "score": cell.entropy.score},
                           "temperature": TEMP_WORDS[cell.synesthesia_tags[0]["value"]]})
        check = self.check_palette([c["hex"] for c in colors], background=background)
        return {"scheme": scheme, "base": to_hex(rgb0), "colors": colors, "check": check, "provenance": PROVENANCE}

    def check_palette(self, colors, background=None, min_delta_e: float = 0.06) -> dict:
        rgbs = [parse_color(c) for c in colors]
        if not 2 <= len(rgbs) <= 12:
            raise ValueError("нужно от 2 до 12 цветов")
        arr = np.array(rgbs, dtype=np.float64)
        iu = np.triu_indices(len(rgbs), 1)
        views = {"normal": arr, **{k: simulate_cvd(arr, k) for k in CVD_MATRICES}}
        report, problems = {}, []
        for name, view in views.items():
            lab = rgb_to_oklab(view)
            d = delta_e_ok(lab[iu[0]], lab[iu[1]])
            bad = [(int(i), int(j), _r(v)) for i, j, v in zip(iu[0], iu[1], d) if v < min_delta_e]
            report[name] = {"min_delta_e": _r(d.min()), "too_similar_pairs": [
                {"a": to_hex(rgbs[i]), "b": to_hex(rgbs[j]), "delta_e": v} for i, j, v in bad[:6]]}
            if bad:
                problems.append(f"{name}: {len(bad)} пар(ы) ближе {min_delta_e}")
        out: dict[str, Any] = {"distinguishability": report}
        if background is not None:
            bg = parse_color(background)
            ratios = [float(contrast_ratio(c, bg)) for c in rgbs]
            out["contrast_vs_background"] = [{"hex": to_hex(c), "ratio": _r(r, 2), "ok_non_text_3": r >= 3,
                                              "ok_text_4_5": r >= 4.5} for c, r in zip(rgbs, ratios)]
            low = [to_hex(c) for c, r in zip(rgbs, ratios) if r < 3]
            if low:
                problems.append(f"контраст с фоном < 3: {', '.join(low)}")
        out["ok"] = not problems
        out["problems"] = problems
        return out

    # -- harmony / multi-target / animation -------------------------------
    def check_palette_harmony(self, colors):
        """Check color harmony (complementary/analogous/triadic/none).

        Input: colors = list of hex strings or RGB tuples, 1-6 colors
        Output: {
            "harmony_type": "complementary"|"analogous"|"triadic"|"split_complementary"|"none"|"single",
            "score": 0.0-1.0,
            "hue_distances": [degrees between consecutive colors],
            "analysis": "human-readable description"
        }
        """
        import colorsys

        # Convert all to RGB then to HSL hue
        rgb_list = []
        for c in colors:
            if isinstance(c, str):
                rgb_list.append(parse_color(c))
            else:
                rgb_list.append(tuple(c))

        # Calculate hues (colorsys returns h in [0,1]; multiply by 360)
        hues = []
        for rgb in rgb_list:
            r, g, b = rgb[0] / 255, rgb[1] / 255, rgb[2] / 255
            h, _s, _l = colorsys.rgb_to_hls(r, g, b)
            hues.append(h * 360)

        n = len(hues)
        # Pairwise hue distances (circular)
        distances = []
        for i in range(n):
            for j in range(i + 1, n):
                d = abs(hues[i] - hues[j]) % 360
                d = min(d, 360 - d)
                distances.append(d)

        if not distances:
            return {"harmony_type": "single", "score": 1.0, "hue_distances": [],
                    "analysis": "Single color"}

        min_dist = min(distances)
        max_dist = max(distances)

        # Complementary: ~180°
        if 150 <= max_dist <= 210:
            harmony = "complementary"
            score = 1.0 - abs(max_dist - 180) / 30
        # Triadic: ~120° (both min and max near 120)
        elif 100 <= min_dist <= 140 and 100 <= max_dist <= 140:
            harmony = "triadic"
            score = 1.0 - abs(min_dist - 120) / 20
        # Analogous: small spread
        elif max_dist <= 60:
            harmony = "analogous"
            score = 1.0 - max_dist / 60
        # Split complementary: one pair ~180°, another close
        elif 150 <= max_dist <= 210 and min_dist <= 60:
            harmony = "split_complementary"
            score = 0.8
        else:
            harmony = "none"
            score = 0.3

        score = max(0.0, min(1.0, score))
        analysis = (f"{harmony} harmony (score {score:.2f}), "
                    f"hue distances: {[round(d) for d in distances]}")

        return {
            "harmony_type": harmony,
            "score": round(score, 3),
            "hue_distances": [round(d, 1) for d in distances],
            "analysis": analysis,
        }

    def find_multi_colors(self, targets, harmony="complementary", count=1, random=False):
        """Find multiple colors with different emotions, checking harmony.

        Input: targets = [{"feel": "anxiety", "role": "background"}, {"feel": "warmth", "role": "accent"}]
               harmony = "complementary"|"analogous"|"triadic"|"none"
        Output: {"colors": [...], "harmony": {...}, "n_targets": ...}
        """
        if not hasattr(self, '_search_index'):
            self._search_index = SearchIndex(self.reader)
        si = self._search_index

        results = []
        for target in targets:
            feel = target.get("feel")
            role = target.get("role", "unknown")
            # SearchIndex.find doesn't accept `random`; ignore it (kept in signature for schema parity).
            r = si.find(feel=feel, count=count, random=random)
            if r.get("candidates"):
                results.append({
                    "role": role,
                    "feel": feel,
                    "color": r["candidates"][0] if count == 1 else r["candidates"],
                })

        # Collect all hex codes for harmony check (color can be a dict or a list of dicts)
        all_colors = []
        for r in results:
            c = r["color"]
            if isinstance(c, dict):
                all_colors.append(c["hex"])
            else:  # list of dicts (count > 1)
                all_colors.extend(item["hex"] for item in c)

        if len(all_colors) >= 2:
            harmony_check = self.check_palette_harmony(all_colors)
        else:
            harmony_check = {"harmony_type": "single", "score": 1.0,
                             "hue_distances": [], "analysis": "Fewer than 2 colors found"}

        return {
            "colors": results,
            "harmony": harmony_check,
            "n_targets": len(targets),
            "requested_harmony": harmony,
        }

    def find_animation_path(self, from_state, to_state, steps=5):
        """Find N colors forming a gradient from one emotional state to another.

        Input: from_state = {"feel": "anxiety"}, to_state = {"feel": "delight"}, steps=5
        Output: {"path": [color1, color2, ..., colorN], "from": ..., "to": ..., "steps": ...}
        """
        if not hasattr(self, '_search_index'):
            self._search_index = SearchIndex(self.reader)
        si = self._search_index

        steps = int(min(max(steps, 2), 12))

        # Get endpoints
        r1 = si.find(feel=from_state.get("feel"), count=1)
        r2 = si.find(feel=to_state.get("feel"), count=1)

        if not r1.get("candidates") or not r2.get("candidates"):
            return {"path": [], "error": "Could not find endpoints",
                    "from": from_state, "to": to_state}

        c1 = r1["candidates"][0]
        c2 = r2["candidates"][0]

        # Interpolate in sRGB (perceptually reasonable approximation within gamut)
        rgb1 = np.array(c1["rgb"], dtype=float)
        rgb2 = np.array(c2["rgb"], dtype=float)

        path = [c1]
        for i in range(1, steps - 1):
            t = i / (steps - 1)
            rgb_mid = rgb1 * (1 - t) + rgb2 * t
            rgb_mid_int = tuple(int(round(v)) for v in rgb_mid)
            cell = self.reader.get_cell(rgb_mid_int)
            path.append({
                "hex": to_hex(rgb_mid_int),
                "rgb": list(rgb_mid_int),
                "empathy": {"label": cell.empathy.label, "score": cell.empathy.score},
                "t": round(t, 2),
            })
        path.append(c2)

        return {
            "path": path,
            "from": from_state,
            "to": to_state,
            "steps": steps,
        }
