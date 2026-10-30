"""Pure Python Open Packaging Conventions (OPC) XLSX writer for ATBOffice Ledger."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from atboffice.modules.spreadsheet.calc.references import cell_name
from atboffice.modules.spreadsheet.io.xlsx_reader import BUILTIN_NUMFMTS
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.vfs.opc import PackageWriter, SourcePackage

XML_HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_CORE = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
NS_DC = "http://purl.org/dc/elements/1.1/"
NS_DCTERMS = "http://purl.org/dc/terms/"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_EXT_PROPS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
NS_VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"

CT_WORKBOOK = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
CT_WORKSHEET = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
CT_STYLES = "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"
CT_SHARED_STRINGS = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"
)
CT_THEME = "application/vnd.openxmlformats-officedocument.theme+xml"
CT_CORE_PROPS = "application/vnd.openxmlformats-package.core-properties+xml"
CT_APP_PROPS = "application/vnd.openxmlformats-officedocument.extended-properties+xml"
CT_RELATIONSHIPS = "application/vnd.openxmlformats-package.relationships+xml"
CT_DRAWING = "application/vnd.openxmlformats-officedocument.drawing+xml"

REL_OFFICE_DOC = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
REL_WORKSHEET = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
)
REL_STYLES = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
)
REL_SHARED_STRINGS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"
)
REL_THEME = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
)
REL_CORE_PROPS = (
    "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"
)
REL_APP_PROPS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"
)
REL_DRAWING = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
)
REL_IMAGE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
)

RE_UNSAFE_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
BUILTIN_CODE_TO_ID: dict[str, int] = {v: k for k, v in BUILTIN_NUMFMTS.items()}


def _xml_escape(s: str) -> str:
    """Escape XML characters: &, <, >, \", '."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _clean_text(s: str) -> str:
    """Replace control characters not permitted in standard XML."""
    return RE_UNSAFE_XML.sub(lambda m: f"_x{ord(m.group(0)):04X}_", s)


def _text_element(s: str, tag: str = "t") -> str:
    """Format a text node preserving whitespace if necessary."""
    clean = _clean_text(str(s))
    escaped = _xml_escape(clean)
    if clean and (
        clean[0].isspace() or clean[-1].isspace() or "\n" in clean or "\r" in clean
    ):
        return f'<{tag} xml:space="preserve">{escaped}</{tag}>'
    return f"<{tag}>{escaped}</{tag}>"


def _color_hex(c: str | None) -> str | None:
    """Normalize color to 8-character ARGB uppercase hex string."""
    if not c:
        return None
    val = str(c).strip().lstrip("#").upper()
    if len(val) == 6:
        return "FF" + val
    if len(val) == 8:
        return val
    return None


class SharedStringsManager:
    """Manages unique shared strings for xl/sharedStrings.xml."""

    def __init__(self) -> None:
        self.strings: list[str] = []
        self.index_map: dict[str, int] = {}
        self.total_count: int = 0

    def add(self, s: str) -> int:
        self.total_count += 1
        idx = self.index_map.get(s)
        if idx is not None:
            return idx
        idx = len(self.strings)
        self.strings.append(s)
        self.index_map[s] = idx
        return idx

    def to_xml(self) -> bytes:
        if not self.strings:
            return b""
        parts = [
            XML_HEADER,
            f'<sst xmlns="{NS_MAIN}" count="{self.total_count}" uniqueCount="{len(self.strings)}">',
        ]
        for s in self.strings:
            truncated = s[:32767] if len(s) > 32767 else s
            parts.append(f"<si>{_text_element(truncated)}</si>")
        parts.append("</sst>")
        return "".join(parts).encode("utf-8")


