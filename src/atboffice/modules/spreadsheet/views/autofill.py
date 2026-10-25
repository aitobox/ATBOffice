"""AutoFill sequence extrapolation engine and fill handle calculations for ATBOffice Ledger."""

from __future__ import annotations

import copy
import datetime
import re
from collections.abc import Callable
from typing import Any, Final

from atboffice.drawing.numfmt import (
    _is_date_format,
    date_to_serial,
    serial_to_parts,
)
from atboffice.modules.spreadsheet.calc.references import translate
from atboffice.modules.spreadsheet.models.selection_model import SelectionRange
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel

# Built-in sequence lists for cyclical autofill
DEFAULT_LISTS: Final[list[list[str]]] = [
    ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ],
    [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ],
    [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
    [
        "星期一",
        "星期二",
        "星期三",
        "星期四",
        "星期五",
        "星期六",
        "星期日",
    ],
    [
        "一月",
        "二月",
        "三月",
        "四月",
        "五月",
        "六月",
        "七月",
        "八月",
        "九月",
        "十月",
        "十一月",
        "十二月",
    ],
    ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"],
    ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"],
]

NUMBERED_TEXT_RE: Final[re.Pattern[str]] = re.compile(r"^(.*?)(\d+)(\D*)$")
ISO_DATE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$"
)


def _match_list(val_str: str) -> tuple[list[str], int] | None:
    """Find matching list and index for string (case-insensitive)."""
    s_lower = val_str.strip().lower()
    for lst in DEFAULT_LISTS:
        for idx, item in enumerate(lst):
            if item.lower() == s_lower:
                return lst, idx
    return None


def _case_like(template: str, text: str) -> str:
    """Format text casing similar to template."""
    if template.isupper() and template != template.lower():
        return text.upper()
    if template.islower() and template != template.upper():
        return text.lower()
    return text


def _linear_trend(vals: list[float]) -> tuple[float, float]:
    """Calculate slope b and intercept a for least squares regression: y = a + b * x."""
    n = len(vals)
    if n <= 1:
        return (vals[0] if vals else 0.0), 1.0

    sx = sum(range(n))
    sy = sum(vals)
    sxx = sum(x * x for x in range(n))
    sxy = sum(x * y for x, y in enumerate(vals))

    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return vals[0], 0.0

    b = (n * sxy - sx * sy) / denom
    a = (sy - b * sx) / n
    return a, b


def _round15(v: float) -> int | float:
    """Round to 15 significant digits or integer to prevent float drift."""
    r = round(v, 10)
    if r.is_integer():
        return int(r)
    return r


class SourceItem:
    """Source cell wrapper holding position and clone."""

    def __init__(self, r: int, c: int, cell: CellData | None) -> None:
        self.r = r
        self.c = c
        self.cell = cell


