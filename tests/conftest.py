"""Global pytest configuration and shared fixtures for ATBOffice."""

import shutil
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import PySide6.QtCore as _qtcore
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtPrintSupport import QPrintDialog
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox

from atboffice.core.app import ATBApplication, create_application

_ORIG_QSETTINGS = QSettings
_PYTEST_QSETTINGS_DIR: str | None = None


class _IsolatedQSettings(_ORIG_QSETTINGS):  # type: ignore[misc]
    """Redirect 1/2-arg QSettings(org, app) calls to per-worker INI files during pytest."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if (
            _PYTEST_QSETTINGS_DIR
            and len(args) in (1, 2)
            and all(isinstance(a, str) for a in args)
            and not kwargs
        ):
            org = args[0]
            app = args[1] if len(args) == 2 else org
            ini_path = str(Path(_PYTEST_QSETTINGS_DIR) / f"{org}__{app}.ini")
            super().__init__(ini_path, _ORIG_QSETTINGS.Format.IniFormat)
        else:
            super().__init__(*args, **kwargs)


def pytest_configure(config: pytest.Config) -> None:
    """Create the suite's application before any test module can make a plain one."""
    global _PYTEST_QSETTINGS_DIR
    _PYTEST_QSETTINGS_DIR = tempfile.mkdtemp(prefix="atboffice-pytest-settings-")
    _qtcore.QSettings = _IsolatedQSettings  # type: ignore[misc]
    settings_mod = sys.modules.get("atboffice.core.settings")
    if settings_mod is not None:
        settings_mod.QSettings = _IsolatedQSettings  # type: ignore[attr-defined]
    create_application([])


def pytest_unconfigure(config: pytest.Config) -> None:
    """Remove per-worker QSettings storage created during pytest_configure."""
    global _PYTEST_QSETTINGS_DIR
    _qtcore.QSettings = _ORIG_QSETTINGS  # type: ignore[misc]
    settings_mod = sys.modules.get("atboffice.core.settings")
    if settings_mod is not None:
        settings_mod.QSettings = _ORIG_QSETTINGS  # type: ignore[attr-defined]
    if _PYTEST_QSETTINGS_DIR:
        shutil.rmtree(_PYTEST_QSETTINGS_DIR, ignore_errors=True)
        _PYTEST_QSETTINGS_DIR = None


@pytest.fixture(scope="session")
def qapp() -> ATBApplication:
    """Provide the ATBApplication singleton for all GUI test fixtures."""
    return create_application([])