class StyleManager:
    """Manages styles and generates xl/styles.xml."""

    def __init__(self) -> None:
        self.fonts: list[str] = []
        self.font_map: dict[tuple[Any, ...], int] = {}

        self.fills: list[str] = []
        self.fill_map: dict[tuple[Any, ...], int] = {}

        self.borders: list[str] = []
        self.border_map: dict[tuple[Any, ...], int] = {}

        self.num_fmts: list[tuple[int, str]] = []
        self.num_fmt_map: dict[str, int] = {}
        self._next_num_fmt_id = 164

        # Baseline styles per ECMA-376:
        # Font 0: default font
        self._get_or_add_font("Arial", 10, False, False, False, False, None)

        # Fill 0: none, Fill 1: gray125
        self.fills.append('<fill><patternFill patternType="none"/></fill>')
        self.fills.append('<fill><patternFill patternType="gray125"/></fill>')

        # Border 0: empty
        self.borders.append('<border><left/><right/><top/><bottom/><diagonal/></border>')

        # CellXfs
        self.cell_xfs: list[dict[str, Any]] = []
        self.cell_xf_map: dict[tuple[Any, ...], int] = {}
        self.dxfs: list[dict[str, Any]] = []

        # Default normal cellXf at index 0
        self.cell_xfs.append(
            {
                "numFmtId": 0,
                "fontId": 0,
                "fillId": 0,
                "borderId": 0,
                "align": None,
            }
        )
        self.cell_xf_map[(0, 0, 0, 0, None)] = 0

    def _get_or_add_font(
        self,
        name: str,
        sz: int,
        bold: bool,
        italic: bool,
        underline: bool,
        strike: bool,
        color: str | None,
    ) -> int:
        c_hex = _color_hex(color)
        key = (
            name or "Arial",
            sz or 10,
            bool(bold),
            bool(italic),
            bool(underline),
            bool(strike),
            c_hex,
        )
        if key in self.font_map:
            return self.font_map[key]

        parts = []
        if bold:
            parts.append("<b/>")
        if italic:
            parts.append("<i/>")
        if strike:
            parts.append("<strike/>")
        if underline:
            parts.append('<u val="single"/>')
        parts.append(f'<sz val="{sz or 10}"/>')
        if c_hex:
            parts.append(f'<color rgb="{c_hex}"/>')
        parts.append(f'<name val="{_xml_escape(name or "Arial")}"/>')
        parts.append('<family val="2"/>')

        xml = f"<font>{''.join(parts)}</font>"
        idx = len(self.fonts)
        self.fonts.append(xml)
        self.font_map[key] = idx
        return idx

    def _get_or_add_fill(
        self, bg_color: str | None, pattern: str | None = None
    ) -> int:
        if not bg_color and (not pattern or pattern == "none"):
            return 0
        c_hex = _color_hex(bg_color)
        key = (c_hex, pattern or "solid")
        if key in self.fill_map:
            return self.fill_map[key]

        ptype = pattern or "solid"
        if c_hex:
            xml = (
                f'<fill><patternFill patternType="{ptype}">'
                f'<fgColor rgb="{c_hex}"/><bgColor rgb="{c_hex}"/>'
                f"</patternFill></fill>"
            )
        else:
            xml = f'<fill><patternFill patternType="{ptype}"/></fill>'
        idx = len(self.fills)
        self.fills.append(xml)
        self.fill_map[key] = idx
        return idx

    def _border_side_xml(self, tag: str, side: BorderStyle | None) -> str:
        if not side or not side.style or side.style == "none":
            return f"<{tag}/>"
        c_hex = _color_hex(side.color)
        c_xml = f'<color rgb="{c_hex}"/>' if c_hex else ""
        return f'<{tag} style="{_xml_escape(side.style)}">{c_xml}</{tag}>'

    def _get_or_add_border(
        self,
        top: BorderStyle | None,
        bottom: BorderStyle | None,
        left: BorderStyle | None,
        right: BorderStyle | None,
    ) -> int:
        top_k = (top.style, _color_hex(top.color)) if top else None
        bot_k = (bottom.style, _color_hex(bottom.color)) if bottom else None
        left_k = (left.style, _color_hex(left.color)) if left else None
        right_k = (right.style, _color_hex(right.color)) if right else None
        key = (top_k, bot_k, left_k, right_k)
        if not any(key):
            return 0
        if key in self.border_map:
            return self.border_map[key]

        l_xml = self._border_side_xml("left", left)
        r_xml = self._border_side_xml("right", right)
        t_xml = self._border_side_xml("top", top)
        b_xml = self._border_side_xml("bottom", bottom)
        d_xml = "<diagonal/>"

        xml = f"<border>{l_xml}{r_xml}{t_xml}{b_xml}{d_xml}</border>"
        idx = len(self.borders)
        self.borders.append(xml)
        self.border_map[key] = idx
        return idx

    def _get_or_add_num_fmt(self, code: str | None) -> int:
        if not code or code == "General":
            return 0
        if code in BUILTIN_CODE_TO_ID:
            return BUILTIN_CODE_TO_ID[code]
        if code in self.num_fmt_map:
            return self.num_fmt_map[code]
        fid = self._next_num_fmt_id
        self._next_num_fmt_id += 1
        self.num_fmts.append((fid, code))
        self.num_fmt_map[code] = fid
        return fid

    def get_style_index(self, cell: CellData | None) -> int:
        if cell is None:
            return 0

        has_font = bool(
            cell.bold
            or cell.italic
            or cell.underline
            or cell.strike
            or cell.font_size != 10
            or cell.font_family != "Arial"
            or cell.fg_color
        )
        has_fill = bool(cell.bg_color or (cell.pattern and cell.pattern != "none"))
        has_border = bool(
            cell.border_top
            or cell.border_bottom
            or cell.border_left
            or cell.border_right
        )
        has_num_fmt = bool(cell.format_code and cell.format_code != "General")
        has_align = bool(
            (cell.align_h and cell.align_h != "general")
            or (cell.align_v and cell.align_v != "bottom")
            or cell.wrap_text
            or cell.text_rotation
            or cell.shrink_to_fit
            or cell.indent
        )

        if not (has_font or has_fill or has_border or has_num_fmt or has_align):
            return 0

        font_id = (
            self._get_or_add_font(
                cell.font_family,
                cell.font_size,
                cell.bold,
                cell.italic,
                cell.underline,
                cell.strike,
                cell.fg_color,
            )
            if has_font
            else 0
        )
        fill_id = (
            self._get_or_add_fill(cell.bg_color, cell.pattern) if has_fill else 0
        )
        border_id = (
            self._get_or_add_border(
                cell.border_top,
                cell.border_bottom,
                cell.border_left,
                cell.border_right,
            )
            if has_border
            else 0
        )
        num_fmt_id = (
            self._get_or_add_num_fmt(cell.format_code) if has_num_fmt else 0
        )

        align_key = None
        if has_align:
            align_key = (
                cell.align_h if cell.align_h != "general" else None,
                cell.align_v if cell.align_v != "bottom" else None,
                bool(cell.wrap_text),
                bool(cell.shrink_to_fit),
                int(cell.text_rotation or 0),
                int(cell.indent or 0),
            )

        xf_key = (font_id, fill_id, border_id, num_fmt_id, align_key)
        if xf_key in self.cell_xf_map:
            return self.cell_xf_map[xf_key]

        idx = len(self.cell_xfs)
        self.cell_xfs.append(
            {
                "numFmtId": num_fmt_id,
                "fontId": font_id,
                "fillId": fill_id,
                "borderId": border_id,
                "align": align_key,
            }
        )
        self.cell_xf_map[xf_key] = idx
        return idx

    def add_dxf(
        self,
        bg_color: str | None = None,
        fg_color: str | None = None,
        bold: bool | None = None,
        italic: bool | None = None,
    ) -> int:
        """Register differential formatting record for conditional formatting."""
        dxf = {
            "bg_color": bg_color,
            "fg_color": fg_color,
            "bold": bold,
            "italic": italic,
        }
        self.dxfs.append(dxf)
        return len(self.dxfs) - 1

    def to_styles_xml(self) -> bytes:
        parts = [XML_HEADER, f'<styleSheet xmlns="{NS_MAIN}">']

        # 1. numFmts
        if self.num_fmts:
            parts.append(f'<numFmts count="{len(self.num_fmts)}">')
            for fid, code in self.num_fmts:
                parts.append(
                    f'<numFmt numFmtId="{fid}" formatCode="{_xml_escape(code)}"/>'
                )
            parts.append("</numFmts>")

        # 2. fonts
        parts.append(f'<fonts count="{len(self.fonts)}">')
        parts.extend(self.fonts)
        parts.append("</fonts>")

        # 3. fills
        parts.append(f'<fills count="{len(self.fills)}">')
        parts.extend(self.fills)
        parts.append("</fills>")

        # 4. borders
        parts.append(f'<borders count="{len(self.borders)}">')
        parts.extend(self.borders)
        parts.append("</borders>")

        # 5. cellStyleXfs (1 normal default)
        parts.append(
            '<cellStyleXfs count="1">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
            "</cellStyleXfs>"
        )

        # 6. cellXfs
        parts.append(f'<cellXfs count="{len(self.cell_xfs)}">')
        for xf in self.cell_xfs:
            attrs = [
                f'numFmtId="{xf["numFmtId"]}"',
                f'fontId="{xf["fontId"]}"',
                f'fillId="{xf["fillId"]}"',
                f'borderId="{xf["borderId"]}"',
                'xfId="0"',
            ]
            if xf["numFmtId"] != 0:
                attrs.append('applyNumberFormat="1"')
            if xf["fontId"] != 0:
                attrs.append('applyFont="1"')
            if xf["fillId"] != 0:
                attrs.append('applyFill="1"')
            if xf["borderId"] != 0:
                attrs.append('applyBorder="1"')

            align_k = xf["align"]
            align_attrs = []
            if align_k:
                h, v, wrap, shrink, rot, ind = align_k
                if h:
                    align_attrs.append(f'horizontal="{h}"')
                if v:
                    align_attrs.append(f'vertical="{v}"')
                if wrap:
                    align_attrs.append('wrapText="1"')
                if shrink:
                    align_attrs.append('shrinkToFit="1"')
                if rot:
                    align_attrs.append(f'textRotation="{rot}"')
                if ind:
                    align_attrs.append(f'indent="{ind}"')

            if align_attrs:
                attrs.append('applyAlignment="1"')
                parts.append(
                    f'<xf {" ".join(attrs)}><alignment {" ".join(align_attrs)}/></xf>'
                )
            else:
                parts.append(f'<xf {" ".join(attrs)}/>')
        parts.append("</cellXfs>")

        # 7. cellStyles
        parts.append(
            '<cellStyles count="1">'
            '<cellStyle name="Normal" xfId="0" builtinId="0"/>'
            "</cellStyles>"
        )

        # 8. dxfs
        if not self.dxfs:
            parts.append('<dxfs count="0"/>')
        else:
            parts.append(f'<dxfs count="{len(self.dxfs)}">')
            for d in self.dxfs:
                parts.append("<dxf>")
                font_parts = []
                if d.get("bold"):
                    font_parts.append('<b val="1"/>')
                if d.get("italic"):
                    font_parts.append('<i val="1"/>')
                if d.get("fg_color"):
                    c_hex = _color_hex(d["fg_color"])
                    if c_hex:
                        font_parts.append(f'<color rgb="{c_hex}"/>')
                if font_parts:
                    parts.append(f"<font>{''.join(font_parts)}</font>")

                if d.get("bg_color"):
                    c_hex = _color_hex(d["bg_color"])
                    if c_hex:
                        parts.append(
                            f'<fill><patternFill patternType="solid"><fgColor rgb="{c_hex}"/></patternFill></fill>'
                        )
                parts.append("</dxf>")
            parts.append("</dxfs>")

        # 9. tableStyles
        parts.append(
            '<tableStyles count="0" defaultTableStyle="TableStyleMedium2" '
            'defaultPivotStyle="PivotStyleLight16"/>'
        )

        parts.append("</styleSheet>")
        return "".join(parts).encode("utf-8")


