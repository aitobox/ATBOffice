"""macOS native desktop shell and window system integration."""

from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu
from atboffice.ui.shell.main_window import MainWindow
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.ui.shell.start_center import StartCenterWindow

__all__ = [
    "BaseOfficeWindow",
    "LecternWindow",
    "LedgerWindow",
    "MacMenuBar",
    "MainWindow",
    "QuireWindow",
    "StartCenterWindow",
    "setup_mac_menu",
]
