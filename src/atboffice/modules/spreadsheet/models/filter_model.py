"""Data models, comparators, and algorithms for AutoFilter and multi-column Sort."""

from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import math
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def is_blank(val: Any) -> bool:
    """Check if value is considered empty/blank in Excel."""
    return val is None or val == ""


def is_error(val: Any) -> bool:
    """Check if value is an Excel formula error."""
    if isinstance(val, str) and val.startswith("#") and val.endswith("!"):
        return True
    return False


def type_rank(val: Any) -> int:
    """Return Excel data type sort priority:
    0: Number
    1: String
    2: Boolean
    3: Error
    4: Blank (always last)
    """
    if is_blank(val):
        return 4
    if is_error(val):
        return 3
    if isinstance(val, bool):
        return 2
    if isinstance(val, (int, float)):
        return 0
    return 1


def excel_sort_cmp(
    a: Any, b: Any, desc: bool = False, case_sensitive: bool = False
) -> int:
    """Three-way comparator for Excel cell values.
    Returns:
      < 0 if a < b
      0   if a == b
      > 0 if a > b
    Blanks are ALWAYS sorted to the bottom in both ascending and descending.
    """
    ta, tb = type_rank(a), type_rank(b)

    # Blanks are always placed at the bottom regardless of sort order
    if ta == 4 and tb == 4:
        return 0
    if ta == 4:
        return 1
    if tb == 4:
        return -1

    if ta != tb:
        return (tb - ta) if desc else (ta - tb)

    diff = 0
    if ta == 0:
        # Numbers
        fa, fb = float(a), float(b)
        if math.isclose(fa, fb, abs_tol=1e-12):
            diff = 0
        else:
            diff = -1 if fa < fb else 1
    elif ta == 1:
        # Strings
        sa, sb = str(a), str(b)
        if not case_sensitive:
            sa, sb = sa.lower(), sb.lower()
        if sa < sb:
            diff = -1
        elif sa > sb:
            diff = 1
        else:
            diff = 0
    elif ta == 2:
        # Booleans (False < True)
        ba, bb = int(bool(a)), int(bool(b))
        diff = -1 if ba < bb else (1 if ba > bb else 0)
    elif ta == 3:
        # Errors
        sa, sb = str(a), str(b)
        diff = -1 if sa < sb else (1 if sa > sb else 0)

    return -diff if desc else diff


@dataclass
class ExcelSortItem:
    """Comparable wrapper object for Excel values in multi-key tuples."""

    val: Any
    desc: bool = False
    case_sensitive: bool = False

    def __lt__(self, other: ExcelSortItem) -> bool:
        return (
            excel_sort_cmp(
                self.val, other.val, self.desc, self.case_sensitive
            )
            < 0
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExcelSortItem):
            return False
        return (
            excel_sort_cmp(
                self.val, other.val, self.desc, self.case_sensitive
            )
            == 0
        )

    def __gt__(self, other: ExcelSortItem) -> bool:
        return (
            excel_sort_cmp(
                self.val, other.val, self.desc, self.case_sensitive
            )
            > 0
        )

    def __le__(self, other: ExcelSortItem) -> bool:
        return not (self > other)

    def __ge__(self, other: ExcelSortItem) -> bool:
        return not (self < other)


def excel_sort_key(
    val: Any, desc: bool = False, case_sensitive: bool = False
) -> ExcelSortItem:
    """Generate a comparable key wrapper for sorting Excel cells."""
    return ExcelSortItem(val, desc=desc, case_sensitive=case_sensitive)


