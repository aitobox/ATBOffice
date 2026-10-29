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

    @property
    def sheet_reference(self) -> SheetReference | None:
        if self.sheet:
            c_str = f"{'$' if self.ca else ''}{self._col_name(self.c)}{'$' if self.ra else ''}{self.r + 1}"
            return SheetReference(sheet_name=self.sheet, cell_range=c_str, target=self)
        return None

    @staticmethod
    def _col_name(c: int) -> str:
        s = ""
        c = c + 1
        while c > 0:
            m = (c - 1) % 26
            s = chr(65 + m) + s
            c = (c - 1) // 26
        return s


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

    @property
    def sheet_reference(self) -> SheetReference | None:
        if self.sheet:
            p1 = f"{'$' if self.ca1 else ''}{CellRefNode._col_name(self.c1)}{'$' if self.ra1 else ''}{self.r1 + 1}"
            p2 = f"{'$' if self.ca2 else ''}{CellRefNode._col_name(self.c2)}{'$' if self.ra2 else ''}{self.r2 + 1}"
            return SheetReference(sheet_name=self.sheet, cell_range=f"{p1}:{p2}", target=self)
        return None


@dataclass
class SheetReference(ASTNode):
    """Sheet-qualified reference AST node (e.g. Sheet2!A1 or 'Q1 Summary'!B5:C10)."""

    sheet_name: str = ""
    cell_range: str = ""
    t: str = "sheet_ref"
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
    is_range: bool = False
    target: ASTNode | None = None

    def __post_init__(self) -> None:
        if self.target is not None:
            if isinstance(self.target, CellRefNode):
                self.r = self.target.r
                self.c = self.target.c
                self.ra = self.target.ra
                self.ca = self.target.ca
                self.is_range = False
            elif isinstance(self.target, AreaRefNode):
                self.r1 = self.target.r1
                self.c1 = self.target.c1
                self.r2 = self.target.r2
                self.c2 = self.target.c2
                self.ra1 = self.target.ra1
                self.ca1 = self.target.ca1
                self.ra2 = self.target.ra2
                self.ca2 = self.target.ca2
                self.is_range = True
        elif self.cell_range:
            self._parse_range_str(self.cell_range)

    def _parse_range_str(self, s: str) -> None:
        import re

        clean = s.strip()
        re_cell = re.compile(r"^(\$?)([A-Za-z]{1,3})(\$?)(\d{1,7})$")

        def col_idx(col_str: str) -> int:
            n = 0
            for ch in col_str.upper():
                n = n * 26 + (ord(ch) - 64)
            return n - 1

        if ":" in clean:
            parts = clean.split(":")
            if len(parts) == 2:
                self.is_range = True
                p1, p2 = parts[0].strip(), parts[1].strip()
                m1, m2 = re_cell.match(p1), re_cell.match(p2)
                if m1 and m2:
                    c1_val = col_idx(m1.group(2))
                    r1_val = int(m1.group(4)) - 1
                    c2_val = col_idx(m2.group(2))
                    r2_val = int(m2.group(4)) - 1
                    self.r1 = min(r1_val, r2_val)
                    self.c1 = min(c1_val, c2_val)
                    self.r2 = max(r1_val, r2_val)
                    self.c2 = max(c1_val, c2_val)
                    self.ra1 = bool(m1.group(3))
                    self.ca1 = bool(m1.group(1))
                    self.ra2 = bool(m2.group(3))
                    self.ca2 = bool(m2.group(1))
        else:
            m = re_cell.match(clean)
            if m:
                self.c = col_idx(m.group(2))
                self.r = int(m.group(4)) - 1
                self.ca = bool(m.group(1))
                self.ra = bool(m.group(3))
                self.is_range = False


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
