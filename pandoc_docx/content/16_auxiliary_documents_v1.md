# 16. Auxiliary documents (v1.6 --- auxiliary deliverables)

После v1.5 (Task 66 #milestone v49) создано 4 auxiliary документа в ходе &plan обсуждений и анализа. Они не являются формальными Tasks (нет trace.log, нет !feat/!fix команд), но влияют на future protocol evolution. Все документы доступны в /home/z/my-project/download/.

## 16.1. aesthetics.md / aesthetics.docx

Aesthetic principles reference document. Создан в ходе обсуждения «как сделать ассистента более творческим в визуализации». v0.1 → v0.4 (316 строк markdown, очищен от project-specific упоминаний).

  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Aspect**                          **Value**
  ----------------------------------- ------------------------------------------------------------------------------------------------------------------------------------------------
  Source markdown                     download/aesthetics.md (316 строк, 16 КБ)

  DOCX rendering                      download/aesthetics.docx (508 КБ, 10 страниц A4)

  PDF preview                         download/aesthetics.pdf (632 КБ)

  Reference images                    3 шт. (warehouse surreal / mage combat / zombie horse graveyard) --- embedded в §9

  Comparative analysis                §9: 3-way score table (9 principles × 3 images), principled verdict (Image 2 = 5/9, Image 3 = 3/9, Image 1 = 1/9)

  Three archetypes                    Static surreal / Dynamic dramatic / Atmospheric horror

  Sample palette                      DRAMATIC_DARK (deep_purple_core + cyan_mid + magenta_rim + star_white_pure + void_black)

  Self-critique checklist             §8: mandatory YAML block для !\*shader\* delivery (palette, ratio, harmony, focal, motion, density, contrast, reference_target, self_critique)
  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

*Таблица 16. aesthetics.md/docx --- reference document summary.*

Status: experimental v0.4. Не integrated в formal protocol (mandatory aesthetic_notes: block пока НЕ required для !\*shader\*). Pending user decision: integrate как protocol rule или оставить как reference doc.

## 16.2. reqs_killswitch.md --- REJECTED

Kill-switch specification. Предлагал сигил × с глаголами ×disallow/×allow, карантинную папку disallowed/, registry.json, скрипт disallow_artifact.py, Rules 16-18 для safe rejection артефактов протокола.

  --------------------------------------------------------------------------------------------------------------------------------------------
  **Aspect**                          **Value**
  ----------------------------------- --------------------------------------------------------------------------------------------------------
  Status                              REJECTED 2026-10-31 (пользователь явно отказался)

  File                                download/reqs_killswitch.md (367 строк, 20 КБ) --- сохранён как historical record

  Что НЕ реализовано                  сигил ×, глаголы ×disallow/×allow, Rules 16-18, disallowed/ папка, registry.json, disallow_artifact.py

  Принцип отказа                      Не плодить инфраструктуру «про запас» (тот же принцип что при отказе !macro в Task 53)

  Если понадобится в будущем          ad-hoc cleanup скриптом под конкретный случай, без общей инфраструктуры
  --------------------------------------------------------------------------------------------------------------------------------------------

*Таблица 17. reqs_killswitch.md --- REJECTED spec summary.*

## 16.3. doc_gen.md --- performance optimization analysis

Analysis «почему documentation generation занимает долго + concrete steps для ускорения». Создан после v1.5 generation, занявшей 5-8 минут wall time из-за syntax errors и избыточной verification.

  --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Aspect**                          **Value**
  ----------------------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------
  File                                download/doc_gen.md (160 строк, 9 КБ)

  Real timeline analysis              10 шагов, \~70s realistic / 5-8 мин wall time (с failed runs)

  Main bottlenecks                    \(1\) skill reload \~15s, (2) syntax errors в MultiEdit \~30s, (3) избыточная verification \~15s, (4) failed image Read \~5s

  7 concrete optimization steps       pre-install deps / skip skill reload / py_compile syntax-check / меньшие Edits / минимальная verification / skip image Read / separate changelog files

  Expected speedup                    Version bump 1-2 min → 10-30s (4-12× faster после step 7 refactor)
  --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

*Таблица 18. doc_gen.md --- optimization analysis summary.*

## 16.4. sugg_pandoc_docx.md --- Pandoc migration proposal

14-question risk analysis для migration с gen_sigil_btb_doc.py (1099-line Python + python-docx) на content/\*.md + auto_build.py (Pandoc CLI). Benchmark: pandoc 0.2s vs my generator 5s = 25× faster raw conversion.

  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Aspect**                          **Value**
  ----------------------------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
  File                                download/sugg_pandoc_docx.md (372 строки, 22 КБ)

  Pandoc availability                 ✅ installed v3.1.11.1 (/usr/bin/pandoc, 198 MB)

  Benchmark                           aesthetics.md (316 строк) → docx: pandoc 0.215s vs my generator \~5s = 23× faster

  Image embedding                     ✅ verified --- markdown \![\](path) syntax embeds PNGs correctly

  Page breaks                         \\newpage НЕ работает для docx (bug в user auto_build.py). Fix: raw openxml block \`\<w:br w:type=\"page\"/\>\`

  Custom styling                      via \--reference-doc=template.docx (one-time setup)

  14 decision points                  extraction / markdown flavor / tables / diagrams / cover / TOC / numbering / styling / page breaks / image sizing / validation / rollback / execution / persistence

  Expected after migration            Version bump v1.5→v1.6: 5-8 min → 10-30s (4-12× faster)

  Migration cost                      \~1.5 часа (pilot + phased approach)

  Status                              Pending user decision: #ok all-defaults / per-question selection / &plan detailed
  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

*Таблица 19. sugg_pandoc_docx.md --- Pandoc migration proposal summary.*
