#!/usr/bin/env python3
"""
repo2txt.py — собрать весь релевантный код проекта в один текстовый файл.

Назначение:
  Обходит дерево каталогов, пропускает мусор (node_modules, .git, бинарники,
  архивы, медиа, __pycache__, виртуальные окружения, lock-файлы и т.д.),
  и склеивает оставшиеся текстовые файлы в один .txt с понятными разделителями.

  Полезно для:
    - скармливания всего кода LLM (ChatGPT, Claude, GLM) одним промптом
    - быстрого обзора структуры проекта
    - экспорта кода в issue/PR-описания
    - archiving snapshots в text-форме

Использование:
  python3 scripts/repo2txt.py                       # по умолчанию: root=., output=download/repo2txt_output.txt
  python3 scripts/repo2txt.py --root /path/to/proj
  python3 scripts/repo2txt.py --output out.txt
  python3 scripts/repo2txt.py --stats-only          # только статистика, без записи файла
  python3 scripts/repo2txt.py --git-tracked-only    # только файлы, отслеживаемые git
  python3 scripts/repo2txt.py --max-size 256        # лимит размера файла в KB (по умолч. 1024)
  python3 scripts/repo2txt.py --exclude-dir build,tmp
  python3 scripts/repo2txt.py --include-ext .log    # добавить расширение к дефолтным
  python3 scripts/repo2txt.py --exclude-pattern '*.bak' --exclude-pattern 'test_*'

Выход:
  - Заголовок с проектом, временем генерации, статистикой
  - Дерево каталогов (упрощённое)
  - Подсчёт по расширениям
  - Затем каждый файл в виде:
      === FILE: relative/path.py (1234 bytes, 45 lines, python) ===
      <содержимое>
      === END FILE ===
"""
from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Дефолтные правила фильтрации — ЗДЕСЬ И ТОЛЬКО ЗДЕСЬ настраивать "что тащить"
# ---------------------------------------------------------------------------

# Каталоги, которые ТАЩИТЬ НЕЛЬЗЯ никогда (даже если в --include-dir)
DEFAULT_EXCLUDE_DIRS: set[str] = {
    # VCS
    ".git", ".hg", ".svn", ".bzr",
    # Python
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "env", ".env",  # виртуальные окружения
    ".tox", ".coverage", "htmlcov", ".eggs", "build", "dist",
    # Node.js
    "node_modules", ".next", ".nuxt", ".output", ".svelte-kit",
    "bower_components", "jspm_packages",
    # Web/Compile output
    "target",  # Rust/Java
    "out", "bin", "obj",  # C# / .NET / C++ build artifacts
    "coverage", ".nyc_output",
    # IDE
    ".idea", ".vscode", ".vs", ".fleet",
    # OS junk
    ".DS_Store", "Thumbs.db",
    # Caches
    ".cache", ".parcel-cache", ".turbo", ".swc",
    # Project-specific
    "archive",  # backups/snapshots в нашем проекте
}

# Каталоги, которые можно переопределить через --include-dir (по умолч. исключаются)
SOFT_EXCLUDE_DIRS: set[str] = {
    "scripts",     # в нашем проекте scripts/ — полезный код, тащим
    "tests",
    "test",
    "docs",
    "examples",
}

# Расширения файлов, которые ТАЩИМ (по умолчанию)
DEFAULT_INCLUDE_EXTS: set[str] = {
    # Code
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx", ".hh", ".inl",
    ".cs", ".java", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".kts", ".scala",
    ".lua", ".pl", ".pm", ".tcl", ".r", ".dart", ".elm", ".ex", ".exs",
    ".clj", ".cljs", ".cljc", ".lisp", ".scm",
    ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1", ".fish",
    # Web
    ".html", ".htm", ".css", ".scss", ".sass", ".less", ".stylus",
    ".vue", ".svelte", ".astro",
    # Markup / docs
    ".md", ".markdown", ".rst", ".txt", ".tex", ".adoc", ".asciidoc",
    ".org", ".creole", ".wiki", ".pod",
    # Data / config
    ".json", ".json5", ".jsonc",
    ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".config",
    ".xml", ".csv", ".tsv",
    ".env", ".env.local", ".env.example",  # примеры окружения (не реальные секреты!)
    # Build
    ".dockerfile", "Dockerfile",  # последний — без точки, файл с именем Dockerfile
    "Makefile", "makefile",
    "CMakeLists.txt",
    ".mk",
    # Shader / GLSL
    ".glsl", ".frag", ".vert", ".comp", ".geom", ".tesc", ".tese",
    # Other
    ".sql", ".graphql", ".gql", ".proto", ".thrift",
    ".gitignore", ".gitattributes", ".editorconfig",
    ".lock",  # у нас есть пакетные lock-файлы, но их фильтруем по имени отдельно
    ".log",   # часто полезен для отладки
}

