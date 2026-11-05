"""XML Spreadsheet 2003 (SpreadsheetML) reader and writer for ATBOffice Ledger."""

from __future__ import annotations

import datetime
import html
import re
import xml.etree.ElementTree as ET
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import date_to_serial
from atboffice.modules.spreadsheet.calc.errors import ALL_ERRORS, ExcelError
from atboffice.modules.spreadsheet.calc.references import (
    col_index,
    col_name,
)
from atboffice.modules.spreadsheet.io.csv_io import decode_bytes
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

SS_URN = "urn:schemas-microsoft-com:office:spreadsheet"


def from_r1c1(text: str, r: int, c: int) -> str:
    """Convert R1C1 formula string to A1 format for a cell at (r, c).

    Returns formula string without leading '='.
    """
    s = text.lstrip("=")
    out: list[str] = []
    i = 0
    n = len(s)

    def part(m: str | None, base: int) -> tuple[int, bool]:
        if not m:
            return base, False
        if m.startswith("[") and m.endswith("]"):
            return base + int(m[1:-1]), False
        return int(m) - 1, True

    def cell_a1(rr: tuple[int, bool], cc: tuple[int, bool]) -> str:
        c_abs = "$" if cc[1] else ""
        c_str = col_name(max(0, cc[0]))
        r_abs = "$" if rr[1] else ""
        r_str = str(max(0, rr[0]) + 1)
        return f"{c_abs}{c_str}{r_abs}{r_str}"

    r1c1_re = re.compile(r"^(?:[Rr](\[-?\d+\]|\d+)?)?(?:[Cc](\[-?\d+\]|\d+)?)?")

    while i < n:
        ch = s[i]
        # Preserve double-quoted string literals
        if ch == '"':
            end_idx = s.find('"', i + 1)
            while end_idx != -1 and end_idx + 1 < n and s[end_idx + 1] == '"':
                end_idx = s.find('"', end_idx + 2)
            e = n if end_idx == -1 else end_idx + 1
            out.append(s[i:e])
            i = e
            continue

        # Preserve single-quoted sheet names (e.g. 'Sheet 1'!R1C1)
        if ch == "'":
            end_idx = s.find("'", i + 1)
            while end_idx != -1 and end_idx + 1 < n and s[end_idx + 1] == "'":
                end_idx = s.find("'", end_idx + 2)
            e = n if end_idx == -1 else end_idx + 1
            out.append(s[i:e])
            i = e
            continue

        prev = s[i - 1] if i > 0 else ""
        if ch in "RrCc" and not (prev and (prev.isalnum() or prev in "_.]$")):
            m = r1c1_re.match(s[i:])
            if m:
                tok = m.group(0)
                after = s[i + len(tok)] if i + len(tok) < n else ""
                has_r = tok.startswith(("R", "r"))
                after_r = re.sub(r"^[Rr](\[-?\d+\]|\d+)?", "", tok)
                has_c = any(c_ch in "Cc" for c_ch in after_r)

                if (
                    tok
                    and (has_r or has_c)
                    and not (after and (after.isalnum() or after in "_.(("))
                ):
                    m_r = m.group(1)
                    m_c = m.group(2)
                    rr = part(m_r, r) if has_r else None
                    cc = part(m_c, c) if has_c else None

                    if rr and cc:
                        out.append(cell_a1(rr, cc))
                    elif rr:
                        r_abs = "$" if rr[1] else ""
                        out.append(f"{r_abs}{rr[0] + 1}:{r_abs}{rr[0] + 1}")
                    elif cc:
                        c_abs = "$" if cc[1] else ""
                        c_name = col_name(cc[0])
                        out.append(f"{c_abs}{c_name}:{c_abs}{c_name}")

                    i += len(tok)
                    continue

        out.append(ch)
        i += 1

    res = "".join(out)
    # Simplify duplicate row / col ranges like 1:1:3:3 -> 1:3
    res = re.sub(r"(\$?\d+):\$?\d+:(\$?\d+):\$?\d+", r"\1:\2", res)
    res = re.sub(r"(\$?[A-Z]+):\$?[A-Z]+:(\$?[A-Z]+):\$?[A-Z]+", r"\1:\2", res)
    return res


