#!/usr/bin/env python3
"""Embed fire_spritesheet.png as a base64 data URI in preview.html.

Why: headless Chrome treats file:// images as cross-origin and WebGL2 refuses
to sample them ("The image element contains cross-origin data, and may not be
loaded"). Embedding the PNG as a data URI sidesteps CORS entirely.
"""
import base64
import sys
from pathlib import Path

DEMO_DIR = Path("/home/z/my-project/download/demo_intro")
PNG_PATH = DEMO_DIR / "fire_spritesheet.png"
HTML_PATH = DEMO_DIR / "preview.html"

# Load PNG
png_bytes = PNG_PATH.read_bytes()
print(f"PNG size: {len(png_bytes)} bytes")
b64 = base64.b64encode(png_bytes).decode("ascii")
data_uri = f"data:image/png;base64,{b64}"
print(f"Data URI length: {len(data_uri)} chars")

# Patch preview.html: replace `fireImg.src = 'fire_spritesheet.png';`
# with `fireImg.src = '<data URI>';`
html = HTML_PATH.read_text(encoding="utf-8")
old_line = "fireImg.src = 'fire_spritesheet.png';"
new_line = f"fireImg.src = '{data_uri}';"
if old_line not in html:
    print(f"ERROR: anchor not found: {old_line!r}", file=sys.stderr)
    sys.exit(1)
new_html = html.replace(old_line, new_line)
print(f"Patch: {old_line!r} → data URI ({len(new_line)} chars)")

HTML_PATH.write_text(new_html, encoding="utf-8")
print(f"Wrote: {HTML_PATH} ({len(new_html)} bytes total)")
