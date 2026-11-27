"""Spreadsheet view component containing the FormulaBar, GridViewport, and EditorController."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from atboffice.core.diagnostics import record_action
from atboffice.modules.spreadsheet.calc.references import cell_name
from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionModel,
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.editor_controller import (
    EditorController,
)
from atboffice.modules.spreadsheet.views.formula_bar import FormulaBar
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport
from atboffice.modules.spreadsheet.views.object_layer import (
    SpreadsheetObjectLayer,
)
from atboffice.modules.spreadsheet.views.sheet_tab_bar import SheetTabBar


class SpreadsheetView(QWidget):
    """Top-level view for ATBOffice Ledger spreadsheet editing."""

    workbook_changed = Signal(object)
    # Re-emitted from whichever sheet's SelectionModel is active, so listeners stay
    # connected across workbook loads and sheet switches.
    selection_changed = Signal()
    active_cell_changed = Signal(int, int)

    def __init__(
        self,
        workbook: WorkbookModel | None = None,
        model: SheetDataModel | None = None,
        selection: SelectionModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # 1. Manage WorkbookModel and per-sheet selections
        if workbook is not None:
            self._workbook = workbook
        elif model is not None:
            self._workbook = WorkbookModel(sheets=[model])
        else:
            self._workbook = WorkbookModel()

        self._sheet_selections: dict[SheetDataModel, SelectionModel] = {}
        self._forwarded_selection: SelectionModel | None = None
        active_sheet = self._workbook.active_sheet
        if selection is not None:
            self._sheet_selections[active_sheet] = selection
        else:
            self._sheet_selections[active_sheet] = self._create_selection(active_sheet)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 2. Top Formula Bar
        self.formula_bar = FormulaBar(self)
        layout.addWidget(self.formula_bar)

        # 3. Virtualized Grid Viewport
        active_sel = self._sheet_selections[active_sheet]
        self.grid = GridViewport(model=active_sheet, selection=active_sel, parent=self)
        self.grid.workbook = self._workbook
        layout.addWidget(self.grid)

        # 4. In-cell editor & formula controller
        self.editor_controller = EditorController(
            viewport=self.grid,
            model=active_sheet,
            selection=active_sel,
            formula_bar=self.formula_bar,
            parent=self,
        )
        self.grid.editor_controller = self.editor_controller

        # Connect navigation requests from NameBox
        self.formula_bar.navigate_requested.connect(self._on_navigate_requested)
        self.formula_bar.range_navigate_requested.connect(self._on_range_navigate_requested)

        # Connect workbook signals for active sheet synchronization and cleanup
        self._workbook.active_sheet_changed.connect(self._on_active_sheet_changed)
        self._workbook.sheet_removed.connect(self._on_sheet_removed)

        # 5. Bottom SheetTabBar embedded in grid viewport scrollbar
        self.sheet_tab_bar = SheetTabBar(workbook=self._workbook, parent=self)
        self.grid.addScrollBarWidget(self.sheet_tab_bar, Qt.AlignmentFlag.AlignLeft)
        # The tabs share the scroll bar's row, which is only as tall as the scroll
        # bar itself; keep the row at least as tall as the tab strip.
        self.grid.horizontalScrollBar().setMinimumHeight(self.sheet_tab_bar.height())
        self._sync_sheet_tab_bar_width()

        # 6. Floating Object Layer overlay
        self.object_layer = SpreadsheetObjectLayer(model=active_sheet, parent=self.grid.viewport())
        self.grid.object_layer = self.object_layer
        self.object_layer.set_zoom(self.grid.zoom)
        self.object_layer.set_header_dimensions(
            self.grid.row_header_width, self.grid.col_header_height
        )
        self.grid.horizontalScrollBar().valueChanged.connect(self._sync_object_layer_scroll)
        self.grid.verticalScrollBar().valueChanged.connect(self._sync_object_layer_scroll)
        self.grid.header_dimensions_changed.connect(self.object_layer.set_header_dimensions)

        self._forward_selection_signals(active_sel)
        self.retranslate_ui()

    def _forward_selection_signals(self, selection: SelectionModel) -> None:
        """Route the active sheet's selection signals through this view (exactly once)."""
        previous = self._forwarded_selection
        if previous is selection:
            return
        if previous is not None:
            try:
                previous.selection_changed.disconnect(self.selection_changed)
                previous.active_cell_changed.disconnect(self.active_cell_changed)
            except (RuntimeError, TypeError):
                pass
        selection.selection_changed.connect(self.selection_changed)
        selection.active_cell_changed.connect(self.active_cell_changed)
        self._forwarded_selection = selection

    def _sync_object_layer_scroll(self, _: int = 0) -> None:
        """Synchronize object layer scroll coordinates with grid viewport."""
        if hasattr(self, "object_layer") and hasattr(self, "grid"):
            self.object_layer.set_scroll_offset(
                self.grid.horizontalScrollBar().value(),
                self.grid.verticalScrollBar().value(),
            )

    def _sync_sheet_tab_bar_width(self) -> None:
        """Keep the tab strip proportional so the horizontal scrollbar spans the right edge."""
        if not hasattr(self, "sheet_tab_bar") or not hasattr(self, "grid"):
            return
        grid_w = self.grid.width()
        if grid_w >= 320:
            self.sheet_tab_bar.setFixedWidth(max(200, int(grid_w * 0.65)))

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        self._sync_sheet_tab_bar_width()
        if hasattr(self, "object_layer") and hasattr(self, "grid"):
            self.object_layer.setGeometry(self.grid.viewport().rect())
            self.object_layer.set_header_dimensions(
                self.grid.row_header_width, self.grid.col_header_height
            )
            self._sync_object_layer_scroll()

    @property
    def workbook(self) -> WorkbookModel:
        """Return the bound WorkbookModel."""
        return self._workbook

    @workbook.setter
    def workbook(self, value: WorkbookModel) -> None:
        """Bind a new WorkbookModel and reinitialize views."""
        if hasattr(self, "grid") and self.grid is not None:
            self.grid.cancel_drag(why="api")
            self.grid.clear_undo_stack()
            self.grid.horizontalScrollBar().setValue(0)
            self.grid.verticalScrollBar().setValue(0)
        if hasattr(self, "editor_controller") and self.editor_controller is not None:
            if hasattr(self.editor_controller, "cancel_editing"):
                self.editor_controller.cancel_editing()
            elif hasattr(self.editor_controller, "cancel"):
                self.editor_controller.cancel()

        if hasattr(self, "_workbook") and self._workbook is not None:
            try:
                self._workbook.active_sheet_changed.disconnect(self._on_active_sheet_changed)
            except Exception:
                pass
            try:
                self._workbook.sheet_removed.disconnect(self._on_sheet_removed)
            except Exception:
                pass
        self._workbook = value
        if hasattr(self, "grid") and self.grid is not None:
            self.grid.workbook = value
        record_action("bind_workbook", "spreadsheet_view", {"sheet_count": len(value.sheets)})
        self._sheet_selections.clear()
        if hasattr(self, "sheet_tab_bar") and self.sheet_tab_bar is not None:
            self.sheet_tab_bar.set_workbook(value)
        self._workbook.active_sheet_changed.connect(self._on_active_sheet_changed)
        self._workbook.sheet_removed.connect(self._on_sheet_removed)
        self._on_active_sheet_changed(self._workbook.active_sheet_index)
        self.workbook_changed.emit(value)

    @property
    def model(self) -> SheetDataModel:
        """Return the active SheetDataModel for backward compatibility."""
        return self._workbook.active_sheet

    @model.setter
    def model(self, value: SheetDataModel) -> None:
        idx = self._workbook.sheet_index(value)
        if idx != -1:
            self.set_active_sheet_index(idx)
        else:
            self._workbook.add_sheet(sheet=value)
            self.set_active_sheet_index(len(self._workbook) - 1)

    @property
    def selection(self) -> SelectionModel:
        """Return the active SelectionModel for the current worksheet."""
        return self._get_selection_for_sheet(self._workbook.active_sheet)

    def _get_selection_for_sheet(self, sheet: SheetDataModel) -> SelectionModel:
        if sheet not in self._sheet_selections:
            self._sheet_selections[sheet] = self._create_selection(sheet)
        return self._sheet_selections[sheet]

    @staticmethod
    def _create_selection(sheet: SheetDataModel) -> SelectionModel:
        """Create a SelectionModel seeded from the sheet's saved view state.

        Later selection changes are written back to ``sheet.view_state`` so that
        saving keeps the current active cell and selection.
        """
        sel = SelectionModel()
        vs = getattr(sheet, "view_state", None)
        if vs is None:
            return sel
        ranges = vs.selection_ranges()
        active = vs.active_cell_rc()
        if active is not None or ranges:
            if active is None:
                active = (ranges[0][0], ranges[0][1])
            sel_ranges = [SelectionRange(*rg) for rg in ranges] or [
                SelectionRange(active[0], active[1], active[0], active[1])
            ]
            # The range holding the active cell is the primary (last) range.
            sel_ranges.sort(key=lambda rg: rg.contains(*active))
            sel.restore_snapshot(
                {"active_cell": active, "anchor_cell": active, "ranges": sel_ranges}
            )

        def _sync() -> None:
            vs = sheet.view_state
            r, c = sel.active_cell
            vs.active_cell = cell_name(r, c)
            parts = [
                cell_name(rg.min_r, rg.min_c)
                if (rg.min_r, rg.min_c) == (rg.max_r, rg.max_c)
                else f"{cell_name(rg.min_r, rg.min_c)}:{cell_name(rg.max_r, rg.max_c)}"
                for rg in sel.ranges
            ]
            vs.sqref = " ".join(parts) or vs.active_cell

        sel.selection_changed.connect(_sync)
        return sel

    def set_active_sheet_index(self, index: int) -> None:
        """Switch active worksheet by index."""
        self._workbook.set_active_sheet_index(index)

    @property
    def view_mode(self) -> str:
        """Current view mode of the grid viewport ('normal' or 'page_break')."""
        return self.grid.view_mode

    def set_view_mode(self, mode: str, prompt_welcome: bool = True) -> None:
        """Set grid viewport view mode ('normal' or 'page_break')."""
        if hasattr(self, "grid") and self.grid is not None:
            self.grid.cancel_drag(why="api")
        record_action("set_view_mode", "spreadsheet_view", {"mode": mode})
        self.grid.set_view_mode(mode, prompt_welcome=prompt_welcome)

    # ---- Window > Split --------------------------------------------------------
    split_grid: GridViewport | None = None

    def is_split(self) -> bool:
        return self.split_grid is not None

    def toggle_split(self) -> bool:
        """Window > Split: a second, independently scrolling pane above the grid.

        Both panes show the active sheet and share its selection; edits made in the
        main pane repaint the other. Returns the new split state.
        """
        from PySide6.QtWidgets import QSplitter

        layout = self.layout()
        if self.split_grid is None:
            splitter = QSplitter(Qt.Orientation.Vertical, self)
            splitter.setObjectName("windowSplitter")
            idx = layout.indexOf(self.grid)
            layout.insertWidget(idx, splitter, 1)
            pane = GridViewport(
                model=self.grid.model, selection=self.grid.selection, parent=splitter
            )
            pane.workbook = self._workbook
            pane.setObjectName("splitPane")
            splitter.addWidget(pane)
            splitter.addWidget(self.grid)
            splitter.setSizes([1, 1])
            self.split_grid = pane
            self._split_splitter = splitter
            for a, b in ((self.grid, pane), (pane, self.grid)):
                a.cell_selected.connect(lambda *_x, other=b: other.viewport().update())
            self.editor_controller.cell_committed.connect(self._repaint_split)
            return True
        splitter = self._split_splitter
        idx = layout.indexOf(splitter)
        layout.insertWidget(idx, self.grid, 1)
        try:
            self.editor_controller.cell_committed.disconnect(self._repaint_split)
        except (RuntimeError, TypeError):
            pass
        self.split_grid.setParent(None)
        self.split_grid.deleteLater()
        splitter.setParent(None)
        splitter.deleteLater()
        self.split_grid = None
        self._split_splitter = None
        self.grid.setFocus()
        return False

    def _repaint_split(self, *_args: Any) -> None:
        if self.split_grid is not None:
            self.split_grid.viewport().update()

    def _on_active_sheet_changed(self, index: int) -> None:
        """Synchronize viewport and editor with newly activated worksheet."""
        if hasattr(self, "grid") and self.grid is not None:
            self.grid.cancel_drag(why="api")
        if hasattr(self, "editor_controller") and self.editor_controller is not None:
            if hasattr(self.editor_controller, "cancel_editing"):
                self.editor_controller.cancel_editing()
            elif hasattr(self.editor_controller, "cancel"):
                self.editor_controller.cancel()

        record_action("active_sheet_changed", "spreadsheet_view", {"index": index})
        active_sheet = self._workbook.active_sheet
        active_sel = self._get_selection_for_sheet(active_sheet)

        self.grid.set_model_and_selection(active_sheet, active_sel)
        if getattr(self, "split_grid", None) is not None:
            self.split_grid.set_model_and_selection(active_sheet, active_sel)
        self.editor_controller.set_model_and_selection(active_sheet, active_sel)
        if hasattr(self, "object_layer") and self.object_layer is not None:
            self.object_layer.select_object(None)
            self.object_layer.set_model(active_sheet)
            self._sync_object_layer_scroll()
        self._forward_selection_signals(active_sel)
        self.grid.viewport().update()
        # The visible selection changed with the sheet: refresh listeners once.
        self.selection_changed.emit()

    def _on_sheet_removed(self, index: int, name: str) -> None:
        """Clean up cached selections for removed worksheets."""
        current_sheets = set(self._workbook.sheets)
        dead_keys = [s for s in self._sheet_selections if s not in current_sheets]
        for s in dead_keys:
            self._sheet_selections.pop(s, None)

    def _on_navigate_requested(self, r: int, c: int) -> None:
        """Handle single cell navigation requested from NameBox."""
        self.selection.select_cell(r, c)
        self.grid.reveal(r, c)
        self.grid.viewport().update()

    def _on_range_navigate_requested(self, r1: int, c1: int, r2: int, c2: int) -> None:
        """Handle range navigation requested from NameBox."""
        self.selection.clear()
        self.selection.add_range(SelectionRange(r1, c1, r2, c2))
        self.selection.set_active_cell(r1, c1)
        self.grid.reveal(r1, c1)
        self.grid.viewport().update()

    def retranslate_ui(self) -> None:
        """Retranslate all UI strings in this view."""
        self.formula_bar.retranslate_ui()
        self.grid.retranslate_ui()
        if hasattr(self, "sheet_tab_bar") and self.sheet_tab_bar is not None:
            self.sheet_tab_bar.retranslate_ui()
        if hasattr(self, "object_layer") and self.object_layer is not None:
            self.object_layer.retranslate_ui()
