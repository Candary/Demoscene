# Uroboros migration: разбор замечаний GLM

Разбор по пунктам — что реально, что нет, и что с этим делать.

## Короткая оценка

| Пункт GLM | Статус | Действие |
|---|---|---|
| #1 dynamic imports | **реальный gap** (не баг) | добавил `_scan_dynamic_imports` в скрипт миграции |
| #2 «другой проект» | **workflow**, не код | `--target <other>` + `--check` уже поддерживаются; ничего не меняю |
| #3 `parent.parent` в шиме | **реальный баг** | исправил; ниже диф |

---

## #3 — баг в шиме: `parent.parent` вместо `parent`

GLM прав. В моём шиме `_self_check` искал `patches/` как `Path(__file__).parent.parent / "patches"`. Это корректно только когда шим лежит в `examples/engine.py` (тогда `parent.parent` = корень проекта). Но шим по инструкции копируется **в корень проекта** рядом с `patches/` — и там `parent.parent` указывает на родителя проекта, а не на сам проект. Баг «тихий»: `patches.is_dir()` вернёт `False`, проверка скажет `skipped`, но ничего не проверит.

**Фикс.** Добавить `from pathlib import Path` в шапку шима (после `import warnings as _warnings`) и заменить `_self_check` на:

```python
def _find_patches_dir() -> Path | None:
    """Найти `patches/` рядом с шимом.

    Два кандидата, в порядке приоритета:
      1. `<dir of shim>/patches`        — шим в корне проекта (рекомендуемое размещение)
      2. `<parent of shim dir>/patches` — шим в `examples/` (исходное размещение в репо)
    """
    here = Path(__file__).resolve().parent
    for candidate in (here / "patches", here.parent / "patches"):
        if candidate.is_dir():
            return candidate
    return None


def _self_check() -> int:
    import tempfile

    print(f"engine shim: FORMAT = {FORMAT!r}")
    if FORMAT != "uroboros.patch/2":
        print(f"engine shim: unexpected FORMAT {FORMAT!r}")
        return 1

    if canonical({"b": 2, "a": 1}) != b'{"a":1,"b":2}':
        print("engine shim: canonical() returned unexpected bytes")
        return 1
    if digest(b"x") != digest(b"x") or digest(b"x") == digest(b"y"):
        print("engine shim: digest() is not deterministic")
        return 1
    print("engine shim: canonical/digest ok")

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

        patches = _find_patches_dir()
        if patches is None:
            print("engine shim: PatchRegistry skipped (no patches/ found near shim)")
            print("engine shim: all reachable checks passed")
            return 0

        r = PatchRegistry(patches)
        print(f"engine shim: PatchRegistry ok ({len(r.ops)} op(s) from {patches})")

        if not (patches / "geometry.py").exists():
            print("engine shim: Uroboros.run skipped (patches/geometry.py not found)")
            print("engine shim: all reachable checks passed")
            return 0

        u = Uroboros(root=f"{tmp}/u", patches=patches, workers=1)
        plan = {
            "format": FORMAT,
            "name": "shim_smoke",
            "nodes": [{
                "id": "g", "target": "scene", "operation": "geometry.generate",
                "params": {"width": 3.0, "depth": 2.0},
            }],
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
```

Остальное в шиме не меняется.

---

## #1 — dynamic imports: реальный gap, закрыт

Статический анализ `from engine import ...` / `import engine` действительно не видит `importlib.import_module("engine")`, `__import__("engine")` и `importlib.util.find_spec("engine")`. Если такой код есть, удаление шима сломает его с `ModuleNotFoundError`.

**Добавить в `scripts/migrate_v0_2_to_v0_3.py`** (после `DEFAULT_EXCLUDES`):

```python
_DYNAMIC_IMPORT_FUNCS = {"__import__", "import_module", "find_spec"}


def _call_name(func: ast.AST) -> str | None:
    """Вернуть пунктирное имя вызываемого (a.b.c) или None."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = [func.attr]
        node = func.value
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _is_dynamic_import_call(fname: str) -> bool:
    """Срабатывает на любой <prefix>.import_module / __import__ / find_spec.

    Покрывает importlib.import_module, il.import_module, from importlib import
    import_module, __import__, importlib.util.find_spec. Ложные срабатывания
    на пользовательских одноимённых функциях возможны, но это warning, не error.
    """
    return fname.rsplit(".", 1)[-1] in _DYNAMIC_IMPORT_FUNCS


def _first_string_arg(node: ast.Call) -> ast.Constant | None:
    """Первый строковый аргумент: позиционный или keyword name=."""
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0]
    for kw in node.keywords:
        if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value
    return None


def _scan_dynamic_imports(path: Path, tree: ast.AST) -> list[str]:
    """Warnings про динамические импорты `engine`.

    НЕ покрыто (принципиально не статично): exec(), eval(), sys.modules[...],
    вычисляемые имена, плагин-системы (entry_points, pkgutil). Для них —
    оставляйте шим.
    """
    warnings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = _call_name(node.func)
        if fname is None or not _is_dynamic_import_call(fname):
            continue
        arg = _first_string_arg(node)
        if arg is None:
            warnings.append(
                f"{path}:{node.lineno}: {fname}() with non-constant argument; "
                f"cannot verify if it imports 'engine'"
            )
            continue
        if arg.value == "engine" or arg.value.startswith("engine."):
            kind = "find_spec" if fname.endswith("find_spec") else "import"
            warnings.append(
                f"{path}:{node.lineno}: dynamic {kind} of {arg.value!r} via {fname}() — "
                f"won't be rewritten; keep the shim or fix manually"
            )
    return warnings
```

