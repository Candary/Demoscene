"""Сцена: базовая поза (данные) отделена от вычисленной позы (результат анимации)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .core import MotusError, QueryError
from .mathx import IDENTITY, ONE, QID, ZERO, Mat4, Quat, Vec3, compose, matmul, qnorm, vec


@dataclass
class Transform:
    pos: Vec3 = ZERO
    rot: Quat = QID
    scale: Vec3 = ONE

    def copy(self) -> "Transform":
        return Transform(self.pos, self.rot, self.scale)


class Entity:
    __slots__ = ("eid", "name", "parent", "children", "base", "pose", "params", "alive", "tag")

    def __init__(self, eid: int, name: str, base: Transform):
        self.eid = eid
        self.name = name
        self.parent: Optional[int] = None
        self.children: List[int] = []
        self.base = base
        self.pose = base.copy()
        self.params: Dict[str, Any] = {}
        self.alive = True
        self.tag = ""


class Scene:
    """O(N) обход: preorder кэшируется, матрицы пересчитываются только у грязных поддеревьев."""

    def __init__(self):
        self._e: List[Entity] = []
        self._by_name: Dict[str, int] = {}
        self._order: List[int] = []
        self._topo_dirty = True
        self._pose_dirty: List[bool] = []
        self._changed: List[bool] = []
        self._local: List[Mat4] = []
        self._world: List[Mat4] = []

    def __len__(self) -> int:
        return len(self._e)

    def names(self) -> List[str]:
        return sorted(self._by_name)

    def entity(self, eid: int) -> Entity:
        return self._e[eid]

    def find(self, name: str) -> Optional[int]:
        return self._by_name.get(name)

    def id_of(self, name: str) -> int:
        eid = self._by_name.get(name)
        if eid is None:
            raise QueryError(f"объект '{name}' не существует", fragment=name, hints=self.names())
        return eid

    def add(self, name: Optional[str] = None, parent: Optional[int] = None, *,
            pos=ZERO, rot=QID, scale=ONE, params: Optional[dict] = None) -> int:
        eid = len(self._e)
        name = name or f"e{eid}"
        if name in self._by_name:
            raise MotusError(f"имя '{name}' уже занято")
        base = Transform(vec(pos, 3), qnorm(vec(rot, 4)), vec(scale, 3))
        ent = Entity(eid, name, base)
        if params:
            ent.params.update(params)
        self._e.append(ent)
        self._by_name[name] = eid
        self._pose_dirty.append(True)
        self._changed.append(False)
        self._local.append(IDENTITY)
        self._world.append(IDENTITY)
        self._topo_dirty = True
        if parent is not None:
            self.set_parent(eid, parent)
        return eid

    def set_parent(self, child: int, parent: Optional[int]) -> None:
        if parent is not None:
            if parent == child:
                raise MotusError("объект не может быть родителем самому себе")
            p: Optional[int] = parent
            while p is not None:
                if p == child:
                    raise MotusError("цикл в иерархии")
                p = self._e[p].parent
        ent = self._e[child]
        if ent.parent is not None:
            self._e[ent.parent].children.remove(child)
        ent.parent = parent
        if parent is not None:
            self._e[parent].children.append(child)
        self._topo_dirty = True
        self.mark(child)

    def mark(self, eid: int) -> None:
        self._pose_dirty[eid] = True

    def reset_pose(self, eid: int) -> None:
        ent = self._e[eid]
        ent.pose = ent.base.copy()
        self._pose_dirty[eid] = True

    def drop(self, eid: int) -> None:
        self._e[eid].alive = False

    def world(self, eid: int) -> Mat4:
        return self._world[eid]

    def _rebuild_order(self) -> None:
        order: List[int] = []
        stack = [e.eid for e in reversed(self._e) if e.parent is None]
        while stack:
            eid = stack.pop()
            order.append(eid)
            stack.extend(reversed(self._e[eid].children))
        self._order = order
        self._topo_dirty = False

    def update(self) -> None:
        if self._topo_dirty:
            self._rebuild_order()
        changed = self._changed
        for eid in self._order:
            ent = self._e[eid]
            dirty = self._pose_dirty[eid]
            if dirty:
                p = ent.pose
                self._local[eid] = compose(p.pos, p.rot, p.scale)
                self._pose_dirty[eid] = False
            par = ent.parent
            if par is not None and changed[par]:
                dirty = True
            if dirty:
                self._world[eid] = (self._local[eid] if par is None
                                    else matmul(self._world[par], self._local[eid]))
            changed[eid] = dirty