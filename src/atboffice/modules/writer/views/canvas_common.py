"""Types and helpers shared by the canvas_view modules."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtGui import (
    QColor,
)

if TYPE_CHECKING:
    from atboffice.modules.writer.views.canvas_view import WriterCanvasView


def _undoable(label: str, parts: tuple[str, ...] = ()) -> Callable[[Any], Any]:
    """Record the decorated edit of the blocks around the caret as one undo step.

    ``parts`` names other document parts the edit may change (``styles``,
    ``comments``...); they are copied before and after as well.
    """

    def deco(fn: Any) -> Any:
        @functools.wraps(fn)
        def wrapper(self: WriterCanvasView, *args: Any, **kwargs: Any) -> Any:
            with self.controller.edit_scope(label, parts):
                return fn(self, *args, **kwargs)

        return wrapper

    return deco


def _undoable_document(label: str) -> Callable[[Any], Any]:
    """Record the decorated edit, which may touch the whole document, as one step."""

    def deco(fn: Any) -> Any:
        @functools.wraps(fn)
        def wrapper(self: WriterCanvasView, *args: Any, **kwargs: Any) -> Any:
            out: list[Any] = []
            self.run_undoable(lambda: out.append(fn(self, *args, **kwargs)), label)
            return out[0] if out else None

        return wrapper

    return deco


# Standard Word 2003 visual styling constants matching .vibeoffice looks
COLOR_WORKSPACE_BG = QColor(144, 151, 163)  # Classic neutral gray workspace (#9097A3)


COLOR_PAGE_PAPER = QColor(255, 255, 255)  # Pure white paper sheet


COLOR_PAGE_BORDER = QColor(112, 112, 112)  # 1px border around page


COLOR_SHADOW_DARK = QColor(58, 58, 58, 160)  # Classic drop shadow (dark core)


COLOR_SHADOW_LIGHT = QColor(80, 80, 80, 70)  # Soft drop shadow ambient falloff


# w:highlight names (ST_HighlightColor) → screen colours
WORD_HIGHLIGHT_COLORS: dict[str, str] = {
    "yellow": "#FFFF00",
    "green": "#00FF00",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "blue": "#0000FF",
    "red": "#FF0000",
    "darkBlue": "#000080",
    "darkCyan": "#008080",
    "darkGreen": "#008000",
    "darkMagenta": "#800080",
    "darkRed": "#800000",
    "darkYellow": "#808000",
    "darkGray": "#808080",
    "lightGray": "#C0C0C0",
    "black": "#000000",
    "white": "#FFFFFF",
}


COLOR_SELECTION = QColor(51, 153, 255, 110)  # Word selection highlight blue


COLOR_CARET = QColor(0, 0, 0)  # Blinking caret black


COLOR_MARGIN_GUIDE = QColor(200, 200, 200, 120)  # Subtle margin boundary guides


_WAVY_UNDERLINES = frozenset({"wave", "wavyHeavy", "wavyDouble"})


_UNDERLINE_PEN_STYLES = {
    "dotted": Qt.PenStyle.DotLine,
    "dottedHeavy": Qt.PenStyle.DotLine,
    "dash": Qt.PenStyle.DashLine,
    "dashed": Qt.PenStyle.DashLine,
    "dashedHeavy": Qt.PenStyle.DashLine,
    "dashLong": Qt.PenStyle.DashLine,
    "dashLongHeavy": Qt.PenStyle.DashLine,
    "dotDash": Qt.PenStyle.DashDotLine,
    "dashDotHeavy": Qt.PenStyle.DashDotLine,
    "dotDotDash": Qt.PenStyle.DashDotDotLine,
    "dashDotDotHeavy": Qt.PenStyle.DashDotDotLine,
}
