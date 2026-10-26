"""Core Document Object Model (DOM Tree) for Quire word processing module."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable

from atboffice.modules.writer.models.properties import (
    CellProperties,
    ParagraphProperties,
    RowProperties,
    RunProperties,
    SectionProperties,
    TableProperties,
)

_NID_COUNTER = 1


def _next_nid() -> int:
    global _NID_COUNTER
    nid = _NID_COUNTER
    _NID_COUNTER += 1
    return nid


@dataclass
class RunItem:
    """Base class for inline run items."""

    t: str
    r_pr: RunProperties = field(default_factory=RunProperties)


@dataclass
class TextItem(RunItem):
    """Inline text run."""

    text: str = ""

    def __init__(self, text: str = "", r_pr: RunProperties | None = None) -> None:
        super().__init__(t="text", r_pr=r_pr or RunProperties())
        self.text = text


@dataclass
class TabItem(RunItem):
    """Inline tab character."""

    def __init__(self, r_pr: RunProperties | None = None) -> None:
        super().__init__(t="tab", r_pr=r_pr or RunProperties())


@dataclass
class BreakItem(RunItem):
    """Inline line, page, or column break."""

    break_type: str = "line"  # "line", "page", "column"

    def __init__(self, break_type: str = "line", r_pr: RunProperties | None = None) -> None:
        super().__init__(t="br", r_pr=r_pr or RunProperties())
        self.break_type = break_type


@dataclass
class SymbolItem(RunItem):
    """Inline special symbol glyph."""

    font: str = "Symbol"
    char: str = ""

    def __init__(self, font: str = "Symbol", char: str = "", r_pr: RunProperties | None = None) -> None:
        super().__init__(t="sym", r_pr=r_pr or RunProperties())
        self.font = font
        self.char = char


@dataclass
class BookmarkStartItem(RunItem):
    """Bookmark start marker."""

    name: str = ""
    bookmark_id: int = 0

    def __init__(self, name: str = "", bookmark_id: int = 0, r_pr: RunProperties | None = None) -> None:
        super().__init__(t="bs", r_pr=r_pr or RunProperties())
        self.name = name
        self.bookmark_id = bookmark_id


@dataclass
class BookmarkEndItem(RunItem):
    """Bookmark end marker."""

    bookmark_id: int = 0

    def __init__(self, bookmark_id: int = 0, r_pr: RunProperties | None = None) -> None:
        super().__init__(t="be", r_pr=r_pr or RunProperties())
        self.bookmark_id = bookmark_id


@dataclass
class FieldBeginItem(RunItem):
    """Dynamic field begin marker."""

    field_type: str = ""
    instr: str = ""
    locked: bool = False

    def __init__(self, field_type: str = "", instr: str = "", locked: bool = False, r_pr: RunProperties | None = None) -> None:
        super().__init__(t="fb", r_pr=r_pr or RunProperties())
        self.field_type = field_type
        self.instr = instr
        self.locked = locked


@dataclass
class FieldSeparateItem(RunItem):
    """Dynamic field separator marker (dividing instruction from cached result)."""

    def __init__(self, r_pr: RunProperties | None = None) -> None:
        super().__init__(t="fs", r_pr=r_pr or RunProperties())


@dataclass
class FieldEndItem(RunItem):
    """Dynamic field end marker."""

    def __init__(self, r_pr: RunProperties | None = None) -> None:
        super().__init__(t="fe", r_pr=r_pr or RunProperties())


@dataclass
class CommentRangeStart(RunItem):
    """Comment annotation range start marker."""

    comment_id: str | int = 0

    def __init__(self, comment_id: str | int = 0, r_pr: RunProperties | None = None) -> None:
        super().__init__(t="cs", r_pr=r_pr or RunProperties())
        self.comment_id = comment_id


@dataclass
class CommentRangeEnd(RunItem):
    """Comment annotation range end marker."""

    comment_id: str | int = 0

    def __init__(self, comment_id: str | int = 0, r_pr: RunProperties | None = None) -> None:
        super().__init__(t="ce", r_pr=r_pr or RunProperties())
        self.comment_id = comment_id


def ilen(item: RunItem) -> int:
    """Character position length of an inline run item."""
    if item.t == "text":
        return len(getattr(item, "text", ""))
    if item.t in {"cs", "ce", "bs", "be", "fb", "fs", "fe", "perm", "sdts", "sdte"}:
        return 0
    return 1


@dataclass
class Paragraph:
    """Paragraph block containing formatted inline runs."""

    id: int = field(default_factory=_next_nid)
    runs: list[RunItem] = field(default_factory=list)
    p_pr: ParagraphProperties = field(default_factory=ParagraphProperties)
    r_pr: RunProperties = field(default_factory=RunProperties)
    sect: SectionProperties | None = None
    _o: int = 0  # Reading order index in story


def plen(p: Paragraph) -> int:
    """Total character length of a paragraph."""
    return sum(ilen(it) for it in p.runs)


def ptext(p: Paragraph, from_idx: int | None = None, to_idx: int | None = None) -> str:
    """Paragraph text with placeholders ('￼') for non-text objects and breaks."""
    buf: list[str] = []
    for it in p.runs:
        if it.t == "text":
            buf.append(it.text)
        elif it.t == "tab":
            buf.append("\t")
        elif it.t == "br":
            buf.append("\f" if getattr(it, "break_type", "") == "page" else "\v" if getattr(it, "break_type", "") == "column" else "\n")
        elif it.t == "sym":
            buf.append(getattr(it, "char", "") or "￼")
        elif ilen(it) > 0:
            buf.append("￼")
    full_str = "".join(buf)
    return full_str[from_idx:to_idx]


def plain_text(p: Paragraph, skip_deleted: bool = True) -> str:
    """Visible text without non-text object placeholders (used for search, word counts)."""
    buf: list[str] = []
    for it in p.runs:
        if it.t == "text":
            buf.append(it.text)
        elif it.t == "tab":
            buf.append("\t")
        elif it.t == "br":
            if getattr(it, "break_type", "line") == "line":
                buf.append("\n")
        elif it.t == "sym":
            buf.append(getattr(it, "char", ""))
    return "".join(buf)


@dataclass
class Cell:
    """Table cell containing block elements (paragraphs and nested tables)."""

    id: int = field(default_factory=_next_nid)
    tc_pr: CellProperties = field(default_factory=CellProperties)
    blocks: list[Paragraph | Table] = field(default_factory=lambda: [Paragraph()])


@dataclass
class Row:
    """Table row containing cells."""

    id: int = field(default_factory=_next_nid)
    tr_pr: RowProperties = field(default_factory=RowProperties)
    cells: list[Cell] = field(default_factory=list)


@dataclass
class Table:
    """Table block containing rows and column grid definitions."""

    id: int = field(default_factory=_next_nid)
    tbl_pr: TableProperties = field(default_factory=TableProperties)
    grid: list[float] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)


@dataclass
class Story:
    """A story container (main body, header, footer, footnote, endnote, textbox)."""

    kind: str = "main"
    blocks: list[Paragraph | Table] = field(default_factory=list)
    paras: list[Paragraph] = field(default_factory=list)


@dataclass
class Document:
    """Root Quire document container."""

    main: Story = field(default_factory=lambda: Story(kind="main", blocks=[Paragraph()]))
    sect: SectionProperties = field(default_factory=SectionProperties)
    styles: dict[str, Any] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=lambda: {"r_pr": RunProperties(), "p_pr": ParagraphProperties()})
    numbering: dict[str, Any] = field(default_factory=lambda: {"abs": {}, "nums": {}})
    hf: dict[str, Story] = field(default_factory=dict)
    fn: dict[str, Story] = field(default_factory=dict)
    en: dict[str, Story] = field(default_factory=dict)
    comments: dict[str, Story] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    props: dict[str, Any] = field(default_factory=dict)
    _idx: dict[int, dict[str, Any]] = field(default_factory=dict)
    _tbls: dict[int, dict[str, Any]] = field(default_factory=dict)
    _idx_dirty: bool = True

    def __post_init__(self) -> None:
        if not self.styles:
            from atboffice.modules.writer.models.styles import builtin_styles

            self.styles = builtin_styles()


# ----------------------------------------------------------------------
# Run Editing & Slicing Operations
# ----------------------------------------------------------------------


def locate(p: Paragraph, o: int, side: str = "after") -> tuple[int, int, int]:
    """Locate item covering character offset `o`: returns (item_index, offset_in_item, start_pos)."""
    pos = 0
    runs = p.runs
    for i, it in enumerate(runs):
        n = ilen(it)
        if side == "before":
            if pos < o <= pos + n:
                return (i, o - pos, pos)
        else:
            if o < pos + n:
                return (i, o - pos, pos)
        if n == 0 and o == pos and side == "marker":
            return (i, 0, pos)
        pos += n
    return (len(runs), 0, pos)


def split_at(p: Paragraph, o: int) -> int:
    """Split runs so that a run boundary exists at character offset `o`. Returns item index at/after `o`."""
    pos = 0
    for i, it in enumerate(p.runs):
        n = ilen(it)
        if o == pos:
            return i
        if o < pos + n:
            if it.t != "text":
                return i
            k = o - pos
            txt = getattr(it, "text", "")
            a = TextItem(text=txt[:k], r_pr=copy.deepcopy(it.r_pr))
            b = TextItem(text=txt[k:], r_pr=copy.deepcopy(it.r_pr))
            p.runs[i : i + 1] = [a, b]
            return i + 1
        pos += n
    return len(p.runs)


def insert_index(p: Paragraph, o: int) -> int:
    """Return index for inserting content at offset `o`, advancing past trailing end markers."""
    i = split_at(p, o)
    while i < len(p.runs) and p.runs[i].t in {"fe", "ce", "be", "sdts"}:
        i += 1
    return i


def normalize(p: Paragraph) -> Paragraph:
    """Merge adjacent TextItems with equal formatting, and remove empty TextItems."""
    out: list[RunItem] = []
    for it in p.runs:
        if it.t == "text" and not getattr(it, "text", ""):
            continue
        if out and it.t == "text" and out[-1].t == "text":
            last = out[-1]
            if last.r_pr == it.r_pr:
                last.text += getattr(it, "text", "")
                continue
        out.append(it)
    p.runs = out
    return p


def slice_runs(p: Paragraph, a: int, b: int) -> list[RunItem]:
    """Deep copy of items covering character range [a, b)."""
    out: list[RunItem] = []
    pos = 0
    for it in p.runs:
        n = ilen(it)
        s, e = pos, pos + n
        pos = e
        if n == 0:
            is_end = it.t in {"ce", "be", "fe", "sdte"}
            if s >= a and s <= b:
                if not (s == b and b != a and not is_end) and not (s == a and a != b and is_end):
                    out.append(copy.deepcopy(it))
            continue
        if e <= a or s >= b:
            continue
        if it.t == "text":
            item_copy = copy.deepcopy(it)
            item_copy.text = it.text[max(0, a - s) : min(n, b - s)]
            out.append(item_copy)
        else:
            out.append(copy.deepcopy(it))
    return out


# ----------------------------------------------------------------------
# Tree Indexing, Traversal, and Query
# ----------------------------------------------------------------------


def walk(
    container: Any,
    callback: Callable[[Any, Any, int, Any, list[Any]], bool | None],
    story: Any = None,
    parents: list[Any] | None = None,
) -> bool:
    """Visit every block depth-first: callback(block, container, index, story, parents)."""
    story = story or container
    parents = parents or []
    blocks = getattr(container, "blocks", [])
    for i, b in enumerate(blocks):
        res = callback(b, container, i, story, parents)
        if res is False:
            return False
        if isinstance(b, Table):
            for r in b.rows:
                for c in r.cells:
                    sub_parents = parents + [{"tbl": b, "row": r, "cell": c}]
                    if walk(c, callback, story, sub_parents) is False:
                        return False
    return True


def reindex(doc: Document) -> dict[int, dict[str, Any]]:
    """Build global fast-lookup index and reading order for all paragraphs in all stories."""
    para_map: dict[int, dict[str, Any]] = {}
    tbl_map: dict[int, dict[str, Any]] = {}

    def index_story(st: Story) -> None:
        paras: list[Paragraph] = []

        def visitor(b: Any, cont: Any, i: int, cur_story: Any, parents: list[Any]) -> bool | None:
            if isinstance(b, Paragraph):
                if cur_story != st:
                    return None
                b._o = len(paras)
                paras.append(b)
                para_map[b.id] = {"p": b, "cont": cont, "i": i, "story": st, "parents": parents}
            elif isinstance(b, Table):
                tbl_map[b.id] = {"tbl": b, "cont": cont, "i": i, "story": st, "parents": parents}
            return None

        walk(st, visitor)
        st.paras = paras

    all_stories = [doc.main] + list(doc.hf.values()) + list(doc.fn.values()) + list(doc.en.values()) + list(doc.comments.values())
    for s in all_stories:
        index_story(s)

    doc._idx = para_map
    doc._tbls = tbl_map
    doc._idx_dirty = False
    return para_map


def info(doc: Document, p: Paragraph | int) -> dict[str, Any] | None:
    """Get location and container info for a paragraph."""
    if doc._idx_dirty or not doc._idx:
        reindex(doc)
    pid = p.id if isinstance(p, Paragraph) else p
    r = doc._idx.get(pid)
    if not r:
        reindex(doc)
        r = doc._idx.get(pid)
    return r


def all_paragraphs(doc: Document, all_stories: bool = False) -> list[Paragraph]:
    """Return all paragraphs in reading order."""
    if doc._idx_dirty or not doc._idx:
        reindex(doc)
    if not all_stories:
        return doc.main.paras
    out: list[Paragraph] = []
    stories = [doc.main] + list(doc.hf.values()) + list(doc.fn.values()) + list(doc.en.values()) + list(doc.comments.values())
    for s in stories:
        out.extend(s.paras)
    return out


def paras_between(doc: Document, a: Paragraph, b: Paragraph) -> list[Paragraph]:
    """Return all paragraphs from a to b inclusive in story reading order."""
    ia = info(doc, a)
    ib = info(doc, b)
    if not ia or not ib or ia["story"] != ib["story"]:
        return [a]
    s_paras = ia["story"].paras
    i0 = min(a._o, b._o)
    i1 = max(a._o, b._o)
    return s_paras[i0 : i1 + 1]


def sections(doc: Document) -> list[dict[str, Any]]:
    """Extract section ranges in the main story: [{sect, from, to, end_para}]."""
    out: list[dict[str, Any]] = []
    start_idx = 0
    blocks = doc.main.blocks
    for i, b in enumerate(blocks):
        if isinstance(b, Paragraph) and b.sect:
            out.append({"sect": b.sect, "from": start_idx, "to": i + 1, "end_para": b})
            start_idx = i + 1
    out.append({"sect": doc.sect, "from": start_idx, "to": len(blocks), "end_para": None})
    return out


def sect_for(doc: Document, p: Paragraph) -> SectionProperties:
    """Return the SectionProperties governing a paragraph."""
    inf = info(doc, p)
    if not inf or inf["story"] != doc.main:
        return doc.sect
    top_block_idx = inf["parents"][0]["tbl"].id if inf["parents"] else inf["i"]
    for s in sections(doc):
        if inf["i"] < s["to"] or s["end_para"] is None:
            return s["sect"]
    return doc.sect