# Расширения, которые НИКОГДА не тащим (даже если в --include-ext)
HARDCODED_EXCLUDE_EXTS: set[str] = {
    # Binaries / compiled
    ".exe", ".dll", ".so", ".dylib", ".a", ".lib", ".o", ".obj",
    ".pyc", ".pyo", ".pyd", ".class", ".jar", ".war",
    ".wasm", ".wat",
    # Archives
    ".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz",
    ".gz", ".bz2", ".xz", ".7z", ".rar", ".lz", ".lzma",
    # Media
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp",
    ".ico", ".icns", ".svgz",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flv", ".webm",
    ".ogg", ".flac", ".aac", ".m4a", ".wma",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp",
    # Databases / large data
    ".db", ".sqlite", ".sqlite3", ".mdb",
    ".npz", ".npy",  # numpy binaries (большие)
    ".h5", ".hdf5", ".pkl", ".pickle",
    ".parquet", ".feather", ".arrow",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # Misc
    ".DS_Store", ".swp", ".swo", ".bak", ".tmp", ".temp",
}

# Префиксы каталогов, которые всегда исключаем (backup_*, pre_*_patches, etc.)
DEFAULT_EXCLUDE_DIR_PREFIXES: tuple[str, ...] = (
    "backup_",       # backup_v43_working_milestone и т.п.
    "pre_",          # pre_perf_patches, pre_color_matrix_migration
    "_backup",       # альтернативное имя
    "_old",          # _old_version
    "_archived",     # _archived_stuff
)

# Имена файлов, которые не тащим (даже с подходящим расширением)
DEFAULT_EXCLUDE_FILENAMES: set[str] = {
    # Lock files — гигантские, не релевантны для чтения
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "composer.lock",
    "Cargo.lock", "go.sum", "Pipfile.lock", "poetry.lock",
    "Gemfile.lock", "bun.lock", "bun.lockb",
    # OS junk
    ".DS_Store", "Thumbs.db", "desktop.ini",
    # Project-specific junk
    "trace.log",  # огромный лог в нашем проекте
    # Secrets — реальные env-файлы могут содержать пароли/токены
    ".env", ".env.local", ".env.production", ".env.staging",
    ".env.development",  # разработческие тоже часто с секретами
}

# Glob-шаблоны имён файлов, которые исключаем (поверх DEFAULT_EXCLUDE_FILENAMES)
DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (
    "trace_*.log",           # trace_v45_GOOD_reference.log
    "trace_v*.log",
    "*.bak", "*.backup", "*.orig",
    "*~",                    # vim swap files
)

