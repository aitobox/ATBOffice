"""Document-model operations behind Quire's dialogs and toolbar commands.

Each function mutates ``canvas.doc`` at the caret. Callers wrap them in
``WriterCanvasView.run_undoable`` so every command is one undo step.
"""

from __future__ import annotations

import copy
import datetime as _dt
import re
import uuid
from typing import Any

from atboffice.core.i18n import safe_tr
from atboffice.modules.writer.models.document import (
    BookmarkEndItem,
    BookmarkStartItem,
    BreakItem,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    NoteRefItem,
    Paragraph,
    Story,
    TabItem,
    Table,
    TextItem,
    ilen,
    reindex,
)
from atboffice.modules.writer.models.document import plain_text as ptext
from atboffice.modules.writer.models.properties import RunProperties
from atboffice.modules.writer.views.caret_controller import DocPos, Selection, split_paragraph

# ---------------------------------------------------------------------------
# Caret helpers
# ---------------------------------------------------------------------------


def current_paragraph(canvas: Any) -> Paragraph | None:
    return canvas.controller._paragraph_by_id(canvas.controller.pos.para_id)


def _story_blocks_of(canvas: Any, para: Paragraph) -> list[Any]:
    """The block list (body, table cell, header...) that directly holds ``para``."""
    from atboffice.modules.writer.models.document import info

    inf = info(canvas.doc, para.id)
    parents = (inf or {}).get("parents") or []
    for parent in reversed(parents):
        if isinstance(parent, dict) and parent.get("cell") is not None:
            return parent["cell"].blocks
    story = (inf or {}).get("story")
    return story.blocks if story is not None else canvas.doc.main.blocks


def _split_runs_at(p: Paragraph, offset: int) -> int:
    """Split ``p``'s runs so a run boundary falls at ``offset``; return its run index."""
    cur = 0
    for i, it in enumerate(p.runs):
        n = ilen(it)
        if offset == cur:
            return i
        if it.t == "text" and cur < offset < cur + n:
            local = offset - cur
            tail = TextItem(it.text[local:], copy.deepcopy(it.r_pr))
            it.text = it.text[:local]
            p.runs.insert(i + 1, tail)
            return i + 1
        cur += n
    return len(p.runs)


def _caret_r_pr(p: Paragraph, offset: int) -> RunProperties:
    cur = 0
    for it in p.runs:
        n = ilen(it)
        if cur <= offset <= cur + n and it.t == "text":
            return copy.deepcopy(it.r_pr)
        cur += n
    return copy.deepcopy(p.runs[-1].r_pr if p.runs else p.r_pr)


def insert_items(canvas: Any, items: list[Any]) -> None:
    """Insert inline run items at the caret and move the caret after them."""
    ctrl = canvas.controller
    if not ctrl.selection.is_collapsed:
        ctrl.delete_selection()
    p = current_paragraph(canvas)
    if p is None:
        return
    idx = _split_runs_at(p, ctrl.pos.offset)
    for k, item in enumerate(items):
        p.runs.insert(idx + k, item)
    advance = sum(ilen(it) for it in items)
    ctrl.pos = DocPos(p.id, ctrl.pos.offset + advance)
    ctrl.selection = Selection(ctrl.pos, ctrl.pos)


def insert_plain_text(canvas: Any, text: str) -> None:
    p = current_paragraph(canvas)
    if p is None or not text:
        return
    insert_items(canvas, [TextItem(text, _caret_r_pr(p, canvas.controller.pos.offset))])


def insert_field(canvas: Any, code: str, result: str, field_type: str = "") -> None:
    """Insert a complex field (begin / code / separate / cached result / end)."""
    p = current_paragraph(canvas)
    if p is None:
        return
    r_pr = _caret_r_pr(p, canvas.controller.pos.offset)
    name = field_type or (code.strip().split() or [""])[0].upper()
    insert_items(
        canvas,
        [
            FieldBeginItem(field_type=name, instr=f" {code.strip()} ", r_pr=copy.deepcopy(r_pr)),
            FieldSeparateItem(r_pr=copy.deepcopy(r_pr)),
            TextItem(result, copy.deepcopy(r_pr)),
            FieldEndItem(r_pr=copy.deepcopy(r_pr)),
        ],
    )


