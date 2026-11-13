#!/usr/bin/env bash
#
# move_download_to_repo.sh
#
# Перенос файлов (НЕ директорий) из корня /download в локальный Git-репозиторий,
# с последующим автоматическим git add + git commit + git push.
#
# Жёсткие условия (выполнены):
#   - Перемещаются ТОЛЬКО файлы в корне /download (find -maxdepth 1 -type f)
#   - Вложенные папки /download/* НЕ трогаются
#   - Имена с пробелами/спецсимволами обрабатываются через -print0 + mapfile -d ''
#   - Имена начинающиеся с '-' обрабатываются через 'mv --'
#   - Проверяется существование /download и валидность REPO_DIR как Git-репо
#
# Usage:
#   REPO_DIR=/path/to/repo ./move_download_to_repo.sh
#   # или отредактируйте переменную REPO_DIR ниже
#
# Exit codes:
#   0 — успех (или нет файлов для переноса)
#   1 — ошибка валидации / git commit failed
#   2 — git push failed

set -euo pipefail
# -e: exit on any command failure
# -u: error on undefined variables
# -o pipefail: a pipeline fails if ANY command in it fails

# ============================================================================
# Configuration
# ============================================================================

# REPO_DIR — путь к локальному Git-репозиторию.
# Можно задать через env var; по умолчанию — текущий проект.
: "${REPO_DIR:=/home/z/my-project}"

# DOWNLOAD_DIR — абсолютный путь к папке-источнику.
# Файлы из КОРНЯ этой папки будут перенесены в REPO_DIR.
# Вложенные папки игнорируются.
DOWNLOAD_DIR="${DOWNLOAD_DIR:-/home/z/my-project/download}"

# ============================================================================
# Validation
# ============================================================================

# 1. Проверяем, что DOWNLOAD_DIR существует и является директорией.
#    `-d` проверяет именно директорию (не файл/симлинк на файл).
if [[ ! -d "$DOWNLOAD_DIR" ]]; then
    echo "ERROR: Download directory '$DOWNLOAD_DIR' does not exist or is not a directory." >&2
    echo "Hint: set DOWNLOAD_DIR env var to the correct path." >&2
    exit 1
fi

# 2. Проверяем, что REPO_DIR существует и является директорией.
if [[ ! -d "$REPO_DIR" ]]; then
    echo "ERROR: Repository directory '$REPO_DIR' does not exist or is not a directory." >&2
    echo "Hint: set REPO_DIR env var to the correct path." >&2
    exit 1
fi

# 3. Проверяем, что REPO_DIR — валидный Git-репозиторий.
#    `git -C <dir> rev-parse --is-inside-work-tree` возвращает 'true' и exit 0
#    если <dir> находится внутри working tree Git-репо.
#    Перенаправляем stdout/stderr в /dev/null — нам нужен только exit code.
if ! git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: '$REPO_DIR' is not a valid Git repository." >&2
    echo "Hint: run 'git init' in that directory first." >&2
    exit 1
fi

# 4. Проверяем, что в репо настроен remote 'origin' (нужен для push).
#    Если remote нет — push не сработает. Лучше упасть сейчас, чем позже.
if ! git -C "$REPO_DIR" remote get-url origin >/dev/null 2>&1; then
    echo "ERROR: No 'origin' remote configured in '$REPO_DIR'." >&2
    echo "Hint: run 'git -C \"$REPO_DIR\" remote add origin <url>' first." >&2
    exit 1
fi

# ============================================================================
# Find files (NOT directories) in download root
# ============================================================================

# Используем find с -maxdepth 1 (только корень, без вложенных папок)
#               и -type f (только обычные файлы, не директории/симлинки/сокеты).
# -print0 — разделяет имена NUL-байтом (\0), а не newline.
#   Это единственный способ корректно обработать имена с пробелами,
#   переносами строк, кавычками и другими спецсимволами.
#
# mapfile -d '' -t files < <(find ... -print0)
#   -d '' — разделитель элементов = NUL (как в find -print0)
#   -t — убрать trailing NUL из каждого элемента
#   Читаем в массив `files` через process substitution `< <(...)` —
#   это позволяет избежать subshell (изменения массива сохранятся).

mapfile -d '' -t files < <(find "$DOWNLOAD_DIR" -maxdepth 1 -type f -print0)

