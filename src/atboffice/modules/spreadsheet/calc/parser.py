"""Tokeniser, Pratt precedence parser, and serializer for Excel spreadsheet formulas."""

from __future__ import annotations

import re
from typing import Any, Final

from atboffice.modules.spreadsheet.calc.references import (
    MAXC,
    MAXR,
    cell_name,
    col_index,
    col_name,
    quote_sheet,
    walk,
)
from atboffice.modules.spreadsheet.calc.tokens import (
    AreaRefNode,
    ArrayNode,
    ASTNode,
    BinaryOpNode,
    CellRefNode,
    FunctionCallNode,
    InvokeNode,
    LiteralNode,
    NameNode,
    ParenNode,
    ParseError,
    PercentNode,
    RefErrNode,
    SheetReference,
    StructuredRefNode,
    Token,
    UnaryOpNode,
    UnionNode,
)

ERRORS: Final[list[str]] = [
    "#NULL!",
    "#DIV/0!",
    "#VALUE!",
    "#REF!",
    "#NAME?",
    "#NUM!",
    "#N/A",
    "#GETTING_DATA",
    "#SPILL!",
    "#CALC!",
    "#CYCLE!",
    "#FIELD!",
    "#BLOCKED!",
    "#UNKNOWN!",
    "#CONNECT!",
    "#BUSY!",
    "#EXTERNAL!",
    "#PYTHON!",
]

FUTURE: Final[set[str]] = set(
    (
        "ACOT ACOTH AGGREGATE ARABIC BASE BETA.DIST BETA.INV BINOM.DIST "
        "BINOM.DIST.RANGE BINOM.INV BITAND BITLSHIFT BITOR BITRSHIFT BITXOR "
        "CEILING.MATH CEILING.PRECISE CHISQ.DIST CHISQ.DIST.RT CHISQ.INV "
        "CHISQ.INV.RT CHISQ.TEST COMBINA CONCAT CONFIDENCE.NORM CONFIDENCE.T "
        "COT COTH COVARIANCE.P COVARIANCE.S CSC CSCH DAYS DECIMAL ERF.PRECISE "
        "ERFC.PRECISE EXPON.DIST F.DIST F.DIST.RT F.INV F.INV.RT F.TEST "
        "FILTERXML FLOOR.MATH FLOOR.PRECISE FORECAST.ETS FORECAST.ETS.CONFINT "
        "FORECAST.ETS.SEASONALITY FORECAST.ETS.STAT FORECAST.LINEAR FORMULATEXT "
        "GAMMA GAMMA.DIST GAMMA.INV GAMMALN.PRECISE GAUSS HYPGEOM.DIST IFNA "
        "IFS IMCOSH IMCOT IMCSC IMCSCH IMSEC IMSECH IMSINH IMTAN ISFORMULA "
        "ISOWEEKNUM LOGNORM.DIST LOGNORM.INV MAXIFS MINIFS MODE.MULT MODE.SNGL "
        "MUNIT NEGBINOM.DIST NORM.DIST NORM.INV NORM.S.DIST NORM.S.INV "
        "NUMBERVALUE PDURATION PERCENTILE.EXC PERCENTILE.INC PERCENTRANK.EXC "
        "PERCENTRANK.INC PERMUTATIONA PHI POISSON.DIST QUARTILE.EXC "
        "QUARTILE.INC QUERYSTRING RANK.AVG RANK.EQ RRI SEC SECH SHEET SHEETS "
        "SKEW.P STDEV.P STDEV.S SWITCH T.DIST T.DIST.2T T.DIST.RT T.INV "
        "T.INV.2T T.TEST TEXTJOIN UNICHAR UNICODE VAR.P VAR.S WEBSERVICE "
        "WEIBULL.DIST XOR Z.TEST XLOOKUP XMATCH FILTER SORT SORTBY UNIQUE "
        "SEQUENCE RANDARRAY LET LAMBDA TEXTBEFORE TEXTAFTER TEXTSPLIT VSTACK "
        "HSTACK TOCOL TOROW WRAPROWS WRAPCOLS TAKE DROP CHOOSEROWS CHOOSECOLS "
        "EXPAND ARRAYTOTEXT VALUETOTEXT ISOMITTED BYROW BYCOL MAP REDUCE "
        "SCAN MAKEARRAY ECMA.CEILING ISO.CEILING NETWORKDAYS.INTL "
        "WORKDAY.INTL STOCKHISTORY IMAGE REGEXTEST REGEXEXTRACT REGEXREPLACE "
        "GROUPBY PIVOTBY PERCENTOF TRIMRANGE ANCHORARRAY SINGLE FIELDVALUE CONCAT"
    ).split()
)
XLWS: Final[set[str]] = {"FILTER", "SORT", "SORTBY"}

