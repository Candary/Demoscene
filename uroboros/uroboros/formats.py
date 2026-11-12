"""Shared constants and helpers for the Uroboros patch format."""
from __future__ import annotations

import hashlib
import json
from typing import Any

FORMAT = "uroboros.patch/2"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


class PatchError(RuntimeError):
    """Raised for any protocol-level violation (bad format, unknown op, cycle in DAG, ...)."""