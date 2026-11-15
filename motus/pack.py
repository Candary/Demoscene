"""Собрать архив проекта: python pack.py -> dist/motus-0.1.0.zip"""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", "dist", "cache", ".venv"}
SKIP_EXT = {".pyc", ".pyo", ".f32"}


def main() -> int:
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    target = dist / "motus-0.1.0.zip"
    files = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        if p.suffix in SKIP_EXT or p == target:
            continue
        files.append(p)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, str(Path("motus") / p.relative_to(ROOT)))
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f"{target}  ({len(files)} файлов, {target.stat().st_size} байт)")
    print(f"sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())