BIN_PREC: Final[dict[str, int]] = {
    ":": 9,
    " ": 8,
    "^": 5,
    "*": 4,
    "/": 4,
    "+": 3,
    "-": 3,
    "&": 2,
    "=": 1,
    "<": 1,
    ">": 1,
    "<=": 1,
    ">=": 1,
    "<>": 1,
}
UNARY_PREC: Final[int] = 7
PCT_PREC: Final[int] = 6

RE_CELL: Final[re.Pattern[str]] = re.compile(
    r"^(\$?)([A-Za-z]{1,3})(\$?)(\d{1,7})(?![A-Za-z0-9_.(\[])"
)
RE_COL: Final[re.Pattern[str]] = re.compile(r"^(\$?)([A-Za-z]{1,3})(?=\s*:)")
RE_ROW_PAIR: Final[re.Pattern[str]] = re.compile(
    r"^(\$?)(\d{1,7}):(\$?)(\d{1,7})(?![\d.A-Za-z(])"
)
RE_COL_PAIR: Final[re.Pattern[str]] = re.compile(
    r"^(\$?)([A-Za-z]{1,3}):(\$?)([A-Za-z]{1,3})(?![A-Za-z0-9_.(\[!])"
)
RE_NUM: Final[re.Pattern[str]] = re.compile(
    r"^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
)
RE_IDENT: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z_\\¡-ÿ][A-Za-z0-9_.\\?¡-ÿ]*"
)
RE_SHEET_UNQ: Final[re.Pattern[str]] = re.compile(
    r"^([A-Za-z0-9_.¡-ÿ]+(?::[A-Za-z0-9_.¡-ÿ]+)?)!"
)


def store_name(name: str) -> str:
    """Return file-storage name with _xlfn. prefix if required by Excel."""
    if name in FUTURE:
        prefix = "_xlfn._xlws." if name in XLWS else "_xlfn."
        return f"{prefix}{name}"
    return name


def match_bracket(src: str, i: int) -> int:
    """Find matching closing square bracket for structured reference."""
    depth = 0
    j = i
    n = len(src)
    while j < n:
        c = src[j]
        if c == "'" and j + 1 < n:
            j += 2
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    raise ParseError("Missing ] in structured reference", i)


def split_sheet_3d(s: str) -> tuple[str, str] | None:
    """Split 3D sheet reference 'Sheet1:Sheet3' into ('Sheet1', 'Sheet3') or None."""
    k = s.find(":")
    if k <= 0:
        return None
    return (s[:k], s[k + 1 :])


def ref_token(s: str) -> Token | None:
    """Detect cell, area, whole-row, or whole-column reference at the start of s."""
    m_row = RE_ROW_PAIR.match(s)
    if m_row:
        a = int(m_row.group(2)) - 1
        b = int(m_row.group(4)) - 1
        if 0 <= a < MAXR and 0 <= b < MAXR:
            return Token(
                t="ref",
                kind="rows",
                r1=a,
                r2=b,
                ra1=bool(m_row.group(1)),
                ra2=bool(m_row.group(3)),
                len=len(m_row.group(0)),
            )

    m_col = RE_COL_PAIR.match(s)
    if m_col:
        a = col_index(m_col.group(2))
        b = col_index(m_col.group(4))
        if 0 <= a < MAXC and 0 <= b < MAXC:
            return Token(
                t="ref",
                kind="cols",
                c1=a,
                c2=b,
                ca1=bool(m_col.group(1)),
                ca2=bool(m_col.group(3)),
                len=len(m_col.group(0)),
            )

    m = RE_CELL.match(s)
    if not m:
        return None
    c = col_index(m.group(2))
    r = int(m.group(4)) - 1
    if c >= MAXC or r < 0 or r >= MAXR:
        return None

    ca = bool(m.group(1))
    ra = bool(m.group(3))
    first_len = len(m.group(0))
    rest = s[first_len:]

    if rest.startswith(":"):
        m2 = RE_CELL.match(rest[1:])
        if m2:
            c2 = col_index(m2.group(2))
            r2 = int(m2.group(4)) - 1
            if 0 <= c2 < MAXC and 0 <= r2 < MAXR:
                return Token(
                    t="ref",
                    kind="area",
                    r1=r,
                    c1=c,
                    ra1=ra,
                    ca1=ca,
                    r2=r2,
                    c2=c2,
                    ra2=bool(m2.group(3)),
                    ca2=bool(m2.group(1)),
                    len=first_len + 1 + len(m2.group(0)),
                )

    return Token(
        t="ref",
        kind="cell",
        r=r,
        c=c,
        ra=ra,
        ca=ca,
        len=first_len,
    )


# ---------------------------------------------------------------- Tokenizer


