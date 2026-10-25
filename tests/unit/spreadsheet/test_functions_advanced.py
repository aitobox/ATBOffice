"""Comprehensive unit tests for Issue #11: Advanced Worksheet Functions and Dynamic Arrays (519 Coverage)."""

import math
import pytest

from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import DIV0, NA, NUM, SPILL, VALUE, is_error
from atboffice.modules.spreadsheet.calc.evaluator import evaluate, evaluate_ast
from atboffice.modules.spreadsheet.calc.fn_info import ALL_FUNCTIONS_CATALOG
from atboffice.modules.spreadsheet.calc.functions import FUNCTION_REGISTRY, call_function
from atboffice.modules.spreadsheet.calc.parser import parse
from atboffice.modules.spreadsheet.calc.spill import SpillManager, SpillRange


# --- 1. Full 519 Function Registry Coverage ---


def test_registry_size_519():
    """Verify that FUNCTION_REGISTRY has exactly 519 functions and 100% matches ALL_FUNCTIONS_CATALOG."""
    assert len(ALL_FUNCTIONS_CATALOG) == 519
    assert len(FUNCTION_REGISTRY) == 519
    missing = set(ALL_FUNCTIONS_CATALOG.keys()) - set(FUNCTION_REGISTRY.keys())
    assert not missing, f"Missing functions from catalog: {missing}"


# --- 2. Dynamic Array Functions ---


def test_dynamic_arrays():
    """Verify modern dynamic array operations."""
    ctx = EvalContext()

    # SEQUENCE(rows, [cols], [start], [step])
    seq = call_function("SEQUENCE", [3, 2, 1, 2], ctx)
    assert isinstance(seq, Arr)
    assert seq.rows == 3 and seq.cols == 2
    assert seq.data == [[1, 3], [5, 7], [9, 11]]

    # UNIQUE
    data = Arr([[1], [2], [2], [3], [1]])
    uniq = call_function("UNIQUE", [data], ctx)
    assert isinstance(uniq, Arr)
    assert uniq.data == [[1], [2], [3]]

    # SORT
    unsorted = Arr([[3], [1], [2]])
    sorted_arr = call_function("SORT", [unsorted], ctx)
    assert isinstance(sorted_arr, Arr)
    assert sorted_arr.data == [[1], [2], [3]]

    # FILTER
    vals = Arr([[10], [20], [30], [40]])
    mask = Arr([[True], [False], [True], [False]])
    filtered = call_function("FILTER", [vals, mask], ctx)
    assert isinstance(filtered, Arr)
    assert filtered.data == [[10], [30]]

    # XLOOKUP
    lookup_val = "Beta"
    lookup_arr = Arr([["Alpha"], ["Beta"], ["Gamma"]])
    return_arr = Arr([[100], [200], [300]])
    found = call_function("XLOOKUP", [lookup_val, lookup_arr, return_arr], ctx)
    assert found == 200

    # XMATCH
    pos = call_function("XMATCH", ["Gamma", lookup_arr], ctx)
    assert pos == 3

    # TEXTJOIN
    joined = call_function("TEXTJOIN", [", ", True, "apple", "", "banana", "orange"], ctx)
    assert joined == "apple, banana, orange"

    # TEXTSPLIT
    split = call_function("TEXTSPLIT", ["apple,banana,orange", ","], ctx)
    assert isinstance(split, Arr)
    assert split.data == [["apple", "banana", "orange"]]


# --- 3. Higher Order & Lambdas ---


def test_let_and_lambda():
    """Verify LET and LAMBDA higher order function evaluations."""
    ctx = EvalContext()

    # LET evaluation
    res_let = evaluate("=LET(x, 5, y, 10, x * y)", ctx)
    assert res_let == 50

    # Nested LET
    res_nested = evaluate("=LET(a, 2, b, LET(c, 3, a + c), b * 10)", ctx)
    assert res_nested == 50

    # MAP with LAMBDA
    res_map = evaluate("=MAP(SEQUENCE(3), LAMBDA(x, x * 2))", ctx)
    assert isinstance(res_map, Arr)
    assert res_map.data == [[2], [4], [6]]

    # REDUCE with LAMBDA
    res_reduce = evaluate("=REDUCE(0, SEQUENCE(4), LAMBDA(acc, v, acc + v))", ctx)
    assert res_reduce == 10

    # BYROW with LAMBDA
    matrix = Arr([[1, 2], [3, 4]])
    res_byrow = call_function("BYROW", [matrix, lambda r, ctx=None: sum(r.data[0])], ctx)
    assert isinstance(res_byrow, Arr)
    assert res_byrow.data == [[3], [7]]

    # BYCOL with LAMBDA
    res_bycol = call_function("BYCOL", [matrix, lambda c, ctx=None: sum(row[0] for row in c.data)], ctx)
    assert isinstance(res_bycol, Arr)
    assert res_bycol.data == [[4, 6]]


# --- 4. Dynamic Array Spill & Collision Handling ---


