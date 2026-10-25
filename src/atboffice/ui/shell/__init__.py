"""macOS native desktop shell and window system integration."""

from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu
from atboffice.ui.shell.main_window import MainWindow

__all__ = ["MacMenuBar", "MainWindow", "setup_mac_menu"]