def tokenize(src: str) -> list[Token]:
    """Tokenize a formula string into a list of Tokens."""
    toks: list[Token] = []
    i = 0
    n = len(src)

    def prev_significant() -> Token | None:
        for k in range(len(toks) - 1, -1, -1):
            if toks[k].t != "ws":
                return toks[k]
        return None

    def operand_ended() -> bool:
        p = prev_significant()
        if not p:
            return False
        return p.t in (
            "num",
            "str",
            "bool",
            "err",
            "ref",
            "name",
            "struct",
            "spill",
            ")",
            "}",
        ) or (p.t == "op" and p.v == "%")

    while i < n:
        ch = src[i]
        rest = src[i:]

        # Whitespace
        if ch in (" ", "\n", "\r", "\t", "\xa0"):
            j = i
            while j < n and src[j] in (" ", "\n", "\r", "\t", "\xa0"):
                j += 1
            toks.append(Token(t="ws", v=src[i:j], pos=i))
            i = j
            continue

        # String literal
        if ch == '"':
            j = i + 1
            s = ""
            while True:
                if j >= n:
                    raise ParseError("Missing closing quotation mark", i)
                if src[j] == '"':
                    if j + 1 < n and src[j + 1] == '"':
                        s += '"'
                        j += 2
                        continue
                    break
                s += src[j]
                j += 1
            toks.append(Token(t="str", v=s, pos=i))
            i = j + 1
            continue

        # # (spill or error code)
        if ch == "#":
            pv = toks[-1] if toks else None
            is_err = any(rest.upper().startswith(e) for e in ERRORS)
            if pv and pv.t in ("ref", "name") and not is_err:
                toks.append(Token(t="spill", pos=i))
                i += 1
                continue
            matched_err = next(
                (e for e in ERRORS if rest.upper().startswith(e)), None
            )
            if not matched_err:
                raise ParseError("Unknown error value", i)
            toks.append(Token(t="err", v=matched_err, pos=i))
            i += len(matched_err)
            continue

        # Parentheses, braces, commas, semicolons
        if ch in ("{", "}", "(", ")", ",", ";"):
            toks.append(Token(t=ch, pos=i))
            i += 1
            continue

        # Comparisons
        if ch in ("<", ">"):
            two = src[i : i + 2]
            if two in ("<=", ">=", "<>"):
                toks.append(Token(t="op", v=two, pos=i))
                i += 2
            else:
                toks.append(Token(t="op", v=ch, pos=i))
                i += 1
            continue

        # Operators
        if ch in "+-*/^&=%:@":
            toks.append(Token(t="op", v=ch, pos=i))
            i += 1
            continue

        # Structured table reference without table name: [@Col]
        if ch == "[" and not operand_ended() and not re.match(r"^\[[^\[\]]+\][^!\[\]]*!", rest):
            j = match_bracket(src, i)
            toks.append(Token(t="struct", table=None, spec=src[i : j + 1], pos=i))
            i = j + 1
            continue

        # External workbook / sheet qualifier
        book: str | None = None
        sheet_txt: str | None = None
        j0 = i
        if ch == "[":
            j = src.find("]", i)
            if j > i:
                book = src[i + 1 : j]
                j0 = j + 1

        r2 = src[j0:]
        if r2.startswith("'"):
            j = j0 + 1
            s = ""
            while True:
                if j >= n:
                    raise ParseError("Missing closing quote in sheet name", i)
                if src[j] == "'":
                    if j + 1 < n and src[j + 1] == "'":
                        s += "'"
                        j += 2
                        continue
                    break
                s += src[j]
                j += 1
            if j + 1 >= n or src[j + 1] != "!":
                raise ParseError("Expected ! after sheet name", j)
            sheet_txt = s
            j0 = j + 2
        else:
            m_unq = RE_SHEET_UNQ.match(r2)
            if m_unq:
                sheet_txt = m_unq.group(1)
                j0 += len(m_unq.group(0))

        if sheet_txt is not None or book is not None:
            if sheet_txt is not None and book is None:
                bm = re.match(r"^(?:.*[\\/])?\[([^\]]+)\](.*)$", sheet_txt)
                if bm:
                    book = bm.group(1)
                    sheet_txt = bm.group(2)
            sheet = sheet_txt
            sheet2 = None
            if sheet_txt is not None:
                k_3d = split_sheet_3d(sheet_txt)
                if k_3d:
                    sheet, sheet2 = k_3d

            after = src[j0:]
            tok = ref_token(after)
            if tok:
                tok.sheet = sheet
                tok.sheet2 = sheet2
                tok.book = book
                tok.pos = i
                toks.append(tok)
                i = j0 + tok.len
                continue

            if after.upper().startswith("#REF!"):
                toks.append(
                    Token(
                        t="ref",
                        kind="err",
                        sheet=sheet,
                        sheet2=sheet2,
                        book=book,
                        pos=i,
                    )
                )
                i = j0 + 5
                continue

            im = RE_IDENT.match(after)
            if im:
                toks.append(
                    Token(
                        t="name",
                        v=im.group(0),
                        sheet=sheet,
                        sheet2=sheet2,
                        book=book,
                        pos=i,
                    )
                )
                i = j0 + len(im.group(0))
                continue

            raise ParseError("Invalid reference", i)

        # Standalone reference
        rt = ref_token(rest)
        if rt:
            rt.pos = i
            toks.append(rt)
            i += rt.len
            continue

        if ch == "!":
            bt = ref_token(rest[1:])
            if bt:
                bt.pos = i
                bt.bang = True
                bt.len += 1
                toks.append(bt)
                i += bt.len
                continue

        # Number literal
        nm = RE_NUM.match(rest)
        if nm:
            raw_str = nm.group(0)
            num_val = float(raw_str) if ("." in raw_str or "e" in raw_str.lower()) else int(raw_str)
            toks.append(Token(t="num", v=num_val, raw=raw_str, pos=i))
            i += len(raw_str)
            continue

        # Identifier, function call, boolean, or structured ref with table
        im = RE_IDENT.match(rest)
        if im:
            id_str = im.group(0)
            k = i + len(id_str)
            if k < n and src[k] == "(":
                toks.append(Token(t="fn", v=id_str, pos=i))
                i = k
                continue
            if k < n and src[k] == "[":
                j = match_bracket(src, k)
                toks.append(
                    Token(
                        t="struct",
                        table=id_str,
                        spec=src[k : j + 1],
                        pos=i,
                    )
                )
                i = j + 1
                continue

            up = id_str.upper()
            if up in ("TRUE", "FALSE"):
                toks.append(Token(t="bool", v=(up == "TRUE"), pos=i))
                i = k
                continue

            toks.append(Token(t="name", v=id_str, pos=i))
            i = k
            continue

        raise ParseError(f"Unexpected character {ch}", i)

    return toks


