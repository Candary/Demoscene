#!/usr/bin/env python3
"""
make_reference_docx.py — create pandoc_docx/reference.docx with proper table styling.

Generates a reference.docx template that defines:
  - "Table" style: visible borders (single 4pt black), cell margins (100 twips)
  - "Table Header" paragraph style: bold + light gray shading
  - "Compact" paragraph style: tight spacing for table cells

Pandoc inherits these styles via --reference-doc, fixing ugly default tables.

Usage:
  python3 scripts/make_reference_docx.py
  → pandoc_docx/reference.docx
"""
import subprocess
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Pt, RGBColor


OUT = Path("/home/z/my-project/pandoc_docx/reference.docx")
DEFAULT_REF = Path("/tmp/pandoc_default_reference.docx")


def get_default_reference():
    """Extract pandoc's default reference.docx via CLI."""
    result = subprocess.run(
        ["pandoc", "--print-default-data-file", "reference.docx"],
        capture_output=True, check=True,
    )
    DEFAULT_REF.write_bytes(result.stdout)
    print(f"  extracted default reference.docx → {DEFAULT_REF} ({len(result.stdout)} bytes)")


def add_table_borders(style_element):
    """Add tblBorders (single 4pt black) to a table style element."""
    tbl_pr = style_element.find(qn("w:tblPr"))
    if tbl_pr is None:
        tbl_pr = OxmlElement("w:tblPr")
        style_element.insert(0, tbl_pr)
    # Remove existing tblBorders if any
    existing = tbl_pr.find(qn("w:tblBorders"))
    if existing is not None:
        tbl_pr.remove(existing)
    # Add new tblBorders
    tbl_borders = OxmlElement("w:tblBorders")
    for border_name in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        border = OxmlElement(f"w:{border_name}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "4")        # 4 half-points = 0.5pt
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), "666666")  # dark gray (softer than pure black)
        tbl_borders.append(border)
    tbl_pr.append(tbl_borders)


def add_cell_margins(style_element, top=80, left=120, bottom=80, right=120):
    """Add tblCellMar (cell margins in twips) to a table style element."""
    tbl_pr = style_element.find(qn("w:tblPr"))
    if tbl_pr is None:
        tbl_pr = OxmlElement("w:tblPr")
        style_element.insert(0, tbl_pr)
    existing = tbl_pr.find(qn("w:tblCellMar"))
    if existing is not None:
        tbl_pr.remove(existing)
    tbl_cell_mar = OxmlElement("w:tblCellMar")
    for side, val in [("top", top), ("left", left), ("bottom", bottom), ("right", right)]:
        mar = OxmlElement(f"w:{side}")
        mar.set(qn("w:w"), str(val))
        mar.set(qn("w:type"), "dxa")
        tbl_cell_mar.append(mar)
    tbl_pr.append(tbl_cell_mar)


def set_table_layout_fixed(style_element):
    """Set table layout to 'fixed' (vs 'autofit') for predictable column widths."""
    tbl_pr = style_element.find(qn("w:tblPr"))
    if tbl_pr is None:
        tbl_pr = OxmlElement("w:tblPr")
        style_element.insert(0, tbl_pr)
    existing = tbl_pr.find(qn("w:tblLayout"))
    if existing is not None:
        tbl_pr.remove(existing)
    tbl_layout = OxmlElement("w:tblLayout")
    tbl_layout.set(qn("w:type"), "fixed")
    tbl_pr.append(tbl_layout)


def add_header_shading(paragraph_style_element, fill="E8E8F0"):
    """Add background shading to a paragraph style (for table header)."""
    p_pr = paragraph_style_element.find(qn("w:pPr"))
    if p_pr is None:
        p_pr = OxmlElement("w:pPr")
        paragraph_style_element.insert(0, p_pr)
    existing = p_pr.find(qn("w:shd"))
    if existing is not None:
        p_pr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    p_pr.append(shd)


def main():
    print("=== make_reference_docx.py ===")
    get_default_reference()

    print("  opening default reference.docx ...")
    doc = Document(str(DEFAULT_REF))

    styles = doc.styles
    found_table = False
    found_table_header = False

    # 1. Modify "Table" style (add borders + cell margins + fixed layout)
    for style in styles:
        if style.name == "Table":
            print(f"  found 'Table' style (id={style.style_id}), adding borders + margins + fixed layout")
            style_elem = style.element
            add_table_borders(style_elem)
            add_cell_margins(style_elem)
            set_table_layout_fixed(style_elem)
            found_table = True
            break

    if not found_table:
        print("  'Table' style not found, creating new one")
        from docx.enum.style import WD_STYLE_TYPE
        new_style = styles.add_style("Table", WD_STYLE_TYPE.TABLE)
        style_elem = new_style.element
        add_table_borders(style_elem)
        add_cell_margins(style_elem)
        set_table_layout_fixed(style_elem)

    # 2. Modify "Table Header" paragraph style (bold + shading)
    for style in styles:
        if style.name == "Table Header":
            print(f"  found 'Table Header' paragraph style, adding bold + shading")
            style_elem = style.element
            # Set bold
            r_pr = style_elem.find(qn("w:rPr"))
            if r_pr is None:
                r_pr = OxmlElement("w:rPr")
                style_elem.append(r_pr)
            bold = r_pr.find(qn("w:b"))
            if bold is None:
                bold = OxmlElement("w:b")
                r_pr.append(bold)
            # Add shading
            add_header_shading(style_elem, fill="E8E8F0")
            found_table_header = True
            break

    if not found_table_header:
        print("  'Table Header' style not found, creating new one")
        from docx.enum.style import WD_STYLE_TYPE
        new_style = styles.add_style("Table Header", WD_STYLE_TYPE.PARAGRAPH)
        style_elem = new_style.element
        r_pr = OxmlElement("w:rPr")
        r_pr.append(OxmlElement("w:b"))
        style_elem.append(r_pr)
        add_header_shading(style_elem, fill="E8E8F0")

    # 3. Save reference.docx
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print(f"\n✅ saved: {OUT} ({OUT.stat().st_size} bytes)")
    print(f"\nNow rebuild via:")
    print(f"  cd /home/z/my-project/pandoc_docx && python3 build.py")
    print(f"Pandoc will use reference.docx automatically (--reference-doc flag in build.py).")


if __name__ == "__main__":
    main()
