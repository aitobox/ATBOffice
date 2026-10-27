"""Presentation dialogs package."""

from atboffice.modules.presentation.dialogs.datasheet_dialog import (
    DatasheetDialog,
)
from atboffice.modules.presentation.dialogs.format_shape import (
    ColorButton,
    ColorsLinesTab,
    FormatShapeDialog,
    PictureTab,
    PositionTab,
    SizeTab,
    TextBoxTab,
    WebTab,
)
from atboffice.modules.presentation.dialogs.header_footer import (
    HeaderFooterDialog,
)
from atboffice.modules.presentation.dialogs.setup_show import (
    SetupShowDialog,
)
from atboffice.modules.presentation.dialogs.slide_layout import (
    SlideLayoutDialog,
)

__all__ = [
    "DatasheetDialog",
    "FormatShapeDialog",
    "SetupShowDialog",
    "HeaderFooterDialog",
    "SlideLayoutDialog",
    "ColorButton",
    "ColorsLinesTab",
    "SizeTab",
    "PositionTab",
    "PictureTab",
    "TextBoxTab",
    "WebTab",
]