# ---------------------------------------------------------------- Pratt Parser


def parse(text: str, opts: dict[str, Any] | None = None) -> ASTNode:
    """Parse Excel formula text (with or without leading '=') into an ASTNode."""
    formula_text = str(text).strip()
    if formula_text.startswith("="):
        formula_text = formula_text[1:]

    toks = tokenize(formula_text)
    sig_toks = [t for t in toks if t.t != "ws"]
    if not sig_toks:
        raise ParseError("Empty formula", 0)

    p = 0

    def peek() -> Token | None:
        nonlocal p
        while p < len(toks) and toks[p].t == "ws":
            p += 1
        return toks[p] if p < len(toks) else None

    def peek_raw() -> Token | None:
        return toks[p] if p < len(toks) else None

    def next_tok() -> Token:
        t = peek()
        nonlocal p
        p += 1
        return t  # type: ignore[return-value]

    def expect(t_type: str) -> Token:
        k = next_tok()
        if not k or k.t != t_type:
            pos = k.pos if k else len(formula_text)
            raise ParseError(f"Expected {t_type}", pos)
        return k

    def starts_operand(t: Token | None) -> bool:
        if not t:
            return False
        return (
            t.t in ("num", "str", "bool", "err", "ref", "name", "fn", "(", "{", "struct")
            or (t.t == "op" and t.v in ("-", "+", "@"))
        )

    def ref_node(t: Token) -> ASTNode:
        if t.kind == "err":
            return RefErrNode(
                sheet=t.sheet,
                sheet2=t.sheet2,
                book=t.book,
                bang=t.bang,
            )
        if t.kind == "cell":
            return CellRefNode(
                r=t.r,
                c=t.c,
                ra=t.ra,
                ca=t.ca,
                sheet=t.sheet,
                sheet2=t.sheet2,
                book=t.book,
                bang=t.bang,
            )
        if t.kind == "area":
            return AreaRefNode(
                r1=t.r1,
                c1=t.c1,
                r2=t.r2,
                c2=t.c2,
                ra1=t.ra1,
                ca1=t.ca1,
                ra2=t.ra2,
                ca2=t.ca2,
                sheet=t.sheet,
                sheet2=t.sheet2,
                book=t.book,
                bang=t.bang,
            )
        if t.kind == "cols":
            return AreaRefNode(
                kind="cols",
                r1=0,
                r2=MAXR - 1,
                c1=t.c1,
                c2=t.c2,
                ca1=t.ca1,
                ca2=t.ca2,
                ra1=True,
                ra2=True,
                sheet=t.sheet,
                sheet2=t.sheet2,
                book=t.book,
                bang=t.bang,
            )
        if t.kind == "rows":
            return AreaRefNode(
                kind="rows",
                c1=0,
                c2=MAXC - 1,
                r1=t.r1,
                r2=t.r2,
                ra1=t.ra1,
                ra2=t.ra2,
                ca1=True,
                ca2=True,
                sheet=t.sheet,
                sheet2=t.sheet2,
                book=t.book,
                bang=t.bang,
            )
        raise ParseError("Bad reference", t.pos)

    def call_args() -> list[ASTNode]:
        args: list[ASTNode] = []
        k = peek()
        if k and k.t == ")":
            next_tok()
            return args
        while True:
            k = peek()
            if k and k.t in (",", ")"):
                args.append(LiteralNode(t="missing"))
            else:
                args.append(expr(0, allow_union=False))
            k = next_tok()
            if not k:
                raise ParseError("Missing )", len(formula_text))
            if k.t == ")":
                break
            if k.t != ",":
                raise ParseError("Expected , or )", k.pos)
            k2 = peek()
            if k2 and k2.t == ")":
                args.append(LiteralNode(t="missing"))
                next_tok()
                break
        return args

    def primary(allow_union: bool) -> ASTNode:
        t = next_tok()
        if not t:
            raise ParseError("Formula is incomplete", len(formula_text))

        if t.t == "num":
            return LiteralNode(t="num", v=t.v)
        if t.t == "str":
            return LiteralNode(t="str", v=t.v)
        if t.t == "bool":
            return LiteralNode(t="bool", v=t.v)
        if t.t == "err":
            return LiteralNode(t="err", v=t.v)
        if t.t == "ref":
            return ref_node(t)
        if t.t == "struct":
            return StructuredRefNode(table=t.table, spec=t.spec or "", sheet=t.sheet)
        if t.t == "name":
            nm = re.sub(r"^_xlpm\.", "", str(t.v), flags=re.IGNORECASE)
            return NameNode(name=nm, sheet=t.sheet, book=t.book)
        if t.t == "fn":
            raw = str(t.v)
            udf = bool(re.match(r"^_xludf\.", raw, re.IGNORECASE))
            name = re.sub(
                r"^(_xlfn\.|_xlws\.|_xludf\.)", "", raw, flags=re.IGNORECASE
            ).upper()
            expect("(")
            node: ASTNode = FunctionCallNode(
                name=raw[7:] if udf else name,
                args=call_args(),
                raw=raw,
                udf=udf,
            )
            # Immediately invoked lambda
            while peek_raw() and peek_raw().t == "(":  # type: ignore[union-attr]
                next_tok()
                node = InvokeNode(fn=node, args=call_args())
            return node
        if t.t == "(":
            e = expr(0, allow_union=True)
            items = [e]
            k = peek()
            while k and k.t == ",":
                next_tok()
                items.append(expr(0, allow_union=True))
                k = peek()
            expect(")")
            return ParenNode(a=UnionNode(items=items) if len(items) > 1 else e)
        if t.t == "{":
            rows: list[list[ASTNode]] = [[]]
            while True:
                k = next_tok()
                neg = False
                if k and k.t == "op" and k.v in ("-", "+"):
                    neg = k.v == "-"
                    k = next_tok()
                if not k:
                    raise ParseError("Missing }", len(formula_text))
                if k.t in (",", ";", "}") and not neg:
                    rows[-1].append(LiteralNode(t="missing"))
                    if k.t == "}":
                        break
                    if k.t == ";":
                        rows.append([])
                    continue
                v: ASTNode
                if k.t == "num":
                    v = LiteralNode(t="num", v=-k.v if neg else k.v)
                elif k.t == "str":
                    v = LiteralNode(t="str", v=k.v)
                elif k.t == "bool":
                    v = LiteralNode(t="bool", v=k.v)
                elif k.t == "err":
                    v = LiteralNode(t="err", v=k.v)
                else:
                    raise ParseError(
                        "Array constants can contain only numbers, text, logical values and errors",
                        k.pos,
                    )
                rows[-1].append(v)
                k = next_tok()
                if not k:
                    raise ParseError("Missing }", len(formula_text))
                if k.t == "}":
                    break
                if k.t == ",":
                    continue
                if k.t == ";":
                    rows.append([])
                    continue
                raise ParseError("Unexpected item in array constant", k.pos)

            w = len(rows[0])
            if any(len(r) != w for r in rows):
                raise ParseError(
                    "Array constant rows must have the same length", t.pos
                )
            return ArrayNode(rows=rows)
        if t.t == "op":
            if t.v in ("-", "+", "@"):
                return UnaryOpNode(
                    op=t.v,
                    a=expr(UNARY_PREC, allow_union=allow_union),
                )
            raise ParseError(f"Unexpected operator {t.v}", t.pos)

        raise ParseError(f"Unexpected {t.t}", t.pos)

    def is_ref_like(n: ASTNode | None) -> bool:
        if not n:
            return False
        return (
            isinstance(
                n,
                (
                    CellRefNode,
                    AreaRefNode,
                    NameNode,
                    ParenNode,
                    FunctionCallNode,
                    StructuredRefNode,
                ),
            )
            or (isinstance(n, BinaryOpNode) and n.op in (":", " "))
        )

    def expr(min_prec: int, allow_union: bool = False) -> ASTNode:
        nonlocal p
        left = primary(allow_union)
        while True:
            # Intersection: whitespace followed by reference operand
            raw = peek_raw()
            if raw and raw.t == "ws":
                save = p
                p += 1
                nx = peek_raw()
                if (
                    nx
                    and starts_operand(nx)
                    and nx.t != "op"
                    and BIN_PREC[" "] >= min_prec
                ):
                    if is_ref_like(left) and (
                        nx.t in ("ref", "name", "(", "fn", "struct")
                    ):
                        right = expr(BIN_PREC[" "] + 1, allow_union)
                        left = BinaryOpNode(op=" ", left=left, right=right)
                        continue
                p = save

            t = peek()
            if not t:
                break
            if t.t == "spill":
                next_tok()
                left = FunctionCallNode(
                    name="ANCHORARRAY",
                    args=[left],
                    raw="_xlfn.ANCHORARRAY",
                )
                continue
            if t.t == "op" and t.v == "%":
                if PCT_PREC < min_prec:
                    break
                next_tok()
                left = PercentNode(a=left)
                continue
            if t.t != "op":
                break

            prec = BIN_PREC.get(t.v)
            if prec is None or prec < min_prec:
                break
            next_tok()
            # Left associative: climb with prec + 1
            right = expr(prec + 1, allow_union)
            left = BinaryOpNode(op=t.v, left=left, right=right)

        return left

    ast = expr(0, allow_union=False)
    rest = peek()
    if rest:
        msg = (
            "Too many closing parentheses"
            if rest.t == ")"
            else "Unexpected text after the formula"
        )
        raise ParseError(msg, rest.pos)

    mark_params(ast)
    return ast


