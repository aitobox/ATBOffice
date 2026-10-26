"""UI components package."""

from atboffice.ui.components.color_picker import (
    OFFICE_2003_STANDARD_COLORS,
    ColorPickerButton,
    ColorPickerPopup,
)
from atboffice.ui.components.status_bar import StatusBar
from atboffice.ui.components.toolbar import DottedGrip, OfficeToolBar

__all__ = [
    "ColorPickerButton",
    "ColorPickerPopup",
    "DottedGrip",
    "OFFICE_2003_STANDARD_COLORS",
    "OfficeToolBar",
    "StatusBar",
]
