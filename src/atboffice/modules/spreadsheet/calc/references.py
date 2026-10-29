"""Cell and range coordinate arithmetic, shift, translate, and structural adjustments."""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from typing import Any, Final

from atboffice.modules.spreadsheet.calc.tokens import (
    AreaRefNode,
    ArrayNode,
    ASTNode,
    BinaryOpNode,
    CellRefNode,
    FunctionCallNode,
    InvokeNode,
    NameNode,
    ParenNode,
    PercentNode,
    RefErrNode,
    SheetReference,
    UnaryOpNode,
    UnionNode,
)

MAXR: Final[int] = 1048576
MAXC: Final[int] = 16384

RE_CELL: Final[re.Pattern[str]] = re.compile(r"^(\$?)([A-Za-z]{1,3})(\$?)(\d{1,7})$")
RE_COL_PAIR: Final[re.Pattern[str]] = re.compile(r"^(\$?)([A-Za-z]{1,3}):(\$?)([A-Za-z]{1,3})$")
RE_ROW_PAIR: Final[re.Pattern[str]] = re.compile(r"^(\$?)(\d{1,7}):(\$?)(\d{1,7})$")


def col_name(c: int) -> str:
    """Convert 0-based column index to letter string (e.g. 0 -> 'A', 27 -> 'AB')."""
    s = ""
    c = c + 1
    while c > 0:
        m = (c - 1) % 26
        s = chr(65 + m) + s
        c = (c - 1) // 26
    return s


def col_index(s: str) -> int:
    """Convert column letter string to 0-based column index (e.g. 'A' -> 0, 'Z' -> 25)."""
    n = 0
    s = s.upper()
    for ch in s:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def cell_name(r: int, c: int, ra: bool = False, ca: bool = False) -> str:
    """Format row and column into A1 notation string (e.g. '$B$3' or 'A1')."""
    return f"{'$' if ca else ''}{col_name(c)}{'$' if ra else ''}{r + 1}"


def parse_cell(s: str) -> dict[str, Any] | None:
    """Parse 'B3' or '$B$3' into {'r': 2, 'c': 1, 'ra': bool, 'ca': bool} or None."""
    m = RE_CELL.match(str(s).strip())
    if not m:
        return None
    c = col_index(m.group(2))
    r = int(m.group(4)) - 1
    if c < 0 or c >= MAXC or r < 0 or r >= MAXR:
        return None
    return {"r": r, "c": c, "ca": bool(m.group(1)), "ra": bool(m.group(3))}


def parse_range(s: str) -> dict[str, int] | None:
    """Parse 'A1:B5', 'A:A', '3:3', 'B2' into normalized {'r1', 'c1', 'r2', 'c2'} or None."""
    clean = str(s).strip().replace("$", "")
    if ":" in clean:
        parts = clean.split(":")
        if len(parts) == 2:
            p1, p2 = parts[0], parts[1]
            # Try whole columns A:B
            if p1.isalpha() and p2.isalpha():
                c1, c2 = col_index(p1), col_index(p2)
                if 0 <= c1 < MAXC and 0 <= c2 < MAXC:
                    return {
                        "r1": 0,
                        "c1": min(c1, c2),
                        "r2": MAXR - 1,
                        "c2": max(c1, c2),
                    }
            # Try whole rows 1:5
            if p1.isdigit() and p2.isdigit():
                r1, r2 = int(p1) - 1, int(p2) - 1
                if 0 <= r1 < MAXR and 0 <= r2 < MAXR:
                    return {
                        "r1": min(r1, r2),
                        "c1": 0,
                        "r2": max(r1, r2),
                        "c2": MAXC - 1,
                    }
            # Try cell range A1:B5
            a, b = parse_cell(p1), parse_cell(p2)
            if a and b:
                return {
                    "r1": min(a["r"], b["r"]),
                    "c1": min(a["c"], b["c"]),
                    "r2": max(a["r"], b["r"]),
                    "c2": max(a["c"], b["c"]),
                }
    else:
        # Single cell
        a = parse_cell(clean)
        if a:
            return {"r1": a["r"], "c1": a["c"], "r2": a["r"], "c2": a["c"]}
    return None


def range_name(rg: dict[str, int]) -> str:
    """Format a range bounding box into display A1 notation."""
    r1, c1, r2, c2 = rg["r1"], rg["c1"], rg["r2"], rg["c2"]
    if r1 == 0 and r2 == MAXR - 1 and not (c1 == 0 and c2 == MAXC - 1):
        return f"{col_name(c1)}:{col_name(c2)}"
    if c1 == 0 and c2 == MAXC - 1:
        return f"{r1 + 1}:{r2 + 1}"
    a = f"{col_name(c1)}{r1 + 1}"
    if r1 == r2 and c1 == c2:
        return a
    return f"{a}:{col_name(c2)}{r2 + 1}"


