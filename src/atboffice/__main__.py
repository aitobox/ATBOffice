"""Command-line entry point for ATBOffice suite and module launchers."""

from __future__ import annotations

import sys
from typing import Any

from atboffice import __version__
from atboffice.core.app import create_application
from atboffice.core.window_manager import WindowManager
from atboffice.ui.shell.main_window import MainWindow  # noqa: F401

__all__ = [
    "MainWindow",
    "main",
    "main_lectern",
    "main_ledger",
    "main_quire",
    "parse_cli_args",
]


def parse_cli_args(args: list[str]) -> tuple[str, str | None]:
    """Parse command line arguments into an action and optional document path.

    Args:
        args: List of command-line arguments (typically sys.argv[1:] or sub-arguments).

    Returns:
        tuple[str, str | None]: (action, path) where action is one of:
            'start_center', 'quire', 'ledger', 'lectern', 'file', 'version', 'help'.
    """
    if not args:
        return "start_center", None

    # Strip executable name if caller passed raw sys.argv
    normalized = list(args)
    first_item = normalized[0].strip()
    if (
        first_item in ("atboffice", "atboffice.py", "__main__.py")
        or first_item.endswith(("/atboffice", "\\atboffice", ".py"))
    ):
        normalized = normalized[1:]

    if not normalized:
        return "start_center", None

    token = normalized[0].strip()

    if token in ("-s", "--start-center"):
        return "start_center", None

    if token in ("-v", "--version"):
        return "version", None

    if token in ("-h", "--help"):
        return "help", None

    subcommands: dict[str, str] = {
        "quire": "quire",
        "--quire": "quire",
        "ledger": "ledger",
        "--ledger": "ledger",
        "lectern": "lectern",
        "--lectern": "lectern",
    }

    if token in subcommands:
        action = subcommands[token]
        path: str | None = None
        for item in normalized[1:]:
            val = item.strip()
            if val and not val.startswith("-"):
                path = val
                break
        return action, path

    # If argument starts with '-' but wasn't recognized as a known option, fallback to start center
    if token.startswith("-"):
        return "start_center", None

    # Non-flag positional argument is treated as a direct file path
    return "file", token


def main(argv: list[str] | None = None, exec_app: bool = True) -> int:
    """Start the ATBOffice desktop application.

    Args:
        argv: Command-line arguments. If None, sys.argv is used.
        exec_app: If True, execute the Qt event loop via app.exec().

    Returns:
        Exit code (0 for success).
    """
    raw_argv = argv if argv is not None else sys.argv
    app = create_application(raw_argv)
    from atboffice.core.settings import get_app_settings

    get_app_settings().apply_startup_settings()
    win_mgr = WindowManager.get_instance()

    # Determine arguments to pass to parse_cli_args
    if argv is None:
        cli_args = raw_argv[1:]
    else:
        # Check if caller provided full argv with script/binary name at index 0
        if raw_argv and (
            raw_argv[0] in ("atboffice", "atboffice.py", "__main__.py")
            or raw_argv[0].endswith(("/atboffice", "\\atboffice", ".py"))
        ):
            cli_args = raw_argv[1:]
        else:
            cli_args = raw_argv

    action, path = parse_cli_args(cli_args)

    if action == "version":
        print(f"ATBOffice {__version__}")
        return 0

    if action == "help":
        print("Usage: atboffice [quire|ledger|lectern] [file] [-s|--start-center]")
        return 0

    window: Any
    if action == "quire":
        window = win_mgr.open_quire(path)
    elif action == "ledger":
        window = win_mgr.open_ledger(path)
    elif action == "lectern":
        window = win_mgr.open_lectern(path)
    elif action == "file" and path:
        window = win_mgr.open_file_auto(path)
    else:
        start_beh = get_app_settings().get_value(
            "general/start_behavior", "start_center"
        )
        if start_beh == "new_doc":
            window = win_mgr.open_quire()
        else:
            window = win_mgr.show_start_center()

    app.register_main_window(window)

    if not exec_app:
        return 0
    return app.exec()


def main_quire(argv: list[str] | None = None, exec_app: bool = True) -> int:
    """Convenience CLI entry point for the Quire word processor.

    Prepends ['quire'] subcommand and invokes main().
    """
    args = argv if argv is not None else sys.argv[1:]
    # Strip binary name if present in custom argv
    if args and (
        args[0] in ("atboffice-quire", "quire")
        or args[0].endswith((".py", "/atboffice-quire", "\\atboffice-quire"))
    ):
        args = args[1:]

    forward_args = args if (args and args[0] in ("quire", "--quire")) else ["quire", *args]
    return main(forward_args, exec_app=exec_app)


def main_ledger(argv: list[str] | None = None, exec_app: bool = True) -> int:
    """Convenience CLI entry point for the Ledger spreadsheet.

    Prepends ['ledger'] subcommand and invokes main().
    """
    args = argv if argv is not None else sys.argv[1:]
    if args and (
        args[0] in ("atboffice-ledger", "ledger")
        or args[0].endswith((".py", "/atboffice-ledger", "\\atboffice-ledger"))
    ):
        args = args[1:]

    forward_args = args if (args and args[0] in ("ledger", "--ledger")) else ["ledger", *args]
    return main(forward_args, exec_app=exec_app)


def main_lectern(argv: list[str] | None = None, exec_app: bool = True) -> int:
    """Convenience CLI entry point for the Lectern presentation tool.

    Prepends ['lectern'] subcommand and invokes main().
    """
    args = argv if argv is not None else sys.argv[1:]
    if args and (
        args[0] in ("atboffice-lectern", "lectern")
        or args[0].endswith((".py", "/atboffice-lectern", "\\atboffice-lectern"))
    ):
        args = args[1:]

    forward_args = args if (args and args[0] in ("lectern", "--lectern")) else ["lectern", *args]
    return main(forward_args, exec_app=exec_app)


if __name__ == "__main__":
    raise SystemExit(main())
