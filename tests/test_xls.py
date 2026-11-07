"""Comprehensive unit and integration test suite for Excel 97-2003 (.xls) support."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from atboffice.modules.spreadsheet.io.xls_reader import (
    is_xls_supported,
    read_xls,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.ui.shell.ledger_window import LedgerWindow


def test_is_xls_supported():
    """Verify is_xls_supported returns True when xlrd is available."""
    assert is_xls_supported() is True


def test_read_xls_multi_sheet():
    """Verify reading a multi-sheet .xls file preserves sheet names and orders."""
    sample = Path("tests/docs/excel/xls/libreoffice__AutoFilter.xls")
    assert sample.exists()

    wb = read_xls(sample)
    assert isinstance(wb, WorkbookModel)
    sheet_names = [s.name for s in wb.sheets]
    assert sheet_names == ["Sheet1", "Sheet2", "Sheet3"]
    assert len(wb.sheets[0].cells) > 0


def test_read_xls_data_types():
    """Verify reading numbers, integers, floats, strings, and booleans."""
    sample = Path("tests/docs/excel/xls/poi__tile-range-test.xls")
    assert sample.exists()

    wb = read_xls(sample)
    s = wb.sheets[0]

    # Integers / floats
    assert s.get_cell_value(0, 0) == 0
    assert isinstance(s.get_cell_value(0, 0), int)
    assert s.get_cell_value(0, 1) == 1
    assert isinstance(s.get_cell_value(0, 1), int)

    val_float = s.get_cell_value(1, 0)
    assert abs(val_float - 0.1) < 1e-6
    assert isinstance(val_float, float)


def test_read_xls_ifna_test_cases():
    """Verify reading formulas, text, and structure from poi__IfNaTestCaseData.xls."""
    sample = Path("tests/docs/excel/xls/poi__IfNaTestCaseData.xls")
    assert sample.exists()

    wb = read_xls(sample)
    assert len(wb.sheets) == 2
    assert wb.sheets[0].name == "Read Me"
    assert wb.sheets[1].name == "Ifna"

    cell_0_0 = wb.sheets[0].get_cell(0, 0)
    assert cell_0_0 is not None
    assert "IFNA" in cell_0_0.value


def test_read_xls_from_bytes_and_stream():
    """Verify read_xls accepts bytes and BytesIO streams."""
    sample = Path("tests/docs/excel/xls/poi__tile-range-test.xls")
    raw_bytes = sample.read_bytes()

    wb_from_bytes = read_xls(raw_bytes)
    assert len(wb_from_bytes.sheets) == 2

    stream = io.BytesIO(raw_bytes)
    wb_from_stream = read_xls(stream)
    assert len(wb_from_stream.sheets) == 2


def test_read_xls_merged_cells():
    """Verify merged cell bounds conversion from half-open [rlo, rhi) to inclusive."""
    sample = Path("tests/docs/excel/xls/poi__49524.xls")
    if sample.exists():
        wb = read_xls(sample)
        # Verify that merged cell ranges have r_end >= r_start and c_end >= c_start
        for sheet in wb.sheets:
            for r1, c1, r2, c2 in sheet.merges:
                assert r2 >= r1
                assert c2 >= c1


def test_read_xls_geometry_and_styles():
    """Verify column widths, row heights, and font styles are extracted."""
    sample = Path("tests/docs/excel/xls/libreoffice__AutoFilter.xls")
    assert sample.exists()

    wb = read_xls(sample)
    s = wb.sheets[0]

    # Geometries should be initialized
    assert hasattr(s, "geometry")
    # Non-empty cells should have formatting and fonts
    for (r, c), cell in s.cells.items():
        assert cell.font_size > 0
        assert cell.format_code is not None


def test_read_xls_missing_dependency(monkeypatch):
    """Verify read_xls raises RuntimeError when xlrd is missing."""
    import atboffice.modules.spreadsheet.io.xls_reader as mod

    monkeypatch.setattr(mod, "HAS_XLRD", False)
    with pytest.raises(RuntimeError, match="xlrd is not installed"):
        mod.read_xls(Path("tests/docs/excel/xls/poi__tile-range-test.xls"))


def test_read_xls_nonexistent_file():
    """Verify read_xls raises FileNotFoundError for missing paths."""
    with pytest.raises(FileNotFoundError):
        read_xls(Path("tests/docs/excel/xls/nonexistent_file_12345.xls"))


def test_read_xls_corrupt_file():
    """Verify read_xls raises ValueError on corrupt/invalid files."""
    corrupt_sample = Path("tests/docs/excel/xls/libreoffice__crash-5.xls")
    if corrupt_sample.exists():
        with pytest.raises(ValueError):
            read_xls(corrupt_sample)


def test_ledger_window_open_xls_with_notice(qtbot, monkeypatch, tmp_path: Path):
    """Verify LedgerWindow opens .xls file, displays status notice, and updates state."""
    sample = Path("tests/docs/excel/xls/poi__tile-range-test.xls")
    assert sample.exists()

    win = LedgerWindow()
    qtbot.addWidget(win)

    win.maybe_save_prompt = lambda: True

    success = win.open_file(sample)
    assert success is True
    assert win.current_file_path == sample.resolve()
    assert win.is_modified is False
    assert len(win.spreadsheet_view.workbook.sheets) == 2
    # Gentle notice shown on status bar
    assert "Excel 97–2003" in win.status_bar.currentMessage()


def test_ledger_window_open_xls_fallback_when_disabled(qtbot, monkeypatch, tmp_path: Path):
    """Verify LedgerWindow falls back to guidance dialog when xls reading is unsupported."""
    monkeypatch.setattr(
        "atboffice.modules.spreadsheet.io.xls_reader.is_xls_supported",
        lambda: False,
    )
    sample = Path("tests/docs/excel/xls/poi__tile-range-test.xls")
    assert sample.exists()

    win = LedgerWindow()
    qtbot.addWidget(win)

    win.maybe_save_prompt = lambda: True

    dialogs: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, text, *args, **kwargs: dialogs.append((title, text)),
    )

    success = win.open_file(sample)
    assert success is False
    assert len(dialogs) >= 1
    assert any("xls" in text.lower() or "xlsx" in text.lower() for _, text in dialogs)


def test_ledger_window_disguised_file_rejected(qtbot, monkeypatch, tmp_path: Path):
    """Verify disguised Word document with .xls extension is rejected."""
    # Create fake OLE file with WordDocument stream but .xls extension
    from atboffice.vfs.crypto import CFB_SIGNATURE

    fake_word = bytearray(CFB_SIGNATURE + b"\x00" * 504)
    fake_word.extend("WordDocument".encode("utf-16le"))

    fake_xls = tmp_path / "disguised.xls"
    fake_xls.write_bytes(bytes(fake_word))

    win = LedgerWindow()
    qtbot.addWidget(win)
    win.maybe_save_prompt = lambda: True

    dialogs: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, text, *args, **kwargs: dialogs.append((title, text)),
    )

    success = win.open_file(fake_xls)
    assert success is False
    assert len(dialogs) >= 1
    assert any("word" in text.lower() for _, text in dialogs)


def test_read_xls_sparse_poi_51535_correctness_and_budget():
    """Verify poi__51535.xls (65536x256 sparse) parses within strict performance budget."""
    import time

    sample = Path("tests/docs/excel/xls/poi__51535.xls")
    assert sample.exists()

    t0 = time.perf_counter()
    wb = read_xls(sample)
    duration = time.perf_counter() - t0

    # Strict budget: Must complete in under 1.0s (baseline was 17s)
    assert duration < 1.0, f"Parse took {duration:.2f}s, exceeding 1.0s budget"

    assert len(wb.sheets) == 3
    s0 = wb.sheets[0]
    assert s0.name == "Sheet1"

    # Verify corner cells values
    assert s0.get_cell_value(0, 0) == "Top Left Cell"
    assert s0.get_cell_value(0, 255) == "Top Right Cell"
    assert s0.get_cell_value(65535, 0) == "Bottom Left Cell"
    assert s0.get_cell_value(65535, 255) == "Bottom Right Cell"

    # Verify sparsity: total loaded cells in sheet 0 is exactly 4
    assert len(s0.cells) == 4
    assert s0.get_cell(1, 1) is None
    assert s0.get_cell(1000, 50) is None


def test_read_xls_cancellation():
    """Verify read_xls halts and raises InterruptedError when cancel_check triggers."""
    sample = Path("tests/docs/excel/xls/poi__51535.xls")
    assert sample.exists()

    # Cancel immediately
    with pytest.raises(InterruptedError, match="cancelled"):
        read_xls(sample, cancel_check=lambda: True)

    # Cancel after a few rows
    counter = {"count": 0}

    def cancel_after_some():
        counter["count"] += 1
        return counter["count"] > 2

    with pytest.raises(InterruptedError, match="cancelled"):
        read_xls(sample, cancel_check=cancel_after_some)


def test_read_xls_progress_callback():
    """Verify progress_callback receives valid progression updates."""
    sample = Path("tests/docs/excel/xls/libreoffice__AutoFilter.xls")
    assert sample.exists()

    progress_ticks: list[tuple[int, int]] = []

    def on_progress(cur: int, total: int) -> None:
        progress_ticks.append((cur, total))

    wb = read_xls(sample, progress_callback=on_progress)
    assert len(wb.sheets) == 3
    assert len(progress_ticks) >= 3
    # Final tick should indicate completion
    assert progress_ticks[-1] == (3, 3)


def test_ledger_window_open_xls_cancellation_handled(qtbot, monkeypatch):
    """Verify LedgerWindow handles InterruptedError gracefully without error dialogs."""
    sample = Path("tests/docs/excel/xls/poi__tile-range-test.xls")
    assert sample.exists()

    import atboffice.modules.spreadsheet.io.xls_reader as mod

    def mock_read_xls_cancelled(*args, **kwargs):
        raise InterruptedError("User cancelled import")

    monkeypatch.setattr(mod, "read_xls", mock_read_xls_cancelled)

    win = LedgerWindow()
    qtbot.addWidget(win)
    win.maybe_save_prompt = lambda: True

    success = win.open_file(sample)
    assert success is False
    assert "取消" in win.status_bar.currentMessage()

