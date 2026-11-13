"""Startup: paths + singleton readers (optimization: load once per session)."""
import sys, os

COZY_DIR = os.path.dirname(os.path.abspath(__file__))
COLOR_MATRIX_DIR = os.path.join(COZY_DIR, "..", "color_matrix", "output")

for p in [COZY_DIR, COLOR_MATRIX_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

_reader = None
_cozy_store = None
_cozy_matrix = None

def get_color_matrix_reader():
    global _reader
    if _reader is None:
        from color_matrix_python import FullRGBMatrixReader
        _reader = FullRGBMatrixReader(os.path.join(COLOR_MATRIX_DIR, "color-matrix-full-rgb-v11.npz"))
    return _reader

def get_cozy_store():
    global _cozy_store
    if _cozy_store is None:
        from cozy_engine.scenes import SceneStore
        _cozy_store = SceneStore.load(os.path.join(COZY_DIR, "data", "cozy_scenes.npz"))
    return _cozy_store

def get_cozy_matrix():
    global _cozy_matrix
    if _cozy_matrix is None:
        from cozy_engine.matrix import CozyMatrix
        _cozy_matrix = CozyMatrix.load(os.path.join(COZY_DIR, "data", "cozy_matrix.npz"))
    return _cozy_matrix

def get_unified_toolbox():
    from color_matrix_python.tools import ColorToolbox
    from cozy_engine.tools import CozyToolbox, UnifiedToolbox
    cm_tb = ColorToolbox(get_color_matrix_reader())
    cozy_tb = CozyToolbox.from_dir(os.path.join(COZY_DIR, "data"), cm_tb)
    return UnifiedToolbox(cm_tb, cozy_tb)
