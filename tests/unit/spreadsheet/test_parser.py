"""Unit tests for spreadsheet formula Pratt parser and serializer."""

import pytest

from atboffice.modules.spreadsheet.calc.parser import (
    display,
    parse,
    to_store,
    to_text,
    try_parse,
)
from atboffice.modules.spreadsheet.calc.references import translate
from atboffice.modules.spreadsheet.calc.tokens import (
    AreaRefNode,
    ArrayNode,
    BinaryOpNode,
    CellRefNode,
    FunctionCallNode,
    InvokeNode,
    LiteralNode,
    ParenNode,
    ParseError,
    PercentNode,
    StructuredRefNode,
    UnaryOpNode,
    UnionNode,
)


def test_parse_literals():
    ast_num = parse("42.5")
    assert isinstance(ast_num, LiteralNode)
    assert ast_num.v == 42.5

    ast_str = parse('"Hello ""World"""')
    assert isinstance(ast_str, LiteralNode)
    assert ast_str.v == 'Hello "World"'

    ast_bool = parse("TRUE")
    assert isinstance(ast_bool, LiteralNode)
    assert ast_bool.v is True

    ast_err = parse("#REF!")
    assert isinstance(ast_err, LiteralNode)
    assert ast_err.v == "#REF!"


def test_parse_binary_precedence():
    # 1 + 2 * 3 -> 1 + (2 * 3)
    ast = parse("1 + 2 * 3")
    assert isinstance(ast, BinaryOpNode)
    assert ast.op == "+"
    assert isinstance(ast.left, LiteralNode) and ast.left.v == 1
    assert isinstance(ast.right, BinaryOpNode)
    assert ast.right.op == "*"

    # (1 + 2) * 3
    ast_paren = parse("(1 + 2) * 3")
    assert isinstance(ast_paren, BinaryOpNode)
    assert ast_paren.op == "*"
    assert isinstance(ast_paren.left, ParenNode)

    # 2 ^ 3 ^ 2 -> left-associative in Excel (2^3)^2 = 64
    ast_pow = parse("2 ^ 3 ^ 2")
    assert isinstance(ast_pow, BinaryOpNode)
    assert ast_pow.op == "^"
    assert isinstance(ast_pow.left, BinaryOpNode)
    assert ast_pow.left.op == "^"
    assert isinstance(ast_pow.right, LiteralNode) and ast_pow.right.v == 2


def test_parse_unary_and_percent():
    ast_neg = parse("-5 + 3")
    assert isinstance(ast_neg, BinaryOpNode)
    assert ast_neg.op == "+"
    assert isinstance(ast_neg.left, UnaryOpNode)
    assert ast_neg.left.op == "-"

    # -2 ^ 2 -> (-2) ^ 2 in Excel (unary has precedence 7, power has 5)
    ast_u_pow = parse("-2 ^ 2")
    assert isinstance(ast_u_pow, BinaryOpNode)
    assert ast_u_pow.op == "^"
    assert isinstance(ast_u_pow.left, UnaryOpNode)

    ast_pct = parse("50%")
    assert isinstance(ast_pct, PercentNode)
    assert isinstance(ast_pct.a, LiteralNode) and ast_pct.a.v == 50


def test_parse_references():
    ast_cell = parse("A1")
    assert isinstance(ast_cell, CellRefNode)
    assert ast_cell.r == 0 and ast_cell.c == 0

    ast_area = parse("$A$1:$B$10")
    assert isinstance(ast_area, AreaRefNode)
    assert ast_area.r1 == 0 and ast_area.c1 == 0
    assert ast_area.r2 == 9 and ast_area.c2 == 1
    assert ast_area.ra1 and ast_area.ca1 and ast_area.ra2 and ast_area.ca2

    # Whole column and row
    ast_cols = parse("A:C")
    assert isinstance(ast_cols, AreaRefNode)
    assert ast_cols.c1 == 0 and ast_cols.c2 == 2

    ast_rows = parse("2:5")
    assert isinstance(ast_rows, AreaRefNode)
    assert ast_rows.r1 == 1 and ast_rows.r2 == 4

    # Sheet and 3D Sheet reference
    ast_sh = parse("'Sales 2024'!B5")
    assert isinstance(ast_sh, CellRefNode)
    assert ast_sh.sheet == "Sales 2024"
    assert ast_sh.r == 4 and ast_sh.c == 1

    ast_3d = parse("'Sheet1:Sheet3'!A1:B10")
    assert isinstance(ast_3d, AreaRefNode)
    assert ast_3d.sheet == "Sheet1"
    assert ast_3d.sheet2 == "Sheet3"

    # External workbook
    ast_book = parse("[Budget.xlsx]Summary!C10")
    assert isinstance(ast_book, CellRefNode)
    assert ast_book.book == "Budget.xlsx"
    assert ast_book.sheet == "Summary"


