"""Uroboros: patch-driven, file-backed iterative pipeline with human approval."""
from .engine import Uroboros
from .formats import FORMAT, PatchError, canonical, digest
from .memory import FileMemory
from .plan import full_plan, load_plan, save_plan, simple_room_plan
from .registry import PatchRegistry

__all__ = [
    "Uroboros", "FORMAT", "PatchError", "canonical", "digest",
    "FileMemory", "PatchRegistry",
    "simple_room_plan", "full_plan", "load_plan", "save_plan",
]
__version__ = "0.3.0"