def insert_paragraphs_after(canvas: Any, texts: list[str], style: str | None = None) -> None:
    """Insert new paragraphs after the caret paragraph and put the caret at the last one."""
    p = current_paragraph(canvas)
    if p is None:
        return
    blocks = _story_blocks_of(canvas, p)
    idx = blocks.index(p) + 1 if p in blocks else len(blocks)
    last = p
    for k, text in enumerate(texts):
        np = Paragraph(p_pr=copy.deepcopy(p.p_pr), r_pr=copy.deepcopy(p.r_pr))
        np.p_pr.num = None
        if style:
            np.p_pr.style = style
        if text:
            np.runs.append(TextItem(text, copy.deepcopy(p.r_pr)))
        blocks.insert(idx + k, np)
        last = np
    reindex(canvas.doc)
    canvas.controller.pos = DocPos(last.id, sum(ilen(it) for it in last.runs))
    canvas.controller.selection = Selection(canvas.controller.pos, canvas.controller.pos)


# ---------------------------------------------------------------------------
# Insert menu
# ---------------------------------------------------------------------------


def insert_break(canvas: Any, kind: str, value: str) -> None:
    """Insert → Break: page / column / text-wrapping, or a section break."""
    ctrl = canvas.controller
    if kind == "break":
        insert_items(canvas, [BreakItem({"wrap": "line"}.get(value, value))])
        return
    # Section break: end the current paragraph here and give it the section's
    # properties (the paragraph carries w:sectPr for the section that ends).
    p = current_paragraph(canvas)
    if p is None:
        return
    tail = split_paragraph(p, ctrl.pos.offset)
    blocks = _story_blocks_of(canvas, p)
    idx = blocks.index(p) + 1 if p in blocks else len(blocks)
    blocks.insert(idx, tail)
    sect = copy.deepcopy(canvas.doc.sect)
    sect.sect_type = value or "nextPage"
    p.sect = sect  # type: ignore[attr-defined]
    reindex(canvas.doc)
    ctrl.pos = DocPos(tail.id, 0)
    ctrl.selection = Selection(ctrl.pos, ctrl.pos)


def insert_symbol(canvas: Any, char: str) -> None:
    insert_plain_text(canvas, char)


def _format_date(fmt: str, when: _dt.datetime | None = None) -> str:
    """Render a Word date picture (``MMMM d, yyyy``, ``yyyy-MM-dd``, ``h:mm am/pm``...)."""
    when = when or _dt.datetime.now()
    tokens = [
        ("yyyy", f"{when.year:04d}"),
        ("yy", f"{when.year % 100:02d}"),
        ("MMMM", when.strftime("%B")),
        ("MMM", when.strftime("%b")),
        ("MM", f"{when.month:02d}"),
        ("M", str(when.month)),
        ("dddd", when.strftime("%A")),
        ("ddd", when.strftime("%a")),
        ("dd", f"{when.day:02d}"),
        ("d", str(when.day)),
        ("HH", f"{when.hour:02d}"),
        ("H", str(when.hour)),
        ("hh", f"{(when.hour % 12) or 12:02d}"),
        ("h", str((when.hour % 12) or 12)),
        ("mm", f"{when.minute:02d}"),
        ("ss", f"{when.second:02d}"),
        ("am/pm", "am" if when.hour < 12 else "pm"),
        ("AM/PM", "AM" if when.hour < 12 else "PM"),
    ]
    pattern = "|".join(re.escape(t) for t, _ in tokens)
    mapping = dict(tokens)
    return re.sub(pattern, lambda m: mapping[m.group(0)], fmt)


def insert_date_time(canvas: Any, fmt_text: str, update_automatically: bool) -> None:
    """Insert → Date and Time. ``fmt_text`` is the chosen sample shown in the dialog."""
    if update_automatically:
        insert_field(canvas, f'DATE \\@ "{fmt_text}"', fmt_text, "DATE")
    else:
        insert_plain_text(canvas, fmt_text)


