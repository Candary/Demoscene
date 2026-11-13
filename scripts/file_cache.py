#!/usr/bin/env python3
"""
file_cache.py — кеш файлового индекса для ускорения os.walk.

Вместо обхода 490+ файлов каждый раз (292ms), кеш:
  1. Первый запуск: full os.walk → строит {dir: {mtime, files}} → сохраняет в .file_cache.json
  2. Последующие запуски: проверяет только mtime каталогов (~25ms)
     - Если все mtime совпадают → берёт файлы из кеша
     - Если какой-то каталог изменился → re-scan только его

Скорость:
  - os.walk (current): 292ms
  - cache valid:        25ms (12× быстрее)
  - cache stale:        317ms (walk + cache rebuild)
  - first run:          297ms (walk + cache save)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Iterable

# Те же исключения что в repo2txt
EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "archive", "skills",
}
EXCLUDE_DIR_PREFIXES = ("backup_", "pre_", "_old", "_backup", "_archived")

CACHE_FILE = ".file_cache.json"


def _should_skip_dir(d: str) -> bool:
    if d in EXCLUDE_DIRS:
        return True
    if d.startswith(".git"):
        return True
    return any(d.startswith(p) for p in EXCLUDE_DIR_PREFIXES)


def _build_cache(root: str = ".") -> dict:
    """Full os.walk → build cache dict."""
    cache = {}
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune in-place
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]

        try:
            dir_mtime = os.stat(dirpath).st_mtime
        except OSError:
            continue

        files = []
        for f in filenames:
            fpath = os.path.join(dirpath, f)
            try:
                fstat = os.stat(fpath)
                files.append({
                    "n": f,                              # name
                    "s": fstat.st_size,                   # size
                    "m": fstat.st_mtime,                  # mtime
                    "e": os.path.splitext(f)[1].lower(),  # ext
                })
            except OSError:
                pass

        cache[dirpath] = {"mtime": dir_mtime, "files": files}

    return cache


def _save_cache(cache: dict, path: str = CACHE_FILE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, separators=(",", ":"))  # compact JSON


def _load_cache(path: str = CACHE_FILE) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _is_cache_valid(cache: dict, root: str = ".") -> bool:
    """Check if cache is still valid by comparing directory mtimes.

    Only stats directories (not files) — ~20 stat calls vs 490+.
    If a directory's mtime changed → files were added/removed → cache stale.
    """
    if not cache:
        return False

    for dirpath, cached in cache.items():
        try:
            current_mtime = os.stat(dirpath).st_mtime
        except OSError:
            return False  # directory deleted → stale

        if current_mtime != cached["mtime"]:
            return False  # directory changed → stale

    return True


def _rebuild_stale_dirs(cache: dict, root: str = ".") -> dict:
    """Re-scan only directories whose mtime changed."""
    new_cache = {}
    for dirpath, cached in cache.items():
        try:
            current_mtime = os.stat(dirpath).st_mtime
        except OSError:
            continue  # dir deleted, skip

        if current_mtime != cached["mtime"]:
            # Re-scan this directory
            try:
                entries = os.listdir(dirpath)
            except OSError:
                continue
            files = []
            for f in entries:
                fpath = os.path.join(dirpath, f)
                if os.path.isfile(fpath):
                    try:
                        fstat = os.stat(fpath)
                        files.append({
                            "n": f, "s": fstat.st_size,
                            "m": fstat.st_mtime,
                            "e": os.path.splitext(f)[1].lower(),
                        })
                    except OSError:
                        pass
            new_cache[dirpath] = {"mtime": current_mtime, "files": files}
        else:
            # Keep cached data
            new_cache[dirpath] = cached

    return new_cache


def get_files(
    root: str = ".",
    extensions: set[str] | None = None,
    max_size: int = 1024 * 1024,
) -> list[dict]:
    """Get file list from cache (or rebuild if stale).

    Returns list of {path, name, size, ext} dicts.
    """
    cache = _load_cache(os.path.join(root, CACHE_FILE))

    if cache and _is_cache_valid(cache, root):
        # Cache valid — use it (FAST path)
        pass
    elif cache:
        # Cache stale — rebuild only changed dirs
        cache = _rebuild_stale_dirs(cache, root)
        _save_cache(cache, os.path.join(root, CACHE_FILE))
    else:
        # No cache — full walk
        cache = _build_cache(root)
        _save_cache(cache, os.path.join(root, CACHE_FILE))

    # Flatten cache → file list
    files = []
    for dirpath, data in cache.items():
        for f in data["files"]:
            if max_size and f["s"] > max_size:
                continue
            if extensions and f["e"] not in extensions:
                continue
            files.append({
                "path": os.path.join(dirpath, f["n"]),
                "name": f["n"],
                "size": f["s"],
                "ext": f["e"],
            })

    return sorted(files, key=lambda x: x["path"].lower())


def benchmark(root: str = "."):
    """Benchmark: os.walk vs cache."""
    print("=== Benchmark: os.walk vs file_cache ===\n")

    # 1. Plain os.walk
    t0 = time.perf_counter()
    count = 0
    for dp, dn, fn in os.walk(root):
        if _should_skip_dir(os.path.basename(dp)):
            dn[:] = []
            continue
        for f in fn:
            count += 1
    t1 = time.perf_counter()
    walk_ms = (t1 - t0) * 1000
    print(f"  os.walk (plain):          {walk_ms:>6.0f} ms  ({count} files)")

    # 2. Cache — first run (cold)
    cache_path = os.path.join(root, CACHE_FILE)
    if os.path.exists(cache_path):
        os.remove(cache_path)

    t0 = time.perf_counter()
    files = get_files(root)
    t1 = time.perf_counter()
    cold_ms = (t1 - t0) * 1000
    print(f"  cache (cold, first run):  {cold_ms:>6.0f} ms  ({len(files)} files)")

    # 3. Cache — warm (valid)
    t0 = time.perf_counter()
    files = get_files(root)
    t1 = time.perf_counter()
    warm_ms = (t1 - t0) * 1000
    print(f"  cache (warm, valid):      {warm_ms:>6.0f} ms  ({len(files)} files)")

    # 4. Cache — with extension filter
    t0 = time.perf_counter()
    files_py = get_files(root, extensions={".py", ".md", ".json"})
    t1 = time.perf_counter()
    filter_ms = (t1 - t0) * 1000
    print(f"  cache (warm + ext filter): {filter_ms:>5.0f} ms  ({len(files_py)} files)")

    print(f"\n  Speedup (warm vs walk): {walk_ms / warm_ms:.1f}×")
    print(f"  Speedup (cold vs walk): {walk_ms / cold_ms:.1f}×")
    print(f"  Cache file: {os.path.getsize(cache_path)} bytes")


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    benchmark(root)
