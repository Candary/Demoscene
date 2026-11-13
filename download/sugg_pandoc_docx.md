# Migration risk analysis — Pandoc + content/*.md approach

**Документ:** sugg_pandoc_docx.md
**Дата:** 2026-11-01
**Контекст:** ответ на `?Продумай все шаги, как избежать ошибок при и после миграции на pandoc в формате диалога, предлагай выбрать варианты и внизу под каждым вариантом - своё оценочное суждение о нём`
**Subject:** 14 decision points для migration с gen_sigil_btb_doc.py (1099-line Python + python-docx) → content/*.md + auto_build.py (Pandoc), с вариантами и оценочными суждениями для каждого

---

## Q1: Как извлекать контент из 1099-строчного `gen_sigil_btb_doc.py` в markdown?

**Вариант A: Manual copy-paste**

Моя оценка: ❌ медленно (40+ минут), error-prone при копировании русских текстов с unicode escapes (`\u201c` и т.д.). Подходит только если контент < 200 строк. У нас 1099 строк Python с 16 секциями — manual copy приведёт к потере форматирования и багам в unicode.

**Вариант B: Script-extraction (strip `add_body("...")` → `.md`)**

Моя оценка: ⚠️ medium risk. Написать regex-экстрактор за 5 минут, который парсит `add_body("text")`, `add_table(headers, rows)`, `add_code(text)`, `h1("text")`. Получит ~80% контента корректно. Останутся edge cases: multi-line strings с `\n` внутри, `add_body_runs()` со списком кортежей, escape-последовательности. После extraction — manual cleanup ~10 минут. **Лучший баланс скорости и точности.**

**Вариант C: Hybrid — run gen_sigil_btb_doc.py, capture python-docx output, convert to markdown via `pandoc -f docx -t markdown`**

Моя оценка: ✅ fastest и most reliable. Запустить текущий generator → получить v1.5 docx → `pandoc sigil_btb_documentation.docx -f docx -t markdown -o output.md` → получить markdown с правильным извлечением всех таблиц, code blocks, heading levels. Pandoc сам сделает extraction корректно. Потом разбить на content/*.md файлы по `## ` заголовкам. **Recommended.**

**Мой recommendation:** C (roundtrip через pandoc). Самый надёжный, 5 минут работы.

---

## Q2: Какой markdown flavor использовать в content/*.md?

**Вариант A: Standard CommonMark**

Моя оценка: ⚠️ loses pandoc-specific features (raw openxml blocks для page breaks, attribute syntax для image sizing). Стандартный, но придётся обходить ограничения.

**Вариант B: Pandoc markdown (`-f markdown`)**

Моя оценка: ✅ full feature set: raw openxml blocks, image attributes `{width=380px}`, fenced divs, YAML metadata. Pandoc native — все возможности доступны. **Recommended.**

**Вариант C: PHP Markdown Extra / MultiMarkdown**

Моя оценка: ❌ unnecessary complexity. Pandoc markdown уже superset этих flavors. Не даёт дополнительных преимуществ.

**Мой recommendation:** B (pandoc markdown). Native формат, все features доступны.

---

## Q3: Как конвертировать rich tables (shading, bold headers, column widths)?

**Вариант A: Plain markdown pipe tables**
```markdown
| Header 1 | Header 2 |
|----------|----------|
| cell     | cell     |
```

Моя оценка: ⚠️ loses shading и precise column widths. Header bold auto (pandoc), но alternate row shading — нет. Column widths auto-fit content. Подходит для простых таблиц. У нас 18 таблиц — большинство простые, но несколько с color-coded rows (Table 11 v2 reforms).

**Вариант B: Pandoc grid tables**
```
+----------+----------+
| Header 1 | Header 2 |
+==========+==========+
| cell     | cell     |
+----------+----------+
```

Моя оценка: ⚠️ supports multi-line cells, но всё ещё no shading. Visual alignment в source file, но output — plain. Не решает проблему shading.

**Вариант C: HTML tables (`<table>`, `<tr>`, `<td style="background-color:...">`)**

Моя оценка: ✅ full control: shading, bold, alignment, column widths. Pandoc пропускает HTML напрямую в docx. Verbose, но работает. Для 2-3 critical tables (Table 11 v2 reforms, Table 14 triggers) — стоит. Для остальных — markdown pipe tables.

**Вариант D: All tables in markdown pipe + rely on template.docx table style**

Моя оценка: ✅ simplest. Template.docx определяет default table style (header bold, alternating rows, borders). Все markdown pipe tables получают этот стиль автоматически. Lose per-cell shading, но uniform look. **Recommended для большинства таблиц.**

**Мой recommendation:** D для большинства + C для 2-3 critical tables с color coding. Hybrid approach.

---

## Q4: Как обрабатывать 4 matplotlib диаграммы?

**Вариант A: Pre-generate PNGs once, store in `content/images/`, reference via `![](images/diag1.png)`**

Моя оценка: ✅ best for stable diagrams (не меняются между версиями). Один раз запускаешь `gen_diagrams.py` → 4 PNGs готовы → markdown ссылается. auto_build.py не вызывает matplotlib вообще. **Recommended если диаграммы не меняются.**

**Вариант B: auto_build.py вызывает `gen_diagrams.py` перед pandoc**

Моя оценка: ⚠️ slower build (matplotlib import + render = 3-5s), но always fresh diagrams. Если диаграммы могут меняться (например, BTB confidence chart updates per Task) — нужно. Если stable — overhead unnecessary.

**Вариант C: Embed diagrams as base64 in markdown**

Моя оценка: ❌ bad. Base64 inflates markdown file (each PNG ~50KB → 70KB base64). Source files unreadable. Pandoc handles binary PNGs via path reference — no reason to embed.

**Мой recommendation:** A. Диаграммы sigil_picker/btb_flow/rule13_gate — stable (не меняются с v1.0). BTB confidence chart — обновляется per Task, но это ~once per 5 version bumps. Pre-generate для большинства, rerun gen_diagrams.py вручную когда BTB chart updated.

---

## Q5: Cover page — как сохранить custom layout?

**Вариант A: Define cover in template.docx**

Моя оценка: ✅ best. Открываешь template.docx в Word/LibreOffice → настраиваешь first page: title, subtitle, accent line, metadata block, palette. Pandoc при генерации сохраняет template's first page как cover. Content начинается со page 2. **Recommended.**

**Вариант B: Markdown YAML frontmatter only**
```yaml
---
title: "Документация sigil+BTB"
subtitle: "Протокол общения..."
version: "v1.5"
date: "2026-10-31"
---
```

Моя оценка: ⚠️ basic. Pandoc вставляет title + date в standard places, но custom accent lines / palette / borders — нет. Loses ~80% cover styling. Быстро, но ugly.

**Вариант C: Hybrid — pandoc генерирует body, python-docx добавляет cover отдельно после**

Моя оценка: ❌ complex pipeline. `pandoc content.md → body.docx` → `python-docx: open body.docx, insert cover section at start, save final.docx`. Multiple tools, multiple failure points. Не стоит.

**Вариант D: Skip cover entirely — start with §1**

Моя оценка: ⚠️ simplest, но теряется formal document feel. Для internal technical reference — OK. Для documentation deliverable — нет.

**Мой recommendation:** A. Template.docx с настроенным cover — one-time setup 10 минут, потом все версии получают consistent cover автоматически.

---

## Q6: TOC — как генерировать и обновлять?

**Вариант A: `pandoc --toc --toc-depth=3`**

Моя оценка: ✅ auto-generates TOC с правильными page numbers и hyperlinks. Один flag. TOC обновляется при открытии в Word (если `--toc` ставит updateFields=true). **Recommended.**

**Вариант B: Manual TOC placeholder + add_toc_placeholders.py (как сейчас)**

Моя оценка: ❌ unnecessary complexity. Pandoc `--toc` делает это автоматически. Зачем дублировать?

**Вариант C: No TOC**

Моя оценка: ❌ для 32-page document — обязательно нужен TOC для navigation.

**Мой recommendation:** A. Pandoc `--toc` flag, ничего больше.

---

## Q7: Section numbering — auto или manual?

**Вариант A: `pandoc --number-sections`**

Моя оценка: ✅ auto-numbers all headings: `1`, `1.1`, `1.2`, `2`, etc. Clean, consistent, no manual maintenance. **Но:** current headings already have manual numbers (`§1`, `§2`, `3.1. 60-30-10 rule`). Двойная нумерация (`1. §1 Контекст`) — ugly.

**Вариант B: Manual numbering в markdown headings (`## 3. Сигилы`)**

Моя оценка: ✅ preserves current style. Pandoc НЕ добавляет auto numbers (без `--number-sections`). Heading text уже содержит "3. Сигилы". TOC покажет "3. Сигилы" с page number. **Recommended — matches current style.**

**Вариант C: Hybrid — auto для subsections, manual для main sections**

Моя оценка: ❌ inconsistent. Нельзя делать `--number-sections` для `###` но не для `##`. Pandoc применяет ко всем уровням.

**Мой recommendation:** B. Убрать `--number-sections` из auto_build.py, использовать manual numbering в markdown. Соответствует текущему стилю.

---

## Q8: Custom palette и fonts — как перенести?

**Вариант A: Configure in template.docx (Word/LibreOffice UI)**

Моя оценка: ✅ visual, intuitive. Открываешь template.docx → Styles pane → modify Heading 1/2/3, Body, Source Code styles → set colors, fonts, sizes. One-time setup 15 минут. Все markdown конверсии наследуют стили. **Recommended.**

**Вариант B: Generate template.docx programmatically with python-docx**

Моя оценка: ⚠️ requires ~100 lines Python code to define styles. Reproducible, version-controllable, но initial setup longer. Если template нужно пересоздавать часто (sandbox restarts) — лучше. Если stable — A проще.

**Вариант C: Use my current sigil_btb_documentation.docx v1.5 as template**

Моя оценка: ⚠️ quick start, но inherits all current quirks. Pandoc `--reference-doc` берёт styles из template, но не layout. Cover page template.docx будет v1.5 cover. Might work, might have unexpected style inheritance. Risky.

**Вариант D: Default pandoc styling (no custom palette)**

Моя оценка: ❌ lose DRAMATIC_DARK palette, accent colors, custom heading colors. Output looks generic. Не соответствует quality bar.

**Мой recommendation:** A для initial setup (15 мин в LibreOffice), потом B для reproducibility (если template теряется при sandbox restart). Hybrid: A сначала, B как backup.

---

## Q9: Page breaks между sections — как вставлять?

**Вариант A: Pandoc raw openxml blocks**
```markdown
\`\`\`{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
\`\`\`
```

Моя оценка: ✅ works correctly (verified — вставляет настоящий Word page break). Verbose, но можно сделать macro/snippet. **Recommended.**

**Вариант B: `\newpage` (LaTeX syntax)**

Моя оценка: ❌ не работает для docx output (verified — pandoc игнорирует). Это bug в текущем auto_build.py.

**Вариант C: Auto page break before each H1 (via template.docx style)**

Моя оценка: ✅ elegant. В template.docx: Heading 1 style → Paragraph properties → "Page break before" = true. Тогда каждый `## Section` автоматически starts на new page. Markdown остаётся clean, no raw openxml. **Best long-term.**

**Вариант D: No page breaks (continuous flow)**

Моя оценка: ❌ 32-page document без page breaks между sections — unreadable.

**Мой recommendation:** C (template.docx Heading 1 style с "page break before"). Самый clean markdown + auto page breaks. Запасной вариант: A (raw openxml) для специальных случаев (например, page break внутри section).

---

## Q10: Image sizing в markdown — как контролировать?

**Вариант A: Pandoc attribute syntax `![caption](path){width=380px}`**

Моя оценка: ✅ explicit, per-image control. Pandoc понимает `{width=380px height=380px}`. Markdown остаётся readable. **Recommended.**

**Вариант B: Pre-resize images to display size**

Моя оценка: ⚠️ lose original resolution. Если потом захочешь larger image — нужно re-resize. OK для final delivery, bad для iterative editing.

**Вариант C: Default pandoc sizing (image native DPI)**

Моя оценка: ⚠️ unpredictable. Pandoc может вставить 768×768 image на всю страницу. Bad layout.

**Вариант D: Template.docx image style**

Моя оценка: ⚠️ pandoc не применяет image styles из template.docx последовательно. Unreliable.

**Мой recommendation:** A. Pandoc attribute syntax, explicit `{width=380px height=380px}` для square reference images, `{width=600px}` для diagrams.

---

## Q11: Validation strategy — как проверять output?

**Вариант A: Trust pandoc output (no validation)**

Моя оценка: ❌ risky. Pandoc может пропустить image (wrong path), malformed table, broken heading level. Need at least basic check.

**Вариант B: Light validation (file size > 10KB, как в auto_build.py)**

Моя оценка: ⚠️ catches gross failures (empty output), но misses content issues (missing image, wrong heading level). Better than nothing.

**Вариант C: Structural validation via python-docx (heading count, table count, image count)**

Моя оценка: ✅ catches structural regressions. Сравниваешь с expected: 16 H1, 33 H2, 18 tables, 4 images. Если mismatch — alert. ~10 lines Python. **Recommended.**

**Вариант D: Full postcheck.py + diff с previous version**

Моя оценка: ⚠️ thorough, но slow (postcheck ~5s). Для major version bumps — стоит. Для minor edits — overkill.

**Мой recommendation:** C для routine builds (5s, catches regressions), D для major version bumps. Hybrid.

---

## Q12: Rollback plan — что если pandoc output хуже?

**Вариант A: Keep gen_sigil_btb_doc.py as backup, run in parallel для first 2 versions**

Моя оценка: ✅ safest. После migration — generate обоими (pandoc + old Python), сравнить outputs, выбрать лучше. После 2 successful pandoc versions — delete old generator. **Recommended.**

**Вариант B: Delete old generator immediately после first successful pandoc build**

Моя оценка: ❌ risky. Если через неделю обнаружится issue (например, template.docx style inheritance bug) — нечем откатиться.

**Вариант C: Version-control both approaches (git branches)**

Моя оценка: ⚠️ overhead. У нас нет git в project (files в /home/z/my-project/). Можно zip backup старого generator, но git formalism — unnecessary.

**Вариант D: Accept risk, no rollback**

Моя оценка: ❌ для documentation deliverable — недопустимо. Всегда нужен rollback path.

**Мой recommendation:** A. Parallel generation для 2 versions (v1.5 уже есть как reference, v1.6 пробуем pandoc). Если v1.6 pandoc output ≥ v1.6 old-generator output по quality — delete old generator после v1.7.

---

## Q13: Migration execution plan — в каком порядке делать?

**Вариант A: Big bang — всё за один заход**

Моя оценка: ❌ high risk. 16 .md files + template.docx + fixed auto_build.py + 4 diagram PNGs — слишком много переменных одновременно. Если что-то сломается — сложно локализовать.

**Вариант B: Phased — phase 1: simple sections, phase 2: complex tables, phase 3: diagrams**

Моя оценка: ✅ controllable. Phase 1: migrate §1-§2 (text only) → verify pandoc output matches. Phase 2: migrate §3, §11, §14 (tables) → verify table rendering. Phase 3: migrate diagrams + cover. Каждый phase — тестируемый checkpoint. **Recommended.**

**Вариант C: Test on copy first (aesthetics.md → pandoc → compare с existing aesthetics.docx)**

Моя оценка: ✅ excellent pilot. У нас уже есть aesthetics.md + aesthetics.docx (мной сгенерированный). Запускаем `pandoc aesthetics.md → aesthetics_pandoc.docx` → сравниваем по structure + content. Если pandoc version acceptable — proceed with sigil_btb migration. **Best first step.**

**Мой recommendation:** C сначала (pilot на aesthetics), потом B (phased migration для sigil_btb).

---

## Q14: Sandbox persistence — что если sandbox перезапустится?

**Вариант A: Rely on /home/z/my-project/ persistence (per system prompt)**

Моя оценка: ⚠️ works для active session, но sandbox может быть recycled между messages. Per system prompt: "everything under `/home/z/my-project/` is kept". Но if sandbox recycled — content/*.md могут потеряться.

**Вариант B: Backup content/*.md + template.docx в zip после каждого change**

Моя оценка: ✅ safe. `zip -r content_backup.zip content/ template.docx auto_build.py` → сохраняем в /home/z/my-project/download/. При sandbox restart — unzip restores. ~5 seconds per backup. **Recommended.**

**Вариант C: Git version control (init repo в /home/z/my-project/)**

Моя оценка: ⚠️ proper, но overhead. У нас нет git workflow в project. Можно сделать `git init && git add . && git commit -m "v1.6"`, но это меняет project structure.

**Вариант D: Store content/ в download/demo_intro/ (persistent folder)**

Моя оценка: ✅ content/ уже persistent если в /home/z/my-project/download/. Symlink или прямой path. Simplest.

**Мой recommendation:** B + D. Content/ живёт в /home/z/my-project/download/sigil_btb_content/. После каждого edit — `zip -r sigil_btb_content_backup_$(date).zip sigil_btb_content/` в download/ root.

---

## Итоговая recommendation matrix

| Question | Recommended | Time saved | Risk reduced |
|----------|-------------|------------|--------------|
| Q1 extraction | C: pandoc roundtrip | 30 min → 5 min | high |
| Q2 markdown flavor | B: pandoc markdown | — | medium |
| Q3 tables | D + C hybrid | — | medium |
| Q4 diagrams | A: pre-generate PNGs | 5s per build | low |
| Q5 cover | A: template.docx | — | high |
| Q6 TOC | A: pandoc --toc | 5s per build | high |
| Q7 numbering | B: manual | — | low |
| Q8 styling | A then B: template.docx | — | high |
| Q9 page breaks | C: template style | — | medium |
| Q10 image sizing | A: attribute syntax | — | low |
| Q11 validation | C + D hybrid | — | high |
| Q12 rollback | A: parallel 2 versions | — | high |
| Q13 execution | C then B: pilot + phased | — | high |
| Q14 persistence | B + D: zip backup | — | medium |

**Итого: ~1.5 часа работы для full migration с pilot + phased approach.**

После migration: **version bump v1.5 → v1.6 занимает 10-30 секунд** (vs 1-2 min сейчас).

---

## Что нужно от вас

Выберите для **каждого** из 14 questions:
- Номер варианта (A/B/C/D)
- Или `?` если хотите обсудить конкретный вопрос подробнее
- Или `default` — принять мой recommendation

Например:
```
Q1: C
Q2: B
Q3: default
Q4: A
...
```

Или одной строкой: `#ok all-defaults` — принять все мои recommendations и начать migration.

Или `&plan detailed Q5 Q8 Q12` — обсудить только эти 3 вопроса (cover, styling, rollback — наиболее critical).

---

## Статус

**Этот документ:** `/home/z/my-project/download/sugg_pandoc_docx.md`
**Размер:** ~14 КБ
**Доступен для скачивания:** да (в Z.ai web interface — file panel справа или attachments dropdown)

Если файл не виден в интерфейсе — обновите страницу (F5) или попросите явно: «пришли sugg_pandoc_docx.md как attachment».