def to_r1c1(formula: str, r: int, c: int) -> str:
    """Convert A1 formula string into R1C1 format with leading '=' for a cell at (r, c)."""
    s = formula.lstrip("=")

    def rel(target: int, base: int, is_abs: bool) -> str:
        if is_abs:
            return str(target + 1)
        if target == base:
            return ""
        return f"[{target - base}]"

    def cell_to_rc(col_str: str, row_str: str) -> str:
        ca = col_str.startswith("$")
        c_idx = col_index(col_str.lstrip("$"))
        ra = row_str.startswith("$")
        r_idx = int(row_str.lstrip("$")) - 1
        return f"R{rel(r_idx, r, ra)}C{rel(c_idx, c, ca)}"

    def col_range_to_rc(c1_str: str, c2_str: str) -> str:
        ca1 = c1_str.startswith("$")
        c1_idx = col_index(c1_str.lstrip("$"))
        ca2 = c2_str.startswith("$")
        c2_idx = col_index(c2_str.lstrip("$"))
        return f"C{rel(c1_idx, c, ca1)}:C{rel(c2_idx, c, ca2)}"

    def row_range_to_rc(r1_str: str, r2_str: str) -> str:
        ra1 = r1_str.startswith("$")
        r1_idx = int(r1_str.lstrip("$")) - 1
        ra2 = r2_str.startswith("$")
        r2_idx = int(r2_str.lstrip("$")) - 1
        return f"R{rel(r1_idx, r, ra1)}:R{rel(r2_idx, r, ra2)}"

    ref_pat = re.compile(
        r"((?:'(?:[^']|'')+'|[A-Za-z0-9_]+)!)?"
        r"(?:"
        r"(\$?[A-Za-z]{1,3})(\$?\d+):(\$?[A-Za-z]{1,3})(\$?\d+)"
        r"|(?<![A-Za-z0-9_])(\$?[A-Za-z]{1,3}):(\$?[A-Za-z]{1,3})(?![A-Za-z0-9_])"
        r"|(?<![A-Za-z0-9_])(\$?\d+):(\$?\d+)(?![A-Za-z0-9_])"
        r"|(?<![A-Za-z0-9_])(\$?[A-Za-z]{1,3})(\$?\d+)(?![A-Za-z0-9_]|\s*\()"
        r")"
    )

    def replace_ref(m: re.Match[str]) -> str:
        sh = m.group(1) or ""
        if m.group(2) and m.group(3) and m.group(4) and m.group(5):
            return f"{sh}{cell_to_rc(m.group(2), m.group(3))}:{cell_to_rc(m.group(4), m.group(5))}"
        if m.group(6) and m.group(7):
            return f"{sh}{col_range_to_rc(m.group(6), m.group(7))}"
        if m.group(8) and m.group(9):
            return f"{sh}{row_range_to_rc(m.group(8), m.group(9))}"
        if m.group(10) and m.group(11):
            return f"{sh}{cell_to_rc(m.group(10), m.group(11))}"
        return m.group(0)

    # Tokenize preserving string literals
    tokens: list[str] = []
    i = 0
    n = len(s)
    curr_seg: list[str] = []

    while i < n:
        if s[i] == '"':
            if curr_seg:
                tokens.append("".join(curr_seg))
                curr_seg = []
            end = s.find('"', i + 1)
            while end != -1 and end + 1 < n and s[end + 1] == '"':
                end = s.find('"', end + 2)
            e = n if end == -1 else end + 1
            tokens.append(s[i:e])
            i = e
        else:
            curr_seg.append(s[i])
            i += 1
    if curr_seg:
        tokens.append("".join(curr_seg))

    out_parts: list[str] = [
        tok if tok.startswith('"') else ref_pat.sub(replace_ref, tok) for tok in tokens
    ]
    return "=" + "".join(out_parts)


def _local_name(tag: str) -> str:
    """Extract local name from XML tag removing namespace if present."""
    return tag.split("}")[-1] if "}" in tag else tag


def _get_attrib(el: ET.Element, name: str) -> str | None:
    """Get attribute ignoring namespace prefix or matching ss: prefix."""
    if f"{{{SS_URN}}}{name}" in el.attrib:
        return el.attrib[f"{{{SS_URN}}}{name}"]
    if f"ss:{name}" in el.attrib:
        return el.attrib[f"ss:{name}"]
    if name in el.attrib:
        return el.attrib[name]
    for k, v in el.attrib.items():
        if _local_name(k) == name:
            return v
    return None


