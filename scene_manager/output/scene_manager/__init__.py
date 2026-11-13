"""Scene Manager: Directed Timeline для демо без лимита размера (show.json -> baked -> рантайм)."""
from .effects import EffectCatalog
from .session import ShowSession, empty_show
from .timeline import compile_show

__all__ = ["EffectCatalog", "ShowSession", "empty_show", "compile_show"]
