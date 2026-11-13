"""Append-only event journal + content-addressed blob store + JSON caches.

No database server, no SQLite. Safe for concurrent writes from multiple threads:
* blobs are content-addressed (sha256), tmp files use uuid suffixes so parallel writers don't collide;
* cache/run JSON is written via uuid tmp + os.replace;
* journal appends are protected by a lock.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .formats import PatchError, canonical, digest


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return default


class FileMemory:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.blobs = self.root / "blobs"
        self.cache = self.root / "cache"
        self.runs = self.root / "runs"
        self.pipeline_cache = self.root / "pipeline_cache"
        for p in (self.blobs, self.cache, self.runs, self.pipeline_cache):
            p.mkdir(parents=True, exist_ok=True)
        self.journal = self.root / "memory.jsonl"
        self._lock = threading.Lock()

    # ---- blobs --------------------------------------------------------------
    def put_blob(self, data: bytes) -> dict:
        key = digest(data)
        path = self.blobs / key[:2] / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
            tmp.write_bytes(data)
            os.replace(tmp, path)
        return {"hash": key, "path": str(path.relative_to(self.root)), "size": len(data)}

    def get_blob(self, ref: dict) -> bytes:
        path = self.root / ref["path"]
        data = path.read_bytes()
        if digest(data) != ref["hash"]:
            raise PatchError(f"Blob checksum mismatch: {path}")
        return data

    # ---- journal ------------------------------------------------------------
    def event(self, event: dict) -> None:
        line = canonical({"ts": time.time(), **event}) + b"\n"
        with self._lock:
            with self.journal.open("ab") as f:
                f.write(line)
                f.flush()

    # ---- cache --------------------------------------------------------------
    def cache_get(self, key: str):
        path = self.cache / key[:2] / f"{key}.json"
        record = read_json(path)
        if not record:
            return None
        for ref in record.get("blob_refs", []):
            self.get_blob(ref)
        return record

    def cache_put(self, key: str, record: dict) -> None:
        path = self.cache / key[:2] / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_bytes(canonical(record))
        os.replace(tmp, path)

    # ---- runs ---------------------------------------------------------------
    def save_run(self, run_id: str, record: dict) -> None:
        path = self.runs / f"{run_id}.json"
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_bytes(canonical(record))
        os.replace(tmp, path)

    def load_run(self, run_id: str) -> dict | None:
        return read_json(self.runs / f"{run_id}.json")

    def save_pipeline_trace(self, key: str, run_id: str, record: dict) -> None:
        folder = self.pipeline_cache / key[:2] / key
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{run_id}.json"
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_bytes(canonical(record))
        os.replace(tmp, path)

    def load_pipeline_trace(self, key: str) -> list[dict]:
        folder = self.pipeline_cache / key[:2] / key
        if not folder.exists():
            return []
        return [read_json(p) for p in sorted(folder.glob("*.json"))]

    # ---- stats --------------------------------------------------------------
    def stats(self) -> dict:
        blob_paths = [p for p in self.blobs.rglob("*") if p.is_file()]
        cache_entries = sum(1 for _ in self.cache.rglob("*.json"))
        runs = sum(1 for _ in self.runs.glob("*.json"))
        journal_lines = 0
        if self.journal.exists():
            with self.journal.open("rb") as f:
                journal_lines = sum(1 for _ in f)
        return {
            "root": str(self.root),
            "blobs": len(blob_paths),
            "blob_size_bytes": sum(p.stat().st_size for p in blob_paths),
            "cache_entries": cache_entries,
            "runs": runs,
            "journal_lines": journal_lines,
        }