def read_xmlss(
    content: str | bytes,
    model: SheetDataModel | WorkbookModel | None = None,
    return_workbook: bool = False,
) -> SheetDataModel | WorkbookModel:
    """Parse XML Spreadsheet 2003 content into a SheetDataModel or WorkbookModel."""
    if isinstance(content, bytes):
        text, _ = decode_bytes(content)
    else:
        text = content

    if "urn:schemas-microsoft-com:office:spreadsheet" not in text:
        raise ValueError("This file is not an XML Spreadsheet 2003 workbook.")

    root = ET.fromstring(text)

    # 1. Parse Styles
    styles: dict[str, dict[str, Any]] = {}
    styles_el = None
    for child in root:
        if _local_name(child.tag) == "Styles":
            styles_el = child
            break

    if styles_el is not None:
        for st_el in styles_el:
            if _local_name(st_el.tag) != "Style":
                continue
            st_id = _get_attrib(st_el, "ID")
            if not st_id:
                continue

            style_dict: dict[str, Any] = {}
            for prop in st_el:
                prop_tag = _local_name(prop.tag)
                if prop_tag == "Font":
                    for ak, av in prop.attrib.items():
                        aln = _local_name(ak)
                        if aln == "Bold" and av in ("1", "true", "True"):
                            style_dict["bold"] = True
                        elif aln == "Italic" and av in ("1", "true", "True"):
                            style_dict["italic"] = True
                        elif aln == "Underline":
                            if av and av != "None":
                                style_dict["underline"] = True
                                style_dict["underline_style"] = av.lower()
                        elif aln == "StrikeThrough" and av in ("1", "true", "True"):
                            style_dict["strike"] = True
                        elif aln == "VerticalAlign":
                            style_dict["vert_align"] = av.lower()
                        elif aln == "Color":
                            style_dict["fg_color"] = av
                        elif aln == "FontName":
                            style_dict["font_family"] = av
                        elif aln == "Size":
                            try:
                                style_dict["font_size"] = int(float(av))
                            except ValueError:
                                pass
                elif prop_tag == "Interior":
                    for ak, av in prop.attrib.items():
                        aln = _local_name(ak)
                        if aln == "Color":
                            style_dict["bg_color"] = av
                        elif aln == "Pattern":
                            style_dict["pattern"] = av
                        elif aln == "PatternColor":
                            style_dict["pattern_color"] = av
                elif prop_tag == "NumberFormat":
                    fmt = _get_attrib(prop, "Format")
                    if fmt:
                        style_dict["format_code"] = fmt
                elif prop_tag == "Alignment":
                    for ak, av in prop.attrib.items():
                        aln = _local_name(ak)
                        if aln == "Horizontal" and av != "Automatic":
                            style_dict["align_h"] = av.lower()
                        elif aln == "Vertical" and av != "Automatic":
                            style_dict["align_v"] = av.lower()
                        elif aln == "WrapText" and av in ("1", "true", "True"):
                            style_dict["wrap_text"] = True
                        elif aln == "ShrinkToFit" and av in ("1", "true", "True"):
                            style_dict["shrink_to_fit"] = True
                        elif aln == "Indent":
                            try:
                                style_dict["indent"] = int(av)
                            except ValueError:
                                pass
                        elif aln == "Rotate":
                            try:
                                style_dict["text_rotation"] = int(av)
                            except ValueError:
                                pass
                elif prop_tag == "Borders":
                    for b_el in prop:
                        if _local_name(b_el.tag) != "Border":
                            continue
                        pos = _get_attrib(b_el, "Position")
                        line_style = _get_attrib(b_el, "LineStyle") or "Continuous"
                        weight_str = _get_attrib(b_el, "Weight") or "1"
                        color = _get_attrib(b_el, "Color")
                        wt = int(weight_str) if weight_str.isdigit() else 1
                        bs_style = "thin"
                        if line_style == "Double":
                            bs_style = "double"
                        elif line_style in ("Dash", "Dot"):
                            bs_style = "dashed" if line_style == "Dash" else "dotted"
                        elif wt >= 3:
                            bs_style = "thick"
                        elif wt == 2:
                            bs_style = "medium"
                        elif wt == 0:
                            bs_style = "hair"

                        b_obj = BorderStyle(style=bs_style, color=color)
                        if pos == "Top":
                            style_dict["border_top"] = b_obj
                        elif pos == "Bottom":
                            style_dict["border_bottom"] = b_obj
                        elif pos == "Left":
                            style_dict["border_left"] = b_obj
                        elif pos == "Right":
                            style_dict["border_right"] = b_obj
                        elif pos == "DiagonalLeft":
                            style_dict["border_diag_down"] = b_obj
                        elif pos == "DiagonalRight":
                            style_dict["border_diag_up"] = b_obj

            styles[st_id] = style_dict

    # 2. Parse ExcelWorkbook options (ActiveSheet)
    active_sheet_index = 0
    for child in root:
        if _local_name(child.tag) == "ExcelWorkbook":
            for wb_child in child:
                if _local_name(wb_child.tag) == "ActiveSheet":
                    try:
                        active_sheet_index = int(wb_child.text or "0")
                    except ValueError:
                        pass

    # 3. Parse all Worksheets
    parsed_sheets: list[SheetDataModel] = []

    sheet_idx = 0
    for child in root:
        if _local_name(child.tag) != "Worksheet":
            continue

        raw_sheet_name = _get_attrib(child, "Name")
        sheet_name = raw_sheet_name if raw_sheet_name else f"Sheet{sheet_idx + 1}"
        sheet = SheetDataModel(name=sheet_name)

        # WorksheetOptions
        for ws_child in child:
            if _local_name(ws_child.tag) == "WorksheetOptions":
                for opt in ws_child:
                    opt_tag = _local_name(opt.tag)
                    if opt_tag == "Selected":
                        active_sheet_index = sheet_idx
                    elif opt_tag == "SplitHorizontal":
                        try:
                            sheet.freeze_rows = int(opt.text or "0")
                        except ValueError:
                            pass
                    elif opt_tag == "SplitVertical":
                        try:
                            sheet.freeze_cols = int(opt.text or "0")
                        except ValueError:
                            pass

        table_el = None
        for ws_child in child:
            if _local_name(ws_child.tag) == "Table":
                table_el = ws_child
                break

        if table_el is not None:
            # Table level defaults
            def_col_w_pt = _get_attrib(table_el, "DefaultColumnWidth")
            if def_col_w_pt:
                try:
                    sheet.geometry.default_col_width = int(round(float(def_col_w_pt) / 0.75))
                except ValueError:
                    pass
            def_row_h_pt = _get_attrib(table_el, "DefaultRowHeight")
            if def_row_h_pt:
                try:
                    sheet.geometry.default_row_height = int(round(float(def_row_h_pt) / 0.75))
                except ValueError:
                    pass

            # Columns
            col_curr = -1
            for t_child in table_el:
                if _local_name(t_child.tag) == "Column":
                    idx_attr = _get_attrib(t_child, "Index")
                    if idx_attr:
                        try:
                            col_curr = int(idx_attr) - 1
                        except ValueError:
                            col_curr += 1
                    else:
                        col_curr += 1

                    span = 0
                    span_attr = _get_attrib(t_child, "Span")
                    if span_attr:
                        try:
                            span = int(span_attr)
                        except ValueError:
                            pass

                    w_attr = _get_attrib(t_child, "Width")
                    hidden_attr = _get_attrib(t_child, "Hidden")
                    for k in range(span + 1):
                        target_col = col_curr + k
                        if w_attr:
                            try:
                                sheet.geometry.set_col_width(
                                    target_col, int(round(float(w_attr) / 0.75))
                                )
                            except ValueError:
                                pass
                        if hidden_attr == "1":
                            sheet.geometry.hidden_cols.add(target_col)

                    col_curr += span

            # Rows & Cells
            row_curr = -1
            for t_child in table_el:
                if _local_name(t_child.tag) != "Row":
                    continue

                idx_attr = _get_attrib(t_child, "Index")
                if idx_attr:
                    try:
                        row_curr = int(idx_attr) - 1
                    except ValueError:
                        row_curr += 1
                else:
                    row_curr += 1

                span = 0
                span_attr = _get_attrib(t_child, "Span")
                if span_attr:
                    try:
                        span = int(span_attr)
                    except ValueError:
                        pass

                h_attr = _get_attrib(t_child, "Height")
                hidden_attr = _get_attrib(t_child, "Hidden")
                for k in range(span + 1):
                    target_row = row_curr + k
                    if h_attr:
                        try:
                            sheet.geometry.set_row_height(
                                target_row, int(round(float(h_attr) / 0.75))
                            )
                        except ValueError:
                            pass
                    if hidden_attr == "1":
                        sheet.geometry.hidden_rows.add(target_row)

                # Cells
                cell_curr = -1
                for cell_el in t_child:
                    if _local_name(cell_el.tag) != "Cell":
                        continue

                    c_idx_attr = _get_attrib(cell_el, "Index")
                    if c_idx_attr:
                        try:
                            cell_curr = int(c_idx_attr) - 1
                        except ValueError:
                            cell_curr += 1
                    else:
                        cell_curr += 1

                    merge_across = 0
                    ma_attr = _get_attrib(cell_el, "MergeAcross")
                    if ma_attr:
                        try:
                            merge_across = int(ma_attr)
                        except ValueError:
                            pass

                    merge_down = 0
                    md_attr = _get_attrib(cell_el, "MergeDown")
                    if md_attr:
                        try:
                            merge_down = int(md_attr)
                        except ValueError:
                            pass

                    if merge_across > 0 or merge_down > 0:
                        sheet.add_merge(
                            row_curr,
                            cell_curr,
                            row_curr + merge_down,
                            cell_curr + merge_across,
                        )

                    style_id = _get_attrib(cell_el, "StyleID")
                    formula = _get_attrib(cell_el, "Formula")

                    # Value
                    val: Any = None
                    for d_el in cell_el:
                        if _local_name(d_el.tag) == "Data":
                            d_type = _get_attrib(d_el, "Type") or "String"
                            raw_text = d_el.text or ""
                            if d_type == "Number":
                                try:
                                    val = int(raw_text) if "." not in raw_text else float(raw_text)
                                except ValueError:
                                    val = raw_text
                            elif d_type == "Boolean":
                                val = raw_text in ("1", "true", "True")
                            elif d_type == "DateTime":
                                # ISO 8601 string
                                m = re.match(
                                    r"^(\d{4})-(\d\d)-(\d\d)(?:T(\d\d):(\d\d)(?::(\d\d(?:\.\d+)?))?)?",
                                    raw_text,
                                )
                                if m:
                                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                                    hh = int(m.group(4) or 0)
                                    mm = int(m.group(5) or 0)
                                    ss = float(m.group(6) or 0)
                                    s_val = date_to_serial(y, mo, d)
                                    if not isinstance(s_val, ExcelError):
                                        fraction = (hh * 3600 + mm * 60 + ss) / 86400.0
                                        val = s_val + fraction
                                    else:
                                        val = raw_text
                                else:
                                    val = raw_text
                            elif d_type == "Error":
                                val = ExcelError(raw_text)
                            else:
                                val = raw_text
                            break

                    # Comment
                    for cm_el in cell_el:
                        if _local_name(cm_el.tag) == "Comment":
                            author = _get_attrib(cm_el, "Author") or ""
                            visible = _get_attrib(cm_el, "ShowAlways") == "1"
                            cm_text = ""
                            for cm_child in cm_el:
                                if _local_name(cm_child.tag) in ("Data", "ss:Data"):
                                    cm_text = (cm_child.text or "").strip()
                                    break
                            if not cm_text and cm_el.text:
                                cm_text = cm_el.text.strip()
                            sheet.set_comment(row_curr, cell_curr, cm_text, author, visible)

                    a1_formula = from_r1c1(formula, row_curr, cell_curr) if formula else None

                    # Apply style and create cell
                    cell = CellData(value=val, formula=a1_formula)
                    if style_id and style_id in styles:
                        st = styles[style_id]
                        for prop_name, prop_val in st.items():
                            if hasattr(cell, prop_name):
                                setattr(cell, prop_name, prop_val)

                    sheet.set_cell(row_curr, cell_curr, cell)
                    cell_curr += merge_across

                row_curr += span

        parsed_sheets.append(sheet)
        sheet_idx += 1

    if not parsed_sheets:
        parsed_sheets.append(SheetDataModel(name="Sheet1"))

    # Clamp active_sheet_index
    if active_sheet_index < 0 or active_sheet_index >= len(parsed_sheets):
        active_sheet_index = 0

    # Build WorkbookModel
    wb = WorkbookModel(sheets=parsed_sheets)
    wb.set_active_sheet_index(active_sheet_index)

    if isinstance(model, WorkbookModel):
        # Populate existing WorkbookModel
        while len(model._sheets) > 1:
            model.remove_sheet(len(model._sheets) - 1)
        # Rename or replace first sheet
        model._sheets = list(parsed_sheets)
        model.set_active_sheet_index(active_sheet_index)
        return model

    if isinstance(model, SheetDataModel):
        # Populate existing SheetDataModel from active sheet
        source_sheet = parsed_sheets[active_sheet_index]
        model.name = source_sheet.name
        model.cells = dict(source_sheet.cells)
        model.merges = list(source_sheet.merges)
        model.geometry = source_sheet.geometry
        model.comments = dict(source_sheet.comments)
        model.freeze_rows = source_sheet.freeze_rows
        model.freeze_cols = source_sheet.freeze_cols
        model.extra["workbook"] = wb
        return model

    if return_workbook:
        return wb

    res_sheet = wb.active_sheet
    res_sheet.extra["workbook"] = wb
    return res_sheet


