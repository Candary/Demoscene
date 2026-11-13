#!/usr/bin/env python3
"""content/NN_*.md + meta.yaml -> output/<name>_v<version>.docx через Pandoc."""
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT, OUT = ROOT / "content", ROOT / "output"
META, REF = ROOT / "meta.yaml", ROOT / "reference.docx"


def fail(msg: str):
    sys.exit(f"❌ {msg}")


def main():
    if not shutil.which("pandoc"):
        fail("pandoc не найден в PATH")

    files = sorted(CONTENT.glob("*.md"))
    bad = [f.name for f in files if not re.match(r"\d{2}_", f.name)]
    if not files or bad:
        fail(f"нужны файлы NN_name.md; проблема: {bad or 'content/ пуст'}")

    m = re.search(r'^version:\s*"?([\w.\-]+)"?\s*$', META.read_text("utf-8"), re.M)
    if not m:
        fail("в meta.yaml нет поля version")
    out = OUT / f"sigil_btb_v{m.group(1)}.docx"
    OUT.mkdir(exist_ok=True)

    cmd = ["pandoc", *map(str, files), "--metadata-file", str(META),
           "--toc", "--toc-depth=3", f"--resource-path={CONTENT}",
           "--fail-if-warnings", "-o", str(out)]
    if REF.exists():
        cmd += ["--reference-doc", str(REF)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        fail(f"pandoc:\n{r.stderr}")

    # Проверка: заголовки H1 в docx == заголовки H1 в исходниках
    try:
        xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")
    except (zipfile.BadZipFile, KeyError):
        fail("выходной файл — не валидный docx")
    got = len(re.findall(r'w:pStyle w:val="Heading1"', xml))
    want = sum(len(re.findall(r"^# ", f.read_text("utf-8"), re.M)) for f in files)
    if got != want:
        fail(f"H1: в md {want}, в docx {got}")

    print(f"✅ {out}  ({out.stat().st_size / 1024:.1f} KB, H1: {got}, файлов: {len(files)})")


if __name__ == "__main__":
    main()