def test_parse_function_calls():
    ast = parse("SUM(A1:B10, 5, MAX(C1, C2))")
    assert isinstance(ast, FunctionCallNode)
    assert ast.name == "SUM"
    assert len(ast.args) == 3
    assert isinstance(ast.args[0], AreaRefNode)
    assert isinstance(ast.args[1], LiteralNode)
    assert isinstance(ast.args[2], FunctionCallNode)
    assert ast.args[2].name == "MAX"

    # Missing arguments
    ast_miss = parse("IF(A1,,B1)")
    assert isinstance(ast_miss, FunctionCallNode)
    assert len(ast_miss.args) == 3
    assert ast_miss.args[1].t == "missing"

    # Immediately invoked lambda
    ast_inv = parse("LAMBDA(x, x * 2)(10)")
    assert isinstance(ast_inv, InvokeNode)
    assert isinstance(ast_inv.fn, FunctionCallNode)
    assert ast_inv.fn.name == "LAMBDA"
    assert len(ast_inv.args) == 1


def test_parse_structured_and_spill():
    ast_struct = parse("Table1[@Amount]")
    assert isinstance(ast_struct, StructuredRefNode)
    assert ast_struct.table == "Table1"
    assert ast_struct.spec == "[@Amount]"

    # Spill operator A1#
    ast_spill = parse("A1#")
    assert isinstance(ast_spill, FunctionCallNode)
    assert ast_spill.name == "ANCHORARRAY"
    assert len(ast_spill.args) == 1
    assert isinstance(ast_spill.args[0], CellRefNode)


def test_parse_array_constant():
    ast_arr = parse("{1, 2, 3; 4, 5, 6}")
    assert isinstance(ast_arr, ArrayNode)
    assert len(ast_arr.rows) == 2
    assert len(ast_arr.rows[0]) == 3
    assert len(ast_arr.rows[1]) == 3

    # Mismatched rows raise ParseError
    with pytest.raises(ParseError):
        parse("{1, 2; 3}")


def test_parse_union_and_intersection():
    # Intersection: space between ref-like nodes
    ast_inter = parse("A1:C3 B2:D4")
    assert isinstance(ast_inter, BinaryOpNode)
    assert ast_inter.op == " "

    # Union: comma inside parentheses
    ast_union = parse("(A1:B2, C3:D4)")
    assert isinstance(ast_union, ParenNode)
    assert isinstance(ast_union.a, UnionNode)
    assert len(ast_union.a.items) == 2


def test_serializer_and_roundtrip():
    expr = "SUM(A1:B10)+5*$C$2"
    ast = parse(expr)
    text = to_text(ast)
    assert text == "SUM(A1:B10)+5*$C$2"

    # Array to_text
    ast_arr = parse("{1,2;3,4}")
    assert to_text(ast_arr) == "{1,2;3,4}"

    # String with escaped quotes
    ast_str = parse('"A""B"')
    assert to_text(ast_str) == '"A""B"'

    # Display vs store
    assert display("_xlfn.ANCHORARRAY(A1)") == "A1#"
    assert to_store("A1#") == "_xlfn.ANCHORARRAY(A1)"

    # Translate with formula
    translated = translate("=A1+$B$1", 2, 3)
    assert translated == "=D3+$B$1"


def test_try_parse():
    ast, err = try_parse("=SUM(A1:A5)")
    assert ast is not None
    assert err is None

    ast_bad, err_bad = try_parse("=SUM(")
    assert ast_bad is None
    assert err_bad is not None