# Имена файлов, которые тащим по basename (даже без расширения)
SPECIAL_BASENAMES: set[str] = {
    "Dockerfile", "Makefile", "makefile", "CMakeLists.txt",
    ".gitignore", ".gitattributes", ".editorconfig", ".env.example",
    "LICENSE", "LICENSE.md", "LICENSE.txt", "README", "README.md", "README.txt",
    "CHANGELOG", "CHANGELOG.md", "AUTHORS", "CONTRIBUTING.md",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class FileInfo:
    path: Path          # relative to root
    abs_path: Path
    size: int
    ext: str            # lowercase, with leading dot (or empty)
    lines: int = 0
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class RepoStats:
    total_files_scanned: int = 0
    included: int = 0
    skipped_dir: int = 0
    skipped_ext: int = 0
    skipped_size: int = 0
    skipped_binary: int = 0
    skipped_name: int = 0
    skipped_pattern: int = 0
    skipped_git: int = 0
    included_bytes: int = 0
    by_ext: dict[str, int] = field(default_factory=dict)


# Сигнатуры бинарных файлов (первые N байт)
BINARY_CHECK_BYTES = 8000
NULL_BYTE_THRESHOLD = 1  # если есть хотя бы 1 \0 в первых N байтах — бинарник


def is_binary(path: Path) -> bool:
    """Эвристика: если в первых 8KB есть \0 — файл бинарный."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(BINARY_CHECK_BYTES)
        return b"\x00" in chunk
    except (OSError, PermissionError):
        return True  # не читается — считаем бинарником и пропускаем


def read_text_safely(path: Path) -> str | None:
    """Прочитать файл как текст. Возвращает None если не получилось."""
    try:
        # Пробуем UTF-8 сначала
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        pass
    try:
        # Fallback: latin-1 (никогда не падает, но может дать мусор)
        with open(path, "r", encoding="latin-1") as f:
            return f.read()
    except (OSError, PermissionError):
        return None


def detect_lang(ext: str, basename: str) -> str:
    """Простая карта расширение/имя → язык для метки в выходном файле."""
    m = {
        ".py": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
        ".ts": "typescript", ".tsx": "tsx", ".jsx": "jsx",
        ".c": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
        ".h": "c-header", ".hpp": "cpp-header", ".hxx": "cpp-header",
        ".cs": "csharp", ".java": "java", ".go": "go", ".rs": "rust",
        ".rb": "ruby", ".php": "php", ".swift": "swift", ".kt": "kotlin", ".scala": "scala",
        ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".bat": "batch", ".cmd": "batch", ".ps1": "powershell",
        ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss", ".sass": "sass",
        ".vue": "vue", ".svelte": "svelte",
        ".md": "markdown", ".markdown": "markdown", ".rst": "rst",
        ".txt": "text", ".tex": "latex",
        ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
        ".ini": "ini", ".cfg": "config", ".conf": "config",
        ".xml": "xml", ".csv": "csv", ".tsv": "tsv",
        ".sql": "sql", ".graphql": "graphql", ".gql": "graphql", ".proto": "protobuf",
        ".glsl": "glsl", ".frag": "glsl-fragment", ".vert": "glsl-vertex",
        ".dockerfile": "dockerfile", "Dockerfile": "dockerfile",
        "Makefile": "makefile", "CMakeLists.txt": "cmake",
        ".gitignore": "gitignore", ".env": "env-config",
    }
    if basename in m:
        return m[basename]
    return m.get(ext.lower(), "unknown")


def get_git_tracked_files(root: Path) -> set[str] | None:
    """Возвращает set путей, отслеживаемых git. None если не git-репозиторий."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if result.returncode != 0:
            return None
        return set(line.strip() for line in result.stdout.splitlines() if line.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Основная логика обхода
# ---------------------------------------------------------------------------

def walk_and_collect(
    root: Path,
    *,
    exclude_dirs: set[str],
    exclude_dir_prefixes: tuple[str, ...],
    include_exts: set[str],
    exclude_filenames: set[str],
    exclude_patterns: list[str],
    max_size_bytes: int,
    git_tracked: set[str] | None,
) -> tuple[list[FileInfo], RepoStats]:
    """Обойти дерево, вернуть список файлов к включению + статистику."""
    stats = RepoStats()
    collected: list[FileInfo] = []

    import fnmatch

    # Объединить default patterns с CLI patterns
    all_patterns = list(DEFAULT_EXCLUDE_PATTERNS) + list(exclude_patterns)

    for dirpath, dirnames, filenames in os.walk(root):
        # Модифицируем dirnames in-place чтобы os.walk не заходил в исключённые каталоги
        kept_dirs = []
        for d in dirnames:
            if d in exclude_dirs:
                stats.skipped_dir += 1
                continue
            if d.startswith(".git") or d == "__pycache__":
                stats.skipped_dir += 1
                continue
            # Проверяем префиксы (backup_*, pre_*, _old, etc.)
            if any(d.startswith(prefix) for prefix in exclude_dir_prefixes):
                stats.skipped_dir += 1
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fname in filenames:
            abs_path = Path(dirpath) / fname
            try:
                rel_path = abs_path.relative_to(root)
            except ValueError:
                continue

            stats.total_files_scanned += 1
            rel_posix = rel_path.as_posix()

            # 1. Skip by filename (exact match)
            if fname in exclude_filenames:
                stats.skipped_name += 1
                continue

            # 2. Skip by glob pattern (default patterns + CLI patterns)
            if any(fnmatch.fnmatch(rel_posix, pat) or fnmatch.fnmatch(fname, pat)
                   for pat in all_patterns):
                stats.skipped_pattern += 1
                continue

            # 3. Git-tracked filter
            if git_tracked is not None and rel_posix not in git_tracked:
                stats.skipped_git += 1
                continue

            # 4. Determine extension / special basename
            ext = ("." + fname.rsplit(".", 1)[1].lower()) if "." in fname else ""
            is_special = fname in SPECIAL_BASENAMES

            # 5. Skip by hard exclude ext (binaries, archives, etc.)
            if ext in HARDCODED_EXCLUDE_EXTS:
                stats.skipped_ext += 1
                continue

            # 6. Include only if ext in include list OR basename is special
            if not is_special and ext not in include_exts:
                stats.skipped_ext += 1
                continue

            # 7. Size check
            try:
                size = abs_path.stat().st_size
            except OSError:
                stats.skipped_size += 1
                continue

            if size > max_size_bytes:
                stats.skipped_size += 1
                continue

            if size == 0:
                # пустой файл — пропускаем (нет контента)
                stats.skipped_size += 1
                continue

            # 8. Binary detection
            if is_binary(abs_path):
                stats.skipped_binary += 1
                continue

            # 9. Read text
            content = read_text_safely(abs_path)
            if content is None:
                stats.skipped_binary += 1
                continue

            lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            fi = FileInfo(
                path=rel_path, abs_path=abs_path,
                size=size, ext=ext or "(no-ext)", lines=lines,
            )
            collected.append(fi)
            stats.included += 1
            stats.included_bytes += size
            ext_key = ext if ext else "(no-ext)"
            stats.by_ext[ext_key] = stats.by_ext.get(ext_key, 0) + 1

    # Sort: by path for stable output
    collected.sort(key=lambda f: str(f.path).lower())
    return collected, stats


# ---------------------------------------------------------------------------
# Генерация выходного файла
# ---------------------------------------------------------------------------

HEADER_TEMPLATE = """================================================================================
repo2txt output
================================================================================
Project root:  {root}
Generated:     {timestamp}
Total files scanned:     {scanned}
Files included:          {included}
Total included bytes:    {bytes} ({bytes_kb} KB, {bytes_mb} MB)
Skipped (dir):           {sk_dir}
Skipped (ext/binary):    {sk_ext}
Skipped (size > limit):  {sk_size}
Skipped (filename):      {sk_name}
Skipped (pattern):       {sk_pat}
Skipped (git untracked): {sk_git}
Skipped (binary \\\\x00): {sk_bin}
Max file size:           {max_kb} KB

Files by extension:
{by_ext}

File tree (included files only):
{tree}
================================================================================
"""


def build_tree(files: list[FileInfo], root: Path) -> str:
    """Упрощённое дерево включённых файлов."""
    if not files:
        return "(no files included)"

    # Группируем по родительскому каталогу
    lines: list[str] = []
    current_dir: Path | None = None
    for f in files:
        parent = f.path.parent
        if parent != current_dir:
            current_dir = parent
            if str(parent) == ".":
                lines.append(f"{root.name}/")
            else:
                lines.append(f"{root.name}/{parent}/")
        lines.append(f"  {f.path.name}  ({f.size} B, {f.lines} L)")

    return "\n".join(lines)


FILE_DELIM_OPEN = "=== FILE: {path} ({size} bytes, {lines} lines, {lang}) ==="
FILE_DELIM_CLOSE = "=== END FILE: {path} ==="


def write_output(
    out_path: Path,
    files: list[FileInfo],
    root: Path,
    stats: RepoStats,
    max_size_kb: int,
) -> None:
    """Записать финальный .txt файл."""
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    by_ext_str = "\n".join(
        f"  {ext:12s}  {count} file(s)"
        for ext, count in sorted(stats.by_ext.items(), key=lambda kv: -kv[1])
    ) or "  (none)"

    tree = build_tree(files, root)

    header = HEADER_TEMPLATE.format(
        root=str(root),
        timestamp=timestamp,
        scanned=stats.total_files_scanned,
        included=stats.included,
        bytes=stats.included_bytes,
        bytes_kb=f"{stats.included_bytes / 1024:.1f}",
        bytes_mb=f"{stats.included_bytes / (1024 * 1024):.3f}",
        sk_dir=stats.skipped_dir,
        sk_ext=stats.skipped_ext,
        sk_size=stats.skipped_size,
        sk_name=stats.skipped_name,
        sk_pat=stats.skipped_pattern,
        sk_git=stats.skipped_git,
        sk_bin=stats.skipped_binary,
        max_kb=max_size_kb,
        by_ext=by_ext_str,
        tree=tree,
    )

    with open(out_path, "w", encoding="utf-8") as out:
        out.write(header)
        out.write("\n\n")
        for fi in files:
            content = read_text_safely(fi.abs_path)
            if content is None:
                # пропустили на повторном чтении — пишем заглушку
                out.write(FILE_DELIM_OPEN.format(
                    path=fi.path, size=fi.size, lines=fi.lines,
                    lang="unreadable",
                ) + "\n")
                out.write("(could not re-read file)\n")
                out.write(FILE_DELIM_CLOSE.format(path=fi.path) + "\n\n")
                continue

            lang = detect_lang(fi.ext, fi.path.name)
            out.write(FILE_DELIM_OPEN.format(
                path=fi.path, size=fi.size, lines=fi.lines, lang=lang,
            ) + "\n")
            # Убедимся что контент заканчивается переводом строки
            if not content.endswith("\n"):
                content += "\n"
            out.write(content)
            if not content.endswith("\n"):
                out.write("\n")
            out.write(FILE_DELIM_CLOSE.format(path=fi.path) + "\n\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Собрать весь релевантный код проекта в один текстовый файл.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--root", default=".",
                    help="Корень проекта (по умолчанию: текущий каталог)")
    ap.add_argument("--output", default=None,
                    help="Куда писать результат (по умолчанию: <root>/download/repo2txt_output.txt)")
    ap.add_argument("--max-size", type=int, default=1024,
                    help="Максимальный размер файла в KB (по умолчанию: 1024 = 1MB)")
    ap.add_argument("--include-ext", default="",
                    help="Дополнительные расширения к дефолтным (через запятую, с точкой: .log,.cfg)")
    ap.add_argument("--exclude-dir", default="",
                    help="Дополнительные каталоги к исключению (через запятую)")
    ap.add_argument("--exclude-pattern", action="append", default=[],
                    help="Glob-шаблон для исключения файлов (можно несколько раз)")
    ap.add_argument("--stats-only", action="store_true",
                    help="Только напечатать статистику, не записывать файл")
    ap.add_argument("--git-tracked-only", action="store_true",
                    help="Включать только файлы, отслеживаемые git")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.stderr.write(f"ERROR: root {root!s} is not a directory\n")
        return 1

    # Resolve output path
    if args.output:
        out_path = Path(args.output).resolve()
    else:
        out_dir = root / "download"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "repo2txt_output.txt"

    # Build exclude/include sets
    exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
    if args.exclude_dir:
        exclude_dirs.update(d.strip() for d in args.exclude_dir.split(",") if d.strip())

    include_exts = set(DEFAULT_INCLUDE_EXTS)
    if args.include_ext:
        for ext in args.include_ext.split(","):
            ext = ext.strip()
            if ext:
                if not ext.startswith("."):
                    ext = "." + ext
                include_exts.add(ext.lower())

    exclude_patterns = list(args.exclude_pattern)

    # Git filter
    git_tracked: set[str] | None = None
    if args.git_tracked_only:
        git_tracked = get_git_tracked_files(root)
        if git_tracked is None:
            sys.stderr.write("WARN: --git-tracked-only but no git repo at root; ignoring\n")
        else:
            sys.stderr.write(f"[git] tracked files: {len(git_tracked)}\n")

    max_size_bytes = args.max_size * 1024

    # Walk
    files, stats = walk_and_collect(
        root,
        exclude_dirs=exclude_dirs,
        exclude_dir_prefixes=DEFAULT_EXCLUDE_DIR_PREFIXES,
        include_exts=include_exts,
        exclude_filenames=DEFAULT_EXCLUDE_FILENAMES,
        exclude_patterns=exclude_patterns,
        max_size_bytes=max_size_bytes,
        git_tracked=git_tracked,
    )

    # Print stats
    print(f"Project root:        {root}")
    print(f"Files scanned:       {stats.total_files_scanned}")
    print(f"Files included:      {stats.included}")
    print(f"Included bytes:      {stats.included_bytes} ({stats.included_bytes/1024:.1f} KB)")
    print(f"Skipped (filename):  {stats.skipped_name}")
    print(f"Skipped (pattern):   {stats.skipped_pattern}")
    print(f"Skipped (git):       {stats.skipped_git}")
    print(f"Skipped (size):      {stats.skipped_size}")
    print(f"Skipped (ext/bin):   {stats.skipped_ext}")
    print(f"Skipped (binary):    {stats.skipped_binary}")
    print()
    print("Files by extension:")
    for ext, count in sorted(stats.by_ext.items(), key=lambda kv: -kv[1]):
        print(f"  {ext:12s}  {count}")

    if args.stats_only:
        return 0

    # Write
    write_output(out_path, files, root, stats, args.max_size)
    print(f"\nWritten: {out_path}  ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
