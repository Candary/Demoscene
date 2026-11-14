"""CLI: demo | selfcheck | bake."""
from __future__ import annotations

import argparse
import sys

from .runtime import Runtime

DEMO_DSL = """mode dsl
new ball pos=(0,0,0) param.color=(1.0,0.6,0.2)
new halo parent=ball pos=(0,0.6,0)
anim ball.position from=(0,0,0) to=(3,0,0) at=0 over=2 ease=smooth
proc ball.rotation spin rate=180 at=0
proc halo.scale.uniform pulse base=1.0 amp=0.2 freq=2 at=0 mode=mul
fx burst on=ball at=2 for=1.5 count=600 seed=7 speed=7
fx vignette at=0 amount=0.4
drop halo at=3
"""

DEMO_FREE = """mode free
Создай шар, покрась в оранжевый.
Пусть летит вправо две секунды, потом взорвётся искрами и исчезнет.
"""


def _demo() -> int:
    for title, text in (("DSL", DEMO_DSL), ("FREE", DEMO_FREE)):
        rt = Runtime(particles=False)
        rep = rt.submit(text)
        print(f"=== {title} === {rep}")
        if not rep.ok:
            return 1
        for t in (0.0, 0.5, 2.0, 2.6, 3.5):
            fp = rt.frame(t)
            names = ", ".join(i.name for i in fp.items) or "-"
            print(f"  t={t:>4}: objects=[{names}] stats={fp.stats}")
            for it in fp.items:
                if it.name in ("ball", "obj0"):
                    print(f"        pos={tuple(round(v, 4) for v in it.world[12:15])}"
                          f" params={ {k: v for k, v in it.params.items()} }")
    return 0


def _selfcheck() -> int:
    sys.path.insert(0, ".")
    from tests.test_motus import run_all
    return run_all()


def _bake(args) -> int:
    from .bake import bake
    rt = Runtime(particles=False)
    rep = rt.submit(DEMO_DSL)
    if not rep.ok:
        print(rep)
        return 1
    m = bake(rt, fps=args.fps, duration=args.duration, out=args.out)
    print(f"baked {m['frames']} frames x {len(m['entities'])} entities -> {args.out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="motus")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo")
    sub.add_parser("selfcheck")
    b = sub.add_parser("bake")
    b.add_argument("--fps", type=float, default=60.0)
    b.add_argument("--duration", type=float, default=4.0)
    b.add_argument("--out", default="cache")
    args = ap.parse_args(argv)
    if args.cmd == "demo":
        return _demo()
    if args.cmd == "selfcheck":
        return _selfcheck()
    return _bake(args)


if __name__ == "__main__":
    raise SystemExit(main())