def sort_sheet_range(
    model: SheetDataModel,
    r1: int,
    c1: int,
    r2: int,
    c2: int,
    keys: list[tuple[int, bool]],  # list of (col_index, desc_bool)
    has_header: bool = True,
    case_sensitive: bool = False,
) -> None:
    """Sort rows within the range (r1, c1, r2, c2) by up to 3 keys.
    Preserves all cell properties, formulas, formats, and custom row heights.
    """
    start_r = r1 + 1 if has_header else r1
    if start_r >= r2:
        return

    num_rows = r2 - start_r + 1
    row_records: list[dict[str, Any]] = []

    for idx in range(num_rows):
        orig_r = start_r + idx
        # Extract row cells
        cells = {
            c: model.get_cell(orig_r, c)
            for c in range(c1, c2 + 1)
            if model.get_cell(orig_r, c) is not None
        }
        # Extract sort key values
        key_items = tuple(
            excel_sort_key(
                model.get_cell_value(orig_r, col),
                desc=desc,
                case_sensitive=case_sensitive,
            )
            for col, desc in keys
        )
        row_records.append(
            {
                "orig_r": orig_r,
                "cells": cells,
                "height": model.geometry.custom_row_heights.get(orig_r),
                "sort_key": key_items,
            }
        )

    # Stable sort
    row_records.sort(key=lambda item: item["sort_key"])

    # Clear old cell positions in range
    for r in range(start_r, r2 + 1):
        for c in range(c1, c2 + 1):
            if (r, c) in model.cells:
                del model.cells[(r, c)]

    # Write sorted rows back
    for idx, rec in enumerate(row_records):
        dest_r = start_r + idx
        for c, cell_data in rec["cells"].items():
            model.set_cell(dest_r, c, cell_data)

        if rec["height"] is not None:
            model.geometry.set_row_height(dest_r, rec["height"])
        elif dest_r in model.geometry.custom_row_heights:
            del model.geometry.custom_row_heights[dest_r]


# -----------------------------------------------------------------------------
# AutoFilter Data Structures & Filtering Algorithm
# -----------------------------------------------------------------------------


@dataclass
class ColumnFilter:
    """Filter criteria applied to a single column."""

    values: set[str] | None = None
    blank: bool = False
    custom_list: list[tuple[str, str]] | None = None  # [(op, val), ...]
    custom_and: bool = True
    top10_top: bool | None = None  # True = Top, False = Bottom
    top10_percent: bool = False
    top10_val: int = 10

    def has_criteria(self) -> bool:
        return bool(
            self.values is not None
            or self.blank
            or self.custom_list
            or self.top10_top is not None
        )


@dataclass
class AutoFilter:
    """Worksheet AutoFilter range and active column criteria."""

    r1: int
    c1: int
    r2: int
    c2: int
    cols: dict[int, ColumnFilter] = field(default_factory=dict)
    filtered_rows: set[int] = field(default_factory=set)


def test_custom_condition(op: str, val_pattern: str, cell_val: Any, cell_text: str) -> bool:
    """Evaluate an Excel custom condition against cell value and formatted text."""
    pattern = str(val_pattern)
    num_pattern: float | None = None
    try:
        if pattern.strip() != "":
            num_pattern = float(pattern)
    except ValueError:
        num_pattern = None

    if op in ("equal", "notEqual"):
        matched = False
        if pattern == "" or pattern == " ":
            matched = is_blank(cell_val)
        elif "*" in pattern or "?" in pattern:
            matched = fnmatch.fnmatchcase(cell_text.lower(), pattern.lower())
        elif num_pattern is not None and isinstance(cell_val, (int, float)):
            matched = math.isclose(cell_val, num_pattern, abs_tol=1e-9)
        else:
            matched = cell_text.lower() == pattern.lower()

        return matched if op == "equal" else not matched

    if op in ("greaterThan", "greaterThanOrEqual", "lessThan", "lessThanOrEqual"):
        if num_pattern is not None and isinstance(cell_val, (int, float)):
            diff = cell_val - num_pattern
        elif isinstance(cell_val, (int, float)) or num_pattern is not None:
            return False
        else:
            sa = cell_text.lower()
            sb = pattern.lower()
            diff = -1 if sa < sb else (1 if sa > sb else 0)

        if op == "greaterThan":
            return diff > 0
        if op == "greaterThanOrEqual":
            return diff >= 0
        if op == "lessThan":
            return diff < 0
        if op == "lessThanOrEqual":
            return diff <= 0

    if op == "begins":
        return cell_text.lower().startswith(pattern.lower())
    if op == "notBegins":
        return not cell_text.lower().startswith(pattern.lower())
    if op == "ends":
        return cell_text.lower().endswith(pattern.lower())
    if op == "notEnds":
        return not cell_text.lower().endswith(pattern.lower())
    if op == "contains":
        return pattern.lower() in cell_text.lower()
    if op == "notContains":
        return pattern.lower() not in cell_text.lower()

    return True


