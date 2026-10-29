"""Worksheet floating object layer (SpreadsheetObjectLayer) and DrawingML models.

Enables placing, selecting, moving, resizing, and rendering floating graphic objects
(shapes, textboxes, images, charts) over the spreadsheet grid, with full two-cell
anchoring and DrawingML synchronization.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QContextMenuEvent,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import QMenu, QWidget

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import (
        SheetDataModel,
        SheetGeometry,
    )


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("SpreadsheetObjectLayer", text)


class AnchorType(Enum):
    """DrawingML anchor binding mode."""

    TWO_CELL = "twoCell"
    ONE_CELL = "oneCell"
    ABSOLUTE = "absolute"


class HandleType(Enum):
    """Selection bounding box resize handle types."""

    NONE = 0
    NW = 1
    N = 2
    NE = 3
    E = 4
    SE = 5
    S = 6
    SW = 7
    W = 8
    BODY = 9


@dataclass
class CellAnchorPoint:
    """Cell anchor coordinate: 0-based column & row plus pixel offsets."""

    col: int = 0
    col_off: int = 0  # pixel offset from column left edge
    row: int = 0
    row_off: int = 0  # pixel offset from row top edge

    def to_dict(self) -> dict[str, int]:
        return {
            "col": self.col,
            "col_off": self.col_off,
            "row": self.row,
            "row_off": self.row_off,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CellAnchorPoint:
        if not data:
            return cls()
        return cls(
            col=int(data.get("col", 0)),
            col_off=int(data.get("col_off", 0)),
            row=int(data.get("row", 0)),
            row_off=int(data.get("row_off", 0)),
        )


@dataclass
class FloatingObject:
    """Floating graphic element anchored over a worksheet."""

    id: int = 1
    name: str = "Shape 1"
    kind: str = "rect"  # "rect", "roundRect", "oval", "arrow", "line", "textbox", "image", "chart"
    anchor_type: AnchorType = AnchorType.TWO_CELL
    from_point: CellAnchorPoint = field(default_factory=CellAnchorPoint)
    to_point: CellAnchorPoint = field(default_factory=CellAnchorPoint)
    abs_rect: tuple[int, int, int, int] = (0, 0, 120, 80)  # (x, y, w, h)
    fill_color: str = "#4F81BD"
    fill_alpha: float = 1.0
    line_color: str = "#385D8A"
    line_width: float = 1.0
    text: str = ""
    text_color: str = "#000000"
    font_size: int = 11
    font_family: str = "Calibri"
    image_data: bytes | None = None
    image_mime: str = "image/png"
    z_index: int = 0

    def clone(self) -> FloatingObject:
        """Create a deep copy of this floating object."""
        return copy.deepcopy(self)

    def to_dict(self) -> dict[str, Any]:
        """Serialize object metadata to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "anchor_type": self.anchor_type.value,
            "from_point": self.from_point.to_dict(),
            "to_point": self.to_point.to_dict(),
            "abs_rect": list(self.abs_rect),
            "fill_color": self.fill_color,
            "fill_alpha": self.fill_alpha,
            "line_color": self.line_color,
            "line_width": self.line_width,
            "text": self.text,
            "text_color": self.text_color,
            "font_size": self.font_size,
            "font_family": self.font_family,
            "image_mime": self.image_mime,
            "z_index": self.z_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FloatingObject:
        """Construct FloatingObject from dictionary representation."""
        anchor_type_str = data.get("anchor_type", "twoCell")
        try:
            anchor_type = AnchorType(anchor_type_str)
        except ValueError:
            anchor_type = AnchorType.TWO_CELL

        return cls(
            id=int(data.get("id", 1)),
            name=str(data.get("name", "Shape")),
            kind=str(data.get("kind", "rect")),
            anchor_type=anchor_type,
            from_point=CellAnchorPoint.from_dict(data.get("from_point")),
            to_point=CellAnchorPoint.from_dict(data.get("to_point")),
            abs_rect=tuple(data.get("abs_rect", [0, 0, 120, 80])),  # type: ignore
            fill_color=str(data.get("fill_color", "#4F81BD")),
            fill_alpha=float(data.get("fill_alpha", 1.0)),
            line_color=str(data.get("line_color", "#385D8A")),
            line_width=float(data.get("line_width", 1.0)),
            text=str(data.get("text", "")),
            text_color=str(data.get("text_color", "#000000")),
            font_size=int(data.get("font_size", 11)),
            font_family=str(data.get("font_family", "Calibri")),
            image_mime=str(data.get("image_mime", "image/png")),
            z_index=int(data.get("z_index", 0)),
        )


