"""Conditional formatting data models and evaluation engine for ATBOffice Ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


class CFRuleType(str, Enum):
    """Conditional formatting rule types matching OpenXML / Excel standards."""

    CELL_IS = "cellIs"
    EXPRESSION = "expression"
    COLOR_SCALE = "colorScale"
    DATA_BAR = "dataBar"
    CONTAINS_TEXT = "containsText"
    NOT_CONTAINS_TEXT = "notContainsText"
    BEGINS_WITH = "beginsWith"
    ENDS_WITH = "endsWith"
    DUPLICATE_VALUES = "duplicateValues"
    UNIQUE_VALUES = "uniqueValues"
    TOP10 = "top10"
    ABOVE_AVERAGE = "aboveAverage"


class CFOp(str, Enum):
    """Comparison operators for cellIs conditional formatting rules."""

    BETWEEN = "between"
    NOT_BETWEEN = "notBetween"
    EQUAL = "equal"
    NOT_EQUAL = "notEqual"
    GREATER_THAN = "greaterThan"
    LESS_THAN = "lessThan"
    GREATER_THAN_OR_EQUAL = "greaterThanOrEqual"
    LESS_THAN_OR_EQUAL = "lessThanOrEqual"


class CFVOType(str, Enum):
    """Conditional formatting value object (CFVO) types."""

    MIN = "min"
    MAX = "max"
    NUM = "num"
    PERCENT = "percent"
    PERCENTILE = "percentile"
    FORMULA = "formula"


@dataclass
class CFVO:
    """Conditional formatting threshold value specification."""

    type: str = "min"
    val: Any = None
    gte: bool = True


@dataclass
class ColorScaleRule:
    """Color scale rule configuration (2-color or 3-color gradient)."""

    cfvos: list[CFVO] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)


@dataclass
class DataBarRule:
    """In-cell data bar configuration."""

    cfvos: list[CFVO] = field(default_factory=list)
    color: str = "#638EC6"
    neg_color: str = "#FF0000"
    min_len: float = 0.1
    max_len: float = 0.9
    show_value: bool = True


@dataclass
class CFRule:
    """Individual conditional formatting rule."""

    type: str = CFRuleType.CELL_IS.value
    operator: str | None = None
    formula: list[str] = field(default_factory=list)
    text: str | None = None
    priority: int = 1
    stop_if_true: bool = False

    # Formatting payload
    bg_color: str | None = None
    fg_color: str | None = None
    bold: bool | None = None
    italic: bool | None = None

    # Graphical rules
    color_scale: ColorScaleRule | None = None
    data_bar: DataBarRule | None = None


@dataclass
class ConditionalFormat:
    """Container mapping ranges to a collection of rules."""

    sqref: str = ""
    ranges: list[tuple[int, int, int, int]] = field(default_factory=list)
    rules: list[CFRule] = field(default_factory=list)


@dataclass
class CFResult:
    """Evaluation result for a cell."""

    bg_color: str | None = None
    fg_color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    data_bar: dict[str, Any] | None = None


def lerp(a: float, b: float, t: float) -> int:
    """Linearly interpolate between integer color channels a and b."""
    return round(a + (b - a) * t)


def mix_colors(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two hex colors by factor t in [0.0, 1.0]."""
    t = max(0.0, min(1.0, t))
    h1 = c1.lstrip("#")
    h2 = c2.lstrip("#")
    r1, g1, b1 = int(h1[0:2], 16), int(h1[2:4], 16), int(h1[4:6], 16)
    r2, g2, b2 = int(h2[0:2], 16), int(h2[2:4], 16), int(h2[4:6], 16)
    r = lerp(r1, r2, t)
    g = lerp(g1, g2, t)
    b = lerp(b1, b2, t)
    return f"#{r:02X}{g:02X}{b:02X}"


def _in_ranges(ranges: list[tuple[int, int, int, int]], r: int, c: int) -> bool:
    """Check if (r, c) falls inside any bounding range."""
    return any(r1 <= r <= r2 and c1 <= c <= c2 for r1, c1, r2, c2 in ranges)


def _get_range_values(
    sheet: SheetDataModel,
    ranges: list[tuple[int, int, int, int]],
    nums_only: bool = False,
) -> list[Any]:
    """Extract cell values across the specified ranges."""
    out: list[Any] = []
    for r1, c1, r2, c2 in ranges:
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                cell = sheet.get_cell(r, c)
                if cell is not None and cell.value is not None and cell.value != "":
                    if nums_only:
                        try:
                            val = float(cell.value)
                            out.append(val)
                        except (ValueError, TypeError):
                            pass
                    else:
                        out.append(cell.value)
    return out


