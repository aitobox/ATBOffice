"""Comprehensive unit tests for Ledger core worksheet functions and calculation engine."""

import pytest

from atboffice.modules.spreadsheet.calc.coercion import (
    build_criteria_matcher,
    date_to_serial,
    serial_to_parts,
    to_bool,
    to_num,
    to_str,
    wildcard_to_regex,
)
from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import (
    DIV0,
    NA,
    NUM,
    REF,
    VALUE,
    ExcelError,
    is_error,
)
from atboffice.modules.spreadsheet.calc.evaluator import evaluate
from atboffice.modules.spreadsheet.calc.functions import (
    call_function,
    fn_abs,
    fn_and,
    fn_average,
    fn_averageif,
    fn_averageifs,
    fn_choose,
    fn_concat,
    fn_concatenate,
    fn_count,
    fn_counta,
    fn_countblank,
    fn_countif,
    fn_countifs,
    fn_date,
    fn_datedif,
    fn_day,
    fn_hlookup,
    fn_if,
    fn_iferror,
    fn_ifna,
    fn_ifs,
    fn_index,
    fn_int,
    fn_left,
    fn_len,
    fn_lookup,
    fn_lower,
    fn_match,
    fn_max,
    fn_mid,
    fn_min,
    fn_mod,
    fn_month,
    fn_not,
    fn_now,
    fn_or,
    fn_power,
    fn_product,
    fn_right,
    fn_round,
    fn_rounddown,
    fn_roundup,
    fn_sqrt,
    fn_substitute,
    fn_subtotal,
    fn_sum,
    fn_sumif,
    fn_sumifs,
    fn_switch,
    fn_today,
    fn_trim,
    fn_upper,
    fn_vlookup,
    fn_weekday,
    fn_year,
)


@pytest.fixture
def sample_context() -> EvalContext:
    """Fixture providing populated sample workbook data."""
    ctx = EvalContext()
    # Sheet1: A1:A10 = 1..10
    sheet1_data = {
        (0, 0): 1,
        (1, 0): 2,
        (2, 0): 3,
        (3, 0): 4,
        (4, 0): 5,
        (5, 0): 6,
        (6, 0): 7,
        (7, 0): 8,
        (8, 0): 9,
        (9, 0): 10,
        # B1:B5 = apple, banana, cherry, date, elder
        (0, 1): "apple",
        (1, 1): "banana",
        (2, 1): "cherry",
        (3, 1): "date",
        (4, 1): "elder",
        (5, 1): "",
    }
    # Data sheet:
    # Row 0: Name, Dept, Sales, Date
    # Row 1: Ann, East, 100, 45292
    # Row 2: Bob, West, 250, 45300
    # Row 3: Cy, East, 175, 45310
    # Row 4: Di, North, 50, 45320
    # Row 5: Ed, West, 300, 45330
    data_sheet = {
        (0, 0): "Name",
        (0, 1): "Dept",
        (0, 2): "Sales",
        (0, 3): "Date",
        (1, 0): "Ann",
        (1, 1): "East",
        (1, 2): 100,
        (1, 3): 45292,
        (2, 0): "Bob",
        (2, 1): "West",
        (2, 2): 250,
        (2, 3): 45300,
        (3, 0): "Cy",
        (3, 1): "East",
        (3, 2): 175,
        (3, 3): 45310,
        (4, 0): "Di",
        (4, 1): "North",
        (4, 2): 50,
        (4, 3): 45320,
        (5, 0): "Ed",
        (5, 1): "West",
        (5, 2): 300,
        (5, 3): 45330,
    }
    ctx.workbook_data["Sheet1"] = sheet1_data
    ctx.workbook_data["Data"] = data_sheet
    return ctx


# ==============================================================================
# 1. Coercion, Criteria, Wildcards & Date Conversion Tests
# ==============================================================================

def test_coercion_primitives():
    assert to_num(42) == 42
    assert to_num(" 1,234.5 ") == 1234.5
    assert to_num("12%") == 0.12
    assert to_num(True) == 1
    assert to_num(False) == 0
    assert to_num(None) == 0
    assert to_num("abc") == VALUE

    assert to_bool(True) is True
    assert to_bool(1) is True
    assert to_bool(0) is False
    assert to_bool("TRUE") is True
    assert to_bool("false") is False
    assert to_bool("not a bool") == VALUE

    assert to_str(42) == "42"
    assert to_str(True) == "TRUE"
    assert to_str(False) == "FALSE"
    assert to_str(DIV0) == "#DIV/0!"


def test_criteria_and_wildcard_matching():
    matcher_num = build_criteria_matcher(">5")
    assert matcher_num(10) is True
    assert matcher_num(5) is False
    assert matcher_num(2) is False

    matcher_neq = build_criteria_matcher("<>apple")
    assert matcher_neq("banana") is True
    assert matcher_neq("apple") is False
    assert matcher_neq("APPLE") is False

    matcher_wild = build_criteria_matcher("*e*")
    assert matcher_wild("apple") is True
    assert matcher_wild("banana") is False
    assert matcher_wild("elder") is True

    # Escaped tilde wildcard
    matcher_tilde = build_criteria_matcher("apple~*")
    assert matcher_tilde("apple*") is True
    assert matcher_tilde("applePie") is False


