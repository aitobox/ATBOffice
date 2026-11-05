"""Base styling definitions and builders for Ledger spreadsheet templates.

Aligns styling conventions and spec data structures with .vibeoffice/public/ledger/js/panes.js.
"""

from __future__ import annotations

import copy
from typing import Any

from atboffice.modules.spreadsheet.calc.references import col_index, parse_cell, parse_range
from atboffice.modules.spreadsheet.models.sheet_model import BorderStyle, CellData, SheetDataModel
from atboffice.modules.spreadsheet.models.validation import DataValidation, ValidationType
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

# Shared style tokens aligned with .vibeoffice TPL
B: dict[str, Any] = {"bold": True}

HDR: dict[str, Any] = {
    "bold": True,
    "fg_color": "#FFFFFF",
    "bg_color": "#336699",
    "pattern": "solid",
    "align_h": "center",
    "align_v": "center",
    "wrap_text": True,
}

TITLE: dict[str, Any] = {
    "bold": True,
    "font_size": 16,
    "fg_color": "#1F3F7F",
}

MONEY: dict[str, Any] = {
    "format_code": "$#,##0.00",
}

BOX: dict[str, Any] = {
    "border_top": BorderStyle(style="thin", color="#808080"),
    "border_bottom": BorderStyle(style="thin", color="#808080"),
    "border_left": BorderStyle(style="thin", color="#808080"),
    "border_right": BorderStyle(style="thin", color="#808080"),
}

INPUT: dict[str, Any] = {
    "bg_color": "#FFFFCC",
    "pattern": "solid",
    "locked": False,
}


def merge_styles(*styles: dict[str, Any] | None) -> dict[str, Any]:
    """Merge multiple style dictionaries into a combined style spec."""
    merged: dict[str, Any] = {}
    for st in styles:
        if st:
            for k, v in st.items():
                if isinstance(v, BorderStyle):
                    merged[k] = copy.copy(v)
                else:
                    merged[k] = v
    return merged


def apply_cell_spec(
    sheet: SheetDataModel,
    addr: str,
    val: Any,
    style: dict[str, Any] | None = None,
) -> None:
    """Parse address string, create CellData, and apply style properties."""
    coords = parse_cell(addr)
    if coords is None:
        return
    r = coords["r"]
    c = coords["c"]

    cell = sheet.get_cell(r, c) or CellData()

    if isinstance(val, str) and val.startswith("="):
        cell.formula = val
        cell.value = None
    elif val is not None:
        cell.value = val

    if style:
        if "format_code" in style:
            cell.format_code = style["format_code"]
        if "nf" in style:
            # Map .vibeoffice nf format string
            cell.format_code = style["nf"]
        if "bold" in style:
            cell.bold = bool(style["bold"])
        if "italic" in style:
            cell.italic = bool(style["italic"])
        if "font_size" in style:
            cell.font_size = int(style["font_size"])
        if "sz" in style:
            cell.font_size = int(style["sz"])
        if "font_family" in style:
            cell.font_family = str(style["font_family"])
        if "fg_color" in style:
            cell.fg_color = style["fg_color"]
        if "bg_color" in style:
            cell.bg_color = style["bg_color"]
        if "pattern" in style:
            cell.pattern = style["pattern"]
        if "align_h" in style:
            cell.align_h = style["align_h"]
        if "align_v" in style:
            cell.align_v = style["align_v"]
        if "wrap_text" in style:
            cell.wrap_text = bool(style["wrap_text"])
        if "locked" in style:
            cell.locked = bool(style["locked"])

        # Borders
        for side in ("border_top", "border_bottom", "border_left", "border_right"):
            if side in style and style[side] is not None:
                setattr(cell, side, copy.copy(style[side]))

    sheet.set_cell(r, c, cell)


def build_sheet_from_spec(
    spec: dict[str, Any],
    workbook: WorkbookModel,
) -> SheetDataModel:
    """Build and attach a SheetDataModel from a template sheet spec dictionary."""
    sheet_data = spec["sheets"][0]
    sheet_name = sheet_data.get("name", "Sheet1")
    sheet = workbook.add_sheet(name=sheet_name)

    # 1. Cells
    for item in sheet_data.get("cells", []):
        addr = item[0]
        val = item[1]
        st = item[2] if len(item) > 2 else None
        apply_cell_spec(sheet, addr, val, st)

    # 2. Ranges styles
    for rg, st in sheet_data.get("ranges", []):
        r_info = parse_range(rg)
        if r_info:
            for r in range(r_info["r1"], r_info["r2"] + 1):
                for c in range(r_info["c1"], r_info["c2"] + 1):
                    cell = sheet.get_cell(r, c) or CellData()
                    if st:
                        apply_cell_spec(sheet, f"R{r+1}C{c+1}", cell.value, st)

    # 3. Column widths
    for col_letter, width in sheet_data.get("cols", {}).items():
        c_idx = col_index(col_letter)
        sheet.geometry.set_col_width(c_idx, int(width * 8))

    # 4. Merged regions
    for m in sheet_data.get("merges", []):
        rng = parse_range(m)
        if rng:
            sheet.add_merge(rng["r1"], rng["c1"], rng["r2"], rng["c2"])

    # 5. Freeze panes
    freeze = sheet_data.get("freeze")
    if freeze and len(freeze) >= 2:
        sheet.freeze_rows = int(freeze[0])
        sheet.freeze_cols = int(freeze[1])

    # 6. Grid visibility & selection
    if sheet_data.get("grid") is False:
        sheet.extra["show_grid"] = False
    if "sel" in sheet_data:
        sheet.extra["initial_selection"] = sheet_data["sel"]

    # 7. Data validations
    for d in sheet_data.get("dv", []):
        ref = d.get("ref", "")
        f1 = d.get("f1", "")
        p_range = parse_range(ref)
        ranges = [(p_range["r1"], p_range["c1"], p_range["r2"], p_range["c2"])] if p_range else []
        dv = DataValidation(
            type=ValidationType.LIST.value if d.get("type") == "list" else ValidationType.ANY.value,
            formula1=f1,
            sqref=ref,
            ranges=ranges,
            show_dropdown=True,
            allow_blank=True,
            show_input_message=bool(d.get("prompt")),
            input_title=d.get("promptTitle", ""),
            input_message=d.get("prompt", ""),
        )
        sheet.add_data_validation(dv)

    return sheet
