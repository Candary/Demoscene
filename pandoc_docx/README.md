# Pandoc DOCX pipeline — test mode

**Location:** `/home/z/my-project/pandoc_docx/`
**Status:** TEST MODE — parallel to `scripts/gen_sigil_btb_doc.py` (Python generator)
**Setup date:** 2026-11-01
**Approved via:** `#ok use-existing-verbs` (user, 2026-11-01)

---

## What this is

Test pipeline для sigil_btb_documentation.docx generation using Pandoc + Markdown.
Parallel to existing Python generator. v1.7+ version bumps будут use this pipeline;
v1.6 still produced by Python generator (in `/home/z/my-project/download/`).

---

## How to build

```bash
cd /home/z/my-project/pandoc_docx/
python3 build.py
# → output/sigil_btb_v<version>.docx
```

Build takes **~0.5 seconds** (vs ~5 sec Python generator).

---

## Version bump workflow

1. **Edit content/NN_*.md files** (add new section / modify existing)
   - To add new section: create `content/20_new_section_name.md`
   - To modify: edit existing `content/NN_*.md`

2. **Edit meta.yaml:**
   ```yaml
   version: "1.6" → "1.7"
   date: "1 ноября 2026" → "<current date>"
   ```

3. **Run build:**
   ```bash
   cd /home/z/my-project/pandoc_docx/
   python3 build.py
   ```

4. **Verify:**
   ```bash
   ls output/sigil_btb_v1.7.docx
   # check H1 count, file size в build output
   ```

5. **Compare with previous:**
   ```bash
   python3 tools_compare.py output/sigil_btb_v1.6.docx output/sigil_btb_v1.7.docx
   ```

6. **Copy to download/ for user access:**
   ```bash
   cp output/sigil_btb_v1.7.docx /home/z/my-project/download/sigil_btb_documentation.docx
   ```

7. **Update backup:**
   ```bash
   cd /home/z/my-project/
   zip -r download/pandoc_docx_backup.zip pandoc_docx/ -x "pandoc_docx/output/*" "pandoc_docx/tests/pages_*/*"
   ```

---

## v1.6 test results

### Build
- Command: `python3 build.py`
- Output: `output/sigil_btb_v1.6.docx`
- Size: **302 KB**
- H1 count: **19**
- Files processed: **19**
- Build time: **~0.5 sec**

### Structural comparison (vs golden + Python v1.6)

```
golden  H1:20 H2:43 tables:27 images:4 drawings:4 size:336 KB
pandoc  H1:19 H2:43 tables:27 images:4 drawings:4 size:302 KB
```

**Text similarity: 1.0000 (100% match)**
**Divergence blocks: 0**

Only difference: H1 count 19 vs 20 (pandoc не считает TOC title как Heading1 — minor).

### Visual comparison (PDF)

| Metric | Pandoc output | Python output |
|--------|---------------|---------------|
| Pages | 38 | 39 |
| PDF size | 787 KB | 882 KB |
| Docx size | 302 KB | 344 KB |

Pandoc output **1 page fewer** (continuous flow, no page break before each H1).

---

## What's different from Python generator

### ✅ Preserved (100% match)
- All text content
- All H2 headings (43)
- All tables (27)
- All images (4)
- All drawings (4)

### ❌ Lost (default pandoc styling)
- Custom cover page (title, accent line, metadata block) — pandoc starts directly with TOC
- DRAMATIC_DARK palette (custom heading colors)
- Page breaks between sections (continuous flow)
- Alternating row shading in tables
- Code blocks custom monospace + shading
- 1 H1 heading (TOC title)

### ✅ Gained
- 25× faster build (0.5s vs 5s)
- Markdown source (easier to edit, no syntax errors)
- Single source of truth (meta.yaml for version)
- Reproducible (deterministic output)
- Self-validating (H1 count check)

---

## To make production-ready

After 2-3 successful version bumps в test mode, upgrade to production:

1. **Create reference.docx** (one-time setup, ~15 min в LibreOffice):
   ```bash
   pandoc --print-default-data-file reference.docx > reference.docx
   # Open в LibreOffice, configure:
   # - Heading 1: color #0F0F1A, font Calibri/SimHei, "page break before" = true
   # - Heading 2: color #505070
   # - Body: line spacing 1.3x, justified, 2-char indent
   # - Source Code: Consolas, light gray shading
   # - Table style: header bold, alternating rows
   ```

2. **Add image sizing attributes** в markdown (5 min):
   ```markdown
   ![caption](media/image1.png){width=600px}
   ```

3. **Run build**, verify styles applied:
   ```bash
   python3 build.py  # now uses reference.docx automatically
   ```

---

## Rollback procedure

**If Pandoc pipeline rejected:** use existing `!remove` verb

```
!remove pandoc-pipeline
  reason: <конкретная причина>
  action: disable pandoc, restore Python generator как default
  preserve: pandoc_docx/ → legacy/pandoc_docx_disabled_<date>/
```

What I do:
1. `mv pandoc_docx/ legacy/pandoc_docx_disabled_$(date)/`
2. Update `meta.auto`: `[docx:pipeline] = python-restored`
3. Regenerate `download/sigil_btb_documentation.docx` via `python3 scripts/gen_sigil_btb_doc.py`
4. Report: rollback complete

**If full revert needed:** `!revert pre-pandoc-migration` (snapshot в `download/snapshots/pre-pandoc-migration.zip`)

**If sandbox recycled:** manual restore:
```bash
cd /home/z/my-project/
unzip download/pandoc_docx_backup.zip
python3 pandoc_docx/build.py  # verify works
```

---

## Files

| Path | Purpose |
|------|---------|
| `build.py` | Pandoc-based generator (35 lines, clean) |
| `meta.yaml` | Single source of truth (version, title, date, lang) |
| `content/NN_slug.md` | 19 section files (sorted by NN prefix) |
| `content/media/image1-4.png` | 4 diagram PNGs |
| `golden/v1.6.docx` | Reference from Python generator |
| `golden/v1.6.txt` | Plain text of golden reference |
| `tools_split_roundtrip.py` | Extraction tool (used once for migration) |
| `tools_compare.py` | Structural + text comparison |
| `tests/` | Comparison reports + PDFs |
| `legacy/` | Placeholder for gen_sigil_btb_doc.py after migration |

---

## Protection

`pandoc_docx/` защищён от accidental deletion через:
- `meta.auto [avoid:default]` includes `pandoc_docx/`
- Backup zip: `download/pandoc_docx_backup.zip`
- Pre-pandoc snapshot: `download/snapshots/pre-pandoc-migration.zip`

---

## Migration plan (phases)

- **v1.6 (current):** both generators produce same content (parallel test) ✅
- **v1.7:** pandoc pipeline used, Python generator as backup
- **v1.8:** if v1.7 OK → pandoc only, Python → `legacy/`
- **v1.9+:** pandoc only, `reference.docx` added for production styling
