"""Runtime: submit(text) -> события и биндинги; frame(t) -> FramePlan.

Скраб назад переигрывает события с нуля — поэтому кадр N всегда одинаков,
независимо от того, как мы к нему пришли.
"""
from __future__ import annotations

import copy
import math
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .anim import Animator, Binding, Mode, ProcCall, resolve_channel
from .clock import Transport
from .core import MotusError, QueryError
from .effects import EFFECTS, EffectSystem, Field, compute_field
from .mathx import IDENTITY, Mat4, translation
from .query import Cmd, parse
from .scene import Scene
from .track import Kind, Track, coerce, kind_of

EVENT_OPS = ("new", "set", "drop")


@dataclass
class DrawItem:
    entity: int
    name: str
    world: Mat4
    params: Dict[str, Any]


@dataclass
class Batch:
    emitter: int
    effect: str
    count: int
    origin: tuple
    data: Optional[Field]


@dataclass
class Post:
    effect: str
    params: Dict[str, Any]


@dataclass
class FramePlan:
    time: float
    items: List[DrawItem] = field(default_factory=list)
    batches: List[Batch] = field(default_factory=list)
    posts: List[Post] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Report:
    ok: bool
    applied: int
    issues: List[QueryError] = field(default_factory=list)
    mode: str = "auto"

    def __str__(self) -> str:
        if self.ok:
            return f"ok: применено {self.applied} команд (режим {self.mode})"
        return "\n".join(str(i) for i in self.issues)


