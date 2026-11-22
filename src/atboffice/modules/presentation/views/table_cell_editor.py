"""In-place rich text editor for a single Lectern table cell."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF

from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.tools import table_ops
from atboffice.modules.presentation.views.text_editor import ShapeTextEditorItem

if TYPE_CHECKING:
    from atboffice.modules.presentation.views.shape_item import ShapeGraphicsItem

# Same padding the table painter uses around cell text
CELL_INSETS = (6.0, 3.0, 6.0, 3.0)


class TableCellEditorItem(ShapeTextEditorItem):
    """Edits the text of cell (row, col) and commits it back into the table model.

    The base editor works on ``self.model.text`` sized to ``self.model.w/h``; here
    ``self.model`` is a proxy shape the size of the cell, and the editor is offset to
    the cell's position inside the table.
    """

    def __init__(self, shape_item: ShapeGraphicsItem, row: int, col: int) -> None:
        tbl = shape_item.model.tbl or {}
        table_ops.normalize(tbl)
        self.row, self.col = table_ops.origin_of(tbl, row, col)
        self.cell = table_ops.cell(tbl, self.row, self.col)
        self._cell_body = table_ops.ensure_tx(self.cell)
        x, y, w, h = table_ops.cell_rect(tbl, shape_item.model.w, self.row, self.col)
        self._cell_origin = QPointF(x, y)

        proxy_body = copy.deepcopy(self._cell_body)
        proxy_body.insets = CELL_INSETS
        self._proxy = Shape(
            id=f"{shape_item.model.id}#r{self.row}c{self.col}",
            type="text",
            w=w,
            h=h,
            text=proxy_body,
        )
        super().__init__(shape_item)
        # Re-point the base editor at the cell proxy
        self.model = self._proxy
        self._orig_text_body = copy.deepcopy(proxy_body)
        self.load_from_text_body(proxy_body)
        self._sync_geometry_from_shape()

    def _sync_geometry_from_shape(self) -> None:
        super()._sync_geometry_from_shape()
        origin = getattr(self, "_cell_origin", None)
        if origin is not None and self.model is getattr(self, "_proxy", None):
            self.setPos(self.pos() + origin)

    def apply_autofit(self, mode: str | None = None) -> None:
        """Cells grow with the row in PowerPoint; never shrink the text here."""

    def commit_and_finish(self) -> None:
        if self._is_finishing:
            return
        self._is_finishing = True

        import shiboken6

        if not shiboken6.isValid(self) or not shiboken6.isValid(self.shape_item):
            return
        sc = self.scene()
        if sc is None or getattr(sc, "_is_loading_slide", False):
            self.shape_item.is_editing_text = False
            self.shape_item._text_editor = None
            return

        body = self.to_text_body()
        body.insets = self._cell_body.insets
        self.cell["tx"] = body
        self._grow_row_to_fit(body)
        self.editingFinished.emit(self.shape_item.model.id, body)
        self.shape_item.finish_text_editing()

    def _grow_row_to_fit(self, body: object) -> None:
        """PowerPoint grows a row when a cell's text no longer fits."""
        tbl = self.shape_item.model.tbl or {}
        rows = tbl.get("rows") or []
        if not rows:
            return
        _r1, _c1, r2, _c2 = table_ops.span_of(tbl, self.row, self.col)
        _x, _y, _w, cell_h = table_ops.cell_rect(tbl, self.shape_item.model.w, self.row, self.col)
        needed = self.document().size().height() + CELL_INSETS[1] + CELL_INSETS[3]
        if needed > cell_h + 0.5:
            rows[r2]["h"] = float(rows[r2].get("h", 30.0)) + (needed - cell_h)
            new_h = table_ops.table_height(tbl)
            if new_h > self.shape_item.model.h:
                self.shape_item.prepareGeometryChange()
                self.shape_item.model.h = new_h
