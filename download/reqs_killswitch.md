# Требования: Kill-switch для артефактов протокола

**Документ:** reqs_killswitch.md
**Дата:** 2026-10-31
**Статус:** REJECTED 2026-10-31 — пользователь отказался от концепции kill-switch.
**Связанные задачи:** историческая запись; в roadmap Task 64 НЕ заведён, правила 16-18 НЕ введены.
**Автор:** ассистент
**Назначение:** спецификация механизма безболезненного отказа от артефактов проекта (booster_final.json, scripts/query_booster.py и любых будущих) с переносом в `disallowed/` и cleanup всех упоминаний.

> ⚠ **REJECTED (2026-10-31):** Пользователь явно отказался от kill-switch концепции.
> Реализация не выполнена: `×` sigil НЕ введён, `×disallow`/`×allow` глаголов НЕТ,
> `disallowed/` папки НЕТ, `registry.json` НЕТ, `scripts/disallow_artifact.py` НЕ написан,
> Rules 16-18 НЕ активны. Документ сохранён как историческая запись дизайна,
> который был предложен и отклонён.
>
> Если в будущем потребуется отказаться от артефакта — будет сделано manual:
> ad-hoc cleanup скриптом под конкретный случай, без общей инфраструктуры.
>
> Документ оставлен в `download/` как reference; можно удалить, когда станет не нужен.

---

## 1. Постановка проблемы

Текущий протокол sigil+BTB v2.1 имеет 5 сигилов (`? ! @ # &`) и не предоставляет явного пути для **отказа от артефакта** — файла, который перестал быть нужным или оказался вредным. Возможные сценарии:

- `booster_final.json` (Task 63) — Cg-bias может оказаться сильнее, чем ожидалось; top3=77% на Cg-репозитории не обязательно переносится на GLSL 3.3 core проект.
- `scripts/query_booster.py` — orphaned dependency, если booster сам disallowed.
- Будущие артефакты — любой вводимый tool/script/policy может потребовать отката.

**Принцип:** kill-switch проектируется **до** интеграции, а не после. Как emergency-exit в самолёте — чертится вместе с фюзеляжем, а не прорезается в полёте.

Без явного механизма отказ превращается в:
- ручную чистку roadmap (3 копии) / meta.auto / btb_stats.json / docx / scripts — долго, error-prone
- забытые упоминания в архивных файлах — будущие сессии думают, что артефакт активен
- необратимость — файл удалён, history потеряна
- страх перед интеграцией новых tools («а вдруг не подойдёт, а откатывать больно»)

---

## 2. Предлагаемое решение

### 2.1 Новый сигил `×` (U+00D7 MULTIPLICATION SIGN)

| Свойство | Значение |
|----------|----------|
| Тип строки | rejection / quarantine / disallow |
| trace.log | **нет** (мета-операция, как `?` `&` `#`) |
| BTB | delta=[] (base-only, как `?` `&`) |
| Глаголы | `×disallow` `×allow` (2 глагола, минимально) |
| Reversible | да, через `×allow` |

**Почему `×`:**
- Универсально читается как «крестик/вычёркивание/reject»
- Visually distinct от 5 существующих сигилов (`? ! @ # &`)
- Не путается с wildcards (`*`) или флагами (`-`)
- Single character (как другие сигилы)
- Abandonment — значимое действие, заслуживает визуальной distinctности в чате

**Итого сигилов в протоколе:** 6 (`? ! @ # & ×`)
**Глаголов `×`:** 2 (`disallow`, `allow`)

### 2.2 Глаголы

#### `×disallow <artifact> [reason: ...] [scope: full|narrow]`

- `<artifact>` — путь к файлу или имя (поиск по project tree)
- `reason:` — **обязательный** (Rule 16, без него операция отменяется)
- `scope:` — опц., default=`full`
  - `full` — quarantine файла + cleanup всех упоминаний в проекте
  - `narrow` — только quarantine файла, без cleanup

#### `×allow <artifact> [to: <path>]`

- Восстановление из `disallowed/` обратно
- Требует предварительного `#ok` от пользователя (Rule 17 — восстановление значимое действие)
- `to:` — опц., default = `original_path` из registry.json

---

## 3. Filesystem layout

```
/home/z/my-project/
├── upload/           # input от пользователя (read-only)
├── download/         # deliverables
├── scripts/          # рабочие скрипты
├── disallowed/       # NEW — quarantine zone
│   ├── registry.json # метаданные всех disallowed артефактов
│   ├── booster_final.json     # (если disallowed)
│   └── query_booster.py       # (если disallowed)
├── skills/
└── tools/
```

