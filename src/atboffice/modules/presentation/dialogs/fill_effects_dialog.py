"""PowerPoint 2003 Classic Fill Effects Dialog (Gradient, Texture, Pattern, Picture) for Lectern."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QWidget

from atboffice.modules.presentation.dialogs.background_dlg import (
    FillEffectsDialog as BaseFillEffectsDialog,
)
from atboffice.modules.presentation.models.shape import Fill

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.designs import DesignTemplate


def safe_tr(text: str) -> str:
    """Translate UI text safely for FillEffectsDialog."""
    return QCoreApplication.translate("FillEffectsDialog", text)


class FillEffectsDialog(BaseFillEffectsDialog):
    """4-tab Fill Effects dialog for Gradient, Texture, Pattern, and Picture fills."""

    def __init__(
        self,
        initial_fill: Fill | dict[str, Any] | None = None,
        design: DesignTemplate | None = None,
        parent: QWidget | None = None,
    ) -> None:
        fill_obj: Fill | None = None
        if isinstance(initial_fill, dict):
            fill_obj = Fill.from_dict(initial_fill)
        elif isinstance(initial_fill, Fill):
            fill_obj = initial_fill
        super().__init__(fill_obj, design, parent)
        if initial_fill is None:
            self.tab_widget.setCurrentIndex(0)
            self._refresh_gradient()

    def get_fill_spec(self) -> dict[str, Any]:
        """Return structured dictionary specifying the chosen fill."""
        fill = self.get_fill()
        d = fill.to_dict() if hasattr(fill, "to_dict") else {}
        d["type"] = getattr(fill, "type", d.get("t", "gradient"))
        return d


__all__ = ["FillEffectsDialog"]
