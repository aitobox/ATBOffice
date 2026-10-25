"""Command-line entry point for ``python -m atboffice``."""

from __future__ import annotations

import sys
from pathlib import Path

from atboffice.core.app import ATBApplication, create_application
from atboffice.ui.shell.main_window import MainWindow


def main(argv: list[str] | None = None, exec_app: bool = True) -> int:
    """Start the ATBOffice desktop application."""
    args = argv if argv is not None else sys.argv
    app = create_application(args)

    window = MainWindow()
    app.register_main_window(window)

    # Process CLI file arguments (sys.argv[1:])
    for arg in args[1:]:
        if not arg.startswith("-"):
            file_path = Path(arg).resolve()
            if file_path.exists():
                window.open_file(file_path)

    window.show()
    if not exec_app:
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
