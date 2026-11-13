# Documentation generation — diagnosis & optimization

**Документ:** doc_gen.md
**Дата:** 2026-10-31
**Контекст:** ответ на `?Почему документация генерируется так долго, какие шаги предпринять, чтобы она создавалась быстрее ?`
**Subject:** анализ времени генерации `sigil_btb_documentation.docx` v1.5 + concrete steps для ускорения

---

## 1. Честный diagnosis — почему v1.5 генерация заняла долго

Разбор что было медленно в предыдущей генерации `sigil_btb_documentation.docx` v1.5.

### Real timeline (что заняло время)

| Шаг | Время | Зачем | Necessary? |
|-----|-------|-------|-----------|
| 1. LS + Read docx skill files | ~15s | SKILL.md + routes/create.md + design-system.md (1797 строк) | ❌ избыточно — я уже генерировал aesthetics.docx ранее в этой же сессии, skill уже в контексте |
| 2. MultiEdit gen_sigil_btb_doc.py (250+ строк нового контента) | ~10s | Добавить §13.1, §14, §15 | ✅ но слишком большой chunk → syntax errors |
| 3. Run generator → syntax error #1 (лишний `]`) | ~5s | Python parse fails | ❌ можно было поймать заранее |
| 4. Edit fix → rerun → syntax error #2 (`}` вместо `]`) | ~10s | Опять bracket mismatch | ❌ можно было поймать заранее |
| 5. Edit fix → rerun → SUCCESS | ~5s | docx saved | ✅ |
| 6. postcheck.py | ~5s | verify | ✅ |
| 7. add_toc_placeholders.py | ~5s | fix TOC update fields | ✅ |
| 8. soffice convert to PDF | ~10s | для preview | ⚠️ опционально |
| 9. python-docx verify (headings/tables/images count) | ~5s | structure check | ✅ |
| 10. md5sum | ~1s | checksum | ✅ |

**Итого: ~70s realistic, но с failed runs и reading skill files — реально 5-8 минут wall time.**

---

## 2. Главные причины медленности

### 2.1. Избыточное чтение skill файлов (~15s wasted)

Уже сгенерировал aesthetics.docx в этой же сессии — docx skill уже загружен. Но я ещё раз читал routes/create.md, design-system.md. Зачем-то.

### 2.2. Syntax errors из-за больших MultiEdit (~30s wasted)

MultiEdit с 250-строк new_str содержит много nested lists типа `[["...", "...", "..."], ["...", "...", "..."]]`. Легко ошибиться в bracket count. Я ошибся дважды:
- Лишний `]` в словаре (Edit fix)
- `}` вместо `]` в v1.5 extension table (Edit fix)

### 2.3. Избыточная verification (~15s wasted)

Запускал: postcheck + soffice convert + pdftoppm (render) + pdftotext + pdfinfo + pdfimages + python-docx + md5sum = 8 шагов. Для routine update достаточно postcheck + md5sum = 2 шага.

### 2.4. Failed Read image (~5s wasted)

Пробовал `Read page-01.jpg` для visual check — моя модель не может смотреть images. Бесполезный tool call.

---

## 3. Concrete steps для ускорения

### Step 1 — Pre-install dependencies once (экономия ~30s на каждый будущий docx)

Сейчас `image-size` установлен в `/home/z/my-project/node_modules` (после aesthetics.docx). Но при sandbox restart это может потеряться. Надо:

```bash
# Создать persistent package.json с всеми нужными deps
cd /home/z/my-project && cat > package.json << 'EOF'
{"name":"docx-gen","version":"1.0.0","dependencies":{"docx":"latest","image-size":"latest"}}
EOF
npm install  # выполнится один раз за session
```

Это уже сделано — `package.json` существует. Но при новом sandbox’е надо запомнить запустить `npm install` сразу.

### Step 2 — Skip skill reload в той же сессии (экономия ~15s)

