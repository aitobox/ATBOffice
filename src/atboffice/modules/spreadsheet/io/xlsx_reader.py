"""Pure Python Open Packaging Conventions (OPC) XLSX reader for ATBOffice Ledger."""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import BinaryIO

from atboffice.modules.spreadsheet.calc.references import (
    parse_cell,
    parse_range,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    FormatDelta,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

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

    base_dir = rels_path.replace("/_rels/", "/").rsplit(".rels", 1)[0]
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


def _parse_shared_strings(zip_file: zipfile.ZipFile, sst_path: str) -> list[str]:
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
        t_el = _find_child(si, "t")
        if t_el is not None:
            sst.append(_unescape_xml_text(t_el.text or ""))
            continue

        # Check for rich text runs <r><t>...</t></r>
        runs = _find_children(si, "r")
        if runs:
            parts = []
            for r in runs:
                rt = _find_child(r, "t")
                if rt is not None and rt.text:
                    parts.append(_unescape_xml_text(rt.text))
            sst.append("".join(parts))
        else:
            sst.append("")

    return sst


def _parse_color(el: ET.Element | None) -> str | None:
    """Extract 8-character ARGB hex string from color element."""
    if el is None:
        return None
    rgb = _attr(el, "rgb")
    if rgb:
        clean = rgb.replace("#", "").upper()
        if len(clean) == 6:
            return "FF" + clean
        return clean
    return None


def _parse_border_side(side_el: ET.Element | None) -> BorderStyle | None:
    """Parse single border side element (left, right, top, bottom, etc.)."""
    if side_el is None:
        return None
    style = _attr(side_el, "style")
    if not style or style == "none":
        return None
    col = _parse_color(_find_child(side_el, "color"))
    return BorderStyle(style=style, color=col)


def _parse_styles(zip_file: zipfile.ZipFile, styles_path: str) -> list[FormatDelta]:
    """Parse xl/styles.xml into a list of FormatDelta objects indexed by xfId."""
    deltas: list[FormatDelta] = []
    try:
        content = zip_file.read(styles_path)
    except KeyError:
        return [FormatDelta()]

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return [FormatDelta()]

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
                col = _parse_color(c_el)
                if col:
                    font_info["color"] = col
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
                    fg = _parse_color(_find_child(pf, "fgColor"))
                    bg = _parse_color(_find_child(pf, "bgColor"))
                    fill_info["bg_color"] = fg or bg
            fills.append(fill_info)

    # 4. Borders
    borders: list[dict[str, BorderStyle | None]] = []
    borders_el = _find_child(root, "borders")
    if borders_el is not None:
        for b_el in _find_children(borders_el, "border"):
            b_info = {
                "top": _parse_border_side(_find_child(b_el, "top")),
                "bottom": _parse_border_side(_find_child(b_el, "bottom")),
                "left": _parse_border_side(_find_child(b_el, "left")),
                "right": _parse_border_side(_find_child(b_el, "right")),
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
                except ValueError:
                    pass

            # Fill
            fill_id_str = _attr(xf, "fillId")
            if fill_id_str is not None:
                try:
                    fill_id = int(fill_id_str)
                    if 0 <= fill_id < len(fills):
                        fl = fills[fill_id]
                        if "bg_color" in fl:
                            delta.bg_color = fl["bg_color"]
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

            deltas.append(delta)

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


def _parse_worksheet(
    zip_file: zipfile.ZipFile,
    sheet_path: str,
    sheet: SheetDataModel,
    sst: list[str],
    style_deltas: list[FormatDelta],
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

    # 1. Custom column widths & hidden columns
    cols_el = _find_child(root, "cols")
    if cols_el is not None:
        for col_el in _find_children(cols_el, "col"):
            min_c_str = _attr(col_el, "min")
            max_c_str = _attr(col_el, "max")
            width_str = _attr(col_el, "width")
            hidden = _attr(col_el, "hidden") in ("1", "true")

            if min_c_str and max_c_str:
                try:
                    c1 = max(0, int(min_c_str) - 1)
                    c2 = max(c1, int(max_c_str) - 1)
                    w_px = int(float(width_str) * 8) if width_str else None

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
                    ht_px = int(float(ht_str) * 1.33)
                    sheet.geometry.set_row_height(curr_r, ht_px)
                except ValueError:
                    pass

            if _attr(row_el, "hidden") in ("1", "true"):
                sheet.geometry.hidden_rows.add(curr_r)

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
                if formula_el is not None and formula_el.text:
                    ftext = formula_el.text.strip()
                    formula_str = ftext.lstrip("=")

                # Parse value
                val_str: str | None = None
                if cell_type == "inlineStr":
                    is_el = _find_child(c_el, "is")
                    if is_el is not None:
                        t_el = _find_child(is_el, "t")
                        if t_el is not None:
                            val_str = t_el.text
                else:
                    v_el = _find_child(c_el, "v")
                    if v_el is not None:
                        val_str = v_el.text

                parsed_value = _parse_cell_value(val_str, cell_type, sst)

                # Skip completely empty cells without formula or style
                if parsed_value is None and formula_str is None and not style_idx_str:
                    continue

                cell = CellData(value=parsed_value, formula=formula_str)

                # Apply style delta
                if style_idx_str:
                    try:
                        s_idx = int(style_idx_str)
                        if 0 <= s_idx < len(style_deltas):
                            delta = style_deltas[s_idx]
                            sheet.set_cell(r, c, cell)
                            sheet.apply_format_delta(r, c, delta)
                            continue
                    except ValueError:
                        pass

                sheet.set_cell(r, c, cell)

    # 3. Merged cells
    merges_el = _find_child(root, "mergeCells")
    if merges_el is not None:
        for m_el in _find_children(merges_el, "mergeCell"):
            ref = _attr(m_el, "ref")
            if ref:
                rg = parse_range(ref)
                if rg:
                    sheet.add_merge(rg["r1"], rg["c1"], rg["r2"], rg["c2"])


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

        try:
            wb_xml_content = z.read(wb_part)
            wb_root = ET.fromstring(wb_xml_content)
        except (KeyError, ET.ParseError) as err:
            raise ValueError(f"Archive is damaged: missing or invalid '{wb_part}'.") from err

        # 2. Parse workbook relationships
        wb_dir = wb_part.rsplit("/", 1)[0] if "/" in wb_part else ""
        wb_file_name = wb_part.rsplit("/", 1)[-1]
        if wb_dir:
            wb_rels_path = f"{wb_dir}/_rels/{wb_file_name}.rels"
        else:
            wb_rels_path = f"_rels/{wb_part}.rels"
        wb_rels = _parse_rels(z, wb_rels_path)

        # Locate sharedStrings and styles
        sst_path: str | None = None
        styles_path: str | None = None
        for _, (rel_type, target) in wb_rels.items():
            if rel_type == "sharedStrings":
                sst_path = target
            elif rel_type == "styles":
                styles_path = target

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

        # 3. Parse shared strings and styles
        sst = _parse_shared_strings(z, sst_path) if sst_path else []
        style_deltas = _parse_styles(z, styles_path) if styles_path else [FormatDelta()]

        # 4. Parse sheets list from workbook.xml
        sheets_el = _find_child(wb_root, "sheets")
        if sheets_el is None:
            raise ValueError("Workbook XML contains no <sheets> definition.")

        sheet_entries: list[tuple[str, str | None]] = []
        for s_el in _find_children(sheets_el, "sheet"):
            s_name = _unescape_xml_text(_attr(s_el, "name", "Sheet1"))
            r_id = _attr(s_el, "id")
            s_part = wb_rels.get(r_id, (None, None))[1] if r_id else None
            sheet_entries.append((s_name, s_part))

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
        for idx, (s_name, s_part) in enumerate(sheet_entries):
            if idx == 0 and len(wb) == 1 and wb[0].name == s_name:
                sheet_model = wb[0]
            else:
                sheet_model = wb.add_sheet(name=s_name)

            if s_part:
                _parse_worksheet(z, s_part, sheet_model, sst, style_deltas)

        # Set active sheet index
        if 0 <= active_tab_idx < len(wb):
            wb.set_active_sheet_index(active_tab_idx)

    return wb
