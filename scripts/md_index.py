#!/usr/bin/env python3
"""
md_index.py — собрать список всех .md файлов проекта с краткими описаниями.

Для каждого .md файла извлекает:
  - путь
  - размер в байтах
  - число строк
  - первый H1 заголовок (если есть)
  - первую непустую строку после H1 как summary (до 100 символов)

Выход: таблица в md.txt
"""
import os
import re
import sys
from pathlib import Path

# Каталоги, которые исключаем (мусор, backups, skills — чужие)
EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "archive", "backup_v43_working_milestone", "backup_v46_nebula",
    "backup_v47_probe", "backup_v48_noise3fix",
    "skills",  # это готовые skills от z.ai, не наш проект
}
EXCLUDE_DIR_PREFIXES = ("backup_", "pre_")

H1_RE = re.compile(r'^#\s+(.+?)\s*$', re.MULTILINE)


def extract_title_and_summary(path: Path) -> tuple[str, str]:
    """Вернуть (title, summary) для .md файла."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(unreadable)", ""

    # 1. Найти первый H1
    m = H1_RE.search(text)
    title = m.group(1).strip() if m else path.stem  # fallback на filename

    # 2. Найти первую непустую строку после H1 (или после frontmatter)
    lines = text.splitlines()
    skip_frontmatter = False
    if lines and lines[0].strip() == "---":
        # Skip YAML frontmatter
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                skip_frontmatter = True
                body_start = i + 1
                break
        else:
            body_start = 0
    else:
        body_start = 0

    # Skip до H1
    h1_line_idx = -1
    for i in range(body_start, len(lines)):
        if lines[i].startswith("# "):
            h1_line_idx = i
            break

    summary_start = h1_line_idx + 1 if h1_line_idx >= 0 else body_start

    # Find first non-empty, non-heading, non-frontmatter line
    summary = ""
    for line in lines[summary_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("---"):
            continue
        if stripped.startswith("```"):
            continue
        if stripped.startswith("|"):
            continue
        # Got a real line
        summary = stripped
        break

    # Truncate summary to 100 chars
    if len(summary) > 100:
        summary = summary[:97] + "..."

    return title, summary


def should_skip(path: Path, root: Path) -> bool:
    """Пропустить ли файл (по каталогу/префиксу)."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    parts = rel.parts
    for p in parts[:-1]:  # все каталоги кроме последнего (там файл)
        if p in EXCLUDE_DIRS:
            return True
        if any(p.startswith(prefix) for prefix in EXCLUDE_DIR_PREFIXES):
            return True
    return False


def main():
    root = Path("/home/z/my-project").resolve()
    out_path = root / "download" / "md.txt"

    # Найти все .md файлы
    all_mds = []
    for dirpath, dirnames, filenames in os.walk(root):
        # in-place prune
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS
                       and not any(d.startswith(p) for p in EXCLUDE_DIR_PREFIXES)]
        for fname in filenames:
            if fname.lower().endswith(".md"):
                p = Path(dirpath) / fname
                if not should_skip(p, root):
                    all_mds.append(p)

    all_mds.sort(key=lambda p: str(p.relative_to(root)).lower())

    # Собрать описания
    rows = []
    for p in all_mds:
        try:
            rel = p.relative_to(root)
        except ValueError:
            rel = p
        stat = p.stat()
        size = stat.st_size
        lines = 0
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = sum(1 for _ in f)
        except OSError:
            pass
        title, summary = extract_title_and_summary(p)
        rows.append((str(rel), title, summary, size, lines))

    # Записать md.txt
    with open(out_path, "w", encoding="utf-8") as out:
        out.write("# Markdown files index\n\n")
        out.write(f"Project: {root}\n")
        out.write(f"Total .md files: {len(rows)}\n\n")
        out.write("| # | Path | Title | Summary | Size | Lines |\n")
        out.write("|---|------|-------|---------|------|-------|\n")
        for i, (path, title, summary, size, lines) in enumerate(rows, 1):
            # Escape pipes in fields
            t = title.replace("|", "\\|")
            s = summary.replace("|", "\\|")
            out.write(f"| {i} | `{path}` | {t} | {s} | {size} B | {lines} |\n")

        # Also a plain-text list format for easy copy/paste
        out.write("\n## Plain text list\n\n")
        for i, (path, title, summary, size, lines) in enumerate(rows, 1):
            out.write(f"{i:3d}. {path}\n")
            out.write(f"     Title: {title}\n")
            if summary:
                out.write(f"     Summary: {summary}\n")
            out.write(f"     Size: {size} bytes, {lines} lines\n\n")

    print(f"Wrote {out_path}")
    print(f"Total .md files indexed: {len(rows)}")
    print(f"Output size: {out_path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
