# Rollback procedure — Color Matrix integration

**Created:** 2026-11-01
**Snapshot:** `download/snapshots/pre-color-matrix-migration.zip` (897 KB, MD5 `794634f2...`)
**Purpose:** Откат к состоянию проекта БЕЗ Color Matrix, если интеграция неудачна

---

## Что в snapshot (8 файлов)

| Файл | Зачем в snapshot |
|------|-----------------|
| `download/aesthetics.md` | Будет упрощён в W20 — snapshot хранит v0.4 (316 строк, cleaned) |
| `download/aesthetics.docx` | Pandoc-rendered v0.4 (для reference) |
| `download/demo_intro/meta.auto` | Текущее состояние (pandoc tokens, БЕЗ color_matrix tokens) |
| `download/demo_intro/roadmap.md` | Tasks 1-67 (БЕЗ Task 68 color matrix integration) |
| `download/sigil_btb_documentation.docx` | v1.7 pandoc output (reference) |
| `roadmap.md` | Synced copy |
| `scripts/gen_sigil_btb_doc.py` | Python generator (legacy backup, unchanged) |

---

## Что будет добавлено во время интеграции (и удалено при откате)

| Путь | Что | Что произойдёт при откате |
|------|-----|---------------------------|
| `/home/z/my-project/color_matrix/` | Вся папка Color Matrix (NPZ, Python, policy, tests) | `rm -rf color_matrix/` |
| `/home/z/my-project/scripts/anim_parser.py` | Парсер `%anim[...]` shortcut | `rm scripts/anim_parser.py` |
| `/home/z/my-project/download/color_catalog.md` | Каталог цветов по Tasks | `rm download/color_catalog.md` |
| `/home/z/my-project/download/color_matrix_backup.zip` | Backup zip | `rm download/color_matrix_backup.zip` |

---

## Команды отката (существующие глаголы, без новых сигилов)

### Сценарий A: Color Matrix не нравится, отключить

```
!remove color-matrix
  reason: <конкретная причина>
  action: disable Color Matrix, restore pre-integration state
  preserve: color_matrix/ → legacy/color_matrix_disabled_<date>/ (не delete)
```

**Что я делаю:**
1. `mv color_matrix/ legacy/color_matrix_disabled_$(date)/`
2. `rm scripts/anim_parser.py download/color_catalog.md download/color_matrix_backup.zip`
3. Restore из snapshot:
   - `unzip download/snapshots/pre-color-matrix-migration.zip -d /tmp/restore/`
   - `cp /tmp/restore/download/aesthetics.md download/aesthetics.md`
   - `cp /tmp/restore/download/demo_intro/meta.auto download/demo_intro/meta.auto`
   - `cp /tmp/restore/download/demo_intro/roadmap.md download/demo_intro/roadmap.md`
   - `cp /tmp/restore/roadmap.md roadmap.md`
4. Update meta.auto: убрать `[color_matrix:*]` tokens и `color_matrix/` из `[avoid:default]`
5. Report: rollback complete, project at pre-Color-Matrix state

**Время:** ~30 секунд

### Сценарий B: Полный revert к snapshot

```
!revert pre-color-matrix-migration
```

**Что я делаю:**
1. `unzip download/snapshots/pre-color-matrix-migration.zip -d /home/z/my-project/`
2. `rm -rf color_matrix/ scripts/anim_parser.py download/color_catalog.md download/color_matrix_backup.zip`
3. Verify: `ls color_matrix/ 2>&1` → "No such file or directory"
4. Report: full revert complete

**Время:** ~10 секунд

### Сценарий C: Sandbox recycled, restore Color Matrix из backup

Если sandbox перезапустился и `color_matrix/` пропала, но вы хотите её ВОССТАНОВИТЬ (не откатить):

```bash
cd /home/z/my-project/
unzip download/color_matrix_backup.zip
python3 color_matrix/output/color_matrix_python/reader.py  # verify
```

**Время:** ~5 секунд

---

## Защита от случайного удаления (3 слоя)

| Слой | Механизм | Что защищает |
|------|----------|--------------|
| **1. [avoid:default]** | `meta.auto` будет включать `color_matrix/` после интеграции | Защита от `!clean` и accidental cleanup |
| **2. Backup zip** | `download/color_matrix_backup.zip` (после интеграции) | Sandbox persistence |
| **3. Pre-integration snapshot** | `download/snapshots/pre-color-matrix-migration.zip` (897 KB) | Rollback к состоянию БЕЗ Color Matrix |

---

## Проверка snapshot (только что выполнена)

```
$ unzip -l download/snapshots/pre-color-matrix-migration.zip
Archive:  download/snapshots/pre-color-matrix-migration.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
    16483  2026-11-01 16:13   download/aesthetics.md
   508743  2026-11-01 16:13   download/aesthetics.docx
     2104  2026-11-01 16:13   download/demo_intro/meta.auto
    53950  2026-11-01 16:13   download/demo_intro/roadmap.md
   313025  2026-11-01 16:13   download/sigil_btb_documentation.docx
    53950  2026-11-01 16:13   roadmap.md
   112225  2026-11-01 16:13   scripts/gen_sigil_btb_doc.py
---------                     -------
  1062480                     7 files + folder structure
```

✅ Snapshot валиден, 7 файлов, 897 KB сжатый.

---

## Статус

- ✅ Snapshot создан: `download/snapshots/pre-color-matrix-migration.zip`
- ✅ MD5: `794634f2759e154a5eed193dfdd19b79`
- ✅ Rollback procedure задокументирована
- ⏸ Ожидает: ваше `#ok` для запуска интеграции Color Matrix

---

## Готово к запуску интеграции

Теперь если Color Matrix integration пройдёт плохо:
- `!remove color-matrix` → отключить, сохранить в legacy/
- `!revert pre-color-matrix-migration` → полный revert за 10 секунд
- Все 3 сценария covered

**Принцип «не плодить инфраструктуру» соблюдён:** used existing `!snapshot`, `!remove`, `!revert` verbs. No new sigil.
