"""Smart Guides alignment detection and magnetic snapping for Lectern canvas."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene


@dataclass
class GuideLine:
    """Represents an active alignment guide line."""

    orientation: str  # "v" (vertical) or "h" (horizontal)
    coord: float
    start: float
    end: float


class SmartGuideController:
    """Calculates magnetic snapping and displays alignment guidelines."""

    def __init__(self, snap_threshold: float = 6.0) -> None:
        self.snap_threshold = snap_threshold
        self._active_guidelines: list[GuideLine] = []
        self._guide_items: list[QGraphicsLineItem] = []

    @property
    def active_guidelines(self) -> list[GuideLine]:
        return self._active_guidelines

    def calculate_snap(
        self,
        moving_rect: QRectF,
        target_rects: list[QRectF],
        slide_width: float,
        slide_height: float,
    ) -> tuple[float, float, list[GuideLine]]:
        """Calculate magnetic snap delta (dx, dy) and generate active guide lines."""
        best_dx: float | None = None
        min_dist_x = self.snap_threshold + 1.0
        active_v_guide: GuideLine | None = None

        # Horizontal targets (X-coordinates)
        x_targets: list[tuple[float, float, float]] = [
            (0.0, 0.0, slide_height),
            (slide_width / 2.0, 0.0, slide_height),
            (slide_width, 0.0, slide_height),
        ]
        for tr in target_rects:
            x_targets.append((tr.left(), tr.top(), tr.bottom()))
            x_targets.append((tr.center().x(), tr.top(), tr.bottom()))
            x_targets.append((tr.right(), tr.top(), tr.bottom()))

        moving_x_points = [
            (moving_rect.left(), "left"),
            (moving_rect.center().x(), "center"),
            (moving_rect.right(), "right"),
        ]

        for mx, align_type in moving_x_points:
            for tx, t_top, t_bot in x_targets:
                dist = abs(mx - tx)
                if dist <= self.snap_threshold and dist < min_dist_x:
                    min_dist_x = dist
                    if align_type == "left":
                        best_dx = tx - moving_rect.left()
                    elif align_type == "center":
                        best_dx = tx - moving_rect.center().x()
                    else:
                        best_dx = tx - moving_rect.right()

                    y_start = min(moving_rect.top(), t_top)
                    y_end = max(moving_rect.bottom(), t_bot)
                    active_v_guide = GuideLine("v", tx, y_start, y_end)

        # Vertical targets (Y-coordinates)
        best_dy: float | None = None
        min_dist_y = self.snap_threshold + 1.0
        active_h_guide: GuideLine | None = None

        y_targets: list[tuple[float, float, float]] = [
            (0.0, 0.0, slide_width),
            (slide_height / 2.0, 0.0, slide_width),
            (slide_height, 0.0, slide_width),
        ]
        for tr in target_rects:
            y_targets.append((tr.top(), tr.left(), tr.right()))
            y_targets.append((tr.center().y(), tr.left(), tr.right()))
            y_targets.append((tr.bottom(), tr.left(), tr.right()))

        moving_y_points = [
            (moving_rect.top(), "top"),
            (moving_rect.center().y(), "middle"),
            (moving_rect.bottom(), "bottom"),
        ]

        for my, align_type in moving_y_points:
            for ty, t_left, t_right in y_targets:
                dist = abs(my - ty)
                if dist <= self.snap_threshold and dist < min_dist_y:
                    min_dist_y = dist
                    if align_type == "top":
                        best_dy = ty - moving_rect.top()
                    elif align_type == "middle":
                        best_dy = ty - moving_rect.center().y()
                    else:
                        best_dy = ty - moving_rect.bottom()

                    x_start = min(moving_rect.left(), t_left)
                    x_end = max(moving_rect.right(), t_right)
                    active_h_guide = GuideLine("h", ty, x_start, x_end)

        dx = best_dx if best_dx is not None else 0.0
        dy = best_dy if best_dy is not None else 0.0

        guides: list[GuideLine] = []
        if active_v_guide is not None:
            guides.append(active_v_guide)
        if active_h_guide is not None:
            guides.append(active_h_guide)

        self._active_guidelines = guides
        return dx, dy, guides

    def render_guides(self, scene: QGraphicsScene) -> None:
        """Render active guidelines on the scene as red dashed lines."""
        self._clear_rendered_items(scene)

        pen = QPen(QColor(230, 20, 20, 220), 1.0, Qt.PenStyle.DashLine)
        for g in self._active_guidelines:
            if g.orientation == "v":
                item = scene.addLine(g.coord, g.start, g.coord, g.end, pen)
            else:
                item = scene.addLine(g.start, g.coord, g.end, g.coord, pen)
            item.setZValue(9999.0)  # Always on top of shapes
            self._guide_items.append(item)

    def _clear_rendered_items(self, scene: QGraphicsScene | None = None) -> None:
        for item in self._guide_items:
            if scene is not None:
                scene.removeItem(item)
            elif item.scene() is not None:
                item.scene().removeItem(item)
        self._guide_items.clear()

    def clear_guides(self, scene: QGraphicsScene | None = None) -> None:
        """Clear all active guidelines and definitions."""
        self._clear_rendered_items(scene)
        self._active_guidelines.clear()
