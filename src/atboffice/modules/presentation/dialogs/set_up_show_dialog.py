"""PowerPoint 2003 Classic Set Up Show Dialog alias for Lectern."""

from __future__ import annotations

from typing import TYPE_CHECKING

from atboffice.modules.presentation.dialogs.setup_show import SetupShowDialog
from atboffice.modules.presentation.models.presentation import Presentation

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


class SetUpShowDialog(SetupShowDialog):
    """Alias and wrapper for SetupShowDialog supporting optional presentation."""

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        pres = presentation or Presentation()
        super().__init__(pres, parent)


__all__ = ["SetUpShowDialog", "SetupShowDialog"]