class AutoFillEngine:
    """High-performance multi-mode series extrapolation engine for ATBOffice Ledger."""

    @staticmethod
    def determine_destination(
        src: SelectionRange, hover_r: int, hover_c: int
    ) -> tuple[SelectionRange, bool]:
        """Compute the extended (or shrunk) destination range based on mouse position.

        Returns (dest_range, is_shrink).
        """
        dr = (
            hover_r - src.max_r
            if hover_r > src.max_r
            else (hover_r - src.min_r if hover_r < src.min_r else 0)
        )
        dc = (
            hover_c - src.max_c
            if hover_c > src.max_c
            else (hover_c - src.min_c if hover_c < src.min_c else 0)
        )

        # Dominant axis extension
        if abs(dr) >= abs(dc) and dr != 0:
            if dr > 0:
                return (
                    SelectionRange(src.min_r, src.min_c, hover_r, src.max_c),
                    False,
                )
            else:
                return (
                    SelectionRange(hover_r, src.min_c, src.max_r, src.max_c),
                    False,
                )
        elif dc != 0:
            if dc > 0:
                return (
                    SelectionRange(src.min_r, src.min_c, src.max_r, hover_c),
                    False,
                )
            else:
                return (
                    SelectionRange(src.min_r, hover_c, src.max_r, src.max_c),
                    False,
                )

        # Shrink checks
        if hover_r < src.max_r and hover_r >= src.min_r and src.max_r > src.min_r:
            return (
                SelectionRange(src.min_r, src.min_c, hover_r, src.max_c),
                True,
            )
        if hover_c < src.max_c and hover_c >= src.min_c and src.max_c > src.min_c:
            return (
                SelectionRange(src.min_r, src.min_c, src.max_r, hover_c),
                True,
            )

        return src, False

    @classmethod
    def series_generator(
        cls,
        src_items: list[SourceItem],
        mode: str = "auto",
        ctrl_pressed: bool = False,
    ) -> Callable[[int, int, int], CellData | None]:
        """Create a generator function k -> CellData for target offsets.

        k: offset index (0 .. n-1 are source cells, >= n are forward fills, < 0 are reverse fills).
        target_r, target_c: destination cell coordinates (for formula reference translation).
        """
        n = len(src_items)
        if n == 0:
            return lambda k, tr, tc: None

        # 1. Strict Copy or Formats-Only
        if mode == "copy":
            return lambda k, tr, tc: cls._clone_and_translate(
                src_items[((k % n) + n) % n], tr, tc
            )

        # Inspect values and formulas
        vals = [
            (item.cell.value if item.cell is not None else None)
            for item in src_items
        ]
        has_formula = any(
            item.cell is not None and item.cell.formula is not None
            for item in src_items
        )

        # 2. Formulas without numbers: repeat and translate references
        if has_formula:
            return lambda k, tr, tc: cls._clone_and_translate(
                src_items[((k % n) + n) % n], tr, tc
            )

        # 3. Numeric Sequences & Date Serials
        all_numeric = all(
            isinstance(v, (int, float)) and not isinstance(v, bool)
            for v in vals
            if v is not None
        ) and all(v is not None for v in vals)

        if all_numeric and n >= 1:
            # Check if all cells have date formatting
            is_date_cells = all(
                item.cell is not None
                and _is_date_format(item.cell.format_code)
                for item in src_items
            )

            if is_date_cells and mode in (
                "auto",
                "days",
                "weekdays",
                "months",
                "years",
            ):
                return cls._create_date_generator(src_items, vals, mode)

            # Single numeric cell:
            # If Ctrl pressed or mode is linear -> increment (+1 per cell)
            # If Ctrl NOT pressed -> copy value
            if n == 1:
                if ctrl_pressed or mode == "linear":
                    base_val = vals[0]
                    base_item = src_items[0]
                    return lambda k, tr, tc: cls._create_numeric_cell(
                        base_item, _round15(base_val + k)
                    )
                else:
                    return lambda k, tr, tc: cls._clone_and_translate(
                        src_items[0], tr, tc
                    )

            # Two or more numbers: linear trend
            float_vals = [float(v) for v in vals]
            a, b = _linear_trend(float_vals)
            return lambda k, tr, tc: cls._create_numeric_cell(
                src_items[((k % n) + n) % n], _round15(a + b * k)
            )

        # 4. Text with Built-in Lists (Mon..Sun, Jan..Dec, 周一..周日, etc.)
        str_vals = [
            str(v) if v is not None and not isinstance(v, bool) else ""
            for v in vals
        ]
        matched_lists = [_match_list(s) for s in str_vals]

        if all(m is not None for m in matched_lists) and n >= 1:
            first_list = matched_lists[0][0]  # type: ignore[index]
            if all(m[0] == first_list for m in matched_lists):  # type: ignore[index]
                indices = [m[1] for m in matched_lists]  # type: ignore[index]
                list_len = len(first_list)
                step = (indices[1] - indices[0]) if n > 1 else 1

                def _list_gen(k: int, tr: int, tc: int) -> CellData | None:
                    j = k - (n - 1)
                    idx = (((indices[-1] + step * j) % list_len) + list_len) % list_len
                    new_text = _case_like(str_vals[-1], first_list[idx])
                    base_item = src_items[((k % n) + n) % n]
                    cell = (
                        copy.copy(base_item.cell)
                        if base_item.cell
                        else CellData()
                    )
                    cell.value = new_text
                    return cell

                return _list_gen

        # 5. Text with ISO Date format ("2026-10-25" or "2026/10/25")
        iso_dates: list[datetime.date | None] = []
        for s in str_vals:
            m = ISO_DATE_RE.match(s.strip())
            if m:
                try:
                    iso_dates.append(
                        datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    )
                except ValueError:
                    iso_dates.append(None)
            else:
                iso_dates.append(None)

        if all(d is not None for d in iso_dates) and n >= 1:
            step_days = (
                (iso_dates[1] - iso_dates[0]).days if n > 1 else 1  # type: ignore[operator]
            )

            def _iso_date_gen(k: int, tr: int, tc: int) -> CellData | None:
                j = k - (n - 1)
                new_date = iso_dates[-1] + datetime.timedelta(days=step_days * j)  # type: ignore[operator]
                sep = "-" if "-" in str_vals[0] else "/"
                val_str = f"{new_date.year:04d}{sep}{new_date.month:02d}{sep}{new_date.day:02d}"
                base_item = src_items[((k % n) + n) % n]
                cell = (
                    copy.copy(base_item.cell)
                    if base_item.cell
                    else CellData()
                )
                cell.value = val_str
                return cell

            return _iso_date_gen

        # 6. Text with Numbers ("Item 1", "Week 01", "Q1", "第1节")
        parsed_numbered: list[tuple[str, int, str, int] | None] = []
        for s in str_vals:
            m = NUMBERED_TEXT_RE.match(s)
            if m and not s.isdigit():
                pre, num_str, post = m.group(1), m.group(2), m.group(3)
                parsed_numbered.append((pre, int(num_str), post, len(num_str)))
            else:
                parsed_numbered.append(None)

        if all(p is not None for p in parsed_numbered) and n >= 1:
            p0 = parsed_numbered[0]
            same_affix = all(
                p[0] == p0[0] and p[2] == p0[2]  # type: ignore[index]
                for p in parsed_numbered
            )
            if same_affix:
                step_num = (
                    (parsed_numbered[1][1] - parsed_numbered[0][1])  # type: ignore[index]
                    if n > 1
                    else 1
                )

                def _numbered_gen(k: int, tr: int, tc: int) -> CellData | None:
                    j = k - (n - 1)
                    last_p = parsed_numbered[-1]
                    next_val = last_p[1] + step_num * j  # type: ignore[index]
                    width = last_p[3]  # type: ignore[index]
                    num_formatted = (
                        f"{next_val:0{width}d}" if width > 1 else str(next_val)
                    )
                    text = f"{last_p[0]}{num_formatted}{last_p[2]}"  # type: ignore[index]
                    base_item = src_items[((k % n) + n) % n]
                    cell = (
                        copy.copy(base_item.cell)
                        if base_item.cell
                        else CellData()
                    )
                    cell.value = text
                    return cell

                return _numbered_gen

        # 7. Default: Cyclical repetition
        return lambda k, tr, tc: cls._clone_and_translate(
            src_items[((k % n) + n) % n], tr, tc
        )

    @classmethod
    def _create_date_generator(
        cls,
        src_items: list[SourceItem],
        vals: list[Any],
        mode: str,
    ) -> Callable[[int, int, int], CellData | None]:
        """Construct date increment generator for Excel date serial numbers."""
        n = len(src_items)
        date_parts = [serial_to_parts(float(v)) for v in vals]

        unit = "d"
        if mode in ("days", "weekdays", "months", "years"):
            unit = mode[0]
        elif n > 1:
            # Detect step unit
            d_days = vals[1] - vals[0]
            if abs(d_days - round(d_days)) < 1e-6:
                d_int = int(round(d_days))
                if d_int % 365 == 0:
                    unit = "y"
                elif 28 <= d_int <= 31:
                    unit = "m"

        step = (vals[1] - vals[0]) if n > 1 else 1.0

        def _date_gen(k: int, tr: int, tc: int) -> CellData | None:
            j = k - (n - 1)
            last_parts = date_parts[-1]
            last_v = float(vals[-1])
            new_v: float

            if unit == "m":
                t = (
                    last_parts.year * 12
                    + (last_parts.month - 1)
                    + int(j * step)
                )
                y = t // 12
                m = t % 12 + 1
                # clamp day
                max_d = 31
                if m in (4, 6, 9, 11):
                    max_d = 30
                elif m == 2:
                    max_d = 29 if (y % 4 == 0 and y % 100 != 0 or y % 400 == 0) else 28
                d = min(last_parts.day, max_d)
                new_v = float(date_to_serial(y, m, d))
            elif unit == "y":
                y = last_parts.year + int(j * step)
                m = last_parts.month
                d = last_parts.day
                if m == 2 and d == 29 and not (y % 4 == 0 and y % 100 != 0 or y % 400 == 0):
                    d = 28
                new_v = float(date_to_serial(y, m, d))
            elif unit == "w":  # Weekdays: skip Sat (6) and Sun (0)
                cur = last_v
                left = abs(int(j * step))
                direction = 1 if j * step >= 0 else -1
                while left > 0:
                    cur += direction
                    wd = serial_to_parts(cur).weekday
                    if wd not in (0, 6):
                        left -= 1
                new_v = cur
            else:
                new_v = last_v + step * j

            base_item = src_items[((k % n) + n) % n]
            return cls._create_numeric_cell(base_item, _round15(new_v))

        return _date_gen

    @classmethod
    def _create_numeric_cell(
        cls, base_item: SourceItem, val: int | float
    ) -> CellData:
        cell = copy.copy(base_item.cell) if base_item.cell else CellData()
        cell.value = val
        cell.formula = None
        return cell

    @classmethod
    def _clone_and_translate(
        cls, source_item: SourceItem, target_r: int, target_c: int
    ) -> CellData | None:
        """Clone source cell, translating formula relative references."""
        if source_item.cell is None:
            return None
        cell = copy.copy(source_item.cell)
        if cell.formula:
            dr = target_r - source_item.r
            dc = target_c - source_item.c
            cell.formula = translate(cell.formula, dr, dc)
        return cell

    @classmethod
    def auto_fill(
        cls,
        model: SheetDataModel,
        src: SelectionRange,
        dest: SelectionRange,
        mode: str = "auto",
        ctrl_pressed: bool = False,
    ) -> None:
        """Execute autofill from source range into destination range on SheetDataModel."""
        # 1. Check if shrinking / contracting
        if (
            dest.min_r == src.min_r
            and dest.min_c == src.min_c
            and (dest.max_r < src.max_r or dest.max_c < src.max_c)
        ):
            # Clear cells that are inside src but outside dest
            for r in range(src.min_r, src.max_r + 1):
                for c in range(src.min_c, src.max_c + 1):
                    if r > dest.max_r or c > dest.max_c:
                        model.cells.pop((r, c), None)
            return

        down = dest.max_r > src.max_r
        up = dest.min_r < src.min_r
        right = dest.max_c > src.max_c
        left = dest.min_c < src.min_c

        vertical = down or up

        if vertical:
            lines = src.max_c - src.min_c + 1
            for li in range(lines):
                c = src.min_c + li
                src_items = [
                    SourceItem(r, c, model.get_cell(r, c))
                    for r in range(src.min_r, src.max_r + 1)
                ]
                gen = cls.series_generator(src_items, mode, ctrl_pressed)

                # Fill Down
                if down:
                    for r in range(src.max_r + 1, dest.max_r + 1):
                        k = r - src.min_r
                        new_cell = gen(k, r, c)
                        cls._apply_filled_cell(model, r, c, new_cell, mode)

                # Fill Up
                if up:
                    for r in range(src.min_r - 1, dest.min_r - 1, -1):
                        k = r - src.min_r
                        new_cell = gen(k, r, c)
                        cls._apply_filled_cell(model, r, c, new_cell, mode)

        else:
            # Horizontal (right or left)
            lines = src.max_r - src.min_r + 1
            for li in range(lines):
                r = src.min_r + li
                src_items = [
                    SourceItem(r, c, model.get_cell(r, c))
                    for c in range(src.min_c, src.max_c + 1)
                ]
                gen = cls.series_generator(src_items, mode, ctrl_pressed)

                # Fill Right
                if right:
                    for c in range(src.max_c + 1, dest.max_c + 1):
                        k = c - src.min_c
                        new_cell = gen(k, r, c)
                        cls._apply_filled_cell(model, r, c, new_cell, mode)

                # Fill Left
                if left:
                    for c in range(src.min_c - 1, dest.min_c - 1, -1):
                        k = c - src.min_c
                        new_cell = gen(k, r, c)
                        cls._apply_filled_cell(model, r, c, new_cell, mode)

    @staticmethod
    def _apply_filled_cell(
        model: SheetDataModel,
        r: int,
        c: int,
        new_cell: CellData | None,
        mode: str,
    ) -> None:
        """Apply generated cell to model according to fill mode."""
        if new_cell is None:
            model.cells.pop((r, c), None)
            return

        old_cell = model.get_cell(r, c)
        if mode == "formats":
            if old_cell is not None:
                cell = copy.copy(old_cell)
                # Copy styles only
                cell.format_code = new_cell.format_code
                cell.bold = new_cell.bold
                cell.italic = new_cell.italic
                cell.underline = new_cell.underline
                cell.font_size = new_cell.font_size
                cell.font_family = new_cell.font_family
                cell.fg_color = new_cell.fg_color
                cell.bg_color = new_cell.bg_color
                cell.align_h = new_cell.align_h
                cell.align_v = new_cell.align_v
                model.set_cell(r, c, cell)
            return

        if mode == "values":
            if old_cell is not None:
                cell = copy.copy(old_cell)
                cell.value = new_cell.value
                cell.formula = new_cell.formula
                model.set_cell(r, c, cell)
            else:
                model.set_cell(r, c, new_cell)
            return

        model.set_cell(r, c, new_cell)