def read_xmlss_workbook(content: str | bytes) -> WorkbookModel:
    """Convenience helper to read XMLSS directly into a WorkbookModel."""
    wb = read_xmlss(content, return_workbook=True)
    if isinstance(wb, WorkbookModel):
        return wb
    return WorkbookModel(sheets=[wb])


def write_xmlss(
    model: SheetDataModel | WorkbookModel,
    sheet_name: str = "Sheet1",
) -> str:
    """Serialize a SheetDataModel or WorkbookModel to XML Spreadsheet 2003 XML string."""
    if isinstance(model, WorkbookModel):
        sheets = model.sheets
        active_idx = model.active_sheet_index
    else:
        sheets = [model]
        active_idx = 0

    out: list[str] = [
        '<?xml version="1.0"?>',
        '<?mso-application progid="Excel.Sheet"?>',
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:o="urn:schemas-microsoft-com:office:office"',
        ' xmlns:x="urn:schemas-microsoft-com:office:excel"',
        ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:html="http://www.w3.org/TR/REC-html40">',
    ]

    # Collect unique styles across all sheets
    style_map: dict[tuple[Any, ...], str] = {}
    style_defs: list[str] = [
        '  <Style ss:ID="Default" ss:Name="Normal">',
        '   <Alignment ss:Vertical="Bottom"/>',
        '   <Font ss:FontName="Arial" ss:Size="10"/>',
        "  </Style>",
    ]

    for sh in sheets:
        for cell in sh.cells.values():
            bt = (cell.border_top.style, cell.border_top.color) if cell.border_top else None
            bb = (
                (cell.border_bottom.style, cell.border_bottom.color) if cell.border_bottom else None
            )
            bl = (cell.border_left.style, cell.border_left.color) if cell.border_left else None
            br = (cell.border_right.style, cell.border_right.color) if cell.border_right else None
            key = (
                cell.bold,
                cell.italic,
                cell.underline,
                cell.underline_style,
                cell.strike,
                cell.vert_align,
                cell.font_size,
                cell.font_family,
                cell.fg_color,
                cell.bg_color,
                cell.pattern,
                cell.pattern_color,
                cell.align_h,
                cell.align_v,
                cell.wrap_text,
                cell.shrink_to_fit,
                cell.indent,
                cell.text_rotation,
                cell.format_code,
                bt,
                bb,
                bl,
                br,
            )
            if key not in style_map:
                sid = f"s{len(style_map) + 21}"
                style_map[key] = sid

                s_xml = [f'  <Style ss:ID="{sid}">']

                # Alignment
                align_attrs = []
                if cell.align_h and cell.align_h != "general":
                    align_attrs.append(f'ss:Horizontal="{cell.align_h.capitalize()}"')
                if cell.align_v and cell.align_v != "bottom":
                    align_attrs.append(f'ss:Vertical="{cell.align_v.capitalize()}"')
                if cell.wrap_text:
                    align_attrs.append('ss:WrapText="1"')
                if cell.shrink_to_fit:
                    align_attrs.append('ss:ShrinkToFit="1"')
                if cell.indent:
                    align_attrs.append(f'ss:Indent="{cell.indent}"')
                if cell.text_rotation:
                    align_attrs.append(f'ss:Rotate="{cell.text_rotation}"')
                if align_attrs:
                    s_xml.append(f"   <Alignment {' '.join(align_attrs)}/>")

                # Borders
                if any((cell.border_top, cell.border_bottom, cell.border_left, cell.border_right)):
                    s_xml.append("   <Borders>")
                    for pos, b in (
                        ("Top", cell.border_top),
                        ("Bottom", cell.border_bottom),
                        ("Left", cell.border_left),
                        ("Right", cell.border_right),
                    ):
                        if b:
                            line_style = "Continuous"
                            weight = 1
                            if b.style == "thick":
                                weight = 3
                            elif b.style == "medium":
                                weight = 2
                            elif b.style == "double":
                                line_style = "Double"
                                weight = 3
                            elif b.style in ("dashed", "dash"):
                                line_style = "Dash"
                            elif b.style in ("dotted", "dot"):
                                line_style = "Dot"
                            elif b.style == "hair":
                                weight = 0

                            col_str = f' ss:Color="{b.color}"' if b.color else ""
                            b_tag = (
                                f'    <Border ss:Position="{pos}" ss:LineStyle="{line_style}" '
                                f'ss:Weight="{weight}"{col_str}/>'
                            )
                            s_xml.append(b_tag)
                    s_xml.append("   </Borders>")

                # Font
                font_attrs = [f'ss:FontName="{cell.font_family}"']
                if cell.font_size != 10:
                    font_attrs.append(f'ss:Size="{cell.font_size}"')
                if cell.bold:
                    font_attrs.append('ss:Bold="1"')
                if cell.italic:
                    font_attrs.append('ss:Italic="1"')
                if cell.underline:
                    u_map = {
                        "double": "Double",
                        "singleaccounting": "SingleAccounting",
                        "doubleaccounting": "DoubleAccounting",
                    }
                    u_val = u_map.get(cell.underline_style.lower(), "Single")
                    font_attrs.append(f'ss:Underline="{u_val}"')
                if cell.strike:
                    font_attrs.append('ss:StrikeThrough="1"')
                if cell.vert_align:
                    va_val = (
                        "Superscript" if cell.vert_align.lower() == "superscript" else "Subscript"
                    )
                    font_attrs.append(f'ss:VerticalAlign="{va_val}"')
                if cell.fg_color:
                    font_attrs.append(f'ss:Color="{cell.fg_color}"')
                s_xml.append(f"   <Font {' '.join(font_attrs)}/>")

                # Interior
                if cell.bg_color or cell.pattern:
                    int_attrs = []
                    if cell.bg_color:
                        int_attrs.append(f'ss:Color="{cell.bg_color}"')
                    pat = cell.pattern or "Solid"
                    int_attrs.append(f'ss:Pattern="{pat}"')
                    if cell.pattern_color:
                        int_attrs.append(f'ss:PatternColor="{cell.pattern_color}"')
                    s_xml.append(f"   <Interior {' '.join(int_attrs)}/>")

                # NumberFormat
                if cell.format_code and cell.format_code != "General":
                    s_xml.append(f'   <NumberFormat ss:Format="{html.escape(cell.format_code)}"/>')

                s_xml.append("  </Style>")
                style_defs.append("\n".join(s_xml))

    out.append(" <Styles>")
    out.extend(style_defs)
    out.append(" </Styles>")

    # ExcelWorkbook active sheet
    out.append(' <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">')
    out.append(f"  <ActiveSheet>{active_idx}</ActiveSheet>")
    out.append(" </ExcelWorkbook>")

    # Worksheets
    for idx, sh in enumerate(sheets):
        curr_sheet_name = sh.name if isinstance(model, WorkbookModel) else sheet_name
        safe_sheet_name = html.escape(curr_sheet_name)
        out.append(f' <Worksheet ss:Name="{safe_sheet_name}">')

        # Geometry defaults
        def_w_pt = sh.geometry.default_col_width * 0.75
        def_h_pt = sh.geometry.default_row_height * 0.75
        out.append(
            f'  <Table ss:DefaultColumnWidth="{def_w_pt:.2f}" ss:DefaultRowHeight="{def_h_pt:.2f}">'
        )

        # Custom Columns
        special_cols = sorted(
            list(set(sh.geometry.custom_col_widths.keys()) | sh.geometry.hidden_cols)
        )
        for c in special_cols:
            col_attrs = [f'ss:Index="{c + 1}"']
            if c in sh.geometry.custom_col_widths:
                w_pt = sh.geometry.custom_col_widths[c] * 0.75
                col_attrs.append(f'ss:Width="{w_pt:.2f}"')
            if c in sh.geometry.hidden_cols:
                col_attrs.append('ss:Hidden="1"')
            out.append(f"   <Column {' '.join(col_attrs)}/>")

        # Merges
        merges_by_origin: dict[tuple[int, int], tuple[int, int]] = {}
        covered_cells: set[tuple[int, int]] = set()
        for r1, c1, r2, c2 in sh.merges:
            merges_by_origin[(r1, c1)] = (r2 - r1, c2 - c1)
            for mr in range(r1, r2 + 1):
                for mc in range(c1, c2 + 1):
                    if mr != r1 or mc != c1:
                        covered_cells.add((mr, mc))

        # Rows
        active_rows = sorted(
            list(
                set(r for r, _ in sh.cells.keys())
                | set(sh.geometry.custom_row_heights.keys())
                | sh.geometry.hidden_rows
            )
        )
        last_r = -1

        for r in active_rows:
            row_attrs = []
            if r != last_r + 1:
                row_attrs.append(f'ss:Index="{r + 1}"')
            last_r = r

            if r in sh.geometry.custom_row_heights:
                h_pt = sh.geometry.custom_row_heights[r] * 0.75
                row_attrs.append(f'ss:Height="{h_pt:.2f}"')
            if r in sh.geometry.hidden_rows:
                row_attrs.append('ss:Hidden="1"')

            attr_str = (" " + " ".join(row_attrs)) if row_attrs else ""
            out.append(f"   <Row{attr_str}>")

            row_cells = sorted(
                [c for r_c, c in sh.cells.keys() if r_c == r and (r, c) not in covered_cells]
            )
            last_c = -1

            for c in row_cells:
                cell = sh.get_cell(r, c)
                if cell is None:
                    continue

                cell_attrs = []
                if c != last_c + 1:
                    cell_attrs.append(f'ss:Index="{c + 1}"')

                if (r, c) in merges_by_origin:
                    md, ma = merges_by_origin[(r, c)]
                    if ma > 0:
                        cell_attrs.append(f'ss:MergeAcross="{ma}"')
                    if md > 0:
                        cell_attrs.append(f'ss:MergeDown="{md}"')
                    last_c = c + ma
                else:
                    last_c = c

                bt = (cell.border_top.style, cell.border_top.color) if cell.border_top else None
                bb = (
                    (cell.border_bottom.style, cell.border_bottom.color)
                    if cell.border_bottom
                    else None
                )
                bl = (cell.border_left.style, cell.border_left.color) if cell.border_left else None
                br = (
                    (cell.border_right.style, cell.border_right.color)
                    if cell.border_right
                    else None
                )
                key = (
                    cell.bold,
                    cell.italic,
                    cell.underline,
                    cell.underline_style,
                    cell.strike,
                    cell.vert_align,
                    cell.font_size,
                    cell.font_family,
                    cell.fg_color,
                    cell.bg_color,
                    cell.pattern,
                    cell.pattern_color,
                    cell.align_h,
                    cell.align_v,
                    cell.wrap_text,
                    cell.shrink_to_fit,
                    cell.indent,
                    cell.text_rotation,
                    cell.format_code,
                    bt,
                    bb,
                    bl,
                    br,
                )
                if key in style_map:
                    cell_attrs.append(f'ss:StyleID="{style_map[key]}"')

                if cell.formula:
                    r1c1_f = to_r1c1(cell.formula, r, c)
                    cell_attrs.append(f'ss:Formula="{html.escape(r1c1_f)}"')

                cell_attr_str = (" " + " ".join(cell_attrs)) if cell_attrs else ""

                # Data block
                data_str = ""
                if cell.value is not None:
                    val = cell.value
                    if isinstance(val, bool):
                        d_type = "Boolean"
                        d_val = "1" if val else "0"
                    elif isinstance(val, (int, float)):
                        d_type = "Number"
                        d_val = str(val)
                    elif isinstance(val, (datetime.datetime, datetime.date)):
                        d_type = "DateTime"
                        if isinstance(val, datetime.datetime):
                            d_val = val.strftime("%Y-%m-%dT%H:%M:%S.000")
                        else:
                            d_val = f"{val.isoformat()}T00:00:00.000"
                    elif isinstance(val, ExcelError) or (
                        isinstance(val, str)
                        and (val in [str(e) for e in ALL_ERRORS] or val.startswith("#"))
                    ):
                        d_type = "Error"
                        d_val = html.escape(str(val))
                    else:
                        d_type = "String"
                        d_val = html.escape(str(val))

                    data_str = f'<Data ss:Type="{d_type}">{d_val}</Data>'

                # Comment block
                cm = sh.get_comment(r, c)
                comment_str = ""
                if cm:
                    auth_attr = f' ss:Author="{html.escape(cm.author)}"' if cm.author else ""
                    show_attr = ' ss:ShowAlways="1"' if cm.visible else ""
                    esc_cm = html.escape(cm.text)
                    comment_str = f"<Comment{auth_attr}{show_attr}><Data>{esc_cm}</Data></Comment>"

                if data_str or comment_str:
                    out.append(f"    <Cell{cell_attr_str}>{data_str}{comment_str}</Cell>")
                else:
                    out.append(f"    <Cell{cell_attr_str}/>")

            out.append("   </Row>")

        out.append("  </Table>")

        # WorksheetOptions
        opt_parts = []
        if idx == active_idx:
            opt_parts.append("   <Selected/>")
        if sh.freeze_rows > 0:
            opt_parts.append(f"   <SplitHorizontal>{sh.freeze_rows}</SplitHorizontal>")
        if sh.freeze_cols > 0:
            opt_parts.append(f"   <SplitVertical>{sh.freeze_cols}</SplitVertical>")
        if sh.freeze_rows > 0 or sh.freeze_cols > 0:
            opt_parts.append("   <FreezePanes/>")

        if opt_parts:
            out.append('  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">')
            out.extend(opt_parts)
            out.append("  </WorksheetOptions>")

        out.append(" </Worksheet>")

    out.append("</Workbook>")
    return "\n".join(out)
