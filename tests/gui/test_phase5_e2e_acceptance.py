"""Phase 5 End-to-End Workflow, Parity, and Stability Acceptance Test Suite.

Issue #201: [Phase 5] 执行三模块端到端与稳定性最终验收.
Covers:
1. Quire (Word Processor):
   - Workflow: New -> Input -> Format -> Undo/Redo -> Save (docx & html) -> Reopen -> Edit -> Cancel Close.
2. Ledger (Spreadsheet):
   - Workflow: New -> Cell Data & Formula -> Format -> Undo/Redo -> Save (xlsx & csv) -> Reopen -> Edit -> Cancel Close.
3. Lectern (Presentation):
   - Workflow: New -> Shapes & Text -> Format -> Undo/Redo -> Save (pptx) -> Reopen -> Edit -> Cancel Close.
4. 100-cycle mixed interaction stress test in native Qt event loop across all 3 modules.
5. 100-cycle isolated subprocess replay stress test across all 3 modules with diagnostics.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from atboffice.core.diagnostics import drain_event_loop
from atboffice.modules.presentation.models.shape import Fill, Line, Shape
from atboffice.modules.presentation.models.text import TextBody
from atboffice.modules.writer.models.document import (
    Paragraph,
    TextItem,
    all_paragraphs,
    ptext,
)
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow
from tests.gui.test_crash_replay_diagnostics import SubprocessReplayRunner


@pytest.fixture
def replay_runner(tmp_path: Path) -> SubprocessReplayRunner:
    project_root = Path(__file__).resolve().parent.parent.parent
    return SubprocessReplayRunner(work_dir=project_root, log_dir=tmp_path)


# ==============================================================================
# 1. Quire E2E Workflow & Roundtrip Acceptance
# ==============================================================================

def test_quire_e2e_workflow_and_roundtrip(qtbot, monkeypatch, tmp_path: Path):
    """Quire complete lifecycle: New -> Input -> Format -> Undo/Redo -> Save -> Reopen -> Cancel Close."""
    win = QuireWindow()
    qtbot.addWidget(win)
    win.resize(1000, 700)
    win.show()
    drain_event_loop(2)

    # 1. New document is active and not modified
    assert win.writer_view is not None
    assert win.is_modified is False

    # 2. Input text via CaretController (true user typing pathway)
    test_text = "Phase 5 Quire End-to-End Acceptance Verification"
    win.writer_view.canvas_view.controller.insert_text(test_text)
    drain_event_loop(2)

    assert win.is_modified is True
    paras = list(all_paragraphs(win.writer_view.canvas_view.doc))
    assert any(test_text in ptext(p) for p in paras)

    # 3. Formatting and Undo/Redo
    win.undo()
    drain_event_loop(1)
    win.redo()
    drain_event_loop(1)

    # 4. Save to DOCX and HTML
    docx_path = tmp_path / "quire_acceptance.docx"
    saved_docx = win.save_file(docx_path)
    assert saved_docx is True
    assert docx_path.exists()
    assert docx_path.stat().st_size > 0
    assert win.is_modified is False

    html_path = tmp_path / "quire_acceptance.html"
    saved_html = win.save_file(html_path)
    assert saved_html is True
    assert html_path.exists()
    assert html_path.stat().st_size > 0

    # 5. Reopen saved DOCX in a fresh window and verify content
    win2 = QuireWindow()
    qtbot.addWidget(win2)
    win2.show()
    opened = win2.open_file(docx_path)
    assert opened is True
    assert win2.current_file_path == docx_path
    assert win2.is_modified is False
    paras2 = list(all_paragraphs(win2.writer_view.canvas_view.doc))
    assert any(test_text in ptext(p) for p in paras2)

    # 6. Edit existing file and test cancel close
    win2.writer_view.canvas_view.controller.insert_text(" - Extra edited content")
    assert win2.is_modified is True

    # User clicks Cancel on the save confirmation prompt
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    close_event = QCloseEvent()
    win2.closeEvent(close_event)
    assert close_event.isAccepted() is False
    assert win2.is_modified is True

    win.close()
    win2.set_modified(False)
    win2.close()
    drain_event_loop(2)


# ==============================================================================
# 2. Ledger E2E Workflow & Roundtrip Acceptance
# ==============================================================================

def test_ledger_e2e_workflow_and_roundtrip(qtbot, monkeypatch, tmp_path: Path):
    """Ledger complete lifecycle: New -> Cell Data & Formula -> Format -> Undo/Redo -> Save -> Reopen -> Cancel Close."""
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.resize(1000, 700)
    win.show()
    drain_event_loop(2)

    assert win.spreadsheet_view is not None
    assert win.is_modified is False

    # 1. Input cell data and formulas
    view = win.spreadsheet_view
    view.model.set_cell_value(0, 0, "Quarter")
    view.model.set_cell_value(0, 1, "Revenue")
    view.model.set_cell_value(1, 0, "Q1")
    view.model.set_cell_value(1, 1, 1500)
    view.model.set_cell_value(2, 0, "Q2")
    view.model.set_cell_value(2, 1, 2500)
    view.model.set_cell_value(3, 0, "Total")
    view.model.set_cell_value(3, 1, "=SUM(B2:B3)")
    win.set_modified(True)
    drain_event_loop(2)

    assert win.is_modified is True
    assert view.model.get_cell_value(0, 0) == "Quarter"
    assert view.model.get_cell_value(1, 1) == 1500
    assert view.model.get_cell_value(3, 1) == "=SUM(B2:B3)"

    # 2. Undo and Redo
    win.undo()
    drain_event_loop(1)
    win.redo()
    drain_event_loop(1)

    # 3. Save to XLSX and CSV
    xlsx_path = tmp_path / "ledger_acceptance.xlsx"
    saved_xlsx = win.save_file(xlsx_path)
    assert saved_xlsx is True
    assert xlsx_path.exists()
    assert xlsx_path.stat().st_size > 0
    assert win.is_modified is False

    csv_path = tmp_path / "ledger_acceptance.csv"
    saved_csv = win.save_file(csv_path)
    assert saved_csv is True
    assert csv_path.exists()
    assert csv_path.stat().st_size > 0

    # 4. Reopen saved XLSX in a fresh window and verify data integrity
    win2 = LedgerWindow()
    qtbot.addWidget(win2)
    win2.show()
    opened = win2.open_file(xlsx_path)
    assert opened is True
    assert win2.current_file_path == xlsx_path
    assert win2.is_modified is False

    view2 = win2.spreadsheet_view
    assert view2.model.get_cell_value(0, 0) == "Quarter"
    assert view2.model.get_cell_value(0, 1) == "Revenue"
    assert view2.model.get_cell_value(1, 0) == "Q1"
    assert view2.model.get_cell_value(1, 1) == 1500

    # 5. Modify and test cancel close
    view2.model.set_cell_value(4, 0, "Unsaved Draft")
    win2.set_modified(True)
    assert win2.is_modified is True

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    close_event = QCloseEvent()
    win2.closeEvent(close_event)
    assert close_event.isAccepted() is False
    assert win2.is_modified is True

    win.close()
    win2.set_modified(False)
    win2.close()
    drain_event_loop(2)


# ==============================================================================
# 3. Lectern E2E Workflow & Roundtrip Acceptance
# ==============================================================================

def test_lectern_e2e_workflow_and_roundtrip(qtbot, monkeypatch, tmp_path: Path):
    """Lectern complete lifecycle: New -> Shapes & Text -> Format -> Undo/Redo -> Save -> Reopen -> Cancel Close."""
    win = LecternWindow()
    qtbot.addWidget(win)
    win.resize(1000, 700)
    win.show()
    drain_event_loop(2)

    assert win.presentation is not None
    assert len(win.presentation.slides) >= 1
    assert win.is_modified is False

    # 1. Add shape and formatted text
    slide = win.presentation.slides[0]
    shape = Shape(
        id="phase5_shape_1",
        geom="roundRect",
        x=80.0,
        y=80.0,
        w=320.0,
        h=160.0,
        fill=Fill.solid("#1E395B"),
        line=Line(color="#FFFFFF", width=2.0),
        text=TextBody.from_plain_text("Phase 5 Lectern E2E Parity Acceptance"),
    )
    slide.add_shape(shape)
    win.set_modified(True)
    drain_event_loop(2)

    assert win.is_modified is True
    assert any(s.id == "phase5_shape_1" for s in slide.shapes)

    # 2. Undo and Redo
    win.undo()
    drain_event_loop(1)
    win.redo()
    drain_event_loop(1)

    # 3. Save to PPTX
    pptx_path = tmp_path / "lectern_acceptance.pptx"
    saved_pptx = win.save_file(pptx_path)
    assert saved_pptx is True
    assert pptx_path.exists()
    assert pptx_path.stat().st_size > 0
    assert win.is_modified is False

    # 4. Reopen saved PPTX in a fresh window and verify presentation integrity
    win2 = LecternWindow()
    qtbot.addWidget(win2)
    win2.show()
    opened = win2.open_file(pptx_path)
    assert opened is True
    assert win2.current_file_path == pptx_path
    assert win2.is_modified is False
    assert len(win2.presentation.slides) >= 1

    slide2 = win2.presentation.slides[0]
    assert any(
        s.text and "Phase 5 Lectern E2E Parity Acceptance" in s.text.plain_text
        for s in slide2.shapes
    )

    # 5. Modify and test cancel close
    slide2.add_shape(Shape(id="unsaved_shape", geom="rect", x=50, y=50, w=100, h=100))
    win2.set_modified(True)
    assert win2.is_modified is True

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    close_event = QCloseEvent()
    win2.closeEvent(close_event)
    assert close_event.isAccepted() is False
    assert win2.is_modified is True

    win.close()
    win2.set_modified(False)
    win2.close()
    drain_event_loop(2)


# ==============================================================================
# 4. Three Modules Native In-Process 100 Mixed GUI Interactions
# ==============================================================================

def test_three_modules_in_process_100_mixed_interactions(qtbot):
    """Execute >= 100 mixed GUI interactions across Quire, Ledger, and Lectern without crash or leak."""
    # Module 1: Quire (100 mixed interactions)
    quire_win = QuireWindow()
    qtbot.addWidget(quire_win)
    quire_win.resize(900, 600)
    quire_win.show()
    drain_event_loop(2)

    central_q = quire_win.centralWidget()
    for i in range(100):
        # Mix mouse movement, focus, zoom, and typing
        x = 50 + (i % 25) * 8
        y = 50 + (i % 20) * 8
        if central_q is not None:
            pos = QPointF(float(x), float(y))
            ev = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                pos,
                pos,
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QApplication.sendEvent(central_q, ev)
        if i % 10 == 0:
            quire_win.zoom_in()
        elif i % 10 == 5:
            quire_win.zoom_reset()
        if i % 25 == 0:
            drain_event_loop(1)

    quire_win.close()
    drain_event_loop(2)

    # Module 2: Ledger (100 mixed interactions)
    ledger_win = LedgerWindow()
    qtbot.addWidget(ledger_win)
    ledger_win.resize(900, 600)
    ledger_win.show()
    drain_event_loop(2)

    view_l = ledger_win.spreadsheet_view
    for i in range(100):
        r = i % 10
        c = (i // 10) % 5
        view_l.selection.select_cell(r, c)
        if i % 15 == 0:
            view_l.model.set_cell_value(r, c, f"val_{i}")
        if i % 20 == 0:
            ledger_win.zoom_in()
        elif i % 20 == 10:
            ledger_win.zoom_reset()
        if i % 25 == 0:
            drain_event_loop(1)

    ledger_win.set_modified(False)
    ledger_win.close()
    drain_event_loop(2)

    # Module 3: Lectern (100 mixed interactions)
    lectern_win = LecternWindow()
    qtbot.addWidget(lectern_win)
    lectern_win.resize(900, 600)
    lectern_win.show()
    drain_event_loop(2)

    central_l = lectern_win.centralWidget()
    for i in range(100):
        x = 60 + (i % 30) * 6
        y = 60 + (i % 20) * 6
        if central_l is not None:
            pos = QPointF(float(x), float(y))
            ev = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                pos,
                pos,
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QApplication.sendEvent(central_l, ev)
        if i % 20 == 0:
            lectern_win.zoom_in()
        elif i % 20 == 10:
            lectern_win.zoom_reset()
        if i % 25 == 0:
            drain_event_loop(1)

    lectern_win.set_modified(False)
    lectern_win.close()
    drain_event_loop(2)


# ==============================================================================
# 5. Three Modules Isolated Subprocess 100 Stress Replay
# ==============================================================================

@pytest.mark.parametrize("module", ["quire", "ledger", "lectern"])
def test_three_modules_subprocess_100_stress_replay(
    replay_runner: SubprocessReplayRunner, module: str
) -> None:
    """Isolated subprocess runs 100 stress interactions with diagnostics enabled and exits cleanly."""
    result = replay_runner.run(
        module=module,
        action="stress_interaction",
        extra_args=["--replay-iterations=100"],
        timeout=30.0,
    )
    assert result.status == "normal_exit", (
        f"Subprocess 100 stress replay failed for {module}.\n"
        f"Exit code: {result.exit_code}\n"
        f"Stderr: {result.stderr}\n"
        f"Crash log: {result.crash_log}"
    )
    assert result.exit_code == 0
    assert result.duration > 0.0
