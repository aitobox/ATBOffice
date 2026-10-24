"""Unit tests for spreadsheet formula AST tokens and nodes."""

from atboffice.modules.spreadsheet.calc.tokens import (
    ArrayNode,
    BinaryOpNode,
    CellRefNode,
    FunctionCallNode,
    LiteralNode,
    ParseError,
    Token,
    TokenType,
)


def test_token_creation():
    tok = Token(t=TokenType.NUM, v=42.0, pos=3, raw="42")
    assert tok.t == TokenType.NUM
    assert tok.v == 42.0
    assert tok.pos == 3
    assert tok.raw == "42"


def test_parse_error():
    err = ParseError("Unexpected character", 5)
    assert err.pos == 5
    assert "Unexpected character" in str(err)


def test_ast_node_hierarchy():
    lit1 = LiteralNode(kind="num", v=10.0)
    lit2 = LiteralNode(kind="num", v=20.0)
    bin_op = BinaryOpNode(op="+", left=lit1, right=lit2)
    assert bin_op.op == "+"
    assert bin_op.left == lit1
    assert bin_op.right == lit2

    cell = CellRefNode(r=0, c=0, ra=False, ca=False)
    fn = FunctionCallNode(name="SUM", args=[cell, bin_op])
    assert fn.name == "SUM"
    assert len(fn.args) == 2

    arr = ArrayNode(rows=[[lit1, lit2]])
    assert len(arr.rows) == 1
