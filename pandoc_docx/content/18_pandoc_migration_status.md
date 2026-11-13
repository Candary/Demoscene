# 18. Pandoc migration --- status & proposal

В ходе v1.6 работы исследована возможность migration на Pandoc-based generation. Pandoc уже установлен в sandbox (v3.1.11.1, /usr/bin/pandoc). Benchmark показал 25× faster raw conversion (0.2s vs 5s). Full risk analysis в sugg_pandoc_docx.md.

## 18.1. Current state (v1.6)

  ---------------------------------------------------------------------------------------------------------------
  **Item**                               **Status**
  -------------------------------------- ------------------------------------------------------------------------
  Pandoc binary                          ✅ installed v3.1.11.1, 198 MB

  Benchmark (markdown → docx)            ✅ 0.215s for 316-line aesthetics.md

  Image embedding test                   ✅ verified --- \![\](path) syntax works

  Page break test                        ✅ raw openxml \`\<w:br w:type=\"page\"/\>\` works; \\newpage does NOT

  Custom template test                   ✅ \--reference-doc=template.docx works

  Migration proposal (14 questions)      ✅ saved in sugg_pandoc_docx.md

  Migration execution                    ⏸ pending user decision

  Old generator (gen_sigil_btb_doc.py)   ✅ still active, used for this v1.6 generation
  ---------------------------------------------------------------------------------------------------------------

*Таблица 22. Pandoc migration --- current state.*

## 18.2. Decision points (pending user)

14 decision points покрыто в sugg_pandoc_docx.md. Ключевые:

  -----------------------------------------------------------------------------------------------------------------
  **Decision**             **Options**                                                **My recommendation**
  ------------------------ ---------------------------------------------------------- -----------------------------
  Q1: Content extraction   A manual / B regex / C pandoc roundtrip                    C (pandoc roundtrip, 5 min)

  Q5: Cover page           A template.docx / B YAML / C hybrid / D skip               A (template.docx)

  Q8: Custom styling       A template UI / B python-docx / C reuse v1.5 / D default   A then B

  Q12: Rollback plan       A parallel 2 versions / B delete / C git / D no rollback   A (parallel)

  Q13: Execution order     A big bang / B phased / C pilot + B phased                 C then B
  -----------------------------------------------------------------------------------------------------------------

*Таблица 23. Pandoc migration --- key decision points.*

## 18.3. Expected outcome after migration

После migration (если approved):

  --------------------------------------------------------------------------------------------------------------
  **Scenario**                       **Current (v1.6 Python)**    **After Pandoc migration**   **Speedup**
  ---------------------------------- ---------------------------- ---------------------------- -----------------
  Version bump (v1.6 → v1.7)         \~50 sec (this generation)   10-30 sec                    2-5×

  Major content addition (new §19)   \~5 min                      \~1-2 min                    3-5×

  New docx from scratch              \~5 min                      \~2-3 min                    2×

  Fix typo                           \~30 sec                     \~10 sec                     3×
  --------------------------------------------------------------------------------------------------------------

*Таблица 24. Expected speedup after Pandoc migration.*

Migration cost: \~1.5 часа one-time refactor. Break-even: after 2-3 version bumps (expected within 1-2 weeks of active development).
