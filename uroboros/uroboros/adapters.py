"""Bridges to Color Matrix and Cozy Engine with graceful degradation.

Both subsystems are optional. If importable (installed or found via env var),
adapters call them; otherwise functions return a clear "unavailable" marker and
the calling patch falls back to hardcoded behavior.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CACHE: dict[str, object] = {}


# --- поиск пакета -----------------------------------------------------------

def _try_import(module: str, candidates: list[Path]) -> bool:
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        pass
    for cand in candidates:
        if cand and cand.is_dir():
            parent = str(cand.parent)
            if parent not in sys.path:
                sys.path.insert(0, parent)
            try:
                importlib.import_module(module)
                return True
            except ImportError:
                continue
    return False


def _color_candidates() -> list[Path]:
    env = os.environ.get("UROBOROS_COLOR_MATRIX_PATH")
    return [p for p in [
        Path(env) / "color_matrix_python" if env else None,
        _PROJECT_ROOT / "color_matrix_python",
        _PROJECT_ROOT / "Color matrix",
        _PROJECT_ROOT.parent / "color_matrix_python",
    ] if p]


def _cozy_candidates() -> list[Path]:
    env = os.environ.get("UROBOROS_COZY_PATH")
    return [p for p in [
        Path(env) / "cozy_engine" if env else None,
        _PROJECT_ROOT / "cozy_engine",
        _PROJECT_ROOT / "Cozy Engine",
        _PROJECT_ROOT.parent / "cozy_engine",
    ] if p]


def color_matrix_available() -> bool:
    if "cm_avail" not in _CACHE:
        _CACHE["cm_avail"] = _try_import("color_matrix_python", _color_candidates())
    return bool(_CACHE["cm_avail"])


def cozy_engine_available() -> bool:
    if "cozy_avail" not in _CACHE:
        _CACHE["cozy_avail"] = _try_import("cozy_engine", _cozy_candidates())
    return bool(_CACHE["cozy_avail"])


# --- Color Matrix -----------------------------------------------------------

def get_color_toolbox():
    """Return a ColorToolbox if both package and .npz are available, else None."""
    if "cm_toolbox" in _CACHE:
        return _CACHE["cm_toolbox"]
    if not color_matrix_available():
        _CACHE["cm_toolbox"] = None
        return None
    npz = os.environ.get("UROBOROS_COLOR_MATRIX_NPZ")
    if not npz or not Path(npz).exists():
        _CACHE["cm_toolbox"] = None
        return None
    from color_matrix_python.reader import FullRGBMatrixReader
    from color_matrix_python.tools import ColorToolbox
    reader = FullRGBMatrixReader(npz)
    _CACHE["cm_toolbox"] = ColorToolbox(reader)
    return _CACHE["cm_toolbox"]


MOOD_TO_FEEL = {
    "quiet_warm": "warmth",
    "energetic": "delight",
    "calm": "neutral",
    "tense": "tension",
    "anxious": "anxiety",
}


def build_palette_via_matrix(mood: str, scheme: str, size: int) -> dict:
    tb = get_color_toolbox()
    if tb is None:
        return {"ok": False, "error": "Color Matrix not available (set UROBOROS_COLOR_MATRIX_NPZ)"}
    feel = MOOD_TO_FEEL.get(mood, "warmth")
    base_res = tb.dispatch("find_colors", {"feel": feel, "min_chroma": 0.08, "count": 1})
    if base_res.get("error") or not base_res.get("candidates"):
        return {"ok": False, "error": base_res.get("error") or "no base color"}
    base = base_res["candidates"][0]["hex"]
    pal = tb.dispatch("build_palette", {"base": base, "scheme": scheme, "size": size})
    if pal.get("error"):
        return {"ok": False, "error": pal["error"]}
    return {
        "ok": True,
        "base": base,
        "palette": [c["hex"] for c in pal["colors"]],
        "profiles": pal["colors"],
        "checks": pal.get("check", {}),
    }


def describe_color_via_matrix(color: str) -> dict:
    tb = get_color_toolbox()
    if tb is None:
        return {"ok": False, "error": "Color Matrix not available", "color": color}
    res = tb.dispatch("describe_color", {"color": color})
    if res.get("error"):
        return {"ok": False, "error": res["error"], "color": color}
    return {"ok": True, **res}


# --- Cozy Engine ------------------------------------------------------------

def get_cozy_toolbox():
    """Return a CozyToolbox if CozyMatrix + ColorToolbox + npz files are available."""
    if "cozy_toolbox" in _CACHE:
        return _CACHE["cozy_toolbox"]
    if not cozy_engine_available():
        _CACHE["cozy_toolbox"] = None
        return None
    cozy_npz = os.environ.get("UROBOROS_COZY_MATRIX_NPZ")
    if not cozy_npz or not Path(cozy_npz).exists():
        _CACHE["cozy_toolbox"] = None
        return None
    color_tb = get_color_toolbox()
    if color_tb is None:
        _CACHE["cozy_toolbox"] = None
        return None
    from cozy_engine.matrix import CozyMatrix
    from cozy_engine.tools import CozyToolbox
    matrix = CozyMatrix.load(cozy_npz)
    _CACHE["cozy_toolbox"] = CozyToolbox(matrix, color_tb)
    return _CACHE["cozy_toolbox"]


def plan_room_via_cozy(room: str, count: int) -> dict:
    tb = get_cozy_toolbox()
    if tb is None:
        return {"ok": False, "error": "Cozy Engine not configured "
                                      "(set UROBOROS_COZY_MATRIX_NPZ and UROBOROS_COLOR_MATRIX_NPZ)",
                "room": room}
    res = tb.dispatch("cozy_scene_plan", {"room": room, "count": count})
    if res.get("error"):
        return {"ok": False, "error": res["error"], "room": room}
    return {"ok": True, **res}