"""Pure Python Open Packaging Conventions (OPC) XLSX writer for ATBOffice Ledger."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from atboffice.modules.spreadsheet.calc.references import MAXC, MAXR, cell_name, parse_range
from atboffice.modules.spreadsheet.io.xlsx_drawing_shapes import drawings_signature
from atboffice.modules.spreadsheet.io.xlsx_reader import BUILTIN_NUMFMTS, comments_signature
from atboffice.modules.spreadsheet.models.color_utils import (
    DEFAULT_INDEXED_PALETTE,
    DEFAULT_THEME_COLORS,
    normalize_hex_color,
    resolve_color_spec,
)
from atboffice.modules.spreadsheet.models.excel_units import DEFAULT_MDW, px_to_width
from atboffice.modules.spreadsheet.models.pivot_model import write_pivots_to_package
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    RichTextRun,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.vfs.opc import PackageWriter, SourcePackage, get_rels_path, relative_part_uri
from atboffice.vfs.xml_tree import (
    LET,
    ensure_child,
    find_all_local,
    find_local,
    insert_in_order,
    namespace_of,
    parse_fragment,
    parse_lxml,
    serialize_lxml,
)

XML_HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
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
CT_SHARED_STRINGS = "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"
CT_THEME = "application/vnd.openxmlformats-officedocument.theme+xml"
CT_CORE_PROPS = "application/vnd.openxmlformats-package.core-properties+xml"
CT_APP_PROPS = "application/vnd.openxmlformats-officedocument.extended-properties+xml"
CT_RELATIONSHIPS = "application/vnd.openxmlformats-package.relationships+xml"
CT_DRAWING = "application/vnd.openxmlformats-officedocument.drawing+xml"
CT_CHART = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"
CT_COMMENTS = "application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml"
CT_VML_DRAWING = "application/vnd.openxmlformats-officedocument.vmlDrawing"

REL_OFFICE_DOC = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
REL_WORKSHEET = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
REL_STYLES = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
REL_SHARED_STRINGS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"
)
REL_THEME = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
REL_CORE_PROPS = (
    "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"
)
REL_APP_PROPS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"
)
REL_DRAWING = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
REL_CHART = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
REL_COMMENTS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
REL_VML_DRAWING = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing"
REL_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
REL_PIVOT_TABLE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotTable"
REL_PIVOT_CACHE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheDefinition"
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
    if clean and (clean[0].isspace() or clean[-1].isspace() or "\n" in clean or "\r" in clean):
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


def _spec_key(spec: dict[str, Any] | None) -> tuple[tuple[str, Any], ...] | None:
    """Convert an OOXML color spec dict into a hashable cache key."""
    if not spec:
        return None
    return tuple(sorted(spec.items()))


def _color_element(
    tag: str,
    hex_color: str | None,
    spec: dict[str, Any] | None = None,
    theme_colors: Sequence[str] | None = None,
    palette: Sequence[str] | None = None,
) -> str:
    """Serialize an OOXML color element, preserving theme/indexed/tint/auto when valid."""
    if spec:
        if spec.get("auto") and hex_color is None:
            return f'<{tag} auto="1"/>'
        if hex_color is not None:
            expected = resolve_color_spec(spec, theme_colors=theme_colors, palette=palette)
            norm_cur = normalize_hex_color(hex_color)
            if expected and norm_cur and expected.upper() == norm_cur.upper():
                attrs: list[str] = []
                if "theme" in spec and spec["theme"] is not None:
                    attrs.append(f'theme="{spec["theme"]}"')
                elif spec.get("rgb"):
                    attrs.append(f'rgb="{spec["rgb"]}"')
                elif "indexed" in spec and spec["indexed"] is not None:
                    attrs.append(f'indexed="{spec["indexed"]}"')
                if attrs:
                    if spec.get("tint"):
                        attrs.append(f'tint="{spec["tint"]}"')
                    return f"<{tag} {' '.join(attrs)}/>"
    c_hex = _color_hex(hex_color)
    if c_hex:
        return f'<{tag} rgb="{c_hex}"/>'
    return ""


class SharedStringsManager:
    """Manages unique shared strings for xl/sharedStrings.xml."""

    def __init__(
        self,
        theme_colors: Sequence[str] | None = None,
        palette: Sequence[str] | None = None,
    ) -> None:
        self.strings: list[str | tuple[str, list[RichTextRun]]] = []
        self.index_map: dict[Any, int] = {}
        self.total_count: int = 0
        self.theme_colors = list(theme_colors) if theme_colors else list(DEFAULT_THEME_COLORS)
        self.palette = list(palette) if palette else list(DEFAULT_INDEXED_PALETTE)

    def add(self, s: str, runs: list[RichTextRun] | None = None) -> int:
        self.total_count += 1
        has_runs = bool(
            runs
            and any(
                r.font_family
                or r.font_size
                or r.bold
                or r.italic
                or r.underline
                or r.strike
                or r.fg_color
                or r.vert_align
                for r in runs
            )
        )
        if has_runs and runs:
            key = (
                "rich",
                s,
                tuple(
                    (
                        r.text,
                        r.font_family,
                        r.font_size,
                        r.bold,
                        r.italic,
                        r.underline,
                        r.underline_style,
                        r.strike,
                        r.fg_color,
                        _spec_key(getattr(r, "fg_color_spec", None)),
                        r.vert_align,
                    )
                    for r in runs
                ),
            )
            entry: str | tuple[str, list[RichTextRun]] = (s, list(runs))
        else:
            key = ("plain", s)
            entry = s

        idx = self.index_map.get(key)
        if idx is not None:
            return idx
        idx = len(self.strings)
        self.strings.append(entry)
        self.index_map[key] = idx
        return idx

    def to_xml(self) -> bytes:
        if not self.strings:
            return b""
        parts = [
            XML_HEADER,
            f'<sst xmlns="{NS_MAIN}" count="{self.total_count}" uniqueCount="{len(self.strings)}">',
        ]
        for entry in self.strings:
            if isinstance(entry, tuple):
                _, runs = entry
                si_parts = ["<si>"]
                for r in runs:
                    rpr_parts: list[str] = []
                    if r.font_family:
                        rpr_parts.append(f'<rFont val="{_xml_escape(r.font_family)}"/>')
                    if r.bold:
                        rpr_parts.append("<b/>")
                    if r.italic:
                        rpr_parts.append("<i/>")
                    if r.strike:
                        rpr_parts.append("<strike/>")
                    if r.underline:
                        u_style = r.underline_style or "single"
                        if u_style == "single":
                            rpr_parts.append("<u/>")
                        else:
                            rpr_parts.append(f'<u val="{_xml_escape(u_style)}"/>')
                    if r.font_size:
                        rpr_parts.append(f'<sz val="{r.font_size}"/>')
                    if r.fg_color or getattr(r, "fg_color_spec", None):
                        col_xml = _color_element(
                            "color",
                            r.fg_color,
                            getattr(r, "fg_color_spec", None),
                            self.theme_colors,
                            self.palette,
                        )
                        if col_xml:
                            rpr_parts.append(col_xml)
                    if r.vert_align:
                        rpr_parts.append(f'<vertAlign val="{_xml_escape(r.vert_align)}"/>')

                    rpr_xml = f"<rPr>{''.join(rpr_parts)}</rPr>" if rpr_parts else ""
                    t_xml = _text_element(r.text)
                    si_parts.append(f"<r>{rpr_xml}{t_xml}</r>")
                si_parts.append("</si>")
                parts.append("".join(si_parts))
            else:
                truncated = entry[:32767] if len(entry) > 32767 else entry
                parts.append(f"<si>{_text_element(truncated)}</si>")
        parts.append("</sst>")
        return "".join(parts).encode("utf-8")


_STYLESHEET_ORDER = [
    "numFmts",
    "fonts",
    "fills",
    "borders",
    "cellStyleXfs",
    "cellXfs",
    "cellStyles",
    "dxfs",
    "tableStyles",
    "colors",
    "extLst",
]


def _freeze(value: Any) -> Any:
    """Turn nested dicts/lists into hashable tuples for signature keys."""
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if hasattr(value, "__dataclass_fields__"):
        return tuple((k, _freeze(getattr(value, k))) for k in value.__dataclass_fields__)
    return value


_SIGNATURE_FIELDS = (
    "format_code",
    "bold",
    "italic",
    "underline",
    "underline_style",
    "strike",
    "vert_align",
    "font_size",
    "font_family",
    "fg_color",
    "fg_color_spec",
    "bg_color",
    "bg_color_spec",
    "align_h",
    "align_v",
    "indent",
    "wrap_text",
    "shrink_to_fit",
    "text_rotation",
    "text_direction",
    "border_top",
    "border_bottom",
    "border_left",
    "border_right",
    "border_diag_up",
    "border_diag_down",
    "pattern",
    "pattern_color",
    "pattern_color_spec",
    "locked",
    "hidden",
)


def _format_signature(cell: CellData) -> tuple[Any, ...]:
    """Everything about a cell that its ``<xf>`` record determines."""
    return tuple(_freeze(getattr(cell, name, None)) for name in _SIGNATURE_FIELDS)


class StyleManager:
    """Manages styles and generates xl/styles.xml."""

    def __init__(
        self,
        theme_colors: Sequence[str] | None = None,
        indexed_palette: Sequence[str] | None = None,
    ) -> None:
        self.theme_colors = list(theme_colors) if theme_colors else list(DEFAULT_THEME_COLORS)
        self.indexed_palette = list(indexed_palette) if indexed_palette else None
        self.palette = list(indexed_palette) if indexed_palette else list(DEFAULT_INDEXED_PALETTE)

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
        self.borders.append("<border><left/><right/><top/><bottom/><diagonal/></border>")

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

        # Set by from_source(): the original stylesheet that new records are appended to.
        self._source_root: Any = None
        self._base_counts: dict[str, int] = {}
        self._source_xf_by_signature: dict[tuple[Any, ...], int] = {}
        self._ns = NS_MAIN

    @classmethod
    def from_source(
        cls,
        styles_xml: bytes,
        style_deltas: Sequence[Any],
        theme_colors: Sequence[str] | None = None,
        indexed_palette: Sequence[str] | None = None,
    ) -> StyleManager:
        """Build a manager that appends to an existing ``styles.xml``.

        Every original font, fill, border, number format, cell format and differential
        format keeps its index, so style references carried verbatim in worksheet XML
        (``<col style>``, ``<row s>``, conditional-format ``dxfId``) stay valid. Cells whose
        formatting still matches an original cell format reuse that format's index; only
        genuinely new formatting is appended.
        """
        mgr = cls(theme_colors=theme_colors, indexed_palette=indexed_palette)
        root = parse_lxml(styles_xml)
        ns = namespace_of(root)

        def count(container: str, item: str) -> int:
            return len(find_all_local(find_local(root, container), item))

        mgr._source_root = root
        mgr._base_counts = {
            "fonts": count("fonts", "font"),
            "fills": count("fills", "fill"),
            "borders": count("borders", "border"),
            "cellXfs": count("cellXfs", "xf"),
            "dxfs": count("dxfs", "dxf"),
        }
        # Placeholders keep new records' indices after the original ones.
        mgr.fonts = [""] * mgr._base_counts["fonts"]
        mgr.fills = [""] * max(mgr._base_counts["fills"], 2)
        mgr.borders = [""] * max(mgr._base_counts["borders"], 1)
        mgr.cell_xfs = [{}] * max(mgr._base_counts["cellXfs"], 1)
        mgr.dxfs = [{}] * mgr._base_counts["dxfs"]
        mgr.font_map, mgr.fill_map, mgr.border_map, mgr.cell_xf_map = {}, {}, {}, {}
        mgr._base_counts = {
            "fonts": len(mgr.fonts),
            "fills": len(mgr.fills),
            "borders": len(mgr.borders),
            "cellXfs": len(mgr.cell_xfs),
            "dxfs": len(mgr.dxfs),
        }
        if not mgr.fonts:
            mgr._get_or_add_font("Arial", 10, False, False, False, False, None)

        mgr.num_fmts, mgr.num_fmt_map = [], {}
        max_id = 163
        for nf in find_all_local(find_local(root, "numFmts"), "numFmt"):
            try:
                fid = int(nf.get("numFmtId", ""))
            except ValueError:
                continue
            code = nf.get("formatCode")
            if code is not None:
                mgr.num_fmt_map.setdefault(code, fid)
            max_id = max(max_id, fid)
        mgr._next_num_fmt_id = max_id + 1

        probe = SheetDataModel()
        for idx, delta in enumerate(style_deltas):
            probe.cells.clear()
            cell = probe.apply_format_delta(0, 0, delta)
            mgr._source_xf_by_signature.setdefault(_format_signature(cell), idx)
        mgr._ns = ns
        return mgr

    def has_new_records(self) -> bool:
        """True when this save created styles that the original stylesheet lacks."""
        if self._source_root is None:
            return True
        b = self._base_counts
        return bool(
            self.num_fmts
            or len(self.fonts) > b["fonts"]
            or len(self.fills) > b["fills"]
            or len(self.borders) > b["borders"]
            or len(self.cell_xfs) > b["cellXfs"]
            or len(self.dxfs) > b["dxfs"]
        )

    def _merge_into_source(self) -> bytes:
        """Append the records created during this save to the original stylesheet."""
        root = self._source_root
        ns = self._ns
        sections = [
            (
                "numFmts",
                "numFmt",
                [
                    f'<numFmt numFmtId="{fid}" formatCode="{_xml_escape(code)}"/>'
                    for fid, code in self.num_fmts
                ],
            ),
            ("fonts", "font", self.fonts[self._base_counts["fonts"] :]),
            ("fills", "fill", self.fills[self._base_counts["fills"] :]),
            ("borders", "border", self.borders[self._base_counts["borders"] :]),
            (
                "cellXfs",
                "xf",
                [self._xf_xml(xf) for xf in self.cell_xfs[self._base_counts["cellXfs"] :]],
            ),
            ("dxfs", "dxf", [self._dxf_xml(d) for d in self.dxfs[self._base_counts["dxfs"] :]]),
        ]
        for container_name, item_name, items in sections:
            items = [x for x in items if x]
            if not items:
                continue
            container = ensure_child(root, container_name, _STYLESHEET_ORDER)
            for el in parse_fragment("".join(items), ns):
                container.append(el)
            container.set("count", str(len(find_all_local(container, item_name))))
        return serialize_lxml(root)

    def _get_or_add_font(
        self,
        name: str,
        sz: int,
        bold: bool,
        italic: bool,
        underline: bool,
        strike: bool,
        color: str | None,
        color_spec: dict[str, Any] | None = None,
    ) -> int:
        c_hex = _color_hex(color)
        s_key = _spec_key(color_spec)
        key = (
            name or "Arial",
            sz or 10,
            bool(bold),
            bool(italic),
            bool(underline),
            bool(strike),
            c_hex,
            s_key,
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
        col_xml = _color_element("color", color, color_spec, self.theme_colors, self.palette)
        if col_xml:
            parts.append(col_xml)
        parts.append(f'<name val="{_xml_escape(name or "Arial")}"/>')
        parts.append('<family val="2"/>')

        xml = f"<font>{''.join(parts)}</font>"
        idx = len(self.fonts)
        self.fonts.append(xml)
        self.font_map[key] = idx
        return idx

    def _get_or_add_fill(
        self,
        bg_color: str | None,
        pattern: str | None = None,
        bg_color_spec: dict[str, Any] | None = None,
        pattern_color: str | None = None,
        pattern_color_spec: dict[str, Any] | None = None,
    ) -> int:
        if (
            not bg_color
            and not bg_color_spec
            and not pattern_color
            and not pattern_color_spec
            and (not pattern or pattern == "none")
        ):
            return 0
        c_hex = _color_hex(bg_color)
        p_hex = _color_hex(pattern_color)
        key = (
            c_hex,
            _spec_key(bg_color_spec),
            p_hex,
            _spec_key(pattern_color_spec),
            pattern or "solid",
        )
        if key in self.fill_map:
            return self.fill_map[key]

        ptype = pattern or "solid"
        if ptype == "solid":
            fg_xml = _color_element(
                "fgColor", bg_color, bg_color_spec, self.theme_colors, self.palette
            )
            bg_xml = _color_element(
                "bgColor", bg_color, bg_color_spec, self.theme_colors, self.palette
            )
            if fg_xml or bg_xml:
                xml = (
                    f'<fill><patternFill patternType="{_xml_escape(ptype)}">'
                    f"{fg_xml}{bg_xml}</patternFill></fill>"
                )
            else:
                xml = f'<fill><patternFill patternType="{_xml_escape(ptype)}"/></fill>'
        else:
            fg_xml = _color_element(
                "fgColor", pattern_color, pattern_color_spec, self.theme_colors, self.palette
            )
            bg_xml = _color_element(
                "bgColor", bg_color, bg_color_spec, self.theme_colors, self.palette
            )
            xml = f'<fill><patternFill patternType="{ptype}">{fg_xml}{bg_xml}</patternFill></fill>'
        idx = len(self.fills)
        self.fills.append(xml)
        self.fill_map[key] = idx
        return idx

    def _border_side_xml(self, tag: str, side: BorderStyle | None) -> str:
        if not side or not side.style or side.style == "none":
            return f"<{tag}/>"
        c_xml = _color_element(
            "color",
            side.color,
            getattr(side, "color_spec", None),
            self.theme_colors,
            self.palette,
        )
        return f'<{tag} style="{_xml_escape(side.style)}">{c_xml}</{tag}>'

    def _get_or_add_border(
        self,
        top: BorderStyle | None,
        bottom: BorderStyle | None,
        left: BorderStyle | None,
        right: BorderStyle | None,
    ) -> int:
        def _side_key(side: BorderStyle | None) -> tuple[Any, ...] | None:
            if not side:
                return None
            return (
                side.style,
                _color_hex(side.color),
                _spec_key(getattr(side, "color_spec", None)),
            )

        top_k = _side_key(top)
        bot_k = _side_key(bottom)
        left_k = _side_key(left)
        right_k = _side_key(right)
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
        if self._source_xf_by_signature:
            original = self._source_xf_by_signature.get(_format_signature(cell))
            if original is not None:
                return original

        has_font = bool(
            cell.bold
            or cell.italic
            or cell.underline
            or cell.strike
            or cell.font_size != 10
            or cell.font_family != "Arial"
            or cell.fg_color
            or getattr(cell, "fg_color_spec", None)
        )
        has_fill = bool(
            cell.bg_color
            or getattr(cell, "bg_color_spec", None)
            or cell.pattern_color
            or getattr(cell, "pattern_color_spec", None)
            or (cell.pattern and cell.pattern != "none")
        )
        has_border = bool(
            cell.border_top or cell.border_bottom or cell.border_left or cell.border_right
        )
        has_num_fmt = bool(cell.format_code and cell.format_code != "General")
        has_align = bool(
            (cell.align_h and cell.align_h != "general")
            or (cell.align_v and cell.align_v != "bottom")
            or cell.wrap_text
            or cell.text_rotation
            or cell.shrink_to_fit
            or cell.indent
            or (cell.text_direction and cell.text_direction != "context")
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
                color_spec=getattr(cell, "fg_color_spec", None),
            )
            if has_font
            else 0
        )
        fill_id = (
            self._get_or_add_fill(
                cell.bg_color,
                cell.pattern,
                bg_color_spec=getattr(cell, "bg_color_spec", None),
                pattern_color=cell.pattern_color,
                pattern_color_spec=getattr(cell, "pattern_color_spec", None),
            )
            if has_fill
            else 0
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
        num_fmt_id = self._get_or_add_num_fmt(cell.format_code) if has_num_fmt else 0

        align_key = None
        if has_align:
            ro_val = None
            if cell.text_direction == "ltr":
                ro_val = "1"
            elif cell.text_direction == "rtl":
                ro_val = "2"
            align_key = (
                cell.align_h if cell.align_h != "general" else None,
                cell.align_v if cell.align_v != "bottom" else None,
                bool(cell.wrap_text),
                bool(cell.shrink_to_fit),
                int(cell.text_rotation or 0),
                int(cell.indent or 0),
                ro_val,
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
        bg_color_spec: dict[str, Any] | None = None,
        fg_color_spec: dict[str, Any] | None = None,
    ) -> int:
        """Register differential formatting record for conditional formatting."""
        dxf = {
            "bg_color": bg_color,
            "fg_color": fg_color,
            "bg_color_spec": bg_color_spec,
            "fg_color_spec": fg_color_spec,
            "bold": bold,
            "italic": italic,
        }
        self.dxfs.append(dxf)
        return len(self.dxfs) - 1

    def _xf_xml(self, xf: dict[str, Any]) -> str:
        """Serialize one ``<xf>`` record of ``cellXfs``."""
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

        align_attrs = []
        if xf["align"]:
            h, v, wrap, shrink, rot, ind, ro = xf["align"]
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
            if ro:
                align_attrs.append(f'readingOrder="{ro}"')

        if align_attrs:
            attrs.append('applyAlignment="1"')
            return f"<xf {' '.join(attrs)}><alignment {' '.join(align_attrs)}/></xf>"
        return f"<xf {' '.join(attrs)}/>"

    def _dxf_xml(self, d: dict[str, Any]) -> str:
        """Serialize one ``<dxf>`` differential format."""
        parts = ["<dxf>"]
        font_parts = []
        if d.get("bold"):
            font_parts.append('<b val="1"/>')
        if d.get("italic"):
            font_parts.append('<i val="1"/>')
        if d.get("fg_color") or d.get("fg_color_spec"):
            col_xml = _color_element(
                "color", d.get("fg_color"), d.get("fg_color_spec"), self.theme_colors, self.palette
            )
            if col_xml:
                font_parts.append(col_xml)
        if font_parts:
            parts.append(f"<font>{''.join(font_parts)}</font>")
        if d.get("bg_color") or d.get("bg_color_spec"):
            fg_xml = _color_element(
                "fgColor",
                d.get("bg_color"),
                d.get("bg_color_spec"),
                self.theme_colors,
                self.palette,
            )
            if fg_xml:
                parts.append(
                    f'<fill><patternFill patternType="solid">{fg_xml}</patternFill></fill>'
                )
        parts.append("</dxf>")
        return "".join(parts)

    def to_styles_xml(self) -> bytes:
        if self._source_root is not None:
            return self._merge_into_source()
        parts = [XML_HEADER, f'<styleSheet xmlns="{NS_MAIN}">']

        # 1. numFmts
        if self.num_fmts:
            parts.append(f'<numFmts count="{len(self.num_fmts)}">')
            for fid, code in self.num_fmts:
                parts.append(f'<numFmt numFmtId="{fid}" formatCode="{_xml_escape(code)}"/>')
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
        parts.extend(self._xf_xml(xf) for xf in self.cell_xfs)
        parts.append("</cellXfs>")

        # 7. cellStyles
        parts.append(
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        )

        # 8. dxfs
        if not self.dxfs:
            parts.append('<dxfs count="0"/>')
        else:
            parts.append(f'<dxfs count="{len(self.dxfs)}">')
            parts.extend(self._dxf_xml(d) for d in self.dxfs)
            parts.append("</dxfs>")

        # 9. tableStyles
        parts.append(
            '<tableStyles count="0" defaultTableStyle="TableStyleMedium2" '
            'defaultPivotStyle="PivotStyleLight16"/>'
        )

        # 10. Optional custom indexedColors
        if self.indexed_palette:
            idx_xml = "".join(
                f'<rgbColor rgb="{_color_hex(c) or "FF000000"}"/>'
                for c in self.indexed_palette[:64]
            )
            parts.append(f"<colors><indexedColors>{idx_xml}</indexedColors></colors>")

        parts.append("</styleSheet>")
        return "".join(parts).encode("utf-8")


def _serialize_sheet_data(
    sheet: SheetDataModel,
    style_manager: StyleManager,
    sst_manager: SharedStringsManager,
) -> str:
    """Serialize the <sheetData>...</sheetData> XML block for a worksheet."""
    parts = ["<sheetData>"]
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
            # exact inverse of the reader's round(pt / 0.75): px * 0.75 is a 0.25 pt multiple
            ht_str = f"{ht_px * 0.75:g}"
            row_attrs.append(f'ht="{ht_str}" customHeight="1"')

        if r in sheet.geometry.hidden_rows:
            row_attrs.append('hidden="1"')

        if not c_list:
            parts.append(f"<row {' '.join(row_attrs)}/>")
            continue

        parts.append(f"<row {' '.join(row_attrs)}>")
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
                    parts.append(f'<c r="{c_ref}"{s_attr}><v>{cell.value}</v></c>')
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
                        parts.append(f'<c r="{c_ref}"{s_attr} t="e"><v>{cell.value}</v></c>')
                    else:
                        sst_id = sst_manager.add(cell.value, cell.rich_runs)
                        parts.append(f'<c r="{c_ref}"{s_attr} t="s"><v>{sst_id}</v></c>')
                else:
                    sst_id = sst_manager.add(str(cell.value), cell.rich_runs)
                    parts.append(f'<c r="{c_ref}"{s_attr} t="s"><v>{sst_id}</v></c>')

        parts.append("</row>")

    parts.append("</sheetData>")
    return "".join(parts)


_X14_CF_EXT_URI = "{78C0D931-6437-407d-A8EE-F0AAD7539E65}"
_NS_X14 = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
_NS_XM = "http://schemas.microsoft.com/office/excel/2006/main"


def _icon_set_attrs(ic: Any, x14: bool) -> str:
    attrs = [f'iconSet="{_xml_escape(ic.set_name)}"']
    if not ic.show_value:
        attrs.append('showValue="0"')
    if not ic.percent:
        attrs.append('percent="0"')
    if ic.reverse:
        attrs.append('reverse="1"')
    if x14 and ic.custom:
        attrs.append('custom="1"')
    return " ".join(attrs)


def _icon_set_rule_xml(rule: Any) -> str:
    """Serialize a main-namespace ``<cfRule type="iconSet">``."""
    ic = rule.icon_set
    stop = ' stopIfTrue="1"' if rule.stop_if_true else ""
    out = [f'<cfRule type="iconSet" priority="{rule.priority}"{stop}>']
    out.append(f"<iconSet {_icon_set_attrs(ic, False)}>")
    for cfvo in ic.cfvos:
        v_attr = f' val="{_xml_escape(str(cfvo.val))}"' if cfvo.val is not None else ""
        g_attr = ' gte="0"' if not getattr(cfvo, "gte", True) else ""
        out.append(f'<cfvo type="{cfvo.type}"{v_attr}{g_attr}/>')
    out.append("</iconSet></cfRule>")
    return "".join(out)


def _x14_icon_set_ext_xml(formats: list[tuple[str, list[Any]]]) -> str:
    """Serialize x14-only icon-set rules into a worksheet ``<extLst>`` block."""
    out = [
        f'<extLst><ext uri="{_X14_CF_EXT_URI}" xmlns:x14="{_NS_X14}">',
        "<x14:conditionalFormattings>",
    ]
    for sqref, rules in formats:
        out.append(f'<x14:conditionalFormatting xmlns:xm="{_NS_XM}">')
        for rule in rules:
            ic = rule.icon_set
            stop = ' stopIfTrue="1"' if rule.stop_if_true else ""
            rid = "{" + str(uuid.uuid4()).upper() + "}"
            out.append(f'<x14:cfRule type="iconSet" priority="{rule.priority}"{stop} id="{rid}">')
            out.append(f"<x14:iconSet {_icon_set_attrs(ic, True)}>")
            for cfvo in ic.cfvos:
                g_attr = ' gte="0"' if not getattr(cfvo, "gte", True) else ""
                if cfvo.val is not None:
                    out.append(
                        f'<x14:cfvo type="{cfvo.type}"{g_attr}>'
                        f"<xm:f>{_xml_escape(str(cfvo.val))}</xm:f></x14:cfvo>"
                    )
                else:
                    out.append(f'<x14:cfvo type="{cfvo.type}"{g_attr}/>')
            for c_set, c_id in ic.custom:
                out.append(f'<x14:cfIcon iconSet="{_xml_escape(c_set)}" iconId="{c_id}"/>')
            out.append("</x14:iconSet></x14:cfRule>")
        out.append(f"<xm:sqref>{_xml_escape(sqref)}</xm:sqref></x14:conditionalFormatting>")
    out.append("</x14:conditionalFormattings></ext></extLst>")
    return "".join(out)


def _sheet_views_xml(sheet: SheetDataModel, is_active: bool) -> str:
    """Serialize ``<sheetViews>`` from ``sheet.view_state`` (attributes in CT_SheetView order)."""
    vs = sheet.view_state
    attrs = []
    if not vs.show_grid_lines:
        attrs.append('showGridLines="0"')
    if is_active:
        attrs.append('tabSelected="1"')
    if vs.view in ("pageBreakPreview", "pageLayout"):
        attrs.append(f'view="{vs.view}"')
    if vs.top_left_cell and vs.top_left_rc() is not None:
        attrs.append(f'topLeftCell="{_xml_escape(vs.top_left_cell)}"')
    if vs.zoom_scale:
        zoom = max(10, min(400, int(vs.zoom_scale)))
        attrs.append(f'zoomScale="{zoom}"')
        if vs.view == "pageBreakPreview":
            attrs.append(f'zoomScaleSheetLayoutView="{zoom}"')
    attrs.append('workbookViewId="0"')
    attr_str = "".join(f" {a}" for a in attrs)
    sel_xml = ""
    if vs.active_cell_rc() is not None:
        ranges = (
            " ".join(p for p in (vs.sqref or "").split() if parse_range(p) is not None)
            or vs.active_cell
        )
        sel_xml = (
            f'<selection activeCell="{_xml_escape(vs.active_cell)}" sqref="{_xml_escape(ranges)}"/>'
        )
    if sel_xml:
        return f"<sheetViews><sheetView{attr_str}>{sel_xml}</sheetView></sheetViews>"
    return f"<sheetViews><sheetView{attr_str}/></sheetViews>"


def _breaks_xml(tag: str, breaks: list[int], max_index: int) -> str:
    """Serialize stored manual page breaks as ``<rowBreaks>``/``<colBreaks>``."""
    ids = sorted({b for b in breaks if b > 0})
    if not ids:
        return ""
    brks = "".join(f'<brk id="{b}" max="{max_index}" man="1"/>' for b in ids)
    return f'<{tag} count="{len(ids)}" manualBreakCount="{len(ids)}">{brks}</{tag}>'


def _cf_sqref(cf: Any) -> str:
    """Return ``cf.sqref``, falling back to formatted ``cf.ranges`` if empty."""
    sqref = getattr(cf, "sqref", "") or ""
    if sqref.strip():
        return sqref.strip()
    parts: list[str] = []
    for r1, c1, r2, c2 in getattr(cf, "ranges", []) or []:
        parts.append(
            f"{cell_name(r1, c1)}:{cell_name(r2, c2)}"
            if (r1, c1) != (r2, c2)
            else cell_name(r1, c1)
        )
    return " ".join(parts) or "A1"


def _serialize_conditional_formatting_blocks(
    sheet: SheetDataModel,
    style_manager: StyleManager,
) -> tuple[list[str], list[tuple[str, list[Any]]]]:
    """Serialize ``<conditionalFormatting>`` blocks and collect x14-only icon rules."""
    parts: list[str] = []
    x14_icon_formats: list[tuple[str, list[Any]]] = []
    for cf in getattr(sheet, "conditional_formats", []):
        sqref = _cf_sqref(cf)
        x14_rules = [
            rule for rule in cf.rules if rule.icon_set is not None and rule.icon_set.needs_x14()
        ]
        if x14_rules:
            x14_icon_formats.append((sqref, x14_rules))
        x14_ids = {id(rule) for rule in x14_rules}
        main_rules = [rule for rule in cf.rules if id(rule) not in x14_ids]
        if not main_rules:
            continue
        parts.append(f'<conditionalFormatting sqref="{_xml_escape(sqref)}">')
        for rule in main_rules:
            if rule.icon_set is not None:
                parts.append(_icon_set_rule_xml(rule))
            elif rule.color_scale:
                parts.append(f'<cfRule type="colorScale" priority="{rule.priority}">')
                parts.append("<colorScale>")
                for cfvo in rule.color_scale.cfvos:
                    v_attr = f' val="{cfvo.val}"' if cfvo.val is not None else ""
                    parts.append(f'<cfvo type="{cfvo.type}"{v_attr}/>')
                color_specs = getattr(rule.color_scale, "color_specs", None) or []
                for idx_col, col in enumerate(rule.color_scale.colors):
                    spec = color_specs[idx_col] if idx_col < len(color_specs) else None
                    col_xml = _color_element(
                        "color",
                        col,
                        spec,
                        style_manager.theme_colors,
                        style_manager.palette,
                    )
                    parts.append(col_xml or '<color rgb="FFFFFFFF"/>')
                parts.append("</colorScale>")
                parts.append("</cfRule>")
            elif rule.data_bar:
                db = rule.data_bar
                show_attr = ' showValue="0"' if not getattr(db, "show_value", True) else ""
                parts.append(
                    f'<cfRule type="dataBar" priority="{rule.priority}">'
                    f'<dataBar minLength="{int(db.min_len * 100)}" '
                    f'maxLength="{int(db.max_len * 100)}"{show_attr}>'
                )
                for cfvo in db.cfvos:
                    v_attr = f' val="{cfvo.val}"' if cfvo.val is not None else ""
                    parts.append(f'<cfvo type="{cfvo.type}"{v_attr}/>')
                col_xml = _color_element(
                    "color",
                    db.color,
                    getattr(db, "color_spec", None),
                    style_manager.theme_colors,
                    style_manager.palette,
                )
                parts.append(col_xml or '<color rgb="FF638EC6"/>')
                parts.append("</dataBar></cfRule>")
            else:
                dxf_id = style_manager.add_dxf(
                    bg_color=rule.bg_color,
                    fg_color=rule.fg_color,
                    bold=rule.bold,
                    italic=rule.italic,
                    bg_color_spec=getattr(rule, "bg_color_spec", None),
                    fg_color_spec=getattr(rule, "fg_color_spec", None),
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
                parts.append(f"<cfRule {' '.join(r_attrs)}>")
                for f in rule.formula:
                    parts.append(f"<formula>{_xml_escape(str(f))}</formula>")
                parts.append("</cfRule>")
        parts.append("</conditionalFormatting>")
    return parts, x14_icon_formats


def _serialize_worksheet(
    sheet: SheetDataModel,
    style_manager: StyleManager,
    sst_manager: SharedStringsManager,
    is_active: bool,
    drawing_rid: str | None = None,
    legacy_drawing_rid: str | None = None,
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

    parts = [
        XML_HEADER,
        f'<worksheet xmlns="{NS_MAIN}" xmlns:r="{NS_R}">',
        _sheet_pr_xml(sheet),
        f'<dimension ref="{dim_ref}"/>',
        _sheet_views_xml(sheet, is_active),
        '<sheetFormatPr defaultRowHeight="20"/>',
    ]

    # Columns (<cols>)
    if sheet.geometry.custom_col_widths or sheet.geometry.hidden_cols:
        col_indices = sorted(
            set(sheet.geometry.custom_col_widths.keys()) | set(sheet.geometry.hidden_cols)
        )
        if col_indices:
            parts.append("<cols>")
            for c in col_indices:
                w_px = sheet.geometry.col_size(c)
                mdw = int(sheet.extra.get("excel_mdw") or DEFAULT_MDW)
                w_str = f"{px_to_width(w_px, mdw):.8g}"
                c_1 = c + 1
                hidden_attr = ' hidden="1"' if c in sheet.geometry.hidden_cols else ""
                parts.append(
                    f'<col min="{c_1}" max="{c_1}" width="{w_str}" customWidth="1"{hidden_attr}/>'
                )
            parts.append("</cols>")

    # Rows and cells (<sheetData>)
    parts.append(_serialize_sheet_data(sheet, style_manager, sst_manager))

    # Merged cells (<mergeCells>)
    if sheet.merges:
        parts.append(f'<mergeCells count="{len(sheet.merges)}">')
        for m in sheet.merges:
            ref = f"{cell_name(m[0], m[1])}:{cell_name(m[2], m[3])}"
            parts.append(f'<mergeCell ref="{ref}"/>')
        parts.append("</mergeCells>")

    # Conditional Formatting (<conditionalFormatting>)
    cf_parts, x14_icon_formats = _serialize_conditional_formatting_blocks(sheet, style_manager)
    parts.extend(cf_parts)

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
            parts.append(f"<dataValidation {' '.join(dv_attrs)}>")
            if dv.formula1:
                parts.append(f"<formula1>{_xml_escape(str(dv.formula1))}</formula1>")
            if dv.formula2:
                parts.append(f"<formula2>{_xml_escape(str(dv.formula2))}</formula2>")
            parts.append("</dataValidation>")
        parts.append("</dataValidations>")

    # Print options, margins, page setup and header/footer (File > Page Setup)
    parts.append(_page_setup_block_xml(sheet))
    parts.append(_breaks_xml("rowBreaks", sheet.view_state.row_breaks, MAXC - 1))
    parts.append(_breaks_xml("colBreaks", sheet.view_state.col_breaks, MAXR - 1))
    if drawing_rid:
        parts.append(f'<drawing r:id="{drawing_rid}"/>')
    if legacy_drawing_rid:
        parts.append(f'<legacyDrawing r:id="{legacy_drawing_rid}"/>')
    if x14_icon_formats:
        parts.append(_x14_icon_set_ext_xml(x14_icon_formats))
    parts.append("</worksheet>")

    return "".join(parts).encode("utf-8")


def _page_setup(sheet: Any) -> Any:
    from atboffice.modules.spreadsheet.printing.setup import get_print_setup

    return get_print_setup(sheet)


def _sheet_pr_xml(sheet: Any) -> str:
    return '<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>' if _page_setup(sheet).fit_to else ""


def _page_setup_block_xml(sheet: Any) -> str:
    """``printOptions``, ``pageMargins``, ``pageSetup`` and ``headerFooter`` (schema order)."""
    from atboffice.modules.spreadsheet.printing.setup import PAPER_CODES

    st = _page_setup(sheet)
    out: list[str] = []
    opts = []
    if st.center_h:
        opts.append('horizontalCentered="1"')
    if st.center_v:
        opts.append('verticalCentered="1"')
    if st.headings:
        opts.append('headings="1"')
    if st.gridlines:
        opts.append('gridLines="1"')
    if opts:
        out.append(f"<printOptions {' '.join(opts)}/>")
    m = {k: round(v / 72.0, 4) for k, v in st.margins.items()}
    out.append(
        f'<pageMargins left="{m["left"]}" right="{m["right"]}" top="{m["top"]}" '
        f'bottom="{m["bottom"]}" header="{m["header"]}" footer="{m["footer"]}"/>'
    )
    ps = [f'paperSize="{PAPER_CODES.get(st.paper, 9)}"']
    if st.fit_to:
        ps.append(f'fitToWidth="{st.fit_width}"')
        ps.append(f'fitToHeight="{st.fit_height}"')
    elif st.scale != 100:
        ps.append(f'scale="{st.scale}"')
    if st.first_page_number is not None:
        ps.append(f'firstPageNumber="{st.first_page_number}"')
    if st.page_order == "over_then_down":
        ps.append('pageOrder="overThenDown"')
    ps.append(f'orientation="{st.orientation}"')
    if st.black_white:
        ps.append('blackAndWhite="1"')
    if st.first_page_number is not None:
        ps.append('useFirstPageNumber="1"')
    out.append(f"<pageSetup {' '.join(ps)}/>")
    if st.header or st.footer:
        hf = "<headerFooter>"
        if st.header:
            hf += f"<oddHeader>{_xml_escape(st.header)}</oddHeader>"
        if st.footer:
            hf += f"<oddFooter>{_xml_escape(st.footer)}</oddFooter>"
        out.append(hf + "</headerFooter>")
    return "".join(out)


_PAGE_ELEMENTS = re.compile(
    r"<(printOptions|pageMargins|pageSetup|headerFooter)\b(?:[^>]*/>|[^>]*>.*?</\1>)",
    re.DOTALL,
)
_AFTER_PAGE = re.compile(
    r"<(rowBreaks|colBreaks|customProperties|cellWatches|ignoredErrors|smartTags|drawing|"
    r"legacyDrawing|legacyDrawingHF|picture|oleObjects|controls|webPublishItems|tableParts|"
    r"extLst)\b|</worksheet>"
)


def _patch_page_setup(xml: str, sheet: Any) -> str:
    """Rewrite page-setup elements of preserved XML only when the user changed them."""
    from atboffice.modules.spreadsheet.printing.setup import get_print_setup

    extra = getattr(sheet, "extra", {}) or {}
    if "print_setup" not in extra:
        return xml
    if extra.get("print_setup_loaded") == get_print_setup(sheet).to_dict():
        return xml
    xml = _PAGE_ELEMENTS.sub("", xml)
    m = _AFTER_PAGE.search(xml)
    if m is None:
        return xml
    xml = xml[: m.start()] + _page_setup_block_xml(sheet) + xml[m.start() :]
    fit = get_print_setup(sheet).fit_to
    if re.search(r"<pageSetUpPr\b", xml):
        xml = re.sub(
            r"<pageSetUpPr\b[^>]*/>",
            '<pageSetUpPr fitToPage="1"/>' if fit else "",
            xml,
            count=1,
        )
    elif fit:
        if re.search(r"<sheetPr\b[^>]*/>", xml):
            xml = re.sub(
                r"<sheetPr\b([^>]*)/>",
                r'<sheetPr\1><pageSetUpPr fitToPage="1"/></sheetPr>',
                xml,
                count=1,
            )
        elif "</sheetPr>" in xml:
            # pageSetUpPr is the last child of sheetPr (after tabColor, outlinePr)
            xml = xml.replace("</sheetPr>", '<pageSetUpPr fitToPage="1"/></sheetPr>', 1)
        else:
            xml = re.sub(
                r"(<worksheet\b[^>]*>)",
                r'\1<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>',
                xml,
                count=1,
            )
    return xml


_GROUP_CHILD_EXTENT = 1_000_000  # virtual child coordinate space for written groups


def _iter_drawings(drawings: list[Any]) -> Iterator[Any]:
    """Yield drawings depth-first, including the children of group shapes."""
    for obj in drawings:
        yield obj
        yield from _iter_drawings(getattr(obj, "children", None) or [])


def _hex6(color: str | None, default: str) -> str:
    clean = (color or "").lstrip("#").upper() or default
    return clean[:6]


def _drawing_fill_xml(obj: Any) -> str:
    """spPr fill for a floating object (solid, none, gradient or pattern)."""
    fill_type = getattr(obj, "fill_type", "solid")
    if fill_type == "none":
        return "<a:noFill/>"
    stops = getattr(obj, "gradient_stops", None) or []
    if fill_type == "gradient" and stops:
        gs = "".join(
            f'<a:gs pos="{round(pos * 100000)}"><a:srgbClr val="{_hex6(col, "000000")}">'
            + (f'<a:alpha val="{round(alpha * 100000)}"/>' if alpha < 1.0 else "")
            + "</a:srgbClr></a:gs>"
            for pos, col, alpha in stops
        )
        ang = round(getattr(obj, "gradient_angle", 0.0) * 60000)
        return f'<a:gradFill><a:gsLst>{gs}</a:gsLst><a:lin ang="{ang}"/></a:gradFill>'
    if fill_type == "pattern":
        prst = _xml_escape(getattr(obj, "pattern", "") or "pct50")
        return (
            f'<a:pattFill prst="{prst}">'
            f'<a:fgClr><a:srgbClr val="{_hex6(obj.fill_color, "000000")}"/></a:fgClr>'
            f'<a:bgClr><a:srgbClr val="{_hex6(getattr(obj, "pattern_bg", ""), "FFFFFF")}"/>'
            f"</a:bgClr></a:pattFill>"
        )
    return f'<a:solidFill><a:srgbClr val="{_hex6(obj.fill_color, "4F81BD")}"/></a:solidFill>'


def _drawing_line_xml(obj: Any) -> str:
    """spPr outline for a floating object, including arrow ends."""
    if not getattr(obj, "line_visible", True):
        return "<a:ln><a:noFill/></a:ln>"
    lw_emu = int(max(0.5, getattr(obj, "line_width", 1.0)) * 12700)
    ends = ""
    for tag, attr in (("headEnd", "head_end"), ("tailEnd", "tail_end")):
        end_type = getattr(obj, attr, "")
        if end_type:
            ends += f'<a:{tag} type="{_xml_escape(end_type)}"/>'
    return (
        f'<a:ln w="{lw_emu}">'
        f'<a:solidFill><a:srgbClr val="{_hex6(obj.line_color, "385D8A")}"/></a:solidFill>'
        f"{ends}</a:ln>"
    )


def _drawing_geom_xml(obj: Any, geom_map: dict[str, str]) -> str:
    """Preset geometry (with adjustments) for a floating object."""
    geometry = getattr(obj, "geometry", "")
    if not geometry or geometry == "custom":
        geometry = geom_map.get(obj.kind, "rect")
        adj: dict[str, Any] = {}
    else:
        adj = getattr(obj, "geometry_adj", None) or {}
    gds = "".join(
        f'<a:gd name="{_xml_escape(str(name))}" fmla="val {round(float(val))}"/>'
        for name, val in adj.items()
        if isinstance(val, (int, float))
    )
    return f'<a:prstGeom prst="{_xml_escape(geometry)}"><a:avLst>{gds}</a:avLst></a:prstGeom>'


def _group_child_xfrm(obj: Any, tag: str = "a:xfrm") -> str:
    fx, fy, fw, fh = getattr(obj, "group_frac", None) or (0.0, 0.0, 1.0, 1.0)
    ext = _GROUP_CHILD_EXTENT
    flips = ""
    if getattr(obj, "flip_h", False):
        flips += ' flipH="1"'
    if getattr(obj, "flip_v", False):
        flips += ' flipV="1"'
    return (
        f'<{tag}{flips}><a:off x="{round(fx * ext)}" y="{round(fy * ext)}"/>'
        f'<a:ext cx="{round(fw * ext)}" cy="{round(fh * ext)}"/></{tag}>'
    )


def _object_xml(
    obj: Any,
    image_rids: dict[int, str],
    geom_map: dict[str, str],
    in_group: bool = False,
    chart_rids: dict[int, str] | None = None,
) -> str:
    """Serialize one floating object (picture, shape, chart or group) into DrawingML."""
    name_esc = _xml_escape(obj.name or f"Object {obj.id}")
    xfrm = _group_child_xfrm(obj) if in_group else ""

    if obj.kind == "chart" and chart_rids and obj.id in chart_rids:
        chart_rid = chart_rids[obj.id]
        return (
            '<xdr:graphicFrame macro="">'
            "<xdr:nvGraphicFramePr>"
            f'<xdr:cNvPr id="{obj.id}" name="{name_esc}"/>'
            "<xdr:cNvGraphicFramePr/>"
            "</xdr:nvGraphicFramePr>"
            '<xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm>'
            "<a:graphic>"
            f'<a:graphicData uri="{NS_C}">'
            f'<c:chart xmlns:c="{NS_C}" xmlns:r="{NS_R}" r:id="{chart_rid}"/>'
            "</a:graphicData>"
            "</a:graphic>"
            "</xdr:graphicFrame>"
        )

    if obj.kind == "group":
        ext = _GROUP_CHILD_EXTENT
        own = (
            _group_child_xfrm(obj)
            if in_group
            else f'<a:xfrm><a:off x="0" y="0"/><a:ext cx="{ext}" cy="{ext}"/>'
            f'<a:chOff x="0" y="0"/><a:chExt cx="{ext}" cy="{ext}"/></a:xfrm>'
        )
        if in_group:
            child_space = f'<a:chOff x="0" y="0"/><a:chExt cx="{ext}" cy="{ext}"/>'
            own = own.replace("</a:xfrm>", f"{child_space}</a:xfrm>")
        kids = "".join(
            _object_xml(c, image_rids, geom_map, in_group=True, chart_rids=chart_rids)
            for c in sorted(obj.children, key=lambda o: o.z_index)
        )
        return (
            f'<xdr:grpSp><xdr:nvGrpSpPr><xdr:cNvPr id="{obj.id}" name="{name_esc}"/>'
            f"<xdr:cNvGrpSpPr/></xdr:nvGrpSpPr><xdr:grpSpPr>{own}</xdr:grpSpPr>"
            f"{kids}</xdr:grpSp>"
        )

    if obj.kind == "image" and obj.id in image_rids:
        img_rid = image_rids[obj.id]
        locks = '<a:picLocks noChangeAspect="1"/>' if getattr(obj, "lock_aspect", False) else ""
        nv_pic_pr = (
            f'<xdr:nvPicPr><xdr:cNvPr id="{obj.id}" name="{name_esc}"/>'
            f"<xdr:cNvPicPr>{locks}</xdr:cNvPicPr></xdr:nvPicPr>"
        )
        blip_fill = (
            f"<xdr:blipFill>"
            f'<a:blip xmlns:r="{NS_R}" r:embed="{img_rid}"/>'
            f"<a:stretch><a:fillRect/></a:stretch>"
            f"</xdr:blipFill>"
        )
        return (
            f"<xdr:pic>{nv_pic_pr}{blip_fill}"
            f'<xdr:spPr>{xfrm}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr>'
            f"</xdr:pic>"
        )

    is_tb = "1" if obj.kind == "textbox" else "0"

    # Text body
    tx_body = ""
    if getattr(obj, "text", "") or obj.kind == "textbox":
        txt_clean = _hex6(getattr(obj, "text_color", "#000000"), "000000")
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
            f"{''.join(p_items)}"
            f"</xdr:txBody>"
        )

    nv_sp_pr = (
        f'<xdr:nvSpPr><xdr:cNvPr id="{obj.id}" name="{name_esc}"/>'
        f'<xdr:cNvSpPr txBox="{is_tb}"/></xdr:nvSpPr>'
    )
    return (
        f'<xdr:sp macro="" textlink="">'
        f"{nv_sp_pr}"
        f"<xdr:spPr>{xfrm}"
        f"{_drawing_geom_xml(obj, geom_map)}"
        f"{_drawing_fill_xml(obj)}{_drawing_line_xml(obj)}"
        f"</xdr:spPr>"
        f"{tx_body}"
        f"</xdr:sp>"
    )


def _serialize_drawings(
    drawings: list[Any],
    image_rids: dict[int, str],
    chart_rids: dict[int, str] | None = None,
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
            obj.anchor_type.value if hasattr(obj.anchor_type, "value") else str(obj.anchor_type)
        )

        parts.append(
            f'<xdr:twoCellAnchor editAs="{anchor_type_val}">'
            f"<xdr:from><xdr:col>{f_col}</xdr:col><xdr:colOff>{f_col_off}</xdr:colOff>"
            f"<xdr:row>{f_row}</xdr:row><xdr:rowOff>{f_row_off}</xdr:rowOff></xdr:from>"
            f"<xdr:to><xdr:col>{t_col}</xdr:col><xdr:colOff>{t_col_off}</xdr:colOff>"
            f"<xdr:row>{t_row}</xdr:row><xdr:rowOff>{t_row_off}</xdr:rowOff></xdr:to>"
        )

        parts.append(_object_xml(obj, image_rids, geom_map, chart_rids=chart_rids))

        parts.append("<xdr:clientData/></xdr:twoCellAnchor>")

    parts.append("</xdr:wsDr>")
    return "".join(parts).encode("utf-8")


_WORKBOOK_ORDER = [
    "fileVersion",
    "fileSharing",
    "workbookPr",
    "AlternateContent",
    "revisionPtr",
    "absPath",
    "workbookProtection",
    "bookViews",
    "sheets",
    "functionGroups",
    "externalReferences",
    "definedNames",
    "calcPr",
    "oleSize",
    "customWorkbookViews",
    "pivotCaches",
    "smartTagPr",
    "smartTagTypes",
    "webPublishing",
    "fileRecoveryPr",
    "webPublishObjects",
    "extLst",
]


def _serialize_comments_xml(comments: dict[Any, Any]) -> bytes:
    """Serialize worksheet comments into SpreadsheetML comments XML (xl/commentsN.xml)."""
    authors: list[str] = []
    author_index: dict[str, int] = {}
    items = sorted(comments.items(), key=lambda kv: kv[0])
    for _, cm in items:
        author = str(getattr(cm, "author", "") or "")
        if author not in author_index:
            author_index[author] = len(authors)
            authors.append(author)
    if not authors:
        authors.append("")
        author_index[""] = 0

    parts = [
        XML_HEADER,
        f'<comments xmlns="{NS_MAIN}"><authors>',
    ]
    for a in authors:
        parts.append(f"<author>{_xml_escape(_clean_text(a))}</author>")
    parts.append("</authors><commentList>")
    for (r, c), cm in items:
        author = str(getattr(cm, "author", "") or "")
        aid = author_index[author]
        ref = cell_name(r, c)
        text = str(getattr(cm, "text", "") or "")
        parts.append(
            f'<comment ref="{ref}" authorId="{aid}"><text>{_text_element(text)}</text></comment>'
        )
    parts.append("</commentList></comments>")
    return "".join(parts).encode("utf-8")


def _serialize_comments_vml(comments: dict[Any, Any]) -> bytes:
    """Serialize VML note shapes so comment visibility survives XLSX round-trip."""
    parts = [
        '<xml xmlns:v="urn:schemas-microsoft-com:vml"\r\n',
        ' xmlns:o="urn:schemas-microsoft-com:office:office"\r\n',
        ' xmlns:x="urn:schemas-microsoft-com:office:excel">\r\n',
        ' <o:shapelayout v:ext="edit"><o:idmap v:ext="edit" data="1"/></o:shapelayout>\r\n',
        ' <v:shapetype id="_x0000_t202" coordsize="21600,21600" o:spt="202"\r\n',
        '  path="m,l,21600r21600,l21600,xe">\r\n',
        '  <v:stroke joinstyle="miter"/>\r\n',
        '  <v:path gradientshapeok="t" o:connecttype="rect"/>\r\n',
        " </v:shapetype>\r\n",
    ]
    for idx, ((r, c), cm) in enumerate(sorted(comments.items(), key=lambda kv: kv[0]), start=1):
        vis = bool(getattr(cm, "visible", False))
        vis_css = "visible" if vis else "hidden"
        vis_tag = "<x:Visible/>" if vis else ""
        parts.append(
            f' <v:shape id="_x0000_s{1024 + idx}" type="#_x0000_t202"'
            f" style='position:absolute;width:96pt;height:55.5pt;z-index:{idx};"
            f'visibility:{vis_css}\' fillcolor="infoBackground [80]" o:insetmode="auto">\r\n'
            '  <v:fill color2="infoBackground [80]"/>\r\n'
            '  <v:shadow on="t" color="black" obscured="t"/>\r\n'
            '  <v:path o:connecttype="none"/>\r\n'
            "  <v:textbox style='mso-direction-alt:auto'>"
            "<div style='text-align:left'></div></v:textbox>\r\n"
            '  <x:ClientData ObjectType="Note">\r\n'
            "   <x:MoveWithCells/><x:SizeWithCells/>\r\n"
            "   <x:AutoFill>False</x:AutoFill>\r\n"
            f"   {vis_tag}<x:Row>{r}</x:Row><x:Column>{c}</x:Column>\r\n"
            "  </x:ClientData>\r\n"
            " </v:shape>\r\n"
        )
    parts.append("</xml>")
    return "".join(parts).encode("utf-8")


@dataclass
class _SheetEntry:
    """Where one worksheet lives in the written package."""

    sheet: SheetDataModel
    part: str
    rel_id: str
    sheet_id: str
    from_source: bool


def _sheet_element_attrs(entry: _SheetEntry) -> list[tuple[str, str]]:
    attrs = [("name", entry.sheet.name), ("sheetId", entry.sheet_id)]
    state = entry.sheet.extra.get("sheet_state")
    if state and state != "visible":
        attrs.append(("state", state))
    return attrs


def _serialize_workbook(workbook: WorkbookModel, entries: list[_SheetEntry]) -> bytes:
    """Serialize a new xl/workbook.xml (used when there is no source package)."""
    fv_code_name = workbook.extra.get("file_version_code_name")
    fv_attr = f' codeName="{_xml_escape(fv_code_name)}"' if fv_code_name else ""
    wb_code_name = getattr(workbook, "code_name", None) or workbook.extra.get("code_name")
    wpr_attrs = ['defaultThemeVersion="124226"']
    if wb_code_name:
        wpr_attrs.append(f'codeName="{_xml_escape(wb_code_name)}"')
    if workbook.extra.get("date1904"):
        wpr_attrs.append('date1904="1"')

    parts = [
        XML_HEADER,
        f'<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_R}">',
        f'<fileVersion appName="xl" lastEdited="4" lowestEdited="4" rupBuild="4505"{fv_attr}/>',
        f"<workbookPr {' '.join(wpr_attrs)}/>",
    ]

    prot = workbook.extra.get("protection")
    if prot:
        prot_str = " ".join(f'{k}="{_xml_escape(str(v))}"' for k, v in prot.items())
        parts.append(f"<workbookProtection {prot_str}/>")

    active_idx = workbook.active_sheet_index
    parts.append(f'<bookViews><workbookView activeTab="{active_idx}"/></bookViews>')
    parts.append("<sheets>")
    for entry in entries:
        attrs = " ".join(f'{k}="{_xml_escape(v)}"' for k, v in _sheet_element_attrs(entry))
        parts.append(f'<sheet {attrs} r:id="{entry.rel_id}"/>')
    parts.append("</sheets>")

    def_names = workbook.extra.get("defined_names")
    if def_names:
        parts.append(def_names)

    pc_xml = _pivot_caches_xml(workbook)
    if pc_xml:
        parts.append(pc_xml)

    parts.append('<calcPr calcId="124519" fullCalcOnLoad="1"/>')
    parts.append("</workbook>")
    return "".join(parts).encode("utf-8")


def _pivot_caches_xml(workbook: WorkbookModel) -> str:
    pivots = workbook.extra.get("pivots")
    if not pivots:
        return ""
    elems = [
        f'<pivotCache cacheId="{c.cache_id}" r:id="{c.rel_id}"/>'
        for c in pivots.caches
        if not c.drop and c.rel_id
    ]
    return f"<pivotCaches>{''.join(elems)}</pivotCaches>" if elems else ""


def _patch_workbook_xml(
    original: bytes, workbook: WorkbookModel, entries: list[_SheetEntry]
) -> bytes:
    """Update the original workbook.xml in place.

    Only the sheet list, the active tab, defined names (when edited) and pivot caches are
    model-driven; ``calcPr``, ``extLst``, ``fileSharing``, sheet visibility and anything
    else is carried as-is. Returns ``original`` unchanged when nothing differs.
    """
    root = parse_lxml(original)
    ns = namespace_of(root)
    q = (lambda n: f"{{{ns}}}{n}") if ns else (lambda n: n)
    r_id_attr = f"{{{NS_R}}}id"
    changed = False

    sheets_el = ensure_child(root, "sheets", _WORKBOOK_ORDER)
    old_by_rid: dict[str, Any] = {}
    for el in find_all_local(sheets_el, "sheet"):
        rid = el.get(r_id_attr) or next(
            (v for k, v in el.attrib.items() if k.endswith("}id")), None
        )
        if rid:
            old_by_rid[rid] = el
    old_order = [el.get(r_id_attr) for el in find_all_local(sheets_el, "sheet")]

    new_children = []
    for entry in entries:
        el = old_by_rid.get(entry.rel_id) if entry.from_source else None
        if el is None:
            el = LET.Element(q("sheet"))
            changed = True
        for key, value in _sheet_element_attrs(entry):
            if el.get(key) != value:
                el.set(key, value)
                changed = True
        if el.get(r_id_attr) != entry.rel_id:
            el.set(r_id_attr, entry.rel_id)
            changed = True
        new_children.append(el)
    if [e.rel_id for e in entries] != old_order:
        changed = True
    if changed:
        for el in find_all_local(sheets_el, "sheet"):
            sheets_el.remove(el)
        for el in new_children:
            sheets_el.append(el)

    views = ensure_child(root, "bookViews", _WORKBOOK_ORDER)
    view = find_local(views, "workbookView")
    if view is None:
        view = LET.SubElement(views, q("workbookView"))
    active = str(workbook.active_sheet_index)
    if (view.get("activeTab") or "0") != active:
        view.set("activeTab", active)
        changed = True

    names = workbook.extra.get("defined_names")
    if names != workbook.extra.get("defined_names_loaded"):
        old = find_local(root, "definedNames")
        if old is not None:
            root.remove(old)
        if names:
            for el in parse_fragment(names, ns):
                insert_in_order(root, el, _WORKBOOK_ORDER)
        changed = True

    if workbook.extra.get("pivots"):
        pc_xml = _pivot_caches_xml(workbook)
        old = find_local(root, "pivotCaches")

        def _keys(parent: Any) -> list[tuple[str | None, str | None]]:
            return [
                (el.get("cacheId"), el.get(r_id_attr))
                for el in find_all_local(parent, "pivotCache")
            ]

        new_els = parse_fragment(pc_xml, ns, {"r": NS_R}) if pc_xml else []
        new_keys = _keys(new_els[0]) if new_els else []
        if new_keys != _keys(old):
            if old is not None:
                root.remove(old)
            for el in new_els:
                insert_in_order(root, el, _WORKBOOK_ORDER)
            changed = True

    return serialize_lxml(root) if changed else original


def _relationships_xml(rels: list[tuple[str, str, str, str]]) -> bytes:
    """Serialize a .rels part from ``(id, type, target, target_mode)`` tuples."""
    parts = [XML_HEADER, f'<Relationships xmlns="{NS_PKG_REL}">']
    for rid, rtype, target, mode in rels:
        mode_attr = f' TargetMode="{_xml_escape(mode)}"' if mode and mode != "Internal" else ""
        parts.append(
            f'<Relationship Id="{_xml_escape(rid)}" Type="{_xml_escape(rtype)}" '
            f'Target="{_xml_escape(target)}"{mode_attr}/>'
        )
    parts.append("</Relationships>")
    return "".join(parts).encode("utf-8")


def _unique_id(used: set[str], prefix: str = "rId") -> str:
    n = 1
    while f"{prefix}{n}" in used:
        n += 1
    rid = f"{prefix}{n}"
    used.add(rid)
    return rid


def _unique_part(pattern: str, used: set[str]) -> str:
    """Return ``pattern.format(n)`` for the smallest n not already in ``used``."""
    n = 1
    while pattern.format(n).lower() in used:
        n += 1
    name = pattern.format(n)
    used.add(name.lower())
    return name


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
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
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
        f"  <a:themeElements>\n"
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
        f"    </a:clrScheme>\n"
        f'    <a:fontScheme name="Office">\n'
        f"      <a:majorFont>\n"
        f'        <a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/>\n'
        f"      </a:majorFont>\n"
        f"      <a:minorFont>\n"
        f'        <a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/>\n'
        f"      </a:minorFont>\n"
        f"    </a:fontScheme>\n"
        f'    <a:fmtScheme name="Office">\n'
        f"      <a:fillStyleLst>\n"
        f'        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>\n'
        f"      </a:fillStyleLst>\n"
        f"      <a:lnStyleLst>\n"
        f'        <a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>\n'
        f"      </a:lnStyleLst>\n"
        f"      <a:effectStyleLst>\n"
        f"        <a:effectStyle><a:effectLst/></a:effectStyle>\n"
        f"      </a:effectStyleLst>\n"
        f"      <a:bgFillStyleLst>\n"
        f'        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>\n'
        f"      </a:bgFillStyleLst>\n"
        f"    </a:fmtScheme>\n"
        f"  </a:themeElements>\n"
        f"</a:theme>"
    ).encode()


_WORKSHEET_ORDER = [
    "sheetPr",
    "dimension",
    "sheetViews",
    "sheetFormatPr",
    "cols",
    "sheetData",
    "sheetCalcPr",
    "sheetProtection",
    "protectedRanges",
    "scenarios",
    "autoFilter",
    "sortState",
    "dataConsolidate",
    "customSheetViews",
    "mergeCells",
    "phoneticPr",
    "conditionalFormatting",
    "dataValidations",
    "hyperlinks",
    "printOptions",
    "pageMargins",
    "pageSetup",
    "headerFooter",
    "rowBreaks",
    "colBreaks",
    "customProperties",
    "cellWatches",
    "ignoredErrors",
    "smartTags",
    "drawing",
    "legacyDrawing",
    "legacyDrawingHF",
    "drawingHF",
    "picture",
    "oleObjects",
    "controls",
    "webPublishItems",
    "tableParts",
    "extLst",
]


def _dimension_ref(sheet: SheetDataModel) -> str:
    coords = list(sheet.cells.keys())
    for m in sheet.merges:
        coords.append((m[0], m[1]))
        coords.append((m[2], m[3]))
    if not coords:
        return "A1"
    min_r = min(r for r, _ in coords)
    max_r = max(r for r, _ in coords)
    min_c = min(c for _, c in coords)
    max_c = max(c for _, c in coords)
    return f"{cell_name(min_r, min_c)}:{cell_name(max_r, max_c)}"


def _splice_sheet_data(original: bytes, sheet_data_xml: str, dim_ref: str) -> bytes:
    """Replace ``<sheetData>`` (and the dimension) of an original worksheet, keeping the rest.

    Works on the parsed tree, so prefixed markup (``<x:sheetData>``) and Strict
    namespaces are handled and nothing outside ``sheetData`` is re-serialized by hand.
    """
    root = parse_lxml(original)
    ns = namespace_of(root)
    new_sd = parse_fragment(sheet_data_xml, ns)[0]
    old = find_local(root, "sheetData")
    if old is None:
        insert_in_order(root, new_sd, _WORKSHEET_ORDER)
    else:
        root.replace(old, new_sd)
    dim = find_local(root, "dimension")
    if dim is not None:
        dim.set("ref", dim_ref)
    return serialize_lxml(root)


def _splice_conditional_formatting(
    ws_bytes: bytes,
    sheet: SheetDataModel,
    style_manager: StyleManager,
) -> bytes:
    """Replace worksheet ``<conditionalFormatting>`` blocks when CF was edited."""
    root = parse_lxml(ws_bytes)
    ns = namespace_of(root)
    for old_cf in find_all_local(root, "conditionalFormatting"):
        root.remove(old_cf)
    cf_parts, x14_icon_formats = _serialize_conditional_formatting_blocks(sheet, style_manager)
    for block in cf_parts:
        for el in parse_fragment(block, ns):
            insert_in_order(root, el, _WORKSHEET_ORDER)
    if x14_icon_formats:
        ext_lst = find_local(root, "extLst")
        if ext_lst is not None:
            for ext_el in list(ext_lst):
                if ext_el.get("uri") == _X14_CF_EXT_URI:
                    ext_lst.remove(ext_el)
            x14_doc = parse_fragment(_x14_icon_set_ext_xml(x14_icon_formats), None)[0]
            for ext_el in list(x14_doc):
                ext_lst.append(ext_el)
        else:
            for el in parse_fragment(_x14_icon_set_ext_xml(x14_icon_formats), None):
                insert_in_order(root, el, _WORKSHEET_ORDER)
    return serialize_lxml(root)


def _ensure_worksheet_rel_ref(ws_bytes: bytes, tag: str, rel_id: str) -> bytes:
    """Add ``<tag r:id>`` to a worksheet in schema order if not already present."""
    root = parse_lxml(ws_bytes)
    if find_local(root, tag) is not None:
        return ws_bytes
    ns = namespace_of(root)
    el = LET.Element(f"{{{ns}}}{tag}" if ns else tag)
    el.set(f"{{{NS_R}}}id", rel_id)
    insert_in_order(root, el, _WORKSHEET_ORDER)
    return serialize_lxml(root)


def _ensure_drawing_ref(ws_bytes: bytes, rel_id: str) -> bytes:
    """Add ``<drawing r:id>`` to a worksheet that did not have drawings before."""
    return _ensure_worksheet_rel_ref(ws_bytes, "drawing", rel_id)


def _ensure_legacy_drawing_ref(ws_bytes: bytes, rel_id: str) -> bytes:
    """Add ``<legacyDrawing r:id>`` to a worksheet that did not have VML notes before."""
    return _ensure_worksheet_rel_ref(ws_bytes, "legacyDrawing", rel_id)


def _remove_worksheet_rel_ref(ws_bytes: bytes, tag: str) -> bytes:
    """Remove ``<tag .../>`` elements from a worksheet if present."""
    root = parse_lxml(ws_bytes)
    matches = find_all_local(root, tag)
    if not matches:
        return ws_bytes
    for el in matches:
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
    return serialize_lxml(root)


def _rel_type_is(rel_type: str, name: str) -> bool:
    return rel_type.rsplit("/", 1)[-1] == name


def write_xlsx(
    workbook: WorkbookModel,
    output_path: str | Path | BinaryIO | None = None,
    source_opc: SourcePackage | bytes | str | Path | None = None,
) -> bytes:
    """Serialize a WorkbookModel to an OOXML .xlsx package.

    When the workbook came from a file, the original package is the starting point:
    parts the model does not own are carried byte-for-byte, and the parts it does own
    (worksheets, styles, workbook.xml) are edited in place so that unmodelled content
    survives. Original part names and relationship ids are kept.

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
    elif getattr(workbook, "_source_package", None) is not None:
        source_pkg = workbook._source_package
    elif workbook.extra.get("source_package") is not None:
        source_pkg = workbook.extra.get("source_package")

    wb_part = "xl/workbook.xml"
    if source_pkg is not None:
        src_wb = workbook.extra.get("xlsx_workbook_part")
        if src_wb and source_pkg.has_part(src_wb):
            wb_part = src_wb
        elif not source_pkg.has_part(wb_part):
            source_pkg = None  # unrelated package: write from scratch
    wb_from_source = source_pkg is not None and source_pkg.has_part(wb_part)

    is_xlsm = False
    if output_path is not None and str(output_path).lower().endswith(".xlsm"):
        is_xlsm = True
    elif workbook.extra.get("is_macro_enabled"):
        is_xlsm = True
    elif source_pkg and (
        source_pkg.has_part("xl/vbaProject.bin")
        or source_pkg.get_content_type(wb_part)
        == "application/vnd.ms-excel.sheet.macroEnabled.main+xml"
    ):
        is_xlsm = True

    ct_workbook = "application/vnd.ms-excel.sheet.macroEnabled.main+xml" if is_xlsm else CT_WORKBOOK

    pkg_writer = PackageWriter(source_package=source_pkg)
    used_parts: set[str] = {p.lower() for p in source_pkg.parts()} if source_pkg else set()

    # Original workbook relationships, resolved to part names.
    orig_wb_rels = source_pkg.get_relationships(wb_part) if wb_from_source else []

    def _orig_target(name: str) -> str | None:
        for r in orig_wb_rels:
            if _rel_type_is(r.type, name) and not r.is_external:
                return r.resolve_target(wb_part)
        return None

    styles_part = _orig_target("styles") or "xl/styles.xml"
    sst_part = _orig_target("sharedStrings") or "xl/sharedStrings.xml"
    theme_part = _orig_target("theme")

    wb_theme_colors = getattr(workbook, "theme_colors", None)
    wb_palette = getattr(workbook, "indexed_palette", None)
    sst_manager = SharedStringsManager(theme_colors=wb_theme_colors, palette=wb_palette)
    style_deltas = workbook.extra.get("xlsx_style_deltas")
    if source_pkg is not None and style_deltas and source_pkg.has_part(styles_part):
        style_manager = StyleManager.from_source(
            source_pkg.read_part(styles_part),
            style_deltas,
            theme_colors=wb_theme_colors,
            indexed_palette=wb_palette,
        )
    else:
        style_manager = StyleManager(theme_colors=wb_theme_colors, indexed_palette=wb_palette)
    any_dirty = bool(
        getattr(workbook, "dirty", False)
        or any(getattr(s, "dirty", False) for s in workbook.sheets)
    )

    # 0. Decide where every sheet lives and which relationship points at it.
    orig_sheet_rels = {
        r.id: r.resolve_target(wb_part)
        for r in orig_wb_rels
        if _rel_type_is(r.type, "worksheet") and not r.is_external
    }
    used_wb_rids = {r.id for r in orig_wb_rels}
    used_sheet_ids: set[str] = {
        str(s.extra["sheet_id"]) for s in workbook.sheets if s.extra.get("sheet_id")
    }
    entries: list[_SheetEntry] = []
    claimed_parts: set[str] = set()
    for sheet in workbook.sheets:
        ooxml_part = getattr(sheet, "_ooxml_part", None) or sheet.extra.get("ooxml_part")
        rel_id = sheet.extra.get("sheet_rel_id")
        from_source = bool(
            source_pkg
            and ooxml_part
            and source_pkg.has_part(ooxml_part)
            and ooxml_part not in claimed_parts
        )
        if from_source:
            part = ooxml_part
            if not rel_id or orig_sheet_rels.get(rel_id) != part:
                rel_id = next((k for k, v in orig_sheet_rels.items() if v == part), None)
            if not rel_id:
                rel_id = _unique_id(used_wb_rids)
        else:
            part = _unique_part("xl/worksheets/sheet{}.xml", used_parts)
            rel_id = _unique_id(used_wb_rids)
        claimed_parts.add(part)
        sheet_id = str(sheet.extra.get("sheet_id") or "")
        if not sheet_id or (not from_source and sheet_id in used_sheet_ids):
            n = 1
            while str(n) in used_sheet_ids:
                n += 1
            sheet_id = str(n)
        used_sheet_ids.add(sheet_id)
        entries.append(_SheetEntry(sheet, part, rel_id, sheet_id, from_source))

    # Worksheets that were deleted from the model are removed from the package.
    kept_parts = {e.part for e in entries}
    for part in orig_sheet_rels.values():
        if part not in kept_parts and source_pkg.has_part(part):
            pkg_writer.delete_part(part)
            pkg_writer.delete_part(get_rels_path(part))

    pivots: Any = workbook.extra.get("pivots")

    # 1. Serialize each worksheet and associated drawings
    for idx, entry in enumerate(entries):
        sheet = entry.sheet
        part_name = entry.part
        is_active = idx == workbook.active_sheet_index
        sheet_rels_part = get_rels_path(part_name)
        src_sheet_rels = source_pkg.get_relationships(part_name) if entry.from_source else []
        orig_drawing_rel = next(
            (r for r in src_sheet_rels if _rel_type_is(r.type, "drawing")), None
        )
        orig_comments_rel = next(
            (r for r in src_sheet_rels if _rel_type_is(r.type, "comments")), None
        )
        orig_vml_rel = next((r for r in src_sheet_rels if _rel_type_is(r.type, "vmlDrawing")), None)
        reserved_rids: set[str] = {r.id for r in src_sheet_rels}
        has_drawings = bool(getattr(sheet, "drawings", None))
        drawings_unchanged = orig_drawing_rel is not None and sheet.extra.get(
            "xlsx_drawings_signature"
        ) == drawings_signature(sheet.drawings)
        regenerate_drawings = has_drawings and not drawings_unchanged
        drawing_rid = None
        if regenerate_drawings:
            if orig_drawing_rel:
                drawing_rid = orig_drawing_rel.id
            elif "rIdDrawing" not in reserved_rids:
                drawing_rid = "rIdDrawing"
            else:
                drawing_rid = _unique_id(reserved_rids)
            reserved_rids.add(drawing_rid)

        sheet_comments = getattr(sheet, "comments", None) or {}
        has_comments = bool(sheet_comments)
        comments_unchanged = orig_comments_rel is not None and sheet.extra.get(
            "xlsx_comments_signature"
        ) == comments_signature(sheet_comments)
        regenerate_comments = has_comments and not comments_unchanged
        delete_comments = not has_comments and orig_comments_rel is not None
        has_ctrl_props = any(_rel_type_is(r.type, "ctrlProp") for r in src_sheet_rels)
        delete_comments_vml = bool(
            delete_comments and orig_vml_rel is not None and not has_ctrl_props
        )
        comments_rid = None
        legacy_drawing_rid = None
        if regenerate_comments:
            comments_rid = orig_comments_rel.id if orig_comments_rel else _unique_id(reserved_rids)
            reserved_rids.add(comments_rid)
            if orig_vml_rel is None:
                legacy_drawing_rid = _unique_id(reserved_rids)
                reserved_rids.add(legacy_drawing_rid)

        if entry.from_source:
            if (
                not any_dirty
                and not sheet.extra.get("cf_dirty")
                and not regenerate_drawings
                and not regenerate_comments
                and not delete_comments_vml
            ):
                ws_bytes = source_pkg.read_part(part_name)
            else:
                if any_dirty:
                    ws_bytes = _splice_sheet_data(
                        source_pkg.read_part(part_name),
                        _serialize_sheet_data(sheet, style_manager, sst_manager),
                        _dimension_ref(sheet),
                    )
                    patched = _patch_page_setup(ws_bytes.decode("utf-8"), sheet)
                    ws_bytes = patched.encode("utf-8")
                else:
                    ws_bytes = source_pkg.read_part(part_name)
                if sheet.extra.get("cf_dirty"):
                    ws_bytes = _splice_conditional_formatting(ws_bytes, sheet, style_manager)
                if regenerate_drawings and orig_drawing_rel is None and drawing_rid:
                    ws_bytes = _ensure_drawing_ref(ws_bytes, drawing_rid)
                if regenerate_comments and orig_vml_rel is None and legacy_drawing_rid:
                    ws_bytes = _ensure_legacy_drawing_ref(ws_bytes, legacy_drawing_rid)
                if delete_comments_vml:
                    ws_bytes = _remove_worksheet_rel_ref(ws_bytes, "legacyDrawing")
            pkg_writer.add_part(part_name, ws_bytes, CT_WORKSHEET)
        else:
            ws_bytes = _serialize_worksheet(
                sheet,
                style_manager,
                sst_manager,
                is_active,
                drawing_rid=drawing_rid,
                legacy_drawing_rid=legacy_drawing_rid,
            )
            pkg_writer.add_part(part_name, ws_bytes, CT_WORKSHEET)

        sheet_rels: list[tuple[str, str, str, str]] = []
        used_sheet_rids: set[str] = set()

        if regenerate_drawings and drawing_rid:
            if orig_drawing_rel is not None:
                drawing_part = orig_drawing_rel.resolve_target(part_name)
                # Its old relationships (images, charts) are replaced below.
                pkg_writer.delete_part(get_rels_path(drawing_part))
            else:
                drawing_part = _unique_part("xl/drawings/drawing{}.xml", used_parts)

            image_rids: dict[int, str] = {}
            chart_rids: dict[int, str] = {}
            drawing_rels: list[tuple[str, str, str, str]] = []
            used_drawing_rids: set[str] = set()
            for obj in _iter_drawings(sheet.drawings):
                if obj.kind == "image" and getattr(obj, "image_data", None):
                    mime = getattr(obj, "image_mime", "image/png")
                    ext = "jpg" if ("jpeg" in mime or "jpg" in mime) else "png"
                    media_part = _unique_part(f"xl/media/image{{}}.{ext}", used_parts)
                    pkg_writer.add_part(media_part, obj.image_data, mime)
                    rid = _unique_id(used_drawing_rids)
                    image_rids[obj.id] = rid
                    drawing_rels.append(
                        (rid, REL_IMAGE, relative_part_uri(drawing_part, media_part), "")
                    )
                elif obj.kind == "chart":
                    from atboffice.modules.presentation.chart.io import chart_to_xml

                    chart_part = _unique_part("xl/charts/chart{}.xml", used_parts)
                    chart_xml_str = chart_to_xml(obj.chart_data or {})
                    pkg_writer.add_part(chart_part, chart_xml_str.encode("utf-8"), CT_CHART)
                    rid = _unique_id(used_drawing_rids)
                    chart_rids[obj.id] = rid
                    drawing_rels.append(
                        (rid, REL_CHART, relative_part_uri(drawing_part, chart_part), "")
                    )

            pkg_writer.add_part(
                drawing_part,
                _serialize_drawings(sheet.drawings, image_rids, chart_rids),
                CT_DRAWING,
            )
            if drawing_rels:
                pkg_writer.add_part(
                    get_rels_path(drawing_part),
                    _relationships_xml(drawing_rels),
                    CT_RELATIONSHIPS,
                )
            sheet_rels.append(
                (drawing_rid, REL_DRAWING, relative_part_uri(part_name, drawing_part), "")
            )
            used_sheet_rids.add(drawing_rid)

        if regenerate_comments and comments_rid:
            comments_part = (
                orig_comments_rel.resolve_target(part_name)
                if orig_comments_rel is not None
                else _unique_part("xl/comments{}.xml", used_parts)
            )
            pkg_writer.add_part(comments_part, _serialize_comments_xml(sheet_comments), CT_COMMENTS)
            sheet_rels.append(
                (comments_rid, REL_COMMENTS, relative_part_uri(part_name, comments_part), "")
            )
            used_sheet_rids.add(comments_rid)
            if orig_vml_rel is None and legacy_drawing_rid:
                vml_part = _unique_part("xl/drawings/vmlDrawing{}.vml", used_parts)
                pkg_writer.add_part(
                    vml_part, _serialize_comments_vml(sheet_comments), CT_VML_DRAWING
                )
                vml_rel_uri = relative_part_uri(part_name, vml_part)
                sheet_rels.append((legacy_drawing_rid, REL_VML_DRAWING, vml_rel_uri, ""))
                used_sheet_rids.add(legacy_drawing_rid)
            elif orig_vml_rel is not None and not has_ctrl_props:
                pkg_writer.add_part(
                    orig_vml_rel.resolve_target(part_name),
                    _serialize_comments_vml(sheet_comments),
                    CT_VML_DRAWING,
                )
        elif delete_comments and orig_comments_rel is not None:
            pkg_writer.delete_part(orig_comments_rel.resolve_target(part_name))
            if delete_comments_vml and orig_vml_rel is not None:
                vml_target = orig_vml_rel.resolve_target(part_name)
                if source_pkg is None or source_pkg.has_part(vml_target):
                    pkg_writer.delete_part(vml_target)

        # Pivot tables attached to this sheet
        if pivots:
            for t in getattr(pivots, "tables", []):
                if not t.drop and t.sheet_name.lower() == sheet.name.lower():
                    t_rid = t.rel_id or f"rIdPivot{t.cache_id}"
                    sheet_rels.append(
                        (t_rid, REL_PIVOT_TABLE, relative_part_uri(part_name, t.part_name), "")
                    )
                    used_sheet_rids.add(t_rid)

        # Every other original sheet relationship is kept with its id.
        for r in src_sheet_rels:
            if _rel_type_is(r.type, "drawing") and regenerate_drawings:
                continue
            if _rel_type_is(r.type, "comments") and (regenerate_comments or delete_comments):
                continue
            if _rel_type_is(r.type, "vmlDrawing") and delete_comments_vml:
                continue
            if _rel_type_is(r.type, "pivotTable") and pivots:
                continue
            r_id = r.id if r.id not in used_sheet_rids else _unique_id(used_sheet_rids)
            used_sheet_rids.add(r_id)
            sheet_rels.append((r_id, r.type, r.target, r.target_mode))

        if sheet_rels:
            new_rels = _relationships_xml(sheet_rels)
            unchanged = entry.from_source and [
                (a, b, c, d or "Internal") for a, b, c, d in sheet_rels
            ] == [(r.id, r.type, r.target, r.target_mode) for r in src_sheet_rels]
            if not unchanged:
                pkg_writer.add_part(sheet_rels_part, new_rels, CT_RELATIONSHIPS)
        elif entry.from_source and src_sheet_rels:
            pkg_writer.delete_part(sheet_rels_part)

    # 2. sharedStrings.xml (rebuilt from the cells that were serialized)
    sst_bytes = sst_manager.to_xml()
    if sst_bytes:
        pkg_writer.add_part(sst_part, sst_bytes, CT_SHARED_STRINGS)
    sst_present = bool(sst_bytes) or bool(source_pkg and source_pkg.has_part(sst_part))

    # 3. styles.xml: carried when nothing changed, otherwise the original is extended.
    if (
        source_pkg
        and source_pkg.has_part(styles_part)
        and not (any_dirty or style_manager.has_new_records())
    ):
        pass  # carried byte-for-byte
    else:
        pkg_writer.add_part(styles_part, style_manager.to_styles_xml(), CT_STYLES)

    # 4. Theme: only generated for workbooks that have none.
    if not theme_part or not (source_pkg and source_pkg.has_part(theme_part)):
        theme_part = "xl/theme/theme1.xml"
        if not (source_pkg and source_pkg.has_part(theme_part)):
            pkg_writer.add_part(theme_part, _serialize_theme(), CT_THEME)

    # 5. workbook.xml and its relationships
    if wb_from_source:
        wb_bytes = _patch_workbook_xml(source_pkg.read_part(wb_part), workbook, entries)
        if (
            wb_bytes is not source_pkg.read_part(wb_part)
            or source_pkg.get_content_type(wb_part) != ct_workbook
        ):
            pkg_writer.replace_part(wb_part, wb_bytes, ct_workbook)
    else:
        pkg_writer.add_part(wb_part, _serialize_workbook(workbook, entries), ct_workbook)

    wb_rels: list[tuple[str, str, str, str]] = []
    sheet_rel_ids = {e.rel_id for e in entries}
    for r in orig_wb_rels:
        if _rel_type_is(r.type, "worksheet") and r.id not in sheet_rel_ids:
            continue  # deleted sheet
        if _rel_type_is(r.type, "pivotCacheDefinition") and pivots:
            continue  # re-added from the model below
        if _rel_type_is(r.type, "sharedStrings") and not sst_present:
            continue
        wb_rels.append((r.id, r.type, r.target, r.target_mode))
    have_types = {r[1].rsplit("/", 1)[-1] for r in wb_rels}
    have_ids = {r[0] for r in wb_rels} | used_wb_rids
    present = {r[0] for r in wb_rels}
    for e in entries:
        if e.rel_id not in present:
            wb_rels.append((e.rel_id, REL_WORKSHEET, relative_part_uri(wb_part, e.part), ""))
    if "styles" not in have_types:
        wb_rels.append(
            (_unique_id(have_ids), REL_STYLES, relative_part_uri(wb_part, styles_part), "")
        )
    if "theme" not in have_types:
        wb_rels.append(
            (_unique_id(have_ids), REL_THEME, relative_part_uri(wb_part, theme_part), "")
        )
    if sst_present and "sharedStrings" not in have_types:
        wb_rels.append(
            (_unique_id(have_ids), REL_SHARED_STRINGS, relative_part_uri(wb_part, sst_part), "")
        )
    if pivots:
        for c in pivots.caches:
            if not c.drop and c.rel_id:
                wb_rels.append(
                    (c.rel_id, REL_PIVOT_CACHE, relative_part_uri(wb_part, c.part_name), "")
                )
    wb_rels_part = get_rels_path(wb_part)
    wb_rels_unchanged = wb_from_source and [
        (a, b, c, d or "Internal") for a, b, c, d in wb_rels
    ] == [(r.id, r.type, r.target, r.target_mode) for r in orig_wb_rels]
    if not wb_rels_unchanged:
        pkg_writer.add_part(wb_rels_part, _relationships_xml(wb_rels), CT_RELATIONSHIPS)

    # 5b. Pivot parts (lossless carry or modified)
    if pivots:
        write_pivots_to_package(pkg_writer, workbook, pivots)

    # 5c. Preserve vbaProject.bin if XLSM
    if is_xlsm and source_pkg and source_pkg.has_part("xl/vbaProject.bin"):
        pkg_writer.replace_part(
            "xl/vbaProject.bin",
            source_pkg.read_part("xl/vbaProject.bin"),
            "application/vnd.ms-office.vbaProject",
        )

    # 6. Core package plumbing for new workbooks
    if not source_pkg or not source_pkg.has_part("docProps/core.xml"):
        pkg_writer.add_part("docProps/core.xml", _serialize_core_props(), CT_CORE_PROPS)

    sheet_names = [s.name for s in workbook.sheets]
    if not source_pkg or not source_pkg.has_part("docProps/app.xml"):
        pkg_writer.add_part("docProps/app.xml", _serialize_app_props(sheet_names), CT_APP_PROPS)

    if not source_pkg or not source_pkg.has_part("_rels/.rels"):
        pkg_writer.add_part("_rels/.rels", _serialize_root_rels(), CT_RELATIONSHIPS)

    # 7. Generate ZIP bytes
    payload = pkg_writer.to_bytes()

    # 8. Write to output if requested
    if output_path is not None:
        if hasattr(output_path, "write"):
            output_path.write(payload)
        else:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            pkg_writer.save(path)

    return payload
