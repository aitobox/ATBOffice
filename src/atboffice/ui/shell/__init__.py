"""macOS native desktop shell and window system integration."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from atboffice.ui.shell.base_window import BaseOfficeWindow
    from atboffice.ui.shell.lectern_window import LecternWindow
    from atboffice.ui.shell.ledger_window import LedgerWindow
    from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu
    from atboffice.ui.shell.quire_window import QuireWindow
    from atboffice.ui.shell.start_center import StartCenterWindow

_EXPORTS: dict[str, tuple[str, str]] = {
    "BaseOfficeWindow": ("atboffice.ui.shell.base_window", "BaseOfficeWindow"),
    "LecternWindow": ("atboffice.ui.shell.lectern_window", "LecternWindow"),
    "LedgerWindow": ("atboffice.ui.shell.ledger_window", "LedgerWindow"),
    "MacMenuBar": ("atboffice.ui.shell.mac_menu", "MacMenuBar"),
    "QuireWindow": ("atboffice.ui.shell.quire_window", "QuireWindow"),
    "StartCenterWindow": ("atboffice.ui.shell.start_center", "StartCenterWindow"),
    "setup_mac_menu": ("atboffice.ui.shell.mac_menu", "setup_mac_menu"),
}

__all__ = [
    "BaseOfficeWindow",
    "LecternWindow",
    "LedgerWindow",
    "MacMenuBar",
    "QuireWindow",
    "StartCenterWindow",
    "setup_mac_menu",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve shell exports so importing one submodule doesn't pull in all editors."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value