def _cfvo_value(cfvo: CFVO, nums: list[float]) -> float:
    """Calculate the threshold value for a CFVO given numbers in range."""
    if not nums:
        return 0.0
    sorted_nums = sorted(nums)
    min_v = sorted_nums[0]
    max_v = sorted_nums[-1]

    if cfvo.type == "min":
        return min_v
    elif cfvo.type == "max":
        return max_v
    elif cfvo.type in ("num", "formula"):
        try:
            return float(cfvo.val) if cfvo.val is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    elif cfvo.type == "percent":
        try:
            p = float(cfvo.val) if cfvo.val is not None else 0.0
        except (ValueError, TypeError):
            p = 0.0
        return min_v + (max_v - min_v) * (p / 100.0)
    elif cfvo.type == "percentile":
        try:
            p = (float(cfvo.val) if cfvo.val is not None else 0.0) / 100.0
        except (ValueError, TypeError):
            p = 0.0
        n = len(sorted_nums)
        if n == 1:
            return sorted_nums[0]
        idx = p * (n - 1)
        i = int(math.floor(idx))
        if i + 1 < n:
            return sorted_nums[i] + (idx - i) * (sorted_nums[i + 1] - sorted_nums[i])
        return sorted_nums[-1]
    return 0.0


def _rule_matches(
    rule: CFRule,
    sheet: SheetDataModel,
    ranges: list[tuple[int, int, int, int]],
    r: int,
    c: int,
    val: Any,
) -> bool:
    """Evaluate whether rule applies to cell value."""
    rule_type = rule.type

    if rule_type == CFRuleType.CELL_IS.value:
        if val is None:
            return False
        try:
            num_val = float(val)
            f0 = float(rule.formula[0]) if rule.formula else 0.0
        except (ValueError, TypeError):
            # Fall back to string comparison
            s_val = str(val)
            s_f0 = str(rule.formula[0]) if rule.formula else ""
            if rule.operator == CFOp.EQUAL.value:
                return s_val.lower() == s_f0.lower()
            elif rule.operator == CFOp.NOT_EQUAL.value:
                return s_val.lower() != s_f0.lower()
            return False

        op = rule.operator or CFOp.EQUAL.value
        if op == CFOp.BETWEEN.value or op == CFOp.NOT_BETWEEN.value:
            f1 = float(rule.formula[1]) if len(rule.formula) > 1 else 0.0
            lo, hi = min(f0, f1), max(f0, f1)
            inside = lo <= num_val <= hi
            return inside if op == CFOp.BETWEEN.value else not inside
        elif op == CFOp.EQUAL.value:
            return num_val == f0
        elif op == CFOp.NOT_EQUAL.value:
            return num_val != f0
        elif op == CFOp.GREATER_THAN.value:
            return num_val > f0
        elif op == CFOp.LESS_THAN.value:
            return num_val < f0
        elif op == CFOp.GREATER_THAN_OR_EQUAL.value:
            return num_val >= f0
        elif op == CFOp.LESS_THAN_OR_EQUAL.value:
            return num_val <= f0
        return False

    elif rule_type == CFRuleType.CONTAINS_TEXT.value:
        target = rule.text or (rule.formula[0] if rule.formula else "")
        return target.lower() in str(val).lower() if val is not None else False

    elif rule_type == CFRuleType.NOT_CONTAINS_TEXT.value:
        target = rule.text or (rule.formula[0] if rule.formula else "")
        return target.lower() not in str(val).lower() if val is not None else True

    elif rule_type == CFRuleType.BEGINS_WITH.value:
        target = rule.text or (rule.formula[0] if rule.formula else "")
        return str(val).lower().startswith(target.lower()) if val is not None else False

    elif rule_type == CFRuleType.ENDS_WITH.value:
        target = rule.text or (rule.formula[0] if rule.formula else "")
        return str(val).lower().endswith(target.lower()) if val is not None else False

    elif rule_type in (CFRuleType.DUPLICATE_VALUES.value, CFRuleType.UNIQUE_VALUES.value):
        if val is None or val == "":
            return False
        all_vals = _get_range_values(sheet, ranges, nums_only=False)
        target_s = str(val).strip().lower()
        count = sum(1 for v in all_vals if str(v).strip().lower() == target_s)
        return count > 1 if rule_type == CFRuleType.DUPLICATE_VALUES.value else count == 1

    return False


