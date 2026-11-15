"""Инварианты. Работают и под pytest, и без него: python -m motus selfcheck."""
from __future__ import annotations

import math
from contextlib import contextmanager

from motus import (Animator, Binding, Kind, Mode, ProcCall, QueryError, Runtime,
                   Scene, Track, Transport, hash01, qslerp)
from motus.query import parse


@contextmanager
def fails(exc=Exception):
    try:
        yield
    except exc:
        return
    raise AssertionError(f"ожидалось исключение {exc.__name__}")


def _tr3(pairs, ease="linear"):
    return Track(Kind.VEC3, ease=ease).keys(pairs)


def test_i1_determinism():
    tr = _tr3([(0.0, (0, 0, 0)), (1.0, (1, 2, 3)), (2.0, (0, 1, 0))], "smooth")
    ref = tr.sample(0.7)
    for t in (1.9, 0.0, 2.0, -5.0, 0.7):
        tr.sample(t)
    assert tr.sample(0.7) == ref


def test_i2_hash_purity():
    a = [hash01(42, i) for i in range(64)]
    for _ in range(500):
        hash01(7, 999)
    assert a == [hash01(42, i) for i in range(64)]
    assert len(set(a)) == 64


def test_i3_framerate_independence():
    tr = _tr3([(0.0, (0, 0, 0)), (2.0, (10, 0, 0))], "smooth")
    for k in range(121):
        t = k / 60.0
        assert tr.sample(t) == tr.sample(round(t * 240) / 240.0)


def test_i4_boundaries():
    tr = _tr3([(0.0, (1, 2, 3)), (1.0, (4, 5, 6))])
    for t in (-1e12, -1.0, 0.0, 1e12, math.inf, -math.inf, math.nan):
        v = tr.sample(t)
        assert len(v) == 3 and all(math.isfinite(x) for x in v)
    assert Track(Kind.VEC3).sample(0.0) == (0.0, 0.0, 0.0)
    assert Track(Kind.FLOAT).sample(0.0) == 0.0
    with fails():
        Track(Kind.FLOAT).key(1.0, 1).key(1.0, 2)


def test_i5_identity_defaults():
    sc = Scene()
    e = sc.add("a")
    sc.update()
    p = sc.entity(e).pose
    assert p.scale == (1.0, 1.0, 1.0) and p.rot == (0.0, 0.0, 0.0, 1.0)
    assert sc.world(e)[15] == 1.0


def test_i6_blend_algebra():
    for w, expect in ((0.0, 0.0), (0.5, 5.0), (1.0, 10.0)):
        sc = Scene()
        sc.add("a")
        an = Animator()
        an.add(Binding("a", "position.x",
                       Track(Kind.FLOAT).key(0.0, 10.0), Mode.REPLACE, w))
        an.evaluate(0.0, sc)
        assert abs(sc.entity(0).pose.pos[0] - expect) < 1e-9
    sc = Scene()
    sc.add("a", scale=(2.0, 2.0, 2.0))
    an = Animator()
    an.add(Binding("a", "scale", Track(Kind.VEC3).key(0.0, (3, 3, 3)), Mode.MUL, 1.0))
    an.evaluate(0.0, sc)
    assert sc.entity(0).pose.scale == (6.0, 6.0, 6.0)
    with fails(QueryError):
        Binding("a", "rotation", Track(Kind.QUAT).key(0.0, (0, 0, 0, 1)), Mode.MUL)


def test_i7_hierarchy():
    sc = Scene()
    r = sc.add("r", pos=(1, 0, 0))
    a = sc.add("a", r, pos=(0, 2, 0))
    b = sc.add("b", a, pos=(0, 0, 3))
    sc.update()
    assert sc.world(b)[12:15] == (1.0, 2.0, 3.0)
    with fails():
        sc.set_parent(r, b)


def test_i8_replay_after_scrub():
    rt = Runtime(particles=False)
    assert rt.submit("new a\nanim a.position from=(0,0,0) to=(5,0,0) over=2\n"
                     "new b at=1\ndrop b at=2\n").ok
    ref = rt.frame(0.75).items[0].world
    for t in (3.0, 0.0, 1.5, 2.2, 0.1):
        rt.frame(t)
    assert rt.frame(0.75).items[0].world == ref


def test_i9_offline_equals_realtime():
    text = "new a\nanim a.position from=(0,0,0) to=(9,0,0) over=1 ease=smooth\n"
    a, b = Runtime(particles=False), Runtime(particles=False)
    a.submit(text)
    b.submit(text)
    offline = [a.frame(k / 60.0).items[0].world for k in range(61)]
    realtime = []
    for k in range(61):
        b.frame(0.31 * k)
        realtime.append(b.frame(k / 60.0).items[0].world)
    assert offline == realtime


def test_i10_quaternion():
    q = (0.0, 0.7071067811865476, 0.0, 0.7071067811865476)
    nq = tuple(-v for v in q)
    mid = qslerp(q, nq, 0.5)
    assert abs(sum(v * v for v in mid) - 1.0) < 1e-9
    assert abs(abs(mid[3]) - abs(q[3])) < 1e-6


def test_query_modes_and_equivalence():
    dsl = parse("mode dsl\nnew ball\nanim ball.position from=(0,0,0) to=(2,0,0) over=2\n")
    assert dsl.ok and dsl.mode == "dsl" and [c.op for c in dsl.commands] == ["new", "anim"]
    free = parse("mode free\nСоздай шар. Пусть летит вправо две секунды.\n")
    assert free.ok and free.mode == "free"
    assert [c.op for c in free.commands] == ["new", "anim"]
    mixed = parse("mode free\nсоздай шар\nmode dsl\nanim ball.position from=(0,0,0) to=(1,0,0)\n")
    assert mixed.ok and mixed.mode == "dsl" and len(mixed.commands) == 2


def test_query_error_is_atomic():
    rt = Runtime(particles=False)
    rep = rt.submit("new a\nanim a.nosuch from=(0,0,0) to=(1,0,0)\n")
    assert not rep.ok and len(rt.scene) == 0


def test_spaces_in_vectors_and_beats():
    rt = Runtime(Transport(bpm=120.0), particles=False)
    assert rt.submit("new a pos=(1, 2, 3)\nfx burst at=bar:2 count=10\n").ok
    # P1 fix: events are applied at frame(t), not at submit()
    rt.frame(0.0)
    assert rt.scene.entity(0).base.pos == (1.0, 2.0, 3.0)
    assert rt.effects.emitters[0].start == 4.0


def test_procedural_purity():
    p = ProcCall("orbit", {"radius": 2.0}, seed=3)
    assert p.sample(1.25) == p.sample(1.25)


def test_bake_roundtrip(tmp_path=None):
    import tempfile
    from motus.bake import Playback, bake
    rt = Runtime(particles=False)
    rt.submit("new a\nanim a.position from=(0,0,0) to=(4,0,0) over=1\n")
    with tempfile.TemporaryDirectory() as d:
        m = bake(rt, fps=30.0, duration=1.0, out=d)
        with Playback(d) as pb:
            assert pb.frames == m["frames"] == 31
            assert abs(pb.pose(30, 0)[0] - 4.0) < 1e-5


def run_all() -> int:
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS {name}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0