def insert_field_from_dialog(canvas: Any, data: dict[str, str]) -> None:
    code = (data.get("code") or f"{data.get('name', '')} {data.get('args', '')}").strip()
    if not code:
        return
    name = (data.get("name") or code.split()[0]).upper()
    results = {
        "DATE": _format_date("M/d/yyyy"),
        "TIME": _format_date("h:mm am/pm"),
        "PAGE": "1",
        "NUMPAGES": "1",
        "AUTHOR": str(canvas.doc.props.get("creator", "")),
        "TITLE": str(canvas.doc.props.get("title", "")),
        "FILENAME": str(canvas.doc.props.get("filename", "")),
    }
    insert_field(canvas, code, results.get(name, f"«{name}»"), name)


def _new_bookmark_id(doc: Any) -> int:
    ids = [
        getattr(it, "bookmark_id", 0)
        for p in doc.all_paras()
        for it in p.runs
        if getattr(it, "t", "") == "bs"
    ]
    return (max(ids) + 1) if ids else 1


def document_bookmarks(doc: Any) -> list[str]:
    return [
        it.name
        for p in doc.all_paras()
        for it in p.runs
        if getattr(it, "t", "") == "bs" and getattr(it, "name", "")
    ]


def add_bookmark(canvas: Any, name: str) -> bool:
    """Insert → Bookmark → Add: wrap the selection (or mark the caret) with a bookmark."""
    name = re.sub(r"\s+", "_", name.strip())
    if not name or name in document_bookmarks(canvas.doc):
        return False
    ctrl = canvas.controller
    bid = _new_bookmark_id(canvas.doc)
    start, end = (
        ctrl.selection.ordered_range(canvas.doc)
        if not ctrl.selection.is_collapsed
        else (ctrl.pos, ctrl.pos)
    )
    if start.para_id == end.para_id:
        p = (
            current_paragraph(canvas)
            if ctrl.pos.para_id == start.para_id
            else (ctrl._paragraph_by_id(start.para_id))
        )
        if p is None:
            return False
        e_idx = _split_runs_at(p, end.offset)
        p.runs.insert(e_idx, BookmarkEndItem(bookmark_id=bid))
        s_idx = _split_runs_at(p, start.offset)
        p.runs.insert(s_idx, BookmarkStartItem(name=name, bookmark_id=bid))
        return True
    p_start = ctrl._paragraph_by_id(start.para_id)
    p_end = ctrl._paragraph_by_id(end.para_id)
    if p_start is None or p_end is None:
        return False
    p_end.runs.insert(_split_runs_at(p_end, end.offset), BookmarkEndItem(bookmark_id=bid))
    p_start.runs.insert(
        _split_runs_at(p_start, start.offset), BookmarkStartItem(name=name, bookmark_id=bid)
    )
    return True


def delete_bookmark(canvas: Any, name: str) -> bool:
    bid = None
    for p in canvas.doc.all_paras():
        for it in list(p.runs):
            if getattr(it, "t", "") == "bs" and getattr(it, "name", "") == name:
                bid = it.bookmark_id
                p.runs.remove(it)
    if bid is None:
        return False
    for p in canvas.doc.all_paras():
        p.runs[:] = [
            it
            for it in p.runs
            if not (getattr(it, "t", "") == "be" and getattr(it, "bookmark_id", None) == bid)
        ]
    return True


def insert_hyperlink(canvas: Any, data: dict[str, Any]) -> None:
    """Insert → Hyperlink: link the selection, or insert the display text as a link."""
    target = (data.get("target") or "").strip()
    if not target:
        return
    text = (data.get("text") or "").strip() or target
    link: dict[str, Any] = {"tooltip": data.get("screentip", "")}
    if data.get("kind") == "bookmark" or target.startswith("#"):
        link["anchor"] = target.lstrip("#")
    else:
        if data.get("kind") == "email" and not target.lower().startswith("mailto:"):
            target = f"mailto:{target}"
        link["url"] = target
    ctrl = canvas.controller
    p = current_paragraph(canvas)
    if p is None:
        return
    r_pr = _caret_r_pr(p, ctrl.pos.offset)
    r_pr.link = link
    r_pr.color = "0563C1"
    r_pr.u = "single"
    insert_items(canvas, [TextItem(text, r_pr)])