def mark_params(ast: ASTNode) -> None:
    """Mark LET/LAMBDA parameter names with param=True for file storage."""

    def visitor(n: ASTNode) -> None:
        if not isinstance(n, FunctionCallNode) or n.name not in ("LET", "LAMBDA"):
            return
        params: set[str] = set()
        last = len(n.args) - 1
        for i, a in enumerate(n.args):
            if isinstance(a, NameNode):
                if (n.name == "LET" and i % 2 == 0 and i < last) or (
                    n.name == "LAMBDA" and i < last
                ):
                    params.add(a.name.upper())

        def inner(k: ASTNode) -> None:
            if isinstance(k, NameNode) and k.sheet is None and k.name.upper() in params:
                k.param = True

        walk(n, inner)

    walk(ast, visitor)


def try_parse(
    text: str, opts: dict[str, Any] | None = None
) -> tuple[ASTNode | None, Exception | None]:
    """Safe formula parser returning (ast, None) or (None, error)."""
    try:
        return (parse(text, opts), None)
    except Exception as e:
        return (None, e)


# ---------------------------------------------------------------- Serializer


def fmt_num(v: float | int) -> str:
    """Format number according to Excel standards."""
    a = abs(v)
    if a != 0 and (a >= 1e15 or a < 1e-5):
        return f"{v:E}".upper()
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)