**`FileResult`** — добавить поле:

```python
@dataclass
class FileResult:
    path: Path
    changes: int = 0
    warnings: list[str] = field(default_factory=list)
    dynamic_warnings: list[str] = field(default_factory=list)  # NEW
    old_source: str = ""
    new_source: str = ""
    error: str | None = None
    # ...
```

**`migrate_file`** — сразу после `ast.parse` (до сбора статических правок):

```python
    res.dynamic_warnings.extend(_scan_dynamic_imports(path, tree))
```

**`main`** — вести `dynamic_warnings` отдельно и учитывать в `--check`:

```python
    all_warnings: list[str] = []
    dynamic_warnings: list[str] = []   # NEW

    for path in files:
        # ...
        all_warnings.extend(res.warnings)
        dynamic_warnings.extend(res.dynamic_warnings)   # NEW
        # ...

    # в конце, перед итогом:
    if dynamic_warnings:
        print(f"Dynamic import warnings: {len(dynamic_warnings)}")
        for w in dynamic_warnings:
            print(f"  - {w}")

    if args.check:
        if changed_files:
            print("check failed: static `engine` imports remain")
            return 1
        if dynamic_warnings and not args.allow_dynamic:   # NEW
            print("check failed: dynamic `engine` imports remain "
                  "(pass --allow-dynamic to ignore)")
            return 1
```

**`build_parser`** — добавить флаг:

```python
    p.add_argument("--allow-dynamic", action="store_true",
                   help="при --check не падать на динамических импортах 'engine'")
```

Теперь `--check` падает, если остались **либо** статические, **либо** динамические импорты `engine`. Проекты, которые осознанно используют `importlib.import_module("engine")` для опциональных плагинов, могут передать `--allow-dynamic`.

---

## #2 — «другой проект»

Согласен, но это не код, а workflow. Скрипт уже принимает `--target <other_project>` и `--check`. Рекомендованный порядок для каждого внешнего проекта:

```bash
# 1. Сначала проверить, что вообще нужно
python scripts/migrate_v0_2_to_v0_3.py --target /path/to/other --check
# exit 0 → миграция не нужна, шим не трогаем
# exit 1 → нужна; см. --diff

# 2. Прогнать dry-run с диффом
python scripts/migrate_v0_2_to_v0_3.py --target /path/to/other --diff

# 3. Применить с бэкапами
python scripts/migrate_v0_2_to_v0_3.py --target /path/to/other --apply --backup
```

Если `--check` в другом проекте вернул 1 — это и есть сигнал, что внешний проект ещё использует старый `engine.py` и нуждается в миграции. Если 0 — рекомендация «не делать» относится и к нему.

Один нюанс: `--check` теперь падает и на динамических импортах. Если внешний проект **намеренно** использует `importlib.import_module("engine")`, но готов оставить шим навсегда — `--allow-dynamic` вернёт exit 0.

---

## Что остаётся за пределами статического анализа

Это не баг, это граница метода. Для всех этих случаев единственный безопасный ответ — **оставить шим**:

- `exec("import engine")`, `eval("__import__('engine')")` — принципиально не статичны.
- `sys.modules["engine"]` (проверка загруженности) — не импорт, но семантика изменится, если шим удалить.
- Имя модуля вычисляется в рантайме: `name = "eng" + "ine"; importlib.import_module(name)`.
- Плагин-системы (`entry_points`, `pkgutil.iter_modules` с фильтром по префиксу) — у `engine` нет `entry_points`, но кто-то мог сделать свой загрузчик.
- Не-Python файлы (Jinja-шаблоны, `.ipynb`, конфиги, CI-скрипты) — GLM упомянул это в #1, и я согласен: мой скрипт смотрит только `.py`. Если в проекте есть `import engine` в Jupyter-ноутбуках или в shell-скриптах (например, `python -c "import engine"`) — это не покрыто.

Для этих случаев в `scripts/` можно отдельно погрепать:

```bash
grep -rn --exclude-dir=.git --exclude-dir=.venv --exclude-dir=uroboros \
  -E '(import +engine|from +engine +import|import_module\(["'"'"']engine|__import__\(["'"'"']engine)' \
  .
```

Это не заменяет `--check`, но закрывает то, что не видит AST.

---

## Итог

- **#3** — реальный баг, исправлен (`_find_patches_dir` + `parent.parent` → два кандидата).
- **#1** — реальный gap, закрыт (`_scan_dynamic_imports`, `dynamic_warnings`, `--allow-dynamic`).
- **#2** — не код, а workflow; `--target` уже есть, `--check` теперь ловит и динамику.
- **За пределами** — `exec`/`eval`/`sys.modules`/плагины/не-Python файлы; для них — оставить шим (он лёгкий и ничего не ломает).