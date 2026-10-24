"""AST tokens and node definitions for Ledger spreadsheet formulas."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TokenType(StrEnum):
    """Formula token types."""

    WS = "ws"
    NUM = "num"
    STR = "str"
    BOOL = "bool"
    ERR = "err"
    REF = "ref"
    NAME = "name"
    FN = "fn"
    STRUCT = "struct"
    SPILL = "spill"
    OP = "op"
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    COMMA = ","
    SEMICOLON = ";"


class ParseError(Exception):
    """Formula syntax parsing error with position."""

    def __init__(self, message: str, pos: int = 0) -> None:
        super().__init__(f"{message} at position {pos}")
        self.message = message
        self.pos = pos


@dataclass
class Token:
    """Lexer token representing a formula atom."""

    t: TokenType | str
    v: Any = None
    pos: int = 0
    raw: str | None = None
    len: int = 0
    kind: str | None = None
    sheet: str | None = None
    sheet2: str | None = None
    book: str | None = None
    bang: bool = False
    table: str | None = None
    spec: str | None = None
    # Reference coordinates
    r: int = 0
    c: int = 0
    ra: bool = False
    ca: bool = False
    r1: int = 0
    c1: int = 0
    r2: int = 0
    c2: int = 0
    ra1: bool = False
    ca1: bool = False
    ra2: bool = False
    ca2: bool = False


# ---------------------------------------------------------------- AST Nodes


@dataclass
class ASTNode:
    """Base class for all formula AST nodes."""

    t: str


@dataclass
class LiteralNode(ASTNode):
    """Literal values: numbers, strings, booleans, error codes, and missing params."""

    t: str = "num"
    v: Any = None
    kind: str | None = None

    def __post_init__(self) -> None:
        if self.kind:
            self.t = self.kind


@dataclass
class CellRefNode(ASTNode):
    """Single cell reference (e.g. A1, $B$3, Sheet1!C4)."""

    t: str = "ref"
    r: int = 0
    c: int = 0
    ra: bool = False
    ca: bool = False
    sheet: str | None = None
    sheet2: str | None = None
    book: str | None = None
    bang: bool = False


@dataclass
class AreaRefNode(ASTNode):
    """Area reference (e.g. A1:B10, A:A, 1:5)."""

    t: str = "area"
    r1: int = 0
    c1: int = 0
    r2: int = 0
    c2: int = 0
    ra1: bool = False
    ca1: bool = False
    ra2: bool = False
    ca2: bool = False
    sheet: str | None = None
    sheet2: str | None = None
    book: str | None = None
    kind: str | None = None  # None | "cols" | "rows"
    bang: bool = False


@dataclass
class RefErrNode(ASTNode):
    """#REF! reference error node."""

    t: str = "referr"
    sheet: str | None = None
    sheet2: str | None = None
    book: str | None = None
    bang: bool = False


@dataclass
class NameNode(ASTNode):
    """Defined name identifier."""

    t: str = "name"
    name: str = ""
    sheet: str | None = None
    book: str | None = None
    param: bool = False


@dataclass
class StructuredRefNode(ASTNode):
    """Structured table reference (e.g. Table1[@Amount])."""

    t: str = "struct"
    table: str | None = None
    spec: str = ""
    sheet: str | None = None


@dataclass
class UnaryOpNode(ASTNode):
    """Unary operator node (+, -, @)."""

    t: str = "un"
    op: str = ""
    operand: ASTNode | None = None
    a: ASTNode | None = None

    def __post_init__(self) -> None:
        if self.operand is not None and self.a is None:
            self.a = self.operand
        elif self.a is not None and self.operand is None:
            self.operand = self.a


@dataclass
class BinaryOpNode(ASTNode):
    """Binary operator node (+, -, *, /, ^, &, =, <, >, etc.)."""

    t: str = "op"
    op: str = ""
    left: ASTNode | None = None
    right: ASTNode | None = None
    a: ASTNode | None = None
    b: ASTNode | None = None

    def __post_init__(self) -> None:
        if self.left is not None and self.a is None:
            self.a = self.left
        elif self.a is not None and self.left is None:
            self.left = self.a
        if self.right is not None and self.b is None:
            self.b = self.right
        elif self.b is not None and self.right is None:
            self.right = self.b


@dataclass
class PercentNode(ASTNode):
    """Postfix percent operator node (%)."""

    t: str = "pct"
    operand: ASTNode | None = None
    a: ASTNode | None = None

    def __post_init__(self) -> None:
        if self.operand is not None and self.a is None:
            self.a = self.operand
        elif self.a is not None and self.operand is None:
            self.operand = self.a


@dataclass
class FunctionCallNode(ASTNode):
    """Function call node (e.g. SUM(A1:B2))."""

    t: str = "fn"
    name: str = ""
    args: list[ASTNode] = field(default_factory=list)
    raw: str = ""
    udf: bool = False


@dataclass
class InvokeNode(ASTNode):
    """Immediately invoked function expression (e.g. LAMBDA(x, x*2)(4))."""

    t: str = "invoke"
    fn: ASTNode | None = None
    args: list[ASTNode] = field(default_factory=list)


@dataclass
class ParenNode(ASTNode):
    """Parenthesized expression node."""

    t: str = "paren"
    operand: ASTNode | None = None
    a: ASTNode | None = None

    def __post_init__(self) -> None:
        if self.operand is not None and self.a is None:
            self.a = self.operand
        elif self.a is not None and self.operand is None:
            self.operand = self.a


@dataclass
class UnionNode(ASTNode):
    """Union operator node (e.g. (A1:B2, C3:D4))."""

    t: str = "union"
    items: list[ASTNode] = field(default_factory=list)


@dataclass
class ArrayNode(ASTNode):
    """Array constant literal node (e.g. {1, 2; 3, 4})."""

    t: str = "arr"
    rows: list[list[ASTNode]] = field(default_factory=list)