def abs_range_name(rg: dict[str, int]) -> str:
    """Format a range bounding box into absolute notation with $."""
    r1, c1, r2, c2 = rg["r1"], rg["c1"], rg["r2"], rg["c2"]
    if r1 == 0 and r2 == MAXR - 1:
        return f"${col_name(c1)}:${col_name(c2)}"
    if c1 == 0 and c2 == MAXC - 1:
        return f"${r1 + 1}:${r2 + 1}"
    a = f"${col_name(c1)}${r1 + 1}"
    if r1 == r2 and c1 == c2:
        return a
    return f"{a}:${col_name(c2)}${r2 + 1}"


def quote_sheet(name: str | None) -> str:
    """Format sheet name as it must appear in a formula, adding single quotes if needed."""
    if name is None or not name:
        return ""
    # Safe without quotes if identifier starting with letter/underscore and not cell name or boolean
    if (
        re.match(r"^[A-Za-z_][A-Za-z0-9_.]*$", name)
        and not parse_cell(name)
        and not re.match(r"^R\d*C\d*$", name, re.IGNORECASE)
        and name.upper() not in ("TRUE", "FALSE")
    ):
        return name
    escaped = str(name).replace("'", "''")
    return f"'{escaped}'"


# ----------------------------------------------------------- AST Tree Operations


def walk(node: ASTNode | None, fn: Callable[[ASTNode], None]) -> None:
    """Depth-first preorder traversal of formula AST."""
    if node is None:
        return
    fn(node)
    if isinstance(node, FunctionCallNode):
        for arg in node.args:
            walk(arg, fn)
    elif isinstance(node, InvokeNode):
        walk(node.fn, fn)
        for arg in node.args:
            walk(arg, fn)
    elif isinstance(node, (ParenNode, UnaryOpNode, PercentNode)):
        walk(node.a, fn)
    elif isinstance(node, BinaryOpNode):
        walk(node.left, fn)
        walk(node.right, fn)
    elif isinstance(node, UnionNode):
        for item in node.items:
            walk(item, fn)
    elif isinstance(node, ArrayNode):
        for row in node.rows:
            for item in row:
                walk(item, fn)
    elif isinstance(node, SheetReference):
        if node.target is not None:
            walk(node.target, fn)


def map_ast(
    node: ASTNode | None, fn: Callable[[ASTNode], ASTNode | None]
) -> ASTNode | None:
    """Deep copy with a mapping function for reference or other nodes."""
    if node is None:
        return None
    r = fn(node)
    if r is not None:
        return r

    copied = copy.copy(node)
    if isinstance(copied, FunctionCallNode):
        copied.args = [
            res for a in copied.args if (res := map_ast(a, fn)) is not None
        ]
        return copied
    elif isinstance(copied, InvokeNode):
        copied.fn = map_ast(copied.fn, fn)
        copied.args = [
            res for a in copied.args if (res := map_ast(a, fn)) is not None
        ]
        return copied
    elif isinstance(copied, (ParenNode, UnaryOpNode, PercentNode)):
        copied.a = map_ast(copied.a, fn)
        copied.operand = copied.a
        return copied
    elif isinstance(copied, BinaryOpNode):
        copied.left = map_ast(copied.left, fn)
        copied.right = map_ast(copied.right, fn)
        copied.a = copied.left
        copied.b = copied.right
        return copied
    elif isinstance(copied, UnionNode):
        copied.items = [
            res for item in copied.items if (res := map_ast(item, fn)) is not None
        ]
        return copied
    elif isinstance(copied, ArrayNode):
        copied.rows = [
            [res for item in row if (res := map_ast(item, fn)) is not None]
            for row in copied.rows
        ]
        return copied
    elif isinstance(copied, SheetReference):
        if copied.target is not None:
            copied.target = map_ast(copied.target, fn)
        return copied
    return copy.copy(node)


def ref_err(node: ASTNode) -> RefErrNode:
    """Convert an existing reference node to a #REF! error node, preserving sheet context."""
    sheet = getattr(node, "sheet", None)
    sheet2 = getattr(node, "sheet2", None)
    book = getattr(node, "book", None)
    bang = getattr(node, "bang", False)
    return RefErrNode(sheet=sheet, sheet2=sheet2, book=book, bang=bang)


# ---------------------------------------------------- Shift & Translate


