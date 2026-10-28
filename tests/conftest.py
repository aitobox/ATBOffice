"""Global pytest configuration and shared fixtures for ATBOffice."""

from collections.abc import Generator
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from atboffice.core.app import ATBApplication, create_application


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

    yield

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
    if app is not None:
        for top_w in app.topLevelWidgets():
            if hasattr(top_w, "set_modified"):
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
    if app is not None:
        for top_w in app.topLevelWidgets():
            if hasattr(top_w, "set_modified"):
                top_w.set_modified(False)
