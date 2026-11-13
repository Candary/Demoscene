# 20. Pandoc pipeline — production accepted (v1.7)

**v1.7** — первая версия documentation, сгенерированная через Pandoc pipeline. Пользователь visual accepted 2026-11-01 (Task 67). Python generator (`gen_sigil_btb_doc.py`) остаётся как backup, parallel до v1.8 (per Q12 recommendation A: parallel 2 versions).

## 20.1. Pipeline architecture

```
pandoc_docx/
  build.py                ← 35-line Pandoc-based generator
  meta.yaml               ← single source of truth (version, title, date)
  content/                ← 20 .md files (NN_slug convention)
    01_vvedenie_zachem_nuzhen.md
    ...
    20_pandoc.md          ← этот раздел (NEW в v1.7)
    media/                ← 4 PNG diagrams
  golden/v1.6.docx        ← Python-generated reference (for comparison)
  output/sigil_btb_v<version>.docx
  tests/                  ← comparison reports + PDFs
  legacy/                 ← placeholder для Python generator после v1.8
```

**Single command build:** `python3 build.py` → `output/sigil_btb_v<version>.docx`

## 20.2. Build workflow (concrete)

| Step | Command | Time |
|------|---------|------|
| 1. Edit content | `vim content/NN_slug.md` | 5-10 min (writing) |
| 2. Bump version | `vim meta.yaml` → version: "1.6" → "1.7" | 30 sec |
| 3. Build | `python3 build.py` | **0.5 sec** |
| 4. Verify | `ls output/sigil_btb_v1.7.docx` | 5 sec |
| 5. Copy to download | `cp output/*.docx download/sigil_btb_documentation.docx` | 5 sec |
| 6. Update backup | `zip -r download/pandoc_docx_backup.zip pandoc_docx/` | 5 sec |

**Total: ~10 min** (content writing dominates; build itself 0.5 sec).

## 20.3. v1.7 first generation (this version)

| Metric | Value |
|--------|-------|
| File added | `content/20_pandoc.md` (this section) |
| Build command | `python3 build.py` |
| Build time | ~0.5 sec |
| Output | `output/sigil_btb_v1.7.docx` |
| H1 count | 20 (was 19 в v1.6, +1 for this §20) |
| Files processed | 20 (was 19 в v1.6) |
| Build return code | 0 (success) |

**Self-validation:** `build.py` automatically verifies H1 count in docx == H1 count в markdown sources. If mismatch — build fails.

## 20.4. Comparison with Python generator (v1.6 reference)

| Aspect | Pandoc pipeline | Python generator |
|--------|-----------------|------------------|
| Build time | **0.5 sec** | 5 sec |
| Source format | Markdown (easy) | Python code (1099 lines) |
| Syntax error risk | None (markdown) | High (nested lists, brackets) |
| Version bump time | ~10 min (content + 0.5s build) | ~50 sec (after optimizations) |
| Custom styling | Default pandoc (accepted) | DRAMATIC_DARK palette, custom shading |
| Cover page | Plain (starts with TOC) | Custom layout (accent line, metadata) |
| Page breaks | Continuous flow | PageBreak() before each H1 |
| TOC | `--toc` auto-generated | Manual + add_toc_placeholders.py |
| Reproducibility | Deterministic | Deterministic |
| Self-validation | H1 count check | postcheck.py (9 checks) |
| Text match with golden | **100% (1.0000)** | reference |

**Verdict:** Pandoc wins на speed + maintainability. Python wins на custom styling. Both produce identical text content.

## 20.5. Rollback procedure (3 layers)

**Layer 1: Avoid protection** (preventive)

`meta.auto [avoid:default]` включает `pandoc_docx/` — protected от accidental deletion during `!clean` operations.

**Layer 2: Backup zip** (sandbox persistence)

`download/pandoc_docx_backup.zip` (690 KB) — full pipeline backup. Restore: `unzip download/pandoc_docx_backup.zip`.

**Layer 3: Pre-pandoc snapshot** (rollback point)

`download/snapshots/pre-pandoc-migration.zip` (396 KB) — state before Pandoc pipeline. Includes:
- `scripts/gen_sigil_btb_doc.py` (Python generator)
- `download/sigil_btb_documentation.docx` (v1.6 Python output)
- `meta.auto` (pre-pandoc state)
- `roadmap.md` (pre-Task 67)

**Rollback commands** (existing verbs, no new sigil):

| Scenario | Command | Time |
|----------|---------|------|
| Pandoc output unacceptable | `!remove pandoc-pipeline` | ~30 sec |
| Full revert to pre-Pandoc state | `!revert pre-pandoc-migration` | ~1 min |
| Sandbox recycled, restore pipeline | `unzip download/pandoc_docx_backup.zip` (manual) | ~5 sec |

## 20.6. Migration timeline

| Version | Pipeline | Status |
|---------|----------|--------|
| v1.6 | Python generator (primary) + Pandoc (parallel test) | ✅ complete — both produce same content, 100% text match |
| **v1.7** | **Pandoc (primary)** + Python (backup) | **✅ CURRENT** — first pandoc-generated version, this section |
| v1.8 | Pandoc only (Python → `legacy/`) | ⏳ pending v1.7 success |
| v1.9+ | Pandoc + `reference.docx` (custom styles) | ⏳ pending — production polish |

**Acceptance criterion для v1.8:** v1.7 builds successfully, user confirms visual acceptable, no rollback needed within 1-2 weeks.

## 20.7. Protection autotokens (meta.auto)

```
[avoid:default]         += pandoc_docx/   # protected от cleanup
[docx:pipeline]         = pandoc-accepted  # current state
[docx:python-generator] = scripts/gen_sigil_btb_doc.py   # backup
[docx:pandoc-generator] = pandoc_docx/build.py           # primary
[docx:meta]             = pandoc_docx/meta.yaml
[docx:content]          = pandoc_docx/content/
[docx:golden]           = pandoc_docx/golden/v1.6.docx
[docx:rollback]         = !remove pandoc-pipeline
[docx:snapshot]         = pre-pandoc-migration
[docx:backup]           = download/pandoc_docx_backup.zip
```

## 20.8. Files produced в v1.7

```
pandoc_docx/
  content/20_pandoc.md              ← NEW (this section)
  meta.yaml                         ← UPDATED (version 1.6 → 1.7)
  output/sigil_btb_v1.7.docx        ← NEW (pandoc-built)

download/
  sigil_btb_documentation.docx      ← UPDATED (copy of pandoc v1.7 output)
  pandoc_docx_backup.zip            ← UPDATED (includes 20_pandoc.md)
```

## 20.9. Next version bump (v1.8) workflow

When next content addition needed:

1. Create `content/21_<slug>.md` (new section) OR edit existing `content/NN_*.md`
2. Edit `meta.yaml`: `version: "1.7"` → `"1.8"`, update `date`
3. Run: `cd pandoc_docx && python3 build.py`
4. Copy: `cp output/sigil_btb_v1.8.docx download/sigil_btb_documentation.docx`
5. Update backup: `zip -r download/pandoc_docx_backup.zip pandoc_docx/ -x "pandoc_docx/output/*" "pandoc_docx/tests/pages_*/*" "pandoc_docx/tests/*.pdf"`

**Estimated time:** ~10 min (content writing) + 0.5 sec build.

If v1.8 successful → move `scripts/gen_sigil_btb_doc.py` → `pandoc_docx/legacy/`, update `meta.auto [docx:pipeline] = pandoc-production`.
