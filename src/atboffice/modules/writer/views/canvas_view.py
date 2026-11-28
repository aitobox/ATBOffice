"""Word 2003 high-fidelity paper canvas viewport for Quire word processing."""

from __future__ import annotations

import copy
import logging
import math
from typing import Any

from PySide6.QtCore import (
    QPoint,
    QPointF,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QWidget,
)

from atboffice.core.i18n import safe_tr
from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.core.undo import UndoService
from atboffice.modules.writer.layout.pagination import (
    Page,
    PaginationResult,
    paginate_document,
)
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    reindex,
)
from atboffice.modules.writer.models.properties import (
    RunProperties,
)
from atboffice.modules.writer.spell import SpellEngine
from atboffice.modules.writer.views.canvas_common import (  # noqa: F401  re-exported
    _UNDERLINE_PEN_STYLES,
    _WAVY_UNDERLINES,
    COLOR_CARET,
    COLOR_MARGIN_GUIDE,
    COLOR_PAGE_BORDER,
    COLOR_PAGE_PAPER,
    COLOR_SELECTION,
    COLOR_SHADOW_DARK,
    COLOR_SHADOW_LIGHT,
    COLOR_WORKSPACE_BG,
    WORD_HIGHLIGHT_COLORS,
    _undoable,
    _undoable_document,
)
from atboffice.modules.writer.views.canvas_editing import CanvasEditingMixin
from atboffice.modules.writer.views.canvas_input import CanvasInputMixin
from atboffice.modules.writer.views.canvas_paint import CanvasPaintMixin
from atboffice.modules.writer.views.canvas_paint_objects import CanvasObjectPaintMixin
from atboffice.modules.writer.views.caret_controller import (
    CaretController,
)
from atboffice.modules.writer.views.text_history import TextEditRecorder
from atboffice.modules.writer.views.view_modes import ViewMode

logger = logging.getLogger(__name__)