def sheet_prefix(
    n: CellRefNode | AreaRefNode | RefErrNode | NameNode, opts: dict[str, Any]
) -> str:
    """Generate sheet prefix (e.g. 'Sheet 1'!, [Book.xlsx]Sheet1!)."""
    bang = getattr(n, "bang", False)
    sheet = getattr(n, "sheet", None)
    sheet2 = getattr(n, "sheet2", None)
    book = getattr(n, "book", None)

    if bang and sheet is None:
        return "!"
    if sheet is None and book is None:
        return ""
    book_part = f"[{book}]" if book is not None else ""
    if sheet is None:
        return f"{book_part}!"
    s = f"{sheet}:{sheet2}" if sheet2 else sheet
    q = (
        quote_sheet(sheet) != sheet
        or (sheet2 and quote_sheet(sheet2) != sheet2)
        or (book and bool(re.search(r"[^A-Za-z0-9_.]", book)))
    )
    if q:
        escaped = (book_part + s).replace("'", "''")
        return f"'{escaped}'!"
    return f"{book_part}{s}!"


def ref_text(n: CellRefNode | AreaRefNode | RefErrNode, opts: dict[str, Any]) -> str:
    """Format reference node into text representation."""
    pre = sheet_prefix(n, opts)
    if isinstance(n, RefErrNode):
        return f"{pre}#REF!"
    if isinstance(n, CellRefNode):
        return f"{pre}{cell_name(n.r, n.c, n.ra, n.ca)}"
    if isinstance(n, AreaRefNode):
        if n.kind == "cols":
            c1_str = f"{'$' if n.ca1 else ''}{col_name(n.c1)}"
            c2_str = f"{'$' if n.ca2 else ''}{col_name(n.c2)}"
            return f"{pre}{c1_str}:{c2_str}"
        if n.kind == "rows":
            r1_str = f"{'$' if n.ra1 else ''}{n.r1 + 1}"
            r2_str = f"{'$' if n.ra2 else ''}{n.r2 + 1}"
            return f"{pre}{r1_str}:{r2_str}"
        c1 = cell_name(n.r1, n.c1, n.ra1, n.ca1)
        c2 = cell_name(n.r2, n.c2, n.ra2, n.ca2)
        return f"{pre}{c1}:{c2}"
    return ""


