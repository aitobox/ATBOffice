"""XML Spreadsheet 2003 (SpreadsheetML) reader and writer for ATBOffice Ledger."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Any

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

    r1c1_re = re.compile(
        r"^(?:[Rr](\[-?\d+\]|\d+)?)?(?:[Cc](\[-?\d+\]|\d+)?)?"
    )

    while i < n:
        ch = s[i]
        # Preserve string literals
        if ch == '"':
            end_idx = s.find('"', i + 1)
            while end_idx != -1 and end_idx + 1 < n and s[end_idx + 1] == '"':
                end_idx = s.find('"', end_idx + 2)
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

    def a1_to_rc(col_str: str, row_str: str) -> str:
        ca = col_str.startswith("$")
        c_idx = col_index(col_str.lstrip("$"))
        ra = row_str.startswith("$")
        r_idx = int(row_str.lstrip("$")) - 1

        if ra:
            r_part = f"R{r_idx + 1}"
        elif r_idx == r:
            r_part = "R"
        else:
            r_part = f"R[{r_idx - r}]"

        if ca:
            c_part = f"C{c_idx + 1}"
        elif c_idx == c:
            c_part = "C"
        else:
            c_part = f"C[{c_idx - c}]"

        return r_part + c_part

    # Replace ranges: e.g. A1:B5
    def replace_range(m: re.Match[str]) -> str:
        c1, r1, c2, r2 = m.group(1), m.group(2), m.group(3), m.group(4)
        return f"{a1_to_rc(c1, r1)}:{a1_to_rc(c2, r2)}"

    def replace_cell(m: re.Match[str]) -> str:
        c1, r1 = m.group(1), m.group(2)
        return a1_to_rc(c1, r1)

    # Tokenize preserving strings
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

    out_parts: list[str] = []
    for tok in tokens:
        if tok.startswith('"'):
            out_parts.append(tok)
            continue

        # Area range pattern: e.g. $A$1:$B$5 or A1:B2
        t = re.sub(
            r"(\$?[A-Za-z]+)(\$?\d+):(\$?[A-Za-z]+)(\$?\d+)",
            replace_range,
            tok,
        )
        # Single cell pattern: e.g. $A$1 or B2
        t = re.sub(r"(?<![A-Za-z0-9_])(\$?[A-Za-z]+)(\$?\d+)", replace_cell, t)
        out_parts.append(t)

    return "=" + "".join(out_parts)


def read_xmlss(
    content: str | bytes, model: SheetDataModel | None = None
) -> SheetDataModel:
    """Parse XML Spreadsheet 2003 content into a SheetDataModel."""
    if isinstance(content, bytes):
        text, _ = decode_bytes(content)
    else:
        text = content

    root = ET.fromstring(text)

    if model is None:
        model = SheetDataModel()

    def local_name(tag: str) -> str:
        return tag.split("}")[-1] if "}" in tag else tag

    # 1. Parse Styles
    styles: dict[str, dict[str, Any]] = {}
    styles_el = None
    for child in root:
        if local_name(child.tag) == "Styles":
            styles_el = child
            break

    if styles_el is not None:
        for st_el in styles_el:
            if local_name(st_el.tag) != "Style":
                continue
            st_id = None
            for k, v in st_el.attrib.items():
                if local_name(k) == "ID":
                    st_id = v
                    break
            if not st_id:
                continue

            style_dict: dict[str, Any] = {}
            for prop in st_el:
                prop_tag = local_name(prop.tag)
                if prop_tag == "Font":
                    for ak, av in prop.attrib.items():
                        aln = local_name(ak)
                        if aln == "Bold" and av in ("1", "true", "True"):
                            style_dict["bold"] = True
                        elif aln == "Italic" and av in ("1", "true", "True"):
                            style_dict["italic"] = True
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
                        aln = local_name(ak)
                        if aln == "Color":
                            style_dict["bg_color"] = av
                        elif aln == "Pattern":
                            style_dict["pattern"] = av
                elif prop_tag == "NumberFormat":
                    for ak, av in prop.attrib.items():
                        if local_name(ak) == "Format":
                            style_dict["format_code"] = av
                elif prop_tag == "Alignment":
                    for ak, av in prop.attrib.items():
                        aln = local_name(ak)
                        if aln == "Horizontal":
                            style_dict["align_h"] = av.lower()
                        elif aln == "Vertical":
                            style_dict["align_v"] = av.lower()
                        elif aln == "WrapText" and av in ("1", "true", "True"):
                            style_dict["wrap_text"] = True

            styles[st_id] = style_dict

    # 2. Parse Worksheet and Table
    worksheet_el = None
    for child in root:
        if local_name(child.tag) == "Worksheet":
            worksheet_el = child
            break

    if worksheet_el is None:
        return model

    table_el = None
    for child in worksheet_el:
        if local_name(child.tag) == "Table":
            table_el = child
            break

    if table_el is None:
        return model

    r_idx = 0
    for row_el in table_el:
        if local_name(row_el.tag) != "Row":
            continue

        for k, v in row_el.attrib.items():
            if local_name(k) == "Index":
                try:
                    r_idx = int(v) - 1
                except ValueError:
                    pass
                break

        c_idx = 0
        for cell_el in row_el:
            if local_name(cell_el.tag) != "Cell":
                continue

            merge_across = 0
            merge_down = 0
            style_id = None
            formula = None

            for k, v in cell_el.attrib.items():
                ln = local_name(k)
                if ln == "Index":
                    try:
                        c_idx = int(v) - 1
                    except ValueError:
                        pass
                elif ln == "MergeAcross":
                    try:
                        merge_across = int(v)
                    except ValueError:
                        pass
                elif ln == "MergeDown":
                    try:
                        merge_down = int(v)
                    except ValueError:
                        pass
                elif ln == "StyleID":
                    style_id = v
                elif ln == "Formula":
                    formula = v

            if merge_across > 0 or merge_down > 0:
                model.add_merge(
                    r_idx, c_idx, r_idx + merge_down, c_idx + merge_across
                )

            # Cell Value & Formula
            val = None
            for d_el in cell_el:
                if local_name(d_el.tag) == "Data":
                    d_type = "String"
                    for dk, dv in d_el.attrib.items():
                        if local_name(dk) == "Type":
                            d_type = dv
                            break
                    raw_text = d_el.text or ""
                    if d_type == "Number":
                        try:
                            val = (
                                int(raw_text)
                                if "." not in raw_text
                                else float(raw_text)
                            )
                        except ValueError:
                            val = raw_text
                    elif d_type == "Boolean":
                        val = raw_text in ("1", "true", "True")
                    else:
                        val = raw_text
                    break

            a1_formula = from_r1c1(formula, r_idx, c_idx) if formula else None

            # Apply style and create cell
            cell = CellData(value=val, formula=a1_formula)
            if style_id and style_id in styles:
                st = styles[style_id]
                for prop_name, prop_val in st.items():
                    if hasattr(cell, prop_name):
                        setattr(cell, prop_name, prop_val)

            model.set_cell(r_idx, c_idx, cell)
            c_idx += 1 + merge_across

        r_idx += 1

    return model


def write_xmlss(model: SheetDataModel, sheet_name: str = "Sheet1") -> str:
    """Serialize a SheetDataModel to XML Spreadsheet 2003 XML string."""
    out: list[str] = [
        '<?xml version="1.0"?>',
        '<?mso-application progid="Excel.Sheet"?>',
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:o="urn:schemas-microsoft-com:office:office"',
        ' xmlns:x="urn:schemas-microsoft-com:office:excel"',
        ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:html="http://www.w3.org/TR/REC-html40">',
    ]

    # Collect unique styles
    style_map: dict[tuple[Any, ...], str] = {}
    style_defs: list[str] = [
        '  <Style ss:ID="Default" ss:Name="Normal">',
        '   <Alignment ss:Vertical="Bottom"/>',
        '   <Font ss:FontName="Arial" ss:Size="10"/>',
        "  </Style>",
    ]

    for cell in model.cells.values():
        key = (
            cell.bold,
            cell.italic,
            cell.font_size,
            cell.font_family,
            cell.fg_color,
            cell.bg_color,
            cell.align_h,
            cell.align_v,
            cell.wrap_text,
            cell.format_code,
        )
        if (
            key
            != (
                False,
                False,
                10,
                "Arial",
                None,
                None,
                "general",
                "bottom",
                False,
                "General",
            )
            and key not in style_map
        ):
            sid = f"s{len(style_map) + 21}"
            style_map[key] = sid

            s_xml = [f'  <Style ss:ID="{sid}">']
            font_attrs = [f'ss:FontName="{cell.font_family}"']
            if cell.font_size != 10:
                font_attrs.append(f'ss:Size="{cell.font_size}"')
            if cell.bold:
                font_attrs.append('ss:Bold="1"')
            if cell.italic:
                font_attrs.append('ss:Italic="1"')
            if cell.fg_color:
                font_attrs.append(f'ss:Color="{cell.fg_color}"')
            s_xml.append(f"   <Font {' '.join(font_attrs)}/>")

            if cell.bg_color:
                s_xml.append(
                    f'   <Interior ss:Color="{cell.bg_color}" ss:Pattern="Solid"/>'
                )
            if cell.format_code and cell.format_code != "General":
                s_xml.append(
                    f'   <NumberFormat ss:Format="{html.escape(cell.format_code)}"/>'
                )
            align_attrs = []
            if cell.align_h and cell.align_h != "general":
                align_attrs.append(
                    f'ss:Horizontal="{cell.align_h.capitalize()}"'
                )
            if cell.align_v and cell.align_v != "bottom":
                align_attrs.append(f'ss:Vertical="{cell.align_v.capitalize()}"')
            if cell.wrap_text:
                align_attrs.append('ss:WrapText="1"')
            if align_attrs:
                s_xml.append(f"   <Alignment {' '.join(align_attrs)}/>")
            s_xml.append("  </Style>")
            style_defs.append("\n".join(s_xml))

    out.append(" <Styles>")
    out.extend(style_defs)
    out.append(" </Styles>")

    # Worksheet & Table
    safe_sheet_name = html.escape(sheet_name)
    out.append(f' <Worksheet ss:Name="{safe_sheet_name}">')
    out.append("  <Table>")

    # Compute merges map and covered cells
    merges_by_origin: dict[tuple[int, int], tuple[int, int]] = {}
    covered_cells: set[tuple[int, int]] = set()

    for r1, c1, r2, c2 in model.merges:
        merges_by_origin[(r1, c1)] = (r2 - r1, c2 - c1)
        for mr in range(r1, r2 + 1):
            for mc in range(c1, c2 + 1):
                if mr != r1 or mc != c1:
                    covered_cells.add((mr, mc))

    active_rows = sorted(list(set(r for r, _ in model.cells.keys())))
    last_r = -1

    for r in active_rows:
        row_attrs = []
        if r != last_r + 1:
            row_attrs.append(f'ss:Index="{r + 1}"')
        last_r = r

        attr_str = (" " + " ".join(row_attrs)) if row_attrs else ""
        out.append(f"   <Row{attr_str}>")

        row_cells = sorted(
            [c for r_c, c in model.cells.keys() if r_c == r and (r, c) not in covered_cells]
        )
        last_c = -1

        for c in row_cells:
            cell = model.get_cell(r, c)
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

            key = (
                cell.bold,
                cell.italic,
                cell.font_size,
                cell.font_family,
                cell.fg_color,
                cell.bg_color,
                cell.align_h,
                cell.align_v,
                cell.wrap_text,
                cell.format_code,
            )
            if key in style_map:
                cell_attrs.append(f'ss:StyleID="{style_map[key]}"')

            if cell.formula:
                r1c1_f = to_r1c1(cell.formula, r, c)
                cell_attrs.append(f'ss:Formula="{html.escape(r1c1_f)}"')

            cell_attr_str = (" " + " ".join(cell_attrs)) if cell_attrs else ""

            if cell.value is not None:
                val = cell.value
                if isinstance(val, bool):
                    d_type = "Boolean"
                    d_val = "1" if val else "0"
                elif isinstance(val, (int, float)):
                    d_type = "Number"
                    d_val = str(val)
                else:
                    d_type = "String"
                    d_val = html.escape(str(val))

                out.append(
                    f'    <Cell{cell_attr_str}><Data ss:Type="{d_type}">{d_val}</Data></Cell>'
                )
            else:
                out.append(f"    <Cell{cell_attr_str}/>")

        out.append("   </Row>")

    out.append("  </Table>")
    out.append(" </Worksheet>")
    out.append("</Workbook>")

    return "\n".join(out)
