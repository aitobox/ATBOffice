"""Walk every editable paragraph of a presentation (shapes, groups, table cells, notes).

Find/Replace and Spelling both address text as ``(slide_idx, owner_key, para_idx)``:
``owner_key`` is ``("shape", shape_id)``, ``("cell", shape_id, r, c)`` or ``("notes",)``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun

OwnerKey = tuple[Any, ...]


@dataclass
class ParagraphRef:
    slide_idx: int
    owner: OwnerKey
    para_idx: int
    shape: Any | None  # the owning (top-level or group child) shape; None for notes

    @property
    def key(self) -> tuple[int, OwnerKey, int]:
        return self.slide_idx, self.owner, self.para_idx


def _shape_bodies(shape: Any) -> Iterator[tuple[OwnerKey, Any, TextBody]]:
    from atboffice.modules.presentation.tools.table_ops import ensure_tx

    if getattr(shape, "kids", None):
        for kid in shape.kids:
            yield from _shape_bodies(kid)
    if isinstance(getattr(shape, "text", None), TextBody):
        yield ("shape", shape.id), shape, shape.text
    tbl = getattr(shape, "tbl", None)
    if tbl:
        for r, row in enumerate(tbl.get("rows") or []):
            for c, cl in enumerate(row.get("cells") or []):
                if cl.get("hm") or cl.get("vm"):
                    continue
                yield ("cell", shape.id, r, c), shape, ensure_tx(cl)


def slide_bodies(slide: Any) -> Iterator[tuple[OwnerKey, Any, TextBody]]:
    for shape in getattr(slide, "shapes", []):
        yield from _shape_bodies(shape)


def iter_paragraphs(
    presentation: Any, include_notes: bool = True
) -> Iterator[tuple[ParagraphRef, str]]:
    """Yield every paragraph (and notes line) with its plain text, in reading order."""
    for s_idx, slide in enumerate(getattr(presentation, "slides", [])):
        for owner, shape, body in slide_bodies(slide):
            for p_idx, para in enumerate(body.paragraphs):
                yield ParagraphRef(s_idx, owner, p_idx, shape), para.plain_text
        notes = getattr(slide, "notes", "") or ""
        if include_notes and notes:
            for p_idx, line in enumerate(notes.split("\n")):
                yield ParagraphRef(s_idx, ("notes",), p_idx, None), line


def resolve_paragraph(presentation: Any, ref: ParagraphRef) -> Paragraph | None:
    if ref.owner[0] == "notes":
        return None
    slide = presentation.slides[ref.slide_idx]
    for owner, _shape, body in slide_bodies(slide):
        if owner == ref.owner:
            return body.paragraphs[ref.para_idx] if ref.para_idx < len(body.paragraphs) else None
    return None


def replace_range(para: Paragraph, start: int, end: int, new: str) -> None:
    """Replace characters [start, end) keeping the formatting of the run at ``start``."""
    if not para.runs:
        para.runs.append(TextRun(text=new))
        return
    pos = 0
    first = None
    for i, run in enumerate(para.runs):
        nxt = pos + len(run.text)
        if first is None and (start < nxt or (start == nxt and i == len(para.runs) - 1)):
            first = i
            offset = start - pos
            break
        pos = nxt
    if first is None:  # start at end of paragraph
        para.runs[-1].text += new
        return
    head = para.runs[first].text[:offset]
    remaining = end - start
    tail = ""
    i = first
    cut = offset
    while i < len(para.runs):
        run_text = para.runs[i].text
        avail = len(run_text) - cut
        if remaining <= avail:
            tail = run_text[cut + remaining :]
            break
        remaining -= avail
        i += 1
        cut = 0
    last = min(i, len(para.runs) - 1)
    para.runs[first].text = head + new + tail
    del para.runs[first + 1 : last + 1]


def replace_in_notes(slide: Any, line_idx: int, start: int, end: int, new: str) -> None:
    lines = (slide.notes or "").split("\n")
    if 0 <= line_idx < len(lines):
        line = lines[line_idx]
        lines[line_idx] = line[:start] + new + line[end:]
        slide.notes = "\n".join(lines)


def replace_at(presentation: Any, ref: ParagraphRef, start: int, end: int, new: str) -> None:
    if ref.owner[0] == "notes":
        replace_in_notes(presentation.slides[ref.slide_idx], ref.para_idx, start, end, new)
        return
    para = resolve_paragraph(presentation, ref)
    if para is not None:
        replace_range(para, start, end, new)


def paragraph_text(presentation: Any, ref: ParagraphRef) -> str | None:
    if ref.owner[0] == "notes":
        lines = (presentation.slides[ref.slide_idx].notes or "").split("\n")
        return lines[ref.para_idx] if ref.para_idx < len(lines) else None
    para = resolve_paragraph(presentation, ref)
    return para.plain_text if para is not None else None
