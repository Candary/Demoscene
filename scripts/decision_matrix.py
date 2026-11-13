#!/usr/bin/env python3
"""
decision_matrix.py — заполнить шаблон Decision Matrix для Scene Manager variants.

Шаблон от пользователя: 5 строк (Время/Audio/Atom/Post-proc/Риск) × 4 столбца
(4K / 64K / Demo быстро / Demo качественно).

Добавляем 6-ю строку: Рекомендуемый Variant (B/A/A+E/A→D или E).
"""
import sys
import os
from pathlib import Path

XLSX_SKILL_DIR = "/home/z/my-project/skills/xlsx"
for sub in [XLSX_SKILL_DIR, os.path.join(XLSX_SKILL_DIR, "templates")]:
    if sub not in sys.path:
        sys.path.insert(0, sub)

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT_PATH = "/home/z/my-project/download/decision_matrix.xlsx"

# === Содержание матрицы ===

HEADERS = ["Фактор", "4K compo", "64K compo", "Demo (быстро)", "Demo (качественно)"]

ROWS = [
    # (factor, 4K, 64K, Demo-быстро, Demo-качественно)
    ("Время (time-to-demo)",
     "1-2 дня",
     "3-5 дней",
     "3-5 дней",
     "10-15 дней"),

    ("Audio engine",
     "встроенный синтез (размер < 200 байт)",
     "4Klang или C99 synth (~2-3 КБ)",
     "silence или pre-rendered track",
     "4Klang/C99 + beat sync (full music engine)"),

    ("Atom library (64 shaders)",
     "❌ не нужно",
     "❌ не нужно",
     "❌ не нужно (Variant A с ручными шейдерами)",
     "опционально (Variant D — только если есть неделя на atom library)"),

    ("Post-processing",
     "минимальный (внутри шейдера)",
     "базовый (bloom + chromatic aberration)",
     "минимальный (vignette + grain)",
     "полный pipeline (bloom + grain + aberration + color grade + motion blur)"),

    ("Главный риск",
     "лимит 4096 байт — каждый байт на счету",
     "binary size + transitions FBO overhead",
     "время vs quality tradeoff — компромисс виден",
     "сложность multi-pass + atom library + music sync (3 unknowns)"),

    # 6-я строка — добавленная, итоговая
    ("РЕКОМЕНДУЕМЫЙ VARIANT",
     "B (Uber Shader)",
     "A (Timeline)",
     "A + минимальный post (vignette+grain)",
     "A → E (Layered Hybrid) или A → D (если atom library готов)"),
]

# === Стили ===

# Цвета по status (visualization)
COLOR_HEADER_BG = "1F4E78"     # тёмно-синий
COLOR_HEADER_FG = "FFFFFF"
COLOR_FACTOR_BG = "D9E1F2"     # светло-голубой
COLOR_4K_BG     = "FFE699"     # жёлтый (warning — size limit)
COLOR_64K_BG    = "C6EFCE"     # зелёный (safe)
COLOR_DEMO_FAST = "FFD966"     # оранжевый (tradeoff)
COLOR_DEMO_QUAL = "F4B084"     # красно-оранжевый (high effort)
COLOR_REC_BG    = "FFC000"     # золотой (recommendation row)
COLOR_REC_FG    = "000000"

THIN = Side(border_style="thin", color="000000")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

FONT_HEADER = Font(name="Calibri", size=11, bold=True, color=COLOR_HEADER_FG)
FONT_FACTOR = Font(name="Calibri", size=11, bold=True)
FONT_CELL   = Font(name="Calibri", size=10)
FONT_REC    = Font(name="Calibri", size=11, bold=True, color=COLOR_REC_FG)

ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_LEFT   = Alignment(horizontal="left", vertical="center", wrap_text=True)


def build():
    wb = Workbook()
    wb.properties.creator = "Z.ai"
    ws = wb.active
    ws.title = "Decision Matrix"

    # Заголовки (row 1)
    for col_idx, header in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = FONT_HEADER
        cell.fill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER

    # Данные (rows 2-7) — col_bg индексы 0..4 соответствуют column 1..5
    col_bg = [COLOR_FACTOR_BG, COLOR_4K_BG, COLOR_64K_BG, COLOR_DEMO_FAST, COLOR_DEMO_QUAL]
    for row_idx, row_data in enumerate(ROWS, start=2):
        is_rec_row = row_data[0].startswith("РЕКОМЕНДУЕМЫЙ")
        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = BORDER
            if col_idx == 1:
                # Фактор column
                cell.font = FONT_REC if is_rec_row else FONT_FACTOR
                cell.fill = PatternFill("solid", fgColor=COLOR_REC_BG if is_rec_row else COLOR_FACTOR_BG)
                cell.alignment = ALIGN_LEFT
            else:
                cell.font = FONT_REC if is_rec_row else FONT_CELL
                if is_rec_row:
                    cell.fill = PatternFill("solid", fgColor=COLOR_REC_BG)
                else:
                    cell.fill = PatternFill("solid", fgColor=col_bg[col_idx - 1])
                cell.alignment = ALIGN_LEFT

    # Ширина колонок
    ws.column_dimensions["A"].width = 28
    for col in ["B", "C", "D", "E"]:
        ws.column_dimensions[col].width = 32

    # Высота строк
    ws.row_dimensions[1].height = 30
    for r in range(2, len(ROWS) + 2):
        ws.row_dimensions[r].height = 60 if r == len(ROWS) + 1 else 50

    # Freeze panes (header row + first column)
    ws.freeze_panes = "B2"

    # Title above the table — insert row at top
    ws.insert_rows(1)
    title_cell = ws.cell(row=1, column=1, value="Scene Manager — Decision Matrix (по constraints, не только compo category)")
    title_cell.font = Font(name="Calibri", size=14, bold=True, color="1F4E78")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=5)
    ws.row_dimensions[1].height = 25

    # Notes below the table
    notes_row = len(ROWS) + 3  # after header(1) + title(1) + data(6) = row 8
    notes = [
        "КАК ЧИТАТЬ:",
        "1. Столбец = твоя ситуация (compo + constraint).",
        "2. Строка = фактор, который нужно учесть.",
        "3. Ячейка = требование для этой комбинации.",
        "4. ПОСЛЕДНЯЯ строка = рекомендуемый Variant (с учётом всех факторов).",
        "",
        "ПРИМЕРЫ:",
        "• Demo, но нет времени на 64 atom shaders → столбец «Demo (быстро)» → Variant A.",
        "• Demo, но audio engine не готов → столбец «Demo (быстро)» → Variant A (silence OK).",
        "• Demo, нужен polished look за 2 дня → столбец «Demo (быстро)» → A + минимальный post.",
        "• Demo, есть неделя на atom library → столбец «Demo (качественно)» → A → D или E.",
    ]
    for i, note in enumerate(notes):
        cell = ws.cell(row=notes_row + i, column=1, value=note)
        if note.endswith(":"):
            cell.font = Font(name="Calibri", size=11, bold=True, color="1F4E78")
        else:
            cell.font = Font(name="Calibri", size=10, color="000000")
        ws.merge_cells(start_row=notes_row + i, start_column=1, end_row=notes_row + i, end_column=5)

    wb.save(OUT_PATH)
    print(f"Saved: {OUT_PATH}")
    print(f"Size: {Path(OUT_PATH).stat().st_size} bytes")


if __name__ == "__main__":
    build()