def test_spill_collision():
    """Verify dynamic array spill placement and collision (#SPILL!)."""
    ctx = EvalContext()
    ctx.workbook_data["Sheet1"] = {}
    manager = SpillManager()

    # 1. Clean spill of a 2x2 Arr into empty area
    val = manager.evaluate_and_spill("Sheet1", 0, 0, "=SEQUENCE(2, 2, 1, 1)", ctx)
    assert isinstance(val, Arr)
    assert ("Sheet1", 0, 0) in manager.spills
    spill = manager.spills[("Sheet1", 0, 0)]
    assert spill.r1 == 0 and spill.c1 == 0 and spill.r2 == 1 and spill.c2 == 1
    assert ctx.workbook_data["Sheet1"][(0, 0)] == 1
    assert ctx.workbook_data["Sheet1"][(0, 1)] == 2
    assert ctx.workbook_data["Sheet1"][(1, 0)] == 3
    assert ctx.workbook_data["Sheet1"][(1, 1)] == 4

    # 2. Collision when a target cell has data
    ctx2 = EvalContext()
    ctx2.workbook_data["Sheet1"] = {(1, 1): "Obstructing Data"}
    manager2 = SpillManager()
    val2 = manager2.evaluate_and_spill("Sheet1", 0, 0, "=SEQUENCE(2, 2, 1, 1)", ctx2)
    assert val2 == SPILL


# --- 5. Financial Functions ---


def test_financial_annuities():
    """Verify PMT, PV, FV, NPER, RATE, and cash flow functions."""
    ctx = EvalContext()

    # PMT(0.08/12, 10, 10000)
    pmt = call_function("PMT", [0.08 / 12.0, 10, 10000], ctx)
    assert round(pmt, 2) == -1037.03

    # PV(0.08/12, 10, -1037.03)
    pv = call_function("PV", [0.08 / 12.0, 10, -1037.03], ctx)
    assert round(pv, 0) == 10000

    # FV(0.05/12, 12, -100)
    fv = call_function("FV", [0.05 / 12.0, 12, -100], ctx)
    assert round(fv, 2) == 1227.89

    # NPER(0.12/12, -100, -1000, 10000)
    nper = call_function("NPER", [0.12 / 12.0, -100, -1000, 10000], ctx)
    assert round(nper, 1) == 60.1

    # RATE(10, -1037.03, 10000)
    r = call_function("RATE", [10, -1037.03, 10000], ctx)
    assert round(r * 12.0, 2) == 0.08

    # Cash flows: NPV & IRR
    flows = [-10000, 3000, 4200, 6800]
    irr = call_function("IRR", [flows], ctx)
    assert round(irr, 4) == 0.1634

    npv = call_function("NPV", [0.1, 3000, 4200, 6800], ctx)
    assert round(npv, 2) == 11307.29

    # Depreciation: SLN & DDB
    sln = call_function("SLN", [10000, 1000, 5], ctx)
    assert sln == 1800.0

    ddb = call_function("DDB", [10000, 1000, 5, 1], ctx)
    assert ddb == 4000.0


# --- 6. Engineering Functions ---


def test_engineering_functions():
    """Verify base conversions, bitwise, complex numbers, and CONVERT."""
    ctx = EvalContext()

    # Base conversions
    assert call_function("BIN2DEC", ["1010"], ctx) == 10
    assert call_function("DEC2HEX", [255], ctx) == "FF"
    assert call_function("HEX2BIN", ["F"], ctx) == "1111"
    assert call_function("OCT2DEC", ["12"], ctx) == 10

    # Bitwise
    assert call_function("BITAND", [5, 3], ctx) == 1
    assert call_function("BITOR", [5, 3], ctx) == 7
    assert call_function("BITXOR", [5, 3], ctx) == 6
    assert call_function("BITLSHIFT", [4, 2], ctx) == 16
    assert call_function("BITRSHIFT", [16, 2], ctx) == 4

    # Complex numbers
    assert call_function("COMPLEX", [3, 4], ctx) == "3+4i"
    assert call_function("IMREAL", ["3+4i"], ctx) == 3.0
    assert call_function("IMAGINARY", ["3+4i"], ctx) == 4.0
    assert call_function("IMABS", ["3+4i"], ctx) == 5.0
    assert call_function("IMSUM", ["1+2i", "3+4i"], ctx) == "4+6i"
    assert call_function("IMSUB", ["4+6i", "1+2i"], ctx) == "3+4i"
    assert call_function("IMDIV", ["4+2i", "2"], ctx) == "2+i"

    # CONVERT
    conv_m_yd = call_function("CONVERT", [1, "m", "yd"], ctx)
    assert round(conv_m_yd, 4) == 1.0936

    conv_c_f = call_function("CONVERT", [100, "C", "F"], ctx)
    assert conv_c_f == 212.0


# --- 7. Statistical & Database Functions ---


def test_statistical_and_database():
    """Verify statistical distributions, quantiles, and database functions."""
    ctx = EvalContext()

    # Descriptive & Quantiles
    assert call_function("MEDIAN", [1, 2, 3, 4, 5], ctx) == 3
    assert call_function("MODE", [1, 2, 2, 3], ctx) == 2
    assert call_function("LARGE", [[10, 20, 30, 40], 2], ctx) == 30
    assert call_function("SMALL", [[10, 20, 30, 40], 2], ctx) == 20

    # Normal distribution
    p = call_function("NORM.S.DIST", [0, True], ctx)
    assert p == 0.5

    z = call_function("NORM.S.INV", [0.975], ctx)
    assert round(z, 2) == 1.96

    # Correlation
    x = [1, 2, 3, 4, 5]
    y = [2, 4, 6, 8, 10]
    r = call_function("CORREL", [x, y], ctx)
    assert round(r, 4) == 1.0
    assert call_function("SLOPE", [y, x], ctx) == 2.0
    assert call_function("INTERCEPT", [y, x], ctx) == 0.0