def shift(ast: ASTNode, dr: int, dc: int, wrap: bool = False) -> ASTNode:
    """Shift relative references by (dr, dc). Out of bounds references become #REF!."""
    if dr == 0 and dc == 0:
        return ast

    def wr(v: int) -> int:
        return ((v % MAXR) + MAXR) % MAXR if wrap else v

    def wc(v: int) -> int:
        return ((v % MAXC) + MAXC) % MAXC if wrap else v

    def mapper(n: ASTNode) -> ASTNode | None:
        if isinstance(n, CellRefNode):
            r = n.r if n.ra else wr(n.r + dr)
            c = n.c if n.ca else wc(n.c + dc)
            if r < 0 or r >= MAXR or c < 0 or c >= MAXC:
                return ref_err(n)
            res = copy.copy(n)
            res.r = r
            res.c = c
            return res
        if isinstance(n, AreaRefNode):
            res = copy.copy(n)
            if n.kind != "cols":
                res.r1 = n.r1 if n.ra1 else wr(n.r1 + dr)
                res.r2 = n.r2 if n.ra2 else wr(n.r2 + dr)
            if n.kind != "rows":
                res.c1 = n.c1 if n.ca1 else wc(n.c1 + dc)
                res.c2 = n.c2 if n.ca2 else wc(n.c2 + dc)
            if (
                res.r1 < 0
                or res.r2 >= MAXR
                or res.c1 < 0
                or res.c2 >= MAXC
                or res.r2 < 0
                or res.c2 < 0
                or res.r1 >= MAXR
                or res.c1 >= MAXC
            ):
                return ref_err(n)
            return res
        return None

    mapped = map_ast(ast, mapper)
    return mapped if mapped is not None else ast


def translate(text: str, dr: int, dc: int) -> str:
    """Translate formula text written for (r0, c0) to (r0+dr, c0+dc)."""
    # Lazy import to avoid circular dependency
    from atboffice.modules.spreadsheet.calc.parser import parse, to_text

    try:
        ast = parse(text)
        shifted = shift(ast, dr, dc)
        prefix = "=" if text.startswith("=") else ""
        return prefix + to_text(shifted)
    except Exception:
        return text


# ---------------------------------------------------- Structural Adjustments


def _same_sheet(n: ASTNode, target: str | None, home: str | None) -> bool:
    sheet = getattr(n, "sheet", None)
    s = sheet if sheet is not None else home
    if getattr(n, "book", None) is not None:
        return False
    if getattr(n, "sheet2", None) is not None:
        return False
    return (
        s is not None
        and target is not None
        and str(s).lower() == str(target).lower()
    )


def adjust(
    ast: ASTNode, op: dict[str, Any], home: str | None = None
) -> tuple[ASTNode, bool]:
    """Adjust references for a row/column insertion or deletion."""
    changed = False
    ins = op["n"] > 0
    cnt = abs(op["n"])
    lim = MAXR if op["axis"] == "r" else MAXC

    def mv(x: int) -> int | None:
        if ins:
            return x + cnt if x >= op["at"] else x
        if x < op["at"]:
            return x
        if x >= op["at"] + cnt:
            return x - cnt
        return None  # deleted

    def mapper(n: ASTNode) -> ASTNode | None:
        nonlocal changed
        if not isinstance(n, (CellRefNode, AreaRefNode)) or not _same_sheet(
            n, op.get("sheet"), home
        ):
            return None

        if isinstance(n, CellRefNode):
            k = "r" if op["axis"] == "r" else "c"
            curr_val = getattr(n, k)
            v = mv(curr_val)
            if v is None or v >= lim:
                changed = True
                return ref_err(n)
            if v != curr_val:
                changed = True
                res = copy.copy(n)
                setattr(res, k, v)
                return res
            return None

        if isinstance(n, AreaRefNode):
            k1 = "r1" if op["axis"] == "r" else "c1"
            k2 = "r2" if op["axis"] == "r" else "c2"
            if (op["axis"] == "r" and n.kind == "cols") or (
                op["axis"] == "c" and n.kind == "rows"
            ):
                return None
            a = getattr(n, k1)
            b = getattr(n, k2)
            if ins:
                if a >= op["at"]:
                    a += cnt
                if b >= op["at"]:
                    b += cnt
                if b >= lim:
                    b = lim - 1
                if a >= lim:
                    changed = True
                    return ref_err(n)
            else:
                d0 = op["at"]
                d1 = op["at"] + cnt - 1
                if b < d0:
                    return None
                if a > d1:
                    a -= cnt
                    b -= cnt
                elif a >= d0 and b <= d1:
                    changed = True
                    return ref_err(n)
                else:
                    na = a if a < d0 else d0
                    nb = b - cnt if b > d1 else d0 - 1
                    a, b = na, nb

            if a != getattr(n, k1) or b != getattr(n, k2):
                changed = True
                res = copy.copy(n)
                setattr(res, k1, a)
                setattr(res, k2, b)
                return res
            return None

        return None

    out = map_ast(ast, mapper)
    return (out if out is not None and changed else ast, changed)


