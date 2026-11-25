"""Word 2003 high-fidelity paper canvas viewport for Quire word processing."""

from __future__ import annotations

import copy
import functools
import logging
import math
from collections.abc import Callable
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
    QColor,
    QContextMenuEvent,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
    QTextLayout,
    QTextOption,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QMenu,
    QWidget,
)

from atboffice.core.i18n import safe_tr
from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.core.undo import UndoService
from atboffice.modules.presentation.chart.painter import ChartPainter
from atboffice.modules.writer.layout.math_layout import paint_math
from atboffice.modules.writer.layout.pagination import (
    Page,
    PageFootnoteArea,
    PageHeaderFooter,
    PaginationResult,
    paginate_document,
)
from atboffice.modules.writer.layout.portions import (
    PortionType,
    measure_text_width,
)
from atboffice.modules.writer.layout.table_layout import TableLayout
from atboffice.modules.writer.layout.wrap import FloatBox
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TextItem,
    info,
    normalize,
    paras_between,
    plen,
    ptext,
    reindex,
    split_at,
)
from atboffice.modules.writer.models.drawing import ChartItem, PictureItem, ShapeItem
from atboffice.modules.writer.models.omml import OfficeMathItem
from atboffice.modules.writer.models.properties import (
    IndentProperties,
    NumberingRef,
    ParagraphProperties,
    RunProperties,
    SpacingProperties,
)
from atboffice.modules.writer.models.revision import (
    accept_all_revisions,
    accept_revision,
    insert_comment,
    list_revisions,
    reject_all_revisions,
    reject_revision,
    toggle_tracking,
)
from atboffice.modules.writer.models.table import (
    create_simple_table,
    delete_cols,
    delete_rows,
    insert_cols,
    insert_rows,
    merge_cells,
    split_cells,
    table_map,
)
from atboffice.modules.writer.spell import SpellEngine
from atboffice.modules.writer.views.caret_controller import (
    CaretController,
    DocPos,
    Selection,
    delete_range_in_paragraph,
    insert_text_in_paragraph,
)
from atboffice.modules.writer.views.shape_painter import paint_shape
from atboffice.modules.writer.views.text_history import TextEditRecorder
from atboffice.modules.writer.views.view_modes import ViewMode

logger = logging.getLogger(__name__)


def _undoable(label: str, parts: tuple[str, ...] = ()) -> Callable[[Any], Any]:
    """Record the decorated edit of the blocks around the caret as one undo step.

    ``parts`` names other document parts the edit may change (``styles``,
    ``comments``...); they are copied before and after as well.
    """

    def deco(fn: Any) -> Any:
        @functools.wraps(fn)
        def wrapper(self: WriterCanvasView, *args: Any, **kwargs: Any) -> Any:
            with self.controller.edit_scope(label, parts):
                return fn(self, *args, **kwargs)

        return wrapper

    return deco


def _undoable_document(label: str) -> Callable[[Any], Any]:
    """Record the decorated edit, which may touch the whole document, as one step."""

    def deco(fn: Any) -> Any:
        @functools.wraps(fn)
        def wrapper(self: WriterCanvasView, *args: Any, **kwargs: Any) -> Any:
            out: list[Any] = []
            self.run_undoable(lambda: out.append(fn(self, *args, **kwargs)), label)
            return out[0] if out else None

        return wrapper

    return deco


# Standard Word 2003 visual styling constants matching .vibeoffice looks
COLOR_WORKSPACE_BG = QColor(144, 151, 163)  # Classic neutral gray workspace (#9097A3)
COLOR_PAGE_PAPER = QColor(255, 255, 255)  # Pure white paper sheet
COLOR_PAGE_BORDER = QColor(112, 112, 112)  # 1px border around page
COLOR_SHADOW_DARK = QColor(58, 58, 58, 160)  # Classic drop shadow (dark core)
COLOR_SHADOW_LIGHT = QColor(80, 80, 80, 70)  # Soft drop shadow ambient falloff
# w:highlight names (ST_HighlightColor) → screen colours
WORD_HIGHLIGHT_COLORS: dict[str, str] = {
    "yellow": "#FFFF00",
    "green": "#00FF00",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "blue": "#0000FF",
    "red": "#FF0000",
    "darkBlue": "#000080",
    "darkCyan": "#008080",
    "darkGreen": "#008000",
    "darkMagenta": "#800080",
    "darkRed": "#800000",
    "darkYellow": "#808000",
    "darkGray": "#808080",
    "lightGray": "#C0C0C0",
    "black": "#000000",
    "white": "#FFFFFF",
}
COLOR_SELECTION = QColor(51, 153, 255, 110)  # Word selection highlight blue
COLOR_CARET = QColor(0, 0, 0)  # Blinking caret black
COLOR_MARGIN_GUIDE = QColor(200, 200, 200, 120)  # Subtle margin boundary guides


_WAVY_UNDERLINES = frozenset({"wave", "wavyHeavy", "wavyDouble"})
_UNDERLINE_PEN_STYLES = {
    "dotted": Qt.PenStyle.DotLine,
    "dottedHeavy": Qt.PenStyle.DotLine,
    "dash": Qt.PenStyle.DashLine,
    "dashed": Qt.PenStyle.DashLine,
    "dashedHeavy": Qt.PenStyle.DashLine,
    "dashLong": Qt.PenStyle.DashLine,
    "dashLongHeavy": Qt.PenStyle.DashLine,
    "dotDash": Qt.PenStyle.DashDotLine,
    "dashDotHeavy": Qt.PenStyle.DashDotLine,
    "dotDotDash": Qt.PenStyle.DashDotDotLine,
    "dashDotDotHeavy": Qt.PenStyle.DashDotDotLine,
}