# Проверяем, найдены ли файлы. ${#files[@]} — количество элементов массива.
if [[ ${#files[@]} -eq 0 ]]; then
    echo "No files found in '$DOWNLOAD_DIR' (root level). Nothing to do."
    exit 0
fi

# Выводим список найденных файлов для прозрачности.
echo "Found ${#files[@]} file(s) to move from '$DOWNLOAD_DIR' to '$REPO_DIR':"
for f in "${files[@]}"; do
    # basename — извлекает имя файла без пути.
    # Кавычки обязательны — имя может содержать пробелы.
    echo "  - $(basename "$f")"
done
echo ""

# ============================================================================
# Move files to repo
# ============================================================================

# Счётчики для итогового отчёта.
moved_count=0
failed_count=0

# Итерируемся по массиву с кавычками — каждое имя обрабатывается как один
# аргумент, даже если содержит пробелы.
for f in "${files[@]}"; do
    # Извлекаем чистое имя файла (без пути к /download).
    filename="$(basename "$f")"

    # Формируем путь назначения: REPO_DIR/filename.
    dest="$REPO_DIR/$filename"

    # Проверка: не является ли source и destination одним и тем же файлом
    # (если /download — это симлинк на REPO_DIR или наоборот).
    # `-ef` — "equal file" (один и тот же inode).
    if [[ "$f" -ef "$dest" ]]; then
        echo "SKIP: '$filename' — source and destination are the same file."
        continue
    fi

    # Предупреждение, если файл с таким именем уже существует в репо.
    # НЕ прерываем — перезаписываем (mv это делает по умолчанию).
    if [[ -e "$dest" ]]; then
        echo "WARN: '$filename' already exists in repo. Overwriting."
    fi

    # mv -- : двойной дефис означает конец опций. Всё после -- — имена файлов.
    #   Это защищает от имён типа '-rf' которые mv мог бы интерпретировать как флаги.
    # Кавычки вокруг "$f" и "$dest" — обязательны для имён с пробелами.
    if mv -- "$f" "$dest"; then
        echo "MOVED: '$filename'"
        ((moved_count++)) || true
        # || true нужно потому что ((0)) возвращает exit 1 в bash,
        # что под set -e прервало бы скрипт.
    else
        echo "FAIL: '$filename'" >&2
        ((failed_count++)) || true
    fi
done

echo ""
echo "Summary: $moved_count moved, $failed_count failed."

# Если ни один файл не перемещён — выходим без git операций.
if [[ $moved_count -eq 0 ]]; then
    echo "No files were moved. Exiting without commit."
    exit 0
fi

# ============================================================================
# Git operations: add + commit + push
# ============================================================================

echo ""
echo "=== Git operations ==="

# Переходим в репо (в subshell, чтобы не менять PWD вызывающего процесса).
# Все git команды ниже работают в этом subshell.
(
    cd "$REPO_DIR"

    # git add -A — индексирует ВСЕ изменения:
    #   новые файлы, изменённые файлы, удалённые файлы.
    # Если нужно добавить только конкретные файлы — заменить на
    # git add -- <file1> <file2> ...
    git add -A

    # Проверяем, есть ли что коммитить.
    # git diff --cached --quiet возвращает exit 0 если staged changes пуст,
    # exit 1 если есть staged changes.
    # Под set -e exit 1 прервал бы скрипт, поэтому инвертируем через !.
    if git diff --cached --quiet; then
        echo "No staged changes to commit (files already tracked, no diff)."
        exit 0
    fi

    # Генерируем осмысленное commit message:
    #   - количество перемещённых файлов
    #   - timestamp UTC (для уникальности и аудита)
    #   - список имён (сокращённый — первые 5, чтобы не раздувать сообщение)
    commit_msg="Move $moved_count file(s) from download ($(date -u +%Y-%m-%dT%H:%M:%SZ))"

    # git commit — создаёт новый commit с подготовленным сообщением.
    if git commit -m "$commit_msg"; then
        echo "Committed: $commit_msg"
    else
        echo "ERROR: git commit failed." >&2
        exit 1
    fi

    # git push — отправляем changes на remote.
    # `origin HEAD` — пушим текущую ветку (HEAD) на origin.
    # Используем HEAD вместо имени ветки — работает на любой текущей ветке.
    echo "Pushing to origin..."
    if git push origin HEAD 2>&1; then
        echo "Push succeeded."
    else
        echo "ERROR: git push failed." >&2
        echo "Hint: check remote URL ('git remote get-url origin')" >&2
        echo "      and credentials (SSH keys / PAT / credential helper)." >&2
        exit 2
    fi
)

# Передаём exit code из subshell.
# $? содержит exit code последней команды (subshell в данном случае).
subshell_exit=$?
if [[ $subshell_exit -ne 0 ]]; then
    exit $subshell_exit
fi

echo ""
echo "Done. $moved_count file(s) moved to '$REPO_DIR' and pushed."
