"""Interactive horizontal and vertical rulers facade for Quire word processing.

Splits ruler features into focused components in ``atboffice.modules.writer.views.rulers``:
- ``types.py``: Measurement units, tab kinds, conversions, and styling.
- ``tab_selector.py``: Corner button widget for tab stop and indent selection.
- ``horizontal_ruler.py``: Horizontal ruler with indent markers, tabs, and scale.
- ``vertical_ruler.py``: Vertical ruler with page margin dividers and scale.
"""

from atboffice.modules.writer.views.rulers.horizontal_ruler import HorizontalRuler
from atboffice.modules.writer.views.rulers.tab_selector import TabSelectorWidget
from atboffice.modules.writer.views.rulers.types import (
    PT_PER_CM,
    PT_PER_INCH,
    PT_PER_MM,
    TAB_KINDS,
    RulerUnit,
    TabKind,
    pt_to_unit,
    safe_tr,
    snap_to_grid,
    unit_to_pt,
)
from atboffice.modules.writer.views.rulers.vertical_ruler import VerticalRuler

__all__ = [
    "HorizontalRuler",
    "PT_PER_CM",
    "PT_PER_INCH",
    "PT_PER_MM",
    "RulerUnit",
    "TAB_KINDS",
    "TabKind",
    "TabSelectorWidget",
    "VerticalRuler",
    "pt_to_unit",
    "safe_tr",
    "snap_to_grid",
    "unit_to_pt",
]