def insert_footnote(canvas: Any, settings: dict[str, Any]) -> None:
    """Insert → Reference → Footnote/Endnote: a reference mark and an empty note story."""
    kind = "en" if settings.get("type") == "endnote" else "fn"
    notes = canvas.doc.en if kind == "en" else canvas.doc.fn
    numeric = [int(k) for k in notes if str(k).lstrip("-").isdigit()]
    note_id = str(max([n for n in numeric if n > 0], default=0) + 1)
    mark = settings.get("custom_mark", "") or ""
    p = current_paragraph(canvas)
    if p is None:
        return
    r_pr = _caret_r_pr(p, canvas.controller.pos.offset)
    r_pr.vert = "superscript"
    insert_items(canvas, [NoteRefItem(kind=kind, note_id=note_id, custom_mark=mark, r_pr=r_pr)])
    style = "EndnoteText" if kind == "en" else "FootnoteText"
    body = Paragraph()
    body.p_pr.style = style
    notes[note_id] = Story(kind="endnote" if kind == "en" else "footnote", blocks=[body])


def _seq_count(doc: Any, label: str) -> int:
    pattern = re.compile(rf"^{re.escape(label)}\s+\d+")
    return sum(1 for p in doc.all_paras() if pattern.match(ptext(p)))


def insert_caption(canvas: Any, data: dict[str, Any]) -> None:
    """Insert → Reference → Caption: a ``Caption`` paragraph with a SEQ number."""
    label = (data.get("label") or "Figure").strip()
    caption = data.get("caption") or ""
    number = _seq_count(canvas.doc, label) + 1
    if data.get("exclude_label"):
        text = f"{number}{caption}"
    else:
        text = caption if caption.startswith(label) else f"{label} {number}{caption}"
    p = current_paragraph(canvas)
    if p is None:
        return
    blocks = _story_blocks_of(canvas, p)
    cap = Paragraph()
    cap.p_pr.style = "Caption"
    cap.runs.append(TextItem(text, copy.deepcopy(p.r_pr)))
    idx = blocks.index(p) if p in blocks else len(blocks)
    blocks.insert(idx + (0 if data.get("position") == "above" else 1), cap)
    reindex(canvas.doc)
    canvas.controller.pos = DocPos(cap.id, len(text))
    canvas.controller.selection = Selection(canvas.controller.pos, canvas.controller.pos)


def insert_cross_reference(canvas: Any, data: dict[str, Any]) -> None:
    target = (data.get("target") or "").strip()
    if not target:
        return
    mode = data.get("insert_as") or "text"
    bookmark = re.sub(r"\W+", "_", target)
    code = f"REF {bookmark}" + (" \\h" if data.get("as_hyperlink") else "")
    result = {"page": "1", "number": target.split()[-1] if target.split() else target}.get(
        mode, target
    )
    insert_field(canvas, code, result, "REF")


def headings(doc: Any, max_level: int = 3) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for p in doc.all_paras():
        style = p.p_pr.style or ""
        m = re.match(r"(?i)heading\s*([1-9])$", style)
        lvl = (
            int(m.group(1))
            if m
            else ((p.p_pr.outline_level + 1) if p.p_pr.outline_level is not None else None)
        )
        if lvl and lvl <= max_level and ptext(p).strip():
            out.append((lvl, ptext(p).strip()))
    return out


def insert_table_of_contents(canvas: Any, data: dict[str, Any]) -> None:
    """Index and Tables → Table of Contents: a TOC field block listing the headings."""
    levels = int(data.get("toc_levels") or 3)
    entries = headings(canvas.doc, levels)
    p = current_paragraph(canvas)
    if p is None:
        return
    blocks = _story_blocks_of(canvas, p)
    idx = blocks.index(p) + 1 if p in blocks else len(blocks)
    title = Paragraph()
    title.p_pr.style = "TOCHeading"
    title.runs.append(TextItem(safe_tr("目录")))
    new = [title]
    if not entries:
        empty = Paragraph()
        empty.runs.append(TextItem(safe_tr("未找到目录项。")))
        new.append(empty)
    show_pages = data.get("toc_show_pages", True)
    for lvl, text in entries:
        entry = Paragraph()
        entry.p_pr.style = f"TOC{lvl}"
        entry.runs.append(TextItem(text))
        if show_pages:
            entry.runs.extend([TabItem(), TextItem("1")])
        new.append(entry)
    new[0].runs.insert(0, FieldBeginItem(field_type="TOC", instr=f' TOC \\o "1-{levels}" \\h '))
    new[0].runs.insert(1, FieldSeparateItem())
    new[-1].runs.append(FieldEndItem())
    for k, para in enumerate(new):
        blocks.insert(idx + k, para)
    reindex(canvas.doc)


