"""Regression test for Issue #186: ShapeGraphicsItem.shape attribute collision."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
)

from atboffice.modules.presentation.models.shape import Fill, Line, Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.views.shape_item import ShapeGraphicsItem
from atboffice.modules.presentation.views.slide_canvas import SlideCanvasView, SlideScene


@pytest.fixture
def sample_shape() -> Shape:
    return Shape(
        id="s_test",
        geom="roundRect",
        x=50.0,
        y=50.0,
        w=150.0,
        h=80.0,
        fill=Fill.solid("#2B579A"),
        line=Line(color="#000000", width=1.0),
    )


def test_shape_graphics_item_shape_method_callable(qapp: QApplication, sample_shape: Shape) -> None:
    """Verify that ShapeGraphicsItem.shape is a callable QGraphicsItem virtual method, not shadowed by Shape model."""
    item = ShapeGraphicsItem(sample_shape)
    
    # 1. Model attribute is preserved
    assert hasattr(item, "model")
    assert item.model is sample_shape
    assert item.model.w == 150.0
    assert item.model.h == 80.0

    # 2. shape() is a callable method returning QPainterPath
    assert callable(item.shape)
    path = item.shape()
    assert isinstance(path, QPainterPath)
    rect = path.boundingRect()
    assert rect.width() == pytest.approx(150.0)
    assert rect.height() == pytest.approx(80.0)


def test_slide_scene_mouse_move_over_shape_no_crash(qapp: QApplication, sample_shape: Shape) -> None:
    """Verify that moving mouse over slide canvas and shape triggers Qt hit-testing without segfault or TypeError."""
    slide = Slide(id="test_slide")
    slide.add_shape(sample_shape)

    scene = SlideScene(slide)
    view = SlideCanvasView(scene)
    view.show()

    # Move mouse through shape area
    # Scene pos (100, 90) is inside shape at (50, 50, 150, 80)
    item = scene.get_shape_item(sample_shape.id)
    assert item is not None
    assert callable(item.shape)

    # Simulate mouse move event on scene
    event = QGraphicsSceneMouseEvent(QGraphicsSceneMouseEvent.Type.GraphicsSceneMouseMove)
    event.setScenePos(QPointF(100.0, 90.0))
    event.setScreenPos(QPointF(100.0, 90.0).toPoint())
    event.setButtons(Qt.MouseButton.NoButton)
    event.setModifiers(Qt.KeyboardModifier.NoModifier)

    # Must not raise TypeError: 'Shape' object is not callable
    scene.mouseMoveEvent(event)
    view.close()
