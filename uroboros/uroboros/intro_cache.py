"""intro_cache — iteration state storage for cyclic pipeline.

Stores per-iteration: metrics, param deltas, decisions, binary frame blobs.
Content-addressed dedup via FileMemory.put_blob. JSON metadata + binary blobs.

Layout:
  <root>/intro_cache/
    index.json              # master index: iteration → file refs
    iter_NNN_meta.json      # metrics, delta, decision, timestamp
    iter_NNN_state.json     # scene state snapshot (entities, params)
    iter_NNN_frames.bin     # optional binary frame data (mmap-ready)
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class IterationRecord:
    """One iteration's metadata (JSON-serializable)."""
    iteration: int
    run_id: str
    timestamp: str
    decision: str = "pending"  # approve | feedback_apply | abort
    metrics: Dict[str, Any] = field(default_factory=dict)
    delta: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    convergence: Dict[str, Any] = field(default_factory=dict)
    blob_refs: List[str] = field(default_factory=list)
    screenshot_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration, "run_id": self.run_id,
            "timestamp": self.timestamp, "decision": self.decision,
            "metrics": self.metrics, "delta": self.delta,
            "params": self.params, "convergence": self.convergence,
            "blob_refs": self.blob_refs, "screenshot_refs": self.screenshot_refs,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IterationRecord":
        return cls(
            iteration=int(d["iteration"]), run_id=str(d["run_id"]),
            timestamp=str(d.get("timestamp", "")),
            decision=str(d.get("decision", "pending")),
            metrics=dict(d.get("metrics", {})),
            delta=dict(d.get("delta", {})),
            params=dict(d.get("params", {})),
            convergence=dict(d.get("convergence", {})),
            blob_refs=list(d.get("blob_refs", [])),
            screenshot_refs=list(d.get("screenshot_refs", [])),
        )


class IntroCache:
    """Manages intro_cache directory with iteration records."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.cache_dir = self.root / "intro_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.cache_dir / "index.json"
        if not self._index_path.exists():
            self._write_index({"iterations": [], "final_iteration": None})

    def _read_index(self) -> dict:
        try:
            return json.loads(self._index_path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"iterations": [], "final_iteration": None}

    def _write_index(self, index: dict) -> None:
        tmp = self._index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False), "utf-8")
        tmp.replace(self._index_path)  # atomic

    def _iter_dir(self, iteration: int) -> Path:
        d = self.cache_dir / f"iter_{iteration:03d}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_iteration(self, record: IterationRecord,
                       frames_blob: Optional[bytes] = None) -> str:
        """Save iteration record + optional binary frames. Returns meta path."""
        d = self._iter_dir(record.iteration)
        meta_path = d / "meta.json"
        meta_path.write_text(
            json.dumps(record.to_dict(), indent=2, ensure_ascii=False), "utf-8")

        if frames_blob is not None and len(frames_blob) > 0:
            blob_path = d / "frames.bin"
            blob_path.write_bytes(frames_blob)
            record.blob_refs.append(str(blob_path.relative_to(self.cache_dir)))

        index = self._read_index()
        if record.iteration not in index["iterations"]:
            index["iterations"].append(record.iteration)
            index["iterations"].sort()
        if record.decision == "approve":
            index["final_iteration"] = record.iteration
        self._write_index(index)
        return str(meta_path)

    def load_iteration(self, iteration: int) -> Optional[IterationRecord]:
        meta_path = self.cache_dir / f"iter_{iteration:03d}" / "meta.json"
        if not meta_path.exists():
            return None
        try:
            return IterationRecord.from_dict(
                json.loads(meta_path.read_text("utf-8")))
        except (json.JSONDecodeError, KeyError) as exc:
            return None

    def load_frames(self, iteration: int) -> Optional[bytes]:
        blob_path = self.cache_dir / f"iter_{iteration:03d}" / "frames.bin"
        if not blob_path.exists():
            return None
        return blob_path.read_bytes()

    def list_iterations(self) -> List[int]:
        return self._read_index()["iterations"]

    @property
    def final_iteration(self) -> Optional[int]:
        return self._read_index().get("final_iteration")

    def prune(self, keep_last: int = 2) -> int:
        """Delete non-final iterations, keeping last N + final. Returns deleted count."""
        iterations = self.list_iterations()
        if not iterations:
            return 0
        final = self.final_iteration
        keep = set()
        if final is not None:
            keep.add(final)
        keep.update(iterations[-keep_last:])
        deleted = 0
        for it in iterations:
            if it not in keep:
                d = self._iter_dir(it)
                if d.exists():
                    shutil.rmtree(d)
                    deleted += 1
        index = self._read_index()
        index["iterations"] = [it for it in iterations if it in keep]
        self._write_index(index)
        return deleted

    def clear(self) -> None:
        """Remove all iterations."""
        for d in self.cache_dir.iterdir():
            if d.is_dir() and d.name.startswith("iter_"):
                shutil.rmtree(d)
        self._write_index({"iterations": [], "final_iteration": None})