**Свойства папки `disallowed/`:**
- Создаётся при первом `×disallow`
- Файлы внутри — read-only quarantine, не парсятся в normal workflow (Rule 18)
- `registry.json` — permanent log, никогда не gc'ется
- Удалять/изменять файлы в `disallowed/` можно только через `×allow` path

---

## 4. registry.json — схема

```json
{
  "version": "1.0",
  "disallowed": {
    "booster_final.json": {
      "disallowed_date": "2026-10-31T14:30:00+07:00",
      "original_path": "/home/z/my-project/upload/booster_final.json",
      "quarantined_path": "/home/z/my-project/disallowed/booster_final.json",
      "reason": "Cg-bias too strong for GLSL 3.3 project, L2 query overhead not justified, glslangValidator alone sufficient",
      "scope": "full",
      "cleanup_log": [
        "roadmap.md (3 copies): removed Task 63 entry, Section 6.3 lines 280-282, header line 6 '+ code booster' phrase",
        "meta.auto: removed [booster:llm_prompt_block] token, added [disallowed: booster_final.json]",
        "btb_stats.json: retired signature !feat *shader* (was booster-only)",
        "sigil_btb_documentation.docx: removed section 8 'Code Booster' (regenerated v1.5)",
        "scripts/validate_glsl.py: removed booster pre-generation comment (validator itself kept)",
        "scripts/gen_sigil_btb_doc.py: removed booster section from generator"
      ],
      "mentions_removed_count": 14,
      "reversible_via": "×allow booster_final.json",
      "task_id": 64
    }
  }
}
```

**Поля:**
- `disallowed_date` — ISO 8601 с tz
- `original_path` — абсолютный путь до quarantine
- `quarantined_path` — абсолютный путь после quarantine
- `reason` — обязательный, от пользователя
- `scope` — `full` / `narrow`
- `cleanup_log` — список всех модификаций проекта (для `×allow` reverse + audit)
- `mentions_removed_count` — сумма по cleanup_log
- `reversible_via` — строка-подсказка для восстановления
- `task_id` — roadmap Task number

---

## 5. Cleanup scope — что именно чистится при `×disallow X` (scope=full)

7 точек, all-or-nothing (atomic):