class WriterCanvasView(
    CanvasObjectPaintMixin,
    CanvasPaintMixin,
    CanvasInputMixin,
    CanvasEditingMixin,
    QAbstractScrollArea,
):
    """Word 2003 styled physical paper canvas viewport."""

    zoom_changed = Signal(float)
    caret_moved = Signal(int, int)  # para_id, offset
    view_mode_changed = Signal(object)
    header_footer_requested = Signal(str)  # "hdr" / "ftr"
    float_selected = Signal(object)  # PictureItem / ShapeItem / None
    table_tool_changed = Signal(object)  # "draw" / "erase" / None

    def __init__(
        self,
        doc: Document | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        from atboffice.utils.font_registry import register_bundled_fonts

        register_bundled_fonts()
        self.view_mode: ViewMode = ViewMode.PRINT
        self.doc: Document = doc or Document()
        if not self.doc.main.blocks:
            self.doc.main.blocks.append(Paragraph())
        reindex(self.doc)

        self.pagination: PaginationResult = paginate_document(self.doc)
        self.controller = CaretController(self.doc, self.pagination, self)
        self.spell_engine: SpellEngine = SpellEngine.get_instance()

        # Zoom settings: 50% to 400%
        self._zoom: float = 1.0
        self._printing: bool = False
        self._print_device: Any = None
        self._min_zoom: float = 0.5
        self._max_zoom: float = 4.0
        self.pt_to_px_ratio: float = 96.0 / 72.0  # 1.33333
        self.page_gap_pt: float = 20.0
        # View options driven by the Standard / Reviewing toolbars (issue #443).
        self.show_formatting_marks: bool = False
        # Review display mode: final_markup | final | original_markup | original
        self.revision_view: str = "final_markup"
        self.show_comments: bool = True
        self.show_ins_del: bool = True
        self.show_formatting_changes: bool = True
        # Format Painter: run properties captured from the caret, applied on the next selection.
        self.format_painter_props: RunProperties | None = None
        self.format_painter_sticky: bool = False

        # Mouse drag state
        self._is_dragging: bool = False

        # Table divider interactive resizing & interactive Draw Table / Eraser tools
        self._resizing_table: bool = False
        self._table_tool: str | None = None
        self._table_draw_start: QPoint | None = None
        self._table_draw_current: QPoint | None = None
        self._table_draw_start_cell: dict[str, Any] | None = None
        self._float_sel: tuple[int, Any] | None = None  # (page index, drawing item)
        self._float_drag: Any = None
        self.hf_edit_kind: str | None = None  # header/footer being edited (body dimmed)
        self._resize_info: dict[str, Any] | None = None
        self._resize_guide_pos: QPoint | None = None

        # Ruler guide lines (canvas coordinates)
        self._ruler_guide_x: float | None = None
        self._ruler_guide_y: float | None = None

        # Undo / redo history; typing and deleting are recorded by the controller.
        self.history = UndoService(self)
        self.controller.edit_recorder = TextEditRecorder(self)

        # Inline & floating picture raster pixmap cache
        self._pixmap_cache: dict[str, QPixmap] = {}

        # Connect controller signals
        self.controller.caret_changed.connect(self._on_caret_changed)
        self.controller.selection_changed.connect(self.viewport().update)
        self.controller.document_modified.connect(self._on_document_modified)

        # Setup scroll area and viewport attributes
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setMouseTracking(True)
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.retranslate_ui()
        self._update_scroll_ranges()

    # -----------------------------------------------------------------------
    # Document & Pagination Handling
    # -----------------------------------------------------------------------

    def set_document(self, doc: Document) -> None:
        """Set a new document and repaginate."""
        self._pixmap_cache.clear()
        self.history.clear()
        self._float_sel = None
        self._float_drag = None
        self.hf_edit_kind = None
        if self._table_tool is not None:
            self.set_table_tool(None)
        self.doc = doc
        if not self.doc.main.blocks:
            self.doc.main.blocks.append(Paragraph())
        reindex(self.doc)
        self.pagination = paginate_document(self.doc)
        self.controller.set_document_and_pagination(self.doc, self.pagination)
        self._update_scroll_ranges()
        self.viewport().update()

    def refresh_layout(self) -> None:
        """Repaginate the current document in place after an edit.

        Unlike :meth:`set_document`, this keeps the undo/redo history, the image
        cache, the caret and the selection.
        """
        if not self.doc.main.blocks:
            self.doc.main.blocks.append(Paragraph())
        # Reindex first: a stale index still finds paragraphs that were removed.
        reindex(self.doc)
        self.controller.doc = self.doc
        self.controller._ensure_valid_pos()
        # Emits document_modified, which syncs self.pagination and the scroll ranges.
        self.controller.repaginate_and_refresh()
        self.pagination = self.controller.pagination
        self._update_scroll_ranges()
        self.viewport().update()

    @property
    def table_tool(self) -> str | None:
        """Return active interactive table tool (``'draw'``, ``'erase'``, or ``None``)."""
        return getattr(self, "_table_tool", None)

    def set_table_tool(self, kind: str | None) -> None:
        """Toggle or clear interactive Draw Table pen / Eraser tool mode."""
        from atboffice.modules.writer.views.canvas_table_tool import set_table_tool

        set_table_tool(self, kind)

    def _on_document_modified(self) -> None:
        self.pagination = self.controller.pagination
        self._update_scroll_ranges()
        self.viewport().update()

    # -----------------------------------------------------------------------
    # Undo / Redo Transaction Engine
    # -----------------------------------------------------------------------

    # Document parts a dialog-driven edit may change; snapshotted for undo/redo.
    _SNAPSHOT_PARTS: tuple[str, ...] = (
        "main",
        "sect",
        "hf",
        "fn",
        "en",
        "comments",
        "settings",
        "styles",
        "numbering",
    )

    def _snapshot_doc(self) -> dict[str, Any]:

        return {attr: copy.deepcopy(getattr(self.doc, attr)) for attr in self._SNAPSHOT_PARTS}

    def run_undoable(self, mutate: Any, label: str | None = None) -> Any:
        """Run ``mutate()`` on the document as one undoable step and relayout.

        Used by dialog and toolbar commands that change arbitrary document parts.
        Nothing is recorded when ``mutate`` returns ``False``.
        """
        if not self.history.is_recording:
            result = mutate()
            if result is not False:
                self.refresh_layout()
            return result
        before = self._snapshot_doc()
        with self.history.paused():
            result = mutate()
        if result is False:
            return result
        after = self._snapshot_doc()
        if after != before:
            self.history.record_states(
                label or core_safe_tr("编辑"), before, after, self._restore_doc_snapshot
            )
        self.refresh_layout()
        return result

    def _restore_doc_snapshot(self, state: dict[str, Any]) -> None:
        self._apply_command_state({"type": "doc_snapshot", "before": state}, is_undo=True)

    def push_undo_command(self, cmd: dict[str, Any]) -> None:
        """Record an already-applied ``{"type", "before", "after"}`` change."""
        from atboffice.ui.components.undo_history import entry_label

        self.history.record(
            entry_label(cmd),
            lambda: self._apply_command_state(cmd, is_undo=True),
            lambda: self._apply_command_state(cmd, is_undo=False),
            data=cmd,
        )
        self.controller.document_modified.emit()

    def can_undo(self) -> bool:
        """Return True if there are actions that can be undone."""
        return self.history.can_undo()

    def can_redo(self) -> bool:
        """Return True if there are undone actions that can be redone."""
        return self.history.can_redo()

    def undo(self) -> bool:
        """Undo the last editing or formatting command."""
        return self.history.undo()

    def redo(self) -> bool:
        """Redo the last undone command."""
        return self.history.redo()

    def _apply_command_state(self, cmd: dict[str, Any], is_undo: bool) -> None:
        """Apply the before or after state of a transaction command."""

        state = cmd["before"] if is_undo else cmd["after"]
        cmd_type = cmd.get("type")

        if cmd_type == "paragraph_indent":
            p = self.controller._paragraph_by_id(cmd["para_id"])
            if p:
                p.indent_left = state.get("indent_left", p.indent_left)
                p.indent_first = state.get("indent_first", p.indent_first)
                p.indent_right = state.get("indent_right", p.indent_right)
        elif cmd_type == "paragraph_tabs":
            p = self.controller._paragraph_by_id(cmd["para_id"])
            if p:
                p.p_pr.tabs = copy.deepcopy(state)
        elif cmd_type == "doc_snapshot":
            for attr, value in state.items():
                setattr(self.doc, attr, copy.deepcopy(value))
            reindex(self.doc)
            self.controller.doc = self.doc
            self.controller._ensure_valid_pos()
        elif cmd_type == "section_margins":
            sect = cmd.get("sect")
            if sect:
                if "ml" in state:
                    sect.ml = state["ml"]
                if "mr" in state:
                    sect.mr = state["mr"]
                if "mt" in state:
                    sect.mt = state["mt"]
                if "mb" in state:
                    sect.mb = state["mb"]

        self.controller.repaginate_and_refresh()
        self.controller.document_modified.emit()

    def _on_caret_changed(self) -> None:
        self.caret_moved.emit(self.controller.pos.para_id, self.controller.pos.offset)
        self.viewport().update()

    # -----------------------------------------------------------------------
    # Coordinate Conversion Helpers
    # -----------------------------------------------------------------------

    @property
    def zoom(self) -> float:
        """Current zoom multiplier (1.0 = 100%)."""
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        """Set zoom scale factor clamped between min and max zoom."""
        clamped = max(self._min_zoom, min(self._max_zoom, zoom))
        if math.isclose(clamped, self._zoom, abs_tol=1e-4):
            return
        self._zoom = clamped
        self._update_scroll_ranges()
        self.zoom_changed.emit(self._zoom)
        self.viewport().update()

    def zoom_in(self) -> None:
        """Increase zoom by 10%."""
        self.set_zoom(self._zoom + 0.1)

    def zoom_out(self) -> None:
        """Decrease zoom by 10%."""
        self.set_zoom(self._zoom - 0.1)

    def pt_to_px(self, pt: float) -> float:
        """Convert document logical points to canvas pixels under active zoom."""
        if self._printing:
            return pt  # print mode paints in points (avoid ratio*zoom float drift)
        return pt * self.pt_to_px_ratio * self._zoom

    def px_to_pt(self, px: float) -> float:
        """Convert canvas pixels to document logical points."""
        if self._printing:
            return px
        return px / (self.pt_to_px_ratio * self._zoom)

    def _comment_gutter_px(self) -> float:
        """Reserve right-margin gutter for comment balloons when comments exist in print view."""
        if self.view_mode == ViewMode.PRINT and getattr(self.doc, "comments", None):
            return 230.0 * self._zoom
        return 0.0

    def total_canvas_size(self) -> QSize:
        """Compute the total bounding size (in px) of all pages stacked vertically."""
        if not self.pagination or not self.pagination.pages:
            return QSize(800, 600)
        if self.view_mode in (ViewMode.NORMAL, ViewMode.WEB, ViewMode.READING):
            slots = [clip for _rect, clip in self.page_slots() if not clip.isEmpty()]
            right = max(c.right() for c in slots) + 8.0
            bottom = max(c.bottom() for c in slots) + 24.0
            return QSize(int(math.ceil(right)), int(math.ceil(bottom)))

        max_w = 0.0
        total_h = 33.0  # Top padding aligning page top border (y=33) with baseline captures
        gap_px = self.pt_to_px(self.page_gap_pt)
        gutter_px = self._comment_gutter_px()

        for page in self.pagination.pages:
            w_px = self.pt_to_px(page.width) + gutter_px
            h_px = self.pt_to_px(page.height)
            if w_px > max_w:
                max_w = w_px
            total_h += h_px + gap_px

        total_h += 24.0  # Bottom padding
        max_w += 48.0  # Horizontal padding
        return QSize(int(math.ceil(max_w)), int(math.ceil(total_h)))

    def set_view_mode(self, mode: ViewMode | str) -> None:
        """Switch view display mode (print, normal, web, reading, outline)."""
        if isinstance(mode, str):
            mode = ViewMode(mode)
        if self.view_mode == mode:
            return
        leaving_web = self.view_mode == ViewMode.WEB
        leaving_reading = self.view_mode == ViewMode.READING
        self.view_mode = mode
        if leaving_reading and getattr(self, "_zoom_before_reading", None) is not None:
            self.set_zoom(self._zoom_before_reading)
            self._zoom_before_reading = None
        if mode == ViewMode.WEB or leaving_web:
            self._apply_web_width()
        if mode == ViewMode.READING and self.pagination and self.pagination.pages:
            # Reading Layout: two screens side by side fit the window, like Word
            pair_pt = sum(pg.width for pg in self.pagination.pages[:2]) + self.page_gap_pt
            avail = max(200.0, self.viewport().width() - 48.0)
            fit = avail / (pair_pt * self.pt_to_px_ratio)
            if fit < self._zoom:
                self._zoom_before_reading = self._zoom
                self.set_zoom(max(0.1, fit))
        self._update_scroll_ranges()
        self.viewport().update()
        self.view_mode_changed.emit(self.view_mode)

    def _apply_web_width(self) -> None:
        """Web Layout reflows text to the window: repaginate at the viewport width."""
        width = None
        if self.view_mode == ViewMode.WEB:
            width = max(144.0, self.viewport().width() / (self.pt_to_px_ratio * self._zoom))
        if getattr(self.doc, "_web_layout_width", None) == width:
            return
        self.doc._web_layout_width = width  # type: ignore[attr-defined]
        self.refresh_layout()

    def scroll_to_page(self, page_idx: int) -> None:
        """Scroll vertical scrollbar so page page_idx is visible at the top."""
        if not self.pagination or not self.pagination.pages:
            return
        rect = self.page_rect_canvas(page_idx)
        self.verticalScrollBar().setValue(int(rect.top() - 10))
        self.viewport().update()

    def scroll_to_paragraph(self, para_id: int) -> bool:
        """Locate paragraph on canvas and scroll it into view."""
        if not self.pagination or not self.pagination.pages:
            return False
        for p_idx, page in enumerate(self.pagination.pages):
            for reg in getattr(page, "regions", []):
                for col in getattr(reg, "columns", []):
                    for fr in getattr(col, "fragments", []):
                        if getattr(fr, "paragraph", None) and fr.paragraph.id == para_id:
                            p_rect = self.page_rect_canvas(p_idx)
                            target_y = p_rect.top() + self.pt_to_px(getattr(fr, "top", 0.0))
                            self.verticalScrollBar().setValue(max(0, int(target_y - 20)))
                            self.controller.set_caret(para_id, 0)
                            self.viewport().update()
                            return True
        return False

    # ---- view-mode page placement ------------------------------------------------
    def _content_height_pt(self, page: Page) -> float:
        """Bottom of the last laid-out line (Web Layout pages are endless)."""
        bottom = page.body_top
        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    bottom = max(bottom, page.body_top + col.top + frag.top + frag.height)
        return bottom + 18.0

    def page_slots(self) -> list[tuple[QRectF, QRectF]]:
        """Per page: (page rect, visible clip rect) in canvas px for the current view mode.

        * Print: pages one below the other with a gap (the paper).
        * Normal: only the text area of each page, stacked without gaps (no margins,
          headers or footers); page breaks are drawn as dotted lines.
        * Web: one page as wide as the window, as tall as its text.
        * Reading: two pages side by side.
        """
        pages = self.pagination.pages if self.pagination else []
        out: list[tuple[QRectF, QRectF]] = []
        if not pages:
            return out
        mode = self.view_mode
        if mode == ViewMode.NORMAL:
            cur_y = 8.0
            for page in pages:
                w_px = self.pt_to_px(page.width)
                top_px = self.pt_to_px(page.body_top)
                left_px = self.pt_to_px(page.body_left)
                body_px = self.pt_to_px(page.body_height)
                # The left margin collapses too: text starts near the window edge
                rect = QRectF(12.0 - left_px, cur_y - top_px, w_px, self.pt_to_px(page.height))
                clip_w = self.pt_to_px(page.body_width) + 24.0
                out.append((rect, QRectF(0.0, cur_y, clip_w, body_px)))
                cur_y += body_px
            return out
        if mode == ViewMode.WEB:
            page = pages[0]
            rect = QRectF(
                0.0, 0.0, self.pt_to_px(page.width), self.pt_to_px(self._content_height_pt(page))
            )
            out.append((rect, rect))
            for _extra in pages[1:]:
                out.append((QRectF(), QRectF()))
            return out
        gap_px = self.pt_to_px(self.page_gap_pt)
        if mode == ViewMode.READING:
            vp_w = float(self.viewport().width())
            cur_y = 24.0
            for i in range(0, len(pages), 2):
                pair = pages[i : i + 2]
                widths = [self.pt_to_px(pg.width) for pg in pair]
                total_w = sum(widths) + gap_px * (len(pair) - 1)
                x_px = max(24.0, (vp_w - total_w) / 2.0)
                row_h = 0.0
                for pg, w_px in zip(pair, widths):
                    h_px = self.pt_to_px(pg.height)
                    rect = QRectF(x_px, cur_y, w_px, h_px)
                    out.append((rect, rect))
                    x_px += w_px + gap_px
                    row_h = max(row_h, h_px)
                cur_y += row_h + gap_px
            return out
        vp_width = max(float(self.viewport().width()), self._print_canvas_width())
        gutter_px = self._comment_gutter_px()
        cur_y = 33.0
        for page in pages:
            w_px = self.pt_to_px(page.width)
            h_px = self.pt_to_px(page.height)
            x_px = max(0.0, (vp_width - gutter_px - w_px) / 2.0)
            rect = QRectF(x_px, cur_y, w_px, h_px)
            out.append((rect, rect))
            cur_y += h_px + gap_px
        return out

    def _print_canvas_width(self) -> float:
        gutter_px = self._comment_gutter_px()
        widths = [self.pt_to_px(p.width) + gutter_px for p in self.pagination.pages]
        return (max(widths) if widths else 600.0) + 48.0

    def page_rect_canvas(self, page_idx: int) -> QRectF:
        """Return the physical QRectF bounding box (in canvas px) of page page_idx."""
        if not self.pagination or not self.pagination.pages:
            return QRectF(24, 24, 600, 800)
        if self.view_mode in (ViewMode.NORMAL, ViewMode.WEB, ViewMode.READING):
            slots = self.page_slots()
            if 0 <= page_idx < len(slots):
                return slots[page_idx][0]
            return QRectF(24, 24, 600, 800)

        vp_width = max(float(self.viewport().width()), float(self.total_canvas_size().width()))
        gap_px = self.pt_to_px(self.page_gap_pt)
        gutter_px = self._comment_gutter_px()
        cur_y = 33.0

        for idx, page in enumerate(self.pagination.pages):
            w_px = self.pt_to_px(page.width)
            h_px = self.pt_to_px(page.height)
            x_px = max(0.0, (vp_width - gutter_px - w_px) / 2.0)

            if idx == page_idx:
                return QRectF(x_px, cur_y, w_px, h_px)
            cur_y += h_px + gap_px

        return QRectF(24, cur_y, 600, 800)

    def _update_scroll_ranges(self) -> None:
        total = self.total_canvas_size()
        vp_w = self.viewport().width()
        vp_h = self.viewport().height()

        h_bar = self.horizontalScrollBar()
        v_bar = self.verticalScrollBar()

        h_bar.setRange(0, max(0, total.width() - vp_w))
        v_bar.setRange(0, max(0, total.height() - vp_h))
        h_bar.setPageStep(vp_w)
        v_bar.setPageStep(vp_h)

    def viewport_to_canvas(self, vp_pt: QPoint) -> QPointF:
        """Convert viewport pixel coordinates to virtual canvas coordinates."""
        return QPointF(
            vp_pt.x() + self.horizontalScrollBar().value(),
            vp_pt.y() + self.verticalScrollBar().value(),
        )

    def canvas_to_viewport(self, canvas_pt: QPointF) -> QPointF:
        """Convert virtual canvas coordinates to viewport coordinates."""
        return QPointF(
            canvas_pt.x() - self.horizontalScrollBar().value(),
            canvas_pt.y() - self.verticalScrollBar().value(),
        )

    def viewport_to_doc_coords(self, vp_pt: QPoint) -> tuple[int, QPointF]:
        """Convert viewport coordinates to (page_index, page_relative_point_in_points)."""
        canvas_pt = self.viewport_to_canvas(vp_pt)
        if not self.pagination or not self.pagination.pages:
            return 0, QPointF(0.0, 0.0)

        # Check which page rect encloses or is closest to canvas_pt.y
        best_page = 0
        min_dist = float("inf")

        slots = (
            self.page_slots()
            if self.view_mode in (ViewMode.NORMAL, ViewMode.WEB, ViewMode.READING)
            else None
        )
        for idx in range(len(self.pagination.pages)):
            rect = self.page_rect_canvas(idx)
            if slots is not None:
                rect = slots[idx][1]  # the visible part (Normal stacks text areas only)
                if rect.isEmpty():
                    continue
                if self.view_mode == ViewMode.READING and not (
                    rect.left() <= canvas_pt.x() <= rect.right()
                ):
                    if rect.top() <= canvas_pt.y() <= rect.bottom():
                        continue
            if rect.top() <= canvas_pt.y() <= rect.bottom():
                best_page = idx
                min_dist = 0
                break
            dist = min(abs(canvas_pt.y() - rect.top()), abs(canvas_pt.y() - rect.bottom()))
            if dist < min_dist:
                min_dist = dist
                best_page = idx

        rect = self.page_rect_canvas(best_page)
        rel_x_px = canvas_pt.x() - rect.left()
        rel_y_px = canvas_pt.y() - rect.top()

        pt_x = self.px_to_pt(rel_x_px)
        pt_y = self.px_to_pt(rel_y_px)
        return best_page, QPointF(pt_x, pt_y)

    def scroll_to_caret(self) -> None:
        """Ensure caret is visible within the viewport."""
        page_idx, pt_page, h_pt = self.controller.pos_to_canvas(self.controller.pos)
        page_rect = self.page_rect_canvas(page_idx)

        caret_canvas_x = page_rect.left() + self.pt_to_px(pt_page.x())
        caret_canvas_y = page_rect.top() + self.pt_to_px(pt_page.y())
        caret_canvas_h = self.pt_to_px(h_pt)

        vp_w = self.viewport().width()
        vp_h = self.viewport().height()
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()

        # Check horizontal bounds
        margin = 40
        if caret_canvas_x < scroll_x + margin:
            self.horizontalScrollBar().setValue(int(max(0, caret_canvas_x - margin)))
        elif caret_canvas_x > scroll_x + vp_w - margin:
            self.horizontalScrollBar().setValue(int(caret_canvas_x - vp_w + margin))

        # Check vertical bounds
        if caret_canvas_y < scroll_y + margin:
            self.verticalScrollBar().setValue(int(max(0, caret_canvas_y - margin)))
        elif caret_canvas_y + caret_canvas_h > scroll_y + vp_h - margin:
            self.verticalScrollBar().setValue(int(caret_canvas_y + caret_canvas_h - vp_h + margin))

    # -----------------------------------------------------------------------
    # Painting & Rendering Pipeline
    # -----------------------------------------------------------------------

    def set_ruler_guide(self, x: float | None = None, y: float | None = None) -> None:
        """Set alignment guide line position in virtual canvas coordinates and repaint."""
        self._ruler_guide_x = x
        self._ruler_guide_y = y
        self.viewport().update()

    def clear_ruler_guide(self) -> None:
        """Clear active ruler alignment guide lines and repaint."""
        if self._ruler_guide_x is not None or self._ruler_guide_y is not None:
            self._ruler_guide_x = None
            self._ruler_guide_y = None
            self.viewport().update()

    # -----------------------------------------------------------------------
    # Mouse & Keyboard Event Handlers
    # -----------------------------------------------------------------------

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Update scroll ranges and repaginate/repaint upon resize."""
        super().resizeEvent(event)
        if self.view_mode == ViewMode.WEB:
            self._apply_web_width()
        self._update_scroll_ranges()

    # -----------------------------------------------------------------------
    # Paragraph & Character Formatting Operations
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Table Operations
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Revision & Comment Operations
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # i18n & Localization
    # -----------------------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Localize UI strings, status tips, and accessibility descriptions."""
        self.setToolTip(safe_tr("页面编辑画布 (Word 2003 视图)"))
        self.setStatusTip(safe_tr("点击编辑文本，支持打字、退格、多页排版与选区"))
        self.viewport().setAccessibleName(safe_tr("文档排版画布"))
        self.viewport().setAccessibleDescription(
            safe_tr("Word 2003 高保真多页仿真编辑视口，支持原位光标与选区交互")
        )
