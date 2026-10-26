"""Calculation engine regression tests ported from .vibeoffice/tests/ledger/calc.test.js.

Verifies cross-sheet references, criteria evaluation, arithmetic, strings,
dates, lookup, financial, and statistical functions.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.evaluator import evaluate


@pytest.fixture
def calc_context() -> EvalContext:
    ctx = EvalContext()
    ctx.workbook_data = {"Sheet1": {}, "Data": {}}

    # Data sheet
    data = [
        ["Name", "Dept", "Sales", "Date"],
        ["Ann", "East", 100, 45292],
        ["Bob", "West", 250, 45300],
        ["Cy", "East", 175, 45310],
        ["Di", "North", 50, 45320],
        ["Ed", "West", 300, 45330],
    ]
    for r, row in enumerate(data):
        for c, val in enumerate(row):
            ctx.workbook_data["Data"][(r, c)] = val

    # Sheet1 numbers and words
    for i in range(1, 11):
        ctx.workbook_data["Sheet1"][(i - 1, 0)] = i
    words = ["apple", "banana", "cherry", "date", "elder"]
    for i, w in enumerate(words):
        ctx.workbook_data["Sheet1"][(i, 1)] = w

    # Formulas in Sheet1
    ctx.workbook_data["Sheet1"][(0, 2)] = evaluate("=SUM(A1:A10)", ctx)
    ctx.workbook_data["Sheet1"][(1, 2)] = evaluate("=C1*2", ctx)

    # Criteria block for D-functions
    ctx.workbook_data["Sheet1"][(0, 7)] = "Dept"
    ctx.workbook_data["Sheet1"][(1, 7)] = "West"
    ctx.workbook_data["Sheet1"][(0, 8)] = "Sales"
    ctx.workbook_data["Sheet1"][(1, 8)] = ">200"
    ctx.workbook_data["Sheet1"][(0, 9)] = "Dept"
    ctx.workbook_data["Sheet1"][(1, 9)] = "East"
    ctx.workbook_data["Sheet1"][(2, 9)] = "North"

    return ctx


def assert_eval(ctx: EvalContext, formula: str, expected: Any, tol: float = 1e-9) -> None:
    expr = formula if formula.startswith("=") else f"={formula}"
    got = evaluate(expr, ctx)
    if hasattr(got, "error_code"):
        got = got.error_code

    if isinstance(expected, (int, float)) and isinstance(got, (int, float)):
        assert math.isclose(got, expected, rel_tol=tol, abs_tol=tol), (
            f"Failed {formula}: got {got}, expected {expected}"
        )
    else:
        assert str(got) == str(expected), f"Failed {formula}: got {got}, expected {expected}"


class TestCalcRegression:
    def test_cell_references_and_aggregates(self, calc_context: EvalContext):
        assert_eval(calc_context, "C1", 55)
        assert_eval(calc_context, "C2", 110)
        assert_eval(calc_context, "SUM(A1:A10)/COUNT(A1:A10)", 5.5)
        assert_eval(calc_context, "AVERAGE(A1:A10)", 5.5)
        assert_eval(calc_context, "MEDIAN(A1:A10)", 5.5)
        assert_eval(calc_context, "STDEV(A1:A10)", 3.0276503540974917)
        assert_eval(calc_context, "SUMPRODUCT((A1:A10>5)*A1:A10)", 40)
        assert_eval(calc_context, 'SUMIF(A1:A10,">5")', 40)
        assert_eval(calc_context, 'COUNTIF(B1:B5,"*e*")', 4)
        assert_eval(calc_context, 'COUNTIFS(A1:A10,">2",A1:A10,"<8")', 5)

    def test_cross_sheet_and_lookups(self, calc_context: EvalContext):
        assert_eval(calc_context, 'AVERAGEIFS(Data!C2:C6,Data!B2:B6,"West")', 275)
        assert_eval(calc_context, 'SUMIFS(Data!C2:C6,Data!B2:B6,"East",Data!C2:C6,">100")', 175)
        assert_eval(calc_context, 'VLOOKUP("Cy",Data!A1:D6,3,FALSE)', 175)
        assert_eval(calc_context, 'VLOOKUP("Zed",Data!A1:D6,3,FALSE)', "#N/A")
        assert_eval(calc_context, 'HLOOKUP("Sales",Data!A1:D6,3,FALSE)', 250)
        assert_eval(calc_context, 'INDEX(Data!A1:D6,MATCH("Di",Data!A1:A6,0),2)', "North")
        assert_eval(calc_context, "MATCH(7,A1:A10,1)", 7)
        assert_eval(calc_context, "MATCH(7.5,A1:A10)", 7)
        assert_eval(calc_context, "LOOKUP(6.5,A1:A10,A1:A10)", 6)
        assert_eval(calc_context, 'XLOOKUP("Ed",Data!A2:A6,Data!C2:C6)', 300)
        assert_eval(calc_context, 'XMATCH("cherry",B1:B5)', 3)

    def test_logic_and_branching(self, calc_context: EvalContext):
        assert_eval(calc_context, 'IFERROR(1/0,"x")', "x")
        assert_eval(calc_context, 'ISNA(MATCH("q",B1:B5,0))', True)
        assert_eval(calc_context, 'IF(A1>0,"pos","neg")', "pos")
        assert_eval(calc_context, 'IFS(A3=1,"a",A3=3,"c")', "c")
        assert_eval(calc_context, 'CHOOSE(2,"a","b","c")', "b")
        assert_eval(calc_context, 'SWITCH(2,1,"one",2,"two","other")', "two")

    def test_math_and_numeric_functions(self, calc_context: EvalContext):
        assert_eval(calc_context, "ROUND(2.345,2)", 2.35)
        assert_eval(calc_context, "ROUND(-2.5,0)", -3)
        assert_eval(calc_context, "ROUNDUP(2.341,2)", 2.35)
        assert_eval(calc_context, "ROUNDDOWN(-2.349,2)", -2.34)
        assert_eval(calc_context, "MROUND(10,3)", 9)
        assert_eval(calc_context, "CEILING(2.5,1)", 3)
        assert_eval(calc_context, "FLOOR(-2.5,-1)", -2)
        assert_eval(calc_context, "INT(-1.5)", -2)
        assert_eval(calc_context, "TRUNC(-1.5)", -1)
        assert_eval(calc_context, "MOD(-3,2)", 1)
        assert_eval(calc_context, "MOD(3,-2)", -1)
        assert_eval(calc_context, "POWER(2,10)", 1024)
        assert_eval(calc_context, "SQRT(16)", 4)
        assert_eval(calc_context, "ABS(-3)", 3)
        assert_eval(calc_context, "SIGN(-2)", -1)
        assert_eval(calc_context, "PRODUCT(1,2,3,4)", 24)
        assert_eval(calc_context, "FACT(5)", 120)
        assert_eval(calc_context, "COMBIN(10,3)", 120)
        assert_eval(calc_context, "PERMUT(5,2)", 20)
        assert_eval(calc_context, "GCD(12,18)", 6)
        assert_eval(calc_context, "LCM(4,6)", 12)
        assert_eval(calc_context, "0.1+0.2=0.3", True)

    def test_string_manipulation(self, calc_context: EvalContext):
        assert_eval(calc_context, 'LEN("hello")', 5)
        assert_eval(calc_context, 'LEFT("hello",2)', "he")
        assert_eval(calc_context, 'MID("hello",2,3)', "ell")
        assert_eval(calc_context, 'RIGHT("hello",3)', "llo")
        assert_eval(calc_context, 'UPPER("abc")', "ABC")
        assert_eval(calc_context, 'PROPER("hello WORLD")', "Hello World")
        assert_eval(calc_context, 'TRIM("  a   b  ")', "a b")
        assert_eval(calc_context, 'SUBSTITUTE("aaa","a","b",2)', "aba")
        assert_eval(calc_context, 'REPLACE("abcdef",2,3,"X")', "aXef")
        assert_eval(calc_context, 'FIND("l","hello")', 3)
        assert_eval(calc_context, 'SEARCH("L*O","hello")', 3)
        assert_eval(calc_context, 'TEXT(1234.567,"#,##0.00")', "1,234.57")
        assert_eval(calc_context, 'VALUE("1,234.5")', 1234.5)
        assert_eval(calc_context, 'CONCATENATE("a",1,TRUE)', "a1TRUE")
        assert_eval(calc_context, 'TEXTJOIN(",",TRUE,B1:B3)', "apple,banana,cherry")
        assert_eval(calc_context, 'REPT("ab",3)', "ababab")
        assert_eval(calc_context, 'EXACT("a","A")', False)
        assert_eval(calc_context, '"a"="A"', True)
        assert_eval(calc_context, "CHAR(65)", "A")
        assert_eval(calc_context, 'CODE("a")', 97)

    def test_date_and_time_functions(self, calc_context: EvalContext):
        assert_eval(calc_context, "DATE(2024,2,29)", 45351)
        assert_eval(calc_context, "YEAR(45351)", 2024)
        assert_eval(calc_context, "MONTH(45351)", 2)
        assert_eval(calc_context, "DAY(45351)", 29)
        assert_eval(calc_context, "WEEKDAY(45351)", 5)
        assert_eval(calc_context, "EOMONTH(45292,1)", 45351)
        assert_eval(calc_context, "EDATE(45322,1)", 45351)
        assert_eval(calc_context, 'DATEDIF(DATE(2020,1,15),DATE(2024,3,10),"y")', 4)
        assert_eval(calc_context, "NETWORKDAYS(DATE(2024,1,1),DATE(2024,1,31))", 23)
        assert_eval(calc_context, "WORKDAY(DATE(2024,1,1),10)", 45306)
        assert_eval(calc_context, "WEEKNUM(DATE(2024,3,15))", 11)
        assert_eval(calc_context, "ISOWEEKNUM(DATE(2024,1,1))", 1)

    def test_financial_calculations(self, calc_context: EvalContext):
        assert_eval(calc_context, "PMT(0.05/12,360,200000)", -1073.6432460242795)
        assert_eval(calc_context, "FV(0.06/12,10,-200,-500,1)", 2581.4033740601185)
        assert_eval(calc_context, "PV(0.08/12,240,500)", -59777.14585118727)
        assert_eval(calc_context, "SLN(30000,7500,10)", 2250)
        assert_eval(calc_context, "DDB(2400,300,10,1)", 480)
        assert_eval(calc_context, "SYD(30000,7500,10,1)", 4090.909090909091)
        assert_eval(calc_context, "VDB(2400,300,10,0,1)", 480)
        assert_eval(calc_context, "VDB(2400,300,120,0,1)", 40)
        assert_eval(calc_context, "EFFECT(0.0525,4)", 0.053542667370758365)
        assert_eval(calc_context, "NOMINAL(0.053543,4)", 0.0525003198683560)

    def test_statistics_and_distributions(self, calc_context: EvalContext):
        assert_eval(calc_context, "NORMSDIST(1.96)", 0.9750021048517795)
        assert_eval(calc_context, "NORMSINV(0.975)", 1.959963984540054)
        assert_eval(calc_context, "LARGE(A1:A10,3)", 8)
        assert_eval(calc_context, "SMALL(A1:A10,3)", 3)
        assert_eval(calc_context, "RANK(7,A1:A10)", 4)
        assert_eval(calc_context, "VAR({1,2,3,4})", 1.6666666666666667)
        assert_eval(calc_context, "GAMMALN(4)", 1.791759469228055)
        assert_eval(calc_context, "STANDARDIZE(42,40,1.5)", 1.3333333333333333)

    def test_engineering_and_bitops(self, calc_context: EvalContext):
        assert_eval(calc_context, 'BIN2DEC("1111111111")', -1)
        assert_eval(calc_context, "DEC2BIN(9,4)", "1001")
        assert_eval(calc_context, "DEC2HEX(-54)", "FFFFFFFFCA")
        assert_eval(calc_context, 'HEX2DEC("A5")', 165)
        assert_eval(calc_context, 'OCT2BIN("3")', "11")
        assert_eval(calc_context, "BITAND(13,25)", 9)
        assert_eval(calc_context, "BITOR(23,10)", 31)
        assert_eval(calc_context, "BITXOR(5,3)", 6)
        assert_eval(calc_context, "DELTA(5,5)", 1)
        assert_eval(calc_context, "GESTEP(-4,-5)", 1)
        assert_eval(calc_context, "ERF(1)", 0.8427007929497149)

    def test_error_and_special_semantics(self, calc_context: EvalContext):
        assert_eval(calc_context, "1/0", "#DIV/0!")
        assert_eval(calc_context, "SQRT(-1)", "#NUM!")
        assert_eval(calc_context, '"a"+1', "#VALUE!")
        assert_eval(calc_context, "NA()", "#N/A")
        assert_eval(calc_context, "UNKNOWNFN(1)", "#NAME?")
        assert_eval(calc_context, "2^-1", 0.5)
        assert_eval(calc_context, "-2^2", 4)
        assert_eval(calc_context, "(1+2)*3", 9)