def _serialize_worksheet(
    sheet: SheetDataModel,
    style_manager: StyleManager,
    sst_manager: SharedStringsManager,
    is_active: bool,
    drawing_rid: str | None = None,
) -> bytes:
    """Serialize a single worksheet to SpreadsheetML XML."""
    coords = list(sheet.cells.keys())
    for m in sheet.merges:
        coords.append((m[0], m[1]))
        coords.append((m[2], m[3]))

    if coords:
        min_r = min(r for r, _ in coords)
        max_r = max(r for r, _ in coords)
        min_c = min(c for _, c in coords)
        max_c = max(c for _, c in coords)
        dim_ref = f"{cell_name(min_r, min_c)}:{cell_name(max_r, max_c)}"
    else:
        dim_ref = "A1"

    tab_sel_attr = ' tabSelected="1"' if is_active else ""
    parts = [
        XML_HEADER,
        f'<worksheet xmlns="{NS_MAIN}" xmlns:r="{NS_R}">',
        f'<dimension ref="{dim_ref}"/>',
        f"<sheetViews><sheetView workbookViewId=\"0\"{tab_sel_attr}/></sheetViews>",
        '<sheetFormatPr defaultRowHeight="20"/>',
    ]

    # Columns (<cols>)
    if sheet.geometry.custom_col_widths or sheet.geometry.hidden_cols:
        col_indices = sorted(
            set(sheet.geometry.custom_col_widths.keys())
            | set(sheet.geometry.hidden_cols)
        )
        if col_indices:
            parts.append("<cols>")
            for c in col_indices:
                w_px = sheet.geometry.col_size(c)
                w_str = f"{(w_px + 0.1) / 8.0:.2f}"
                c_1 = c + 1
                hidden_attr = (
                    ' hidden="1"' if c in sheet.geometry.hidden_cols else ""
                )
                parts.append(
                    f'<col min="{c_1}" max="{c_1}" width="{w_str}" '
                    f'customWidth="1"{hidden_attr}/>'
                )
            parts.append("</cols>")

    # Rows and cells (<sheetData>)
    parts.append("<sheetData>")
    rows_dict: dict[int, list[tuple[int, CellData]]] = {}
    for (r, c), cell in sheet.cells.items():
        if r not in rows_dict:
            rows_dict[r] = []
        rows_dict[r].append((c, cell))

    all_row_indices = (
        set(rows_dict.keys())
        | set(sheet.geometry.custom_row_heights.keys())
        | set(sheet.geometry.hidden_rows)
    )

    for r in sorted(all_row_indices):
        c_list = sorted(rows_dict.get(r, []), key=lambda x: x[0])
        r_1 = r + 1

        row_attrs = [f'r="{r_1}"']
        if c_list:
            min_c = c_list[0][0] + 1
            max_c = c_list[-1][0] + 1
            row_attrs.append(f'spans="{min_c}:{max_c}"')

        if r in sheet.geometry.custom_row_heights:
            ht_px = sheet.geometry.row_size(r)
            ht_str = f"{(ht_px + 0.1) / 1.33:.2f}"
            row_attrs.append(f'ht="{ht_str}" customHeight="1"')

        if r in sheet.geometry.hidden_rows:
            row_attrs.append('hidden="1"')

        if not c_list:
            parts.append(f'<row {" ".join(row_attrs)}/>')
            continue

        parts.append(f'<row {" ".join(row_attrs)}>')
        for c, cell in c_list:
            c_ref = cell_name(r, c)
            s_idx = style_manager.get_style_index(cell)
            s_attr = f' s="{s_idx}"' if s_idx != 0 else ""

            if cell.formula:
                f_text = cell.formula.lstrip("=")
                f_xml = f"<f>{_xml_escape(f_text)}</f>"
                v_xml = ""
                t_attr = ""
                if cell.value is not None:
                    if isinstance(cell.value, bool):
                        t_attr = ' t="b"'
                        v_xml = f"<v>{1 if cell.value else 0}</v>"
                    elif isinstance(cell.value, (int, float)):
                        v_xml = f"<v>{cell.value}</v>"
                    elif isinstance(cell.value, str):
                        if cell.value.startswith("#"):
                            t_attr = ' t="e"'
                            v_xml = f"<v>{cell.value}</v>"
                        else:
                            t_attr = ' t="str"'
                            v_xml = f"<v>{_xml_escape(cell.value)}</v>"
                parts.append(f'<c r="{c_ref}"{s_attr}{t_attr}>{f_xml}{v_xml}</c>')
            else:
                if cell.value is None:
                    if s_attr:
                        parts.append(f'<c r="{c_ref}"{s_attr}/>')
                elif isinstance(cell.value, bool):
                    parts.append(
                        f'<c r="{c_ref}"{s_attr} t="b"><v>{1 if cell.value else 0}</v></c>'
                    )
                elif isinstance(cell.value, (int, float)):
                    parts.append(
                        f'<c r="{c_ref}"{s_attr}><v>{cell.value}</v></c>'
                    )
                elif isinstance(cell.value, str):
                    if cell.value.startswith("#") and cell.value in (
                        "#NULL!",
                        "#DIV/0!",
                        "#VALUE!",
                        "#REF!",
                        "#NAME?",
                        "#NUM!",
                        "#N/A",
                    ):
                        parts.append(
                            f'<c r="{c_ref}"{s_attr} t="e"><v>{cell.value}</v></c>'
                        )
                    else:
                        sst_id = sst_manager.add(cell.value)
                        parts.append(
                            f'<c r="{c_ref}"{s_attr} t="s"><v>{sst_id}</v></c>'
                        )
                else:
                    sst_id = sst_manager.add(str(cell.value))
                    parts.append(
                        f'<c r="{c_ref}"{s_attr} t="s"><v>{sst_id}</v></c>'
                    )

        parts.append("</row>")

    parts.append("</sheetData>")

    # Merged cells (<mergeCells>)
    if sheet.merges:
        parts.append(f'<mergeCells count="{len(sheet.merges)}">')
        for m in sheet.merges:
            ref = f"{cell_name(m[0], m[1])}:{cell_name(m[2], m[3])}"
            parts.append(f'<mergeCell ref="{ref}"/>')
        parts.append("</mergeCells>")

    # Conditional Formatting (<conditionalFormatting>)
    for cf in getattr(sheet, "conditional_formats", []):
        parts.append(f'<conditionalFormatting sqref="{cf.sqref}">')
        for rule in cf.rules:
            if rule.color_scale:
                parts.append(f'<cfRule type="colorScale" priority="{rule.priority}">')
                parts.append("<colorScale>")
                for cfvo in rule.color_scale.cfvos:
                    v_attr = f' val="{cfvo.val}"' if cfvo.val is not None else ""
                    parts.append(f'<cfvo type="{cfvo.type}"{v_attr}/>')
                for col in rule.color_scale.colors:
                    c_hex = _color_hex(col) or "FFFFFFFF"
                    parts.append(f'<color rgb="{c_hex}"/>')
                parts.append("</colorScale>")
                parts.append("</cfRule>")
            elif rule.data_bar:
                db = rule.data_bar
                parts.append(
                    f'<cfRule type="dataBar" priority="{rule.priority}">'
                    f'<dataBar minLength="{int(db.min_len * 100)}" maxLength="{int(db.max_len * 100)}">'
                )
                for cfvo in db.cfvos:
                    v_attr = f' val="{cfvo.val}"' if cfvo.val is not None else ""
                    parts.append(f'<cfvo type="{cfvo.type}"{v_attr}/>')
                c_hex = _color_hex(db.color) or "FF638EC6"
                parts.append(f'<color rgb="{c_hex}"/>')
                parts.append("</dataBar></cfRule>")
            else:
                dxf_id = style_manager.add_dxf(
                    bg_color=rule.bg_color,
                    fg_color=rule.fg_color,
                    bold=rule.bold,
                    italic=rule.italic,
                )
                r_attrs = [
                    f'type="{rule.type}"',
                    f'priority="{rule.priority}"',
                    f'dxfId="{dxf_id}"',
                ]
                if rule.operator:
                    r_attrs.append(f'operator="{rule.operator}"')
                if rule.stop_if_true:
                    r_attrs.append('stopIfTrue="1"')
                if rule.text:
                    r_attrs.append(f'text="{_xml_escape(rule.text)}"')
                parts.append(f'<cfRule {" ".join(r_attrs)}>')
                for f in rule.formula:
                    parts.append(f"<formula>{_xml_escape(str(f))}</formula>")
                parts.append("</cfRule>")
        parts.append("</conditionalFormatting>")

    # Data Validations (<dataValidations>)
    dvs = getattr(sheet, "data_validations", [])
    if dvs:
        parts.append(f'<dataValidations count="{len(dvs)}">')
        for dv in dvs:
            dv_attrs = [f'type="{dv.type}"']
            if dv.operator:
                dv_attrs.append(f'operator="{dv.operator}"')
            if dv.allow_blank:
                dv_attrs.append('allowBlank="1"')
            if dv.show_dropdown:
                dv_attrs.append('showDropDown="1"')
            if dv.show_input_message:
                dv_attrs.append('showInputMessage="1"')
            if dv.show_error_alert:
                dv_attrs.append('showErrorMessage="1"')
            if dv.error_style:
                dv_attrs.append(f'errorStyle="{dv.error_style}"')
            if dv.input_title:
                dv_attrs.append(f'promptTitle="{_xml_escape(dv.input_title)}"')
            if dv.input_message:
                dv_attrs.append(f'prompt="{_xml_escape(dv.input_message)}"')
            if dv.error_title:
                dv_attrs.append(f'errorTitle="{_xml_escape(dv.error_title)}"')
            if dv.error_message:
                dv_attrs.append(f'error="{_xml_escape(dv.error_message)}"')
            if dv.sqref:
                dv_attrs.append(f'sqref="{dv.sqref}"')
            parts.append(f'<dataValidation {" ".join(dv_attrs)}>')
            if dv.formula1:
                parts.append(f"<formula1>{_xml_escape(str(dv.formula1))}</formula1>")
            if dv.formula2:
                parts.append(f"<formula2>{_xml_escape(str(dv.formula2))}</formula2>")
            parts.append("</dataValidation>")
        parts.append("</dataValidations>")

    # Page margins
    parts.append(
        '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" '
        'header="0.3" footer="0.3"/>'
    )
    if drawing_rid:
        parts.append(f'<drawing r:id="{drawing_rid}"/>')
    parts.append("</worksheet>")

    return "".join(parts).encode("utf-8")


