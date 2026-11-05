"""Excel 97-2003 (.xls) binary workbook reader for ATBOffice Ledger.

Leverages Python's mature, pure-Python xlrd ecosystem to read multi-worksheet
binary BIFF8/BIFF7/BIFF5 workbooks with cells, data types, geometries,
merged ranges, and styling into WorkbookModel and SheetDataModel.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, BinaryIO

from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

try:
    import xlrd
    HAS_XLRD = True
except ImportError:
    xlrd = None  # type: ignore[assignment]
    HAS_XLRD = False


def is_xls_supported() -> bool:
    """Return True if xlrd is installed and functional in the environment."""
    return HAS_XLRD


def _rgb_from_color_index(book: Any, color_index: int) -> str | None:
    """Convert an xlrd palette color index to a hexadecimal '#RRGGBB' string."""
    if not hasattr(book, "colour_map"):
        return None
    # 0x40 and above usually denote default/system color indices in BIFF
    if color_index is None or color_index >= 0x40 or color_index < 0:
        return None
    rgb = book.colour_map.get(color_index)
    if rgb and isinstance(rgb, (tuple, list)) and len(rgb) == 3:
        r, g, b = rgb
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            return f"#{r:02x}{g:02x}{b:02x}"
    return None


def _map_hor_align(hor_align: int) -> str:
    """Map xlrd horizontal alignment integer to ATBOffice alignment name."""
    mapping = {
        0: "general",
        1: "left",
        2: "center",
        3: "right",
        4: "fill",
        5: "justify",
        6: "center",
        7: "distributed",
    }
    return mapping.get(hor_align, "general")


def _map_vert_align(vert_align: int) -> str:
    """Map xlrd vertical alignment integer to ATBOffice alignment name."""
    mapping = {
        0: "top",
        1: "middle",
        2: "bottom",
        3: "justify",
        4: "distributed",
    }
    return mapping.get(vert_align, "bottom")


def _map_border_style(book: Any, line_style: int, color_index: int) -> BorderStyle | None:
    """Map xlrd border line style and color index to BorderStyle."""
    if not line_style or line_style == 0:
        return None
    style_names = {
        1: "thin",
        2: "medium",
        3: "dashed",
        4: "dotted",
        5: "thick",
        6: "double",
        7: "hair",
    }
    style = style_names.get(line_style, "thin")
    color = _rgb_from_color_index(book, color_index)
    return BorderStyle(style=style, color=color)


def read_xls(
    source: str | Path | bytes | BinaryIO,
    workbook: WorkbookModel | None = None,
) -> WorkbookModel:
    """Read a binary Excel 97-2003 (.xls) workbook into a WorkbookModel.

    Args:
        source: File path, raw bytes, or binary stream of an .xls file.
        workbook: Existing WorkbookModel to populate. If None, a new instance is created.

    Returns:
        WorkbookModel containing the imported worksheets and cell data.

    Raises:
        RuntimeError: If xlrd is not installed in the environment.
        PermissionError: If the workbook is password protected / encrypted.
        ValueError: If the file is not a valid BIFF workbook or is corrupted.
    """
    if not HAS_XLRD or xlrd is None:
        raise RuntimeError("xlrd is not installed in the current environment.")

    book_kwargs: dict[str, Any] = {}
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        book_kwargs["filename"] = str(p.resolve())
    elif isinstance(source, bytes):
        book_kwargs["file_contents"] = source
    elif hasattr(source, "read"):
        content = source.read()
        book_kwargs["file_contents"] = content
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")

    # Attempt opening with formatting_info=True first for full styles;
    # fall back to formatting_info=False on BIFF5/BIFF7 or NotImplementedError.
    book = None
    has_formatting = True
    try:
        book = xlrd.open_workbook(formatting_info=True, on_demand=False, **book_kwargs)
    except NotImplementedError:
        has_formatting = False
        book = xlrd.open_workbook(formatting_info=False, on_demand=False, **book_kwargs)
    except xlrd.biffh.XLRDError as err:
        err_msg = str(err).lower()
        if "encrypted" in err_msg or "password" in err_msg:
            raise PermissionError(f"Workbook is encrypted: {err}") from err
        # Try without formatting info if error was formatting related
        try:
            has_formatting = False
            book = xlrd.open_workbook(formatting_info=False, on_demand=False, **book_kwargs)
        except Exception as retry_err:
            raise ValueError(f"Failed to parse XLS workbook: {retry_err}") from retry_err
    except Exception as err:
        try:
            has_formatting = False
            book = xlrd.open_workbook(formatting_info=False, on_demand=False, **book_kwargs)
        except Exception:
            raise ValueError(f"Failed to parse XLS workbook: {err}") from err

    if book is None:
        raise ValueError("Could not open XLS workbook.")

    wb = workbook if workbook is not None else WorkbookModel()

    # Clear default or existing sheets
    wb._sheets.clear()
    wb._active_sheet_index = 0

    # Process each worksheet
    num_sheets = book.nsheets
    if num_sheets == 0:
        # Guarantee at least one sheet exists
        wb.add_sheet("Sheet1")
        return wb

    for sheet_idx in range(num_sheets):
        sheet = book.sheet_by_index(sheet_idx)
        sheet_name = sheet.name or f"Sheet{sheet_idx + 1}"
        sheet_model = SheetDataModel(name=sheet_name)

        # 1. Merged cells mapping: xlrd half-open [rlo, rhi), [clo, chi)
        # -> inclusive (rlo, clo, rhi-1, chi-1)
        merged_cells = getattr(sheet, "merged_cells", []) or []
        for rlo, rhi, clo, chi in merged_cells:
            if rhi > rlo and chi > clo:
                sheet_model.add_merge(rlo, clo, rhi - 1, chi - 1)

        # 2. Column widths & hidden columns
        colinfo_map = getattr(sheet, "colinfo_map", {}) or {}
        for col_idx, colinfo in colinfo_map.items():
            width_val = getattr(colinfo, "width", 0)
            if width_val > 0:
                # 256 units = 1 character width ~ 8 pixels standard at 96 DPI
                px = max(12, int(round((width_val / 256.0) * 8.0)))
                sheet_model.geometry.set_col_width(col_idx, px)
            if getattr(colinfo, "hidden", 0):
                sheet_model.geometry.hidden_cols.add(col_idx)

        # 3. Row heights & hidden rows
        rowinfo_map = getattr(sheet, "rowinfo_map", {}) or {}
        for row_idx, rowinfo in rowinfo_map.items():
            height_twips = getattr(rowinfo, "height", 0)
            has_default = getattr(rowinfo, "has_default_height", 0)
            if height_twips > 0 and not has_default:
                # 20 twips = 1 pt. At 96 DPI, 1 pt = 96/72 px = 1.333 px. px = twips / 15.0
                px = max(12, int(round(height_twips / 15.0)))
                sheet_model.geometry.set_row_height(row_idx, px)
            if getattr(rowinfo, "hidden", 0):
                sheet_model.geometry.hidden_rows.add(row_idx)

        # 4. Cell data extraction
        nrows = sheet.nrows
        ncols = sheet.ncols
        datemode = getattr(book, "datemode", 0)

        for r in range(nrows):
            for c in range(ncols):
                cell = sheet.cell(r, c)
                ctype = cell.ctype

                if ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    continue

                value: Any = None
                format_code = "General"

                if ctype == xlrd.XL_CELL_TEXT:
                    value = str(cell.value)
                elif ctype == xlrd.XL_CELL_NUMBER:
                    fval = float(cell.value)
                    value = int(fval) if fval.is_integer() else fval
                elif ctype == xlrd.XL_CELL_BOOLEAN:
                    value = bool(cell.value)
                elif ctype == xlrd.XL_CELL_DATE:
                    try:
                        dt = xlrd.xldate_as_datetime(cell.value, datemode)
                        if dt.time() == datetime.time(0, 0, 0):
                            value = dt.strftime("%Y-%m-%d")
                            format_code = "YYYY-MM-DD"
                        else:
                            value = dt.strftime("%Y-%m-%d %H:%M:%S")
                            format_code = "YYYY-MM-DD HH:MM:SS"
                    except Exception:
                        value = cell.value
                elif ctype == xlrd.XL_CELL_ERROR:
                    value = xlrd.error_text_from_code.get(cell.value, "#ERROR!")
                else:
                    value = cell.value

                # 5. Cell styles & formatting
                cell_data = CellData(value=value, format_code=format_code)

                if has_formatting:
                    try:
                        xf_idx = sheet.cell_xf_index(r, c)
                        xf = book.xf_list[xf_idx]
                        font = book.font_list[xf.font_index]

                        # Number format
                        if format_code == "General":
                            fmt_obj = book.format_map.get(xf.format_key)
                            if fmt_obj and fmt_obj.format_str:
                                cell_data.format_code = fmt_obj.format_str

                        # Font styles
                        cell_data.bold = bool(getattr(font, "bold", 0))
                        cell_data.italic = bool(getattr(font, "italic", 0))
                        cell_data.underline = bool(getattr(font, "underlined", 0))
                        cell_data.strike = bool(getattr(font, "struck_out", 0))
                        if getattr(font, "name", None):
                            cell_data.font_family = font.name
                        if getattr(font, "height", None):
                            cell_data.font_size = max(6, int(round(font.height / 20.0)))

                        fg_color = _rgb_from_color_index(book, getattr(font, "colour_index", 0))
                        if fg_color:
                            cell_data.fg_color = fg_color

                        # Background
                        bg = getattr(xf, "background", None)
                        if bg:
                            bg_cidx = getattr(bg, "background_colour_index", 0)
                            bg_color = _rgb_from_color_index(book, bg_cidx)
                            if bg_color:
                                cell_data.bg_color = bg_color

                        # Alignment
                        align = getattr(xf, "alignment", None)
                        if align:
                            cell_data.align_h = _map_hor_align(getattr(align, "hor_align", 0))
                            cell_data.align_v = _map_vert_align(getattr(align, "vert_align", 2))
                            cell_data.wrap_text = bool(getattr(align, "text_wrapped", 0))
                            cell_data.indent = int(getattr(align, "indent_level", 0))

                        # Borders
                        border = getattr(xf, "border", None)
                        if border:
                            cell_data.border_left = _map_border_style(
                                book, border.left_line_style, border.left_colour_index
                            )
                            cell_data.border_right = _map_border_style(
                                book, border.right_line_style, border.right_colour_index
                            )
                            cell_data.border_top = _map_border_style(
                                book, border.top_line_style, border.top_colour_index
                            )
                            cell_data.border_bottom = _map_border_style(
                                book, border.bottom_line_style, border.bottom_colour_index
                            )
                    except Exception:
                        pass

                sheet_model.set_cell(r, c, cell_data)

        wb.add_sheet(name=sheet_name, sheet=sheet_model)

    return wb
