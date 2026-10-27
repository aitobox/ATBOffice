"""ChartGraphicsItem for interactive slide canvas rendering and editing of DrawingML charts."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from atboffice.modules.presentation.chart.model import ChartData
from atboffice.modules.presentation.chart.painter import ChartPainter
from atboffice.modules.presentation.dialogs.datasheet_dialog import (
    DatasheetDialog,
)
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.views.shape_item import ShapeGraphicsItem


class ChartGraphicsItem(ShapeGraphicsItem):
    """Interactive canvas item representing a vector DrawingML chart."""

    def __init__(self, shape: Shape, parent: QGraphicsItem | None = None) -> None:
        if not shape.chart:
            shape.chart = ChartData.create_sample().to_dict()
        super().__init__(shape, parent)
        self._chart_data = ChartData.from_dict(shape.chart)

    @property
    def chart_data(self) -> ChartData:
        return self._chart_data

    def set_chart_data(self, data: ChartData) -> None:
        self._chart_data = data
        self.shape.chart = data.to_dict()
        self.update()
        self.geometryChanged.emit()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """Render chart using vector ChartPainter inside shape bounds."""
        bounds = QRectF(0.0, 0.0, self.shape.w, self.shape.h)
        ChartPainter.paint_chart(painter, self._chart_data, bounds)

        # Selection highlight when selected
        if self.isSelected():
            painter.setPen(Qt.PenStyle.DashLine)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(bounds)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Open the Datasheet Editor dialog on left double-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self.open_datasheet_dialog()
        else:
            super().mouseDoubleClickEvent(event)

    def open_datasheet_dialog(self) -> None:
        """Launch DatasheetDialog modal to edit chart categories, series, and types."""
        parent_widget = self.scene().views()[0] if self.scene() and self.scene().views() else None
        dlg = DatasheetDialog(chart=self._chart_data, parent=parent_widget)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_chart = dlg.get_chart_data()
            self.set_chart_data(new_chart)