def _serialize_drawings(
    drawings: list[Any],
    image_rids: dict[int, str],
) -> bytes:
    """Serialize sheet drawings into SpreadsheetML DrawingML (xl/drawings/drawingN.xml)."""
    parts = [
        XML_HEADER,
        f'<xdr:wsDr xmlns:xdr="{NS_XDR}" xmlns:a="{NS_A}">',
    ]

    geom_map = {
        "rect": "rect",
        "roundRect": "roundRect",
        "oval": "ellipse",
        "arrow": "rightArrow",
        "line": "line",
        "textbox": "rect",
        "chart": "rect",
    }

    for obj in drawings:
        f_col = obj.from_point.col
        f_col_off = obj.from_point.col_off * 9525
        f_row = obj.from_point.row
        f_row_off = obj.from_point.row_off * 9525

        t_col = obj.to_point.col
        t_col_off = obj.to_point.col_off * 9525
        t_row = obj.to_point.row
        t_row_off = obj.to_point.row_off * 9525

        anchor_type_val = (
            obj.anchor_type.value
            if hasattr(obj.anchor_type, "value")
            else str(obj.anchor_type)
        )

        parts.append(
            f'<xdr:twoCellAnchor editAs="{anchor_type_val}">'
            f"<xdr:from><xdr:col>{f_col}</xdr:col><xdr:colOff>{f_col_off}</xdr:colOff>"
            f"<xdr:row>{f_row}</xdr:row><xdr:rowOff>{f_row_off}</xdr:rowOff></xdr:from>"
            f"<xdr:to><xdr:col>{t_col}</xdr:col><xdr:colOff>{t_col_off}</xdr:colOff>"
            f"<xdr:row>{t_row}</xdr:row><xdr:rowOff>{t_row_off}</xdr:rowOff></xdr:to>"
        )

        name_esc = _xml_escape(obj.name or f"Object {obj.id}")

        if obj.kind == "image" and obj.id in image_rids:
            img_rid = image_rids[obj.id]
            nv_pic_pr = (
                f'<xdr:nvPicPr><xdr:cNvPr id="{obj.id}" name="{name_esc}"/>'
                f"<xdr:cNvPicPr/></xdr:nvPicPr>"
            )
            blip_fill = (
                f"<xdr:blipFill>"
                f'<a:blip xmlns:r="{NS_R}" r:embed="{img_rid}"/>'
                f"<a:stretch><a:fillRect/></a:stretch>"
                f"</xdr:blipFill>"
            )
            parts.append(
                f"<xdr:pic>{nv_pic_pr}{blip_fill}"
                f'<xdr:spPr><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr>'
                f"</xdr:pic>"
            )
        else:
            geom = geom_map.get(obj.kind, "rect")
            is_tb = "1" if obj.kind == "textbox" else "0"

            # Fill
            fill_clean = (
                obj.fill_color.lstrip("#").upper() if obj.fill_color else "4F81BD"
            )
            if len(fill_clean) > 6:
                fill_clean = fill_clean[:6]
            fill_xml = f'<a:solidFill><a:srgbClr val="{fill_clean}"/></a:solidFill>'

            # Line
            line_clean = (
                obj.line_color.lstrip("#").upper() if obj.line_color else "385D8A"
            )
            if len(line_clean) > 6:
                line_clean = line_clean[:6]
            lw_emu = int(max(0.5, getattr(obj, "line_width", 1.0)) * 12700)
            line_xml = (
                f'<a:ln w="{lw_emu}">'
                f'<a:solidFill><a:srgbClr val="{line_clean}"/></a:solidFill>'
                f"</a:ln>"
            )

            # Text body
            tx_body = ""
            if getattr(obj, "text", "") or obj.kind == "textbox":
                txt_clean = (
                    getattr(obj, "text_color", "#000000").lstrip("#").upper()
                )
                if len(txt_clean) > 6:
                    txt_clean = txt_clean[:6]
                p_items = []
                for line in (getattr(obj, "text", "") or "").split("\n"):
                    f_name = _xml_escape(getattr(obj, "font_family", "Calibri"))
                    p_items.append(
                        f"<a:p><a:r>"
                        f'<a:rPr lang="en-US" sz="{getattr(obj, "font_size", 11) * 100}">'
                        f'<a:solidFill><a:srgbClr val="{txt_clean}"/></a:solidFill>'
                        f'<a:latin typeface="{f_name}"/>'
                        f"</a:rPr>"
                        f"<a:t>{_xml_escape(line)}</a:t>"
                        f"</a:r></a:p>"
                    )
                tx_body = (
                    f"<xdr:txBody>"
                    f'<a:bodyPr vertOverflow="clip" horzOverflow="clip"/>'
                    f"<a:lstStyle/>"
                    f'{"".join(p_items)}'
                    f"</xdr:txBody>"
                )

            nv_sp_pr = (
                f'<xdr:nvSpPr><xdr:cNvPr id="{obj.id}" name="{name_esc}"/>'
                f'<xdr:cNvSpPr txBox="{is_tb}"/></xdr:nvSpPr>'
            )
            parts.append(
                f'<xdr:sp macro="" textlink="">'
                f"{nv_sp_pr}"
                f"<xdr:spPr>"
                f'<a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>'
                f"{fill_xml}{line_xml}"
                f"</xdr:spPr>"
                f"{tx_body}"
                f"</xdr:sp>"
            )

        parts.append("<xdr:clientData/></xdr:twoCellAnchor>")

    parts.append("</xdr:wsDr>")
    return "".join(parts).encode("utf-8")