def evaluate_cf_for_cell(sheet: SheetDataModel, r: int, c: int) -> CFResult | None:
    """Evaluate all conditional formatting rules matching cell (r, c)."""
    cfs: list[ConditionalFormat] = getattr(sheet, "conditional_formats", [])
    if not cfs:
        return None

    cell = sheet.get_cell(r, c)
    val = cell.value if cell is not None else None

    # Collect matching rules sorted by priority
    candidates: list[tuple[ConditionalFormat, CFRule]] = []
    for cf in cfs:
        if _in_ranges(cf.ranges, r, c):
            for rule in cf.rules:
                candidates.append((cf, rule))

    candidates.sort(key=lambda pair: pair[1].priority)

    result = CFResult()
    has_format = False

    for cf, rule in candidates:
        # 1. Color Scale Rule
        if (rule.type == CFRuleType.COLOR_SCALE.value or rule.color_scale is not None) and rule.color_scale:
            if val is not None:
                try:
                    num_val = float(val)
                    nums = _get_range_values(sheet, cf.ranges, nums_only=True)
                    if nums:
                        cs = rule.color_scale
                        th = [_cfvo_value(cfvo, nums) for cfvo in cs.cfvos]
                        cols = cs.colors
                        if len(th) == 2 and len(cols) >= 2:
                            span = th[1] - th[0]
                            t = 0.5 if span == 0 else (num_val - th[0]) / span
                            hex_col = mix_colors(cols[0], cols[1], t)
                            if result.bg_color is None:
                                result.bg_color = hex_col
                                has_format = True
                        elif len(th) >= 3 and len(cols) >= 3:
                            if num_val <= th[1]:
                                span = th[1] - th[0]
                                t = 1.0 if span == 0 else (num_val - th[0]) / span
                                hex_col = mix_colors(cols[0], cols[1], t)
                            else:
                                span = th[2] - th[1]
                                t = 1.0 if span == 0 else (num_val - th[1]) / span
                                hex_col = mix_colors(cols[1], cols[2], t)
                            if result.bg_color is None:
                                result.bg_color = hex_col
                                has_format = True
                except (ValueError, TypeError):
                    pass
            if rule.stop_if_true:
                break
            continue

        # 2. Data Bar Rule
        if (rule.type == CFRuleType.DATA_BAR.value or rule.data_bar is not None) and rule.data_bar:
            if val is not None:
                try:
                    num_val = float(val)
                    nums = _get_range_values(sheet, cf.ranges, nums_only=True)
                    if nums:
                        db = rule.data_bar
                        cfvo_lo = db.cfvos[0] if len(db.cfvos) > 0 else CFVO(type="min")
                        cfvo_hi = db.cfvos[1] if len(db.cfvos) > 1 else CFVO(type="max")
                        lo = _cfvo_value(cfvo_lo, nums)
                        hi = _cfvo_value(cfvo_hi, nums)
                        if lo > hi:
                            lo, hi = hi, lo
                        span = hi - lo
                        t = 1.0 if span == 0 else (num_val - lo) / span
                        frac = db.min_len + (db.max_len - db.min_len) * max(0.0, min(1.0, t))
                        if result.data_bar is None:
                            result.data_bar = {
                                "frac": frac,
                                "color": db.color,
                                "neg_color": db.neg_color,
                                "show_value": db.show_value,
                            }
                            has_format = True
                except (ValueError, TypeError):
                    pass
            if rule.stop_if_true:
                break
            continue

        # 3. Standard CellIs / Text / Duplicate Rules
        if _rule_matches(rule, sheet, cf.ranges, r, c, val):
            if rule.bg_color is not None and result.bg_color is None:
                result.bg_color = rule.bg_color
                has_format = True
            if rule.fg_color is not None and result.fg_color is None:
                result.fg_color = rule.fg_color
                has_format = True
            if rule.bold is not None and result.bold is None:
                result.bold = rule.bold
                has_format = True
            if rule.italic is not None and result.italic is None:
                result.italic = rule.italic
                has_format = True

            if rule.stop_if_true:
                break

    return result if has_format else None
