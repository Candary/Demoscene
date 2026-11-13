"""Backward-compatibility shim for the legacy single-file `engine.py` (v0.2).

Place this file in the ROOT of your project (next to `patches/`), NOT inside
the `uroboros/` package. It re-exports everything the old module exposed, so
existing `from engine import ...` keeps working while you migrate.

Coverage of the old `engine.py` public surface
----------------------------------------------
    FORMAT, canonical, digest, PatchError, FileMemory, PatchRegistry, Uroboros
        -> re-exported from the `uroboros` package
    read_json
        -> re-exported from `uroboros.memory` (deliberately not top-level)

The old module also defined `Uroboros._checklist`, `_execute_one`, `_make_patch`
and so on, but those were always accessed through the class/instance
(`Uroboros._checklist(...)`, `u._execute_one(...)`). They are still there,
so old code keeps working without re-exports.

Deprecation tracking
--------------------
Set `UROBOROS_SHIM_WARN=1` before running anything to emit a
DeprecationWarning at import time. Combine with

    PYTHONWARNINGS=error::DeprecationWarning

to fail fast on any remaining users of the legacy import path:

    UROBOROS_SHIM_WARN=1 PYTHONWARNINGS=error::DeprecationWarning pytest

Default: silent — production logs stay clean.

Verification
------------
Run this file directly to verify the shim is wired correctly:

    python examples/engine.py

It checks imports, FileMemory roundtrip, PatchRegistry (if `patches/` is
adjacent) and a one-node Uroboros.run smoke test (if `patches/geometry.py`
is present). Exit code 0 means the shim works.

When to remove
--------------
After `python scripts/migrate_v0_2_to_v0_3.py --target . --check` passes
(no files import from `engine` anymore), delete this file.
"""
from __future__ import annotations

import os as _os
import warnings as _warnings

# ---------------------------------------------------------------------------
# Re-exports — exactly the names the old engine.py exposed at module level.
# ---------------------------------------------------------------------------

try:
    from uroboros import (  # noqa: F401
        FORMAT,
        PatchError,
        FileMemory,
        PatchRegistry,
        Uroboros,
        canonical,
        digest,
    )
    from uroboros.memory import read_json  # noqa: F401
except ImportError as _exc:  # pragma: no cover — only on misconfigured env
    raise ImportError(
        "The `engine` shim requires the `uroboros` package.\n"
        "Install it first:\n"
        "    pip install -e path/to/uroboros-0.3.0\n"
        "or, if you use the source tree:\n"
        "    pip install -e .\n"
        f"(underlying ImportError: {_exc})"
    ) from _exc

# `__all__` mirrors the old public surface so `from engine import *` keeps
# working and IDE autocompletion finds the same names as before.
__all__ = [
    "Uroboros",
    "FileMemory",
    "PatchRegistry",
    "FORMAT",
    "PatchError",
    "canonical",
    "digest",
    "read_json",
]

__shim_version__ = "0.3.0+shim"

# ---------------------------------------------------------------------------
# Optional deprecation warning.
# ---------------------------------------------------------------------------

def _maybe_warn() -> None:
    if _os.environ.get("UROBOROS_SHIM_WARN") != "1":
        return
    _warnings.warn(
        "Importing the legacy `engine` shim. "
        "Run `python scripts/migrate_v0_2_to_v0_3.py --target . --apply` "
        "to migrate imports to `uroboros`, then delete engine.py. "
        "Set UROBOROS_SHIM_WARN=0 to silence this warning.",
        DeprecationWarning,
        stacklevel=2,
    )


_maybe_warn()

# ---------------------------------------------------------------------------
# Self-check — `python examples/engine.py`.
# ---------------------------------------------------------------------------

def _self_check() -> int:
    import tempfile
    from pathlib import Path

    print(f"engine shim: FORMAT = {FORMAT!r}")
    if FORMAT != "uroboros.patch/2":
        print(f"engine shim: unexpected FORMAT {FORMAT!r}", flush=True)
        return 1

    # canonical / digest are deterministic.
    if canonical({"b": 2, "a": 1}) != b'{"a":1,"b":2}':
        print("engine shim: canonical() returned unexpected bytes")
        return 1
    if digest(b"x") != digest(b"x") or digest(b"x") == digest(b"y"):
        print("engine shim: digest() is not deterministic")
        return 1
    print("engine shim: canonical/digest ok")

    # FileMemory roundtrip.
    with tempfile.TemporaryDirectory() as tmp:
        m = FileMemory(tmp)
        ref = m.put_blob(b"payload")
        if m.get_blob(ref) != b"payload":
            print("engine shim: blob roundtrip failed")
            return 1
        m.cache_put("k1", {"outputs": {"x": 1}, "blob_refs": [], "operation": "op"})
        if m.cache_get("k1") != {"outputs": {"x": 1}, "blob_refs": [], "operation": "op"}:
            print("engine shim: cache roundtrip failed")
            return 1
        m.save_run("r1", {"status": "ok"})
        if m.load_run("r1") != {"status": "ok"}:
            print("engine shim: run roundtrip failed")
            return 1
        print(f"engine shim: FileMemory ok  (root={tmp})")

        # PatchRegistry — only if patches/ sits next to this file's parent.
        patches = Path(__file__).resolve().parent / "patches"
        if patches.is_dir():
            r = PatchRegistry(patches)
            print(f"engine shim: PatchRegistry ok ({len(r.ops)} op(s) from {patches})")
        else:
            print("engine shim: PatchRegistry skipped (no patches/ next to shim)")
            print("engine shim: all reachable checks passed")
            return 0

        # Uroboros.run — only if the standard geometry patch is available.
        if not (patches / "geometry.py").exists():
            print("engine shim: Uroboros.run skipped (patches/geometry.py not found)")
            print("engine shim: all reachable checks passed")
            return 0

        u = Uroboros(root=f"{tmp}/u", patches=patches, workers=1)
        plan = {
            "format": FORMAT,
            "name": "shim_smoke",
            "nodes": [
                {
                    "id": "g",
                    "target": "scene",
                    "operation": "geometry.generate",
                    "params": {"width": 3.0, "depth": 2.0},
                },
            ],
        }
        state = u.run(plan, require_approval=False, max_iterations=1)
        if state["status"] != "approved":
            print(f"engine shim: Uroboros.run status={state['status']!r}")
            return 1
        if "g" not in (state["final"] or {}).get("outputs", {}):
            print("engine shim: Uroboros.run did not return outputs['g']")
            return 1
        print("engine shim: Uroboros.run ok  (status=approved)")

    print("engine shim: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_check())