# v1.7 version bump workflow (Pandoc pipeline)

**Created:** 2026-11-01
**Purpose:** Concrete workflow для next documentation version bump через Pandoc pipeline

---

## When to use

When next content addition needed:
- New formal Task added to roadmap (Task 67+)
- New §20+ section in documentation
- Auxiliary document promoted to formal section
- User-requested content changes

---

## Steps (concrete commands)

### Step 1: Edit content

```bash
cd /home/z/my-project/pandoc_docx/content/

# Option A: Add new section
# Create new file with NN_ prefix (next number after 19)
vim 20_new_section_slug.md
# Content:
# # 20. New Section Title
# Body text...
# Tables, code blocks, images as needed

# Option B: Modify existing section
vim 19_v1_6_changelog.md
# Add v1.7 changelog entries at the end
```

### Step 2: Edit meta.yaml (version bump)

```bash
cd /home/z/my-project/pandoc_docx/
vim meta.yaml
# Change:
#   version: "1.6" → "1.7"
#   date: "1 ноября 2026" → "<current date>"
# Optionally update abstract if version description changed
```

### Step 3: Run build

```bash
cd /home/z/my-project/pandoc_docx/
python3 build.py
```

**Expected output:**
```
✅ /home/z/my-project/pandoc_docx/output/sigil_btb_v1.7.docx  (XXX.X KB, H1: N, файлов: 20)
```

### Step 4: Verify output

```bash
# Check file exists
ls -la output/sigil_btb_v1.7.docx

# Check H1 count matches expected
# (build.py auto-verifies H1 count == markdown H1 count)

# Optional: structural comparison with v1.6
python3 tools_compare.py output/sigil_btb_v1.6.docx output/sigil_btb_v1.7.docx
# Should show differences only in expected places (new section, version, date)
```

### Step 5: Copy to download/ for user access

```bash
cp output/sigil_btb_v1.7.docx /home/z/my-project/download/sigil_btb_documentation.docx
```

**Note:** This overwrites the previous Python-generated docx. The Python generator is still available in `scripts/gen_sigil_btb_doc.py` as backup.

### Step 6: Update backup

```bash
cd /home/z/my-project/
zip -r download/pandoc_docx_backup.zip pandoc_docx/ \
  -x "pandoc_docx/output/*" "pandoc_docx/tests/pages_*/*" "pandoc_docx/tests/*.pdf"
```

### Step 7: Report to user

```
v1.7 generated via Pandoc pipeline
  build time: 0.5s
  output: download/sigil_btb_documentation.docx (XXX KB)
  H1: N (was 19 в v1.6, +1 for new §20)
  backup: download/pandoc_docx_backup.zip updated
  
  If unacceptable: !remove pandoc-pipeline (rollback to Python generator)
```

---

## Time estimate

| Step | Time |
|------|------|
| 1. Edit content (markdown) | 5-10 min (writing) |
| 2. Edit meta.yaml | 30 sec |
| 3. Run build | 0.5 sec |
| 4. Verify | 30 sec |
| 5. Copy to download | 5 sec |
| 6. Update backup | 5 sec |
| 7. Report | 30 sec |
| **Total** | **~10 min** (content writing dominates) |

**Comparison with Python generator:**
- Python: edit 1275-line .py + run + postcheck = ~50 sec (after py_compile optimizations)
- Pandoc: edit small .md + run = ~10 min total (content writing) + 0.5s build

**Net:** similar total time, BUT markdown editing safer (no Python syntax errors, no bracket matching issues).

---

## Rollback (if v1.7 unacceptable)

```
!remove pandoc-pipeline
  reason: v1.7 pandoc output <specific issue>
  action: restore Python generator
```

What I do:
1. `mv pandoc_docx/ legacy/pandoc_docx_disabled_$(date)/`
2. Update `meta.auto`: `[docx:pipeline] = python-restored`
3. Regenerate `download/sigil_btb_documentation.docx` via Python:
   ```bash
   cd /home/z/my-project/
   python3 scripts/gen_sigil_btb_doc.py
   ```
4. Report: rollback complete, v1.7 reverted to Python output

**Time:** ~30 sec

---

## After 2-3 successful version bumps

If v1.7, v1.8, v1.9 all successful via Pandoc:
1. Move `scripts/gen_sigil_btb_doc.py` → `pandoc_docx/legacy/gen_sigil_btb_doc.py`
2. Update `meta.auto`: `[docx:pipeline] = pandoc-production`
3. Create `reference.docx` with custom styles (15 min в LibreOffice)
4. Add image sizing attributes в markdown
5. Pandoc pipeline becomes production

**After this point:** version bumps take **~10 sec** (just edit meta.yaml + run build).
