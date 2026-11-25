"""Format > AutoFormat presets modelled on Excel 2003's classic table formats."""

from __future__ import annotations

from typing import Any

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.models.sheet_model import BorderStyle

# preset id -> display name (translated lazily)
PRESETS: list[tuple[str, str]] = [
    ("simple", "简单"),
    ("classic1", "古典 1"),
    ("accounting1", "会计 1"),
    ("colorful1", "彩色 1"),
    ("list1", "列表 1"),
    ("none", "无"),
]


def preset_names() -> list[tuple[str, str]]:
    return [(pid, safe_tr(label)) for pid, label in PRESETS]


def _thin() -> BorderStyle:
    return BorderStyle(style="thin", color="#000000")


def apply_autoformat(sheet: Any, rect: tuple[int, int, int, int], preset: str) -> None:
    """Apply ``preset`` to the table in ``rect`` (first row treated as the header)."""
    r1, c1, r2, c2 = rect
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            cell = sheet.ensure_cell(r, c)
            header = r == r1
            last = r == r2
            if preset == "none":
                cell.bold = cell.italic = False
                cell.bg_color = None
                cell.pattern = None
                cell.fg_color = None
                cell.border_top = cell.border_bottom = None
                cell.border_left = cell.border_right = None
                continue
            if preset == "simple":
                cell.bold = header
                cell.border_top = _thin() if header else None
                cell.border_bottom = _thin() if header or last else None
            elif preset == "classic1":
                cell.bold = header or c == c1
                cell.italic = header
                cell.border_bottom = _thin() if header or last else None
                cell.border_top = _thin() if header else None
            elif preset == "accounting1":
                cell.bold = header
                if not header and isinstance(cell.value, (int, float)) and not isinstance(
                    cell.value, bool
                ):
                    cell.format_code = "#,##0.00"
                cell.border_bottom = (
                    _thin()
                    if header
                    else BorderStyle(style="double", color="#000000") if last else None
                )
            elif preset == "colorful1":
                if header:
                    cell.bold = True
                    cell.fg_color = "#FFFFFF"
                    cell.bg_color = "#000080"
                else:
                    cell.bold = False
                    cell.fg_color = None
                    cell.bg_color = "#CCFFFF" if (r - r1) % 2 else "#FFFFFF"
                cell.pattern = "solid"
            elif preset == "list1":
                cell.bold = header
                cell.border_bottom = _thin() if header else None
                cell.bg_color = None if header or (r - r1) % 2 else "#FFFFCC"
                cell.pattern = None if cell.bg_color is None else "solid"
    sheet.dirty = True