def update_table_of_contents(canvas: Any) -> bool:
    """References → Update Table: rebuild the entries of the first TOC field."""
    doc = canvas.doc
    for blocks in (doc.main.blocks,):
        for i, block in enumerate(blocks):
            if not isinstance(block, Paragraph):
                continue
            begin = next(
                (
                    it
                    for it in block.runs
                    if getattr(it, "t", "") == "fb" and getattr(it, "field_type", "") == "TOC"
                ),
                None,
            )
            if begin is None:
                continue
            end_idx = i
            while end_idx < len(blocks) and not (
                isinstance(blocks[end_idx], Paragraph)
                and any(getattr(it, "t", "") == "fe" for it in blocks[end_idx].runs)
            ):
                end_idx += 1
            m = re.search(r'\\o\s+"1-(\d)"', getattr(begin, "instr", ""))
            levels = int(m.group(1)) if m else 3
            del blocks[i + 1 : end_idx + 1]
            entries = []
            for lvl, text in headings(doc, levels):
                entry = Paragraph()
                entry.p_pr.style = f"TOC{lvl}"
                entry.runs.extend([TextItem(text), TabItem(), TextItem("1")])
                entries.append(entry)
            if not entries:
                entry = Paragraph()
                entry.runs.append(TextItem(safe_tr("未找到目录项。")))
                entries.append(entry)
            entries[-1].runs.append(FieldEndItem())
            blocks[i + 1 : i + 1] = entries
            reindex(doc)
            return True
    return False


def toc_paragraph(doc: Any) -> Paragraph | None:
    for p in doc.all_paras():
        if any(
            getattr(it, "t", "") == "fb" and getattr(it, "field_type", "") == "TOC" for it in p.runs
        ):
            return p
    return None


# ---------------------------------------------------------------------------
# Format menu
# ---------------------------------------------------------------------------


def apply_drop_cap(canvas: Any, data: dict[str, Any]) -> None:
    p = current_paragraph(canvas)
    if p is None:
        return
    position = data.get("position", "none")
    if position in (None, "", "none"):
        if p.p_pr.frame_pr and p.p_pr.frame_pr.get("dropCap"):
            p.p_pr.frame_pr = None
        return
    frame = {
        "dropCap": "margin" if position == "margin" else "drop",
        "lines": str(int(data.get("lines", 3))),
        "wrap": "around",
        "vAnchor": "text",
        "hAnchor": "text",
        "hSpace": str(int(float(data.get("distance_cm", 0)) * 567)),
    }
    p.p_pr.frame_pr = frame
    if data.get("font"):
        for it in p.runs[:1]:
            if it.t == "text":
                it.r_pr.font = data["font"]


def apply_text_direction(canvas: Any, direction: str) -> None:
    ctx = canvas.get_current_table_context()
    if ctx is not None:
        ctx["cell"].tc_pr.text_direction = {"vert": "tbRl", "vert270": "btLr"}.get(
            direction, "lrTb"
        )
    else:
        canvas.doc.settings["textDirection"] = direction


def apply_watermark(canvas: Any, data: dict[str, Any]) -> None:
    if data.get("type") in (None, "", "none"):
        canvas.doc.settings.pop("watermark", None)
    else:
        canvas.doc.settings["watermark"] = dict(data)


def _hf_story(doc: Any, kind: str, create: bool = True) -> Story | None:
    """The default header (``hdr``) or footer (``ftr``) story, created when missing."""
    refs = doc.sect.refs.setdefault(kind, {})
    rid = refs.get("default")
    if rid and rid in doc.hf:
        return doc.hf[rid]
    if not create:
        return None
    rid = f"rId_{kind}_{uuid.uuid4().hex[:8]}"
    refs["default"] = rid
    story = Story(kind=kind, blocks=[Paragraph()], id=rid)
    story.blocks[0].p_pr.style = "Header" if kind == "hdr" else "Footer"
    doc.hf[rid] = story
    return story


