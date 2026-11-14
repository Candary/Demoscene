"""Ошибки и универсальный реестр — единственная точка расширения для всех подсистем."""
from __future__ import annotations

from typing import Callable, Dict, Generic, Iterator, List, Optional, TypeVar


class MotusError(Exception):
    """Базовая ошибка motus."""


class QueryError(MotusError):
    """Ошибка разбора/валидации запроса. Ничего не применяется, если она есть."""

    def __init__(self, message: str, *, line: int = 0, fragment: str = "", hints=()):
        super().__init__(message)
        self.message = message
        self.line = line
        self.fragment = fragment
        self.hints = list(hints)

    def __str__(self) -> str:
        where = f"line {self.line}" if self.line else "query"
        near = f" near {self.fragment!r}" if self.fragment else ""
        hint = f" (доступно: {', '.join(self.hints[:8])})" if self.hints else ""
        return f"{where}: {self.message}{near}{hint}"


T = TypeVar("T")


class Registry(Generic[T]):
    """Имя -> объект. Защита от случайной перезаписи, детерминированный листинг."""

    def __init__(self, kind: str):
        self.kind = kind
        self._items: Dict[str, T] = {}

    def add(self, name: str, item: T, *, replace: bool = False) -> T:
        if not isinstance(name, str) or not name:
            raise MotusError(f"{self.kind}: имя должно быть непустой строкой")
        if item is None:
            raise MotusError(f"{self.kind}: нельзя регистрировать None")
        if name in self._items and not replace:
            raise MotusError(f"{self.kind} '{name}' уже зарегистрирован (replace=True)")
        self._items[name] = item
        return item

    def find(self, name: str) -> Optional[T]:
        return self._items.get(name)

    def get(self, name: str) -> T:
        item = self._items.get(name)
        if item is None:
            raise QueryError(f"неизвестный {self.kind} '{name}'",
                             fragment=name, hints=self.names())
        return item

    def names(self) -> List[str]:
        return sorted(self._items)

    def register(self, name: Optional[str] = None, *, replace: bool = False) -> Callable:
        def deco(obj):
            self.add(name or getattr(obj, "__name__", ""), obj, replace=replace)
            return obj
        return deco

    def __contains__(self, name: object) -> bool:
        return name in self._items

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)