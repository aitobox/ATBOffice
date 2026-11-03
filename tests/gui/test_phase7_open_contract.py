"""Contract and regression tests for TASK-702 / Issue #236:
Transactional document open, false-success prevention, legacy format rejection,
password cancellation, and format reader dispatch.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QInputDialog, QMessageBox

from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.vfs.crypto import encrypt_package


def test_quire_legacy_doc_rejected_with_guidance(qtbot, monkeypatch, tmp_path: Path):
    """Quire must reject legacy binary .doc with clear guidance and preserve state."""
    doc_file = Path("tests/docs/word/doc/poi__ThreeColHead.doc")
    if not doc_file.exists():
        doc_file = tmp_path / "legacy.doc"
        doc_file.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512)

    win = QuireWindow()
    qtbot.addWidget(win)

    orig_path = tmp_path / "original.docx"
    win.current_file_path = orig_path
    win.set_modified(True)
    initial_title = win.windowTitle()
    # User confirms discarding unsaved changes to open the new file
    win.maybe_save_prompt = lambda: True

    dialogs: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, text, *args, **kwargs: dialogs.append((title, text)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda parent, title, text, *args, **kwargs: dialogs.append((title, text)),
    )

    success = win.open_file(doc_file)
    assert success is False
    # Transactional state preservation:
    assert win.current_file_path == orig_path
    assert win.is_modified is True
    assert win.windowTitle() == initial_title
    # Guidance was shown:
    assert len(dialogs) >= 1
    assert any("doc" in text.lower() or "docx" in text.lower() for _, text in dialogs)


def test_ledger_legacy_xls_rejected_with_guidance(qtbot, monkeypatch, tmp_path: Path):
    """Ledger must reject legacy binary .xls with clear guidance and preserve state."""
    xls_file = Path("tests/docs/excel/xls/libreoffice__AutoFilter.xls")
    if not xls_file.exists():
        xls_file = tmp_path / "legacy.xls"
        xls_file.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512)

    win = LedgerWindow()
    qtbot.addWidget(win)

    orig_path = tmp_path / "original.xlsx"
    win.current_file_path = orig_path
    win.set_modified(True)
    initial_title = win.windowTitle()
    win.maybe_save_prompt = lambda: True

    dialogs: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, text, *args, **kwargs: dialogs.append((title, text)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda parent, title, text, *args, **kwargs: dialogs.append((title, text)),
    )

    success = win.open_file(xls_file)
    assert success is False
    assert win.current_file_path == orig_path
    assert win.is_modified is True
    assert win.windowTitle() == initial_title
    assert len(dialogs) >= 1
    assert any("xls" in text.lower() or "xlsx" in text.lower() for _, text in dialogs)


def test_lectern_legacy_ppt_rejected_with_guidance(qtbot, monkeypatch, tmp_path: Path):
    """Lectern must reject legacy binary .ppt with clear guidance and preserve state."""
    ppt_file = Path("tests/docs/powerpoint/ppt/poi__datetime.ppt")
    if not ppt_file.exists():
        ppt_file = tmp_path / "legacy.ppt"
        ppt_file.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512)

    win = LecternWindow()
    qtbot.addWidget(win)

    orig_path = tmp_path / "original.pptx"
    win.current_file_path = orig_path
    win.set_modified(True)
    initial_title = win.windowTitle()
    win.maybe_save_prompt = lambda: True

    dialogs: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, text, *args, **kwargs: dialogs.append((title, text)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda parent, title, text, *args, **kwargs: dialogs.append((title, text)),
    )

    success = win.open_file(ppt_file)
    assert success is False
    assert win.current_file_path == orig_path
    assert win.is_modified is True
    assert win.windowTitle() == initial_title
    assert len(dialogs) >= 1
    assert any("ppt" in text.lower() or "pptx" in text.lower() for _, text in dialogs)


def test_unknown_extension_rejected_safely(qtbot, monkeypatch, tmp_path: Path):
    """Opening unknown extensions must fail cleanly and preserve window state."""
    unknown_file = tmp_path / "sample.unsupported_ext"
    unknown_file.write_bytes(b"RANDOM_BYTES")

    for WinClass in (QuireWindow, LedgerWindow, LecternWindow):
        win = WinClass()
        qtbot.addWidget(win)
        win.set_modified(True)
        orig_path = tmp_path / "prev.doc"
        win.current_file_path = orig_path
        win.maybe_save_prompt = lambda: True

        monkeypatch.setattr(QMessageBox, "critical", lambda *a, **kw: None)
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: None)

        assert win.open_file(unknown_file) is False
        assert win.current_file_path == orig_path
        assert win.is_modified is True


def test_encrypted_package_cancellation_aborts_cleanly(qtbot, monkeypatch, tmp_path: Path):
    """Cancelling password dialog for encrypted OOXML packages aborts cleanly without error dialog."""
    # Create valid dummy encrypted docx
    inner_zip = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\x00" * 200
    enc_bytes = encrypt_package(inner_zip, passcode="secret123")
    enc_file = tmp_path / "protected.docx"
    enc_file.write_bytes(enc_bytes)

    win = QuireWindow()
    qtbot.addWidget(win)
    orig_path = tmp_path / "untouched.docx"
    win.current_file_path = orig_path
    win.set_modified(True)
    win.maybe_save_prompt = lambda: True

    critical_dialogs: list[Any] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args, **kwargs: critical_dialogs.append(args),
    )
    # Simulate user clicking Cancel on password prompt
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("", False),
    )

    success = win.open_file(enc_file)
    assert success is False
    assert win.current_file_path == orig_path
    assert win.is_modified is True
    # Cancellation must NOT produce a critical error dialog!
    assert len(critical_dialogs) == 0


def test_encrypted_package_wrong_password_shows_warning(qtbot, monkeypatch, tmp_path: Path):
    """Supplying incorrect password displays warning and aborts without corrupting state."""
    inner_zip = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\x00" * 200
    enc_bytes = encrypt_package(inner_zip, passcode="correct_pass")
    enc_file = tmp_path / "protected.docx"
    enc_file.write_bytes(enc_bytes)

    win = QuireWindow()
    qtbot.addWidget(win)
    orig_path = tmp_path / "untouched.docx"
    win.current_file_path = orig_path
    win.set_modified(True)
    win.maybe_save_prompt = lambda: True

    warnings: list[Any] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: warnings.append(args),
    )
    # Simulate user entering wrong password
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("wrong_pass", True),
    )

    success = win.open_file(enc_file)
    assert success is False
    assert win.current_file_path == orig_path
    assert win.is_modified is True
    assert len(warnings) == 1


def test_quire_binding_failure_rollback(qtbot, monkeypatch, tmp_path: Path):
    """If view binding raises an exception, previous document state is completely preserved."""
    test_docx = tmp_path / "test.docx"
    win_init = QuireWindow()
    qtbot.addWidget(win_init)
    win_init.save_file(test_docx)

    win = QuireWindow()
    qtbot.addWidget(win)
    orig_doc = win.writer_view.canvas_view.doc
    orig_path = tmp_path / "orig.docx"
    win.current_file_path = orig_path
    win.set_modified(True)
    win.maybe_save_prompt = lambda: True

    def failing_set_document(doc):
        raise RuntimeError("Simulated UI canvas binding failure")

    monkeypatch.setattr(win.writer_view.canvas_view, "set_document", failing_set_document)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    success = win.open_file(test_docx)
    assert success is False
    assert win.current_file_path == orig_path
    assert win.is_modified is True
    assert win.writer_view.canvas_view.doc is orig_doc


def test_promised_formats_open_success_contract(qtbot, tmp_path: Path):
    """All promised formats across Quire, Ledger, and Lectern open and bind cleanly."""
    # 1. Quire formats
    # 1.1 Quire HTML
    html_file = tmp_path / "sample.html"
    html_file.write_text("<p>Hello HTML Quire</p>", encoding="utf-8")
    win_q1 = QuireWindow()
    qtbot.addWidget(win_q1)
    assert win_q1.open_file(html_file) is True
    assert win_q1.current_file_path == html_file.resolve()
    assert win_q1.is_modified is False
    assert "sample.html" in win_q1.windowTitle()

    # 1.2 Quire RTF
    rtf_file = tmp_path / "sample.rtf"
    rtf_file.write_bytes(b"{\\rtf1\\ansi\\deff0 {\\fonttbl {\\f0 Arial;}} \\f0\\fs24 Hello RTF}")
    win_q2 = QuireWindow()
    qtbot.addWidget(win_q2)
    assert win_q2.open_file(rtf_file) is True
    assert win_q2.current_file_path == rtf_file.resolve()
    assert win_q2.is_modified is False

    # 1.3 Quire Markdown
    md_file = tmp_path / "sample.md"
    md_file.write_text("# Title\n\nMarkdown paragraph text", encoding="utf-8")
    win_q3 = QuireWindow()
    qtbot.addWidget(win_q3)
    assert win_q3.open_file(md_file) is True
    assert win_q3.current_file_path == md_file.resolve()
    assert win_q3.is_modified is False

    # 1.4 Quire TXT
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text("Line 1 text\nLine 2 text", encoding="utf-8")
    win_q4 = QuireWindow()
    qtbot.addWidget(win_q4)
    assert win_q4.open_file(txt_file) is True
    assert win_q4.current_file_path == txt_file.resolve()
    assert win_q4.is_modified is False

    # 1.5 Quire DOCX
    docx_file = Path("tests/docs/word/docx/libreoffice__textframe-borders.docx")
    if docx_file.exists():
        win_q5 = QuireWindow()
        qtbot.addWidget(win_q5)
        assert win_q5.open_file(docx_file) is True
        assert win_q5.current_file_path == docx_file.resolve()
        assert win_q5.is_modified is False

    # 2. Ledger formats
    # 2.1 Ledger CSV
    csv_file = tmp_path / "sample.csv"
    csv_file.write_text("Name,Age,Score\nAlice,30,95\nBob,25,88\n", encoding="utf-8")
    win_l1 = LedgerWindow()
    qtbot.addWidget(win_l1)
    assert win_l1.open_file(csv_file) is True
    assert win_l1.current_file_path == csv_file.resolve()
    assert win_l1.is_modified is False
    assert win_l1.spreadsheet_view.model.get_cell(0, 0).value == "Name"

    # 2.2 Ledger TSV
    tsv_file = tmp_path / "sample.tsv"
    tsv_file.write_text("ID\tStatus\n101\tActive\n", encoding="utf-8")
    win_l2 = LedgerWindow()
    qtbot.addWidget(win_l2)
    assert win_l2.open_file(tsv_file) is True
    assert win_l2.current_file_path == tsv_file.resolve()
    assert win_l2.is_modified is False
    assert win_l2.spreadsheet_view.model.get_cell(0, 0).value == "ID"

    # 2.3 Ledger XML (XMLSS)
    xml_file = tmp_path / "sample.xml"
    xml_content = (
        '<?xml version="1.0"?>\n'
        '<?mso-application progid="Excel.Sheet"?>\n'
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"\n'
        ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n'
        ' <Worksheet ss:Name="Sheet1">\n'
        "  <Table>\n"
        "   <Row>\n"
        '    <Cell><Data ss:Type="String">XMLSS Header</Data></Cell>\n'
        "   </Row>\n"
        "  </Table>\n"
        " </Worksheet>\n"
        "</Workbook>"
    )
    xml_file.write_text(xml_content, encoding="utf-8")
    win_l3 = LedgerWindow()
    qtbot.addWidget(win_l3)
    assert win_l3.open_file(xml_file) is True
    assert win_l3.current_file_path == xml_file.resolve()
    assert win_l3.is_modified is False

    # 2.4 Ledger XLSX
    xlsx_file = tmp_path / "sample.xlsx"
    win_l_save = LedgerWindow()
    qtbot.addWidget(win_l_save)
    win_l_save.spreadsheet_view.model.set_cell_value(0, 0, "SavedXLSX")
    win_l_save.save_file(xlsx_file)

    win_l4 = LedgerWindow()
    qtbot.addWidget(win_l4)
    assert win_l4.open_file(xlsx_file) is True
    assert win_l4.current_file_path == xlsx_file.resolve()
    assert win_l4.is_modified is False

    # 3. Lectern formats
    pptx_file = tmp_path / "sample.pptx"
    win_p_save = LecternWindow()
    qtbot.addWidget(win_p_save)
    win_p_save.save_file(pptx_file)

    win_p = LecternWindow()
    qtbot.addWidget(win_p)
    assert win_p.open_file(pptx_file) is True
    assert win_p.current_file_path == pptx_file.resolve()
    assert win_p.is_modified is False


def test_recent_files_not_updated_on_failed_open(qtbot, tmp_path: Path):
    """Failed open operations must not register the target path in RecentFilesManager."""
    from atboffice.core.window_manager import WindowManager

    wm = WindowManager.get_instance()
    wm.recent_files.clear_all()

    corrupt_file = tmp_path / "never_opened.docx"
    corrupt_file.write_bytes(b"CORRUPT")

    win = QuireWindow()
    qtbot.addWidget(win)
    win.maybe_save_prompt = lambda: True

    assert win.open_file(corrupt_file) is False
    entries = wm.recent_files.get_entries()
    assert not any(Path(e.path) == corrupt_file.resolve() for e in entries)