def apply_page_numbers(canvas: Any, settings: dict[str, Any]) -> None:
    """Insert → Page Numbers: a PAGE field in the header or footer."""
    doc = canvas.doc
    kind = "hdr" if str(settings.get("position", "bottom")).startswith("top") else "ftr"
    story = _hf_story(doc, kind)
    assert story is not None
    para = Paragraph()
    para.p_pr.style = "Header" if kind == "hdr" else "Footer"
    para.p_pr.jc = {
        "left": "left",
        "center": "center",
        "right": "right",
        "inside": "left",
        "outside": "right",
    }.get(str(settings.get("alignment", "right")), "right")
    para.runs = [
        FieldBeginItem(field_type="PAGE", instr=" PAGE "),
        FieldSeparateItem(),
        TextItem("1"),
        FieldEndItem(),
    ]
    blocks = [b for b in story.blocks if not (isinstance(b, Paragraph) and not b.runs)]
    story.blocks = [*blocks, para]
    doc.sect.title_pg = not settings.get("show_first_page", True)
    fmt = settings.get("number_format")
    if fmt:
        doc.sect.pg_num.fmt = fmt
    if not settings.get("continue_numbering", True):
        doc.sect.pg_num.start = int(settings.get("start_at", 1))
    else:
        doc.sect.pg_num.start = None


def change_case(canvas: Any, mode: str) -> bool:
    """Format → Change Case on the selection (or the word at the caret)."""
    ctrl = canvas.controller
    if ctrl.selection.is_collapsed:
        ctrl.select_word_at(ctrl.pos)
    if ctrl.selection.is_collapsed:
        return False
    start, end = ctrl.selection.ordered_range(ctrl.doc)

    def convert(text: str, at_start: bool) -> str:
        if mode == "upper":
            return text.upper()
        if mode == "lower":
            return text.lower()
        if mode == "title":
            return re.sub(r"\b(\w)(\w*)", lambda m: m.group(1).upper() + m.group(2).lower(), text)
        if mode == "toggle":
            return text.swapcase()
        if mode == "sentence":
            low = text.lower()
            return (low[:1].upper() + low[1:]) if at_start else low
        return text

    first = True
    for p in ctrl.doc.all_paras():
        if p.id not in {start.para_id, end.para_id} and not _between(ctrl, p, start, end):
            continue
        lo = start.offset if p.id == start.para_id else 0
        hi = end.offset if p.id == end.para_id else sum(ilen(it) for it in p.runs)
        cur = 0
        for it in p.runs:
            n = ilen(it)
            if it.t == "text":
                a, b = max(lo, cur), min(hi, cur + n)
                if a < b:
                    la, lb = a - cur, b - cur
                    it.text = it.text[:la] + convert(it.text[la:lb], first) + it.text[lb:]
                    first = False
            cur += n
    return True


def _between(ctrl: Any, p: Paragraph, start: DocPos, end: DocPos) -> bool:
    paras = ctrl.doc.all_paras()
    ids = [x.id for x in paras]
    try:
        return ids.index(start.para_id) < ids.index(p.id) < ids.index(end.para_id)
    except ValueError:
        return False


def apply_hyphenation(canvas: Any, settings: dict[str, Any]) -> None:
    s = canvas.doc.settings
    s["autoHyphenation"] = bool(settings.get("auto"))
    s["doNotHyphenateCaps"] = not settings.get("hyphenate_caps", True)
    s["hyphenationZone"] = float(settings.get("zone_pt", 18.0))
    limit = settings.get("limit")
    s["consecutiveHyphenLimit"] = int(limit) if str(limit).isdigit() else 0


# ---------------------------------------------------------------------------
# Tools menu
# ---------------------------------------------------------------------------


def insert_letter(canvas: Any, data: dict[str, Any]) -> None:
    """Letter Wizard: write the letter at the caret."""
    lines: list[str] = []
    if data.get("date_line"):
        lines.append(_format_date(data.get("date_format") or "MMMM d, yyyy"))
        lines.append("")
    for key in ("recipient_name", "recipient_addr"):
        if data.get(key):
            lines.extend(str(data[key]).splitlines())
    lines.append("")
    if data.get("subject"):
        lines.extend([str(data["subject"]), ""])
    salutation = data.get("salutation") or ""
    name = data.get("recipient_name") or ""
    lines.append(f"{salutation} {name},".strip() if salutation else "")
    lines.extend(["", "", data.get("closing") or "", "", data.get("sender_name") or ""])
    if data.get("sender_addr"):
        lines.extend(str(data["sender_addr"]).splitlines())
    insert_paragraphs_after(canvas, lines)