class Runtime:
    def __init__(self, transport: Optional[Transport] = None, *, mode: str = "auto",
                 max_particles: int = 200_000, particles: bool = True):
        self.transport = transport or Transport()
        self.mode = mode
        self.particles = particles
        self.scene = Scene()
        self.animator = Animator()
        self.effects = EffectSystem(max_particles)
        self._events: List[Cmd] = []
        self._times: List[float] = []
        self._applied = 0
        self._free_state: Dict[str, Any] = {}
        # P1 fix: instance-level _static (was class-level — shared state bug)
        self._static: List[Cmd] = []

    # -------------------------------------------------------- ввод
    def submit(self, text: str) -> Report:
        res = parse(text, mode=self.mode, transport=self.transport, state=self._free_state)
        self.mode = res.mode
        if res.issues:
            return Report(False, 0, res.issues, self.mode)
        snap = self._snapshot()
        try:
            for c in res.commands:
                self._ingest(c)
        except MotusError as exc:
            self._restore(snap)
            return Report(False, 0, [exc if isinstance(exc, QueryError)
                                     else QueryError(str(exc))], self.mode)
        self._events.sort(key=lambda c: c.at)
        self._times = [c.at for c in self._events]
        self._applied = 0
        self.scene = Scene()
        self._rewind_effects()
        return Report(True, len(res.commands), [], self.mode)

    def _rewind_effects(self) -> None:
        self.effects.emitters.clear()
        self.effects.posts.clear()
        self.effects._next = 0
        self.animator = Animator()
        for c in self._static:
            self._ingest_timeless(c)

    def _ingest(self, c: Cmd) -> None:
        if c.op in EVENT_OPS:
            self._events.append(c)
        else:
            self._static.append(c)
            self._ingest_timeless(c)


    def _ingest_timeless(self, c: Cmd) -> None:
        if c.op == "anim":
            kind = kind_of(c.keys[0][1])
            tr = Track(kind, ease=c.ease)
            tr.keys(c.keys)
            dur = c.duration or (tr.span[1] - tr.span[0])
            self.animator.add(Binding(c.name, c.channel, tr, Mode(c.mode), c.weight,
                                      c.priority, c.at, dur, c.loop))
        elif c.op == "proc":
            call = ProcCall(c.proc, dict(c.values), c.seed)
            self.animator.add(Binding(c.name, c.channel, call, Mode(c.mode), c.weight,
                                      c.priority, c.at, c.duration, c.loop))
        elif c.op == "fx":
            spec = EFFECTS.get(c.effect)
            if spec.kind == "emitter":
                vals = dict(c.values)
                origin = vals.pop("origin", (0.0, 0.0, 0.0))
                self.effects.spawn(c.effect, origin=origin, start=c.at, duration=c.duration,
                                   count=c.count, seed=c.seed, attach=c.attach or None, **vals)
            elif spec.kind == "post":
                self.effects.post(c.effect, start=c.at, duration=c.duration, **c.values)
            else:
                if not c.attach:
                    raise QueryError(f"эффект '{c.effect}' требует on=<объект>")
                self.animator.add(Binding(c.attach, spec.channel,
                                          ProcCall(spec.proc, {}, c.seed),
                                          Mode.ADD, 1.0, 0, c.at, c.duration, "hold"))
        else:
            raise QueryError(f"неизвестная операция '{c.op}'")

    # -------------------------------------------------------- события
    def _apply_event(self, c: Cmd) -> None:
        if c.op == "new":
            parent = self.scene.find(c.parent) if c.parent else None
            if c.parent and parent is None:
                raise QueryError(f"родитель '{c.parent}' не существует")
            pose = {k: v for k, v in c.values.items() if k in ("pos", "rot", "scale")}
            params = {k[6:]: v for k, v in c.values.items() if k.startswith("param.")}
            self.scene.add(c.name, parent, params=params, **pose)
        elif c.op == "set":
            eid = self.scene.id_of(c.name)
            ent = self.scene.entity(eid)
            value = c.values["v"]
            spec = resolve_channel(c.channel, kind_of(value))
            v = coerce(spec.kind, value)
            if spec.is_param:
                ent.params[spec.key] = v
            else:
                spec.put(ent.base, v)
                spec.put(ent.pose, v)
            self.scene.mark(eid)
        elif c.op == "drop":
            self.scene.drop(self.scene.id_of(c.name))
        else:
            raise QueryError(f"не событие: {c.op}")

    def _advance(self, t: float) -> None:
        k = bisect_right(self._times, t)
        if k < self._applied:
            self.scene = Scene()
            self._applied = 0
        while self._applied < k:
            self._apply_event(self._events[self._applied])
            self._applied += 1

    # -------------------------------------------------------- кадр
    def frame(self, t: float) -> FramePlan:
        t = float(t)
        if not math.isfinite(t):
            raise MotusError("время кадра должно быть конечным")
        self._advance(t)
        applied = self.animator.evaluate(t, self.scene)
        self.scene.update()

        items: List[DrawItem] = []
        for eid in range(len(self.scene)):
            ent = self.scene.entity(eid)
            if ent.alive:
                items.append(DrawItem(eid, ent.name, self.scene.world(eid), dict(ent.params)))

        batches: List[Batch] = []
        for em in self.effects.active_emitters(t):
            origin = em.origin
            if em.attach:
                eid = self.scene.find(em.attach)
                if eid is not None and self.scene.entity(eid).alive:
                    origin = translation(self.scene.world(eid))
            em_now = em if origin == em.origin else _with_origin(em, origin)
            data = compute_field(em_now, t) if self.particles else None
            batches.append(Batch(em.iid, em.effect, em_now.count, origin, data))

        posts = [Post(p.effect, p.evaluate(t)) for p in self.effects.active_posts(t)]
        return FramePlan(t, items, batches, posts,
                         {"entities": len(self.scene), "drawn": len(items),
                          "bindings": applied, "emitters": len(batches), "posts": len(posts)})

    # -------------------------------------------------------- откат
    def _snapshot(self):
        return (copy.deepcopy(self.scene), copy.deepcopy(self.animator),
                copy.deepcopy(self.effects), list(self._events), list(self._static),
                self._applied, dict(self._free_state))

    def _restore(self, snap) -> None:
        (self.scene, self.animator, self.effects, self._events,
         self._static, self._applied, self._free_state) = snap
        self._times = [c.at for c in self._events]


def _with_origin(em, origin):
    from .effects import Emitter
    return Emitter(em.iid, em.effect, origin, em.start, em.duration, em.count,
                   em.seed, em.params, em.attach)