def adjust_move(
    ast: ASTNode,
    src: dict[str, Any],
    dr: int,
    dc: int,
    home: str | None = None,
    to_sheet: str | None = None,
) -> tuple[ASTNode, bool]:
    """References into src follow a cut-and-paste move by (dr, dc) to to_sheet."""
    changed = False

    def inside(r: int, c: int) -> bool:
        return (
            r >= src["r1"]
            and r <= src["r2"]
            and c >= src["c1"]
            and c <= src["c2"]
        )

    def mapper(n: ASTNode) -> ASTNode | None:
        nonlocal changed
        if not isinstance(n, (CellRefNode, AreaRefNode)) or not _same_sheet(
            n, src.get("sheet"), home
        ):
            return None

        def qual(o: ASTNode) -> ASTNode:
            if to_sheet and str(to_sheet).lower() != str(src.get("sheet", "")).lower():
                setattr(o, "sheet", to_sheet)
            return o

        if isinstance(n, CellRefNode) and inside(n.r, n.c):
            changed = True
            res = copy.copy(n)
            res.r += dr
            res.c += dc
            return qual(res)

        if (
            isinstance(n, AreaRefNode)
            and not n.kind
            and inside(n.r1, n.c1)
            and inside(n.r2, n.c2)
        ):
            changed = True
            res = copy.copy(n)
            res.r1 += dr
            res.r2 += dr
            res.c1 += dc
            res.c2 += dc
            return qual(res)

        return None

    out = map_ast(ast, mapper)
    return (out if out is not None and changed else ast, changed)


def rename_sheet(
    ast: ASTNode, from_name: str, to_name: str | None
) -> tuple[ASTNode, bool]:
    """Rename sheet references, or convert to #REF! if to_name is None (sheet deleted)."""
    changed = False
    f = str(from_name).lower()

    def mapper(n: ASTNode) -> ASTNode | None:
        nonlocal changed
        if not isinstance(n, (CellRefNode, AreaRefNode, RefErrNode, NameNode)):
            return None
        if n.sheet is None or getattr(n, "book", None) is not None:
            return None
        hit1 = str(n.sheet).lower() == f
        sheet2 = getattr(n, "sheet2", None)
        hit2 = sheet2 is not None and str(sheet2).lower() == f
        if not hit1 and not hit2:
            return None

        changed = True
        if to_name is None:
            if isinstance(n, NameNode):
                return copy.copy(n)
            return ref_err(n)

        res = copy.copy(n)
        if hit1:
            res.sheet = to_name
        if hit2:
            res.sheet2 = to_name
        return res

    out = map_ast(ast, mapper)
    return (out if out is not None and changed else ast, changed)


def toggle_abs(text: str, sel_start: int, sel_end: int) -> dict[str, Any] | None:
    """F4 key cycle: cycle $ on reference at caret position in editing text."""
    pattern = re.compile(
        r"((?:'[^']*'|[A-Za-z0-9_.]+)!)?(\$?)([A-Za-z]{1,3})(\$?)(\d{1,7})(?::(\$?)([A-Za-z]{1,3})(\$?)(\d{1,7}))?"
    )
    for m in pattern.finditer(text):
        s = m.start()
        e = m.end()
        if sel_end < s or sel_start > e:
            continue

        # Cycle order: A1 -> $A$1 -> A$1 -> $A1 -> A1
        def cycle(ca: bool, ra: bool) -> tuple[str, str]:
            if not ca and not ra:
                return ("$", "$")
            if ca and ra:
                return ("", "$")
            if not ca and ra:
                return ("$", "")
            return ("", "")

        c1, r1 = cycle(bool(m.group(2)), bool(m.group(4)))
        prefix = m.group(1) or ""
        rep = f"{prefix}{c1}{m.group(3)}{r1}{m.group(5)}"
        if m.group(7):
            c2, r2 = cycle(bool(m.group(6)), bool(m.group(8)))
            rep += f":{c2}{m.group(7)}{r2}{m.group(9)}"

        new_text = text[:s] + rep + text[e:]
        return {"text": new_text, "caret": s + len(rep), "start": s}
    return None
