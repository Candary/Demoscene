"""motus — детерминированный motion-core, управляемый текстовым запросом."""
from .core import MotusError, QueryError, Registry
from .mathx import QID, ONE, ZERO, compose, hash01, matmul, qaxis, qslerp
from .clock import LiveClock, Transport, fixed_frames
from .track import EASINGS, Kind, Track
from .scene import Scene, Transform
from .anim import Animator, Binding, CHANNELS, Mode, PROCS, ProcCall, ProcSpec
from .effects import EFFECTS, EffectSpec, EffectSystem, Emitter, ParamSpec
from .runtime import FramePlan, Report, Runtime
from . import query

__version__ = "0.1.0"
__all__ = [
    "MotusError", "QueryError", "Registry", "Transport", "LiveClock", "fixed_frames",
    "Kind", "Track", "EASINGS", "Scene", "Transform", "Animator", "Binding", "Mode",
    "CHANNELS", "PROCS", "ProcCall", "ProcSpec", "EFFECTS", "EffectSpec", "EffectSystem",
    "Emitter", "ParamSpec", "Runtime", "FramePlan", "Report", "query",
    "compose", "matmul", "qslerp", "qaxis", "hash01", "QID", "ONE", "ZERO",
]