def object_to_rect(
    obj: FloatingObject,
    geometry: SheetGeometry,
    scroll_x: int = 0,
    scroll_y: int = 0,
    row_header_width: int = 46,
    col_header_height: int = 22,
) -> QRect:
    """Calculate widget viewport bounding rectangle for a floating object."""
    if obj.anchor_type == AnchorType.TWO_CELL:
        # Sheet relative X and Y
        x1 = geometry.col_pos(obj.from_point.col) + obj.from_point.col_off
        y1 = geometry.row_pos(obj.from_point.row) + obj.from_point.row_off
        x2 = geometry.col_pos(obj.to_point.col) + obj.to_point.col_off
        y2 = geometry.row_pos(obj.to_point.row) + obj.to_point.row_off

        # Normalize in case coordinates were reversed during drag
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)

        vx = row_header_width + min_x - scroll_x
        vy = col_header_height + min_y - scroll_y
        vw = max(4, max_x - min_x)
        vh = max(4, max_y - min_y)
        return QRect(int(vx), int(vy), int(vw), int(vh))

    elif obj.anchor_type == AnchorType.ONE_CELL:
        x1 = geometry.col_pos(obj.from_point.col) + obj.from_point.col_off
        y1 = geometry.row_pos(obj.from_point.row) + obj.from_point.row_off
        vx = row_header_width + x1 - scroll_x
        vy = col_header_height + y1 - scroll_y
        _, _, w, h = obj.abs_rect
        return QRect(int(vx), int(vy), int(max(4, w)), int(max(4, h)))

    else:  # ABSOLUTE
        x, y, w, h = obj.abs_rect
        vx = row_header_width + x - scroll_x
        vy = col_header_height + y - scroll_y
        return QRect(int(vx), int(vy), int(max(4, w)), int(max(4, h)))


def rect_to_anchor(
    rect: QRect,
    geometry: SheetGeometry,
    scroll_x: int = 0,
    scroll_y: int = 0,
    row_header_width: int = 46,
    col_header_height: int = 22,
) -> tuple[CellAnchorPoint, CellAnchorPoint]:
    """Convert widget viewport bounding rectangle into start and end CellAnchorPoints."""
    # Convert widget viewport position back to sheet-relative pixels
    sheet_x1 = max(0, rect.x() - row_header_width + scroll_x)
    sheet_y1 = max(0, rect.y() - col_header_height + scroll_y)
    sheet_x2 = max(sheet_x1 + 4, sheet_x1 + rect.width())
    sheet_y2 = max(sheet_y1 + 4, sheet_y1 + rect.height())

    # Map start position
    c1 = geometry.find_col_at(sheet_x1)
    col_x1 = geometry.col_pos(c1)
    off_c1 = max(0, sheet_x1 - col_x1)

    r1 = geometry.find_row_at(sheet_y1)
    row_y1 = geometry.row_pos(r1)
    off_r1 = max(0, sheet_y1 - row_y1)

    # Map end position
    c2 = geometry.find_col_at(sheet_x2)
    col_x2 = geometry.col_pos(c2)
    off_c2 = max(0, sheet_x2 - col_x2)

    r2 = geometry.find_row_at(sheet_y2)
    row_y2 = geometry.row_pos(r2)
    off_r2 = max(0, sheet_y2 - row_y2)

    from_point = CellAnchorPoint(col=c1, col_off=off_c1, row=r1, row_off=off_r1)
    to_point = CellAnchorPoint(col=c2, col_off=off_c2, row=r2, row_off=off_r2)
    return from_point, to_point


