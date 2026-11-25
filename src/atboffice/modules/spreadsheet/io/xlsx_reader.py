"""Pure Python Open Packaging Conventions (OPC) XLSX reader for ATBOffice Ledger."""

from __future__ import annotations

import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, BinaryIO

from atboffice.drawing.dml import theme_map as dml_theme_map
from atboffice.modules.spreadsheet.calc.references import (
    parse_cell,
    parse_range,
    translate,
)
from atboffice.modules.spreadsheet.io.xlsx_drawing_shapes import (
    DrawingContext,
    drawings_signature,
    element_xfrm,
    first_shape_element,
    parse_shape_element,
)
from atboffice.modules.spreadsheet.io.xlsx_tables import (
    parse_table_styles,
    parse_worksheet_tables,
)
from atboffice.modules.spreadsheet.models.color_utils import (
    DEFAULT_INDEXED_PALETTE,
    DEFAULT_THEME_COLORS,
    normalize_hex_color,
    parse_color_element,
    parse_theme_xml,
    resolve_color_spec,
)
from atboffice.modules.spreadsheet.models.conditional_format import (
    CFVO,
    CFRule,
    ColorScaleRule,
    ConditionalFormat,
    DataBarRule,
    IconSetRule,
)
from atboffice.modules.spreadsheet.models.excel_units import (
    default_col_px,
    excel_mdw,
    font_row_pt,
    width_to_px,
)
from atboffice.modules.spreadsheet.models.pivot_model import read_pivots_from_zip
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    FormatDelta,
    RichTextRun,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.validation import DataValidation
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.object_layer import (
    AnchorType,
    CellAnchorPoint,
    FloatingObject,
)
from atboffice.vfs.opc import SourcePackage

logger = logging.getLogger(__name__)

# Builtin OOXML number formats (ECMA-376 Part 1 §18.8.30)
BUILTIN_NUMFMTS: dict[int, str] = {
    0: "General",
    1: "0",
    2: "0.00",
    3: "#,##0",
    4: "#,##0.00",
    9: "0%",
    10: "0.00%",
    11: "0.00E+00",
    12: "# ?/?",
    13: "# ??/??",
    14: "m/d/yyyy",
    15: "d-mmm-yy",
    16: "d-mmm",
    17: "mmm-yy",
    18: "h:mm AM/PM",
    19: "h:mm:ss AM/PM",
    20: "h:mm",
    21: "h:mm:ss",
    22: "m/d/yyyy h:mm",
    37: "#,##0 ;(#,##0)",
    38: "#,##0 ;[Red](#,##0)",
    39: "#,##0.00;(#,##0.00)",
    40: "#,##0.00;[Red](#,##0.00)",
    45: "mm:ss",
    46: "[h]:mm:ss",
    47: "mmss.0",
    48: "##0.0E+0",
    49: "@",
}

_RE_UNICODE_HEX = re.compile(r"_x([0-9a-fA-F]{4})_")


def _unescape_xml_text(s: str | None) -> str:
    """Unescape OOXML hex escapes like _x000D_ to actual characters."""
    if not s:
        return ""
    return _RE_UNICODE_HEX.sub(lambda m: chr(int(m.group(1), 16)), s)


def _clean_tag(tag: str) -> str:
    """Strip XML namespace from tag (e.g. '{http://...}sheetData' -> 'sheetData')."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _read_page_setup(root: ET.Element, sheet: Any) -> None:
    """Load page setup into ``sheet.extra["print_setup"]`` (+ a snapshot for round-trip)."""
    from atboffice.modules.spreadsheet.printing.setup import PAPER_CODES, SheetPrintSetup

    opts = _find_child(root, "printOptions")
    margins = _find_child(root, "pageMargins")
    page = _find_child(root, "pageSetup")
    hf = _find_child(root, "headerFooter")
    pr = _find_child(_find_child(root, "sheetPr"), "pageSetUpPr")
    if opts is None and margins is None and page is None and hf is None and pr is None:
        return

    def flag(el: ET.Element | None, name: str) -> bool:
        return (_attr(el, name) or "").lower() in ("1", "true")

    def num(el: ET.Element | None, name: str, default: float) -> float:
        try:
            return float(_attr(el, name) or default)
        except ValueError:
            return default

    st = SheetPrintSetup()
    st.center_h = flag(opts, "horizontalCentered")
    st.center_v = flag(opts, "verticalCentered")
    st.headings = flag(opts, "headings")
    st.gridlines = flag(opts, "gridLines")
    if margins is not None:
        st.margins = {
            key: num(margins, key, st.margins[key] / 72.0) * 72.0
            for key in ("left", "right", "top", "bottom", "header", "footer")
        }
    if page is not None:
        code = int(num(page, "paperSize", 9))
        st.paper = next((n for n, c in PAPER_CODES.items() if c == code), "A4")
        st.orientation = "landscape" if _attr(page, "orientation") == "landscape" else "portrait"
        st.scale = max(10, min(400, int(num(page, "scale", 100))))
        st.fit_width = int(num(page, "fitToWidth", 1))
        st.fit_height = int(num(page, "fitToHeight", 1))
        st.black_white = flag(page, "blackAndWhite")
        st.page_order = (
            "over_then_down" if _attr(page, "pageOrder") == "overThenDown" else "down_then_over"
        )
        if flag(page, "useFirstPageNumber"):
            st.first_page_number = int(num(page, "firstPageNumber", 1))
    st.fit_to = flag(pr, "fitToPage")
    odd_header = _find_child(hf, "oddHeader")
    odd_footer = _find_child(hf, "oddFooter")
    st.header = (odd_header.text or "") if odd_header is not None else ""
    st.footer = (odd_footer.text or "") if odd_footer is not None else ""
    data = st.to_dict()
    sheet.extra["print_setup"] = data
    sheet.extra["print_setup_loaded"] = SheetPrintSetup.from_dict(data).to_dict()


def _find_child(element: ET.Element | None, name: str) -> ET.Element | None:
    """Find first direct child with matching local tag name (case-insensitive)."""
    if element is None:
        return None
    target = name.lower()
    for child in element:
        if _clean_tag(child.tag).lower() == target:
            return child
    return None


def _find_children(element: ET.Element | None, name: str) -> list[ET.Element]:
    """Find all direct children with matching local tag name (case-insensitive)."""
    if element is None:
        return []
    target = name.lower()
    return [c for c in element if _clean_tag(c.tag).lower() == target]


def _attr(element: ET.Element | None, name: str, default: str | None = None) -> str | None:
    """Retrieve attribute by local name, ignoring XML namespace prefixes."""
    if element is None:
        return default
    target = name.lower()
    for k, v in element.attrib.items():
        local_k = k.split("}", 1)[1] if "}" in k else k
        if ":" in local_k:
            local_k = local_k.split(":", 1)[1]
        if local_k.lower() == target:
            return v
    return default


def _cell_formula(
    f_el: ET.Element, r: int, c: int, shared: dict[str, tuple[int, int, str]]
) -> str | None:
    """Return the formula text of a ``<c><f>`` element.

    Shared formulas (``t="shared"``) store their text only on the master cell; every other
    cell in the group carries just ``si``. Those cells get the master formula translated by
    their offset from the master, which is what Excel does on load.
    """
    text = (f_el.text or "").strip().lstrip("=")
    if _attr(f_el, "t") != "shared":
        return text or None
    si = _attr(f_el, "si")
    if text:
        if si is not None:
            shared[si] = (r, c, text)
        return text
    master = shared.get(si) if si is not None else None
    if master is None:
        return None
    mr, mc, mtext = master
    return translate(mtext, r - mr, c - mc)


def _resolve_rel_path(base_file: str, target: str) -> str:
    """Normalize relative target path against base file directory in zip archive."""
    target_clean = target.replace("\\", "/")
    if target_clean.startswith("/"):
        return target_clean.lstrip("/")

    base_parts = base_file.split("/")
    base_parts.pop()  # remove file name

    for seg in target_clean.split("/"):
        if seg == "..":
            if base_parts:
                base_parts.pop()
        elif seg and seg != ".":
            base_parts.append(seg)

    return "/".join(base_parts)


def _parse_rels(zip_file: zipfile.ZipFile, rels_path: str) -> dict[str, tuple[str, str]]:
    """Parse a .rels XML relationship file into {rel_id: (rel_type, target_path)}."""
    rels: dict[str, tuple[str, str]] = {}
    try:
        content = zip_file.read(rels_path)
    except KeyError:
        return rels

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return rels

    # "_rels/.rels" describes the package root; "dir/_rels/part.xml.rels" describes
    # "dir/part.xml". Targets resolve relative to the source part's directory.
    if rels_path.lstrip("/") == "_rels/.rels":
        base_dir = ""
    else:
        base_dir = rels_path.replace("_rels/", "").rsplit(".rels", 1)[0]
    for rel in _find_children(root, "Relationship"):
        r_id = _attr(rel, "Id")
        r_type = _attr(rel, "Type", "") or ""
        r_target = _attr(rel, "Target")
        target_mode = _attr(rel, "TargetMode", "Internal")

        if r_id and r_target:
            clean_type = r_type.rsplit("/", 1)[-1]
            if target_mode == "External":
                resolved_target = r_target
            else:
                resolved_target = _resolve_rel_path(base_dir, r_target)
            rels[r_id] = (clean_type, resolved_target)

    return rels


class SharedString(str):
    """String subclass that optionally carries parsed RichTextRun formatting."""

    rich_runs: list[RichTextRun] | None = None


def _parse_rpr(
    rpr_el: ET.Element | None,
    theme_colors: Sequence[str] | None = None,
    palette: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Parse <rPr> font and style properties for a rich text run."""
    props: dict[str, Any] = {}
    if rpr_el is None:
        return props

    font_el = _find_child(rpr_el, "rFont")
    if font_el is None:
        font_el = _find_child(rpr_el, "name")
    if font_el is not None:
        val = _attr(font_el, "val")
        if val:
            props["font_family"] = val

    sz_el = _find_child(rpr_el, "sz")
    if sz_el is not None:
        val = _attr(sz_el, "val")
        if val:
            try:
                props["font_size"] = float(val)
            except ValueError:
                pass

    b_el = _find_child(rpr_el, "b")
    if b_el is not None:
        val = _attr(b_el, "val")
        props["bold"] = val is None or val.strip().lower() in ("1", "true")

    i_el = _find_child(rpr_el, "i")
    if i_el is not None:
        val = _attr(i_el, "val")
        props["italic"] = val is None or val.strip().lower() in ("1", "true")

    u_el = _find_child(rpr_el, "u")
    if u_el is not None:
        val = _attr(u_el, "val")
        u_val = val if val is not None else "single"
        if u_val != "none":
            props["underline"] = True
            props["underline_style"] = u_val

    strike_el = _find_child(rpr_el, "strike")
    if strike_el is not None:
        val = _attr(strike_el, "val")
        props["strike"] = val is None or val.strip().lower() in ("1", "true")

    color_el = _find_child(rpr_el, "color")
    if color_el is not None:
        col, col_spec = _parse_color_and_spec(color_el, theme_colors, palette)
        if col:
            props["fg_color"] = col
        if col_spec is not None:
            props["fg_color_spec"] = col_spec

    va_el = _find_child(rpr_el, "vertAlign")
    if va_el is not None:
        val = _attr(va_el, "val")
        if val and val.strip().lower() != "baseline":
            props["vert_align"] = val.strip().lower()

    return props