| # | Файл / артефакт | Что делается |
|---|-----------------|--------------|
| 1 | Filesystem | `mv <original_path> /home/z/my-project/disallowed/<filename>` |
| 2 | roadmap.md (×3 synced copies) | grep упоминаний артефакта → удалить строки или заменить на `~~DISALLOWED <date> — see disallowed/registry.json~~` |
| 3 | meta.auto | Убрать autotokens, ссылающиеся на артефакт; добавить `[disallowed: <artifact_name>]` |
| 4 | btb_stats.json | Retire сигнатуры, которые зависели от артефакта (не удалять статистику — помечать `retired: true`) |
| 5 | sigil_btb_documentation.docx | Перегенерировать без секций про артефакт (новая minor version) |
| 6 | scripts/*.py | Убрать references на артефакт в комментариях и code path (сам скрипт оставить, если он multi-purpose) |
| 7 | registry.json | Добавить entry с полным cleanup_log |

**Atomicity:** если любая из 7 точек fails — rollback всех изменений. Скрипт `scripts/disallow_artifact.py` реализует транзакцию через temp-staging (папка `.disallow-staging/` создаётся перед операцией, удаляется после success).

**Specific для booster_final.json + query_booster.py:**

| Artifact | Files modified | Mentions removed |
|----------|----------------|------------------|
| `booster_final.json` | 6 (roadmap×3, meta.auto, btb_stats, docx + 2 scripts) | ~14 |
| `scripts/query_booster.py` | 2 (roadmap, meta.auto) | ~4 |

---

## 6. Safety properties

1. **Atomic** — 7-step transaction, rollback при любой ошибке
2. **Dry-run** — `×disallow X --dry-run` показывает что изменилось бы, без реальных изменений (как `!clean dry-run` в backlog v1.5)
3. **Reversible** — `×allow X` восстанавливает всё по registry.json cleanup_log (в обратном порядке)
4. **Idempotent** — `×disallow X` когда X уже disallowed → no-op + warning `×already-disallowed: see registry.json`
5. **Auditable** — registry.json permanent log, никогда не gc
6. **Reason-gated** — без `reason:` операция отменяется (Rule 16)
7. **Confirm-gated** — `×allow` требует предварительного `#ok` от пользователя (Rule 17)
8. **Filesystem-isolated** — файлы в `disallowed/` никогда не читаются/не парсятся в normal workflow (Rule 18); если скрипт видит путь из registry.json в active context — это bug

---

## 7. Сравнение с альтернативами

| Вариант | Pros | Cons | Вердикт |
|---------|------|------|---------|
| **`×disallow`** (new sigil) | Visible, distinct, kill-switch semantics clear | 6th sigil, +complexity | ✅ RECOMMENDED |
| `#disallow` (extend `#`) | No new sigil, fits `#rule`/`#proto` pattern | Buried in `#` (7 commands), less visible | alternative |
| `!disallow` (extend `!`) | Reuses `!` | Requires trace.log — wrong for meta op | ❌ rejected |
| `&disallow` (extend `&`) | Reuses `&` | `&` is discussion, not action — wrong | ❌ rejected |

**Рекомендация:** `×` (new sigil). Принцип «не плодить сигилы» (отказ `!macro` Task 53) тут соблюдён частично — но `×` покрывает **2** глагола (`disallow`+`allow`), не один, и работу, которая сейчас никак не делается. Это не over-engineering, это заполнение gap'а.

---

## 8. Protocol rules additions

- **Rule 16**: `×disallow` требует явный `reason:` — без него операция отменяется. В ответе: `×disallow REJECTED: reason field required (Rule 16)`
- **Rule 17**: `×allow` требует предварительного `#ok` от пользователя — нельзя восстановить «just because». Без `#ok` → `×allow REJECTED: requires #ok confirmation (Rule 17)`
- **Rule 18**: Файлы в `/home/z/my-project/disallowed/` никогда не читаются/не парсятся в normal workflow — только через `×allow` path. Если скрипт видит путь из registry.json в active context — bug, логировать в trace.log.

---

## 9. Concrete workflow — отказ от booster

### Сценарий

После 3 shader-задач с активным booster'ом, hit_rate падает ниже 0.5 — Cg-bias сильнее, чем ожидалось. Пользователь решает отказаться.

### Команда пользователя

```
×disallow booster_final.json reason: "Cg-bias сильнее, чем ожидалось; GLSL 3.3 project не получает пропорциональной пользы от ngram-статистики Cg-репозитория; glslangValidator + after-predicate достаточно для pipeline. L2 query overhead (3-15 calls × ~50 tokens) не оправдан при top3=77% accuracy на Cg, переносимой на GLSL с потерей."

×disallow scripts/query_booster.py reason: "depends on booster_final.json which is disallowed; orphaned dependency."
```

### Что я делаю

1. Parse сообщения → 2 команды `×disallow`
2. Run `scripts/disallow_artifact.py booster_final.json --reason "..."`:
   - Step 1: validate reason presence (Rule 16) ✓
   - Step 2: create `.disallow-staging/` temp dir
   - Step 3: execute 7-step cleanup (mv file + 6 file modifications)
   - Step 4: update registry.json with cleanup_log
   - Step 5: cleanup staging dir
   - Если любая ошибка → rollback + report
3. Run `scripts/disallow_artifact.py scripts/query_booster.py --reason "..."`:
   - 4-step cleanup (mv file + roadmap + meta.auto + registry)
4. Update roadmap.md Task 64: `×disallow applied to booster_final.json + query_booster.py`
5. Update meta.auto: `[disallowed: booster_final.json, scripts/query_booster.py]`

### Report в чат

```
×disallow booster_final.json — DONE
  quarantined: /home/z/my-project/disallowed/booster_final.json
  cleanup: 6 files modified, 14 mentions removed
  reversible: ×allow booster_final.json (requires #ok)

×disallow scripts/query_booster.py — DONE
  quarantined: /home/z/my-project/disallowed/query_booster.py
  cleanup: 2 files modified, 4 mentions removed
  reversible: ×allow scripts/query_booster.py (requires #ok)
```

### Roadmap состояние после

```
~~Task 63: DISALLOWED 2026-10-31 — see disallowed/registry.json~~

64 — ×disallow booster_final.json + scripts/query_booster.py (user):
     reason: Cg-bias stronger than expected; L2 query overhead not justified.
     cleanup: 8 files modified, 18 mentions removed total.
     registry: /home/z/my-project/disallowed/registry.json
     reversible: ×allow (requires #ok).
```

---

## 10. Script specification

### `scripts/disallow_artifact.py`

**Язык:** Python 3
**Размер:** ~150 строк
**Зависимости:** стандартная library (os, shutil, json, argparse, datetime, pathlib)

**CLI:**
```
python3 scripts/disallow_artifact.py <artifact> \
  --reason "..." \
  [--scope full|narrow] \
  [--dry-run] \
  [--registry /home/z/my-project/disallowed/registry.json]
```

**Поведение:**
1. **Validate**: reason present (Rule 16), artifact exists, not already in registry (idempotent)
2. **Stage**: create `/home/z/my-project/.disallow-staging/` temp dir
3. **Plan**: scan project for mentions — roadmap×3, meta.auto, btb_stats.json, docx-generators, scripts
4. **Execute** (если не `--dry-run`):
   - mv artifact → `disallowed/`
   - Modify each file with mentions (atomic per-file: backup → patch → verify → commit)
   - Update registry.json
5. **Cleanup stage**: rmtree staging dir
6. **Report**: print summary (files modified, mentions removed, reversible path)

**Dry-run mode:**
- Не делает реальных изменений
- Print planned changes: `{file}: {action} {details}`
- Exit 0 если план OK, exit 1 если найдены конфликты

**Rollback:**
- При ошибке на step N — восстановить все изменения step 1..N-1 из staging
- Log rollback в stderr
- Exit code 2

**Idempotency:**
- Если artifact уже в registry.json → warning `×already-disallowed: see registry.json entry "<name>"` + exit 0 (no-op)

---

## 11. BTB treatment

- `×disallow` и `×allow` signatures: delta=[] (base-only, как `?` и `&`)
- No prefetch, no shadow eval
- `btb_stats.json`: neutral entry, не влияет на hit/miss ratio
- BTB SELF-TUNE: если `×disallow` приходит, а в prefetch были файлы, которые теперь disallowed → это MISS (prefetch пере-broad) → auto-prune

---

## 12. Roadmap patch (preview для Task 64)

```
64 — #proto: НОВЫЙ СИГИЛ `×` + глаголы `×disallow` `×allow` (user #ok).
     Назначение: безболезненный отказ от артефактов с cleanup всех упоминаний.
     trace.log НЕ нужен (мета-операция). BTB: delta=[] (base-only).
     Rule 16: reason обязателен. Rule 17: ×allow требует #ok. Rule 18: файлы в
     disallowed/ не читаются в normal workflow.
     Filesystem: /home/z/my-project/disallowed/ + registry.json.
     Cleanup scope: 7 точек (fs, roadmap×3, meta.auto, btb_stats, docx, scripts).
     Atomic + dry-run + reversible + auditable.
     Script: scripts/disallow_artifact.py (~150 строк Python).
     Применение к booster: если L2 query не оправдает себя после 3 shader-задач
     (hit_rate < 0.5) → ×disallow booster_final.json + ×disallow scripts/query_booster.py.
     Spec: see download/reqs_killswitch.md.
```

---

## 13. Open questions / decision points

| # | Вопрос | Опции | Default |
|---|--------|-------|---------|
| Q1 | Принять `×` или расширить `#`? | `×` (new sigil) / `#disallow` (extend #) | `×` (recommended) |
| Q2 | `×allow` требовать `#ok`? | yes / no | yes (Rule 17) |
| Q3 | registry.json gc policy? | never / after N days / manual | never (audit log) |
| Q4 | Dry-run синтаксис? | `--dry-run` flag / `×disallow --dry-run X` / `×preview X` | `--dry-run` flag |
| Q5 | Cleanup mentions в chat-history (_IM context)? | impossible (chat immutable) — document as limitation | — |
| Q6 | Scope `narrow` когда нужен? | artifact без упоминаний / emergency | rarely used, kept for symmetry |
| Q7 | Multi-artifact `×disallow A B C`? | batch mode / one-per-call | one-per-call (atomicity проще) |

---

## 14. Чек-лист перед реализацией

- [ ] Пользователь подтверждает `#ok ×` (или альтернативу)
- [ ] Обновить roadmap.md — Task 64
- [ ] Обновить meta.auto — autotoken `[disallowed: dynamic]`
- [ ] Написать `scripts/disallow_artifact.py`
- [ ] Обновить `sigil_btb_documentation.docx` v1.5 — секция про `×` sigil + rules 16-18
- [ ] Обновить `scripts/gen_sigil_btb_doc.py` — generator знает про `×`
- [ ] Тест dry-run: `×disallow test_dummy.json --dry-run`
- [ ] Тест atomic rollback: simulate failure на step 4, verify rollback

---

## 15. Связанные документы

- `roadmap.md` — рабочая память проекта, Task 63 (booster) и Task 64 (этот kill-switch)
- `meta.auto` — автоподстановки, получит `[disallowed: ...]` token
- `btb_stats.json` v2 — BTB state, neutral для `×`
- `sigil_btb_documentation.docx` v1.4 → v1.5 — добавление секции `×` sigil
- `download/reqs_killswitch.md` — **этот документ**

---

## 16. Статус

**PROPOSED** — ждёт решения пользователя.

Возможные ответы:
- `#ok ×` — принять сигил `×` + глаголы; приступить к реализации (Task 64 + script)
- `#ok × + #disallow` — принять и `×` и синоним `#disallow` для совместимости
- `#ok #disallow` — передумать, расширить `#` вместо нового сигила
- `&plan refinements` — обсудить open questions Q1-Q7
- `?` любой вопрос по спецификации