def make_row_tester(
    model: SheetDataModel,
    af: AutoFilter,
    col_idx: int,
    crit: ColumnFilter,
):
    """Create a predicate function row -> bool testing column criteria."""
    c = af.c1 + col_idx
    data_r1 = af.r1 + 1
    data_r2 = af.r2

    top_cutoff: float | None = None
    if crit.top10_top is not None:
        nums: list[float] = []
        for r in range(data_r1, data_r2 + 1):
            val = model.get_cell_value(r, c)
            if isinstance(val, (int, float)):
                nums.append(float(val))

        if nums:
            nums.sort(reverse=bool(crit.top10_top))
            if crit.top10_percent:
                count = max(1, math.floor(len(nums) * crit.top10_val / 100))
            else:
                count = max(1, crit.top10_val)
            cutoff_idx = min(count, len(nums)) - 1
            top_cutoff = nums[cutoff_idx]

    val_set: set[str] | None = None
    if crit.values is not None:
        val_set = {str(x).lower() for x in crit.values}

    def tester(r: int) -> bool:
        val = model.get_cell_value(r, c)
        text = model.get_formatted_text(r, c)

        if is_blank(val):
            return crit.blank

        # If user explicitly requested only blanks
        if crit.blank and crit.values is None and not crit.custom_list and crit.top10_top is None:
            return False

        if val_set is not None:
            if text.lower() in val_set:
                return True
            if str(val).lower() in val_set:
                return True
            return False

        if crit.custom_list:
            cond_results = [
                test_custom_condition(op, pat, val, text)
                for op, pat in crit.custom_list
            ]
            return (
                all(cond_results)
                if crit.custom_and
                else any(cond_results)
            )

        if crit.top10_top is not None:
            if not isinstance(val, (int, float)) or top_cutoff is None:
                return False
            return (
                val >= top_cutoff
                if crit.top10_top
                else val <= top_cutoff
            )

        return True

    return tester


def apply_auto_filter(model: SheetDataModel, af: AutoFilter) -> None:
    """Apply column filter criteria across rows and update geometry hidden_rows."""
    # Build testers for columns with active criteria
    testers = [
        make_row_tester(model, af, col_idx, crit)
        for col_idx, crit in af.cols.items()
        if crit.has_criteria()
    ]

    # Clear previously filtered rows from this filter
    for r in list(af.filtered_rows):
        model.geometry.hidden_rows.discard(r)
    af.filtered_rows.clear()

    if not testers:
        return

    for r in range(af.r1 + 1, af.r2 + 1):
        if not all(t(r) for t in testers):
            if r not in model.geometry.hidden_rows:
                af.filtered_rows.add(r)
                model.geometry.hidden_rows.add(r)


def clear_auto_filter(
    model: SheetDataModel, af: AutoFilter, col_idx: int | None = None
) -> None:
    """Clear filter criteria for a column or the entire AutoFilter."""
    if col_idx is not None:
        if col_idx in af.cols:
            del af.cols[col_idx]
        apply_auto_filter(model, af)
    else:
        af.cols.clear()
        for r in af.filtered_rows:
            model.geometry.hidden_rows.discard(r)
        af.filtered_rows.clear()
