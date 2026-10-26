"""Caret and Selection controller for Quire document editing."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent

from atboffice.modules.writer.layout.pagination import (
    Page,
    PageFragment,
    PaginationResult,
    paginate_document,
)
from atboffice.modules.writer.layout.portions import (
    LayoutLine,
    Portion,
    measure_text_width,
)
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    Story,
    TextItem,
    all_paragraphs,
    ilen,
    info,
    plen,
    ptext,
    reindex,
)


@dataclass(frozen=True)
class DocPos:
    """Document position addressing a specific paragraph and character offset."""

    para_id: int
    offset: int

    def __repr__(self) -> str:
        return f"DocPos(para_id={self.para_id}, offset={self.offset})"


@dataclass
class Selection:
    """Selection model holding anchor and focus document positions."""

    anchor: DocPos
    focus: DocPos

    @property
    def is_collapsed(self) -> bool:
        """Return True if anchor and focus point to the same document location."""
        return self.anchor.para_id == self.focus.para_id and self.anchor.offset == self.focus.offset

    def ordered_range(self, doc: Document) -> tuple[DocPos, DocPos]:
        """Return (start, end) where start <= end in document reading order."""
        if self.anchor.para_id == self.focus.para_id:
            if self.anchor.offset <= self.focus.offset:
                return self.anchor, self.focus
            return self.focus, self.anchor

        ia = info(doc, self.anchor.para_id)
        ib = info(doc, self.focus.para_id)
        idx_a = ia["p"]._o if ia and "p" in ia else 0
        idx_b = ib["p"]._o if ib and "p" in ib else 0

        if idx_a < idx_b:
            return self.anchor, self.focus
        if idx_a > idx_b:
            return self.focus, self.anchor
        if self.anchor.offset <= self.focus.offset:
            return self.anchor, self.focus
        return self.focus, self.anchor


# ---------------------------------------------------------------------------
# Paragraph Editing Helper Functions
# ---------------------------------------------------------------------------


def insert_text_in_paragraph(p: Paragraph, offset: int, text: str) -> None:
    """Insert text at the specified character offset within paragraph runs."""
    if not text:
        return

    if not p.runs:
        r_pr = copy.deepcopy(p.r_pr)
        p.runs.append(TextItem(text, r_pr))
        return

    cur_offset = 0
    inserted = False
    for i, it in enumerate(p.runs):
        item_len = ilen(it)
        if cur_offset <= offset <= cur_offset + item_len:
            if it.t == "text":
                local_off = offset - cur_offset
                txt = getattr(it, "text", "")
                it.text = txt[:local_off] + text + txt[local_off:]
                inserted = True
                break
            if offset == cur_offset:
                # Insert before non-text run
                r_pr = copy.deepcopy(it.r_pr)
                p.runs.insert(i, TextItem(text, r_pr))
                inserted = True
                break
        cur_offset += item_len

    if not inserted:
        # Append to the end
        if p.runs and p.runs[-1].t == "text":
            p.runs[-1].text += text
        else:
            r_pr = copy.deepcopy(p.runs[-1].r_pr if p.runs else p.r_pr)
            p.runs.append(TextItem(text, r_pr))


def delete_range_in_paragraph(p: Paragraph, start_off: int, end_off: int) -> None:
    """Delete characters from start_off to end_off in a paragraph."""
    if start_off >= end_off:
        return

    cur_offset = 0
    new_runs = []
    for it in p.runs:
        item_len = ilen(it)
        item_start = cur_offset
        item_end = cur_offset + item_len

        # Check overlap with [start_off, end_off]
        if item_end <= start_off or item_start >= end_off:
            new_runs.append(it)
        else:
            if it.t == "text":
                txt = getattr(it, "text", "")
                # Retain portions outside [start_off, end_off]
                left_cut = max(0, start_off - item_start)
                right_cut = max(0, min(item_len, end_off - item_start))
                remaining = txt[:left_cut] + txt[right_cut:]
                if remaining:
                    it.text = remaining
                    new_runs.append(it)
            else:
                # Non-text run falling within delete range is deleted
                pass
        cur_offset += item_len

    p.runs = new_runs


def split_paragraph(p: Paragraph, offset: int) -> Paragraph:
    """Split a paragraph at character offset, returning the new second paragraph."""
    p2 = Paragraph(p_pr=copy.deepcopy(p.p_pr), r_pr=copy.deepcopy(p.r_pr))
    cur_offset = 0
    p1_runs = []
    p2_runs = []

    for it in p.runs:
        item_len = ilen(it)
        item_start = cur_offset
        item_end = cur_offset + item_len

        if item_end <= offset:
            p1_runs.append(it)
        elif item_start >= offset:
            p2_runs.append(it)
        else:
            # Boundary falls inside item
            if it.t == "text":
                txt = getattr(it, "text", "")
                split_at = offset - item_start
                it1 = copy.deepcopy(it)
                it1.text = txt[:split_at]
                it2 = copy.deepcopy(it)
                it2.text = txt[split_at:]
                if it1.text:
                    p1_runs.append(it1)
                if it2.text:
                    p2_runs.append(it2)
            else:
                p2_runs.append(it)
        cur_offset += item_len

    p.runs = p1_runs
    p2.runs = p2_runs
    return p2


# ---------------------------------------------------------------------------
# CaretController Class
# ---------------------------------------------------------------------------


class CaretController(QObject):
    """In-place caret and selection controller for Quire document editing."""

    caret_changed = Signal()
    selection_changed = Signal()
    document_modified = Signal()

    def __init__(
        self,
        doc: Document | None = None,
        pagination: PaginationResult | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc: Document = doc or Document()
        self.pagination: PaginationResult = pagination or paginate_document(self.doc)

        # Initialize position to first paragraph
        first_p = self._first_paragraph()
        p_id = first_p.id if first_p else 0
        self.pos: DocPos = DocPos(p_id, 0)
        self.selection: Selection = Selection(self.pos, self.pos)

        # Visual state
        self.caret_visible: bool = True
        self.preferred_x: float | None = None

        # Blinking timer (500 ms)
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._blink_timer.start()

    def set_document_and_pagination(
        self, doc: Document, pagination: PaginationResult
    ) -> None:
        """Update active document model and pagination result."""
        self.doc = doc
        self.pagination = pagination
        self._ensure_valid_pos()
        self.caret_changed.emit()

    def _first_paragraph(self) -> Paragraph | None:
        paras = all_paragraphs(self.doc)
        return paras[0] if paras else None

    def _last_paragraph(self) -> Paragraph | None:
        paras = all_paragraphs(self.doc)
        return paras[-1] if paras else None

    def _paragraph_by_id(self, pid: int) -> Paragraph | None:
        inf = info(self.doc, pid)
        return inf["p"] if inf and "p" in inf else None

    def _ensure_valid_pos(self) -> None:
        p = self._paragraph_by_id(self.pos.para_id)
        if not p:
            first_p = self._first_paragraph()
            if first_p:
                self.pos = DocPos(first_p.id, 0)
                self.selection = Selection(self.pos, self.pos)
        else:
            length = plen(p)
            if self.pos.offset > length:
                self.pos = DocPos(p.id, length)
            if self.selection.is_collapsed:
                self.selection = Selection(self.pos, self.pos)

    def _toggle_blink(self) -> None:
        self.caret_visible = not self.caret_visible
        self.caret_changed.emit()

    def reset_blink(self) -> None:
        """Reset blink cycle so caret is instantly visible upon user activity."""
        self.caret_visible = True
        self._blink_timer.start()
        self.caret_changed.emit()

    # -----------------------------------------------------------------------
    # Coordinate Mapping & Hit-Testing
    # -----------------------------------------------------------------------

    def pos_to_canvas(self, pos: DocPos) -> tuple[int, QPointF, float]:
        """Convert a document position to physical page index, page point (pt), and caret height (pt)."""
        if not self.pagination or not self.pagination.pages:
            return 0, QPointF(90.0, 72.0), 15.6

        target_pid = pos.para_id
        target_off = pos.offset

        for p_idx, page in enumerate(self.pagination.pages):
            for reg in page.regions:
                for col in reg.columns:
                    for frag in col.fragments:
                        if frag.paragraph.id != target_pid:
                            continue

                        cur_line_top = page.body_top + col.top + frag.top
                        for line in frag.lines:
                            line_y = cur_line_top + line.top
                            line_h = max(line.height, 14.0)

                            # Determine line character span
                            if not line.portions:
                                # Empty line
                                return p_idx, QPointF(page.body_left + col.left + line.indent_left, line_y), line_h

                            l_start = line.portions[0].char_offset
                            l_end = line.portions[-1].char_offset + line.portions[-1].length

                            if l_start <= target_off <= l_end or line is frag.lines[-1]:
                                x = page.body_left + col.left + line.indent_left
                                for po in line.portions:
                                    po_start = po.char_offset
                                    po_end = po_start + po.length
                                    if target_off >= po_end:
                                        x += po.width
                                    else:
                                        # Inside this portion
                                        char_cnt = max(0, target_off - po_start)
                                        substr = po.text[:char_cnt]
                                        sub_w = measure_text_width(
                                            substr, po.font_size, po.font_family
                                        )
                                        x += sub_w
                                        return p_idx, QPointF(x, line_y), line_h
                                return p_idx, QPointF(x, line_y), line_h

        # Fallback to page 0
        p0 = self.pagination.pages[0]
        return 0, QPointF(p0.body_left, p0.body_top), 15.6

    def canvas_to_pos(self, page_idx: int, point_pt: QPointF) -> DocPos:
        """Convert physical page coordinates (in points) to the nearest DocPos using binary search."""
        if not self.pagination or not self.pagination.pages:
            first_p = self._first_paragraph()
            return DocPos(first_p.id if first_p else 0, 0)

        clamped_page = max(0, min(page_idx, len(self.pagination.pages) - 1))
        page = self.pagination.pages[clamped_page]

        # Collect all fragments on this page
        all_frags: list[tuple[ColumnFrame, PageFragment]] = []
        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    all_frags.append((col, frag))

        if not all_frags:
            first_p = self._first_paragraph()
            return DocPos(first_p.id if first_p else 0, 0)

        # Find closest fragment by vertical position
        target_y = point_pt.y()
        best_col, best_frag = all_frags[0]
        min_y_dist = float("inf")

        for col, frag in all_frags:
            f_top = page.body_top + col.top + frag.top
            f_bottom = f_top + frag.height
            if f_top <= target_y <= f_bottom:
                best_col, best_frag = col, frag
                min_y_dist = 0
                break
            dist = min(abs(target_y - f_top), abs(target_y - f_bottom))
            if dist < min_y_dist:
                min_y_dist = dist
                best_col, best_frag = col, frag

        if not best_frag.lines:
            return DocPos(best_frag.paragraph.id, 0)

        # Find closest line in best_frag
        best_line = best_frag.lines[0]
        min_line_dist = float("inf")
        cur_frag_top = page.body_top + best_col.top + best_frag.top

        for line in best_frag.lines:
            l_top = cur_frag_top + line.top
            l_bottom = l_top + line.height
            if l_top <= target_y <= l_bottom:
                best_line = line
                min_line_dist = 0
                break
            dist = min(abs(target_y - l_top), abs(target_y - l_bottom))
            if dist < min_line_dist:
                min_line_dist = dist
                best_line = line

        if not best_line.portions:
            return DocPos(best_frag.paragraph.id, 0)

        # Search across portions on this line
        line_start_x = page.body_left + best_col.left + best_line.indent_left
        target_x = point_pt.x()

        if target_x <= line_start_x:
            return DocPos(best_frag.paragraph.id, best_line.portions[0].char_offset)

        cur_x = line_start_x
        for po in best_line.portions:
            po_end_x = cur_x + po.width
            if target_x <= po_end_x or po is best_line.portions[-1]:
                # Binary search within this portion
                return DocPos(
                    best_frag.paragraph.id,
                    self._binary_search_char_offset(po, cur_x, target_x),
                )
            cur_x = po_end_x

        last_po = best_line.portions[-1]
        return DocPos(best_frag.paragraph.id, last_po.char_offset + last_po.length)

    def _binary_search_char_offset(
        self, portion: Portion, portion_start_x: float, target_x: float
    ) -> int:
        """Find character offset within portion closest to target_x using binary search."""
        text = portion.text
        length = len(text)
        if length == 0:
            return portion.char_offset

        low = 0
        high = length
        rel_target = target_x - portion_start_x

        # Precompute character cumulative widths or bisect
        while low < high:
            mid = (low + high) // 2
            w = measure_text_width(text[:mid], portion.font_size, portion.font_family)
            if w < rel_target:
                low = mid + 1
            else:
                high = mid

        # Check between low-1 and low to see which boundary is closer
        idx1 = max(0, low - 1)
        idx2 = min(length, low)
        w1 = measure_text_width(text[:idx1], portion.font_size, portion.font_family)
        w2 = measure_text_width(text[:idx2], portion.font_size, portion.font_family)

        chosen = idx2 if abs(rel_target - w2) < abs(rel_target - w1) else idx1
        return portion.char_offset + chosen

    # -----------------------------------------------------------------------
    # Selection & Navigation Methods
    # -----------------------------------------------------------------------

    def set_pos(
        self,
        pos: DocPos,
        extend_selection: bool = False,
        reset_preferred_x: bool = True,
    ) -> None:
        """Set active caret position, optionally extending selection."""
        p = self._paragraph_by_id(pos.para_id)
        if p:
            pos = DocPos(p.id, max(0, min(pos.offset, plen(p))))
        self.pos = pos
        if extend_selection:
            self.selection.focus = pos
        else:
            self.selection = Selection(pos, pos)

        if reset_preferred_x:
            self.preferred_x = None

        self.reset_blink()
        self.selection_changed.emit()
        self.caret_changed.emit()

    def select_word_at(self, pos: DocPos) -> None:
        """Select the word around pos."""
        p = self._paragraph_by_id(pos.para_id)
        if not p:
            return
        txt = ptext(p)
        off = pos.offset
        if not txt:
            self.set_pos(pos)
            return

        # Find word boundaries using regex
        matches = list(re.finditer(r"\w+|[^\w\s]+|\s+", txt))
        for m in matches:
            if m.start() <= off <= m.end():
                self.selection = Selection(
                    DocPos(p.id, m.start()), DocPos(p.id, m.end())
                )
                self.pos = self.selection.focus
                self.preferred_x = None
                self.reset_blink()
                self.selection_changed.emit()
                self.caret_changed.emit()
                return

        self.set_pos(pos)

    def select_paragraph_at(self, pos: DocPos) -> None:
        """Select the entire paragraph containing pos."""
        p = self._paragraph_by_id(pos.para_id)
        if not p:
            return
        self.selection = Selection(DocPos(p.id, 0), DocPos(p.id, plen(p)))
        self.pos = self.selection.focus
        self.preferred_x = None
        self.reset_blink()
        self.selection_changed.emit()
        self.caret_changed.emit()

    def select_all(self) -> None:
        """Select all text in document."""
        first_p = self._first_paragraph()
        last_p = self._last_paragraph()
        if not first_p or not last_p:
            return
        self.selection = Selection(DocPos(first_p.id, 0), DocPos(last_p.id, plen(last_p)))
        self.pos = self.selection.focus
        self.preferred_x = None
        self.reset_blink()
        self.selection_changed.emit()
        self.caret_changed.emit()

    def move_left(self, extend: bool = False) -> None:
        """Move caret one character to the left."""
        if not extend and not self.selection.is_collapsed:
            start_pos, _ = self.selection.ordered_range(self.doc)
            self.set_pos(start_pos, extend_selection=False)
            return

        if self.pos.offset > 0:
            self.set_pos(
                DocPos(self.pos.para_id, self.pos.offset - 1), extend_selection=extend
            )
        else:
            # Move to end of previous paragraph
            inf = info(self.doc, self.pos.para_id)
            if inf and "p" in inf:
                paras = all_paragraphs(self.doc)
                idx = inf["p"]._o
                if idx > 0:
                    prev_p = paras[idx - 1]
                    self.set_pos(
                        DocPos(prev_p.id, plen(prev_p)), extend_selection=extend
                    )

    def move_right(self, extend: bool = False) -> None:
        """Move caret one character to the right."""
        if not extend and not self.selection.is_collapsed:
            _, end_pos = self.selection.ordered_range(self.doc)
            self.set_pos(end_pos, extend_selection=False)
            return

        p = self._paragraph_by_id(self.pos.para_id)
        if not p:
            return

        if self.pos.offset < plen(p):
            self.set_pos(
                DocPos(self.pos.para_id, self.pos.offset + 1), extend_selection=extend
            )
        else:
            # Move to start of next paragraph
            inf = info(self.doc, self.pos.para_id)
            if inf and "p" in inf:
                paras = all_paragraphs(self.doc)
                idx = inf["p"]._o
                if idx + 1 < len(paras):
                    next_p = paras[idx + 1]
                    self.set_pos(DocPos(next_p.id, 0), extend_selection=extend)

    def move_up(self, extend: bool = False) -> None:
        """Move caret up to the line above, maintaining preferred horizontal coordinate."""
        page_idx, pt, _ = self.pos_to_canvas(self.pos)
        if self.preferred_x is None:
            self.preferred_x = pt.x()

        # Target point ~15pt above current line top
        target_pt = QPointF(self.preferred_x, pt.y() - 15.0)
        target_page = page_idx
        if target_pt.y() < 0 and page_idx > 0:
            target_page = page_idx - 1
            prev_page = self.pagination.pages[target_page]
            target_pt.setY(prev_page.height - 20.0)

        new_pos = self.canvas_to_pos(target_page, target_pt)
        self.set_pos(new_pos, extend_selection=extend, reset_preferred_x=False)

    def move_down(self, extend: bool = False) -> None:
        """Move caret down to the line below, maintaining preferred horizontal coordinate."""
        page_idx, pt, h = self.pos_to_canvas(self.pos)
        if self.preferred_x is None:
            self.preferred_x = pt.x()

        # Target point ~15pt below current line bottom
        target_pt = QPointF(self.preferred_x, pt.y() + h + 10.0)
        target_page = page_idx
        if (
            target_pt.y() > self.pagination.pages[page_idx].height
            and page_idx + 1 < len(self.pagination.pages)
        ):
            target_page = page_idx + 1
            target_pt.setY(20.0)

        new_pos = self.canvas_to_pos(target_page, target_pt)
        self.set_pos(new_pos, extend_selection=extend, reset_preferred_x=False)

    def move_line_start(self, extend: bool = False) -> None:
        """Move caret to the beginning of the current layout line."""
        page_idx, pt, _ = self.pos_to_canvas(self.pos)
        new_pos = self.canvas_to_pos(page_idx, QPointF(0.0, pt.y() + 2.0))
        self.set_pos(new_pos, extend_selection=extend)

    def move_line_end(self, extend: bool = False) -> None:
        """Move caret to the end of the current layout line."""
        page_idx, pt, _ = self.pos_to_canvas(self.pos)
        page = self.pagination.pages[page_idx]
        new_pos = self.canvas_to_pos(page_idx, QPointF(page.width, pt.y() + 2.0))
        self.set_pos(new_pos, extend_selection=extend)

    def move_doc_start(self, extend: bool = False) -> None:
        """Move caret to start of document."""
        first_p = self._first_paragraph()
        if first_p:
            self.set_pos(DocPos(first_p.id, 0), extend_selection=extend)

    def move_doc_end(self, extend: bool = False) -> None:
        """Move caret to end of document."""
        last_p = self._last_paragraph()
        if last_p:
            self.set_pos(DocPos(last_p.id, plen(last_p)), extend_selection=extend)

    # -----------------------------------------------------------------------
    # Editing Operations
    # -----------------------------------------------------------------------

    def delete_selection(self) -> bool:
        """Delete active selection range if non-collapsed."""
        if self.selection.is_collapsed:
            return False

        start, end = self.selection.ordered_range(self.doc)
        p_start = self._paragraph_by_id(start.para_id)
        p_end = self._paragraph_by_id(end.para_id)

        if not p_start or not p_end:
            return False

        if start.para_id == end.para_id:
            delete_range_in_paragraph(p_start, start.offset, end.offset)
        else:
            # Delete across paragraphs
            delete_range_in_paragraph(p_start, start.offset, plen(p_start))
            delete_range_in_paragraph(p_end, 0, end.offset)

            # Intermediate paragraphs
            paras = all_paragraphs(self.doc)
            idx_s = p_start._o
            idx_e = p_end._o

            # Append remaining runs of p_end into p_start
            p_start.runs.extend(p_end.runs)

            # Remove p_end and intermediate paragraphs from story
            story: Story = self.doc.main
            remove_ids = {
                paras[k].id for k in range(min(idx_s + 1, idx_e), idx_e + 1)
            }
            story.blocks = [
                b
                for b in story.blocks
                if not (isinstance(b, Paragraph) and b.id in remove_ids)
            ]

        self.pos = start
        self.selection = Selection(start, start)
        self.repaginate_and_refresh()
        return True

    def insert_text(self, text: str) -> None:
        """Insert text at caret position, advancing caret."""
        if not text:
            return

        if not self.selection.is_collapsed:
            self.delete_selection()

        p = self._paragraph_by_id(self.pos.para_id)
        if not p:
            first_p = self._first_paragraph()
            if not first_p:
                first_p = Paragraph()
                self.doc.main.blocks.append(first_p)
                reindex(self.doc)
            p = first_p
            self.pos = DocPos(p.id, 0)

        insert_text_in_paragraph(p, self.pos.offset, text)
        self.pos = DocPos(p.id, self.pos.offset + len(text))
        self.selection = Selection(self.pos, self.pos)
        self.preferred_x = None
        self.repaginate_and_refresh()

    def delete_backspace(self) -> None:
        """Handle Backspace key: delete selection, delete char, or merge paragraphs."""
        if not self.selection.is_collapsed:
            self.delete_selection()
            return

        p = self._paragraph_by_id(self.pos.para_id)
        if not p:
            return

        if self.pos.offset > 0:
            delete_range_in_paragraph(p, self.pos.offset - 1, self.pos.offset)
            self.pos = DocPos(p.id, self.pos.offset - 1)
            self.selection = Selection(self.pos, self.pos)
            self.preferred_x = None
            self.repaginate_and_refresh()
        else:
            # At offset 0: merge with preceding paragraph
            inf = info(self.doc, p.id)
            if not inf or "p" not in inf:
                return
            paras = all_paragraphs(self.doc)
            idx = inf["p"]._o
            if idx > 0:
                prev_p = paras[idx - 1]
                target_offset = plen(prev_p)
                prev_p.runs.extend(p.runs)

                # Remove current paragraph
                self.doc.main.blocks = [
                    b
                    for b in self.doc.main.blocks
                    if not (isinstance(b, Paragraph) and b.id == p.id)
                ]
                self.pos = DocPos(prev_p.id, target_offset)
                self.selection = Selection(self.pos, self.pos)
                self.preferred_x = None
                self.repaginate_and_refresh()

    def delete_forward(self) -> None:
        """Handle Delete key: delete selection, delete char forward, or merge next paragraph."""
        if not self.selection.is_collapsed:
            self.delete_selection()
            return

        p = self._paragraph_by_id(self.pos.para_id)
        if not p:
            return

        length = plen(p)
        if self.pos.offset < length:
            delete_range_in_paragraph(p, self.pos.offset, self.pos.offset + 1)
            self.preferred_x = None
            self.repaginate_and_refresh()
        else:
            # At offset == plen: merge next paragraph into current
            inf = info(self.doc, p.id)
            if not inf or "p" not in inf:
                return
            paras = all_paragraphs(self.doc)
            idx = inf["p"]._o
            if idx + 1 < len(paras):
                next_p = paras[idx + 1]
                p.runs.extend(next_p.runs)

                # Remove next paragraph
                self.doc.main.blocks = [
                    b
                    for b in self.doc.main.blocks
                    if not (isinstance(b, Paragraph) and b.id == next_p.id)
                ]
                self.preferred_x = None
                self.repaginate_and_refresh()

    def insert_paragraph_break(self) -> None:
        """Handle Enter / Return key: split paragraph into two."""
        if not self.selection.is_collapsed:
            self.delete_selection()

        p = self._paragraph_by_id(self.pos.para_id)
        if not p:
            return

        p2 = split_paragraph(p, self.pos.offset)

        # Insert p2 after p in main blocks
        blocks = self.doc.main.blocks
        for i, b in enumerate(blocks):
            if isinstance(b, Paragraph) and b.id == p.id:
                blocks.insert(i + 1, p2)
                break
        else:
            blocks.append(p2)

        self.pos = DocPos(p2.id, 0)
        self.selection = Selection(self.pos, self.pos)
        self.preferred_x = None
        self.repaginate_and_refresh()

    def repaginate_and_refresh(self) -> None:
        """Reindex document DOM, repaginate, and notify listeners."""
        reindex(self.doc)
        self.pagination = paginate_document(self.doc)
        self.reset_blink()
        self.document_modified.emit()
        self.selection_changed.emit()
        self.caret_changed.emit()

    def handle_key_event(self, event: QKeyEvent) -> bool:
        """Process keyboard navigation and editing shortcuts."""
        key = event.key()
        modifiers = event.modifiers()
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(
            modifiers
            & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        )

        if key == Qt.Key.Key_Left:
            self.move_left(extend=shift)
            return True
        if key == Qt.Key.Key_Right:
            self.move_right(extend=shift)
            return True
        if key == Qt.Key.Key_Up:
            self.move_up(extend=shift)
            return True
        if key == Qt.Key.Key_Down:
            self.move_down(extend=shift)
            return True
        if key == Qt.Key.Key_Home:
            if ctrl:
                self.move_doc_start(extend=shift)
            else:
                self.move_line_start(extend=shift)
            return True
        if key == Qt.Key.Key_End:
            if ctrl:
                self.move_doc_end(extend=shift)
            else:
                self.move_line_end(extend=shift)
            return True
        if key == Qt.Key.Key_Backspace:
            self.delete_backspace()
            return True
        if key == Qt.Key.Key_Delete:
            self.delete_forward()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.insert_paragraph_break()
            return True
        if ctrl and key == Qt.Key.Key_A:
            self.select_all()
            return True

        text = event.text()
        if text and text.isprintable():
            self.insert_text(text)
            return True

        return False