def to_text(node: ASTNode, store: bool = False) -> str:
    """Convert AST node back to formula text (without leading '=')."""
    opts = {"store": store}

    def t(x: ASTNode) -> str:
        return to_text(x, store=store)

    if isinstance(node, LiteralNode):
        if node.t == "num":
            return fmt_num(node.v)
        if node.t == "str":
            escaped = str(node.v).replace('"', '""')
            return f'"{escaped}"'
        if node.t == "bool":
            return "TRUE" if node.v else "FALSE"
        if node.t == "err":
            return str(node.v)
        if node.t == "missing":
            return ""
        return str(node.v)

    if isinstance(node, (CellRefNode, AreaRefNode, RefErrNode)):
        return ref_text(node, opts)

    if isinstance(node, NameNode):
        pre = (
            sheet_prefix(node, opts)
            if (node.sheet is not None or node.book is not None)
            else ""
        )
        param_pre = "_xlpm." if (store and node.param) else ""
        return f"{pre}{param_pre}{node.name}"

    if isinstance(node, StructuredRefNode):
        table_part = node.table or ""
        return f"{table_part}{node.spec}"

    if isinstance(node, FunctionCallNode):
        if (
            not store
            and node.name == "ANCHORARRAY"
            and len(node.args) == 1
            and isinstance(node.args[0], (CellRefNode, NameNode, AreaRefNode))
        ):
            return f"{t(node.args[0])}#"
        if not store and node.name == "SINGLE" and len(node.args) == 1:
            return f"@{t(node.args[0])}"
        if node.udf:
            prefix = "_xludf." if store else ""
            args_str = ",".join(t(a) for a in node.args)
            return f"{prefix}{node.name}({args_str})"

        fn_name = (
            (
                node.raw
                if (node.raw and node.raw.startswith("_xl") and node.name not in FUTURE)
                else store_name(node.name)
            )
            if store
            else node.name
        )
        args_str = ",".join(t(a) for a in node.args)
        return f"{fn_name}({args_str})"

    if isinstance(node, InvokeNode):
        fn_str = t(node.fn) if node.fn else ""
        args_str = ",".join(t(a) for a in node.args)
        return f"{fn_str}({args_str})"

    if isinstance(node, ParenNode):
        child = node.a or node.operand
        return f"({t(child)})" if child else "()"

    if isinstance(node, UnionNode):
        return ",".join(t(item) for item in node.items)

    if isinstance(node, UnaryOpNode):
        child = node.a or node.operand
        child_str = t(child) if child else ""
        if node.op == "@" and store:
            return f"_xlfn.SINGLE({child_str})"
        return f"{node.op}{child_str}"

    if isinstance(node, PercentNode):
        child = node.a or node.operand
        child_str = t(child) if child else ""
        return f"{child_str}%"

    if isinstance(node, BinaryOpNode):
        left_child = node.left or node.a
        right_child = node.right or node.b
        left_str = t(left_child) if left_child else ""
        right_str = t(right_child) if right_child else ""
        return f"{left_str}{node.op}{right_str}"

    if isinstance(node, ArrayNode):
        row_strs = [",".join(t(item) for item in row) for row in node.rows]
        return f"{{{';'.join(row_strs)}}}"

    return ""


# ---------------------------------------------------- Spacing-Preserving Rewrite


def display(text: str) -> str:
    """Rewrite formula text for display in the formula bar (e.g. A1#, @A1)."""
    return _rewrite(str(text), store=False)


def to_store(text: str) -> str:
    """Rewrite formula text for file storage with _xlfn./_xlpm. prefixes."""
    return _rewrite(str(text), store=True)