def _parse_rich_runs(
    container_el: ET.Element,
    theme_colors: Sequence[str] | None = None,
    palette: Sequence[str] | None = None,
) -> tuple[str, list[RichTextRun] | None]:
    """Parse child <r> elements from <si> or <is> into (full_text, runs_list)."""
    runs = _find_children(container_el, "r")
    if not runs:
        t_el = _find_child(container_el, "t")
        text = _unescape_xml_text(t_el.text or "") if t_el is not None else ""
        return text, None

    parts: list[str] = []
    rich_runs: list[RichTextRun] = []
    has_any_styling = False

    for r_el in runs:
        t_el = _find_child(r_el, "t")
        run_text = _unescape_xml_text(t_el.text or "") if t_el is not None else ""
        parts.append(run_text)

        rpr_el = _find_child(r_el, "rPr")
        props = _parse_rpr(rpr_el, theme_colors, palette)
        if props:
            has_any_styling = True

        rich_runs.append(
            RichTextRun(
                text=run_text,
                font_family=props.get("font_family"),
                font_size=props.get("font_size"),
                bold=props.get("bold"),
                italic=props.get("italic"),
                underline=props.get("underline"),
                underline_style=props.get("underline_style"),
                strike=props.get("strike"),
                fg_color=props.get("fg_color"),
                fg_color_spec=props.get("fg_color_spec"),
                vert_align=props.get("vert_align"),
            )
        )

    full_text = "".join(parts)
    return full_text, rich_runs if (rich_runs and has_any_styling) else None


def _parse_shared_strings(
    zip_file: zipfile.ZipFile,
    sst_path: str,
    theme_colors: Sequence[str] | None = None,
    palette: Sequence[str] | None = None,
) -> list[str]:
    """Parse xl/sharedStrings.xml into a list of strings."""
    sst: list[str] = []
    try:
        content = zip_file.read(sst_path)
    except KeyError:
        return sst

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return sst

    for si in _find_children(root, "si"):
        text, runs = _parse_rich_runs(si, theme_colors, palette)
        s = SharedString(text)
        if runs:
            s.rich_runs = runs
        sst.append(s)

    return sst


