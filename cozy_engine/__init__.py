"""Cozy Engine: корпус описаний сцен -> Cozy Matrix (64x64x64) -> инструменты для LLM, связанные с Color Matrix."""
from . import vocab
from .matrix import CozyMatrix
from .scenes import SceneStore

__all__ = ["vocab", "CozyMatrix", "SceneStore"]
