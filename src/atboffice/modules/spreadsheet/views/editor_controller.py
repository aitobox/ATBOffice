"""In-cell editor overlay and editor controller for ATBOffice Ledger."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import QCoreApplication, QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeyEvent
from PySide6.QtWidgets import QLineEdit, QWidget

from atboffice.modules.spreadsheet.calc.evaluator import evaluate_ast
from atboffice.modules.spreadsheet.calc.parser import parse, tokenize
from atboffice.modules.spreadsheet.calc.references import cell_name
from atboffice.modules.spreadsheet.calc.tokens import TokenType
from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionModel,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
    SheetDataModel,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.views.formula_bar import FormulaBar
    from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport


def safe_tr(text: str) -> str:
    """Translate UI text safely for EditorController."""
    return QCoreApplication.translate("EditorController", text)


class EditorMode(Enum):
    """Active editing mode."""

    READY = auto()
    ENTER = auto()
    EDIT = auto()
    POINT = auto()


@dataclass
class ReferenceHighlight:
    """Colored bounding box highlight for a cell or area reference in formula."""

    r1: int
    c1: int
    r2: int
    c2: int
    color: QColor


# Excel 2003 reference highlight color palette
HIGHLIGHT_PALETTE: Final[list[QColor]] = [
    QColor("#0000FF"),  # Blue
    QColor("#008000"),  # Green
    QColor("#9900CC"),  # Purple
    QColor("#800000"),  # Dark Red
    QColor("#00CC33"),  # Lime Green
    QColor("#CC6600"),  # Orange
    QColor("#CC0099"),  # Magenta
]


class InCellEditor(QLineEdit):
    """Floating QLineEdit overlaying the active grid cell."""

    commit_requested = Signal()
    commit_and_move_requested = Signal(int, int)
    cancel_requested = Signal()
    f2_pressed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrame(False)
        self.setStyleSheet(
            "QLineEdit { border: 2px solid #214283; background: #ffffff; padding: 1px; }"
        )
        self.hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.commit_and_move_requested.emit(-1, 0)
            else:
                self.commit_and_move_requested.emit(1, 0)
            event.accept()
            return

        if key == Qt.Key.Key_Tab:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.commit_and_move_requested.emit(0, -1)
            else:
                self.commit_and_move_requested.emit(0, 1)
            event.accept()
            return

        if key == Qt.Key.Key_Escape:
            self.cancel_requested.emit()
            event.accept()
            return

        if key == Qt.Key.Key_F2:
            self.f2_pressed.emit()
            event.accept()
            return

        super().keyPressEvent(event)


class EditorController(QObject):
    """Coordinates in-cell editing, formula bar two-way binding, and formula pointing."""

    mode_changed = Signal(str)
    highlights_changed = Signal(list)
    cell_committed = Signal(int, int, object)

    def __init__(
        self,
        viewport: GridViewport,
        model: SheetDataModel,
        selection: SelectionModel,
        formula_bar: FormulaBar | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.viewport = viewport
        self.model = model
        self.selection = selection
        self.formula_bar = formula_bar

        self.mode: EditorMode = EditorMode.READY
        self.active_row: int = 0
        self.active_col: int = 0
        self.original_text: str = ""
        self._syncing: bool = False
        self._point_start: int = 0
        self._point_len: int = 0
        self.highlights: list[ReferenceHighlight] = []

        # Create the in-cell editor widget inside the viewport's drawing area
        self.in_cell_editor = InCellEditor(self.viewport.viewport())
        self.in_cell_editor.textChanged.connect(self._on_in_cell_text_changed)
        self.in_cell_editor.commit_requested.connect(self.commit)
        self.in_cell_editor.commit_and_move_requested.connect(
            self.commit_and_move
        )
        self.in_cell_editor.cancel_requested.connect(self.cancel)
        self.in_cell_editor.f2_pressed.connect(self.toggle_mode)

        # Connect formula bar if provided
        if self.formula_bar is not None:
            self.formula_bar.text_changed.connect(
                self._on_formula_bar_text_changed
            )
            self.formula_bar.commit_requested.connect(self.commit)
            self.formula_bar.cancel_requested.connect(self.cancel)
            self.formula_bar.fx_requested.connect(self._on_fx_clicked)

        # Listen to selection changes to update NameBox and formula text when idle
        self.selection.active_cell_changed.connect(self._on_selection_changed)
        self.selection.selection_changed.connect(self._on_selection_range_changed)
        self.viewport.cell_double_clicked.connect(self._on_cell_double_clicked)

        self._update_name_box()
        self._update_formula_bar_from_model()

    @property
    def is_active(self) -> bool:
        """Return True if currently in any active editing mode."""
        return self.mode != EditorMode.READY

    def begin_edit(
        self,
        r: int,
        c: int,
        mode: EditorMode = EditorMode.EDIT,
        initial_text: str | None = None,
    ) -> None:
        """Activate editing on cell (r, c)."""
        if self.is_active:
            self.commit()

        self.active_row = r
        self.active_col = c
        self.selection.select_cell(r, c)
        self.viewport.reveal(r, c)

        cell = self.model.get_cell(r, c)
        if cell is not None and cell.formula:
            self.original_text = f"={cell.formula}"
        elif cell is not None and cell.value is not None:
            self.original_text = str(cell.value)
        else:
            self.original_text = ""

        edit_text = (
            initial_text if initial_text is not None else self.original_text
        )

        self._syncing = True
        self.in_cell_editor.setText(edit_text)
        if self.formula_bar is not None:
            self.formula_bar.set_text(edit_text)
            self.formula_bar.set_editing_state(True)
        self._syncing = False

        self._style_in_cell_editor(cell)
        self.reposition_editor()
        self.in_cell_editor.show()
        self.in_cell_editor.setFocus()
        if mode == EditorMode.EDIT:
            self.in_cell_editor.selectAll()
        else:
            self.in_cell_editor.setCursorPosition(len(edit_text))

        self.mode = mode
        if self._is_formula(edit_text) and self._operand_at():
            self.mode = EditorMode.POINT

        self.mode_changed.emit(self.mode.name.lower())
        self.update_highlights(edit_text)

    def _style_in_cell_editor(self, cell: CellData | None) -> None:
        """Apply cell font and alignment styles to in-cell editor."""
        font = (
            QFont(cell.font_family, cell.font_size)
            if cell is not None
            else QFont("Arial", 10)
        )
        if cell is not None:
            font.setBold(cell.bold)
            font.setItalic(cell.italic)
            font.setUnderline(cell.underline)
        self.in_cell_editor.setFont(font)

        align = Qt.AlignmentFlag.AlignLeft
        if cell is not None:
            if cell.align_h == "center":
                align = Qt.AlignmentFlag.AlignCenter
            elif cell.align_h == "right":
                align = Qt.AlignmentFlag.AlignRight
        self.in_cell_editor.setAlignment(align)

    def reposition_editor(self) -> None:
        """Position and size in-cell editor over active cell in viewport coordinates."""
        if not self.is_active:
            return

        scroll_x = self.viewport.horizontalScrollBar().value()
        scroll_y = self.viewport.verticalScrollBar().value()
        mapper = self.viewport.geometry_mapper

        cell_x = (
            self.viewport.row_header_width
            + mapper.col_pos(self.active_col)
            - scroll_x
        )
        cell_y = (
            self.viewport.col_header_height
            + mapper.row_pos(self.active_row)
            - scroll_y
        )
        cell_w = mapper.col_size(self.active_col)
        cell_h = mapper.row_size(self.active_row)

        # Grow horizontally to fit text without clipping
        fm = QFontMetrics(self.in_cell_editor.font())
        text_w = fm.horizontalAdvance(self.in_cell_editor.text()) + 16
        vw = self.viewport.viewport().width()
        w = max(cell_w, min(vw - cell_x - 2, text_w))
        h = max(cell_h, 20)

        self.in_cell_editor.setGeometry(cell_x, cell_y, w, h)

    def commit_and_move(self, dr: int, dc: int) -> None:
        """Commit current entry and navigate active cell by (dr, dc)."""
        ok = self.commit()
        if ok and (dr != 0 or dc != 0):
            target_r = max(
                0,
                min(
                    self.viewport.geometry_mapper.max_rows - 1,
                    self.active_row + dr,
                ),
            )
            target_c = max(
                0,
                min(
                    self.viewport.geometry_mapper.max_cols - 1,
                    self.active_col + dc,
                ),
            )
            self.selection.select_cell(target_r, target_c)
            self.viewport.reveal(target_r, target_c)
            self.viewport.cell_selected.emit(target_r, target_c)
            self.viewport.viewport().update()

    def commit(self) -> bool:
        """Commit current edit text into the model."""
        if not self.is_active:
            return True

        text = self.in_cell_editor.text().strip()
        r, c = self.active_row, self.active_col

        if text.startswith("="):
            # Formula entry
            formula_body = text[1:].strip()
            val = None
            try:
                ast = parse(formula_body)
                val = evaluate_ast(ast)
            except Exception:
                val = None

            cell = self.model.get_cell(r, c)
            if cell is None:
                cell = CellData(value=val, formula=formula_body)
                self.model.set_cell(r, c, cell)
            else:
                cell.formula = formula_body
                if val is not None:
                    cell.value = val
        else:
            # Literal value
            parsed_val: Any = text
            if text == "":
                parsed_val = None
            elif text.upper() == "TRUE":
                parsed_val = True
            elif text.upper() == "FALSE":
                parsed_val = False
            else:
                try:
                    if "." in text or "e" in text.lower():
                        parsed_val = float(text)
                    else:
                        parsed_val = int(text)
                except ValueError:
                    parsed_val = text

            cell = self.model.get_cell(r, c)
            if cell is None:
                cell = CellData(value=parsed_val, formula=None)
                self.model.set_cell(r, c, cell)
            else:
                cell.value = parsed_val
                cell.formula = None

        self._end_edit()
        self.cell_committed.emit(r, c, text)
        self.viewport.viewport().update()
        return True

    def cancel(self) -> None:
        """Cancel current edit and revert to original value."""
        if not self.is_active:
            return
        self._end_edit()
        self.viewport.viewport().update()

    def _end_edit(self) -> None:
        """Reset editor state back to READY."""
        self.in_cell_editor.hide()
        self.mode = EditorMode.READY
        self.highlights.clear()
        self.highlights_changed.emit(self.highlights)
        self.mode_changed.emit("ready")

        if self.formula_bar is not None:
            self.formula_bar.set_editing_state(False)
            self._update_formula_bar_from_model()

        self.viewport.setFocus()

    def toggle_mode(self) -> None:
        """Toggle between EDIT and ENTER mode on F2."""
        if self.mode == EditorMode.EDIT:
            self.mode = EditorMode.ENTER
        elif self.mode in (EditorMode.ENTER, EditorMode.POINT):
            self.mode = EditorMode.EDIT
        self.mode_changed.emit(self.mode.name.lower())

    def point_at(self, r1: int, c1: int, r2: int, c2: int) -> None:
        """Insert or replace cell/range reference while in Point mode."""
        if not self.is_active:
            return

        ref_str = (
            cell_name(r1, c1)
            if r1 == r2 and c1 == c2
            else f"{cell_name(r1, c1)}:{cell_name(r2, c2)}"
        )

        curr_text = self.in_cell_editor.text()
        pos = self.in_cell_editor.cursorPosition()

        if self.mode == EditorMode.POINT and self._point_len > 0:
            # Replace previous pointed reference
            start = self._point_start
            new_text = (
                curr_text[:start] + ref_str + curr_text[start + self._point_len :]
            )
            self._point_len = len(ref_str)
            new_pos = start + len(ref_str)
        else:
            # Insert at caret
            start = pos
            new_text = curr_text[:start] + ref_str + curr_text[start:]
            self._point_start = start
            self._point_len = len(ref_str)
            new_pos = start + len(ref_str)
            self.mode = EditorMode.POINT
            self.mode_changed.emit("point")

        self._sync_text(new_text, new_pos)
        self.update_highlights(new_text)

    def _sync_text(self, text: str, cursor_pos: int | None = None) -> None:
        """Update both in-cell and formula bar editors synchronously."""
        self._syncing = True
        self.in_cell_editor.setText(text)
        if cursor_pos is not None:
            self.in_cell_editor.setCursorPosition(cursor_pos)
        if self.formula_bar is not None:
            self.formula_bar.set_text(text)
            if cursor_pos is not None:
                self.formula_bar.formula_input.setCursorPosition(cursor_pos)
        self._syncing = False
        self.reposition_editor()

    def update_highlights(self, formula_text: str) -> None:
        """Tokenize formula text and generate colored bounding boxes for references."""
        self.highlights.clear()
        if not formula_text.startswith("="):
            self.highlights_changed.emit(self.highlights)
            self.viewport.viewport().update()
            return

        formula_body = formula_text[1:]
        try:
            tokens = tokenize(formula_body)
        except Exception:
            self.highlights_changed.emit(self.highlights)
            self.viewport.viewport().update()
            return

        color_idx = 0
        seen_ranges: dict[tuple[int, int, int, int], QColor] = {}

        for tok in tokens:
            if tok.t == TokenType.REF:
                if tok.kind == "cell":
                    r1, c1, r2, c2 = tok.r, tok.c, tok.r, tok.c
                elif tok.kind == "area":
                    r1 = min(getattr(tok, "r1", 0), getattr(tok, "r2", 0))
                    c1 = min(getattr(tok, "c1", 0), getattr(tok, "c2", 0))
                    r2 = max(getattr(tok, "r1", 0), getattr(tok, "r2", 0))
                    c2 = max(getattr(tok, "c1", 0), getattr(tok, "c2", 0))
                else:
                    continue

                key = (r1, c1, r2, c2)
                if key not in seen_ranges:
                    color = HIGHLIGHT_PALETTE[color_idx % len(HIGHLIGHT_PALETTE)]
                    color_idx += 1
                    seen_ranges[key] = color

                self.highlights.append(
                    ReferenceHighlight(
                        r1=r1,
                        c1=c1,
                        r2=r2,
                        c2=c2,
                        color=seen_ranges[key],
                    )
                )

        self.highlights_changed.emit(self.highlights)
        self.viewport.viewport().update()

    def _is_formula(self, text: str) -> bool:
        return text.startswith("=")

    def _operand_at(self) -> bool:
        """Check if cursor is after an operator, comma, or open parenthesis."""
        text = self.in_cell_editor.text()
        pos = self.in_cell_editor.cursorPosition()
        if not text.startswith("="):
            return False
        before = text[:pos]
        return bool(
            re.search(r"[=\+\-\*\/\^&,;\(\<\>:]\s*$", before)
            or before.strip() == "="
        )

    def _on_in_cell_text_changed(self, text: str) -> None:
        if self._syncing:
            return
        self._point_len = 0  # Typing clears current pointed reference span
        if self.formula_bar is not None:
            self._syncing = True
            self.formula_bar.set_text(text)
            self._syncing = False

        if self._is_formula(text) and self._operand_at():
            if self.mode != EditorMode.POINT:
                self.mode = EditorMode.POINT
                self.mode_changed.emit("point")
        elif self.mode == EditorMode.POINT:
            self.mode = EditorMode.EDIT
            self.mode_changed.emit("edit")

        self.reposition_editor()
        self.update_highlights(text)

    def _on_formula_bar_text_changed(self, text: str) -> None:
        if self._syncing:
            return
        if not self.is_active:
            r, c = self.selection.active_cell
            self.begin_edit(r, c, mode=EditorMode.EDIT, initial_text=text)
            return

        self._point_len = 0
        self._syncing = True
        self.in_cell_editor.setText(text)
        self._syncing = False

        if self._is_formula(text) and self._operand_at():
            if self.mode != EditorMode.POINT:
                self.mode = EditorMode.POINT
                self.mode_changed.emit("point")
        elif self.mode == EditorMode.POINT:
            self.mode = EditorMode.EDIT
            self.mode_changed.emit("edit")

        self.reposition_editor()
        self.update_highlights(text)

    def _on_cell_double_clicked(self, r: int, c: int) -> None:
        self.begin_edit(r, c, mode=EditorMode.EDIT)

    def _on_fx_clicked(self) -> None:
        if not self.is_active:
            r, c = self.selection.active_cell
            self.begin_edit(r, c, mode=EditorMode.POINT, initial_text="=")
        else:
            text = self.in_cell_editor.text()
            if not text.startswith("="):
                self._sync_text("=" + text)
                self.mode = EditorMode.POINT
                self.mode_changed.emit("point")

    def _on_selection_changed(self, r: int, c: int) -> None:
        if not self.is_active:
            self._update_name_box()
            self._update_formula_bar_from_model()

    def _on_selection_range_changed(self) -> None:
        if not self.is_active:
            self._update_name_box()

    def _update_name_box(self) -> None:
        if self.formula_bar is None:
            return
        pr = self.selection.primary_range
        if pr.min_r == pr.max_r and pr.min_c == pr.max_c:
            self.formula_bar.set_address(cell_name(pr.min_r, pr.min_c))
        else:
            dr = pr.max_r - pr.min_r + 1
            dc = pr.max_c - pr.min_c + 1
            self.formula_bar.set_address(f"{dr}R x {dc}C")

    def _update_formula_bar_from_model(self) -> None:
        if self.formula_bar is None:
            return
        r, c = self.selection.active_cell
        cell = self.model.get_cell(r, c)
        if cell is not None and cell.formula:
            self.formula_bar.set_cell_text(f"={cell.formula}")
        elif cell is not None and cell.value is not None:
            self.formula_bar.set_cell_text(str(cell.value))
        else:
            self.formula_bar.set_cell_text("")