def _parse_color_and_spec(
    el: ET.Element | None,
    theme_colors: Sequence[str] | None = None,
    palette: Sequence[str] | None = None,
    auto: str | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Extract resolved '#RRGGBB' color and original OOXML color spec from element."""
    spec = parse_color_element(el)
    if spec is None:
        return None, None
    resolved = resolve_color_spec(spec, theme_colors=theme_colors, palette=palette, auto=auto)
    return resolved, spec


def _parse_color(
    el: ET.Element | None,
    theme_colors: Sequence[str] | None = None,
    palette: Sequence[str] | None = None,
    auto: str | None = None,
) -> str | None:
    """Resolve SpreadsheetML color element (theme > rgb > indexed + tint) to '#RRGGBB'."""
    resolved, _ = _parse_color_and_spec(el, theme_colors=theme_colors, palette=palette, auto=auto)
    return resolved


def _parse_border_side(
    side_el: ET.Element | None,
    theme_colors: Sequence[str] | None = None,
    palette: Sequence[str] | None = None,
) -> BorderStyle | None:
    """Parse single border side element (left, right, top, bottom, etc.)."""
    if side_el is None:
        return None
    style = _attr(side_el, "style")
    if not style or style == "none":
        return None
    col, col_spec = _parse_color_and_spec(_find_child(side_el, "color"), theme_colors, palette)
    return BorderStyle(style=style, color=col, color_spec=col_spec)


class StyleBundle(list):
    """List of FormatDelta objects with attached dxfs."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.dxfs: list[dict[str, Any]] = []
        self.table_styles: list[dict[str, Any]] = []


def _norm_hex(col: str | None) -> str | None:
    """Normalize color hex to standard #RRGGBB."""
    return normalize_hex_color(col)


def _parse_styles(
    zip_file: zipfile.ZipFile,
    styles_path: str,
    theme_colors: list[str] | None = None,
    palette: list[str] | None = None,
    workbook: WorkbookModel | None = None,
) -> list[FormatDelta]:
    """Parse xl/styles.xml into a list of FormatDelta objects indexed by xfId."""
    deltas = StyleBundle()
    try:
        content = zip_file.read(styles_path)
    except KeyError:
        deltas.append(FormatDelta())
        return deltas

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        deltas.append(FormatDelta())
        return deltas

    active_theme = list(theme_colors) if theme_colors else list(DEFAULT_THEME_COLORS)
    active_palette = list(palette) if palette else list(DEFAULT_INDEXED_PALETTE)

    # 0. Optional custom colors (<colors><indexedColors> / 2006 preview <themeColors>)
    colors_el = _find_child(root, "colors")
    if colors_el is not None:
        if "http://schemas.microsoft.com/office/excel/2006/2" in root.tag:
            tc_el = _find_child(colors_el, "themeColors")
            if tc_el is not None:
                for idx, rgb_el in enumerate(_find_children(tc_el, "rgbColor")):
                    rgb_val = _attr(rgb_el, "rgb")
                    norm = normalize_hex_color(rgb_val)
                    if norm and idx < len(active_theme):
                        active_theme[idx] = norm
                if workbook is not None:
                    workbook.theme_colors = list(active_theme)

        idx_colors_el = _find_child(colors_el, "indexedColors")
        if idx_colors_el is not None:
            for idx, rgb_el in enumerate(_find_children(idx_colors_el, "rgbColor")):
                rgb_val = _attr(rgb_el, "rgb")
                norm = normalize_hex_color(rgb_val)
                if norm and idx < len(active_palette):
                    active_palette[idx] = norm
            if workbook is not None:
                workbook.indexed_palette = list(active_palette)

    # 1. Number formats
    num_fmts: dict[int, str] = dict(BUILTIN_NUMFMTS)
    num_fmts_el = _find_child(root, "numFmts")
    if num_fmts_el is not None:
        for nf in _find_children(num_fmts_el, "numFmt"):
            fid = _attr(nf, "numFmtId")
            code = _attr(nf, "formatCode")
            if fid is not None and code is not None:
                try:
                    num_fmts[int(fid)] = code
                except ValueError:
                    pass

    # 2. Fonts
    fonts: list[dict[str, any]] = []
    fonts_el = _find_child(root, "fonts")
    if fonts_el is not None:
        for f in _find_children(fonts_el, "font"):
            font_info: dict[str, any] = {}
            name_el = _find_child(f, "name")
            if name_el is None:
                name_el = _find_child(f, "rFont")
            if name_el is not None and _attr(name_el, "val"):
                font_info["name"] = _attr(name_el, "val")
            sz_el = _find_child(f, "sz")
            if sz_el is not None and _attr(sz_el, "val"):
                try:
                    font_info["sz"] = int(float(_attr(sz_el, "val")))
                except ValueError:
                    pass
            b_el = _find_child(f, "b")
            if b_el is not None:
                val = _attr(b_el, "val")
                font_info["b"] = val is None or val in ("1", "true")
            i_el = _find_child(f, "i")
            if i_el is not None:
                val = _attr(i_el, "val")
                font_info["i"] = val is None or val in ("1", "true")
            u_el = _find_child(f, "u")
            if u_el is not None:
                u_val = _attr(u_el, "val", "single")
                font_info["u"] = u_val != "none"
                font_info["u_style"] = u_val
            strike_el = _find_child(f, "strike")
            if strike_el is not None:
                val = _attr(strike_el, "val")
                font_info["strike"] = val is None or val in ("1", "true")
            c_el = _find_child(f, "color")
            if c_el is not None:
                col, col_spec = _parse_color_and_spec(c_el, active_theme, active_palette)
                if col:
                    font_info["color"] = col
                if col_spec is not None:
                    font_info["color_spec"] = col_spec
            fonts.append(font_info)

    # 3. Fills
    fills: list[dict[str, any]] = []
    fills_el = _find_child(root, "fills")
    if fills_el is not None:
        for fill_el in _find_children(fills_el, "fill"):
            fill_info: dict[str, any] = {}
            pf = _find_child(fill_el, "patternFill")
            if pf is not None:
                ptype = _attr(pf, "patternType")
                if ptype and ptype != "none":
                    fill_info["pattern"] = ptype
                    fg_hex, fg_spec = _parse_color_and_spec(
                        _find_child(pf, "fgColor"), active_theme, active_palette
                    )
                    bg_hex, bg_spec = _parse_color_and_spec(
                        _find_child(pf, "bgColor"), active_theme, active_palette
                    )
                    if ptype == "solid":
                        fill_info["bg_color"] = fg_hex if fg_spec is not None else bg_hex
                        fill_info["bg_color_spec"] = (
                            fg_spec if fg_spec is not None else bg_spec
                        )
                    else:
                        fill_info["pattern_color"] = fg_hex
                        fill_info["pattern_color_spec"] = fg_spec
                        fill_info["bg_color"] = bg_hex
                        fill_info["bg_color_spec"] = bg_spec
            fills.append(fill_info)

    # 4. Borders
    borders: list[dict[str, BorderStyle | None]] = []
    borders_el = _find_child(root, "borders")
    if borders_el is not None:
        for b_el in _find_children(borders_el, "border"):
            b_info = {
                "top": _parse_border_side(_find_child(b_el, "top"), active_theme, active_palette),
                "bottom": _parse_border_side(
                    _find_child(b_el, "bottom"), active_theme, active_palette
                ),
                "left": _parse_border_side(
                    _find_child(b_el, "left"), active_theme, active_palette
                ),
                "right": _parse_border_side(
                    _find_child(b_el, "right"), active_theme, active_palette
                ),
            }
            borders.append(b_info)

    # 5. Cell formats (<cellXfs>)
    cell_xfs_el = _find_child(root, "cellXfs")
    if cell_xfs_el is not None:
        for xf in _find_children(cell_xfs_el, "xf"):
            delta = FormatDelta()
            # Font
            font_id_str = _attr(xf, "fontId")
            if font_id_str is not None:
                try:
                    fid = int(font_id_str)
                    if 0 <= fid < len(fonts):
                        finfo = fonts[fid]
                        if "name" in finfo:
                            delta.font_family = finfo["name"]
                        if "sz" in finfo:
                            delta.font_size = finfo["sz"]
                        if "b" in finfo:
                            delta.bold = finfo["b"]
                        if "i" in finfo:
                            delta.italic = finfo["i"]
                        if "u" in finfo:
                            delta.underline = finfo["u"]
                            delta.underline_style = finfo.get("u_style", "single")
                        if "strike" in finfo:
                            delta.strike = finfo["strike"]
                        if "color" in finfo:
                            delta.fg_color = finfo["color"]
                        if "color_spec" in finfo:
                            delta.fg_color_spec = finfo["color_spec"]
                except ValueError:
                    pass

            # Fill
            fill_id_str = _attr(xf, "fillId")
            if fill_id_str is not None:
                try:
                    fill_id = int(fill_id_str)
                    if 0 <= fill_id < len(fills):
                        fl = fills[fill_id]
                        if fl.get("bg_color") is not None:
                            delta.bg_color = fl["bg_color"]
                        if fl.get("bg_color_spec") is not None:
                            delta.bg_color_spec = fl["bg_color_spec"]
                        if fl.get("pattern_color") is not None:
                            delta.pattern_color = fl["pattern_color"]
                        if fl.get("pattern_color_spec") is not None:
                            delta.pattern_color_spec = fl["pattern_color_spec"]
                        if "pattern" in fl:
                            delta.pattern = fl["pattern"]
                except ValueError:
                    pass

            # Border
            border_id_str = _attr(xf, "borderId")
            if border_id_str is not None:
                try:
                    bid = int(border_id_str)
                    if 0 <= bid < len(borders):
                        bdata = borders[bid]
                        delta.border_top = bdata["top"]
                        delta.border_bottom = bdata["bottom"]
                        delta.border_left = bdata["left"]
                        delta.border_right = bdata["right"]
                except ValueError:
                    pass

            # Number Format
            num_fmt_id_str = _attr(xf, "numFmtId")
            if num_fmt_id_str is not None:
                try:
                    nf_id = int(num_fmt_id_str)
                    delta.format_code = num_fmts.get(nf_id, "General")
                except ValueError:
                    pass

            # Alignment
            align_el = _find_child(xf, "alignment")
            if align_el is not None:
                h = _attr(align_el, "horizontal")
                if h and h != "general":
                    delta.align_h = h
                v = _attr(align_el, "vertical")
                if v and v != "bottom":
                    delta.align_v = v
                wrap = _attr(align_el, "wrapText")
                if wrap in ("1", "true"):
                    delta.wrap_text = True
                shrink = _attr(align_el, "shrinkToFit")
                if shrink in ("1", "true"):
                    delta.shrink_to_fit = True
                rot = _attr(align_el, "textRotation")
                if rot:
                    try:
                        delta.text_rotation = int(rot)
                    except ValueError:
                        pass
                indent = _attr(align_el, "indent")
                if indent:
                    try:
                        delta.indent = int(indent)
                    except ValueError:
                        pass
                ro = _attr(align_el, "readingOrder")
                if ro == "1":
                    delta.text_direction = "ltr"
                elif ro == "2":
                    delta.text_direction = "rtl"
                elif ro == "0":
                    delta.text_direction = "context"

            deltas.append(delta)

    # 6. Differential formats (<dxfs>)
    dxfs_el = _find_child(root, "dxfs")
    if dxfs_el is not None:
        for dxf_el in _find_children(dxfs_el, "dxf"):
            d_info: dict[str, Any] = {}
            f_el = _find_child(dxf_el, "font")
            if f_el is not None:
                b_el = _find_child(f_el, "b")
                if b_el is not None:
                    val = _attr(b_el, "val")
                    d_info["bold"] = val is None or val in ("1", "true")
                i_el = _find_child(f_el, "i")
                if i_el is not None:
                    val = _attr(i_el, "val")
                    d_info["italic"] = val is None or val in ("1", "true")
                c_el = _find_child(f_el, "color")
                if c_el is not None:
                    fg_hex, fg_spec = _parse_color_and_spec(c_el, active_theme, active_palette)
                    d_info["fg_color"] = fg_hex
                    d_info["fg_color_spec"] = fg_spec
            fill_el = _find_child(dxf_el, "fill")
            if fill_el is not None:
                pf = _find_child(fill_el, "patternFill")
                if pf is not None:
                    fg_hex, fg_spec = _parse_color_and_spec(
                        _find_child(pf, "fgColor"), active_theme, active_palette
                    )
                    bg_hex, bg_spec = _parse_color_and_spec(
                        _find_child(pf, "bgColor"), active_theme, active_palette
                    )
                    d_info["bg_color"] = fg_hex if fg_spec is not None else bg_hex
                    d_info["bg_color_spec"] = fg_spec if fg_spec is not None else bg_spec
                    pt = _attr(pf, "patternType")
                    if pt:
                        d_info["pattern_type"] = pt
            border_el = _find_child(dxf_el, "border")
            if border_el is not None:
                d_borders: dict[str, BorderStyle] = {}
                for side in ("left", "right", "top", "bottom", "horizontal", "vertical"):
                    bs = _parse_border_side(
                        _find_child(border_el, side), active_theme, active_palette
                    )
                    if bs is not None:
                        d_borders[side] = bs
                if d_borders:
                    d_info["borders"] = d_borders
            deltas.dxfs.append(d_info)

    # 7. Custom table styles (<tableStyles>)
    deltas.table_styles = parse_table_styles(root)
    if workbook is not None and deltas.table_styles:
        workbook.extra["table_styles"] = deltas.table_styles

    if not deltas:
        deltas.append(FormatDelta())

    return deltas


def _parse_cell_value(val_str: str | None, cell_type: str | None, sst: list[str]) -> any:
    """Parse string text from cell according to OOXML type code."""
    if cell_type == "s":
        if val_str is None or not val_str.strip():
            return ""
        try:
            idx = int(val_str)
            return sst[idx] if 0 <= idx < len(sst) else ""
        except ValueError:
            return ""

    if cell_type == "b":
        return val_str in ("1", "true")

    if cell_type in ("str", "inlineStr"):
        return _unescape_xml_text(val_str or "")

    if cell_type == "e":
        return val_str or "#ERROR!"

    if cell_type == "d":
        return val_str or ""

    # Default: numeric
    if val_str is None or val_str == "":
        return None

    try:
        if "." in val_str or "e" in val_str.lower():
            return float(val_str)
        return int(val_str)
    except ValueError:
        return _unescape_xml_text(val_str)


def _parse_int_attr(element: ET.Element | None, name: str) -> int | None:
    """Return attribute ``name`` as a positive int, or None when missing/invalid."""
    raw = _attr(element, name)
    if not raw:
        return None
    try:
        val = int(float(raw))
    except ValueError:
        return None
    return val if val > 0 else None


def _parse_sheet_view_state(sv_el: ET.Element, sheet: SheetDataModel) -> None:
    """Fill ``sheet.view_state`` from a ``<sheetView>`` element (ledger/js/xlsx-read.js:591)."""
    vs = sheet.view_state
    vs.show_grid_lines = _attr(sv_el, "showGridLines", "1") not in ("0", "false")
    view = _attr(sv_el, "view", "normal")
    vs.view = view if view in ("normal", "pageBreakPreview", "pageLayout") else "normal"
    zoom = _parse_int_attr(sv_el, "zoomScale")
    if vs.view == "pageBreakPreview":
        zoom = _parse_int_attr(sv_el, "zoomScaleSheetLayoutView") or zoom or 60
    if zoom is not None:
        vs.zoom_scale = zoom
        sheet.extra["zoom"] = zoom
    vs.top_left_cell = _attr(sv_el, "topLeftCell") or None

    # The selection belonging to the active pane wins; otherwise the last one.
    sels = _find_children(sv_el, "selection")
    if sels:
        active_pane = _attr(_find_child(sv_el, "pane"), "activePane")
        sel_el = next(
            (el for el in sels if active_pane and _attr(el, "pane") == active_pane),
            sels[-1],
        )
        vs.active_cell = _attr(sel_el, "activeCell") or None
        vs.sqref = _attr(sel_el, "sqref") or vs.active_cell


def _parse_breaks(breaks_el: ET.Element | None) -> list[int]:
    """Return sorted break ids of ``<rowBreaks>``/``<colBreaks>`` (first index of the next page)."""
    out: set[int] = set()
    for brk in _find_children(breaks_el, "brk"):
        val = _parse_int_attr(brk, "id")
        if val is not None:
            out.add(val)
    return sorted(out)


def _parse_worksheet(
    zip_file: zipfile.ZipFile,
    sheet_path: str,
    sheet: SheetDataModel,
    sst: list[str],
    style_deltas: list[FormatDelta],
    theme_colors: Sequence[str] | None = None,
    palette: Sequence[str] | None = None,
) -> None:
    """Parse a single worksheet XML part into SheetDataModel."""
    try:
        content = zip_file.read(sheet_path)
    except KeyError:
        return

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return

    # 0. Sheet properties & Protection
    spr = _find_child(root, "sheetPr")
    if spr is not None:
        c_name = _attr(spr, "codeName")
        if c_name:
            sheet.code_name = c_name
            sheet.extra["code_name"] = c_name

    sp = _find_child(root, "sheetProtection")
    if sp is not None:
        sheet.protection = dict(sp.attrib)
        sheet.extra["protection"] = dict(sp.attrib)

    af = _find_child(root, "autoFilter")
    if af is not None:
        sheet.extra["auto_filter_xml"] = ET.tostring(af, encoding="utf-8").decode("utf-8")
        ref_str = _attr(af, "ref")
        if ref_str:
            rg = parse_range(ref_str)
            if rg is not None:
                from atboffice.modules.spreadsheet.models.filter_model import AutoFilter

                sheet.auto_filter = AutoFilter(
                    r1=rg["r1"],
                    c1=rg["c1"],
                    r2=rg["r2"],
                    c2=rg["c2"],
                )
            else:
                sheet.auto_filter = None
        else:
            sheet.auto_filter = None

    # 0b. Sheet Views (freeze panes, zoom, gridlines, view mode, selection)
    svs_el = _find_child(root, "sheetViews")
    if svs_el is not None:
        sv_el = _find_child(svs_el, "sheetView")
        if sv_el is not None:
            _parse_sheet_view_state(sv_el, sheet)
            pane_el = _find_child(sv_el, "pane")
            if pane_el is not None:
                p_state = _attr(pane_el, "state", "split")
                xs_str = _attr(pane_el, "xSplit", "0")
                ys_str = _attr(pane_el, "ySplit", "0")
                if p_state in ("frozen", "frozenSplit"):
                    try:
                        sheet.freeze_cols = max(0, int(float(xs_str or 0)))
                        sheet.freeze_rows = max(0, int(float(ys_str or 0)))
                    except ValueError:
                        pass

    # 0b2. Stored manual page breaks (<rowBreaks>/<colBreaks>)
    sheet.view_state.row_breaks = _parse_breaks(_find_child(root, "rowBreaks"))
    sheet.view_state.col_breaks = _parse_breaks(_find_child(root, "colBreaks"))

    # 0b3. File > Page Setup (printOptions, pageMargins, pageSetup, headerFooter)
    _read_page_setup(root, sheet)

    # 0c. Sheet format (default row height & default col width). Both follow the workbook
    # default font (cellXfs[0]); a stored defaultRowHeight only counts with customHeight=1.
    def_font = style_deltas[0] if style_deltas else None
    def_family = getattr(def_font, "font_family", None) or "Calibri"
    def_size = getattr(def_font, "font_size", None) or 11.0
    mdw = excel_mdw(def_family, def_size)
    sheet.extra["excel_mdw"] = mdw
    row_h_px = int(round(font_row_pt(def_family, def_size) / 0.75))
    def_col_w: float | None = None
    base_col_w: float | None = None
    sfp = _find_child(root, "sheetFormatPr")
    if sfp is not None:
        def_row_h = _attr(sfp, "defaultRowHeight")
        custom_h = _attr(sfp, "customHeight") in ("1", "true") or _attr(
            sfp, "zeroHeight"
        ) in ("1", "true")
        if def_row_h and custom_h:
            try:
                # points to pixels: pt * 96 / 72 = pt / 0.75
                h_px = int(round(float(def_row_h) / 0.75))
                if h_px > 0:
                    row_h_px = h_px
            except ValueError:
                pass
        try:
            def_col_w = float(_attr(sfp, "defaultColWidth") or "")
            sheet.extra["default_col_width"] = def_col_w
        except ValueError:
            def_col_w = None
        try:
            base_col_w = float(_attr(sfp, "baseColWidth") or "")
        except ValueError:
            base_col_w = None
    if row_h_px > 0:
        sheet.geometry.default_row_height = row_h_px
        sheet.extra["default_row_height"] = row_h_px
    sheet.geometry.default_col_width = default_col_px(mdw, def_col_w, base_col_w)

    # 1. Custom column widths, hidden columns, and column style ranges
    col_style_ranges: list[tuple[int, int, int]] = []
    cols_el = _find_child(root, "cols")
    if cols_el is not None:
        for col_el in _find_children(cols_el, "col"):
            min_c_str = _attr(col_el, "min")
            max_c_str = _attr(col_el, "max")
            width_str = _attr(col_el, "width")
            hidden = _attr(col_el, "hidden") in ("1", "true")
            col_style_str = _attr(col_el, "style")

            if min_c_str and max_c_str:
                try:
                    c1 = max(0, int(min_c_str) - 1)
                    c2 = max(c1, int(max_c_str) - 1)
                    w_px = width_to_px(float(width_str), mdw) if width_str else None

                    if col_style_str:
                        try:
                            cs_idx = int(col_style_str)
                            if 0 <= cs_idx < len(style_deltas):
                                cs_c2 = min(c2, sheet.geometry.max_cols - 1)
                                col_style_ranges.append((c1, cs_c2, cs_idx))
                                cs_fill = style_deltas[cs_idx].bg_color
                                if cs_fill:
                                    sheet.col_fills.append((c1, cs_c2, cs_fill))
                        except ValueError:
                            pass

                    for c in range(c1, min(c2 + 1, sheet.geometry.max_cols)):
                        if w_px is not None:
                            sheet.geometry.set_col_width(c, w_px)
                        if hidden:
                            sheet.geometry.hidden_cols.add(c)
                except ValueError:
                    pass

    # 2. Sheet data (rows and cells)
    sd_el = _find_child(root, "sheetData")
    if sd_el is not None:
        curr_r = 0
        shared_formulas: dict[str, tuple[int, int, str]] = {}
        for row_el in _find_children(sd_el, "row"):
            r_str = _attr(row_el, "r")
            if r_str:
                try:
                    curr_r = int(r_str) - 1
                except ValueError:
                    pass

            ht_str = _attr(row_el, "ht")
            if ht_str:
                try:
                    # points to pixels like ledger/js M.ptToPx: round(pt * 96 / 72)
                    ht_px = int(round(float(ht_str) / 0.75))
                    sheet.geometry.set_row_height(curr_r, ht_px)
                except (ValueError, OverflowError):
                    pass

            if _attr(row_el, "hidden") in ("1", "true"):
                sheet.geometry.hidden_rows.add(curr_r)

            row_style_idx: int | None = None
            row_s_str = _attr(row_el, "s")
            if row_s_str and _attr(row_el, "customFormat") in ("1", "true"):
                try:
                    rs = int(row_s_str)
                    if 0 <= rs < len(style_deltas):
                        row_style_idx = rs
                        rs_fill = style_deltas[rs].bg_color
                        if rs_fill:
                            sheet.row_fills[curr_r] = rs_fill
                except ValueError:
                    pass

            curr_c = -1
            for c_el in _find_children(row_el, "c"):
                ref = _attr(c_el, "r")
                if ref:
                    parsed = parse_cell(ref)
                    if parsed:
                        r = parsed["r"]
                        c = parsed["c"]
                    else:
                        r = curr_r
                        curr_c += 1
                        c = curr_c
                else:
                    r = curr_r
                    curr_c += 1
                    c = curr_c

                curr_c = c
                cell_type = _attr(c_el, "t")
                style_idx_str = _attr(c_el, "s")

                # Parse formula
                formula_el = _find_child(c_el, "f")
                formula_str: str | None = None
                if formula_el is not None:
                    formula_str = _cell_formula(formula_el, r, c, shared_formulas)

                # Parse value
                val_str: str | None = None
                cell_rich_runs: list[RichTextRun] | None = None
                if cell_type == "inlineStr":
                    is_el = _find_child(c_el, "is")
                    if is_el is not None:
                        val_str, cell_rich_runs = _parse_rich_runs(is_el, theme_colors, palette)
                        parsed_value = val_str
                    else:
                        parsed_value = ""
                else:
                    v_el = _find_child(c_el, "v")
                    if v_el is not None:
                        val_str = v_el.text

                    parsed_value = _parse_cell_value(val_str, cell_type, sst)
                    if (
                        cell_type == "s"
                        and isinstance(parsed_value, SharedString)
                        and parsed_value.rich_runs
                    ):
                        cell_rich_runs = parsed_value.rich_runs

                # Skip completely empty cells without formula or style
                if parsed_value is None and formula_str is None and not style_idx_str:
                    continue

                cached_val = parsed_value if formula_str is not None else None
                cell = CellData(
                    value=parsed_value,
                    formula=formula_str,
                    cached_value=cached_val,
                    rich_runs=cell_rich_runs,
                )

                # Resolve effective style: cell s -> row s -> col style -> cellXfs[0]
                s_idx: int | None = None
                if style_idx_str:
                    try:
                        cand = int(style_idx_str)
                        if 0 <= cand < len(style_deltas):
                            s_idx = cand
                    except ValueError:
                        pass
                if s_idx is None:
                    if row_style_idx is not None:
                        s_idx = row_style_idx
                    else:
                        for cs_c1, cs_c2, cs_idx in reversed(col_style_ranges):
                            if cs_c1 <= c <= cs_c2:
                                s_idx = cs_idx
                                break
                if s_idx is None and style_deltas:
                    s_idx = 0

                sheet.set_cell(r, c, cell)
                if s_idx is not None and 0 <= s_idx < len(style_deltas):
                    sheet.apply_format_delta(r, c, style_deltas[s_idx])

    # 3. Merged cells
    merges_el = _find_child(root, "mergeCells")
    if merges_el is not None:
        for m_el in _find_children(merges_el, "mergeCell"):
            ref = _attr(m_el, "ref")
            if ref:
                rg = parse_range(ref)
                if rg:
                    sheet.add_merge(rg["r1"], rg["c1"], rg["r2"], rg["c2"])

    # 4. Conditional Formatting (<conditionalFormatting>)
    dxfs = getattr(style_deltas, "dxfs", [])
    for cf_el in _find_children(root, "conditionalFormatting"):
        sqref = _attr(cf_el, "sqref", "") or ""
        ranges: list[tuple[int, int, int, int]] = []
        for part in sqref.split():
            rg = parse_range(part)
            if rg:
                ranges.append((rg["r1"], rg["c1"], rg["r2"], rg["c2"]))
        rules: list[CFRule] = []
        for r_el in _find_children(cf_el, "cfRule"):
            rtype = _attr(r_el, "type", "cellIs")
            op = _attr(r_el, "operator")
            priority = 1
            try:
                priority = int(_attr(r_el, "priority", "1"))
            except ValueError:
                pass
            stop_if_true = _attr(r_el, "stopIfTrue") in ("1", "true")
            text_val = _attr(r_el, "text")
            formulas = [
                f.text.strip() for f in _find_children(r_el, "formula") if f.text is not None
            ]

            # Formatting from dxf
            bg_col = None
            fg_col = None
            bg_col_spec = None
            fg_col_spec = None
            bold_val = None
            italic_val = None
            dxf_id_str = _attr(r_el, "dxfId")
            if dxf_id_str is not None:
                try:
                    dxf_id = int(dxf_id_str)
                    if 0 <= dxf_id < len(dxfs):
                        dinfo = dxfs[dxf_id]
                        bg_col = _norm_hex(dinfo.get("bg_color"))
                        fg_col = _norm_hex(dinfo.get("fg_color"))
                        bg_col_spec = dinfo.get("bg_color_spec")
                        fg_col_spec = dinfo.get("fg_color_spec")
                        bold_val = dinfo.get("bold")
                        italic_val = dinfo.get("italic")
                except ValueError:
                    pass

            # Color scale
            scale_rule = None
            cs_el = _find_child(r_el, "colorScale")
            if cs_el is not None:
                cfvos = []
                for vo_el in _find_children(cs_el, "cfvo"):
                    cfvos.append(CFVO(type=_attr(vo_el, "type", "min"), val=_attr(vo_el, "val")))
                colors = []
                color_specs = []
                for col_el in _find_children(cs_el, "color"):
                    c_val, c_spec = _parse_color_and_spec(col_el, theme_colors, palette)
                    colors.append(_norm_hex(c_val) or "#FFFFFF")
                    color_specs.append(c_spec)
                scale_rule = ColorScaleRule(cfvos=cfvos, colors=colors, color_specs=color_specs)

            # Data bar
            bar_rule = None
            db_el = _find_child(r_el, "dataBar")
            if db_el is not None:
                cfvos = []
                for vo_el in _find_children(db_el, "cfvo"):
                    cfvos.append(CFVO(type=_attr(vo_el, "type", "min"), val=_attr(vo_el, "val")))
                c_val, c_spec = _parse_color_and_spec(
                    _find_child(db_el, "color"), theme_colors, palette
                )
                color_hex = _norm_hex(c_val) or "#638EC6"
                bar_rule = DataBarRule(cfvos=cfvos, color=color_hex, color_spec=c_spec)

            # Icon set
            icon_rule = _parse_icon_set(_find_child(r_el, "iconSet"))

            above_avg_attr = _attr(r_el, "aboveAverage")
            above_avg = above_avg_attr != "0"
            equal_avg = _attr(r_el, "equalAverage") in ("1", "true")
            std_dev_attr = _attr(r_el, "stdDev")
            std_dev = int(std_dev_attr) if std_dev_attr and std_dev_attr.isdigit() else None
            rank_attr = _attr(r_el, "rank")
            rank = int(rank_attr) if rank_attr and rank_attr.isdigit() else 10
            bottom = _attr(r_el, "bottom") in ("1", "true")
            percent = _attr(r_el, "percent") in ("1", "true")

            rule = CFRule(
                type=rtype,
                operator=op,
                formula=formulas,
                text=text_val,
                priority=priority,
                stop_if_true=stop_if_true,
                bg_color=bg_col,
                fg_color=fg_col,
                bg_color_spec=bg_col_spec,
                fg_color_spec=fg_col_spec,
                bold=bold_val,
                italic=italic_val,
                color_scale=scale_rule,
                data_bar=bar_rule,
                icon_set=icon_rule,
                above_average=above_avg,
                equal_average=equal_avg,
                std_dev=std_dev,
                rank=rank,
                bottom=bottom,
                percent=percent,
            )
            rules.append(rule)

        cf = ConditionalFormat(sqref=sqref, ranges=ranges, rules=rules)
        sheet.add_conditional_format(cf)

    # 4b. x14 extension rules (icon sets with custom icons / 2009 icon sets)
    for cf in _parse_x14_icon_set_formats(root):
        sheet.add_conditional_format(cf)

    # 5. Data Validations (<dataValidations>)
    dvs_el = _find_child(root, "dataValidations")
    if dvs_el is not None:
        for dv_el in _find_children(dvs_el, "dataValidation"):
            v_type = _attr(dv_el, "type", "any")
            op = _attr(dv_el, "operator", "between")
            allow_blank = _attr(dv_el, "allowBlank") not in ("0", "false")
            show_dropdown = _attr(dv_el, "showDropDown") not in ("0", "false")
            show_input_msg = _attr(dv_el, "showInputMessage") in ("1", "true")
            show_err_alert = _attr(dv_el, "showErrorMessage") not in ("0", "false")
            err_style = _attr(dv_el, "errorStyle", "stop")
            prompt_title = _unescape_xml_text(_attr(dv_el, "promptTitle", ""))
            prompt = _unescape_xml_text(_attr(dv_el, "prompt", ""))
            err_title = _unescape_xml_text(_attr(dv_el, "errorTitle", ""))
            err_msg = _unescape_xml_text(_attr(dv_el, "error", ""))
            sqref = _attr(dv_el, "sqref", "") or ""

            f1_el = _find_child(dv_el, "formula1")
            f2_el = _find_child(dv_el, "formula2")
            f1 = f1_el.text.strip() if f1_el is not None and f1_el.text else None
            f2 = f2_el.text.strip() if f2_el is not None and f2_el.text else None

            ranges = []
            for part in sqref.split():
                rg = parse_range(part)
                if rg:
                    ranges.append((rg["r1"], rg["c1"], rg["r2"], rg["c2"]))

            dv = DataValidation(
                type=v_type,
                operator=op,
                allow_blank=allow_blank,
                show_dropdown=show_dropdown,
                show_input_message=show_input_msg,
                input_title=prompt_title,
                input_message=prompt,
                show_error_alert=show_err_alert,
                error_style=err_style,
                error_title=err_title,
                error_message=err_msg,
                formula1=f1,
                formula2=f2,
                sqref=sqref,
                ranges=ranges,
            )
            sheet.add_data_validation(dv)

    # 5b. Excel tables (ListObjects). The default (cellXfs[0]) font colour is recorded so
    # the renderer can tell unformatted cells, which take the table font, from cells
    # with a deliberate font colour.
    if style_deltas and style_deltas[0].fg_color:
        sheet.extra["default_font_color"] = style_deltas[0].fg_color
    sheet_dir = sheet_path.rsplit("/", 1)[0] if "/" in sheet_path else ""
    sheet_file = sheet_path.rsplit("/", 1)[-1]
    ws_rels_path = (
        f"{sheet_dir}/_rels/{sheet_file}.rels" if sheet_dir else f"_rels/{sheet_file}.rels"
    )
    parse_worksheet_tables(
        zip_file,
        root,
        sheet,
        _parse_rels(zip_file, ws_rels_path),
        theme_colors=theme_colors,
        custom_styles=getattr(style_deltas, "table_styles", None),
        dxfs=getattr(style_deltas, "dxfs", None),
    )

    # 6. Floating drawings
    _parse_worksheet_drawings(zip_file, sheet_path, sheet, theme_colors)
    sheet.extra["xlsx_drawings_signature"] = drawings_signature(sheet.drawings)

    # 7. Worksheet comments
    _parse_worksheet_comments(zip_file, sheet_path, sheet)


def _parse_worksheet_drawings(
    zip_file: zipfile.ZipFile,
    sheet_path: str,
    sheet: SheetDataModel,
    theme_colors: Sequence[str] | None = None,
) -> None:
    """Parse Drawings / Floating Objects associated with sheet_path."""
    sheet_dir = sheet_path.rsplit("/", 1)[0] if "/" in sheet_path else ""
    sheet_file = sheet_path.rsplit("/", 1)[-1]
    rels_path = f"{sheet_dir}/_rels/{sheet_file}.rels" if sheet_dir else f"_rels/{sheet_file}.rels"
    sheet_rels = _parse_rels(zip_file, rels_path)

    drawing_path: str | None = None
    for _, (rel_type, target) in sheet_rels.items():
        if rel_type in ("drawing", "spreadsheetDrawing") or rel_type.endswith("/drawing"):
            drawing_path = target
            break

    if not drawing_path or drawing_path not in zip_file.namelist():
        return

    try:
        drw_content = zip_file.read(drawing_path)
        drw_root = ET.fromstring(drw_content)
    except (KeyError, ET.ParseError):
        return

    # Parse drawing rels for images
    drw_dir = drawing_path.rsplit("/", 1)[0] if "/" in drawing_path else ""
    drw_file = drawing_path.rsplit("/", 1)[-1]
    drw_rels_path = f"{drw_dir}/_rels/{drw_file}.rels" if drw_dir else f"_rels/{drw_file}.rels"
    drw_rels = _parse_rels(zip_file, drw_rels_path)

    if not hasattr(sheet, "drawings") or sheet.drawings is None:
        sheet.drawings = []

    drawing_ctx = DrawingContext(
        zip_file=zip_file, rels=drw_rels, theme=dml_theme_map(theme_colors)
    )

    for anchor_el in drw_root:
        tag = _clean_tag(anchor_el.tag)
        if tag not in ("twoCellAnchor", "oneCellAnchor", "absoluteAnchor"):
            continue

        abs_rect = (0, 0, 120, 80)
        if tag == "oneCellAnchor":
            anchor_type = AnchorType.ONE_CELL
            ext_el = _find_child(anchor_el, "ext")
            if ext_el is not None:
                cx_str = _attr(ext_el, "cx", "0")
                cy_str = _attr(ext_el, "cy", "0")
                try:
                    abs_w = max(4, int(cx_str) // 9525)
                    abs_h = max(4, int(cy_str) // 9525)
                    abs_rect = (0, 0, abs_w, abs_h)
                except ValueError:
                    pass
        elif tag == "absoluteAnchor":
            anchor_type = AnchorType.ABSOLUTE
            pos_el = _find_child(anchor_el, "pos")
            ext_el = _find_child(anchor_el, "ext")
            pos_x = int(_attr(pos_el, "x", "0")) // 9525 if pos_el is not None else 0
            pos_y = int(_attr(pos_el, "y", "0")) // 9525 if pos_el is not None else 0
            abs_w = int(_attr(ext_el, "cx", "0")) // 9525 if ext_el is not None else 120
            abs_h = int(_attr(ext_el, "cy", "0")) // 9525 if ext_el is not None else 80
            abs_rect = (pos_x, pos_y, max(4, abs_w), max(4, abs_h))
        else:
            edit_as_str = _attr(anchor_el, "editAs", "twoCell")
            try:
                anchor_type = AnchorType(edit_as_str)
            except ValueError:
                anchor_type = AnchorType.TWO_CELL

        from_pt = CellAnchorPoint()
        from_el = _find_child(anchor_el, "from")
        if from_el is not None:
            c_el = _find_child(from_el, "col")
            co_el = _find_child(from_el, "colOff")
            r_el = _find_child(from_el, "row")
            ro_el = _find_child(from_el, "rowOff")
            from_pt.col = int(c_el.text) if c_el is not None and c_el.text else 0
            from_pt.col_off = (int(co_el.text) // 9525) if co_el is not None and co_el.text else 0
            from_pt.row = int(r_el.text) if r_el is not None and r_el.text else 0
            from_pt.row_off = (int(ro_el.text) // 9525) if ro_el is not None and ro_el.text else 0

        to_pt = CellAnchorPoint()
        to_el = _find_child(anchor_el, "to")
        if to_el is not None:
            c_el = _find_child(to_el, "col")
            co_el = _find_child(to_el, "colOff")
            r_el = _find_child(to_el, "row")
            ro_el = _find_child(to_el, "rowOff")
            to_pt.col = int(c_el.text) if c_el is not None and c_el.text else 0
            to_pt.col_off = (int(co_el.text) // 9525) if co_el is not None and co_el.text else 0
            to_pt.row = int(r_el.text) if r_el is not None and r_el.text else 0
            to_pt.row_off = (int(ro_el.text) // 9525) if ro_el is not None and ro_el.text else 0

        content_el = first_shape_element(anchor_el)
        if content_el is None:
            continue

        # twoCellAnchor always places the object by its from/to cells; editAs only
        # governs how it reacts to later cell edits. oneCell keeps the xfrm size,
        # absolute needs the cell rect resolved by the layer (sheet geometry).
        anchor_resolved = True
        if tag == "twoCellAnchor" and anchor_type == AnchorType.ONE_CELL:
            xf = element_xfrm(content_el)
            if xf is not None and xf.cx > 0 and xf.cy > 0:
                abs_rect = (0, 0, max(4, xf.cx // 9525), max(4, xf.cy // 9525))
            else:
                anchor_resolved = False
        elif tag == "twoCellAnchor" and anchor_type == AnchorType.ABSOLUTE:
            anchor_resolved = False

        gf_el = content_el if _clean_tag(content_el.tag) == "graphicFrame" else None
        if gf_el is None:
            shape_obj = parse_shape_element(content_el, drawing_ctx)
            if shape_obj is None:
                continue
            shape_obj.anchor_type = anchor_type
            shape_obj.from_point = from_pt
            shape_obj.to_point = to_pt
            shape_obj.abs_rect = abs_rect
            shape_obj.anchor_resolved = anchor_resolved
            shape_obj.z_index = len(sheet.drawings)
            sheet.drawings.append(shape_obj)

        else:
            obj_id = 1
            obj_name = "Chart"
            chart_dict: dict[str, Any] | None = None

            nv_gf = _find_child(gf_el, "nvGraphicFramePr")
            if nv_gf is not None:
                c_nv = _find_child(nv_gf, "cNvPr")
                if c_nv is not None:
                    id_val = _attr(c_nv, "id")
                    if id_val and id_val.isdigit():
                        obj_id = int(id_val)
                    obj_name = _attr(c_nv, "name", "Chart") or "Chart"

            graphic_el = _find_child(gf_el, "graphic")
            if graphic_el is not None:
                graphic_data = _find_child(graphic_el, "graphicData")
                if graphic_data is not None:
                    chart_el = _find_child(graphic_data, "chart")
                    if chart_el is not None:
                        r_id = _attr(chart_el, "id")
                        if not r_id:
                            for k, v in chart_el.attrib.items():
                                if k.endswith("}id") or k == "id":
                                    r_id = v
                                    break
                        if r_id and r_id in drw_rels:
                            chart_target = drw_rels[r_id][1]
                            if chart_target in zip_file.namelist():
                                try:
                                    from atboffice.modules.presentation.chart.io import (
                                        parse_chart_xml,
                                    )

                                    chart_bytes = zip_file.read(chart_target)
                                    parsed_chart = parse_chart_xml(
                                        chart_bytes, worksheet_defaults=True
                                    )
                                    chart_dict = parsed_chart.to_dict()
                                except Exception:
                                    logger.warning(
                                        "Failed to parse chart XML %s", chart_target
                                    )

            obj = FloatingObject(
                id=obj_id,
                name=obj_name,
                kind="chart",
                anchor_type=anchor_type,
                from_point=from_pt,
                to_point=to_pt,
                abs_rect=abs_rect,
                z_index=len(sheet.drawings),
                chart_data=chart_dict,
                anchor_resolved=anchor_resolved,
            )
            sheet.drawings.append(obj)


def _strip_author_prefix(text: str, author: str) -> str:
    """Drop the ``"Author:"`` header Excel stores at the start of a note.

    Excel writes the author as a bold leading run (``"Author:"`` followed by a
    line break). The callout painter draws the author header itself, so keep
    only the body here to avoid showing the name twice.
    """
    name = (author or "").strip()
    if not name:
        return text
    prefix = f"{name}:"
    if not text.startswith(prefix):
        return text
    return text[len(prefix):].lstrip(" \t").removeprefix("\r\n").removeprefix("\n")


def _parse_worksheet_comments(
    zip_file: zipfile.ZipFile,
    sheet_path: str,
    sheet: SheetDataModel,
) -> None:
    """Parse comments and associated VML notes for sheet_path."""
    sheet_dir = sheet_path.rsplit("/", 1)[0] if "/" in sheet_path else ""
    sheet_file = sheet_path.rsplit("/", 1)[-1]
    rels_path = f"{sheet_dir}/_rels/{sheet_file}.rels" if sheet_dir else f"_rels/{sheet_file}.rels"
    sheet_rels = _parse_rels(zip_file, rels_path)

    comments_path: str | None = None
    vml_path: str | None = None

    for _, (rel_type, target) in sheet_rels.items():
        if rel_type in ("comments",) or rel_type.endswith("/comments"):
            comments_path = target
        elif rel_type in ("vmlDrawing",) or rel_type.endswith("/vmlDrawing"):
            vml_path = target

    if not comments_path or comments_path not in zip_file.namelist():
        return

    try:
        c_content = zip_file.read(comments_path)
        c_root = ET.fromstring(c_content)
    except (KeyError, ET.ParseError):
        return

    # 1. Parse Authors
    authors: list[str] = []
    authors_el = _find_child(c_root, "authors")
    if authors_el is not None:
        for a_el in _find_children(authors_el, "author"):
            authors.append(a_el.text or "")

    # 2. Parse VML Note Visibility if available
    vml_visible_cells: set[tuple[int, int]] = set()
    if vml_path and vml_path in zip_file.namelist():
        try:
            vml_text = zip_file.read(vml_path).decode("utf-8", errors="replace")
            shape_re = re.compile(r"<v:shape\b([^>]*)>([\s\S]*?)</v:shape>", re.IGNORECASE)
            for m in shape_re.finditer(vml_text):
                attrs_str, body = m.group(1), m.group(2)
                if 'ObjectType="Note"' in body or 'type="#_x0000_t202"' in attrs_str:
                    row_m = re.search(r"<x:Row>\s*(\d+)\s*</x:Row>", body, re.IGNORECASE)
                    col_m = re.search(r"<x:Column>\s*(\d+)\s*</x:Column>", body, re.IGNORECASE)
                    if row_m and col_m:
                        vr, vc = int(row_m.group(1)), int(col_m.group(1))
                        vis_pat = (
                            r"<x:Visible\s*/>|<x:Visible>True</x:Visible>"
                            r"|visibility:\s*visible"
                        )
                        is_vis = bool(re.search(vis_pat, body + attrs_str, re.IGNORECASE))
                        if is_vis:
                            vml_visible_cells.add((vr, vc))
        except Exception:
            pass

    # 3. Parse Comments
    cl_el = _find_child(c_root, "commentList")
    if cl_el is not None:
        for c_el in _find_children(cl_el, "comment"):
            ref = _attr(c_el, "ref")
            if not ref:
                continue
            parsed_loc = parse_cell(ref)
            if not parsed_loc:
                continue
            r, c = parsed_loc["r"], parsed_loc["c"]

            author_id_str = _attr(c_el, "authorId", "0")
            author = ""
            try:
                aid = int(author_id_str or 0)
                if 0 <= aid < len(authors):
                    author = authors[aid]
            except ValueError:
                pass

            text_parts: list[str] = []
            txt_el = _find_child(c_el, "text")
            if txt_el is not None:
                for elem in txt_el.iter():
                    if _clean_tag(elem.tag) == "t" and elem.text:
                        text_parts.append(elem.text)
            text = _strip_author_prefix("".join(text_parts), author)
            is_visible = (r, c) in vml_visible_cells

            sheet.set_comment(r, c, text, author=author, visible=is_visible)


def _open_zip(source: str | Path | bytes | BinaryIO) -> zipfile.ZipFile:
    """Open a ZipFile from file path, bytes, or binary file stream."""
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists() or not p.is_file():
            raise ValueError(f"File not found: {source}")
        try:
            return zipfile.ZipFile(p, "r")
        except zipfile.BadZipFile as err:
            raise ValueError(f"File '{source}' is not a valid XLSX archive.") from err

    if isinstance(source, bytes):
        try:
            return zipfile.ZipFile(io.BytesIO(source), "r")
        except zipfile.BadZipFile as err:
            raise ValueError("Provided data is not a valid XLSX archive.") from err

    if hasattr(source, "read"):
        try:
            return zipfile.ZipFile(source, "r")
        except zipfile.BadZipFile as err:
            raise ValueError("Provided stream is not a valid XLSX archive.") from err

    raise ValueError(f"Unsupported source type: {type(source)}")


def _parse_icon_set(is_el: ET.Element | None, x14: bool = False) -> IconSetRule | None:
    """Parse ``<iconSet>`` (main namespace) or ``<x14:iconSet>`` into an IconSetRule.

    Main-namespace cfvos carry ``val``; x14 cfvos carry an ``<xm:f>`` child
    (see ``ledger/js/xlsx-read.js:810`` and ``:885-889``).
    """
    if is_el is None:
        return None
    cfvos: list[CFVO] = []
    for vo_el in _find_children(is_el, "cfvo"):
        val: Any = _attr(vo_el, "val")
        f_el = _find_child(vo_el, "f")
        if f_el is not None and f_el.text is not None:
            val = f_el.text.strip()
        cfvos.append(
            CFVO(
                type=_attr(vo_el, "type", "percent") or "percent",
                val=val,
                gte=_attr(vo_el, "gte") not in ("0", "false"),
            )
        )
    custom: list[tuple[str, int]] = []
    for ci_el in _find_children(is_el, "cfIcon"):
        try:
            icon_id = int(_attr(ci_el, "iconId", "0") or 0)
        except ValueError:
            icon_id = 0
        custom.append((_attr(ci_el, "iconSet", "") or "", icon_id))
    return IconSetRule(
        set_name=_attr(is_el, "iconSet") or "3TrafficLights1",
        cfvos=cfvos,
        reverse=_attr(is_el, "reverse") in ("1", "true"),
        show_value=_attr(is_el, "showValue") not in ("0", "false"),
        percent=_attr(is_el, "percent") not in ("0", "false"),
        custom=custom,
        x14=x14,
    )


def _parse_x14_icon_set_formats(root: ET.Element) -> list[ConditionalFormat]:
    """Read icon-set rules stored only in the worksheet x14 ``extLst``."""
    out: list[ConditionalFormat] = []
    ext_lst = _find_child(root, "extLst")
    for ext_el in _find_children(ext_lst, "ext"):
        for cfs_el in _find_children(ext_el, "conditionalFormattings"):
            for cf_el in _find_children(cfs_el, "conditionalFormatting"):
                sq_el = _find_child(cf_el, "sqref")
                sqref = (sq_el.text or "").strip() if sq_el is not None else ""
                ranges: list[tuple[int, int, int, int]] = []
                for part in sqref.split():
                    rg = parse_range(part)
                    if rg:
                        ranges.append((rg["r1"], rg["c1"], rg["r2"], rg["c2"]))
                if not ranges:
                    continue
                rules: list[CFRule] = []
                for r_el in _find_children(cf_el, "cfRule"):
                    if _attr(r_el, "type") != "iconSet":
                        continue  # x14 data bars and others are not handled here
                    icon_rule = _parse_icon_set(_find_child(r_el, "iconSet"), x14=True)
                    if icon_rule is None:
                        continue
                    try:
                        priority = int(_attr(r_el, "priority", "1") or 1)
                    except ValueError:
                        priority = 1
                    rules.append(
                        CFRule(
                            type="iconSet",
                            priority=priority,
                            stop_if_true=_attr(r_el, "stopIfTrue") in ("1", "true"),
                            icon_set=icon_rule,
                        )
                    )
                if rules:
                    out.append(ConditionalFormat(sqref=sqref, ranges=ranges, rules=rules))
    return out


def read_xlsx(
    source: str | Path | bytes | BinaryIO,
    workbook: WorkbookModel | None = None,
) -> WorkbookModel:
    """Read an OpenXML spreadsheet (.xlsx / .xlsm) into a WorkbookModel.

    Args:
        source: Path to file, raw bytes, or readable binary stream.
        workbook: Existing WorkbookModel to populate. If None, a new instance is created.

    Returns:
        WorkbookModel populated with worksheets and cell data.

    Raises:
        ValueError: If the file is not a valid or readable XLSX archive.
    """
    wb = workbook if workbook is not None else WorkbookModel()

    # Capture SourcePackage for lossless Part-level Carry
    try:
        if isinstance(source, bytes):
            source_pkg = SourcePackage.from_bytes(source)
        elif isinstance(source, (str, Path)):
            source_pkg = SourcePackage.open(source)
        elif hasattr(source, "read"):
            pos = source.tell() if hasattr(source, "tell") else 0
            buf = source.read()
            if hasattr(source, "seek"):
                source.seek(pos)
            source_pkg = SourcePackage.from_bytes(buf)
        else:
            source_pkg = None
    except Exception:
        source_pkg = None

    if source_pkg is not None:
        wb._source_package = source_pkg
        wb.extra["source_package"] = source_pkg
        if (
            source_pkg.has_part("xl/vbaProject.bin")
            or source_pkg.get_content_type("xl/workbook.xml")
            == "application/vnd.ms-excel.sheet.macroEnabled.main+xml"
        ):
            wb.extra["is_macro_enabled"] = True

    with _open_zip(source) as z:
        # 1. Discover workbook.xml via _rels/.rels
        root_rels = _parse_rels(z, "_rels/.rels")
        wb_part = "xl/workbook.xml"
        for _, (rel_type, target) in root_rels.items():
            if rel_type in ("officeDocument", "workbook"):
                wb_part = target
                break

        # Fallback check
        if wb_part not in z.namelist():
            for name in z.namelist():
                if name.lower().endswith("workbook.xml"):
                    wb_part = name
                    break

        wb.extra["xlsx_workbook_part"] = wb_part
        try:
            wb_xml_content = z.read(wb_part)
            wb_root = ET.fromstring(wb_xml_content)
        except (KeyError, ET.ParseError) as err:
            raise ValueError(f"Archive is damaged: missing or invalid '{wb_part}'.") from err

        # Extract workbook properties and codeName
        wpr_el = _find_child(wb_root, "workbookPr")
        if wpr_el is not None:
            c_name = _attr(wpr_el, "codeName")
            if c_name:
                wb.code_name = c_name
                wb.extra["code_name"] = c_name
            if _attr(wpr_el, "date1904") in ("1", "true"):
                wb.extra["date1904"] = True

        fv_el = _find_child(wb_root, "fileVersion")
        if fv_el is not None and _attr(fv_el, "codeName"):
            wb.extra["file_version_code_name"] = _attr(fv_el, "codeName")

        wp_el = _find_child(wb_root, "workbookProtection")
        if wp_el is not None:
            wb.extra["protection"] = dict(wp_el.attrib)

        dn_m = re.search(
            r"(<(?:\w+:)?definedNames\b.*?</(?:\w+:)?definedNames>)",
            wb_xml_content.decode("utf-8", "ignore"),
            re.DOTALL,
        )
        if dn_m:
            dn_raw = dn_m.group(1)
            # Normalize to default namespace tags (<definedNames>, <definedName>)
            dn_clean = re.sub(
                r"</?([a-zA-Z0-9_]+):(definedNames?)\b",
                lambda m: ("</" if m.group(0).startswith("</") else "<") + m.group(2),
                dn_raw,
            )
            wb.extra["defined_names"] = dn_clean
            wb.extra["defined_names_loaded"] = dn_clean

        # 2. Parse workbook relationships
        wb_dir = wb_part.rsplit("/", 1)[0] if "/" in wb_part else ""
        wb_file_name = wb_part.rsplit("/", 1)[-1]
        if wb_dir:
            wb_rels_path = f"{wb_dir}/_rels/{wb_file_name}.rels"
        else:
            wb_rels_path = f"_rels/{wb_part}.rels"
        wb_rels = _parse_rels(z, wb_rels_path)

        # Locate sharedStrings, styles, and theme
        sst_path: str | None = None
        styles_path: str | None = None
        theme_path: str | None = None
        for _, (rel_type, target) in wb_rels.items():
            if rel_type == "sharedStrings":
                sst_path = target
            elif rel_type == "styles":
                styles_path = target
            elif rel_type == "theme":
                theme_path = target

        if not sst_path:
            for name in z.namelist():
                if name.lower().endswith("sharedstrings.xml"):
                    sst_path = name
                    break

        if not styles_path:
            for name in z.namelist():
                if name.lower().endswith("styles.xml"):
                    styles_path = name
                    break

        if not theme_path or theme_path not in z.namelist():
            if "xl/theme/theme1.xml" in z.namelist():
                theme_path = "xl/theme/theme1.xml"
            else:
                theme_path = next(
                    (n for n in z.namelist() if n.lower().endswith("theme1.xml")),
                    None,
                )

        # 3. Parse theme, styles (including custom palette), and shared strings
        if theme_path and theme_path in z.namelist():
            try:
                parsed_theme = parse_theme_xml(z.read(theme_path))
                wb.theme_colors = list(parsed_theme["colors"])
                wb.theme_name = parsed_theme["name"]
                wb.theme_major_font = parsed_theme["major"]
                wb.theme_minor_font = parsed_theme["minor"]
                wb.extra["theme"] = parsed_theme
                wb.extra["theme_part"] = theme_path
            except KeyError:
                pass

        style_deltas = (
            _parse_styles(
                z,
                styles_path,
                theme_colors=wb.theme_colors,
                palette=wb.indexed_palette,
                workbook=wb,
            )
            if styles_path
            else [FormatDelta()]
        )
        if styles_path:
            # The writer appends to the original stylesheet on save, so that style
            # indices carried in untouched XML (cols, rows, CF dxfIds) stay valid.
            wb.extra["xlsx_styles_part"] = styles_path
            wb.extra["xlsx_style_deltas"] = style_deltas
        active_palette = wb.indexed_palette or DEFAULT_INDEXED_PALETTE
        sst = (
            _parse_shared_strings(
                z, sst_path, theme_colors=wb.theme_colors, palette=active_palette
            )
            if sst_path
            else []
        )

        # 4. Parse sheets list from workbook.xml
        sheets_el = _find_child(wb_root, "sheets")
        if sheets_el is None:
            raise ValueError("Workbook XML contains no <sheets> definition.")

        sheet_entries: list[tuple[str, str | None, dict[str, str | None]]] = []
        for s_el in _find_children(sheets_el, "sheet"):
            s_name = _unescape_xml_text(_attr(s_el, "name", "Sheet1"))
            r_id = _attr(s_el, "id")
            s_part = wb_rels.get(r_id, (None, None))[1] if r_id else None
            meta = {
                "sheet_id": _attr(s_el, "sheetId"),
                "sheet_state": _attr(s_el, "state"),
                "sheet_rel_id": r_id,
            }
            sheet_entries.append((s_name, s_part, meta))

        if not sheet_entries:
            raise ValueError("No worksheets found in workbook.")

        # Determine active tab
        active_tab_idx = 0
        bv_el = _find_child(wb_root, "bookViews")
        if bv_el is not None:
            wv_el = _find_child(bv_el, "workbookView")
            if wv_el is not None:
                at_str = _attr(wv_el, "activeTab")
                if at_str:
                    try:
                        active_tab_idx = max(0, int(at_str))
                    except ValueError:
                        pass

        # Clear existing sheets if workbook already had default sheet
        while len(wb) > 0:
            if len(wb) == 1 and wb[0].name == sheet_entries[0][0]:
                # Reuse the existing sheet if the name matches
                break
            if len(wb) > 1:
                wb.remove_sheet(0)
            else:
                # Rename the only remaining sheet to first sheet name
                wb.rename_sheet(0, sheet_entries[0][0])
                break

        # 5. Populate sheets
        for idx, (s_name, s_part, meta) in enumerate(sheet_entries):
            if idx == 0 and len(wb) == 1 and wb[0].name == s_name:
                sheet_model = wb[0]
            else:
                sheet_model = wb.add_sheet(name=s_name)
            for key, value in meta.items():
                if value:
                    sheet_model.extra[key] = value

            if s_part:
                sheet_model._ooxml_part = s_part
                sheet_model.extra["ooxml_part"] = s_part
                _parse_worksheet(
                    z,
                    s_part,
                    sheet_model,
                    sst,
                    style_deltas,
                    theme_colors=wb.theme_colors,
                    palette=active_palette,
                )
            sheet_model.dirty = False

        # Set active sheet index
        if 0 <= active_tab_idx < len(wb):
            wb.set_active_sheet_index(active_tab_idx)

        # 6. Parse and preserve Pivot Tables & Pivot Caches if present
        pivots = read_pivots_from_zip(z, wb)
        if pivots is not None:
            wb.extra["pivots"] = pivots

        wb.dirty = False

    return wb