Если я уже генерировал docx в этой сессии — skill instructions в моём контексте. Не нужно:
- `Skill(command="docx")` повторно
- `Read routes/create.md`
- `Read references/design-system.md`

Просто сразу писать generator script.

### Step 3 — Syntax-check Python ПЕРЕД run (экономия ~30s на каждый syntax error)

```bash
python3 -m py_compile scripts/gen_sigil_btb_doc.py && \
echo "SYNTAX OK" && \
python3 scripts/gen_sigil_btb_doc.py
```

`py_compile` ловит bracket/paren errors за 100ms, вместо 5-10s на полный generator run.

### Step 4 — Меньшие Edits, не большие MultiEdits (экономия ~30s на каждый avoided error)

Вместо одного 250-строк MultiEdit с nested lists — делать 5-6 маленьких Edit по 40-50 строк. Каждый проще проверить, syntax error локализуется быстрее.

### Step 5 — Минимальная verification для routine updates (экономия ~15s)

Для routine update (тот же generator, тот же формат):
- ✅ `python3 scripts/gen_sigil_btb_doc.py` — generation
- ✅ `python3 skills/docx/scripts/postcheck.py output.docx` — structure check
- ✅ `md5sum output.docx` — checksum
- ❌ skip soffice PDF convert (только если пользователь попросит preview)
- ❌ skip pdftoppm/pdftotext/pdfinfo/pdfimages (verbose verification только при debugging)
- ❌ skip python-docx structure verify (postcheck уже покрывает)

### Step 6 — Не Read image files (~5s saved)

Моя модель не может view JPG/PNG. Пропустить `Read page-XX.jpg` полностью. Если нужен visual check — использовать VLM skill (отдельный tool call).

### Step 7 — Separate changelog file для version bumps (long-term refactor)

Сейчас каждая v1.x обновление требует редактировать 1100-line `gen_sigil_btb_doc.py`. Это fragile. Лучше:

```
scripts/
  gen_sigil_btb_doc.py        # main generator (stable, rarely edited)
  changelog_v1.5.md           # markdown с changelog content
  changelog_v1.6.md           # будущие версии
```

Generator читает `changelog_v1.X.md` и inserts в §13/§15. Version bump = edit маленький markdown file, не Python.

Это рефакторинг — но окупается после 2-3 version updates.

---

## 4. Ожидаемое время после оптимизаций

| Scenario | Сейчас | После steps 1-6 | После step 7 |
|----------|--------|-----------------|--------------|
| Новый docx с нуля (aesthetics.docx style) | ~5 мин | ~2-3 мин | ~2-3 мин |
| Version bump существующего (sigil_btb v1.5 → v1.6) | ~5-8 мин | ~1-2 мин | **~30s** |
| Routine edit (fix typo, update table row) | ~2 мин | ~30s | ~30s |

---

## 5. Что я сделаю прямо сейчас (немедленные улучшения)

1. ✅ `package.json` уже persistent — image-size и docx не переустановятся
2. Memory: «для docx generation в той же сессии — не перезагружать skill»
3. Memory: «Python syntax-check перед run: `py_compile` + run»
4. Memory: «минимальная verification: postcheck + md5sum только»

---

## 6. Что требует вашего решения

**Step 7 (refactoring generator)** — это larger change. Подход:
- `&plan detailed` — обсудить architecture разделения generator + changelog files
- Или оставить как есть — текущий workflow работает, просто медленнее

Если для вас critical скорость docx generation — step 7 даёт наибольший выигрыш (30s вместо 5 мин для version bumps). Если генерация редкая (раз в несколько сессий) — текущее время приемлемо, refactoring не окупается.

---

## 7. Статус

**Этот документ:** `/home/z/my-project/download/doc_gen.md`
**Размер:** ~7 КБ
**Доступен для скачивания:** да (в Z.ai web interface — file panel справа или attachments dropdown)

Если файл не виден в интерфейсе — обновите страницу (F5) или попросите явно: «пришли doc_gen.md как attachment».
