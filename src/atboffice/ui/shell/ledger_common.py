"""Types and helpers shared by the ledger_window modules."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from atboffice.ui.shell.ledger_window import LedgerWindow


def _cell_edit(
    action: str, *, scope: str = "sheet", recalc: bool = False
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Make the decorated LedgerWindow command one undo step (see ``run_cell_edit``)."""

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(self: LedgerWindow, *args: Any, **kwargs: Any) -> Any:
            return self.run_cell_edit(
                lambda: fn(self, *args, **kwargs), action, scope=scope, recalc=recalc
            )

        return wrapper

    return deco
