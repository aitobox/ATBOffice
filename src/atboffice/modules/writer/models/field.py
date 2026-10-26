"""Word 2003 / Quire dynamic field instruction parser, evaluator, and bookmark manager.

Supports:
- Field instructions: PAGE, NUMPAGES, SECTIONPAGES, SECTION, DATE, TIME,
  CREATEDATE, SAVEDATE, TITLE, AUTHOR, FILENAME, PAGEREF, STYLEREF, TOC, etc.
- Switches: \\* (general formatting), \\# (number pictures), \\@ (date pictures),
  and field-specific switches (\\o, \\h, \\u, \\n, \\p, etc.).
- Bookmarks: creation, lookup, text extraction, and paragraph anchor bookmarks.
- Dynamic field updates and pagination backfill.
"""

from __future__ import annotations

import datetime
import math
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from atboffice.modules.writer.models.document import (
    BookmarkEndItem,
    BookmarkStartItem,
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    RunItem,
    Story,
    TextItem,
    ilen,
    plen,
)
from atboffice.modules.writer.models.properties import RunProperties

if TYPE_CHECKING:
    from atboffice.modules.writer.layout.pagination import PaginationResult

# ---------------------------------------------------------------------------
# Number Formatting Utilities
# ---------------------------------------------------------------------------

_ROMAN_VALS = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
_ROMAN_SYBS = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]

_CARDINALS = [
    (1000000000, "billion"),
    (1000000, "million"),
    (1000, "thousand"),
    (100, "hundred"),
    (90, "ninety"),
    (80, "eighty"),
    (70, "seventy"),
    (60, "sixty"),
    (50, "fifty"),
    (40, "forty"),
    (30, "thirty"),
    (20, "twenty"),
    (19, "nineteen"),
    (18, "eighteen"),
    (17, "seventeen"),
    (16, "sixteen"),
    (15, "fifteen"),
    (14, "fourteen"),
    (13, "thirteen"),
    (12, "twelve"),
    (11, "eleven"),
    (10, "ten"),
    (9, "nine"),
    (8, "eight"),
    (7, "seven"),
    (6, "six"),
    (5, "five"),
    (4, "four"),
    (3, "three"),
    (2, "two"),
    (1, "one"),
    (0, "zero"),
]

_ORDINALS_SPECIAL = {
    "zero": "zeroth",
    "one": "first",
    "two": "second",
    "three": "third",
    "four": "fourth",
    "five": "fifth",
    "eight": "eighth",
    "nine": "ninth",
    "twelve": "twelfth",
    "twenty": "twentieth",
    "thirty": "thirtieth",
    "forty": "fortieth",
    "fifty": "fiftieth",
    "sixty": "sixtieth",
    "seventy": "seventieth",
    "eighty": "eightieth",
    "ninety": "ninetieth",
}