def _rewrite(text: str, store: bool) -> str:
    clean = text[1:] if text.startswith("=") else text
    try:
        toks = tokenize(clean)
    except Exception:
        return text

    params: set[str] | None = None
    if store:
        params = set()
        try:
            ast = parse(clean)

            def get_param(n: ASTNode) -> None:
                if isinstance(n, NameNode) and n.param:
                    params.add(n.name.upper())

            walk(ast, get_param)
        except Exception:
            pass

    def raw(k: int) -> str:
        nxt_pos = toks[k + 1].pos if k + 1 < len(toks) else len(clean)
        return clean[toks[k].pos : nxt_pos]

    out: list[str] = []
    skip: set[int] = set()

    for k in range(len(toks)):
        if k in skip:
            continue
        t = toks[k]
        r = raw(k)

        if t.t == "fn":
            bare = re.sub(r"^(_xlfn\.|_xlws\.)", "", str(t.v), flags=re.IGNORECASE)
            up = bare.upper()
            if re.match(r"^_xludf\.", str(t.v), re.IGNORECASE):
                out.append(t.v if store else t.v[7:])
                continue
            if not store and up == "ANCHORARRAY":
                if (
                    k + 3 < len(toks)
                    and toks[k + 1].t == "("
                    and toks[k + 2].t in ("ref", "name")
                    and toks[k + 3].t == ")"
                ):
                    out.append(raw(k + 2).strip() + "#")
                    skip.update({k + 1, k + 2, k + 3})
                    continue
            if not store and up == "SINGLE" and k + 1 < len(toks) and toks[k + 1].t == "(":
                depth = 0
                m_end = -1
                simple = True
                for q in range(k + 1, len(toks)):
                    tq = toks[q]
                    if tq.t in ("(", "fn", "{"):
                        if tq.t != "fn":
                            depth += 1
                        continue
                    if tq.t in (")", "}"):
                        depth -= 1
                        if depth == 0:
                            m_end = q
                            break
                        continue
                    if depth == 1 and tq.t in ("op", ",", "sep"):
                        simple = False
                if m_end > 0:
                    if simple:
                        out.append("@")
                        skip.add(m_end)
                        skip.add(k + 1)
                    else:
                        out.append("@(")
                        skip.add(k + 1)
                    continue

            out.append(store_name(up) if store else up)
            continue

        if t.t == "spill":
            if not store:
                out.append("#")
            else:
                prev = out.pop() if out else ""
                out.append(f"_xlfn.ANCHORARRAY({prev})")
            continue

        if t.t == "ref":
            if t.kind == "err":
                out.append(re.sub(r"#ref!", "#REF!", r, flags=re.IGNORECASE))
            else:
                out.append(ref_text(ref_node_of(t), {}))
            continue

        if t.t == "name":
            bare = re.sub(r"^_xlpm\.", "", str(t.v), flags=re.IGNORECASE)
            pre = (
                sheet_prefix(CellRefNode(sheet=t.sheet, book=t.book), {})
                if (t.sheet is not None or t.book is not None)
                else ""
            )
            if store and params and bare.upper() in params and t.sheet is None:
                out.append(f"_xlpm.{bare}")
            else:
                out.append(f"{pre}{bare}")
            continue

        if t.t == "bool":
            out.append("TRUE" if t.v else "FALSE")
            continue

        if t.t == "err":
            out.append(str(t.v))
            continue

        out.append(r)

    prefix = "=" if text.startswith("=") else ""
    return prefix + "".join(out)


def ref_node_of(t: Token) -> CellRefNode | AreaRefNode:
    if t.kind == "cell":
        return CellRefNode(
            r=t.r,
            c=t.c,
            ra=t.ra,
            ca=t.ca,
            sheet=t.sheet,
            sheet2=t.sheet2,
            book=t.book,
            bang=t.bang,
        )
    return AreaRefNode(
        r1=t.r1,
        c1=t.c1,
        r2=t.r2,
        c2=t.c2,
        ra1=t.ra1,
        ca1=t.ca1,
        ra2=t.ra2,
        ca2=t.ca2,
        sheet=t.sheet,
        sheet2=t.sheet2,
        book=t.book,
        kind=t.kind,
        bang=t.bang,
    )


def parse_sheet_reference(text: str) -> SheetReference | None:
    """Parse a sheet-qualified reference string into a SheetReference AST node.

    Handles single-quoted sheet names with escaped quotes (e.g. 'O''Reilly'!A1)
    and unquoted sheet names (e.g. Sheet2!B5:C10).
    """
    clean = text.strip()
    if clean.startswith("="):
        clean = clean[1:].strip()
    if "!" not in clean:
        return None

    sheet_name: str
    cell_range: str

    if clean.startswith("'"):
        # Quoted sheet name
        j = 1
        n = len(clean)
        s = ""
        while j < n:
            if clean[j] == "'":
                if j + 1 < n and clean[j + 1] == "'":
                    s += "'"
                    j += 2
                    continue
                break
            s += clean[j]
            j += 1
        if j >= n or j + 1 >= n or clean[j + 1] != "!":
            return None
        sheet_name = s
        cell_range = clean[j + 2 :].strip()
    else:
        # Unquoted sheet name
        parts = clean.split("!", 1)
        sheet_name = parts[0].strip()
        cell_range = parts[1].strip()

    if not sheet_name or not cell_range:
        return None

    return SheetReference(sheet_name=sheet_name, cell_range=cell_range)