def _serialize_workbook(workbook: WorkbookModel, sheet_rids: list[str]) -> bytes:
    """Serialize xl/workbook.xml."""
    parts = [
        XML_HEADER,
        f'<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_R}">',
        '<fileVersion appName="xl" lastEdited="4" lowestEdited="4" rupBuild="4505"/>',
        '<workbookPr defaultThemeVersion="124226"/>',
        f'<bookViews><workbookView activeTab="{workbook.active_sheet_index}"/></bookViews>',
        "<sheets>",
    ]
    for idx, (sheet, rid) in enumerate(zip(workbook.sheets, sheet_rids)):
        parts.append(
            f'<sheet name="{_xml_escape(sheet.name)}" sheetId="{idx + 1}" r:id="{rid}"/>'
        )
    parts.append("</sheets>")
    parts.append('<calcPr calcId="124519" fullCalcOnLoad="1"/>')
    parts.append("</workbook>")
    return "".join(parts).encode("utf-8")


def _serialize_workbook_rels(sheet_count: int) -> bytes:
    """Serialize xl/_rels/workbook.xml.rels."""
    parts = [
        XML_HEADER,
        f'<Relationships xmlns="{NS_PKG_REL}">',
    ]
    for i in range(1, sheet_count + 1):
        parts.append(
            f'<Relationship Id="rId{i}" Type="{REL_WORKSHEET}" '
            f'Target="worksheets/sheet{i}.xml"/>'
        )
    styles_rid = f"rId{sheet_count + 1}"
    parts.append(
        f'<Relationship Id="{styles_rid}" Type="{REL_STYLES}" Target="styles.xml"/>'
    )
    theme_rid = f"rId{sheet_count + 2}"
    parts.append(
        f'<Relationship Id="{theme_rid}" Type="{REL_THEME}" Target="theme/theme1.xml"/>'
    )
    sst_rid = f"rId{sheet_count + 3}"
    parts.append(
        f'<Relationship Id="{sst_rid}" Type="{REL_SHARED_STRINGS}" '
        f'Target="sharedStrings.xml"/>'
    )
    parts.append("</Relationships>")
    return "".join(parts).encode("utf-8")


