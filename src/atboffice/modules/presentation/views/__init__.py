"""Presentation views package."""

from atboffice.modules.presentation.views.geometry_helper import (
    create_shape_path,
    get_adjustment_handles,
)
from atboffice.modules.presentation.views.shape_item import (
    HandleType,
    ShapeGraphicsItem,
    TransformHandleItem,
)
from atboffice.modules.presentation.views.slide_canvas import (
    SlideCanvasView,
    SlideScene,
    safe_tr,
)
from atboffice.modules.presentation.views.smart_guides import (
    GuideLine,
    SmartGuideController,
)

__all__ = [
    "create_shape_path",
    "get_adjustment_handles",
    "HandleType",
    "TransformHandleItem",
    "ShapeGraphicsItem",
    "GuideLine",
    "SmartGuideController",
    "SlideScene",
    "SlideCanvasView",
    "safe_tr",
]
