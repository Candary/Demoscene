"""Patch registry: loads trusted local Python patch scripts from a directory.

Each file must expose `OP` (str) and `apply(context, params) -> dict`.
The directory must be trusted: patches are arbitrary Python.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Callable

from .formats import PatchError, digest


class PatchRegistry:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.ops: dict[str, Callable] = {}
        self.versions: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        self.ops.clear()
        self.versions.clear()
        if not self.folder.is_dir():
            return
        for file in sorted(self.folder.glob("*.py")):
            if file.name.startswith("_"):
                continue
            spec = importlib.util.spec_from_file_location(f"uroboros_patch_{file.stem}", file)
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            name = getattr(mod, "OP", file.stem)
            fn = getattr(mod, "apply", None)
            if not callable(fn):
                raise PatchError(f"{file}: missing callable `apply`")
            if name in self.ops:
                raise PatchError(f"{file}: duplicate OP={name!r} (already registered)")
            self.ops[name] = fn
            self.versions[name] = digest(file.read_bytes())

    def apply(self, name: str, context: dict, params: dict):
        if name not in self.ops:
            raise PatchError(f"Unknown patch operation: {name!r}; available: {sorted(self.ops)}")
        return self.ops[name](context, params)