def test_date_serial_conversions():
    # Excel 1900 dates
    assert date_to_serial(2024, 2, 29) == 45351
    assert date_to_serial(1900, 1, 1) == 1
    assert date_to_serial(1900, 2, 28) == 59
    assert date_to_serial(1900, 2, 29) == 60
    assert date_to_serial(1900, 3, 1) == 61

    parts = serial_to_parts(45351)
    assert parts["y"] == 2024
    assert parts["m"] == 2
    assert parts["d"] == 29
    assert parts["wd"] == 4  # Thursday


# ==============================================================================
# 2. Math & Trigonometry Function Tests
# ==============================================================================

def test_math_sum_and_subtotal(sample_context):
    assert fn_sum(1, 2, 3) == 6
    assert fn_sum("10", 5) == 15
    assert fn_sum("abc", 5) == VALUE

    ref_a = sample_context.create_ref("Sheet1", 0, 0, 9, 0)
    assert fn_sum(ref_a, ctx=sample_context) == 55

    assert fn_subtotal(9, ref_a, ctx=sample_context) == 55
    assert fn_subtotal(1, ref_a, ctx=sample_context) == 5.5
    assert fn_subtotal(999, ref_a, ctx=sample_context) == VALUE


def test_math_sumif_and_sumifs(sample_context):
    ref_a = sample_context.create_ref("Sheet1", 0, 0, 9, 0)
    assert fn_sumif(ref_a, ">5", ctx=sample_context) == 40  # 6+7+8+9+10

    ref_b = sample_context.create_ref("Sheet1", 0, 1, 4, 1)
    ref_a_5 = sample_context.create_ref("Sheet1", 0, 0, 4, 0)
    # SUMIF(B1:B5, "*e*", A1:A5) -> apple(1), cherry(3), date(4), elder(5) -> 13
    assert fn_sumif(ref_b, "*e*", ref_a_5, ctx=sample_context) == 13

    # SUMIFS(Data!C2:C6, Data!B2:B6, "East", Data!C2:C6, ">100") -> Cy(175)
    sales = sample_context.create_ref("Data", 1, 2, 5, 2)
    dept = sample_context.create_ref("Data", 1, 1, 5, 1)
    assert fn_sumifs(sales, dept, "East", sales, ">100", ctx=sample_context) == 175


def test_math_rounding_and_arithmetic():
    assert fn_round(2.345, 2) == 2.35
    assert fn_round(-2.5, 0) == -3
    assert fn_roundup(2.341, 2) == 2.35
    assert fn_rounddown(-2.349, 2) == -2.34

    assert fn_abs(-3) == 3
    assert fn_abs(5) == 5
    assert fn_int(-1.5) == -2
    assert fn_int(1.9) == 1

    assert fn_mod(-3, 2) == 1
    assert fn_mod(3, -2) == -1
    assert fn_mod(4, 0) == DIV0

    assert fn_product(1, 2, 3, 4) == 24
    assert fn_power(2, 10) == 1024
    assert fn_power(-2, 0.5) == NUM
    assert fn_sqrt(16) == 4
    assert fn_sqrt(-4) == NUM


# ==============================================================================
# 3. Statistical Function Tests
# ==============================================================================

def test_statistical_aggregations(sample_context):
    ref_a = sample_context.create_ref("Sheet1", 0, 0, 9, 0)
    assert fn_average(ref_a, ctx=sample_context) == 5.5
    assert fn_average(10, 20, 30) == 20
    assert fn_average() == DIV0

    assert fn_count(ref_a, ctx=sample_context) == 10
    ref_b = sample_context.create_ref("Sheet1", 0, 1, 5, 1)  # 5 text, 1 blank
    assert fn_count(ref_b, ctx=sample_context) == 0
    assert fn_counta(ref_b, ctx=sample_context) == 5
    assert fn_countblank(ref_b, ctx=sample_context) == 1

    assert fn_max(ref_a, ctx=sample_context) == 10
    assert fn_min(ref_a, ctx=sample_context) == 1
    assert fn_max(-5, -2, -10) == -2


def test_statistical_conditional(sample_context):
    ref_a = sample_context.create_ref("Sheet1", 0, 0, 9, 0)
    ref_b = sample_context.create_ref("Sheet1", 0, 1, 4, 1)

    assert fn_countif(ref_b, "*e*", ctx=sample_context) == 4
    assert fn_countifs(ref_a, ">2", ref_a, "<8", ctx=sample_context) == 5

    sales = sample_context.create_ref("Data", 1, 2, 5, 2)
    dept = sample_context.create_ref("Data", 1, 1, 5, 1)
    # AVERAGEIFS(Data!C2:C6, Data!B2:B6, "West") -> (250 + 300) / 2 = 275
    assert fn_averageifs(sales, dept, "West", ctx=sample_context) == 275
    assert fn_averageif(ref_a, ">5", ctx=sample_context) == 8