@pytest.fixture(autouse=True, scope="session")
def guard_modal_dialogs_session() -> Generator[None, None, None]:
    """Prevent unmocked QMessageBox dialogs from blocking the automated test suite.

    If a test specifically mocks QMessageBox via monkeypatch or unittest.mock,
    that mock takes precedence. If a test does not mock it, this fallback prevents
    modal event loops from freezing pytest runs.
    """
    orig_warning = QMessageBox.warning
    orig_question = QMessageBox.question
    orig_information = QMessageBox.information
    orig_critical = QMessageBox.critical
    orig_about = QMessageBox.about

    def safe_warning(
        parent: Any = None,
        title: str = "",
        text: str = "",
        buttons: Any = QMessageBox.StandardButton.Ok,
        defaultButton: Any = QMessageBox.StandardButton.NoButton,
    ) -> Any:
        try:
            if buttons & QMessageBox.StandardButton.Discard:
                return QMessageBox.StandardButton.Discard
            if buttons & QMessageBox.StandardButton.Cancel:
                return QMessageBox.StandardButton.Cancel
            if buttons & QMessageBox.StandardButton.No:
                return QMessageBox.StandardButton.No
            if buttons & QMessageBox.StandardButton.Ok:
                return QMessageBox.StandardButton.Ok
        except Exception:
            pass
        return QMessageBox.StandardButton.Discard

    def safe_question(
        parent: Any = None,
        title: str = "",
        text: str = "",
        buttons: Any = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        defaultButton: Any = QMessageBox.StandardButton.NoButton,
    ) -> Any:
        try:
            if buttons & QMessageBox.StandardButton.Yes:
                return QMessageBox.StandardButton.Yes
            if buttons & QMessageBox.StandardButton.Ok:
                return QMessageBox.StandardButton.Ok
            if buttons & QMessageBox.StandardButton.No:
                return QMessageBox.StandardButton.No
        except Exception:
            pass
        return QMessageBox.StandardButton.Yes

    def safe_information(
        parent: Any = None,
        title: str = "",
        text: str = "",
        buttons: Any = QMessageBox.StandardButton.Ok,
        defaultButton: Any = QMessageBox.StandardButton.NoButton,
    ) -> Any:
        return QMessageBox.StandardButton.Ok

    def safe_critical(
        parent: Any = None,
        title: str = "",
        text: str = "",
        buttons: Any = QMessageBox.StandardButton.Ok,
        defaultButton: Any = QMessageBox.StandardButton.NoButton,
    ) -> Any:
        return QMessageBox.StandardButton.Ok

    def safe_about(
        parent: Any = None,
        title: str = "",
        text: str = "",
    ) -> None:
        return None

    QMessageBox.warning = safe_warning  # type: ignore[assignment]
    QMessageBox.question = safe_question  # type: ignore[assignment]
    QMessageBox.information = safe_information  # type: ignore[assignment]
    QMessageBox.critical = safe_critical  # type: ignore[assignment]
    QMessageBox.about = safe_about  # type: ignore[assignment]

    # File dialogs answer "cancelled" and the print dialog "OK", so commands
    # that ask for a path or a printer run without a person at the keyboard.
    # Tests that need a path monkeypatch these themselves.
    file_dialog_stubs = {
        "getOpenFileName": lambda *a, **k: ("", ""),
        "getOpenFileNames": lambda *a, **k: ([], ""),
        "getSaveFileName": lambda *a, **k: ("", ""),
        "getExistingDirectory": lambda *a, **k: "",
    }
    orig_file_dialog = {name: getattr(QFileDialog, name) for name in file_dialog_stubs}
    for name, stub in file_dialog_stubs.items():
        setattr(QFileDialog, name, staticmethod(stub))
    orig_print_exec = QPrintDialog.exec
    QPrintDialog.exec = lambda self: QPrintDialog.DialogCode.Accepted  # type: ignore[assignment]

    yield

    for name, original in orig_file_dialog.items():
        setattr(QFileDialog, name, original)
    QPrintDialog.exec = orig_print_exec  # type: ignore[assignment]

    QMessageBox.warning = orig_warning  # type: ignore[assignment]
    QMessageBox.question = orig_question  # type: ignore[assignment]
    QMessageBox.information = orig_information  # type: ignore[assignment]
    QMessageBox.critical = orig_critical  # type: ignore[assignment]
    QMessageBox.about = orig_about  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def cleanup_dirty_windows_fixture() -> Generator[None, None, None]:
    """Fixture to reset dirty state on all windows before teardown closes them."""
    yield
    app = QApplication.instance()
    if app is not None and hasattr(app, "topLevelWidgets"):
        # Only main windows carry dirty state; skipping the many top-level QMenus
        # keeps this per-test walk cheap as closed windows accumulate.
        for top_w in app.topLevelWidgets():
            if isinstance(top_w, QMainWindow) and hasattr(top_w, "set_modified"):
                top_w.set_modified(False)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    """Ensure all Qt widgets have dirty state cleared before pytest-qt closes them."""
    widgets = getattr(item, "qt_widgets", None)
    if widgets:
        for w_ref, _ in widgets:
            w = w_ref()
            if w is not None and hasattr(w, "set_modified"):
                w.set_modified(False)

    app = QApplication.instance()
    if app is not None and hasattr(app, "topLevelWidgets"):
        # Only main windows carry dirty state; skipping the many top-level QMenus
        # keeps this per-test walk cheap as closed windows accumulate.
        for top_w in app.topLevelWidgets():
            if isinstance(top_w, QMainWindow) and hasattr(top_w, "set_modified"):
                top_w.set_modified(False)


def pytest_runtest_logfinish(nodeid: str, location: tuple) -> None:
    """Flush deferred deletions after every test (runs after widget teardown).

    Closed windows are only ``deleteLater``-ed; letting hundreds pile up makes the
    next event-loop drain destroy them all at once, and PySide's per-object
    signal-tracker cleanup turns that into a multi-minute (quadratic) stall.
    """
    from PySide6.QtCore import QCoreApplication, QEvent

    if QCoreApplication.instance() is not None:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(autouse=True)
def _no_unexpected_compatibility_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    """A modal Compatibility Checker would block the run: fail fast unless a test patches it."""
    from atboffice.ui.dialogs.compatibility_dialog import CompatibilityDialog

    def unexpected(dlg: Any) -> int:
        raise AssertionError(
            "Unexpected Compatibility Checker dialog: "
            + ", ".join(loss.feature for loss in dlg.losses)
        )

    monkeypatch.setattr(CompatibilityDialog, "exec", unexpected)


@pytest.fixture(autouse=True)
def _restore_default_locale() -> Generator[None, None, None]:
    """Every test starts and ends in Simplified Chinese, the default UI language.

    Tests that switch to another language would otherwise change the text later
    tests on the same worker see.
    """
    from atboffice.core.i18n import get_i18n_manager

    manager = get_i18n_manager()
    if manager.current_locale != "zh-CN":
        manager.set_locale("zh-CN")
    yield
    if manager.current_locale != "zh-CN":
        manager.set_locale("zh-CN")