def _serialize_root_rels() -> bytes:
    """Serialize _rels/.rels."""
    return (
        f"{XML_HEADER}"
        f'<Relationships xmlns="{NS_PKG_REL}">\n'
        f'  <Relationship Id="rId1" Type="{REL_OFFICE_DOC}" Target="xl/workbook.xml"/>\n'
        f'  <Relationship Id="rId2" Type="{REL_CORE_PROPS}" Target="docProps/core.xml"/>\n'
        f'  <Relationship Id="rId3" Type="{REL_APP_PROPS}" Target="docProps/app.xml"/>\n'
        f"</Relationships>"
    ).encode()


def _serialize_core_props() -> bytes:
    """Serialize docProps/core.xml."""
    now_iso = (
        datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )
    return (
        f"{XML_HEADER}"
        f'<cp:coreProperties xmlns:cp="{NS_CORE}" xmlns:dc="{NS_DC}" '
        f'xmlns:dcterms="{NS_DCTERMS}" xmlns:xsi="{NS_XSI}">\n'
        f"  <dc:creator>ATBOffice Ledger</dc:creator>\n"
        f"  <cp:lastModifiedBy>ATBOffice Ledger</cp:lastModifiedBy>\n"
        f'  <dcterms:created xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:created>\n'
        f'  <dcterms:modified xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:modified>\n'
        f"</cp:coreProperties>"
    ).encode()