class SpreadsheetObjectLayer(QWidget):
    """Transparent interactive canvas overlay rendering and managing floating objects."""

    object_selected = Signal(object)
    object_modified = Signal(object)

    HANDLE_SIZE: int = 8
    HANDLE_HALF: int = 4

    def __init__(
        self,
        model: SheetDataModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.model: SheetDataModel | None = model
        self.internal_objects: list[FloatingObject] = []
        if model is not None and hasattr(model, "drawings"):
            self.internal_objects = model.drawings

        self.selected_object: FloatingObject | None = None
        self._clipboard_object: FloatingObject | None = None

        # Coordinate mapper properties
        self.row_header_width: int = 46
        self.col_header_height: int = 22
        self.scroll_x: int = 0
        self.scroll_y: int = 0

        # Mouse interaction drag state
        self._drag_mode: HandleType = HandleType.NONE
        self._drag_start_pos: QPoint | None = None
        self._drag_start_rect: QRect | None = None

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Transparent background for non-object regions
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    @property
    def objects(self) -> list[FloatingObject]:
        """Return all floating objects sorted by z_index."""
        if self.model is not None and hasattr(self.model, "drawings"):
            self.internal_objects = self.model.drawings
        self.internal_objects.sort(key=lambda o: o.z_index)
        return self.internal_objects

    def set_model(self, model: SheetDataModel | None) -> None:
        """Bind a new SheetDataModel to the object layer."""
        self.model = model
        self.selected_object = None
        if model is not None:
            if not hasattr(model, "drawings"):
                model.drawings = []
            self.internal_objects = model.drawings
        else:
            self.internal_objects = []
        self.update()

    def set_scroll_offset(self, scroll_x: int, scroll_y: int) -> None:
        """Update viewport scroll offsets and repaint."""
        self.scroll_x = scroll_x
        self.scroll_y = scroll_y
        self.update()

    def set_header_dimensions(self, row_header_w: int, col_header_h: int) -> None:
        """Update header dimensions and repaint."""
        self.row_header_width = row_header_w
        self.col_header_height = col_header_h
        self.update()

    def retranslate_ui(self) -> None:
        """Update UI localized text and trigger repaint."""
        self.update()

    def add_object(self, obj: FloatingObject) -> None:
        """Add a floating object to the active sheet."""
        if self.model is not None and hasattr(self.model, "drawings"):
            if obj not in self.model.drawings:
                self.model.drawings.append(obj)
            self.internal_objects = self.model.drawings
        else:
            if obj not in self.internal_objects:
                self.internal_objects.append(obj)
        self.update()

    def remove_object(self, obj: FloatingObject) -> None:
        """Remove a floating object from the active sheet."""
        if self.selected_object is obj:
            self.selected_object = None
            self.object_selected.emit(None)

        if self.model is not None and hasattr(self.model, "drawings"):
            if obj in self.model.drawings:
                self.model.drawings.remove(obj)
        if obj in self.internal_objects:
            self.internal_objects.remove(obj)
        self.update()

    def select_object(self, obj: FloatingObject | None) -> None:
        """Set the currently selected floating object."""
        if self.selected_object is not obj:
            self.selected_object = obj
            self.object_selected.emit(obj)
            self.update()

    def get_object_rect(self, obj: FloatingObject) -> QRect:
        """Calculate QRect for given object using current geometry and scroll offsets."""
        geom = self.model.geometry if self.model is not None else None
        if geom is None:
            # Fallback geometry if none bound
            from atboffice.modules.spreadsheet.models.sheet_model import SheetGeometry
            geom = SheetGeometry()

        return object_to_rect(
            obj=obj,
            geometry=geom,
            scroll_x=self.scroll_x,
            scroll_y=self.scroll_y,
            row_header_width=self.row_header_width,
            col_header_height=self.col_header_height,
        )

    def _get_handles(self, rect: QRect) -> dict[HandleType, QRect]:
        """Compute 8 control handle bounding boxes for a selected rectangle."""
        sz = self.HANDLE_SIZE
        half = self.HANDLE_HALF

        x1, y1 = rect.left(), rect.top()
        x2, y2 = rect.right(), rect.bottom()
        xc = rect.center().x()
        yc = rect.center().y()

        return {
            HandleType.NW: QRect(x1 - half, y1 - half, sz, sz),
            HandleType.N: QRect(xc - half, y1 - half, sz, sz),
            HandleType.NE: QRect(x2 - half, y1 - half, sz, sz),
            HandleType.E: QRect(x2 - half, yc - half, sz, sz),
            HandleType.SE: QRect(x2 - half, y2 - half, sz, sz),
            HandleType.S: QRect(xc - half, y2 - half, sz, sz),
            HandleType.SW: QRect(x1 - half, y2 - half, sz, sz),
            HandleType.W: QRect(x1 - half, yc - half, sz, sz),
        }

    def hit_test(self, x: int, y: int) -> tuple[FloatingObject | None, HandleType]:
        """Hit test mouse position (x, y) against handles and object bodies."""
        pt = QPoint(x, y)

        # 1. If an object is selected, test its handles first
        if self.selected_object is not None:
            rect = self.get_object_rect(self.selected_object)
            handles = self._get_handles(rect)
            for handle_type, handle_rect in handles.items():
                if handle_rect.contains(pt):
                    return self.selected_object, handle_type

        # 2. Test object bodies in reverse Z-order (topmost first)
        sorted_objs = list(self.objects)
        sorted_objs.sort(key=lambda o: o.z_index, reverse=True)
        for obj in sorted_objs:
            rect = self.get_object_rect(obj)
            if rect.contains(pt):
                return obj, HandleType.BODY

        return None, HandleType.NONE

    # Z-Order Operations
    def bring_to_front(self, obj: FloatingObject) -> None:
        """Move object to the topmost Z-index position."""
        objs = self.objects
        if not objs or obj not in objs:
            return
        objs.remove(obj)
        objs.append(obj)
        for i, o in enumerate(objs):
            o.z_index = i
        self.update()

    def send_to_back(self, obj: FloatingObject) -> None:
        """Move object to the bottommost Z-index position."""
        objs = self.objects
        if not objs or obj not in objs:
            return
        objs.remove(obj)
        objs.insert(0, obj)
        for i, o in enumerate(objs):
            o.z_index = i
        self.update()

    def bring_forward(self, obj: FloatingObject) -> None:
        """Move object forward by one Z-index position."""
        objs = self.objects
        if not objs or obj not in objs:
            return
        idx = objs.index(obj)
        if idx < len(objs) - 1:
            objs[idx], objs[idx + 1] = objs[idx + 1], objs[idx]
            for i, o in enumerate(objs):
                o.z_index = i
            self.update()

    def send_backward(self, obj: FloatingObject) -> None:
        """Move object backward by one Z-index position."""
        objs = self.objects
        if not objs or obj not in objs:
            return
        idx = objs.index(obj)
        if idx > 0:
            objs[idx], objs[idx - 1] = objs[idx - 1], objs[idx]
            for i, o in enumerate(objs):
                o.z_index = i
            self.update()

    # Clipboard & Editing
    def copy_selected(self) -> None:
        """Copy the selected floating object to clipboard."""
        if self.selected_object is not None:
            self._clipboard_object = self.selected_object.clone()

    def paste(self) -> FloatingObject | None:
        """Paste clipboard object onto the active sheet with a slight offset."""
        if self._clipboard_object is None:
            return None

        pasted = self._clipboard_object.clone()
        max_id = max([o.id for o in self.objects], default=0)
        pasted.id = max_id + 1
        pasted.name = f"{pasted.name} (Copy)"

        # Shift anchor slightly
        pasted.from_point.col += 1
        pasted.from_point.row += 1
        pasted.to_point.col += 1
        pasted.to_point.row += 1
        pasted.z_index = len(self.objects)

        self.add_object(pasted)
        self.select_object(pasted)
        self.object_modified.emit(pasted)
        return pasted

    def delete_selected(self) -> bool:
        """Delete currently selected object."""
        if self.selected_object is not None:
            target = self.selected_object
            self.remove_object(target)
            self.object_modified.emit(target)
            return True
        return False

    # Painting
    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw objects sorted by Z-index
        for obj in self.objects:
            rect = self.get_object_rect(obj)
            # Only draw if intersects visible widget region
            if not rect.intersects(self.rect()):
                continue
            self._paint_object(painter, obj, rect)

        # Draw selection adornments if an object is selected
        if self.selected_object is not None:
            sel_rect = self.get_object_rect(self.selected_object)
            self._paint_selection(painter, sel_rect)

        painter.end()

    def _paint_object(
        self, painter: QPainter, obj: FloatingObject, rect: QRect
    ) -> None:
        """Render a single floating object on canvas."""
        fill_col = QColor(obj.fill_color)
        fill_col.setAlphaF(max(0.0, min(1.0, obj.fill_alpha)))
        line_col = QColor(obj.line_color)

        pen = QPen(line_col, max(0.5, obj.line_width))
        brush = QBrush(fill_col)
        painter.setPen(pen)
        painter.setBrush(brush)

        if obj.kind in ("rect", "textbox"):
            painter.drawRect(rect)
        elif obj.kind == "roundRect":
            painter.drawRoundedRect(rect, 8.0, 8.0)
        elif obj.kind == "oval":
            painter.drawEllipse(rect)
        elif obj.kind == "line":
            painter.drawLine(rect.topLeft(), rect.bottomRight())
        elif obj.kind == "arrow":
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            # Arrow head
            head = QPolygon([rect.bottomRight(), rect.bottomRight() + QPoint(-8, -4), rect.bottomRight() + QPoint(-4, -8)])
            painter.drawPolygon(head)
        elif obj.kind == "image":
            if obj.image_data:
                pix = QPixmap()
                if pix.loadFromData(obj.image_data):
                    painter.drawPixmap(rect, pix)
                else:
                    painter.drawRect(rect)
            else:
                painter.drawRect(rect)
        elif obj.kind == "chart":
            painter.drawRect(rect)
            # Placeholder chart indicator
            painter.drawText(
                rect,
                int(Qt.AlignmentFlag.AlignCenter),
                f"[Chart: {obj.name}]",
            )

        # Draw textbox or shape text
        if obj.text:
            text_col = QColor(obj.text_color)
            painter.setPen(QPen(text_col))
            font = QFont(obj.font_family, max(6, obj.font_size))
            painter.setFont(font)

            pad = 4
            text_rect = rect.adjusted(pad, pad, -pad, -pad)
            flags = (
                int(Qt.AlignmentFlag.AlignLeft)
                | int(Qt.AlignmentFlag.AlignTop)
                | int(Qt.TextFlag.TextWordWrap)
            )
            painter.drawText(text_rect, flags, obj.text)

    def _paint_selection(self, painter: QPainter, rect: QRect) -> None:
        """Render selection rectangle and 8 directional control handles."""
        # Dashed bounding frame
        outline_pen = QPen(
            QColor(33, 115, 70), 1.5, Qt.PenStyle.DashLine
        )  # Excel green accent
        painter.setPen(outline_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        # 8 Square handles
        handle_pen = QPen(QColor(33, 115, 70), 1.0)
        handle_brush = QBrush(QColor(255, 255, 255))
        painter.setPen(handle_pen)
        painter.setBrush(handle_brush)

        handles = self._get_handles(rect)
        for handle_rect in handles.values():
            painter.drawRect(handle_rect)

    # Mouse & Keyboard Events
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            hit_obj, handle = self.hit_test(event.pos().x(), event.pos().y())
            if hit_obj is not None:
                self.select_object(hit_obj)
                self._drag_mode = handle
                self._drag_start_pos = event.pos()
                self._drag_start_rect = self.get_object_rect(hit_obj)
                event.accept()
                return
            else:
                # Clicked empty grid space: deselect and ignore event so grid viewport handles it
                if self.selected_object is not None:
                    self.select_object(None)
                event.ignore()
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.pos()

        # If currently in a drag operation
        if (
            self._drag_mode != HandleType.NONE
            and self.selected_object is not None
            and self._drag_start_pos is not None
            and self._drag_start_rect is not None
        ):
            dx = pos.x() - self._drag_start_pos.x()
            dy = pos.y() - self._drag_start_pos.y()
            orig = self._drag_start_rect

            new_x, new_y = orig.x(), orig.y()
            new_w, new_h = orig.width(), orig.height()

            if self._drag_mode == HandleType.BODY:
                new_x += dx
                new_y += dy
            elif self._drag_mode == HandleType.SE:
                new_w = max(10, orig.width() + dx)
                new_h = max(10, orig.height() + dy)
            elif self._drag_mode == HandleType.E:
                new_w = max(10, orig.width() + dx)
            elif self._drag_mode == HandleType.S:
                new_h = max(10, orig.height() + dy)
            elif self._drag_mode == HandleType.NW:
                new_x = min(orig.right() - 10, orig.x() + dx)
                new_y = min(orig.bottom() - 10, orig.y() + dy)
                new_w = orig.right() - new_x
                new_h = orig.bottom() - new_y
            elif self._drag_mode == HandleType.N:
                new_y = min(orig.bottom() - 10, orig.y() + dy)
                new_h = orig.bottom() - new_y
            elif self._drag_mode == HandleType.W:
                new_x = min(orig.right() - 10, orig.x() + dx)
                new_w = orig.right() - new_x
            elif self._drag_mode == HandleType.NE:
                new_y = min(orig.bottom() - 10, orig.y() + dy)
                new_w = max(10, orig.width() + dx)
                new_h = orig.bottom() - new_y
            elif self._drag_mode == HandleType.SW:
                new_x = min(orig.right() - 10, orig.x() + dx)
                new_w = orig.right() - new_x
                new_h = max(10, orig.height() + dy)

            new_rect = QRect(int(new_x), int(new_y), int(new_w), int(new_h))

            # Update object anchors
            if self.model is not None:
                p1, p2 = rect_to_anchor(
                    rect=new_rect,
                    geometry=self.model.geometry,
                    scroll_x=self.scroll_x,
                    scroll_y=self.scroll_y,
                    row_header_width=self.row_header_width,
                    col_header_height=self.col_header_height,
                )
                self.selected_object.from_point = p1
                self.selected_object.to_point = p2
                self.selected_object.abs_rect = (
                    new_x,
                    new_y,
                    new_w,
                    new_h,
                )

            self.update()
            self.object_modified.emit(self.selected_object)
            event.accept()
            return

        # Update mouse cursor based on hover target
        _, handle = self.hit_test(pos.x(), pos.y())
        if handle in (HandleType.NW, HandleType.SE):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif handle in (HandleType.NE, HandleType.SW):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif handle in (HandleType.N, HandleType.S):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif handle in (HandleType.W, HandleType.E):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif handle == HandleType.BODY:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        event.ignore()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_mode != HandleType.NONE:
            self._drag_mode = HandleType.NONE
            self._drag_start_pos = None
            self._drag_start_rect = None
            if self.selected_object is not None:
                self.object_modified.emit(self.selected_object)
            event.accept()
            return
        event.ignore()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.delete_selected():
                event.accept()
                return
        elif event.matches(QKeyEvent.StandardKey.Copy):
            self.copy_selected()
            event.accept()
            return
        elif event.matches(QKeyEvent.StandardKey.Paste):
            if self.paste() is not None:
                event.accept()
                return

        super().keyPressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        hit_obj, _ = self.hit_test(event.pos().x(), event.pos().y())
        if hit_obj is not None:
            self.select_object(hit_obj)

        menu = QMenu(self)

        act_cut = menu.addAction(safe_tr("Cut"))
        act_copy = menu.addAction(safe_tr("Copy"))
        act_paste = menu.addAction(safe_tr("Paste"))
        act_delete = menu.addAction(safe_tr("Delete"))
        menu.addSeparator()

        act_front = menu.addAction(safe_tr("Bring to Front"))
        act_forward = menu.addAction(safe_tr("Bring Forward"))
        act_backward = menu.addAction(safe_tr("Send Backward"))
        act_back = menu.addAction(safe_tr("Send to Back"))

        has_sel = self.selected_object is not None
        act_cut.setEnabled(has_sel)
        act_copy.setEnabled(has_sel)
        act_delete.setEnabled(has_sel)
        act_front.setEnabled(has_sel)
        act_forward.setEnabled(has_sel)
        act_backward.setEnabled(has_sel)
        act_back.setEnabled(has_sel)
        act_paste.setEnabled(self._clipboard_object is not None)

        action = menu.exec(event.globalPos())
        if not action or not self.selected_object:
            if action == act_paste:
                self.paste()
            return

        sel = self.selected_object
        if action == act_cut:
            self.copy_selected()
            self.delete_selected()
        elif action == act_copy:
            self.copy_selected()
        elif action == act_paste:
            self.paste()
        elif action == act_delete:
            self.delete_selected()
        elif action == act_front:
            self.bring_to_front(sel)
        elif action == act_forward:
            self.bring_forward(sel)
        elif action == act_backward:
            self.send_backward(sel)
        elif action == act_back:
            self.send_to_back(sel)
