"""Command-line interface for Uroboros."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import Uroboros
from .formats import FORMAT
from .glm import make_glm_proposer
from .plan import full_plan, load_plan, save_plan, simple_room_plan


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


# ---- команды --------------------------------------------------------------

def cmd_example(args) -> int:
    if args.kind == "simple":
        plan = simple_room_plan()
    elif args.kind == "validation":
        plan = full_plan(with_validation=True)
    elif args.kind == "cozy":
        plan = full_plan(with_cozy=True)
    else:
        print(f"unknown example kind: {args.kind}", file=sys.stderr)
        return 2
    if args.out:
        save_plan(plan, args.out)
        print(f"written: {args.out}")
    else:
        _print(plan)
    return 0


def cmd_patches(args) -> int:
    u = Uroboros(root=args.root, patches=args.patches, workers=1)
    if not u.patches.ops:
        print(f"no patches in {args.patches}", file=sys.stderr)
        return 1
    for name in sorted(u.patches.ops):
        print(f"  {name:24s}  script sha256: {u.patches.versions[name][:12]}…")
    return 0


def cmd_run(args) -> int:
    plan = load_plan(args.plan)
    glm_propose = make_glm_proposer() if args.glm_feedback else None
    u = Uroboros(root=args.root, patches=args.patches, workers=args.workers,
                 glm_propose=glm_propose)
    approval = (lambda r: True) if args.auto_approve else None

    if not args.auto_approve and not args.yes and sys.stdin.isatty():
        print(f"plan: {plan.get('name', 'untitled')}  ({len(plan.get('nodes', []))} nodes)")
        print("Run interactively and approve each iteration? [y/N]", end=" ")
        sys.stdin.flush()
        if sys.stdin.readline().strip().lower() != "y":
            approval = None  # only one pass, no approval

    state = u.run(plan, max_iterations=args.max_iterations,
                  require_approval=not args.auto_approve, approval=approval)
    _print({
        "run": state["run"],
        "status": state["status"],
        "iterations": len(state["iterations"]),
        "approved": state["approved"],
        "pipeline_cache_key": state.get("pipeline_cache_key"),
    })
    return 0 if state["status"] == "approved" else 1


def cmd_inspect(args) -> int:
    u = Uroboros(root=args.root, patches=args.patches, workers=1)
    record = u.memory.load_run(args.run)
    if record is None:
        print(f"no such run: {args.run}", file=sys.stderr)
        return 1
    _print(record)
    return 0


def cmd_cache_stats(args) -> int:
    u = Uroboros(root=args.root, patches=args.patches, workers=1)
    _print(u.memory.stats())
    return 0


def cmd_clean(args) -> int:
    if not args.yes:
        print("refusing to delete without --yes", file=sys.stderr)
        return 2
    import shutil
    p = Path(args.root)
    if p.exists():
        shutil.rmtree(p)
        print(f"removed: {p}")
    else:
        print(f"nothing to remove: {p}")
    return 0


# ---- парсер ---------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="uroboros", description="Patch-driven iterative pipeline")
    p.add_argument("--root", default=".uroboros", help="data directory (default: .uroboros)")
    p.add_argument("--patches", default="patches", help="patch scripts directory (default: patches)")
    sub = p.add_subparsers(dest="cmd", required=True)

    ex = sub.add_parser("example", help="generate an example plan")
    ex.add_argument("--kind", choices=["simple", "validation", "cozy"], default="simple")
    ex.add_argument("--out", help="write to file instead of stdout")
    ex.set_defaults(func=cmd_example)

    pt = sub.add_parser("patches", help="list installed patches")
    pt.set_defaults(func=cmd_patches)

    rn = sub.add_parser("run", help="run a plan")
    rn.add_argument("--plan", required=True)
    rn.add_argument("--auto-approve", action="store_true", help="approve everything (CI)")
    rn.add_argument("--yes", action="store_true", help="skip interactive prompt")
    rn.add_argument("--max-iterations", type=int, default=4)
    rn.add_argument("--workers", type=int, default=4)
    rn.add_argument("--glm-feedback", action="store_true", help="ask GLM for feedback between iterations")
    rn.set_defaults(func=cmd_run)

    ins = sub.add_parser("inspect", help="show a saved run")
    ins.add_argument("--run", required=True)
    ins.set_defaults(func=cmd_inspect)

    cs = sub.add_parser("cache-stats", help="show cache stats")
    cs.set_defaults(func=cmd_cache_stats)

    cl = sub.add_parser("clean", help="delete the data directory")
    cl.add_argument("--yes", action="store_true")
    cl.set_defaults(func=cmd_clean)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())