def _serialize_app_props(sheet_names: list[str]) -> bytes:
    """Serialize docProps/app.xml."""
    count = len(sheet_names)
    titles = "".join(f"<vt:lpstr>{_xml_escape(name)}</vt:lpstr>" for name in sheet_names)
    return (
        f"{XML_HEADER}"
        f'<Properties xmlns="{NS_EXT_PROPS}" xmlns:vt="{NS_VT}">\n'
        f"  <Application>ATBOffice Ledger</Application>\n"
        f"  <DocSecurity>0</DocSecurity>\n"
        f"  <ScaleCrop>false</ScaleCrop>\n"
        f'  <HeadingPairs><vt:vector size="2" baseType="variant">'
        f"<vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>"
        f"<vt:variant><vt:i4>{count}</vt:i4></vt:variant>"
        f"</vt:vector></HeadingPairs>\n"
        f'  <TitlesOfParts><vt:vector size="{count}" baseType="lpstr">'
        f"{titles}</vt:vector></TitlesOfParts>\n"
        f"  <LinksUpToDate>false</LinksUpToDate>\n"
        f"  <SharedDoc>false</SharedDoc>\n"
        f"  <HyperlinksChanged>false</HyperlinksChanged>\n"
        f"  <AppVersion>12.0000</AppVersion>\n"
        f"</Properties>"
    ).encode()


def _serialize_theme() -> bytes:
    """Serialize standard Office Theme 1 xml."""
    return (
        f"{XML_HEADER}"
        f'<a:theme xmlns:a="{NS_A}" name="Office Theme">\n'
        f'  <a:themeElements>\n'
        f'    <a:clrScheme name="Office">\n'
        f'      <a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>\n'
        f'      <a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>\n'
        f'      <a:dk2><a:srgbClr val="1F497D"/></a:dk2>\n'
        f'      <a:lt2><a:srgbClr val="EEECE1"/></a:lt2>\n'
        f'      <a:accent1><a:srgbClr val="4F81BD"/></a:accent1>\n'
        f'      <a:accent2><a:srgbClr val="C0504D"/></a:accent2>\n'
        f'      <a:accent3><a:srgbClr val="9BBB59"/></a:accent3>\n'
        f'      <a:accent4><a:srgbClr val="8064A2"/></a:accent4>\n'
        f'      <a:accent5><a:srgbClr val="4BACC6"/></a:accent5>\n'
        f'      <a:accent6><a:srgbClr val="F79646"/></a:accent6>\n'
        f'      <a:hlink><a:srgbClr val="0000FF"/></a:hlink>\n'
        f'      <a:folHlink><a:srgbClr val="800080"/></a:folHlink>\n'
        f'    </a:clrScheme>\n'
        f'    <a:fontScheme name="Office">\n'
        f'      <a:majorFont>\n'
        f'        <a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/>\n'
        f'      </a:majorFont>\n'
        f'      <a:minorFont>\n'
        f'        <a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/>\n'
        f'      </a:minorFont>\n'
        f'    </a:fontScheme>\n'
        f'    <a:fmtScheme name="Office">\n'
        f'      <a:fillStyleLst>\n'
        f'        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>\n'
        f'      </a:fillStyleLst>\n'
        f'      <a:lnStyleLst>\n'
        f'        <a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>\n'
        f'      </a:lnStyleLst>\n'
        f'      <a:effectStyleLst>\n'
        f'        <a:effectStyle><a:effectLst/></a:effectStyle>\n'
        f'      </a:effectStyleLst>\n'
        f'      <a:bgFillStyleLst>\n'
        f'        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>\n'
        f'      </a:bgFillStyleLst>\n'
        f'    </a:fmtScheme>\n'
        f'  </a:themeElements>\n'
        f"</a:theme>"
    ).encode()