# ==============================================================================
# 4. Lookup & Reference Function Tests
# ==============================================================================

def test_lookup_functions(sample_context):
    table = sample_context.create_ref("Data", 0, 0, 5, 3)
    # VLOOKUP("Cy", Data!A1:D6, 3, FALSE) -> 175
    assert fn_vlookup("Cy", table, 3, False, ctx=sample_context) == 175
    assert fn_vlookup("Zed", table, 3, False, ctx=sample_context) == NA
    assert fn_vlookup("Ann", table, 0, False, ctx=sample_context) == VALUE
    assert fn_vlookup("Ann", table, 10, False, ctx=sample_context) == REF

    # HLOOKUP("Sales", Data!A1:D6, 3, FALSE) -> Row 2 (Bob's sales) = 250
    assert fn_hlookup("Sales", table, 3, False, ctx=sample_context) == 250

    # MATCH & INDEX
    names = sample_context.create_ref("Data", 0, 0, 5, 0)
    idx_di = fn_match("Di", names, 0, ctx=sample_context)
    assert idx_di == 5  # Row 5 (1-based index)
    assert fn_index(table, idx_di, 2, ctx=sample_context) == "North"

    ref_a = sample_context.create_ref("Sheet1", 0, 0, 9, 0)
    assert fn_match(7, ref_a, 1, ctx=sample_context) == 7
    assert fn_match(7.5, ref_a, 1, ctx=sample_context) == 7

    assert fn_lookup(6.5, ref_a, ref_a, ctx=sample_context) == 6
    assert fn_choose(2, "a", "b", "c") == "b"
    assert fn_choose(5, "a", "b") == VALUE


# ==============================================================================
# 5. Logical & Error Handling Function Tests
# ==============================================================================

def test_logical_and_error_functions():
    assert fn_if(True, "yes", "no") == "yes"
    assert fn_if(False, "yes", "no") == "no"
    assert fn_if("not a bool", "yes", "no") == VALUE

    assert fn_ifs(1 == 2, "a", 3 == 3, "c") == "c"
    assert fn_ifs(1 == 2, "a", 2 == 3, "b") == NA

    assert fn_and(True, True, 1) is True
    assert fn_and(True, False) is False
    assert fn_or(False, False, True) is True
    assert fn_or(False, 0) is False
    assert fn_not(True) is False
    assert fn_not(0) is True

    assert fn_switch(2, 1, "one", 2, "two", "other") == "two"
    assert fn_switch(5, 1, "one", 2, "two", "other") == "other"
    assert fn_switch(5, 1, "one", 2, "two") == NA

    assert fn_iferror(DIV0, "repaired") == "repaired"
    assert fn_iferror(42, "repaired") == 42
    assert fn_ifna(NA, "na_repaired") == "na_repaired"
    assert fn_ifna(DIV0, "na_repaired") == DIV0


# ==============================================================================
# 6. Text Function Tests
# ==============================================================================

def test_text_functions():
    assert fn_concat("a", "b", "c") == "abc"
    assert fn_concatenate("a", 1, True) == "a1TRUE"
    assert fn_left("hello", 2) == "he"
    assert fn_right("hello", 3) == "llo"
    assert fn_mid("hello", 2, 3) == "ell"
    assert fn_len("hello") == 5
    assert fn_trim("  a   b  ") == "a b"
    assert fn_upper("abc") == "ABC"
    assert fn_lower("ABC") == "abc"
    assert fn_substitute("aaa", "a", "b", 2) == "aba"
    assert fn_substitute("aaa", "a", "b") == "bbb"


# ==============================================================================
# 7. Date & Time Function Tests
# ==============================================================================

def test_date_and_time_functions():
    assert fn_date(2024, 2, 29) == 45351
    assert fn_date(2023, 14, 1) == 45323
    assert fn_year(45351) == 2024
    assert fn_month(45351) == 2
    assert fn_day(45351) == 29
    assert fn_weekday(45351) == 5
    assert fn_weekday(45351, 2) == 4

    # DATEDIF
    d_start = fn_date(2020, 1, 15)
    d_end = fn_date(2024, 3, 10)
    assert fn_datedif(d_start, d_end, "y") == 4
    assert fn_datedif(d_start, d_end, "md") == 24

    assert isinstance(fn_today(), int)
    assert isinstance(fn_now(), float)


# ==============================================================================
# 8. End-to-End Expression Evaluator Tests
# ==============================================================================

def test_evaluator_expressions(sample_context):
    assert evaluate("=1 + 2 * 3") == 7
    assert evaluate("=SUM(1, 2, 3) * 2") == 12
    assert evaluate("=IF(1 > 0, 10, 1/0)") == 10  # Lazy evaluation protection
    assert evaluate("=IFERROR(1/0, 999)") == 999
    assert evaluate('="Hello " & "World"') == "Hello World"
    assert evaluate("=SUM(Sheet1!A1:A10)", ctx=sample_context) == 55
    assert evaluate('="3" + 4') == 7
    assert evaluate('=VLOOKUP("Cy", Data!A1:D6, 3, FALSE)', ctx=sample_context) == 175
