# 19. v1.6 changelog --- что нового

Краткий список изменений v1.5 → v1.6:

**1. Auxiliary documents created.** aesthetics.md/docx (aesthetic principles + 3-image comparative analysis), doc_gen.md (performance optimization analysis), sugg_pandoc_docx.md (Pandoc migration proposal, 14 questions), reqs_killswitch.md (REJECTED kill-switch spec).

**2. §16 Auxiliary documents (NEW section).** 4 subsections: aesthetics.md (Table 16), reqs_killswitch.md REJECTED (Table 17), doc_gen.md (Table 18), sugg_pandoc_docx.md (Table 19).

**3. §17 Performance optimization (NEW section).** Applied optimization steps из doc_gen.md. v1.5 \~5-8 min → v1.6 \~50 sec = 6-10× speedup. Table 20 (skipped steps), Table 21 (kept steps), §17.3 net comparison.

**4. §18 Pandoc migration (NEW section).** Status & proposal. Table 22 (current state), Table 23 (key decisions), Table 24 (expected speedup). Pending user decision: #ok all-defaults / per-question / &plan.

**5. Cover metadata updated.** v1.5 → v1.6, дата 31 октября → 1 ноября 2026.

**6. No new formal Tasks.** Auxiliary documents созданы через &plan discussion + «сохрани в файл» requests, не через !feat/!fix. Roadmap Tasks 1-66 unchanged.

**7. PDF generation skipped.** Per user request «pdf не делай». Только docx + postcheck.

**8. Optimization steps applied.** py_compile syntax check (caught 0 errors в этом edit), minimal verification (postcheck + add_toc_placeholders + md5sum только), no PDF render, no image Read.

Протокол sigil+BTB v2.1 остаётся неизменным. v1.6 documentation = v1.5 + auxiliary documents summary + performance analysis + Pandoc migration proposal. Lean approach сохранён: 5 сигилов, 8+3 глаголов, без макросов, без kill-switch.