class WriterCanvasView(QAbstractScrollArea):
    """Word 2003 styled physical paper canvas viewport."""

    zoom_changed = Signal(float)
    caret_moved = Signal(int, int)  # para_id, offset
    view_mode_changed = Signal(object)
    header_footer_requested = Signal(str)  # "hdr" / "ftr"

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

        # Table divider interactive resizing
        self._resizing_table: bool = False
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
        import copy

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
        import copy

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

    def _get_border_pen(self, bp: Any, zoom: float) -> QPen | None:
        """Resolve a QPen for a BorderProperties object under active zoom."""
        if not bp or getattr(bp, "val", "none") in ("none", "nil", "hidden", "", None):
            return None
        val = str(bp.val).lower()
        sz_pt = max(0.5, float(getattr(bp, "sz", 0.5) or 0.5))
        pen_w = max(1.0, sz_pt * self.pt_to_px_ratio * zoom)
        color_val = getattr(bp, "color", "auto") or "auto"
        if color_val in ("auto", "none", ""):
            # "auto" border colour resolves to black (Word renders it as windowText).
            color = QColor(0, 0, 0)
        else:
            hex_c = color_val if color_val.startswith("#") else f"#{color_val}"
            color = QColor(hex_c)
        pen = QPen(color, pen_w)
        if "dash" in val:
            pen.setStyle(Qt.PenStyle.DashLine)
        elif "dot" in val:
            pen.setStyle(Qt.PenStyle.DotLine)
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)
        return pen

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

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint workspace background, paper pages, shadow, text portions, selection, and caret."""
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # 1. Paint Workspace Background
        painter.fillRect(self.viewport().rect(), COLOR_WORKSPACE_BG)

        if not self.pagination or not self.pagination.pages:
            painter.end()
            return

        visible_rect = self.viewport().rect()
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()

        paper_view = self.view_mode in (ViewMode.PRINT, ViewMode.READING)
        if not paper_view:
            # Normal / Web layout: one continuous white sheet, no paper
            painter.fillRect(self.viewport().rect(), COLOR_PAGE_PAPER)
        slots = self.page_slots() if not paper_view else None

        # Render each page
        for p_idx, page in enumerate(self.pagination.pages):
            rect_canvas = self.page_rect_canvas(p_idx)
            if rect_canvas.isEmpty():
                continue
            rect_vp = QRectF(
                rect_canvas.left() - scroll_x,
                rect_canvas.top() - scroll_y,
                rect_canvas.width(),
                rect_canvas.height(),
            )
            clip_vp = rect_vp
            if slots is not None:
                clip = slots[p_idx][1]
                clip_vp = QRectF(
                    clip.left() - scroll_x, clip.top() - scroll_y, clip.width(), clip.height()
                )

            # Viewport culling
            if not clip_vp.intersects(QRectF(visible_rect)):
                continue

            painter.save()
            if not paper_view:
                painter.setClipRect(clip_vp)

            # 2. Paint Page Drop Shadow (only in PRINT and READING modes)
            if paper_view:
                self._paint_page_shadow(painter, rect_vp)

                # 3. Paint Page Sheet Background & Border
                painter.fillRect(rect_vp, COLOR_PAGE_PAPER)
                painter.setPen(QPen(COLOR_PAGE_BORDER, 1.0))
                painter.drawRect(rect_vp)

            # 4. Paint Selection Highlights on this page
            self._paint_selection(painter, p_idx, rect_vp, page)

            # 5. Paint Document Content (Text Lines & Portions)
            self._paint_page_content(painter, rect_vp, page)

            # 5.05 Header/footer editing: dim the body, frame the header/footer area
            if self.hf_edit_kind and paper_view:
                self._paint_hf_edit_overlay(painter, rect_vp, page)

            # 5.06 Selected floating object: frame and sizing handles
            self._paint_float_selection(painter, p_idx, rect_vp, page)

            # 5.1 Paint Comment Balloons & Range Annotations
            if self.show_comments and paper_view:
                self._paint_comments(painter, rect_vp, page)
            painter.restore()

            # Normal view: a dotted line where one page ends and the next begins
            if self.view_mode == ViewMode.NORMAL and p_idx > 0:
                painter.setPen(QPen(QColor(128, 128, 128), 1.0, Qt.PenStyle.DotLine))
                painter.drawLine(
                    QPointF(0.0, clip_vp.top()),
                    QPointF(float(self.viewport().width()), clip_vp.top()),
                )

        # 5.2 Formatting marks (¶ at each paragraph end) when toggled on
        if self.show_formatting_marks:
            self._paint_formatting_marks(painter)

        # 6. Paint Blinking Caret
        if self.hasFocus() and self.controller.caret_visible:
            self._paint_caret(painter)

        # 7. Paint Table Resize Guide Line
        if self._resizing_table and self._resize_guide_pos and self._resize_info:
            guide_pen = QPen(QColor(0, 51, 153), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(guide_pen)
            if self._resize_info.get("kind") == "col":
                gx = float(self._resize_guide_pos.x())
                painter.drawLine(QPointF(gx, 0), QPointF(gx, self.viewport().height()))
            elif self._resize_info.get("kind") == "row":
                gy = float(self._resize_guide_pos.y())
                painter.drawLine(QPointF(0, gy), QPointF(self.viewport().width(), gy))

        # 8. Paint Ruler Guide Line
        if self._ruler_guide_x is not None or self._ruler_guide_y is not None:
            ruler_pen = QPen(QColor(60, 60, 60, 200), 1.0, Qt.PenStyle.DashLine)
            painter.setPen(ruler_pen)
            if self._ruler_guide_x is not None:
                gx = self._ruler_guide_x - scroll_x
                painter.drawLine(QPointF(gx, 0), QPointF(gx, float(self.viewport().height())))
            if self._ruler_guide_y is not None:
                gy = self._ruler_guide_y - scroll_y
                painter.drawLine(QPointF(0, gy), QPointF(float(self.viewport().width()), gy))

        painter.end()

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

    def _paint_page_shadow(self, painter: QPainter, page_rect: QRectF) -> None:
        """Draw classic Word 2003 physical paper drop shadow."""
        # Multi-layer shadow offset
        offset_x = 4.0
        offset_y = 4.0

        # Light ambient outer shadow
        outer_shadow = QRectF(
            page_rect.left() + 1.0,
            page_rect.top() + 1.0,
            page_rect.width() + offset_x + 1.0,
            page_rect.height() + offset_y + 1.0,
        )
        painter.fillRect(outer_shadow, COLOR_SHADOW_LIGHT)

        # Dark primary shadow
        primary_shadow = QRectF(
            page_rect.left() + 2.0,
            page_rect.top() + 2.0,
            page_rect.width() + offset_x - 1.0,
            page_rect.height() + offset_y - 1.0,
        )
        painter.fillRect(primary_shadow, COLOR_SHADOW_DARK)

    def _draw_wavy_line(
        self,
        painter: QPainter,
        x1: float,
        x2: float,
        y: float,
        color: QColor = QColor(255, 0, 0),
        amplitude: float = 1.2,
        pen_width: float = 1.0,
    ) -> None:
        """Draw a wavy line; the defaults are the classic red spellcheck squiggle."""
        if x2 <= x1:
            return
        path = QPainterPath()
        path.moveTo(x1, y)
        step = max(2.0, amplitude * 5.0 / 3.0)
        curr_x = x1
        up = True
        while curr_x < x2:
            next_x = min(curr_x + step, x2)
            target_y = y - amplitude if up else y + amplitude
            path.lineTo(next_x, target_y)
            curr_x = next_x
            up = not up

        old_pen = painter.pen()
        painter.setPen(QPen(color, pen_width))
        painter.drawPath(path)
        painter.setPen(old_pen)

    def _resolve_pixmap(self, pic: Any) -> QPixmap | None:
        """Resolve QPixmap for a PictureItem from cache, package, file, or raw data."""
        cache_key = getattr(pic, "image_part", "") or str(id(pic))
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        # 1. Check raw_data dict
        raw = getattr(pic, "raw_data", None)
        if isinstance(raw, dict):
            if "pixmap" in raw and isinstance(raw["pixmap"], QPixmap):
                if not raw["pixmap"].isNull():
                    self._pixmap_cache[cache_key] = raw["pixmap"]
                    return raw["pixmap"]
            if "image" in raw and isinstance(raw["image"], QImage) and not raw["image"].isNull():
                pm = QPixmap.fromImage(raw["image"])
                self._pixmap_cache[cache_key] = pm
                return pm
            if "bytes" in raw and isinstance(raw["bytes"], (bytes, bytearray)):
                pm = QPixmap()
                if pm.loadFromData(raw["bytes"]) and not pm.isNull():
                    self._pixmap_cache[cache_key] = pm
                    return pm

        # 2. Check source package parts
        part_name = getattr(pic, "image_part", "") or ""
        if part_name:
            pkg = getattr(self.doc, "_source_pkg", None) or self.doc.keep.get("source_pkg")
            if pkg is not None:
                candidates = [part_name, part_name.lstrip("/"), f"word/{part_name.lstrip('/')}"]
                for c in candidates:
                    try:
                        if hasattr(pkg, "has_part") and pkg.has_part(c):
                            data = pkg.read_part(c)
                            pm = QPixmap()
                            if pm.loadFromData(data) and not pm.isNull():
                                self._pixmap_cache[cache_key] = pm
                                return pm
                    except Exception:
                        pass

            # 3. Check local filesystem path
            import os

            if os.path.isfile(part_name):
                pm = QPixmap(part_name)
                if not pm.isNull():
                    self._pixmap_cache[cache_key] = pm
                    return pm

            # 4. Check doc.keep media dictionary
            media_dict = self.doc.keep.get("media", {})
            if isinstance(media_dict, dict) and part_name in media_dict:
                media_val = media_dict[part_name]
                if isinstance(media_val, (bytes, bytearray)):
                    pm = QPixmap()
                    if pm.loadFromData(media_val) and not pm.isNull():
                        self._pixmap_cache[cache_key] = pm
                        return pm

        return None

    def _paint_picture(
        self,
        painter: QPainter,
        pic: Any,
        dest_rect: QRectF,
        zoom: float = 1.0,
        is_vector: bool = False,
    ) -> None:
        """Render a PictureItem onto the canvas with DPR awareness, cropping, and rotation."""
        if dest_rect.width() <= 0 or dest_rect.height() <= 0:
            return

        if isinstance(pic, ShapeItem) and not pic.image_part:
            self._paint_shape(painter, pic, dest_rect, is_vector)
            return

        if isinstance(pic, ChartItem) and pic.chart is not None:
            self._paint_chart(painter, pic, dest_rect, is_vector)
            return

        pixmap = self._resolve_pixmap(pic)
        if pixmap is not None and not pixmap.isNull():
            painter.save()
            try:
                # Enable high-quality bilinear filtering for DPR scaling
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

                # Device pixel ratio awareness
                dpr = 1.0
                if hasattr(self, "devicePixelRatioF"):
                    try:
                        dpr = float(self.devicePixelRatioF())
                    except Exception:
                        dpr = 1.0
                elif painter.device() is not None and hasattr(
                    painter.device(), "devicePixelRatioF"
                ):
                    try:
                        dpr = float(painter.device().devicePixelRatioF())
                    except Exception:
                        dpr = 1.0
                if dpr > 1.0 and hasattr(pixmap, "setDevicePixelRatio"):
                    pixmap.setDevicePixelRatio(dpr)

                # Calculate source rect taking Crop into account
                pw = float(pixmap.width())
                ph = float(pixmap.height())
                crop = getattr(pic, "crop", None)
                if crop and (
                    getattr(crop, "left", 0.0)
                    or getattr(crop, "top", 0.0)
                    or getattr(crop, "right", 0.0)
                    or getattr(crop, "bottom", 0.0)
                ):
                    cl = max(0.0, float(getattr(crop, "left", 0.0) or 0.0))
                    ct = max(0.0, float(getattr(crop, "top", 0.0) or 0.0))
                    cr = max(0.0, float(getattr(crop, "right", 0.0) or 0.0))
                    cb = max(0.0, float(getattr(crop, "bottom", 0.0) or 0.0))
                    src_x = pw * cl
                    src_y = ph * ct
                    src_w = max(1.0, pw * max(0.01, 1.0 - cl - cr))
                    src_h = max(1.0, ph * max(0.01, 1.0 - ct - cb))
                    src_rect = QRectF(src_x, src_y, src_w, src_h)
                else:
                    src_rect = QRectF(0.0, 0.0, pw, ph)

                # Handle rotation
                rot = float(getattr(pic, "rotation", 0.0) or 0.0)
                if rot != 0.0:
                    center = dest_rect.center()
                    painter.translate(center)
                    painter.rotate(rot)
                    draw_box = QRectF(
                        -dest_rect.width() / 2.0,
                        -dest_rect.height() / 2.0,
                        dest_rect.width(),
                        dest_rect.height(),
                    )
                    painter.drawPixmap(draw_box, pixmap, src_rect)
                else:
                    painter.drawPixmap(dest_rect, pixmap, src_rect)
            finally:
                painter.restore()
        else:
            # Fallback placeholder for missing or unresolvable image
            painter.save()
            try:
                painter.fillRect(dest_rect, QColor("#F4F4F4"))
                painter.setPen(QPen(QColor("#B0B0B0"), 1.0, Qt.PenStyle.DashLine))
                painter.drawRect(dest_rect)
                painter.setPen(QPen(QColor("#777777")))
                font = QFont("Helvetica", max(7, int(9 * zoom)))
                painter.setFont(font)
                label = (
                    getattr(pic, "alt_text", "") or getattr(pic, "name", "") or self.tr("Picture")
                )
                painter.drawText(dest_rect, Qt.AlignmentFlag.AlignCenter, label)
            finally:
                painter.restore()

    def _paint_chart(
        self,
        painter: QPainter,
        item: ChartItem,
        dest_rect: QRectF,
        is_vector: bool = False,
    ) -> None:
        """Paint an embedded chart with the shared chart painter.

        The chart is laid out in points (fonts, insets) and scaled to the device so it
        looks the same at every zoom and in print.
        """
        scale = 1.0 if is_vector else self.pt_to_px(1.0)
        if scale <= 0:
            return
        painter.save()
        try:
            painter.translate(dest_rect.topLeft())
            painter.scale(scale, scale)
            ChartPainter.paint_chart(
                painter,
                item.chart,
                QRectF(0.0, 0.0, dest_rect.width() / scale, dest_rect.height() / scale),
            )
        except Exception:
            logger.debug("Chart painting failed for %s", item.name, exc_info=True)
        finally:
            painter.restore()

    def _paint_shape(
        self,
        painter: QPainter,
        shape: ShapeItem,
        dest_rect: QRectF,
        is_vector: bool = False,
    ) -> None:
        """Render a DrawingML/VML shape: geometry, fill, outline and text box content."""
        if is_vector:
            scale = 1.0

            def line_cb(p: QPainter, origin: QPointF, line: Any, x: float, y: float) -> None:
                self._paint_vector_line(p, line, origin.x() + x, origin.y() + y)

            table_cb = None
        else:
            scale = self.pt_to_px(1.0)

            def line_cb(p: QPainter, origin: QPointF, line: Any, x: float, y: float) -> None:
                self._paint_line_portions(
                    p, QRectF(origin.x(), origin.y(), 0.0, 0.0), line, x, y, check_spell=False
                )

            def table_cb(p: QPainter, origin: QPointF, tl: Any, x: float, y: float) -> None:
                self._paint_table_layout(p, QRectF(origin.x(), origin.y(), 0.0, 0.0), tl, x, y)

        def image_cb(p: QPainter, item: ShapeItem, rect: QRectF) -> None:
            self._paint_picture(p, item, rect, self._zoom if not is_vector else 1.0, is_vector)

        paint_shape(
            painter,
            shape,
            dest_rect,
            scale,
            paint_line=line_cb,
            paint_table=table_cb,
            paint_image=image_cb,
            doc=getattr(self, "doc", None),
        )

    def _paint_vector_line(self, painter: QPainter, line: Any, x_pt: float, y_pt: float) -> None:
        """Paint the text portions of one laid-out line in point coordinates (print/PDF)."""
        baseline = y_pt + (line.baseline - line.top)
        cur_x = x_pt
        for po in line.portions:
            if po.type == PortionType.TEXT and po.text:
                font = QFont(po.font_family or "Times New Roman")
                font.setPointSizeF(po.font_size or 12.0)
                font.setBold(bool(getattr(po, "bold", False)))
                font.setItalic(bool(getattr(po, "italic", False)))
                painter.setFont(font)
                color_str = getattr(po, "color", None) or "#000000"
                if color_str == "auto":
                    color_str = "#000000"
                painter.setPen(QPen(QColor(color_str)))
                painter.drawText(QPointF(cur_x, baseline - po.baseline_shift), po.text)
            cur_x += po.width

    def _paint_header_footer(
        self,
        painter: QPainter,
        page_rect: QRectF,
        page: Page,
        hf: PageHeaderFooter | None,
        is_header: bool,
    ) -> None:
        """Render header or footer text and portions on screen canvas in subdued gray."""
        if not hf or not hf.fragments:
            return

        hf_top = hf.y
        for frag in hf.fragments:
            for line in frag.lines:
                line_y = hf_top + line.top
                cur_x = page.body_left + line.indent_left
                for po in line.portions:
                    po_w = po.width
                    if po.type == PortionType.TEXT and po.text:
                        text_str = po.text
                        if text_str == "PAGE":
                            from atboffice.modules.writer.layout.pagination import format_number

                            text_str = format_number(page.page_number, page.page_number_format)
                        elif text_str == "NUMPAGES":
                            total_pgs = (
                                len(self.pagination.pages)
                                if (self.pagination and self.pagination.pages)
                                else (page.index + 1)
                            )
                            text_str = str(total_pgs)

                        font_family = po.font_family or "Times New Roman"
                        font_size_pt = po.font_size or 10.0
                        font = QFont(font_family)
                        font.setPointSizeF(font_size_pt * self._zoom)
                        if getattr(po, "bold", False):
                            font.setBold(True)
                        if getattr(po, "italic", False):
                            font.setItalic(True)
                        painter.setFont(font)

                        x_px = page_rect.left() + self.pt_to_px(cur_x)
                        y_px = page_rect.top() + self.pt_to_px(line_y)
                        baseline_px = y_px + self.pt_to_px(line.baseline - line.top)

                        # Subdued gray for screen view (#666666)
                        painter.setPen(QPen(QColor("#666666")))
                        painter.drawText(
                            QPointF(x_px, baseline_px - self.pt_to_px(po.baseline_shift)), text_str
                        )

                        _ul = getattr(po, "underline", None)
                        if _ul and _ul != "none":
                            pen_u = QPen(QColor("#666666"), 0.75 * self._zoom)
                            painter.setPen(pen_u)
                            painter.drawLine(
                                QPointF(x_px, baseline_px + 1.5 * self._zoom),
                                QPointF(x_px + self.pt_to_px(po_w), baseline_px + 1.5 * self._zoom),
                            )
                        if getattr(po, "strikethrough", False):
                            pen_s = QPen(QColor("#666666"), 0.75 * self._zoom)
                            painter.setPen(pen_s)
                            mid_y = baseline_px - (font_size_pt * self._zoom) * 0.3
                            painter.drawLine(
                                QPointF(x_px, mid_y),
                                QPointF(x_px + self.pt_to_px(po_w), mid_y),
                            )
                        if getattr(po, "dstrike", False):
                            pen_ds = QPen(QColor("#666666"), 0.75 * self._zoom)
                            painter.setPen(pen_ds)
                            mid_y = baseline_px - (font_size_pt * self._zoom) * 0.3
                            gap = 1.5 * self._zoom
                            painter.drawLine(
                                QPointF(x_px, mid_y - gap),
                                QPointF(x_px + self.pt_to_px(po_w), mid_y - gap),
                            )
                            painter.drawLine(
                                QPointF(x_px, mid_y + gap),
                                QPointF(x_px + self.pt_to_px(po_w), mid_y + gap),
                            )

                    elif po.type == PortionType.TAB and po_w > 0:
                        tab_data = getattr(po, "data", None)
                        leader = getattr(tab_data, "leader", "none") if tab_data else "none"
                        if leader and leader != "none":
                            x_px = page_rect.left() + self.pt_to_px(cur_x)
                            y_px = page_rect.top() + self.pt_to_px(line_y)
                            baseline_px = y_px + self.pt_to_px(line.baseline - line.top)
                            w_px = self.pt_to_px(po_w)
                            p1 = QPointF(x_px, baseline_px)
                            p2 = QPointF(x_px + w_px, baseline_px)
                            pen_style = Qt.PenStyle.SolidLine
                            if leader == "dot":
                                pen_style = Qt.PenStyle.DotLine
                            elif leader == "hyphen":
                                pen_style = Qt.PenStyle.DashLine
                            elif leader == "underscore":
                                p1 = QPointF(x_px, baseline_px + 1.5 * self._zoom)
                                p2 = QPointF(x_px + w_px, baseline_px + 1.5 * self._zoom)
                            painter.setPen(QPen(QColor("#666666"), 0.75 * self._zoom, pen_style))
                            painter.drawLine(p1, p2)

                    elif po.type == PortionType.GRAPHIC:
                        x_px = page_rect.left() + self.pt_to_px(cur_x)
                        y_px = page_rect.top() + self.pt_to_px(line_y)
                        baseline_px = y_px + self.pt_to_px(line.baseline - line.top)
                        if isinstance(po.data, OfficeMathItem):
                            paint_math(painter, po.data, x_px, baseline_px, self._zoom)
                        elif isinstance(po.data, PictureItem) or getattr(po.data, "t", "") in (
                            "picture",
                            "img",
                        ):
                            pic_w_px = self.pt_to_px(po.width)
                            pic_h_px = self.pt_to_px(po.ascent)
                            dest_rect = QRectF(x_px, baseline_px - pic_h_px, pic_w_px, pic_h_px)
                            self._paint_picture(painter, po.data, dest_rect, self._zoom)

                    cur_x += po_w

    def _build_portion_font(self, po: Any) -> tuple[QFont, QColor]:
        """Construct styled QFont and QColor for a layout portion under active zoom."""
        font_family = getattr(po, "font_family", None) or "Times New Roman"
        font_size_pt = getattr(po, "font_size", None) or 12.0
        font = QFont(font_family)
        font.setPointSizeF(font_size_pt * self._zoom)
        if getattr(po, "bold", False):
            font.setBold(True)
        if getattr(po, "italic", False):
            font.setItalic(True)
        color_str = getattr(po, "color", None) or "#000000"
        if color_str == "auto":
            color_str = "#000000"
        return font, QColor(color_str)

    def _draw_text_decorations(
        self,
        painter: QPainter,
        po: Any,
        font: QFont,
        color: QColor,
        x1_px: float,
        x2_px: float,
        baseline_px: float,
    ) -> None:
        """Draw a portion's underline and strike over the given horizontal span."""
        self._draw_underline_decoration(painter, po, font, color, x1_px, x2_px, baseline_px)
        self._draw_strike_decoration(painter, po, font, color, x1_px, x2_px, baseline_px)

    def _draw_underline_decoration(
        self,
        painter: QPainter,
        po: Any,
        font: QFont,
        color: QColor,
        x1_px: float,
        x2_px: float,
        baseline_px: float,
    ) -> None:
        """Draw a portion's underline in its Word style; unknown styles draw a single line."""
        style = getattr(po, "underline", None)
        if not style or style == "none" or x2_px <= x1_px:
            return
        if style == "words" and po.type == PortionType.BLANK:
            return
        font_size_pt = getattr(po, "font_size", None) or 12.0
        y_px = baseline_px + font_size_pt * self._zoom * 0.12
        thickness = max(0.75 * self._zoom, self._metrics(font).lineWidth())
        if style == "thick" or "Heavy" in style:
            thickness *= 2.0
        if style in _WAVY_UNDERLINES:
            self._draw_wavy_line(painter, x1_px, x2_px, y_px, color, max(1.2, thickness), thickness)
            return
        pen = QPen(color, thickness, _UNDERLINE_PEN_STYLES.get(style, Qt.PenStyle.SolidLine))
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(x1_px, y_px), QPointF(x2_px, y_px))
        if style == "double":
            second_y = y_px + max(1.5 * self._zoom, thickness * 2.0)
            painter.drawLine(QPointF(x1_px, second_y), QPointF(x2_px, second_y))

    def _paint_highlight(
        self, painter: QPainter, po: Any, font: QFont, x1: float, x2: float, baseline: float
    ) -> None:
        """Fill the text-highlight colour (w:highlight) behind a portion."""
        name = getattr(po, "highlight", None)
        if not name or name == "none" or x2 <= x1:
            return
        hex_color = WORD_HIGHLIGHT_COLORS.get(name, name if str(name).startswith("#") else None)
        if not hex_color:
            return
        fm = self._metrics(font)
        painter.fillRect(
            QRectF(x1, baseline - fm.ascent(), x2 - x1, fm.ascent() + fm.descent()),
            QColor(hex_color),
        )

    def _draw_strike_decoration(
        self,
        painter: QPainter,
        po: Any,
        font: QFont,
        color: QColor,
        x1_px: float,
        x2_px: float,
        baseline_px: float,
    ) -> None:
        """Draw a portion's strike; double strike wins when both flags are set."""
        is_double = bool(getattr(po, "dstrike", False))
        if not is_double and not getattr(po, "strikethrough", False):
            return
        font_size_pt = getattr(po, "font_size", None) or 12.0
        mid_y = baseline_px - font_size_pt * self._zoom * 0.3
        thickness = max(0.75 * self._zoom, self._metrics(font).lineWidth())
        pen = QPen(color, thickness)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        gap = max(1.5 * self._zoom, thickness)
        for offset in (-gap, gap) if is_double else (0.0,):
            painter.drawLine(QPointF(x1_px, mid_y + offset), QPointF(x2_px, mid_y + offset))

    def _draw_spellcheck_for_text(
        self,
        painter: QPainter,
        font: QFont,
        text: str,
        x_px: float,
        baseline_px: float,
    ) -> None:
        """Draw wavy red spellcheck underlines for misspelled tokens in text."""
        if getattr(self, "_printing", False):
            return
        fm = self._metrics(font)
        for w, w_start, w_end in self.spell_engine.tokenize_words(text):
            if not self.spell_engine.is_valid_word(w):
                w_x1 = x_px + fm.horizontalAdvance(text[:w_start])
                w_x2 = x_px + fm.horizontalAdvance(text[:w_end])
                self._draw_wavy_line(painter, w_x1, w_x2, baseline_px + 2.5, QColor(255, 0, 0))

    def _paint_line_portions(
        self,
        painter: QPainter,
        page_rect: QRectF,
        line: Any,
        start_x_pt: float,
        line_y_pt: float,
        check_spell: bool = True,
    ) -> None:
        """Render line portions with RTL BiDi, style coalescing, tabs, graphics, and spellcheck."""
        y_px = page_rect.top() + self.pt_to_px(line_y_pt)
        baseline_px = y_px + self.pt_to_px(line.baseline - line.top)
        should_spell = (
            check_spell
            and not getattr(self.doc, "hide_spelling_errors", False)
            and self.spell_engine.is_enabled("spelling/check_as_you_type", True)
        )

        # RTL BiDi lines: draw unified text via QTextLayout for natural Unicode BiDi shaping
        if getattr(line, "is_rtl", False):
            trimmed = list(line.portions)
            while trimmed and trimmed[-1].type == PortionType.BLANK:
                trimmed.pop()
            text_pts = [po for po in trimmed if po.type in (PortionType.TEXT, PortionType.BLANK)]
            if text_pts and len(text_pts) == len(trimmed):
                full_text = "".join(po.text for po in text_pts)
                if full_text:
                    rep_po = next(
                        (po for po in text_pts if po.type == PortionType.TEXT), text_pts[0]
                    )
                    font, pen_col = self._build_portion_font(rep_po)
                    painter.setFont(font)
                    painter.setPen(QPen(pen_col))
                    tl = self._text_layout(full_text, font)
                    opt = QTextOption(Qt.AlignmentFlag.AlignRight)
                    opt.setTextDirection(Qt.LayoutDirection.RightToLeft)
                    tl.setTextOption(opt)
                    tl.beginLayout()
                    box_w_px = max(20.0, self.pt_to_px(max(line.width, 10.0)) + 8.0)
                    tline = tl.createLine()
                    if tline.isValid():
                        tline.setLineWidth(box_w_px)
                    tl.endLayout()
                    if tline.isValid():
                        right_px = page_rect.left() + self.pt_to_px(start_x_pt + line.width)
                        left_px = right_px - box_w_px
                        tline.draw(painter, QPointF(left_px, baseline_px - tline.ascent()))
                        char_pos = 0
                        for po in text_pts:
                            char_end = char_pos + len(po.text)
                            edge_a = left_px + tline.cursorToX(char_pos)[0]
                            edge_b = left_px + tline.cursorToX(char_end)[0]
                            po_font, po_col = self._build_portion_font(po)
                            self._draw_text_decorations(
                                painter,
                                po,
                                po_font,
                                po_col,
                                min(edge_a, edge_b),
                                max(edge_a, edge_b),
                                baseline_px,
                            )
                            char_pos = char_end
                        return

        portions = line.portions
        extra_blank = getattr(line, "extra_space_per_blank", 0.0)
        can_coalesce = math.isclose(extra_blank, 0.0, abs_tol=1e-6)

        # For justified pure-text lines, distribute actual Qt visual slack across blanks so
        # font substitution differences (e.g. missing Calibri -> system font) never overlap words.
        if not can_coalesce and portions:
            trimmed_j = list(portions)
            while trimmed_j and trimmed_j[-1].type == PortionType.BLANK:
                trimmed_j.pop()
            if trimmed_j and all(
                p.type in (PortionType.TEXT, PortionType.BLANK) for p in trimmed_j
            ):
                target_w_px = self.pt_to_px(line.width)
                word_adv_px: list[float] = []
                blank_indices: list[int] = []
                for p_i, pt in enumerate(trimmed_j):
                    if pt.type == PortionType.BLANK:
                        blank_indices.append(p_i)
                        word_adv_px.append(0.0)
                    else:
                        f, _ = self._build_portion_font(pt)
                        word_adv_px.append(self._metrics(f).horizontalAdvance(pt.text))
                total_words_px = sum(word_adv_px)
                if blank_indices:
                    per_blank_px = max(2.5, (target_w_px - total_words_px) / len(blank_indices))
                    cur_px = page_rect.left() + self.pt_to_px(start_x_pt)
                    for p_i, pt in enumerate(trimmed_j):
                        if pt.type == PortionType.BLANK:
                            f, blank_col = self._build_portion_font(pt)
                            self._draw_text_decorations(
                                painter,
                                pt,
                                f,
                                blank_col,
                                cur_px,
                                cur_px + per_blank_px,
                                baseline_px,
                            )
                            cur_px += per_blank_px
                        elif pt.text:
                            font, pen_col = self._build_portion_font(pt)
                            pt_base_px = baseline_px - self.pt_to_px(pt.baseline_shift)
                            self._paint_highlight(
                                painter, pt, font, cur_px, cur_px + word_adv_px[p_i], pt_base_px
                            )
                            painter.setFont(font)
                            painter.setPen(QPen(pen_col))
                            painter.drawText(QPointF(cur_px, pt_base_px), pt.text)
                            if should_spell:
                                self._draw_spellcheck_for_text(
                                    painter, font, pt.text, cur_px, pt_base_px
                                )
                            self._draw_text_decorations(
                                painter,
                                pt,
                                font,
                                pen_col,
                                cur_px,
                                cur_px + word_adv_px[p_i],
                                pt_base_px,
                            )
                            cur_px += word_adv_px[p_i]
                    return

        cur_px = page_rect.left() + self.pt_to_px(start_x_pt)
        line_jc = getattr(line, "jc", "left")
        if can_coalesce and line_jc in ("center", "right") and portions:
            trimmed_a = list(portions)
            while trimmed_a and trimmed_a[-1].type == PortionType.BLANK:
                trimmed_a.pop()
            if trimmed_a and all(
                p.type in (PortionType.TEXT, PortionType.BLANK) for p in trimmed_a
            ):
                qt_w_px = 0.0
                for pt in trimmed_a:
                    if pt.text:
                        f, _ = self._build_portion_font(pt)
                        qt_w_px += self._metrics(f).horizontalAdvance(pt.text)
                layout_w_px = self.pt_to_px(line.width)
                if line_jc == "center":
                    cur_px += (layout_w_px - qt_w_px) / 2.0
                else:
                    cur_px += layout_w_px - qt_w_px

        last_ink_idx = max(
            (i for i, po in enumerate(portions) if po.type != PortionType.BLANK), default=-1
        )
        for po_idx, po in enumerate(portions):
            po_w_px = self.pt_to_px(po.width)
            if po.type == PortionType.TEXT and po.text:
                font, pen_col = self._build_portion_font(po)
                po_base_px = baseline_px - self.pt_to_px(po.baseline_shift)
                self._paint_highlight(
                    painter,
                    po,
                    font,
                    cur_px,
                    cur_px + self._metrics(font).horizontalAdvance(po.text),
                    po_base_px,
                )
                painter.setFont(font)
                painter.setPen(QPen(pen_col))
                painter.drawText(QPointF(cur_px, po_base_px), po.text)
                if should_spell:
                    self._draw_spellcheck_for_text(painter, font, po.text, cur_px, po_base_px)
                text_adv_px = self._metrics(font).horizontalAdvance(po.text)
                self._draw_text_decorations(
                    painter, po, font, pen_col, cur_px, cur_px + text_adv_px, po_base_px
                )
                cur_px += text_adv_px
                continue
            if po.type == PortionType.BLANK and po.text:
                font, pen_col = self._build_portion_font(po)
                blank_adv_px = (
                    self._metrics(font).horizontalAdvance(po.text) if can_coalesce else po_w_px
                )
                if po_idx < last_ink_idx:
                    self._draw_text_decorations(
                        painter, po, font, pen_col, cur_px, cur_px + blank_adv_px, baseline_px
                    )
                cur_px += blank_adv_px
                continue
            if po.type == PortionType.TAB and po.width > 0:
                tab_data = getattr(po, "data", None)
                leader = getattr(tab_data, "leader", "none") if tab_data else "none"
                if leader and leader != "none":
                    p1 = QPointF(cur_px, baseline_px)
                    p2 = QPointF(cur_px + po_w_px, baseline_px)
                    if leader == "dot":
                        painter.setPen(QPen(QColor(100, 100, 100), 1.0, Qt.PenStyle.DotLine))
                        painter.drawLine(p1, p2)
                    elif leader == "hyphen":
                        painter.setPen(QPen(QColor(100, 100, 100), 1.0, Qt.PenStyle.DashLine))
                        painter.drawLine(p1, p2)
                    elif leader == "underscore":
                        painter.setPen(QPen(QColor(100, 100, 100), 1.0, Qt.PenStyle.SolidLine))
                        painter.drawLine(
                            QPointF(cur_px, baseline_px + 2),
                            QPointF(cur_px + po_w_px, baseline_px + 2),
                        )
            elif po.type == PortionType.GRAPHIC:
                if isinstance(po.data, OfficeMathItem):
                    paint_math(painter, po.data, cur_px, baseline_px, self._zoom)
                elif isinstance(po.data, PictureItem) or getattr(po.data, "t", "") in (
                    "picture",
                    "img",
                ):
                    pic_h_px = self.pt_to_px(po.ascent)
                    dest_rect = QRectF(cur_px, baseline_px - pic_h_px, po_w_px, pic_h_px)
                    self._paint_picture(painter, po.data, dest_rect, self._zoom)

            cur_px += po_w_px

    def _paint_float_box(
        self,
        painter: QPainter,
        page_rect: QRectF,
        page: Page,
        fb: FloatBox,
    ) -> None:
        """Render a floating drawing, picture, or shape object on screen canvas."""
        item = fb.item
        if not item:
            return
        x_px = page_rect.left() + self.pt_to_px(fb.x)
        y_px = page_rect.top() + self.pt_to_px(fb.y)
        w_px = self.pt_to_px(fb.w)
        h_px = self.pt_to_px(fb.h)
        dest_rect = QRectF(x_px, y_px, w_px, h_px)

        if fb.lines:
            for line in fb.lines:
                line_y = fb.y + line.top
                cur_x = fb.x + line.indent_left
                self._paint_line_portions(
                    painter, page_rect, line, cur_x, line_y, check_spell=False
                )
            return

        if isinstance(item, PictureItem) or getattr(item, "t", "") in ("picture", "img"):
            self._paint_picture(painter, item, dest_rect, self._zoom)
        else:
            fill_color = getattr(item, "fill_color", None) or "#E8EEF5"
            stroke_color = getattr(item, "stroke_color", None) or "#4A709C"
            stroke_width = getattr(item, "stroke_width", 1.0) or 1.0

            painter.save()
            painter.setBrush(QColor(fill_color))
            painter.setPen(QPen(QColor(stroke_color), self.pt_to_px(stroke_width)))
            painter.drawRect(dest_rect)
            painter.restore()

    def _author_comment_color(self, author: str) -> QColor:
        """Return deterministic author color matching .vibeoffice review palette."""
        palette = (
            "#B5382B",
            "#1F5EA8",
            "#2A7B4F",
            "#7B3E94",
            "#B36B00",
            "#0E7490",
        )
        key = author or "Author"
        idx = sum(ord(ch) for ch in key) % len(palette)
        return QColor(palette[idx])

    def _paint_comments(self, painter: QPainter, page_rect: QRectF, page: Page) -> None:
        """Render comment range highlights, margin connector lines, and callout balloons."""
        if not getattr(self, "doc", None) or not getattr(self.doc, "comments", None):
            return

        comments_dict = self.doc.comments
        if not comments_dict:
            return

        # Compute 1-based document comment order matching RV.commentNumber
        comment_order: dict[str, int] = {}
        order_idx = 1
        for b in getattr(self.doc.main, "blocks", []):
            if hasattr(b, "runs"):
                for item in b.runs:
                    c_id = getattr(item, "comment_id", None)
                    if c_id is not None:
                        cid_s = str(c_id)
                        if cid_s in comments_dict and cid_s not in comment_order:
                            comment_order[cid_s] = order_idx
                            order_idx += 1

        placed_balloons: list[tuple[str, float]] = []
        placed_set: set[str] = set()
        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    if frag.paragraph is None:
                        continue
                    runs = getattr(frag.paragraph, "runs", [])
                    frag_top = page.body_top + col.top + frag.top
                    for item in runs:
                        c_id = getattr(item, "comment_id", None)
                        if c_id is not None and str(c_id) in comments_dict:
                            cid_str = str(c_id)
                            if cid_str not in placed_set:
                                anchor_y = frag_top + (frag.lines[0].top if frag.lines else 0.0)
                                placed_balloons.append((cid_str, anchor_y))
                                placed_set.add(cid_str)
                                for k, st in comments_dict.items():
                                    if (
                                        getattr(st, "parent_id", "") == cid_str
                                        and k not in placed_set
                                    ):
                                        placed_balloons.append((k, anchor_y))
                                        placed_set.add(k)

        if not placed_balloons:
            return

        painter.save()
        balloon_w_px = 200.0 * self._zoom
        balloon_h_px = 42.0 * self._zoom
        balloon_x_px = page_rect.right() + 12.0 * self._zoom
        prev_bottom_px = page_rect.top()

        for cid_str, anchor_y_pt in placed_balloons:
            story = comments_dict[cid_str]
            anchor_y_px = page_rect.top() + self.pt_to_px(anchor_y_pt)
            balloon_y_px = max(anchor_y_px - 2.0, prev_bottom_px + 4.0)
            prev_bottom_px = balloon_y_px + balloon_h_px

            border_col = self._author_comment_color(getattr(story, "author", ""))
            bg_col = QColor(
                int(border_col.red() * 0.15 + 255 * 0.85),
                int(border_col.green() * 0.15 + 255 * 0.85),
                int(border_col.blue() * 0.15 + 255 * 0.85),
            )

            # Orthogonal dashed connector from right margin to balloon
            connector_pen = QPen(border_col, 1.0, Qt.PenStyle.DashLine)
            painter.setPen(connector_pen)
            line_start_x = page_rect.right() - self.pt_to_px(10.0)
            line_y = anchor_y_px + 10.0
            mid_y = balloon_y_px + 8.0
            if abs(line_y - mid_y) > 2.0:
                elbow_x = page_rect.right() + 2.0
                painter.drawLine(QPointF(line_start_x, line_y), QPointF(elbow_x, line_y))
                painter.drawLine(QPointF(elbow_x, line_y), QPointF(elbow_x, mid_y))
                painter.drawLine(QPointF(elbow_x, mid_y), QPointF(balloon_x_px, mid_y))
            else:
                painter.drawLine(QPointF(line_start_x, mid_y), QPointF(balloon_x_px, mid_y))

            # Balloon box
            balloon_rect = QRectF(balloon_x_px, balloon_y_px, balloon_w_px, balloon_h_px)
            painter.setBrush(bg_col)
            painter.setPen(QPen(border_col, 1.0))
            painter.drawRoundedRect(balloon_rect, 4.0, 4.0)

            # Balloon text: Header (initials + 1-based number + reply tag)
            header_font = QFont("Tahoma")
            header_font.setPointSizeF(7.5 * self._zoom)
            header_font.setBold(True)
            painter.setFont(header_font)
            painter.setPen(QPen(QColor(0, 0, 0)))

            num_val = comment_order.get(cid_str)
            if num_val is None:
                try:
                    num_val = int(cid_str) + 1
                except ValueError:
                    num_val = 1
            initials = story.initials or story.author or ""
            is_reply = bool(getattr(story, "parent_id", ""))
            suffix = " (reply):" if is_reply else ":"
            head_text = f"Comment [{initials}{num_val}]{suffix}"
            painter.drawText(
                QRectF(
                    balloon_rect.left() + 5.0,
                    balloon_rect.top() + 3.0,
                    balloon_w_px - 10.0,
                    14.0,
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                head_text,
            )

            # Balloon body text
            body_text = ""
            for b in getattr(story, "blocks", []):
                if isinstance(b, Paragraph):
                    body_text = "".join(r.text for r in b.runs if hasattr(r, "text"))
                    if body_text:
                        break
            if body_text:
                body_font = QFont("Tahoma")
                body_font.setPointSizeF(7.5 * self._zoom)
                painter.setFont(body_font)
                painter.setPen(QPen(QColor(0, 0, 0)))
                painter.drawText(
                    QRectF(
                        balloon_rect.left() + 5.0,
                        balloon_rect.top() + 17.0,
                        balloon_w_px - 10.0,
                        balloon_h_px - 19.0,
                    ),
                    (
                        Qt.AlignmentFlag.AlignLeft
                        | Qt.AlignmentFlag.AlignTop
                        | Qt.TextFlag.TextWordWrap
                    ),
                    body_text[:80],
                )

        painter.restore()

    def _paint_footnote_area(
        self,
        painter: QPainter,
        page_rect: QRectF,
        page: Page,
        fn_area: PageFootnoteArea,
    ) -> None:
        """Render the 2-inch footnote separator rule and footnote paragraph text."""
        # 1. Standard Word 2003 2-inch (144.0 pt) Footnote Separator Rule
        sep_x = page_rect.left() + self.pt_to_px(page.body_left)
        sep_y = page_rect.top() + self.pt_to_px(fn_area.y)
        sep_w = self.pt_to_px(fn_area.separator_width)

        sep_pen = QPen(QColor(0, 0, 0), max(0.75, self.pt_to_px(0.75)))
        painter.setPen(sep_pen)
        painter.drawLine(QPointF(sep_x, sep_y), QPointF(sep_x + sep_w, sep_y))

        # 2. Footnote paragraph fragments
        for frag in fn_area.fragments:
            frag_top = fn_area.y + frag.top
            for line in frag.lines:
                line_y = frag_top + line.top
                cur_x = page.body_left + line.indent_left
                for po in line.portions:
                    po_w = po.width
                    if po.type == PortionType.TEXT and po.text:
                        font_family = po.font_family or "Times New Roman"
                        font_size_pt = po.font_size or 10.0
                        font = QFont(font_family)
                        font.setPointSizeF(font_size_pt * self._zoom)
                        if getattr(po, "bold", False):
                            font.setBold(True)
                        if getattr(po, "italic", False):
                            font.setItalic(True)
                        painter.setFont(font)

                        x_px = page_rect.left() + self.pt_to_px(cur_x)
                        y_px = page_rect.top() + self.pt_to_px(line_y)
                        baseline_px = y_px + self.pt_to_px(line.baseline - line.top)

                        painter.setPen(QPen(QColor(0, 0, 0)))
                        painter.drawText(
                            QPointF(x_px, baseline_px - self.pt_to_px(po.baseline_shift)), po.text
                        )
                    cur_x += po_w

    def _paint_table_layout(
        self,
        painter: QPainter,
        page_rect: QRectF,
        tl: TableLayout,
        frag_x: float,
        frag_y: float,
    ) -> None:
        """Paint a table, and recursively its nested tables, at origin (frag_x, frag_y) in pt."""
        for rl in tl.rows:
            for cl in rl.cells:
                cell_x_px = page_rect.left() + self.pt_to_px(frag_x + cl.x)
                cell_y_px = page_rect.top() + self.pt_to_px(frag_y + cl.y)
                cell_w_px = self.pt_to_px(cl.width)
                cell_h_px = self.pt_to_px(cl.height)
                cell_rect = QRectF(cell_x_px, cell_y_px, cell_w_px, cell_h_px)

                # Shading
                fill_val = getattr(cl.shd, "fill", "auto")
                if fill_val and fill_val not in ("auto", "clear", "none"):
                    hex_fill = fill_val if fill_val.startswith("#") else f"#{fill_val}"
                    painter.fillRect(cell_rect, QColor(hex_fill))

                # Borders
                bds = getattr(cl, "borders", {}) or {}
                has_explicit_borders = any(
                    getattr(b, "val", "none") not in ("none", "nil", "hidden", "", None)
                    for b in bds.values()
                )
                if has_explicit_borders:
                    top_p = self._get_border_pen(bds.get("top"), self._zoom)
                    if top_p:
                        painter.setPen(top_p)
                        painter.drawLine(
                            QPointF(cell_rect.left(), cell_rect.top()),
                            QPointF(cell_rect.right(), cell_rect.top()),
                        )
                    bot_p = self._get_border_pen(bds.get("bottom"), self._zoom)
                    if bot_p:
                        painter.setPen(bot_p)
                        painter.drawLine(
                            QPointF(cell_rect.left(), cell_rect.bottom()),
                            QPointF(cell_rect.right(), cell_rect.bottom()),
                        )
                    left_p = self._get_border_pen(bds.get("left"), self._zoom)
                    if left_p:
                        painter.setPen(left_p)
                        painter.drawLine(
                            QPointF(cell_rect.left(), cell_rect.top()),
                            QPointF(cell_rect.left(), cell_rect.bottom()),
                        )
                    right_p = self._get_border_pen(bds.get("right"), self._zoom)
                    if right_p:
                        painter.setPen(right_p)
                        painter.drawLine(
                            QPointF(cell_rect.right(), cell_rect.top()),
                            QPointF(cell_rect.right(), cell_rect.bottom()),
                        )
                else:
                    # Fallback default subtle table grid boundary
                    painter.setPen(QPen(QColor(180, 180, 180), 1.0))
                    painter.drawRect(cell_rect)

                # Cell text content with margins and multi-paragraph layout
                mar_l = getattr(cl, "mar_l", 5.4)
                mar_t = getattr(cl, "mar_t", 0.0)
                cell_inner_x = frag_x + cl.x + mar_l
                content_y = frag_y + cl.y + cl.content_offset_y + mar_t

                for item, item_top in zip(cl.block_layouts, cl.block_tops):
                    if isinstance(item, TableLayout):
                        # Nested table: recurse, clipped to the parent cell.
                        painter.save()
                        painter.setClipRect(cell_rect, Qt.ClipOperation.IntersectClip)
                        self._paint_table_layout(
                            painter, page_rect, item, cell_inner_x + item.x, content_y + item_top
                        )
                        painter.restore()
                        continue
                    playout = item
                    p_top = content_y + item_top + playout.effective_space_before
                    for line in playout.lines:
                        line_y = p_top + line.top
                        cur_x = cell_inner_x + line.indent_left
                        for po in line.portions:
                            po_w = po.width
                            if po.type == PortionType.TEXT and po.text:
                                font_family = po.font_family or "Times New Roman"
                                font_size_pt = po.font_size or 12.0
                                font = QFont(font_family)
                                font.setPointSizeF(font_size_pt * self._zoom)
                                if getattr(po, "bold", False):
                                    font.setBold(True)
                                if getattr(po, "italic", False):
                                    font.setItalic(True)
                                painter.setFont(font)
                                x_px = page_rect.left() + self.pt_to_px(cur_x)
                                y_px = page_rect.top() + self.pt_to_px(line_y)
                                baseline_px = y_px + self.pt_to_px(line.baseline_offset)
                                painter.setPen(QPen(QColor(0, 0, 0)))
                                po_base_px = baseline_px - self.pt_to_px(po.baseline_shift)
                                painter.drawText(QPointF(x_px, po_base_px), po.text)
                                if (
                                    self.spell_engine.is_enabled("spelling/check_as_you_type", True)
                                    and po.text
                                ):
                                    fm = self._metrics(font)
                                    for (
                                        w,
                                        w_start,
                                        w_end,
                                    ) in self.spell_engine.tokenize_words(po.text):
                                        if not self.spell_engine.is_valid_word(w):
                                            w_x1 = x_px + fm.horizontalAdvance(po.text[:w_start])
                                            w_x2 = x_px + fm.horizontalAdvance(po.text[:w_end])
                                            self._draw_wavy_line(
                                                painter,
                                                w_x1,
                                                w_x2,
                                                baseline_px + 2.5,
                                                QColor(255, 0, 0),
                                            )
                            elif po.type == PortionType.GRAPHIC:
                                x_px = page_rect.left() + self.pt_to_px(cur_x)
                                y_px = page_rect.top() + self.pt_to_px(line_y)
                                baseline_px = y_px + self.pt_to_px(line.baseline_offset)
                                if isinstance(po.data, OfficeMathItem):
                                    paint_math(
                                        painter,
                                        po.data,
                                        x_px,
                                        baseline_px,
                                        self._zoom,
                                    )
                                elif isinstance(po.data, PictureItem) or getattr(
                                    po.data, "t", ""
                                ) in ("picture", "img"):
                                    pic_w_px = self.pt_to_px(po.width)
                                    pic_h_px = self.pt_to_px(po.ascent)
                                    dest_rect = QRectF(
                                        x_px,
                                        baseline_px - pic_h_px,
                                        pic_w_px,
                                        pic_h_px,
                                    )
                                    self._paint_picture(painter, po.data, dest_rect, self._zoom)
                            cur_x += po_w

    def _paint_page_content(self, painter: QPainter, page_rect: QRectF, page: Page) -> None:
        """Render lines, formatted portions, and table structures on a single page."""
        # 1. Render Header if present
        if page.header:
            self._paint_header_footer(painter, page_rect, page, page.header, is_header=True)

        # 1.5. Render background floating shapes (behind == True)
        for fb in getattr(page, "float_boxes", []):
            if fb.behind:
                self._paint_float_box(painter, page_rect, page, fb)

        # 2. Render Page Regions and Paragraphs/Tables
        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    if frag.table_layout is not None:
                        tl = frag.table_layout
                        frag_x = page.body_left + col.left
                        frag_y = page.body_top + col.top + frag.top

                        self._paint_table_layout(painter, page_rect, tl, frag_x + tl.x, frag_y)
                        continue

                    frag_top = page.body_top + col.top + frag.top
                    for line in frag.lines:
                        line_y = frag_top + line.top
                        cur_x = page.body_left + col.left + line.indent_left
                        self._paint_line_portions(
                            painter, page_rect, line, cur_x, line_y, check_spell=True
                        )

        # 2.5. Render foreground floating shapes (behind == False)
        for fb in getattr(page, "float_boxes", []):
            if not fb.behind:
                self._paint_float_box(painter, page_rect, page, fb)

        # 2.6. Render Footnote Area if present
        if getattr(page, "footnote_area", None) and page.footnote_area.fragments:
            self._paint_footnote_area(painter, page_rect, page, page.footnote_area)

        # 3. Render Footer if present
        if page.footer:
            self._paint_header_footer(painter, page_rect, page, page.footer, is_header=False)

    def _metrics(self, font: QFont) -> QFontMetricsF:
        """Font metrics for the device being painted (the printer while printing)."""
        device = getattr(self, "_print_device", None)
        return QFontMetricsF(font, device) if device is not None else QFontMetricsF(font)

    def _text_layout(self, text: str, font: QFont) -> QTextLayout:
        device = getattr(self, "_print_device", None)
        return QTextLayout(text, font, device) if device is not None else QTextLayout(text, font)

    def render_page_to_painter(
        self,
        painter: QPainter,
        page: Page,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
    ) -> None:
        """Paint ``page`` in points onto ``painter`` (printer, PDF, image) with screen fidelity.

        Uses the on-screen page painter (bullets, highlights, justification, borders and
        shading, watermarks, charts, shapes, headers/footers) in a print mode: coordinates
        are points, fonts are sized for the target device, and editing aids (selection,
        caret, spell-check squiggles, comments, formatting marks) are not drawn.
        """
        device = painter.device()
        dpi = float(device.logicalDpiY()) if device is not None else 72.0
        if dpi <= 0:
            dpi = 72.0
        saved = (
            self.pt_to_px_ratio,
            self._zoom,
            getattr(self, "_printing", False),
            getattr(self, "_print_device", None),
        )
        self.pt_to_px_ratio = dpi / 72.0
        self._zoom = 72.0 / dpi
        self._printing = True
        self._print_device = device
        painter.save()
        try:
            painter.translate(origin_x, origin_y)
            page_rect = QRectF(0.0, 0.0, float(page.width), float(page.height))
            painter.fillRect(page_rect, COLOR_PAGE_PAPER)
            self._paint_page_content(painter, page_rect, page)
        finally:
            painter.restore()
            (self.pt_to_px_ratio, self._zoom, self._printing, self._print_device) = saved

    def _paint_selection(
        self, painter: QPainter, page_idx: int, page_rect: QRectF, page: Page
    ) -> None:
        """Render selection highlight rects for active text selection."""
        sel = self.controller.selection
        if sel.is_collapsed:
            return

        start, end = sel.ordered_range(self.doc)

        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    if frag.paragraph is None:
                        continue
                    pid = frag.paragraph.id
                    inf = info(self.doc, pid)
                    if not inf or "p" not in inf:
                        continue
                    p_order = inf["p"]._o

                    inf_s = info(self.doc, start.para_id)
                    inf_e = info(self.doc, end.para_id)
                    order_s = inf_s["p"]._o if inf_s and "p" in inf_s else 0
                    order_e = inf_e["p"]._o if inf_e and "p" in inf_e else 0

                    # Check if paragraph is within selection range
                    if p_order < order_s or p_order > order_e:
                        continue

                    p_len = plen(frag.paragraph)
                    sel_start_in_p = start.offset if p_order == order_s else 0
                    sel_end_in_p = end.offset if p_order == order_e else p_len

                    frag_top = page.body_top + col.top + frag.top
                    for line in frag.lines:
                        if not line.portions:
                            continue
                        l_start = line.portions[0].char_offset
                        l_end = line.portions[-1].char_offset + line.portions[-1].length

                        # Check line overlap with paragraph selection
                        inter_start = max(l_start, sel_start_in_p)
                        inter_end = min(l_end, sel_end_in_p)

                        if inter_start < inter_end:
                            # Calculate x coordinates of selection on this line
                            x1 = page.body_left + col.left + line.indent_left
                            for po in line.portions:
                                if inter_start >= po.char_offset + po.length:
                                    x1 += po.width
                                else:
                                    sub = max(0, inter_start - po.char_offset)
                                    x1 += measure_text_width(
                                        po.text[:sub], po.font_size, po.font_family
                                    )
                                    break

                            x2 = page.body_left + col.left + line.indent_left
                            for po in line.portions:
                                if inter_end >= po.char_offset + po.length:
                                    x2 += po.width
                                else:
                                    sub = max(0, inter_end - po.char_offset)
                                    x2 += measure_text_width(
                                        po.text[:sub], po.font_size, po.font_family
                                    )
                                    break

                            rect_x = page_rect.left() + self.pt_to_px(x1)
                            rect_y = page_rect.top() + self.pt_to_px(frag_top + line.top)
                            rect_w = max(4.0, self.pt_to_px(x2 - x1))
                            rect_h = self.pt_to_px(max(line.height, 14.0))

                            painter.fillRect(
                                QRectF(rect_x, rect_y, rect_w, rect_h),
                                COLOR_SELECTION,
                            )

    def _paint_formatting_marks(self, painter: QPainter) -> None:
        """Draw a pilcrow at the end of every visible paragraph (Show/Hide ¶)."""
        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        vp_h = self.viewport().height()
        painter.save()
        mark_font = QFont("Arial")
        painter.setPen(QColor(74, 111, 165))
        for p in self.doc.all_paras():
            end = plen(p)
            try:
                page_idx, pt_page, h_pt = self.controller.pos_to_canvas(DocPos(p.id, end))
            except Exception:
                continue
            page_rect = self.page_rect_canvas(page_idx)
            x = page_rect.left() - scroll_x + self.pt_to_px(pt_page.x()) + 1
            y = page_rect.top() - scroll_y + self.pt_to_px(pt_page.y())
            h = max(6.0, self.pt_to_px(h_pt))
            if y + h < 0 or y > vp_h:
                continue
            mark_font.setPixelSize(max(6, int(h * 0.8)))
            painter.setFont(mark_font)
            painter.drawText(QPointF(x, y + h * 0.8), "\u00b6")
        painter.restore()

    def start_format_painter(self, sticky: bool = False) -> bool:
        """Copy the caret's character formatting for the next selection (Format Painter)."""
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if p is None:
            return False
        import copy as _copy

        offset = self.controller.pos.offset
        props = None
        cur = 0
        for it in p.runs:
            n = len(getattr(it, "text", "")) if getattr(it, "t", "") == "text" else 1
            if cur <= offset <= cur + n and getattr(it, "t", "") == "text":
                props = it.r_pr
                break
            cur += n
        self.format_painter_props = _copy.deepcopy(props or p.r_pr)
        self.format_painter_sticky = sticky
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        return True

    def stop_format_painter(self) -> None:
        self.format_painter_props = None
        self.format_painter_sticky = False
        self.viewport().unsetCursor()

    def _apply_format_painter(self) -> bool:
        props = self.format_painter_props
        if props is None or self.controller.selection.is_collapsed:
            return False
        import copy as _copy

        fields = (
            "font",
            "font_ea",
            "font_cs",
            "sz",
            "b",
            "i",
            "u",
            "color",
            "vert",
            "highlight",
            "strike",
            "dstrike",
            "caps",
            "small_caps",
            "spacing",
        )

        def apply(r_pr: RunProperties) -> None:
            for name in fields:
                setattr(r_pr, name, _copy.deepcopy(getattr(props, name)))

        self.run_undoable(lambda: self.format_range(apply))
        if not self.format_painter_sticky:
            self.stop_format_painter()
        return True

    def _paint_caret(self, painter: QPainter) -> None:
        """Render blinking caret at active position."""
        page_idx, pt_page, h_pt = self.controller.pos_to_canvas(self.controller.pos)
        page_rect = self.page_rect_canvas(page_idx)

        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()

        caret_vp_x = page_rect.left() - scroll_x + self.pt_to_px(pt_page.x())
        caret_vp_y = page_rect.top() - scroll_y + self.pt_to_px(pt_page.y())
        caret_vp_h = self.pt_to_px(h_pt)

        painter.setPen(QPen(COLOR_CARET, 1.5))
        painter.drawLine(
            QPointF(caret_vp_x, caret_vp_y),
            QPointF(caret_vp_x, caret_vp_y + caret_vp_h),
        )

    def _hit_test_table_divider(self, vp_pt: QPoint) -> dict[str, Any] | None:
        """Hit test viewport position against table column or row dividers."""
        if not self.pagination or not self.pagination.pages:
            return None

        scroll_x = self.horizontalScrollBar().value()
        scroll_y = self.verticalScrollBar().value()
        threshold = 4.0

        for p_idx, page in enumerate(self.pagination.pages):
            page_rect = self.page_rect_canvas(p_idx)
            page_vp_left = page_rect.left() - scroll_x
            page_vp_top = page_rect.top() - scroll_y

            for reg in page.regions:
                for col in reg.columns:
                    for frag in col.fragments:
                        if frag.table_layout is None:
                            continue
                        tl = frag.table_layout
                        frag_x = page.body_left + col.left
                        frag_y = page.body_top + col.top + frag.top

                        frag_vp_top = page_vp_top + self.pt_to_px(frag_y)
                        frag_vp_bottom = frag_vp_top + self.pt_to_px(tl.height)
                        frag_vp_left = page_vp_left + self.pt_to_px(frag_x)
                        frag_vp_right = frag_vp_left + self.pt_to_px(tl.width)

                        # Test vertical column dividers
                        cur_x = frag_x
                        for c_idx, col_w in enumerate(tl.grid):
                            cur_x += col_w
                            div_vp_x = page_vp_left + self.pt_to_px(cur_x)
                            if (
                                abs(vp_pt.x() - div_vp_x) <= threshold
                                and frag_vp_top - 2 <= vp_pt.y() <= frag_vp_bottom + 2
                            ):
                                return {
                                    "table": tl.table,
                                    "kind": "col",
                                    "index": c_idx,
                                    "start_pt": vp_pt,
                                    "initial_size": col_w,
                                }

                        # Test horizontal row dividers
                        for r_idx, rl in enumerate(tl.rows):
                            div_y = frag_y + rl.y + rl.height
                            div_vp_y = page_vp_top + self.pt_to_px(div_y)
                            if (
                                abs(vp_pt.y() - div_vp_y) <= threshold
                                and frag_vp_left - 2 <= vp_pt.x() <= frag_vp_right + 2
                            ):
                                return {
                                    "table": tl.table,
                                    "kind": "row",
                                    "index": rl.row_idx,
                                    "start_pt": vp_pt,
                                    "initial_size": rl.height,
                                }

        return None

    # -----------------------------------------------------------------------
    # Mouse & Keyboard Event Handlers
    # -----------------------------------------------------------------------

    def _event_pos(self, event: QMouseEvent) -> QPoint:
        """Extract integer pixel QPoint from QMouseEvent safely across Qt versions."""
        if hasattr(event, "position"):
            return event.position().toPoint()
        return event.pos()

    def jump_to_bookmark(self, name: str) -> bool:
        """Jump to bookmark target by scrolling canvas and setting caret position."""
        from atboffice.modules.writer.models.field import find_bookmarks
        from atboffice.modules.writer.views.caret_controller import DocPos

        bms = find_bookmarks(self.doc)
        b = bms.get(name)
        if not b:
            return False
        target_pos = DocPos(b.p.id, b.offset)
        self.controller.set_pos(target_pos, extend_selection=False)
        self.scroll_to_caret()
        self.viewport().update()
        return True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle single-click, double-click, triple-click, and table divider resize."""
        pos_pt = self._event_pos(event)
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test_table_divider(pos_pt)
            if hit is not None:
                self._resizing_table = True
                self._resize_info = hit
                self._resize_guide_pos = pos_pt
                self.viewport().update()
                return

            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            if self._float_press(page_idx, pt_doc):
                return
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)

            # Hyperlink navigation check
            p = self.controller._paragraph_by_id(pos.para_id)
            if p:
                from atboffice.modules.writer.models.document import locate

                item_idx, _, _ = locate(p, pos.offset, side="after")
                if 0 <= item_idx < len(p.runs):
                    it = p.runs[item_idx]
                    link = getattr(it.r_pr, "link", None) if hasattr(it, "r_pr") else None
                    if link and isinstance(link, dict) and "anchor" in link:
                        if self.jump_to_bookmark(link["anchor"]):
                            return

            modifiers = event.modifiers()
            shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

            self._is_dragging = True
            self.setFocus()
            self.controller.set_pos(pos, extend_selection=shift)
            self.viewport().update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse dragging for continuous selection and table resizing."""
        pos_pt = self._event_pos(event)
        if self._resizing_table:
            self._resize_guide_pos = pos_pt
            self.viewport().update()
            return
        if self._float_drag is not None:
            _page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            self._float_drag.current = pt_doc
            self.viewport().update()
            return
        if self._float_hover_cursor(pos_pt):
            return

        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)
            self.controller.set_pos(pos, extend_selection=True)
            self.viewport().update()
            return

        # Divider cursor hover detection
        hit = self._hit_test_table_divider(pos_pt)
        if hit is not None:
            if hit["kind"] == "col":
                self.viewport().setCursor(Qt.CursorShape.SplitHCursor)
            else:
                self.viewport().setCursor(Qt.CursorShape.SplitVCursor)
        else:
            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)
            p = self.controller._paragraph_by_id(pos.para_id)
            is_link = False
            if p:
                from atboffice.modules.writer.models.document import locate

                item_idx, _, _ = locate(p, pos.offset, side="after")
                if 0 <= item_idx < len(p.runs):
                    it = p.runs[item_idx]
                    link = getattr(it.r_pr, "link", None) if hasattr(it, "r_pr") else None
                    if link and isinstance(link, dict) and "anchor" in link:
                        is_link = True
            if is_link:
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.CursorShape.IBeamCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """End mouse selection drag or commit table resize."""
        pos_pt = self._event_pos(event)
        if event.button() == Qt.MouseButton.LeftButton:
            if self._resizing_table and self._resize_info:
                table = self._resize_info["table"]
                idx = self._resize_info["index"]
                kind = self._resize_info["kind"]
                init_sz = self._resize_info["initial_size"]

                if kind == "col":
                    delta_px = pos_pt.x() - self._resize_info["start_pt"].x()
                    delta_pt = self.px_to_pt(delta_px)
                    if 0 <= idx < len(table.grid):
                        table.grid[idx] = max(12.0, round(init_sz + delta_pt, 2))
                elif kind == "row":
                    delta_px = pos_pt.y() - self._resize_info["start_pt"].y()
                    delta_pt = self.px_to_pt(delta_px)
                    if 0 <= idx < len(table.rows):
                        table.rows[idx].tr_pr.h = max(12.0, round(init_sz + delta_pt, 2))
                        table.rows[idx].tr_pr.h_rule = "exact"

                self._resizing_table = False
                self._resize_info = None
                self._resize_guide_pos = None
                self.refresh_layout()
                return

            if self._float_drag is not None:
                _page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
                self._float_release(
                    pt_doc, bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                )
                return

            self._is_dragging = False
            if self.format_painter_props is not None:
                self._apply_format_painter()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Double-click: header/footer area enters header/footer editing, else select a word."""
        pos_pt = self._event_pos(event)
        if event.button() == Qt.MouseButton.LeftButton:
            page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
            kind = self.header_footer_zone(page_idx, pt_doc)
            if kind is not None:
                self.enter_header_footer_mode(kind)
                return
            if self.hf_edit_kind is not None:
                self.exit_header_footer_mode()
            pos = self.controller.canvas_to_pos(page_idx, pt_doc)
            self.controller.select_word_at(pos)
            self.viewport().update()

    # ------------------------------------------------------------ header/footer mode
    def header_footer_zone(self, page_idx: int, pt: QPointF) -> str | None:
        """ "hdr"/"ftr" when ``pt`` (page points) lies in a page's top/bottom margin.

        Only paper views show the margins, so Normal/Web/Reading never match.
        """
        if self.view_mode != ViewMode.PRINT or not self.pagination.pages:
            return None
        page = self.pagination.pages[max(0, min(page_idx, len(self.pagination.pages) - 1))]
        if not 0.0 <= pt.x() <= page.width:
            return None
        if 0.0 <= pt.y() < page.body_top:
            return "hdr"
        if page.height - page.body_bottom_gap < pt.y() <= page.height:
            return "ftr"
        return None

    def enter_header_footer_mode(self, kind: str) -> None:
        self.hf_edit_kind = kind
        self.header_footer_requested.emit(kind)
        self.viewport().update()

    def exit_header_footer_mode(self) -> None:
        self.hf_edit_kind = None
        self.viewport().update()

    def _paint_hf_edit_overlay(self, painter: QPainter, page_rect: QRectF, page: Page) -> None:
        body = QRectF(
            page_rect.left(),
            page_rect.top() + self.pt_to_px(page.body_top),
            page_rect.width(),
            self.pt_to_px(page.height - page.body_top - page.body_bottom_gap),
        )
        painter.save()
        painter.fillRect(body, QColor(255, 255, 255, 150))
        pen = QPen(QColor(128, 128, 128), 1.0, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        left = page_rect.left() + self.pt_to_px(page.body_left)
        width = self.pt_to_px(page.body_width)
        if self.hf_edit_kind == "hdr":
            top = page_rect.top() + self.pt_to_px(float(getattr(page.section, "hdr", 36.0)))
            painter.drawRect(QRectF(left, top, width, max(0.0, body.top() - top)))
        else:
            bottom = page_rect.bottom() - self.pt_to_px(float(getattr(page.section, "ftr", 36.0)))
            painter.drawRect(QRectF(left, body.bottom(), width, max(0.0, bottom - body.bottom())))
        painter.restore()

    # ------------------------------------------------------------ floating objects
    def selected_float(self) -> Any | None:
        return self._float_sel[1] if self._float_sel else None

    def select_float(self, page_idx: int | None, item: Any | None) -> None:
        self._float_sel = (page_idx, item) if item is not None and page_idx is not None else None
        self.viewport().update()

    def _selected_float_box(self) -> tuple[int, Any] | None:
        if not self._float_sel or not self.pagination.pages:
            return None
        from atboffice.modules.writer.views import float_edit

        page_idx, item = self._float_sel
        pages = self.pagination.pages
        order = [page_idx] + [i for i in range(len(pages)) if i != page_idx]
        for idx in order:  # relayout may move the object to another page
            if 0 <= idx < len(pages):
                fb = float_edit.box_for_item(pages[idx], item)
                if fb is not None:
                    return idx, fb
        return None

    def _float_press(self, page_idx: int, pt: QPointF) -> bool:
        """Start selecting/moving/resizing a floating object. True when consumed."""
        from atboffice.modules.writer.views import float_edit

        if not self.pagination.pages:
            return False
        tol = self.px_to_pt(5.0)
        found = self._selected_float_box()
        if found is not None and found[0] == page_idx:
            handle = float_edit.handle_at(found[1], pt, tol)
            if handle is not None:
                fb = found[1]
                self._float_drag = float_edit.FloatDrag(
                    page_idx, fb.item, handle, QPointF(pt), (fb.x, fb.y, fb.w, fb.h)
                )
                return True
        page = self.pagination.pages[max(0, min(page_idx, len(self.pagination.pages) - 1))]
        fb = float_edit.float_at(page, pt)
        if fb is None or getattr(fb.item, "float_pr", None) is None:
            if self._float_sel is not None:
                self.select_float(None, None)
            return False
        self.setFocus()
        self.select_float(page_idx, fb.item)
        self._float_drag = float_edit.FloatDrag(
            page_idx, fb.item, None, QPointF(pt), (fb.x, fb.y, fb.w, fb.h)
        )
        return True

    def _float_release(self, pt: QPointF, lock_aspect: bool = False) -> None:
        from atboffice.modules.writer.views import float_edit

        drag, self._float_drag = self._float_drag, None
        if drag is None:
            return
        changed = self.run_undoable(lambda: float_edit.apply_drag(drag, pt, lock_aspect))
        if changed is False:
            self.viewport().update()

    def delete_selected_float(self) -> bool:
        """Remove the selected floating object from its paragraph (one undo step)."""
        item = self.selected_float()
        if item is None:
            return False

        from atboffice.modules.writer.models.document import all_stories

        def mutate() -> bool:
            for story in all_stories(self.doc):
                for para in story.paras:
                    for i, run in enumerate(para.runs):
                        if run is item:
                            del para.runs[i]
                            return True
            return False

        self._float_sel = None
        return bool(self.run_undoable(mutate))

    def _float_key(self, event: QKeyEvent) -> bool:
        key = event.key()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            return self.delete_selected_float()
        if key == Qt.Key.Key_Escape:
            self.select_float(None, None)
            return True
        self.select_float(None, None)  # typing returns to the text
        return False

    def _paint_float_selection(
        self, painter: QPainter, p_idx: int, page_rect: QRectF, page: Page
    ) -> None:
        from atboffice.modules.writer.views import float_edit

        drag = self._float_drag
        if drag is not None and drag.page_index == p_idx and drag.current is not None:
            float_edit.paint_selection(
                painter, page_rect, self.pt_to_px, float_edit.preview_box(drag), dashed=True
            )
        found = self._selected_float_box()
        if found is not None and found[0] == p_idx:
            fb = found[1]
            float_edit.paint_selection(painter, page_rect, self.pt_to_px, (fb.x, fb.y, fb.w, fb.h))

    def _float_hover_cursor(self, vp_pt: QPoint) -> bool:
        from atboffice.modules.writer.views import float_edit

        if not self.pagination.pages:
            return False
        page_idx, pt = self.viewport_to_doc_coords(vp_pt)
        found = self._selected_float_box()
        if found is not None and found[0] == page_idx:
            handle = float_edit.handle_at(found[1], pt, self.px_to_pt(5.0))
            if handle is not None:
                self.viewport().setCursor(float_edit.cursor_for(handle))
                return True
        page = self.pagination.pages[max(0, min(page_idx, len(self.pagination.pages) - 1))]
        fb = float_edit.float_at(page, pt)
        if fb is not None and getattr(fb.item, "float_pr", None) is not None:
            self.viewport().setCursor(float_edit.cursor_for(None))
            return True
        return False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Dispatch keyboard events to CaretController or trigger F7 spelling dialog."""
        if event.key() == Qt.Key.Key_F7:
            self.open_spelling_dialog()
            event.accept()
            return

        if self._float_sel is not None and self._float_key(event):
            event.accept()
            return

        if self.controller.handle_key_event(event):
            event.accept()
            self.scroll_to_caret()
            self.viewport().update()
        else:
            super().keyPressEvent(event)

    def open_spelling_dialog(self) -> None:
        """Open Spelling and Grammar check modal dialog (F7)."""
        from atboffice.modules.writer.dialogs.spelling_dialog import SpellingGrammarDialog

        dlg = SpellingGrammarDialog(self.doc, controller=self.controller, parent=self)
        dlg.exec()
        self.viewport().update()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Display right-click context menu with spelling corrections or standard actions."""
        pos_pt = self._event_pos(event)
        page_idx, pt_doc = self.viewport_to_doc_coords(pos_pt)
        pos = self.controller.canvas_to_pos(page_idx, pt_doc)

        menu = QMenu(self)
        p = self.controller._paragraph_by_id(pos.para_id)
        misspelled_word = None
        word_start = 0
        word_end = 0

        if p:
            pt = ptext(p)
            for w, s, e in self.spell_engine.tokenize_words(pt):
                if s <= pos.offset <= e:
                    if not self.spell_engine.is_valid_word(w):
                        misspelled_word = w
                        word_start = s
                        word_end = e
                    break

        if misspelled_word and p is not None:
            suggestions = self.spell_engine.suggest(misspelled_word, max_suggestions=5)
            if suggestions:
                for sugg in suggestions:
                    act = menu.addAction(sugg)
                    bold_font = act.font()
                    bold_font.setBold(True)
                    act.setFont(bold_font)

                    def _make_handler(target_sugg: str, para: Paragraph, s: int, e: int):
                        return lambda: self._replace_word_in_para(para, s, e, target_sugg)

                    act.triggered.connect(_make_handler(sugg, p, word_start, word_end))
            else:
                act_no_sugg = menu.addAction(safe_tr("(无拼写建议)"))
                act_no_sugg.setEnabled(False)

            menu.addSeparator()

            act_ignore = menu.addAction(safe_tr("全部忽略(&I)"))
            act_ignore.triggered.connect(
                lambda checked=False, w=misspelled_word: self._ignore_word_all(w)
            )

            act_add = menu.addAction(safe_tr("添加到词典(&A)"))
            act_add.triggered.connect(
                lambda checked=False, w=misspelled_word: self._add_word_to_dict(w)
            )

            menu.addSeparator()

        # Standard editing actions
        act_cut = menu.addAction(safe_tr("剪切(&T)"))
        act_cut.setEnabled(not self.controller.selection.is_collapsed)
        act_cut.triggered.connect(self.cut_selection)

        act_copy = menu.addAction(safe_tr("复制(&C)"))
        act_copy.setEnabled(not self.controller.selection.is_collapsed)
        act_copy.triggered.connect(self.copy_selection)

        act_paste = menu.addAction(safe_tr("粘贴(&P)"))
        act_paste.triggered.connect(self.paste_from_clipboard)

        menu.addSeparator()
        act_select_all = menu.addAction(safe_tr("全选(&A)"))
        act_select_all.triggered.connect(self.controller.select_all)

        menu.exec(event.globalPos())

    def _replace_word_in_para(self, p: Paragraph, start: int, end: int, replacement: str) -> None:
        """Replace text span in paragraph and refresh canvas."""
        delete_range_in_paragraph(p, start, end)
        insert_text_in_paragraph(p, start, replacement)
        self.controller.pos = DocPos(p.id, start + len(replacement))
        self.controller.selection = Selection(self.controller.pos, self.controller.pos)
        self.controller.repaginate_and_refresh()
        self.viewport().update()

    def _ignore_word_all(self, word: str) -> None:
        """Ignore word in session and repaint."""
        self.spell_engine.ignore_all(word)
        self.viewport().update()

    def _add_word_to_dict(self, word: str) -> None:
        """Add word to custom dictionary and repaint."""
        self.spell_engine.add_to_custom_dict(word)
        self.viewport().update()

    def copy_selection(self) -> None:
        """Copy the selection as plain text and formatted HTML (Office Clipboard keeps both)."""
        from PySide6.QtCore import QMimeData

        text = self.controller.get_selected_text()
        if not text:
            return
        cb = QGuiApplication.clipboard()
        if not cb:
            return
        mime = QMimeData()
        mime.setText(text)
        html_text = self._selection_html()
        if html_text:
            mime.setHtml(html_text)
        cb.setMimeData(mime)

    def _selection_html(self) -> str:
        from atboffice.modules.writer.io.clipboard_html import selection_html
        from atboffice.modules.writer.models.document import paras_between

        ctl = self.controller
        if ctl.selection.is_collapsed:
            return ""
        start, end = ctl.selection.ordered_range(self.doc)
        p_start = ctl._paragraph_by_id(start.para_id)
        p_end = ctl._paragraph_by_id(end.para_id)
        if p_start is None or p_end is None:
            return ""
        if p_start is p_end:
            return selection_html([(p_start, start.offset, end.offset)])
        paras = paras_between(self.doc, p_start, p_end)
        segments = []
        for i, para in enumerate(paras):
            a = start.offset if i == 0 else 0
            b = end.offset if i == len(paras) - 1 else None
            segments.append((para, a, b))
        return selection_html(segments)

    def cut_selection(self) -> None:
        """Cut selected text to system clipboard."""
        self.copy_selection()
        with self.controller.edit_scope("剪切"):
            self.controller.delete_selection()

    def paste_from_clipboard(self) -> None:
        """Paste plain text from system clipboard."""
        cb = QGuiApplication.clipboard()
        if cb:
            text = cb.text()
            if text:
                with self.controller.edit_scope("粘贴"):
                    self.controller.insert_text(text)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Update scroll ranges and repaginate/repaint upon resize."""
        super().resizeEvent(event)
        if self.view_mode == ViewMode.WEB:
            self._apply_web_width()
        self._update_scroll_ranges()

    # -----------------------------------------------------------------------
    # Paragraph & Character Formatting Operations
    # -----------------------------------------------------------------------

    def _get_selected_paragraphs(self) -> list[Paragraph]:
        """Return all paragraphs covered by the current selection."""
        if self.controller.selection.is_collapsed:
            p = self.controller._paragraph_by_id(self.controller.pos.para_id)
            return [p] if p is not None else []
        a, b = self.controller.selection.ordered_range(self.doc)
        pa = self.controller._paragraph_by_id(a.para_id)
        pb = self.controller._paragraph_by_id(b.para_id)
        if pa is not None and pb is not None:
            return paras_between(self.doc, pa, pb)
        return [pa] if pa is not None else []

    @_undoable("设置格式")
    def set_paragraph_alignment(self, jc: str) -> None:
        """Set paragraph alignment (left, center, right, both/justify)."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            p.p_pr.jc = jc
        self._on_formatting_applied()

    @_undoable("段落缩进")
    def change_indent(self, delta_pt: float) -> None:
        """Increase or decrease left indent for selected paragraphs."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            if p.p_pr.ind is None:
                p.p_pr.ind = IndentProperties()
            p.p_pr.ind.left = max(0.0, (p.p_pr.ind.left or 0.0) + delta_pt)
        self._on_formatting_applied()

    @_undoable("设置格式")
    def set_line_spacing(self, line: float, line_rule: str = "auto") -> None:
        """Set line spacing multiplier (e.g. 1.0, 1.5, 2.0)."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            if p.p_pr.sp is None:
                p.p_pr.sp = SpacingProperties()
            p.p_pr.sp.line = line
            p.p_pr.sp.line_rule = line_rule
        self._on_formatting_applied()

    @_undoable("项目符号和编号")
    def toggle_list_style(self, kind: str) -> None:
        """Toggle bullet or numbering list on selected paragraphs."""
        paras = self._get_selected_paragraphs()
        if not paras:
            return
        first = paras[0]
        has_num = first.p_pr and first.p_pr.num is not None
        num_target = "1" if kind == "bullet" else "2"
        is_same = has_num and first.p_pr.num.id == num_target

        for p in paras:
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            if is_same:
                p.p_pr.num = None
            else:
                p.p_pr.num = NumberingRef(id=num_target, lvl=0)
        self._on_formatting_applied()

    def format_range(self, fn: Callable[[RunProperties], None]) -> None:
        """Apply a formatting function to all runs in the current selection (one undo step)."""
        with self.controller.edit_scope("设置格式"):
            self._format_range(fn)

    def _format_range(self, fn: Callable[[RunProperties], None]) -> None:
        if self.controller.selection.is_collapsed:
            p = self.controller._paragraph_by_id(self.controller.pos.para_id)
            if p is not None:
                if p.r_pr is None:
                    p.r_pr = RunProperties()
                fn(p.r_pr)
                for r in p.runs:
                    if getattr(r, "t", "") == "text":
                        if r.r_pr is None:
                            r.r_pr = RunProperties()
                        fn(r.r_pr)
        else:
            a, b = self.controller.selection.ordered_range(self.doc)
            pa = self.controller._paragraph_by_id(a.para_id)
            pb = self.controller._paragraph_by_id(b.para_id)
            if pa is not None and pb is not None:
                paras = paras_between(self.doc, pa, pb)
                for p in paras:
                    s = a.offset if p == pa else 0
                    e = b.offset if p == pb else plen(p)
                    if s < e:
                        i0 = split_at(p, s)
                        i1 = split_at(p, e)
                        for i in range(i0, i1):
                            it = p.runs[i]
                            if getattr(it, "t", "") == "text":
                                if it.r_pr is None:
                                    it.r_pr = RunProperties()
                                fn(it.r_pr)
                        normalize(p)
        self._on_formatting_applied()

    def toggle_character_format(self, attr: str) -> None:
        """Toggle a boolean or choice character formatting attribute."""
        curr_val = False
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if p is not None:
            if attr == "bold":
                curr_val = bool(p.r_pr and p.r_pr.b)
            elif attr == "italic":
                curr_val = bool(p.r_pr and p.r_pr.i)
            elif attr == "underline":
                curr_val = bool(p.r_pr and p.r_pr.u and p.r_pr.u != "none")
            elif attr == "strike":
                curr_val = bool(p.r_pr and p.r_pr.strike)
            elif attr == "superscript":
                curr_val = bool(p.r_pr and p.r_pr.vert == "superscript")
            elif attr == "subscript":
                curr_val = bool(p.r_pr and p.r_pr.vert == "subscript")

        def _apply(r: RunProperties) -> None:
            if attr == "bold":
                r.b = not curr_val
            elif attr == "italic":
                r.i = not curr_val
            elif attr == "underline":
                r.u = "none" if curr_val else "single"
            elif attr == "strike":
                r.strike = not curr_val
                r.strike_off = curr_val
            elif attr == "superscript":
                r.vert = "baseline" if curr_val else "superscript"
            elif attr == "subscript":
                r.vert = "baseline" if curr_val else "subscript"

        self.format_range(_apply)

    def set_font_family(self, name: str) -> None:
        """Set font family for selection."""
        self.format_range(lambda r: setattr(r, "font", name))

    def set_font_size(self, size_pt: float) -> None:
        """Set font size in points for selection."""
        self.format_range(lambda r: setattr(r, "sz", size_pt))

    def set_font_color(self, color: str) -> None:
        """Set font color (hex string or 'auto') for selection."""
        self.format_range(lambda r: setattr(r, "color", color))

    def set_highlight_color(self, color: str | None) -> None:
        """Highlight the selection with a Word highlight colour; ``None``/"none" removes it.

        Accepts a w:highlight name ("yellow") or one of the palette's hex colours.
        """
        from atboffice.ui.components.color_picker import HIGHLIGHT_NAME_BY_HEX

        if color in (None, "", "none", "auto"):
            value: str | None = None
        else:
            value = HIGHLIGHT_NAME_BY_HEX.get(str(color).upper(), str(color))
        self.run_undoable(lambda: self.format_range(lambda r: setattr(r, "highlight", value)))

    def get_current_style_id(self) -> str:
        """Return the paragraph style ID at the current caret position."""
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if p and p.p_pr and p.p_pr.style:
            return p.p_pr.style
        return "Normal"

    @_undoable("样式", ("styles",))
    def apply_style(self, style_id: str) -> None:
        """Apply a named style to the currently selected paragraph(s)."""
        from atboffice.modules.writer.models.styles import builtin_styles

        if style_id not in self.doc.styles:
            b_styles = builtin_styles()
            if style_id in b_styles:
                self.doc.styles[style_id] = copy.deepcopy(b_styles[style_id])

        paras = self._get_selected_paragraphs()
        if not paras:
            p = self.controller._paragraph_by_id(self.controller.pos.para_id)
            if p is not None:
                paras = [p]

        for p in paras:
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            p.p_pr.style = style_id

        self._on_formatting_applied()

    @_undoable("清除格式")
    def clear_formatting(self) -> None:
        """Reset paragraph style to Normal and clear run character overrides."""
        paras = self._get_selected_paragraphs()
        if not paras:
            p = self.controller._paragraph_by_id(self.controller.pos.para_id)
            if p is not None:
                paras = [p]

        for p in paras:
            if p.p_pr is not None:
                p.p_pr.style = "Normal"
                p.p_pr.jc = "left"
                p.p_pr.num = None
            if p.r_pr is not None:
                p.r_pr = RunProperties()
            for r in p.runs:
                if getattr(r, "t", "") == "text":
                    r.r_pr = RunProperties()

        self._on_formatting_applied()

    def _on_formatting_applied(self) -> None:
        """Repaginate and re-render in place (keeps undo history, caret and selection)."""
        self.refresh_layout()

    # -----------------------------------------------------------------------
    # Table Operations
    # -----------------------------------------------------------------------

    def get_current_table_context(self) -> dict[str, Any] | None:
        """Return table, row, cell and grid coordinates if caret is within a table."""
        inf = info(self.doc, self.controller.pos.para_id)
        if not inf or not inf.get("parents"):
            return None
        for parent in inf["parents"]:
            if isinstance(parent, dict) and "tbl" in parent:
                tbl = parent["tbl"]
                cell = parent.get("cell")
                r_idx, c_idx = 0, 0
                grid = table_map(tbl)
                for r_i, row in enumerate(grid):
                    for entry in row:
                        if entry.cell is cell:
                            r_idx, c_idx = entry.row_idx, entry.col_idx
                            break
                return {
                    "tbl": tbl,
                    "row": parent.get("row"),
                    "cell": cell,
                    "row_idx": r_idx,
                    "col_idx": c_idx,
                }
        return None

    @_undoable("插入表格")
    def insert_table(self, rows: int = 2, cols: int = 2) -> None:
        """Insert a new table at the current position."""
        tbl = create_simple_table(rows, cols)
        inf = info(self.doc, self.controller.pos.para_id)
        story = inf["story"] if inf and "story" in inf else self.doc.main
        curr_p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        idx = story.blocks.index(curr_p) if curr_p in story.blocks else len(story.blocks)
        story.blocks.insert(idx + 1, tbl)
        reindex(self.doc)
        first_p = tbl.rows[0].cells[0].blocks[0]
        self.controller.pos = DocPos(first_p.id, 0)
        self.controller.selection = Selection(self.controller.pos, self.controller.pos)
        self.controller.repaginate_and_refresh()

    @_undoable("插入行")
    def insert_table_row(self, above: bool = False) -> None:
        """Insert a row above or below current cell."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        insert_rows(tbl, r_idx, count=1, above=above)
        self._on_formatting_applied()

    @_undoable("插入列")
    def insert_table_col(self, left: bool = False) -> None:
        """Insert a column to the left or right of current cell."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        c_idx = ctx["col_idx"]
        insert_cols(tbl, c_idx, count=1, left=left)
        self._on_formatting_applied()

    @_undoable("删除行")
    def delete_table_row(self) -> None:
        """Delete the current table row."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        if len(tbl.rows) > 1:
            target_r = r_idx - 1 if r_idx > 0 else r_idx + 1
            surviving_p = tbl.rows[target_r].cells[0].blocks[0]
            delete_rows(tbl, r_idx, r_idx)
            self._on_formatting_applied()
            self.controller.pos = DocPos(surviving_p.id, 0)
            self.controller.selection = Selection(self.controller.pos, self.controller.pos)
            self.controller.caret_changed.emit()

    @_undoable("删除列")
    def delete_table_col(self) -> None:
        """Delete the current table column."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        c_idx = ctx["col_idx"]
        r_idx = ctx["row_idx"]
        if len(tbl.grid) > 1:
            delete_cols(tbl, c_idx, c_idx)
            self._on_formatting_applied()
            grid = table_map(tbl)
            target_c = min(c_idx, len(tbl.grid) - 1)
            target_r = min(r_idx, len(tbl.rows) - 1)
            surviving_cell = grid[target_r][target_c].cell
            surviving_p = surviving_cell.blocks[0] if surviving_cell.blocks else None
            if surviving_p is not None:
                self.controller.pos = DocPos(surviving_p.id, 0)
                self.controller.selection = Selection(self.controller.pos, self.controller.pos)
                self.controller.caret_changed.emit()

    @_undoable("合并单元格")
    def merge_table_cells(self) -> None:
        """Merge cells in the current table."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        c_idx = ctx["col_idx"]
        if c_idx + 1 < len(tbl.grid):
            merge_cells(tbl, r_idx, r_idx, c_idx, c_idx + 1)
            self._on_formatting_applied()

    @_undoable("拆分单元格")
    def split_table_cells(self, num_rows: int = 1, num_cols: int = 2) -> None:
        """Split the current cell into num_rows x num_cols."""
        ctx = self.get_current_table_context()
        if not ctx or not ctx["cell"]:
            return
        split_cells(ctx["tbl"], ctx["cell"], num_rows, num_cols)
        self._on_formatting_applied()

    @_undoable("平均分布各行")
    def distribute_table_rows(self) -> None:
        """Equalize height of all rows in current table."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        for row in tbl.rows:
            row.tr_pr.h = 24.0
            row.tr_pr.h_rule = "exact"
        self._on_formatting_applied()

    @_undoable("平均分布各列")
    def distribute_table_cols(self) -> None:
        """Equalize width of all columns in current table."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        if tbl.grid:
            avg = sum(tbl.grid) / len(tbl.grid)
            tbl.grid = [round(avg, 2)] * len(tbl.grid)
        self._on_formatting_applied()

    @_undoable("排序")
    def sort_table(self, ascending: bool = True) -> None:
        """Sort data rows of the current table by the current column text."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        c_idx = ctx["col_idx"]
        if len(tbl.rows) > 1:
            grid = table_map(tbl)

            def _key(row_entry: list):
                if c_idx < len(row_entry):
                    p = row_entry[c_idx].cell.blocks[0] if row_entry[c_idx].cell.blocks else None
                    return ptext(p) if p else ""
                return ""

            header = tbl.rows[0]
            rest = tbl.rows[1:]
            rest.sort(key=lambda r: _key(grid[tbl.rows.index(r)]), reverse=not ascending)
            tbl.rows = [header] + rest
            self._on_formatting_applied()

    @_undoable("自动求和")
    def auto_sum_table(self) -> None:
        """Calculate and insert the sum of numbers above current cell."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        c_idx = ctx["col_idx"]
        grid = table_map(tbl)
        total = 0.0
        for r in range(r_idx):
            cell = grid[r][c_idx].cell
            for b in cell.blocks:
                if isinstance(b, Paragraph):
                    txt = ptext(b).strip()
                    try:
                        total += float(txt)
                    except ValueError:
                        pass
        curr_p = ctx["cell"].blocks[0] if ctx["cell"].blocks else None
        if curr_p is not None:
            curr_p.runs = [TextItem(text=f"{total:g}", r_pr=copy.deepcopy(curr_p.r_pr))]
            self._on_formatting_applied()

    # -----------------------------------------------------------------------
    # Revision & Comment Operations
    # -----------------------------------------------------------------------

    def toggle_track_changes(self) -> bool:
        """Toggle track changes mode on document."""
        res = toggle_tracking(self.doc)
        self._on_formatting_applied()
        return res

    @_undoable_document("接受修订")
    def accept_current_revision(self, all_revisions: bool = False) -> None:
        """Accept revision at current position or all revisions."""
        if all_revisions:
            accept_all_revisions(self.doc)
        else:
            revs = list_revisions(self.doc)
            if revs:
                accept_revision(self.doc, revs[0])
        self._on_formatting_applied()

    @_undoable_document("拒绝修订")
    def reject_current_revision(self, all_revisions: bool = False) -> None:
        """Reject revision at current position or all revisions."""
        if all_revisions:
            reject_all_revisions(self.doc)
        else:
            revs = list_revisions(self.doc)
            if revs:
                reject_revision(self.doc, revs[0])
        self._on_formatting_applied()

    @_undoable("插入批注", ("comments",))
    def insert_comment(self, author: str = "User", text: str = "") -> None:
        """Insert a comment on the current paragraph/selection."""
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if p is not None:
            a, b = self.controller.selection.ordered_range(self.doc)
            s = a.offset if a.para_id == p.id else 0
            e = b.offset if b.para_id == p.id else plen(p)
            insert_comment(
                self.doc,
                (p, s),
                (p, max(s + 1, e)),
                text=text or safe_tr("新批注"),
                author=author,
            )
            self._on_formatting_applied()

    @_undoable("大纲级别")
    def change_outline_level(self, delta: int) -> None:
        """Promote (delta < 0) or demote (delta > 0) outline level."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            curr = p.p_pr.outline_level or 1
            new_lvl = max(1, min(9, curr + delta))
            p.p_pr.outline_level = new_lvl
        self._on_formatting_applied()

    @_undoable("大纲级别")
    def set_outline_level(self, level: int | None) -> None:
        """Set outline level (1-9 or None for body text)."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            p.p_pr.outline_level = level
        self._on_formatting_applied()

    @_undoable("移动段落")
    def move_paragraph(self, delta: int) -> None:
        """Move selected paragraph up (delta < 0) or down (delta > 0)."""
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if not p:
            return
        inf = info(self.doc, p)
        story = inf["story"] if inf and "story" in inf else self.doc.main
        if p in story.blocks:
            idx = story.blocks.index(p)
            new_idx = idx + delta
            if 0 <= new_idx < len(story.blocks):
                story.blocks.pop(idx)
                story.blocks.insert(new_idx, p)
                self._on_formatting_applied()

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
