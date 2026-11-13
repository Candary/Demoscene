#!/usr/bin/env python3
"""
generate_docx.py — генерация трёх docx через pandoc:
  1. sigil_btb_documentation.docx     (из pandoc_docx/content/*.md)
  2. color_matrix_documentation.docx  (из color_matrix/policy/*.md + доп.)
  3. cozy_engine_documentation.docx   (из cozy_engine/policy/*.md)

Использует pandoc_docx/reference.docx для стилей (table borders, font, headings).
Выход: download/<name>.docx
"""
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path("/home/z/my-project")
DOWNLOAD = ROOT / "download"
PANDOC_DOCX = ROOT / "pandoc_docx"
REF = PANDOC_DOCX / "reference.docx"

if not shutil.which("pandoc"):
    sys.exit("❌ pandoc не найден в PATH")


def run_pandoc(files: list[Path], meta_yaml: Path, out_path: Path, ref: Path = REF) -> tuple[bool, str]:
    """Запустить pandoc с указанными файлами и meta.yaml."""
    cmd = [
        "pandoc",
        *[str(f) for f in files],
        "--metadata-file", str(meta_yaml),
        "--toc", "--toc-depth=3",
        f"--resource-path={':'.join(str(f.parent) for f in files)}",
        "-o", str(out_path),
    ]
    if ref.exists():
        cmd += ["--reference-doc", str(ref)]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        return False, f"pandoc error:\n{r.stderr}"

    # Verify H1 count
    try:
        xml = zipfile.ZipFile(out_path).read("word/document.xml").decode("utf-8")
    except (zipfile.BadZipFile, KeyError):
        return False, "выходной файл — не валидный docx"
    got_h1 = len(re.findall(r'w:pStyle w:val="Heading1"', xml))
    want_h1 = sum(len(re.findall(r"^# ", f.read_text("utf-8"), re.M)) for f in files)
    return True, f"OK: {got_h1} H1 / {want_h1} expected, size={out_path.stat().st_size} bytes"


# === 1. sigil_btb — re-use existing pipeline ===

def gen_sigil_btb() -> tuple[bool, str]:
    """Запустить существующий pandoc_docx/build.py, скопировать в download/."""
    print("\n[1/3] sigil_btb_documentation.docx")
    build_py = PANDOC_DOCX / "build.py"
    if not build_py.exists():
        return False, "pandoc_docx/build.py not found"

    r = subprocess.run([sys.executable, str(build_py)], capture_output=True, text=True)
    if r.returncode:
        return False, f"build.py failed:\n{r.stderr}"

    # Найти свежесгенерированный файл в pandoc_docx/output/
    output_dir = PANDOC_DOCX / "output"
    if not output_dir.exists():
        return False, "output/ dir not created"

    files = sorted(output_dir.glob("sigil_btb_v*.docx"), key=lambda p: p.stat().st_mtime)
    if not files:
        return False, "no sigil_btb_v*.docx in output/"
    latest = files[-1]

    dest = DOWNLOAD / "sigil_btb_documentation.docx"
    shutil.copy2(latest, dest)
    return True, f"OK: {dest.name} = {dest.stat().st_size} bytes (from {latest.name})"


# === 2. color_matrix ===

def gen_color_matrix() -> tuple[bool, str]:
    """Собрать color_matrix docx из policy/*.md + каталога + rollback."""
    print("\n[2/3] color_matrix_documentation.docx")

    files = []
    # Core policies
    p1 = ROOT / "color_matrix" / "policy" / "color_policy.md"
    p2 = ROOT / "color_matrix" / "policy" / "shader_color_policy.md"
    if p1.exists():
        files.append(p1)
    if p2.exists():
        files.append(p2)
    # Catalog (uses Task log)
    cat = DOWNLOAD / "color_catalog.md"
    if cat.exists():
        files.append(cat)
    # Rollback procedure
    rb = DOWNLOAD / "snapshots" / "ROLLBACK_COLOR_MATRIX.md"
    if rb.exists():
        files.append(rb)

    if not files:
        return False, "no source .md files found for color_matrix"

    # Создать meta.yaml
    meta = DOWNLOAD / "_color_matrix_meta.yaml"
    meta.write_text(
        'title: "Color Matrix v11 — документация"\n'
        'subtitle: "16.7M RGB-цветов с empathy / entropy / synesthesia"\n'
        'author: "Документ — технический мануал"\n'
        'date: "7 ноября 2026"\n'
        'abstract: |\n'
        '  Цветовая матрица v11: 16.7M sRGB-цветов с empathy (-100..+100), entropy (0..100),\n'
        '  6 synesthesia dimensions. 8 Python tools для LLM function-calling.\n'
        '  Интеграция с demo_intro (shader_color_policy) и Cozy Engine (palette picker).\n'
        'version: "11"\n'
        'lang: ru-RU\n'
        'toc-title: "Оглавление"\n'
        'abstract-title: "Аннотация"\n',
        encoding="utf-8"
    )

    out = DOWNLOAD / "color_matrix_documentation.docx"
    ok, msg = run_pandoc(files, meta, out)
    meta.unlink()  # cleanup
    return ok, msg


# === 3. cozy_engine ===

def gen_cozy_engine() -> tuple[bool, str]:
    """Собрать cozy_engine docx из policy/*.md."""
    print("\n[3/3] cozy_engine_documentation.docx")

    files = []
    p = ROOT / "cozy_engine" / "policy" / "cozy_policy.md"
    if p.exists():
        files.append(p)

    if not files:
        return False, "no source .md files found for cozy_engine"

    meta = DOWNLOAD / "_cozy_engine_meta.yaml"
    meta.write_text(
        'title: "Cozy Engine v1.2 — документация"\n'
        'subtitle: "64 атома + Cozy Matrix 64³ + UnifiedToolbox"\n'
        'author: "Документ — технический мануал"\n'
        'date: "7 ноября 2026"\n'
        'abstract: |\n'
        '  Cozy Engine v1.2: ассоциации объектов с «уютом» в корпусе GPT-4o captions к ScanNet.\n'
        '  64 атома (objects + materials + lights + palettes + quality + rooms),\n'
        '  Cozy Matrix 64³, scan-weighted lifts, primitives.py для instantiate_object.\n'
        '  UnifiedToolbox объединяет с Color Matrix.\n'
        'version: "1.2"\n'
        'lang: ru-RU\n'
        'toc-title: "Оглавление"\n'
        'abstract-title: "Аннотация"\n',
        encoding="utf-8"
    )

    out = DOWNLOAD / "cozy_engine_documentation.docx"
    ok, msg = run_pandoc(files, meta, out)
    meta.unlink()
    return ok, msg


# === Main ===

def main():
    DOWNLOAD.mkdir(exist_ok=True)

    results = []
    for fn in [gen_sigil_btb, gen_color_matrix, gen_cozy_engine]:
        try:
            ok, msg = fn()
            results.append((fn.__name__, ok, msg))
            print(f"  → {'✅' if ok else '❌'} {msg}")
        except Exception as e:
            results.append((fn.__name__, False, f"exception: {e}"))
            print(f"  → ❌ exception: {e}")

    print("\n=== Summary ===")
    for name, ok, msg in results:
        status = "✅" if ok else "❌"
        print(f"  {status} {name}: {msg}")

    print(f"\nOutput dir: {DOWNLOAD}")
    for f in sorted(DOWNLOAD.glob("*documentation.docx")):
        print(f"  {f.name:40s} {f.stat().st_size:>10} bytes")


if __name__ == "__main__":
    main()