def insert_envelope(canvas: Any, data: dict[str, Any]) -> None:
    """Envelopes and Labels → Add to Document: addresses at the start of the document."""
    lines: list[str] = []
    if data.get("tab") == "labels":
        lines.extend(str(data.get("label_addr", "")).splitlines())
    else:
        if not data.get("omit_return"):
            lines.extend(str(data.get("return_addr", "")).splitlines())
            lines.append("")
        lines.extend(str(data.get("delivery", "")).splitlines())
    lines = [ln for ln in lines]
    if not any(ln.strip() for ln in lines):
        return
    blocks = canvas.doc.main.blocks
    new = []
    for text in lines:
        p = Paragraph()
        if text:
            p.runs.append(TextItem(text))
        new.append(p)
    new[-1].p_pr.page_break_before = False
    after = blocks[0] if blocks else None
    if isinstance(after, Paragraph):
        after.p_pr.page_break_before = True
    blocks[0:0] = new
    reindex(canvas.doc)


def auto_summarize(canvas: Any, data: dict[str, Any]) -> bool:
    """AutoSummarize: keep the leading sentence of the most important paragraphs."""
    paras = [p for p in canvas.doc.main.blocks if isinstance(p, Paragraph) and ptext(p).strip()]
    if not paras:
        return False
    pct = max(1, min(100, int(data.get("length", 25))))
    keep = max(1, round(len(paras) * pct / 100))
    ranked = sorted(paras, key=lambda p: len(ptext(p)), reverse=True)[:keep]
    chosen = [p for p in paras if p in ranked]
    sentences = [re.split(r"(?<=[.!?。！？])\s*", ptext(p).strip())[0] for p in chosen]
    mode = data.get("mode", "highlight")
    if mode == "highlight":
        for p in chosen:
            for it in p.runs:
                if it.t == "text":
                    it.r_pr.highlight = "yellow"
        return True
    summary = [Paragraph()]
    summary[0].p_pr.style = "Heading1"
    summary[0].runs.append(TextItem(safe_tr("摘要")))
    for text in sentences:
        sp = Paragraph()
        sp.runs.append(TextItem(text))
        summary.append(sp)
    if mode == "new_doc":
        canvas.doc.settings["autoSummary"] = sentences
        return True
    canvas.doc.main.blocks[0:0] = summary
    reindex(canvas.doc)
    return True


# ---------------------------------------------------------------------------
# Table menu
# ---------------------------------------------------------------------------


def table_insert_cells(canvas: Any, action: str) -> None:
    if action in ("down", "row"):
        canvas.insert_table_row(above=False)
    elif action in ("right", "col"):
        canvas.insert_table_col(left=False)


def table_delete_cells(canvas: Any, action: str) -> None:
    if action in ("up", "row"):
        canvas.delete_table_row()
    elif action in ("left", "col"):
        canvas.delete_table_col()


def table_autoformat(canvas: Any, settings: dict[str, Any]) -> None:
    ctx = canvas.get_current_table_context()
    if ctx is None:
        return
    tbl: Table = ctx["tbl"]
    style = settings.get("style")
    if style:
        tbl.tbl_pr.style = style
    look = getattr(tbl.tbl_pr, "look", None)
    flags = {
        "firstRow": bool(settings.get("heading_rows", True)),
        "firstColumn": bool(settings.get("first_col", True)),
        "lastRow": bool(settings.get("last_row", False)),
        "lastColumn": bool(settings.get("last_col", False)),
    }
    if isinstance(look, dict):
        look.update(flags)
    else:
        tbl.tbl_pr.look = flags  # type: ignore[attr-defined]


