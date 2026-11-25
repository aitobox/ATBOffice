"""Regression tests for issue #438: window lifecycle, save safety and RecoveryService."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from atboffice.core.window_manager import WindowManager
from atboffice.modules.writer.io.docx_writer import write_docx
from atboffice.modules.writer.models.document import Paragraph, TextItem
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.vfs.crypto import decrypt_package, encrypt_package, is_encrypted_package


@pytest.fixture
def window_manager(qapp):
    WindowManager.reset_instance()
    wm = WindowManager.get_instance()
    yield wm
    wm._is_quitting = True
    for win in list(wm.active_windows):
        win.set_modified(False)
        win.close()
    if wm.start_center is not None:
        wm.start_center.close()
    qapp.processEvents()
    WindowManager.reset_instance()


@pytest.fixture
def capture_errors(monkeypatch):
    messages: list[str] = []

    def fake_critical(parent, title, text, *args, **kwargs):
        messages.append(text)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "critical", fake_critical)
    return messages


def _quire_with_text(text: str = "Hello Quire") -> QuireWindow:
    win = QuireWindow()
    doc = win.writer_view.canvas_view.doc
    para = Paragraph()
    para.runs.append(TextItem(text=text))
    doc.main.blocks.insert(0, para)
    return win


# ---------------------------------------------------------------------------
# Close lifecycle
# ---------------------------------------------------------------------------


def test_close_event_does_not_drain_event_loop(qtbot, monkeypatch) -> None:
    import atboffice.core.diagnostics as diagnostics

    calls: list[int] = []
    monkeypatch.setattr(diagnostics, "drain_event_loop", lambda n=5: calls.append(n))
    win = QuireWindow()
    qtbot.addWidget(win)

    win.close()

    assert win._is_closed is True
    assert calls == []


@pytest.mark.parametrize("window_cls", [QuireWindow, LedgerWindow, LecternWindow])
def test_rapid_open_close_stress_releases_windows_safely(qapp, window_manager, window_cls) -> None:
    for _ in range(5):
        win = window_cls()
        window_manager.register_window(win)
        win.show()
        win.close()
        # The closed window is kept alive until control returns to the event loop.
        assert win in window_manager._closing_windows
        assert win not in window_manager.active_windows
        qapp.processEvents()

    qapp.processEvents()
    assert window_manager._closing_windows == []


def test_cancelled_close_keeps_window_registered(qtbot, window_manager, monkeypatch) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)
    window_manager.register_window(win)
    monkeypatch.setattr(win, "maybe_save_prompt", lambda: False)

    win.close()

    assert win in window_manager.active_windows
    assert win.recovery_service.is_running() is True


def test_main_window_reference_is_retargeted_on_close(qapp, window_manager) -> None:
    first = QuireWindow()
    second = LedgerWindow()
    window_manager.register_window(first)
    window_manager.register_window(second)
    qapp._main_window = first

    first.close()
    assert qapp._main_window is second

    second.close()
    assert qapp._main_window is window_manager.start_center
    assert qapp._main_window is not second
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Save safety
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("suffix", [".rtf", ".md", ".markdown", ".txt"])
def test_quire_text_exports_are_not_empty(qtbot, tmp_path: Path, suffix: str) -> None:
    win = _quire_with_text("Hello Quire")
    qtbot.addWidget(win)
    target = tmp_path / f"out{suffix}"

    assert win.save_file(target, confirm_overwrite=False) is True

    data = target.read_bytes()
    assert data, "export must not be a 0-byte file"
    assert b"Hello Quire" in data


def test_quire_zip_export_contains_markdown(qtbot, tmp_path: Path) -> None:
    win = _quire_with_text("Zipped text")
    qtbot.addWidget(win)
    target = tmp_path / "bundle.zip"

    assert win.save_file(target, confirm_overwrite=False) is True

    with zipfile.ZipFile(target) as zf:
        md_names = [n for n in zf.namelist() if n.endswith(".md")]
        assert md_names
        assert b"Zipped text" in zf.read(md_names[0])


def test_quire_txt_export_includes_table_text(qtbot, tmp_path: Path, monkeypatch) -> None:
    from atboffice.modules.writer.models.document import Cell, Row, Table
    from atboffice.ui.dialogs.compatibility_dialog import CompatibilityDialog

    shown: list[list[str]] = []

    def accept(dlg):
        shown.append([loss.feature for loss in dlg.losses])
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(CompatibilityDialog, "exec", accept)

    win = _quire_with_text("Intro")
    qtbot.addWidget(win)
    cell_a, cell_b = Cell(), Cell()
    for cell, text in ((cell_a, "A1"), (cell_b, "B1")):
        p = Paragraph()
        p.runs.append(TextItem(text=text))
        cell.blocks = [p]
    win.writer_view.canvas_view.doc.main.blocks.insert(1, Table(rows=[Row(cells=[cell_a, cell_b])]))
    target = tmp_path / "table.txt"

    assert win.save_file(target, confirm_overwrite=False) is True

    text = target.read_text(encoding="utf-8")
    assert "Intro" in text
    assert "A1\tB1" in text
    assert len(shown) == 1 and any("表格" in f for f in shown[0])  # table loss announced once


@pytest.mark.parametrize(
    ("window_cls", "suffix"),
    [
        (QuireWindow, ".png"),
        (QuireWindow, ".odt"),
        (LedgerWindow, ".ods"),
        (LedgerWindow, ".png"),
        (LecternWindow, ".odp"),
        (LecternWindow, ".html"),
    ],
)
def test_unsupported_formats_fail_without_creating_files(
    qtbot, tmp_path: Path, capture_errors, window_cls, suffix: str
) -> None:
    win = window_cls()
    qtbot.addWidget(win)
    target = tmp_path / f"out{suffix}"

    assert win.save_file(target, confirm_overwrite=False) is False

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
    assert capture_errors and suffix in capture_errors[-1]


@pytest.mark.parametrize(
    ("window_cls", "suffix"),
    [(LedgerWindow, ".xlsx"), (LedgerWindow, ".csv"), (LecternWindow, ".pptx")],
)
def test_supported_formats_still_write_content(
    qtbot, tmp_path: Path, window_cls, suffix: str
) -> None:
    win = window_cls()
    qtbot.addWidget(win)
    target = tmp_path / f"out{suffix}"

    assert win.save_file(target, confirm_overwrite=False) is True
    assert target.stat().st_size > 0 or suffix == ".csv"


@pytest.mark.parametrize("window_cls", [LedgerWindow, LecternWindow])
def test_compatibility_losses_prompt_can_cancel_save(
    qtbot, tmp_path: Path, monkeypatch, capture_errors, window_cls
) -> None:
    win = window_cls()
    qtbot.addWidget(win)
    model = win.spreadsheet_view.workbook if window_cls is LedgerWindow else win.presentation
    model.losses = ["Unsupported chart type"]
    asked: list[list[str]] = []

    from atboffice.ui.dialogs.compatibility_dialog import CompatibilityDialog

    def fake_exec(dlg):
        asked.append([loss.feature for loss in dlg.losses])
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(CompatibilityDialog, "exec", fake_exec)
    suffix = ".xlsx" if window_cls is LedgerWindow else ".pptx"
    target = tmp_path / f"lossy{suffix}"

    assert win.save_file(target, confirm_overwrite=False) is False
    assert asked == [["Unsupported chart type"]]  # asked exactly once
    assert not target.exists()


# ---------------------------------------------------------------------------
# Encryption password preservation
# ---------------------------------------------------------------------------


def test_encrypted_docx_stays_encrypted_after_save(qtbot, tmp_path: Path, monkeypatch) -> None:
    source = _quire_with_text("Top secret")
    qtbot.addWidget(source)
    plain = write_docx(source.writer_view.canvas_view.doc)
    target = tmp_path / "secret.docx"
    target.write_bytes(encrypt_package(plain, passcode="s3cret"))

    win = QuireWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "prompt_for_package_password", lambda name: "s3cret")
    assert win.open_file(target) is True

    win.set_modified(True)
    assert win.save_file() is True

    assert is_encrypted_package(target)
    decrypted = decrypt_package(target, passcode="s3cret")
    assert decrypted[:2] == b"PK"


def test_password_cleared_after_opening_plain_file(qtbot, tmp_path: Path, monkeypatch) -> None:
    source = _quire_with_text("Body")
    qtbot.addWidget(source)
    plain = write_docx(source.writer_view.canvas_view.doc)
    enc_path = tmp_path / "enc.docx"
    enc_path.write_bytes(encrypt_package(plain, passcode="pw"))
    plain_path = tmp_path / "plain.docx"
    plain_path.write_bytes(plain)

    win = QuireWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "prompt_for_package_password", lambda name: "pw")
    assert win.open_file(enc_path) is True
    assert win.open_file(plain_path) is True

    assert win.save_file() is True
    assert not is_encrypted_package(plain_path)


def test_failed_open_keeps_previous_password(qtbot, tmp_path: Path, monkeypatch) -> None:
    source = _quire_with_text("Body")
    qtbot.addWidget(source)
    plain = write_docx(source.writer_view.canvas_view.doc)
    enc_path = tmp_path / "enc.docx"
    enc_path.write_bytes(encrypt_package(plain, passcode="first"))
    other = tmp_path / "other.docx"
    other.write_bytes(encrypt_package(plain, passcode="second"))

    win = QuireWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "prompt_for_package_password", lambda name: "first")
    assert win.open_file(enc_path) is True
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok)
    assert win.open_file(other) is False  # wrong password for this file

    assert win.save_file() is True
    assert decrypt_package(enc_path, passcode="first")[:2] == b"PK"


# ---------------------------------------------------------------------------
# RecoveryService lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("window_cls", [QuireWindow, LedgerWindow, LecternWindow])
def test_recovery_service_starts_and_stops_with_window(qtbot, window_cls) -> None:
    win = window_cls()
    qtbot.addWidget(win)
    assert win.recovery_service.is_running() is True

    win.close()

    assert win.recovery_service.is_running() is False


def test_recovery_draft_uses_native_suffix_and_has_content(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    win = _quire_with_text("Draft me")
    qtbot.addWidget(win)
    monkeypatch.setattr(win.recovery_service, "_recovery_dir", tmp_path)

    assert win.recovery_service.trigger_autosave() is False  # unmodified → no draft
    win.set_modified(True)
    assert win.recovery_service.trigger_autosave() is True

    drafts = list(tmp_path.iterdir())
    assert len(drafts) == 1
    assert drafts[0].suffix == ".docx"
    assert drafts[0].stat().st_size > 0


def test_recovery_draft_never_prompts(qtbot, tmp_path: Path, monkeypatch) -> None:
    win = _quire_with_text("Lossy")
    qtbot.addWidget(win)
    win.writer_view.canvas_view.doc.losses = [{"kind": "smartart"}]
    monkeypatch.setattr(win.recovery_service, "_recovery_dir", tmp_path)

    def boom(*args, **kwargs):
        raise AssertionError("autosave must not show dialogs")

    monkeypatch.setattr(QMessageBox, "warning", boom)
    win.set_modified(True)

    assert win.recovery_service.trigger_autosave() is True
    win.set_modified(False)


def test_recovery_draft_cleared_after_manual_save_and_close(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    win = _quire_with_text("Saved")
    qtbot.addWidget(win)
    monkeypatch.setattr(win.recovery_service, "_recovery_dir", drafts_dir)
    win.set_modified(True)
    assert win.recovery_service.trigger_autosave() is True
    assert list(drafts_dir.iterdir())

    assert win.save_file(tmp_path / "saved.docx", confirm_overwrite=False) is True
    assert list(drafts_dir.iterdir()) == []

    win.set_modified(True)
    assert win.recovery_service.trigger_autosave() is True
    win.set_modified(False)
    win.close()
    assert list(drafts_dir.iterdir()) == []


def test_recovery_draft_of_encrypted_document_is_encrypted(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    source = _quire_with_text("Body")
    qtbot.addWidget(source)
    enc_path = tmp_path / "enc.docx"
    enc_path.write_bytes(
        encrypt_package(write_docx(source.writer_view.canvas_view.doc), passcode="pw")
    )
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()

    win = QuireWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "prompt_for_package_password", lambda name: "pw")
    assert win.open_file(enc_path) is True
    monkeypatch.setattr(win.recovery_service, "_recovery_dir", drafts_dir)
    win.set_modified(True)

    assert win.recovery_service.trigger_autosave() is True
    (draft,) = list(drafts_dir.iterdir())
    assert is_encrypted_package(draft)
    win.set_modified(False)


def test_failed_recovery_draft_leaves_no_partial_file(qtbot, tmp_path: Path, monkeypatch) -> None:
    win = _quire_with_text("Broken")
    qtbot.addWidget(win)
    monkeypatch.setattr(win.recovery_service, "_recovery_dir", tmp_path)

    def broken_save(path: Path) -> bool:
        path.write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(win, "do_save", broken_save)
    win.set_modified(True)

    assert win.recovery_service.trigger_autosave() is False
    assert list(tmp_path.iterdir()) == []
    win.set_modified(False)
