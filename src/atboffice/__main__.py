"""Command-line entry point for ``python -m atboffice``."""

import sys

from PySide6.QtWidgets import QApplication

from atboffice.ui.main_window import MainWindow


def main() -> int:
    """Start the ATBOffice desktop application."""
    app = QApplication(sys.argv)
    app.setApplicationName("ATBOffice")
    app.setOrganizationName("ATBOffice")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