def write_xlsx(
    workbook: WorkbookModel,
    output_path: str | Path | BinaryIO | None = None,
    source_opc: SourcePackage | bytes | str | Path | None = None,
) -> bytes:
    """Serialize a WorkbookModel to an OOXML .xlsx package.

    Args:
        workbook: WorkbookModel container holding one or more SheetDataModel instances.
        output_path: Target filesystem path (str/Path) or writable BinaryIO stream.
        source_opc: Optional source OPC package (SourcePackage, bytes, or path)
                    for Part-level Carry of unmodified parts.

    Returns:
        Complete serialized XLSX ZIP package as bytes.
    """
    source_pkg: SourcePackage | None = None
    if source_opc is not None:
        if isinstance(source_opc, SourcePackage):
            source_pkg = source_opc
        elif isinstance(source_opc, bytes):
            source_pkg = SourcePackage.from_bytes(source_opc)
        elif isinstance(source_opc, (str, Path)):
            source_pkg = SourcePackage.open(source_opc)

    pkg_writer = PackageWriter(source_package=source_pkg)

    sst_manager = SharedStringsManager()
    style_manager = StyleManager()

    sheet_count = len(workbook)
    sheet_rids = [f"rId{i}" for i in range(1, sheet_count + 1)]

    # 1. Serialize each worksheet and associated drawings
    drawing_count = 0
    media_count = 0
    for i, sheet in enumerate(workbook.sheets, start=1):
        has_drawings = hasattr(sheet, "drawings") and bool(sheet.drawings)
        drawing_rid = "rIdDrawing" if has_drawings else None
        is_active = (i - 1) == workbook.active_sheet_index
        ws_bytes = _serialize_worksheet(
            sheet, style_manager, sst_manager, is_active, drawing_rid=drawing_rid
        )
        part_name = f"xl/worksheets/sheet{i}.xml"
        pkg_writer.add_part(part_name, ws_bytes, CT_WORKSHEET)

        if has_drawings:
            drawing_count += 1
            drawing_part = f"xl/drawings/drawing{drawing_count}.xml"

            # Check image payloads
            image_rids: dict[int, str] = {}
            drawing_rels: list[str] = []
            rel_counter = 1
            for obj in sheet.drawings:
                if obj.kind == "image" and getattr(obj, "image_data", None):
                    media_count += 1
                    ext = "png"
                    mime = getattr(obj, "image_mime", "image/png")
                    if "jpeg" in mime or "jpg" in mime:
                        ext = "jpg"
                    media_part = f"xl/media/image{media_count}.{ext}"
                    pkg_writer.add_part(media_part, obj.image_data, mime)

                    rid = f"rId{rel_counter}"
                    rel_counter += 1
                    image_rids[obj.id] = rid
                    rel_elem = (
                        f'<Relationship Id="{rid}" Type="{REL_IMAGE}" '
                        f'Target="../media/image{media_count}.{ext}"/>'
                    )
                    drawing_rels.append(rel_elem)

            # Add drawing part
            drawing_bytes = _serialize_drawings(sheet.drawings, image_rids)
            pkg_writer.add_part(drawing_part, drawing_bytes, CT_DRAWING)

            # Add drawing rels if any
            if drawing_rels:
                drawing_rels_xml = (
                    f'{XML_HEADER}<Relationships xmlns="{NS_PKG_REL}">'
                    f'{"".join(drawing_rels)}'
                    f"</Relationships>"
                ).encode()
                pkg_writer.add_part(
                    f"xl/drawings/_rels/drawing{drawing_count}.xml.rels",
                    drawing_rels_xml,
                    CT_RELATIONSHIPS,
                )

            # Add sheet rels
            rel_sheet = (
                f'<Relationship Id="{drawing_rid}" Type="{REL_DRAWING}" '
                f'Target="../drawings/drawing{drawing_count}.xml"/>'
            )
            sheet_rels_xml = (
                f'{XML_HEADER}<Relationships xmlns="{NS_PKG_REL}">'
                f"{rel_sheet}"
                f"</Relationships>"
            ).encode()
            pkg_writer.add_part(
                f"xl/worksheets/_rels/sheet{i}.xml.rels",
                sheet_rels_xml,
                CT_RELATIONSHIPS,
            )

    # 2. Serialize sharedStrings.xml if strings were encountered
    sst_bytes = sst_manager.to_xml()
    if sst_bytes:
        pkg_writer.add_part("xl/sharedStrings.xml", sst_bytes, CT_SHARED_STRINGS)

    # 3. Serialize styles.xml
    styles_bytes = style_manager.to_styles_xml()
    pkg_writer.add_part("xl/styles.xml", styles_bytes, CT_STYLES)

    # 4. Serialize workbook.xml and workbook.xml.rels
    wb_bytes = _serialize_workbook(workbook, sheet_rids)
    pkg_writer.add_part("xl/workbook.xml", wb_bytes, CT_WORKBOOK)

    wb_rels_bytes = _serialize_workbook_rels(sheet_count)
    pkg_writer.add_part(
        "xl/_rels/workbook.xml.rels", wb_rels_bytes, CT_RELATIONSHIPS
    )

    # 5. Core package plumbing (if not already carried or needed)
    if not source_pkg or not source_pkg.has_part("xl/theme/theme1.xml"):
        pkg_writer.add_part("xl/theme/theme1.xml", _serialize_theme(), CT_THEME)

    if not source_pkg or not source_pkg.has_part("docProps/core.xml"):
        pkg_writer.add_part(
            "docProps/core.xml", _serialize_core_props(), CT_CORE_PROPS
        )

    sheet_names = [s.name for s in workbook.sheets]
    if not source_pkg or not source_pkg.has_part("docProps/app.xml"):
        pkg_writer.add_part(
            "docProps/app.xml", _serialize_app_props(sheet_names), CT_APP_PROPS
        )

    if not source_pkg or not source_pkg.has_part("_rels/.rels"):
        pkg_writer.add_part("_rels/.rels", _serialize_root_rels(), CT_RELATIONSHIPS)

    # 6. Generate ZIP bytes
    payload = pkg_writer.to_bytes()

    # 7. Write to output if requested
    if output_path is not None:
        if hasattr(output_path, "write"):
            output_path.write(payload)
        else:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            pkg_writer.save(path)

    return payload