def _to_roman(n: int) -> str:
    if n <= 0:
        return ""
    res: list[str] = []
    i = 0
    while n > 0 and i < len(_ROMAN_VALS):
        for _ in range(n // _ROMAN_VALS[i]):
            res.append(_ROMAN_SYBS[i])
            n -= _ROMAN_VALS[i]
        i += 1
    return "".join(res)


def _to_letters(n: int, lowercase: bool = False) -> str:
    if n <= 0:
        return ""
    base = 97 if lowercase else 65
    repeats = (n - 1) // 26 + 1
    char = chr(base + ((n - 1) % 26))
    return char * repeats


def _ordinal_suffix(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return "th"
    last = n % 10
    if last == 1:
        return "st"
    if last == 2:
        return "nd"
    if last == 3:
        return "rd"
    return "th"


def _cardinal_text(n: int) -> str:
    if n < 0:
        return f"minus {_cardinal_text(-n)}"
    if n == 0:
        return "zero"
    words: list[str] = []
    for val, name in _CARDINALS:
        if val == 0:
            continue
        if n >= val:
            count = n // val
            if val >= 100:
                words.append(f"{_cardinal_text(count)} {name}")
            else:
                words.append(name)
            rem = n % val
            if rem > 0:
                if val == 100 or val >= 1000:
                    words.append(f"and {_cardinal_text(rem)}")
                elif val >= 20:
                    words.append(f"-{_cardinal_text(rem)}")
            return " ".join(words).replace(" -", "-")
    return " ".join(words)


def _ordinal_text(n: int) -> str:
    card = _cardinal_text(n)
    parts = card.rsplit(" ", 1)
    last_word = parts[-1]
    if "-" in last_word:
        subparts = last_word.rsplit("-", 1)
        sub_ord = _ORDINALS_SPECIAL.get(subparts[1], subparts[1] + "th")
        ord_last = f"{subparts[0]}-{sub_ord}"
    else:
        ord_last = _ORDINALS_SPECIAL.get(last_word, last_word + "th")
    if len(parts) > 1:
        return f"{parts[0]} {ord_last}"
    return ord_last


# ---------------------------------------------------------------------------
# Instruction Tokenizer & Parser
# ---------------------------------------------------------------------------


@dataclass
class FieldToken:
    """Token produced from field instruction string."""

    v: str = ""
    q: bool = False  # Quoted string
    sw: str = ""  # Switch prefix (e.g. "\o", "\*", "\#", "\@")


@dataclass
class FieldInstruction:
    """Structured AST representation of parsed field instruction."""

    type: str = ""
    args: list[str] = field(default_factory=list)
    sw: dict[str, str | bool] = field(default_factory=dict)
    fmt: list[str] = field(default_factory=list)
    expr: str = ""


_ARGSW: dict[str, str] = {
    "TOC": "abcdflpst",
    "INDEX": "bcdefghklps",
    "REF": "d",
    "SEQ": "rs",
    "XE": "frty",
    "TC": "fl",
    "MERGEFIELD": "bf",
    "HYPERLINK": "lot",
    "SYMBOL": "fs",
    "INCLUDEPICTURE": "c",
    "FILLIN": "d",
    "ASK": "d",
    "NOTEREF": "",
    "PAGEREF": "",
    "STYLEREF": "",
    "DATE": "",
    "TIME": "",
    "PAGE": "",
    "NUMPAGES": "",
    "AUTHOR": "",
    "TITLE": "",
    "FILENAME": "",
}
_OPTARG: dict[str, str] = {"TOC": "no"}


def tokenize_field_instruction(instr: str) -> list[FieldToken]:
    """Tokenize a field instruction honoring quoted strings and switch prefixes."""
    out: list[FieldToken] = []
    # Pattern: "quoted" | \switch | bareword
    pattern = re.compile(r'\s*(?:"((?:[^"\\]|\\.)*)"|(\\[*#@!]|\\\w+)|([^\s"]+))')
    s = str(instr or "").strip()
    for m in pattern.finditer(s):
        if m.group(1) is not None:
            # Quoted string
            val = m.group(1).replace(r'\"', '"').replace(r"\\", "\\")
            out.append(FieldToken(v=val, q=True))
        elif m.group(2) is not None:
            # Switch
            out.append(FieldToken(sw=m.group(2)))
        elif m.group(3) is not None:
            # Normal token
            out.append(FieldToken(v=m.group(3)))
    return out


def parse_field_instruction(instr: str) -> FieldInstruction:
    """Parse field instruction string into structured FieldInstruction AST."""
    toks = tokenize_field_instruction(instr)
    res = FieldInstruction()
    if not toks:
        return res

    first = toks.pop(0)
    first_val = first.v or ""
    if first_val.startswith("="):
        res.type = "="
        expr_raw = str(instr).strip().lstrip("=").strip()
        res.expr = re.sub(r"\\[#*].*$", "", expr_raw).strip()
    else:
        res.type = first_val.upper()

    arg_sw = _ARGSW.get(res.type)
    opt_sw = _OPTARG.get(res.type, "")

    i = 0
    while i < len(toks):
        t = toks[i]
        if t.sw:
            k = t.sw
            letter = k[1:].lower() if len(k) > 1 else ""
            nx = toks[i + 1] if i + 1 < len(toks) else None

            if k == r"\*":
                # General formatting switch
                if nx and nx.v:
                    res.fmt.append(nx.v)
                    i += 1
                i += 1
                continue

            takes_arg = False
            if k in (r"\#", r"\@"):
                takes_arg = nx is not None and bool(nx.v)
            elif not nx or bool(nx.sw):
                takes_arg = False
            elif arg_sw is not None:
                takes_arg = (letter in arg_sw) or (letter in opt_sw and nx.q)
            else:
                takes_arg = bool(nx.q)

            if takes_arg and nx is not None:
                res.sw[k] = nx.v
                i += 1
            else:
                res.sw[k] = True
        elif res.type != "=":
            res.args.append(t.v)
        i += 1

    return res


# ---------------------------------------------------------------------------
# Formatting Switches & Date Picture Formatting
# ---------------------------------------------------------------------------

_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
_DAYS = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]


def format_field_date(dt: datetime.datetime, pic: str | None = None) -> str:
    """Format datetime using Word date-time picture specification."""
    if not pic:
        pic = "M/d/yyyy"
    pic = pic.strip('"')

    pattern = re.compile(
        r"'([^']*)'|(dddd|ddd|dd|d|MMMM|MMM|MM|M|yyyy|yy|HH|H|hh|h|mm|m|ss|s|am/pm|AM/PM|a/p|A/P)|([\s\S])"
    )

    out: list[str] = []
    h24 = dt.hour
    h12 = h24 % 12 or 12

    for m in pattern.finditer(pic):
        literal, token, char = m.group(1), m.group(2), m.group(3)
        if literal is not None:
            out.append(literal)
        elif char is not None:
            out.append(char)
        elif token is not None:
            if token == "dddd":
                out.append(_DAYS[dt.weekday()])
            elif token == "ddd":
                out.append(_DAYS[dt.weekday()][:3])
            elif token == "dd":
                out.append(f"{dt.day:02d}")
            elif token == "d":
                out.append(str(dt.day))
            elif token == "MMMM":
                out.append(_MONTHS[dt.month - 1])
            elif token == "MMM":
                out.append(_MONTHS[dt.month - 1][:3])
            elif token == "MM":
                out.append(f"{dt.month:02d}")
            elif token == "M":
                out.append(str(dt.month))
            elif token == "yyyy":
                out.append(f"{dt.year:04d}")
            elif token == "yy":
                out.append(f"{dt.year % 100:02d}")
            elif token == "HH":
                out.append(f"{h24:02d}")
            elif token == "H":
                out.append(str(h24))
            elif token == "hh":
                out.append(f"{h12:02d}")
            elif token == "h":
                out.append(str(h12))
            elif token == "mm":
                out.append(f"{dt.minute:02d}")
            elif token == "m":
                out.append(str(dt.minute))
            elif token == "ss":
                out.append(f"{dt.second:02d}")
            elif token == "s":
                out.append(str(dt.second))
            elif token == "am/pm":
                out.append("am" if h24 < 12 else "pm")
            elif token == "AM/PM":
                out.append("AM" if h24 < 12 else "PM")
            elif token == "a/p":
                out.append("a" if h24 < 12 else "p")
            elif token == "A/P":
                out.append("A" if h24 < 12 else "P")
            else:
                out.append(token)

    return "".join(out)


def apply_field_formatting(value: Any, fmt_switches: list[str]) -> str:
    """Apply Word formatting switches (\\* Upper, \\* Lower, \\* Roman, \\* Caps, etc.)."""
    s = str(value)
    for f in fmt_switches:
        k = str(f or "").strip().upper()
        if k in ("MERGEFORMAT", "CHARFORMAT"):
            continue
        if k == "UPPER":
            s = s.upper()
        elif k == "LOWER":
            s = s.lower()
        elif k == "FIRSTCAP":
            s = s.capitalize()
        elif k == "CAPS":
            s = s.title()
        else:
            # Numeric formats
            try:
                clean_num = s.replace(",", "").strip()
                n = float(clean_num)
                int_n = int(math.floor(n))
                if f == "roman":
                    s = _to_roman(int_n).lower()
                elif f == "ROMAN" or k == "ROMAN":
                    s = _to_roman(int_n)
                elif f == "alphabetic":
                    s = _to_letters(int_n, lowercase=True)
                elif f == "ALPHABETIC" or k == "ALPHABETIC":
                    s = _to_letters(int_n, lowercase=False)
                elif k == "ARABIC":
                    s = str(int_n)
                elif k == "ORDINAL":
                    s = f"{int_n}{_ordinal_suffix(int_n)}"
                elif k == "CARDTEXT":
                    s = _cardinal_text(int_n).lower()
                elif k == "ORDTEXT":
                    s = _ordinal_text(int_n).lower()
                elif k == "HEX":
                    s = hex(int_n)[2:].upper()
                elif k == "DOLLARTEXT":
                    w = int_n
                    cents = int(round((n - w) * 100))
                    s = f"{_cardinal_text(w).lower()} and {cents:02d}/100"
            except (ValueError, TypeError):
                pass
    return s


# ---------------------------------------------------------------------------
# Bookmark Extraction & Management
# ---------------------------------------------------------------------------


@dataclass
class BookmarkInfo:
    """Bookmark position and range metadata."""

    name: str
    bookmark_id: int
    p: Paragraph
    offset: int
    end_p: Paragraph | None = None
    end_offset: int = 0
    story: Story | None = None


def find_bookmarks(doc: Document) -> dict[str, BookmarkInfo]:
    """Locate all bookmarks defined in document stories."""
    out: dict[str, BookmarkInfo] = {}
    open_bms: dict[int, BookmarkInfo] = {}

    all_stories: list[Story] = [doc.main]
    all_stories.extend(doc.hf.values())
    all_stories.extend(doc.fn.values())
    all_stories.extend(doc.en.values())

    for st in all_stories:
        for p in st.paras:
            o = 0
            for it in p.runs:
                if isinstance(it, BookmarkStartItem) and it.name:
                    b_info = BookmarkInfo(
                        name=it.name,
                        bookmark_id=it.bookmark_id,
                        p=p,
                        offset=o,
                        story=st,
                    )
                    out[it.name] = b_info
                    open_bms[it.bookmark_id] = b_info
                elif isinstance(it, BookmarkEndItem) and it.bookmark_id in open_bms:
                    b_info = open_bms.pop(it.bookmark_id)
                    b_info.end_p = p
                    b_info.end_offset = o
                o += ilen(it)

    # For bookmarks without explicit end marker, set end to start
    for b in out.values():
        if b.end_p is None:
            b.end_p = b.p
            b.end_offset = b.offset

    return out


def bookmark_text(doc: Document, name: str) -> str | None:
    """Extract plain text covered by a bookmark."""
    bms = find_bookmarks(doc)
    b = bms.get(name)
    if not b or not b.end_p:
        return None

    if b.p == b.end_p:
        from atboffice.modules.writer.models.document import ptext

        return ptext(b.p, b.offset, b.end_offset)

    # Cross-paragraph bookmark text
    parts: list[str] = []
    st = b.story or doc.main
    collecting = False
    for p in st.paras:
        if p == b.p:
            collecting = True
            from atboffice.modules.writer.models.document import ptext

            parts.append(ptext(p, b.offset, None))
        elif p == b.end_p:
            from atboffice.modules.writer.models.document import ptext

            parts.append(ptext(p, 0, b.end_offset))
            break
        elif collecting:
            from atboffice.modules.writer.models.document import ptext

            parts.append(ptext(p))

    return " ".join(parts)


def add_bookmark(
    doc: Document,
    name: str,
    start_p: Paragraph,
    start_offset: int,
    end_p: Paragraph,
    end_offset: int,
) -> int:
    """Add or replace a bookmark around a paragraph text range."""
    # Remove existing bookmark of that name if present
    remove_bookmark(doc, name)

    from atboffice.modules.writer.models.document import _next_nid, split_at

    bm_id = _next_nid()

    ia = split_at(start_p, start_offset)
    start_p.runs.insert(ia, BookmarkStartItem(name=name, bookmark_id=bm_id))

    ib = split_at(end_p, end_offset)
    if start_p == end_p and ib <= ia:
        ib = ia + 1
    end_p.runs.insert(ib, BookmarkEndItem(bookmark_id=bm_id))

    return bm_id


def ensure_para_bookmark(doc: Document, p: Paragraph, prefix: str = "_Toc") -> str:
    """Ensure a hidden anchor bookmark exists around a paragraph (for TOC and links)."""
    for it in p.runs:
        if isinstance(it, BookmarkStartItem) and it.name and it.name.startswith(prefix):
            return it.name

    from atboffice.modules.writer.models.document import _next_nid

    bm_name = f"{prefix}{100000000 + _next_nid():08d}"
    add_bookmark(doc, bm_name, p, 0, p, plen(p))
    return bm_name


def remove_bookmark(doc: Document, name: str) -> bool:
    """Remove bookmark markers by name."""
    bms = find_bookmarks(doc)
    b = bms.get(name)
    if not b:
        return False

    target_id = b.bookmark_id
    for st in [doc.main, *doc.hf.values(), *doc.fn.values(), *doc.en.values()]:
        for p in st.paras:
            p.runs = [
                it
                for it in p.runs
                if not (
                    (isinstance(it, (BookmarkStartItem, BookmarkEndItem)))
                    and it.bookmark_id == target_id
                )
            ]
    return True


# ---------------------------------------------------------------------------
# Dynamic Field Evaluation & In-Paragraph Helpers
# ---------------------------------------------------------------------------


@dataclass
class FieldContext:
    """Contextual metadata provided to field evaluation."""

    page_number: int = 1
    total_pages: int = 1
    section_index: int = 0
    section_pages: int = 1
    page_number_format: str = "decimal"
    now: datetime.datetime | None = None
    file_name: str = "Document1.docx"


def evaluate_field(
    instr: str,
    doc: Document,
    ctx: FieldContext | None = None,
) -> str:
    """Evaluate a field instruction string and return its computed text representation."""
    if ctx is None:
        ctx = FieldContext()

    f = parse_field_instruction(instr)
    t = f.type
    now = ctx.now or datetime.datetime.now()

    def fmt(val: Any) -> str:
        return apply_field_formatting(val, f.fmt)

    def date_val(dt: datetime.datetime) -> str:
        pic = str(f.sw.get(r"\@") or ("h:mm am/pm" if t == "TIME" else "M/d/yyyy"))
        return fmt(format_field_date(dt, pic))

    if t in ("DATE", "TIME"):
        return date_val(now)
    if t == "CREATEDATE":
        created = doc.props.get("created")
        if isinstance(created, datetime.datetime):
            return date_val(created)
        return date_val(now)
    if t == "SAVEDATE":
        modified = doc.props.get("modified")
        if isinstance(modified, datetime.datetime):
            return date_val(modified)
        return date_val(now)
    if t == "PAGE":
        num_fmt = f.fmt[0] if f.fmt else ctx.page_number_format
        from atboffice.modules.writer.layout.pagination import format_number

        val_str = format_number(ctx.page_number, num_fmt)
        return fmt(val_str)
    if t == "NUMPAGES":
        num_fmt = f.fmt[0] if f.fmt else "decimal"
        from atboffice.modules.writer.layout.pagination import format_number

        val_str = format_number(ctx.total_pages, num_fmt)
        return fmt(val_str)
    if t == "SECTIONPAGES":
        from atboffice.modules.writer.layout.pagination import format_number

        val_str = format_number(ctx.section_pages, "decimal")
        return fmt(val_str)
    if t == "SECTION":
        return fmt(str(ctx.section_index + 1))
    if t == "TITLE":
        return fmt(doc.props.get("title") or "")
    if t == "AUTHOR":
        return fmt(doc.props.get("creator") or doc.props.get("author") or "")
    if t == "SUBJECT":
        return fmt(doc.props.get("subject") or "")
    if t == "KEYWORDS":
        return fmt(doc.props.get("keywords") or "")
    if t == "COMMENTS":
        return fmt(doc.props.get("description") or doc.props.get("comments") or "")
    if t == "FILENAME":
        return fmt(ctx.file_name)
    if t == "PAGEREF":
        target_name = f.args[0] if f.args else ""
        bms = find_bookmarks(doc)
        b = bms.get(target_name)
        if not b:
            return "Error! Bookmark not defined."
        # Locate page number of bookmark target
        target_page_num = 1
        if hasattr(doc, "_last_pagination") and doc._last_pagination:  # type: ignore[attr-defined]
            p_res: PaginationResult = doc._last_pagination  # type: ignore[attr-defined]
            for pg in p_res.pages:
                found = False
                for reg in pg.regions:
                    for col in reg.columns:
                        for fr in col.fragments:
                            if fr.paragraph == b.p:
                                target_page_num = pg.page_number
                                found = True
                                break
                        if found:
                            break
                    if found:
                        break
                if found:
                    break
        return fmt(str(target_page_num))
    if t == "STYLEREF":
        target_style = (f.args[0] if f.args else "").lower()
        for p in doc.main.paras:
            style_name = (p.p_pr.style or "Normal").lower()
            if style_name == target_style or (
                target_style in ("1", "2", "3") and style_name.endswith(target_style)
            ):
                from atboffice.modules.writer.models.document import plain_text

                return fmt(plain_text(p).strip())
        return "Error! No text of specified style in document."
    if t == "MERGEFIELD":
        engine = getattr(doc, "mailmerge_engine", None)
        if engine is not None:
            return engine.evaluate_merge_instruction(instr)
        field_name = f.args[0] if f.args else "Field"
        clean_name = field_name.replace("_", " ")
        return fmt(f"«{clean_name}»")
    if t in ("MERGEREC", "MERGESEQ"):
        engine = getattr(doc, "mailmerge_engine", None)
        if engine is not None:
            return fmt(str(engine.current_record + 1))
        return fmt("1")

    return ""


def insert_field(
    p: Paragraph,
    offset: int,
    field_type: str,
    instr: str,
    cached_text: str = "",
    r_pr: RunProperties | None = None,
) -> None:
    """Insert inline field construct [fb]...[fs]result[fe] into paragraph at offset."""
    from atboffice.modules.writer.models.document import split_at

    idx = split_at(p, offset)
    items: list[RunItem] = [
        FieldBeginItem(field_type=field_type, instr=instr, r_pr=r_pr),
        FieldSeparateItem(r_pr=r_pr),
        TextItem(text=cached_text, r_pr=r_pr),
        FieldEndItem(r_pr=r_pr),
    ]
    p.runs[idx:idx] = items


def update_fields(
    doc: Document,
    pagination_result: PaginationResult | None = None,
) -> bool:
    """Traverse all paragraphs and update dynamic fields with current document state.

    Returns True if any field's cached text was modified.
    """
    total_pages = pagination_result.total_pages if pagination_result else 1
    sec_pages_list = pagination_result.section_pages if pagination_result else [total_pages]

    # Map paragraph to (page_number, page_number_format, section_index)
    para_page_map: dict[int, tuple[int, str, int]] = {}
    if pagination_result:
        for pg in pagination_result.pages:
            all_frags = []
            if pg.header:
                all_frags.extend(pg.header.fragments)
            for reg in pg.regions:
                for col in reg.columns:
                    all_frags.extend(col.fragments)
            if pg.footer:
                all_frags.extend(pg.footer.fragments)
            for fr in all_frags:
                if fr.paragraph:
                    para_page_map[fr.paragraph.id] = (
                        pg.page_number,
                        pg.page_number_format,
                        pg.section_index,
                    )

    changed = False
    all_stories: list[Story] = [doc.main]
    all_stories.extend(doc.hf.values())
    all_stories.extend(doc.fn.values())
    all_stories.extend(doc.en.values())

    for st in all_stories:
        for p in st.paras:
            pg_info = para_page_map.get(p.id, (1, "decimal", 0))
            sec_idx = pg_info[2]
            sec_cnt = sec_pages_list[sec_idx] if sec_idx < len(sec_pages_list) else 1

            ctx = FieldContext(
                page_number=pg_info[0],
                total_pages=total_pages,
                section_index=sec_idx,
                section_pages=sec_cnt,
                page_number_format=pg_info[1],
            )

            # Look for fb...fs...fe groups in p.runs
            fb_idx = -1
            fs_idx = -1
            i = 0
            while i < len(p.runs):
                it = p.runs[i]
                if isinstance(it, FieldBeginItem):
                    fb_idx = i
                    fs_idx = -1
                elif isinstance(it, FieldSeparateItem) and fb_idx >= 0:
                    fs_idx = i
                elif isinstance(it, FieldEndItem) and fb_idx >= 0:
                    fb_item = p.runs[fb_idx]
                    instr = fb_item.instr or fb_item.field_type
                    eval_res = evaluate_field(instr, doc, ctx)

                    # Replace runs between fs and fe (or between fb and fe if no fs)
                    start_repl = (fs_idx + 1) if fs_idx >= 0 else (fb_idx + 1)
                    end_repl = i

                    old_text = "".join(
                        getattr(run, "text", "")
                        for run in p.runs[start_repl:end_repl]
                        if isinstance(run, TextItem)
                    )
                    if old_text != eval_res:
                        changed = True
                        p.runs[start_repl:end_repl] = [
                            TextItem(text=eval_res, r_pr=fb_item.r_pr)
                        ]
                        # Recalculate i
                        i = start_repl + 1

                    fb_idx = -1
                    fs_idx = -1
                i += 1

    return changed