def table_formula(canvas: Any, formula: str, number_format: str) -> None:
    """Table → Formula: an ``=`` field with the computed result."""
    ctx = canvas.get_current_table_context()
    expr = formula.strip().lstrip("=")
    result = ""
    if ctx is not None:
        m = re.match(r"(?i)(SUM|AVERAGE|MIN|MAX|COUNT)\((ABOVE|LEFT|BELOW|RIGHT)\)", expr)
        if m:
            fn, direction = m.group(1).upper(), m.group(2).upper()
            values = _neighbour_numbers(ctx, direction)
            if values or fn == "COUNT":
                calc = {
                    "SUM": sum(values),
                    "AVERAGE": (sum(values) / len(values)) if values else 0,
                    "MIN": min(values) if values else 0,
                    "MAX": max(values) if values else 0,
                    "COUNT": len(values),
                }[fn]
                result = f"{calc:g}" if not number_format else _format_number(calc, number_format)
    p = current_paragraph(canvas)
    if p is None:
        return
    insert_field(
        canvas,
        f"={expr}" + (f' \\# "{number_format}"' if number_format else ""),
        result or "!Syntax Error",
        "=",
    )


def _format_number(value: float, fmt: str) -> str:
    decimals = len(fmt.split(".")[1].rstrip("%")) if "." in fmt else 0
    text = f"{value:,.{decimals}f}" if "," in fmt else f"{value:.{decimals}f}"
    if fmt.startswith("$"):
        text = "$" + text
    if fmt.endswith("%"):
        text = text + "%"
    return text


def _neighbour_numbers(ctx: dict[str, Any], direction: str) -> list[float]:
    tbl, r_idx, c_idx = ctx["tbl"], ctx["row_idx"], ctx["col_idx"]
    cells: list[Any] = []
    if direction == "ABOVE":
        cells = [row.cells[c_idx] for row in tbl.rows[:r_idx] if c_idx < len(row.cells)]
    elif direction == "BELOW":
        cells = [row.cells[c_idx] for row in tbl.rows[r_idx + 1 :] if c_idx < len(row.cells)]
    elif direction == "LEFT":
        cells = tbl.rows[r_idx].cells[:c_idx]
    elif direction == "RIGHT":
        cells = tbl.rows[r_idx].cells[c_idx + 1 :]
    out: list[float] = []
    for cell in cells:
        text = " ".join(ptext(b) for b in cell.blocks if isinstance(b, Paragraph))
        m = re.search(r"-?\d[\d,]*\.?\d*", text)
        if m:
            try:
                out.append(float(m.group(0).replace(",", "")))
            except ValueError:
                pass
    return out


# ---------------------------------------------------------------------------
# Columns, breaks, selection
# ---------------------------------------------------------------------------


def set_columns(canvas: Any, preset: int | str) -> None:
    """Format → Columns presets: 1, 2 or 3 equal columns, or two unequal ``left``/``right``."""
    sect = canvas.doc.sect
    cols = sect.cols
    cols.space = cols.space or 36.0
    if preset in ("left", "right"):
        text_w = sect.pg_w - sect.ml - sect.mr - cols.space
        narrow = round(text_w / 3.0, 2)
        wide = round(text_w - narrow, 2)
        cols.num = 2
        cols.equal_width = False
        cols.widths = [narrow, wide] if preset == "left" else [wide, narrow]
        cols.spaces = [cols.space, 0.0]
        return
    cols.num = max(1, int(preset))
    cols.equal_width = True
    cols.widths = []
    cols.spaces = []


def insert_page_break(canvas: Any) -> None:
    insert_items(canvas, [BreakItem("page")])


def select_table(canvas: Any) -> bool:
    """Table → Select → Table: select from the first to the last cell paragraph."""
    ctx = canvas.get_current_table_context()
    if ctx is None:
        return False
    paras: list[Paragraph] = []

    def walk(blocks: list[Any]) -> None:
        for b in blocks:
            if isinstance(b, Paragraph):
                paras.append(b)
            elif isinstance(b, Table):
                for row in b.rows:
                    for cell in row.cells:
                        walk(cell.blocks)

    walk([ctx["tbl"]])
    if not paras:
        return False
    first, last = paras[0], paras[-1]
    end = DocPos(last.id, sum(ilen(it) for it in last.runs))
    canvas.controller.selection = Selection(DocPos(first.id, 0), end)
    canvas.controller.pos = end
    canvas.controller.selection_changed.emit()
    canvas.viewport().update()
    return True


def set_language(canvas: Any, lang: str) -> None:
    """Tools → Language: tag the selection (or the caret paragraph) with ``lang``."""

    def apply(r_pr: RunProperties) -> None:
        if re.match(r"^(zh|ja|ko)", lang):
            r_pr.lang_ea = lang
        else:
            r_pr.lang = lang

    canvas.format_range(apply)
