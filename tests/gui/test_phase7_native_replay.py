# tests/gui/test_phase7_native_replay.py
"""Phase 7 isolated native/offscreen GUI replay, object lifecycle, and crash diagnostics tests.

Verifies:
1. Replay opening another file/window while editing without corruption or crash.
2. Replay view mode switching and sheet switching during active selection.
3. Replay modal dialog and context menu lifecycle with clean dismissal and no reentrancy.
4. Replay drag gesture cancellation and window closure without dangling timers or state leaks.
5. In-process ActionRecorder and document SHA tracking with sanitized breadcrumbs.
6. 100-cycle mixed interaction stress replay.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from atboffice.core.diagnostics import (
    ActionRecorder,
    clear_captured_exceptions,
    drain_event_loop,
    get_captured_exceptions,
    record_action,
    record_document_sha,
)
from tests.gui.test_crash_replay_diagnostics import SubprocessReplayRunner


@pytest.fixture
def replay_runner(tmp_path: Path) -> SubprocessReplayRunner:
    """Fixture providing a SubprocessReplayRunner configured with a temp log directory."""
    project_root = Path(__file__).resolve().parent.parent.parent
    return SubprocessReplayRunner(work_dir=project_root, log_dir=tmp_path)


def test_open_during_edit_replay(replay_runner: SubprocessReplayRunner) -> None:
    """Subprocess modifies an active document, opens a second document, and cleans up cleanly."""
    result = replay_runner.run(
        module="ledger",
        action="open_during_edit",
        timeout=25.0,
    )
    assert result.status == "normal_exit", f"Open during edit replay failed: {result.stderr}"
    assert result.exit_code == 0
    assert result.duration > 0.0


def test_view_mode_switching_replay(replay_runner: SubprocessReplayRunner) -> None:
    """Subprocess toggles view modes (normal / page_break) and sheets during active selection."""
    result = replay_runner.run(
        module="ledger",
        action="switch_views",
        timeout=20.0,
    )
    assert result.status == "normal_exit", f"View mode switching replay failed: {result.stderr}"
    assert result.exit_code == 0


def test_modal_menu_dialog_replay(replay_runner: SubprocessReplayRunner) -> None:
    """Subprocess opens and dismisses modal dialogs and popup menus without reentrancy crash."""
    result = replay_runner.run(
        module="quire",
        action="modal_menu_dialog",
        timeout=20.0,
    )
    assert result.status == "normal_exit", f"Modal menu dialog replay failed: {result.stderr}"
    assert result.exit_code == 0


def test_drag_cancel_and_window_close_replay(replay_runner: SubprocessReplayRunner) -> None:
    """Subprocess begins cell drag gesture, cancels via API, and closes window without dangling timers."""
    result = replay_runner.run(
        module="ledger",
        action="drag_cancel_lifecycle",
        timeout=20.0,
    )
    assert result.status == "normal_exit", f"Drag cancel replay failed: {result.stderr}"
    assert result.exit_code == 0


def test_action_recorder_and_document_sha_diagnostics(tmp_path: Path) -> None:
    """ActionRecorder records chronological action sequences and computes sanitized document SHA."""
    ActionRecorder.reset_instance()
    recorder = ActionRecorder.get_instance()

    # 1. Verify action sequence recording
    record_action("init_view", "grid_viewport", {"rows": 100, "cols": 26})
    record_action("start_drag", "grid_viewport", {"zone": "cell", "r": 0, "c": 0})
    record_action("cancel_drag", "grid_viewport", {"why": "api"})

    actions = recorder.get_recent_actions()
    assert len(actions) == 3
    assert actions[0]["action"] == "init_view"
    assert actions[1]["action"] == "start_drag"
    assert actions[2]["action"] == "cancel_drag"
    assert actions[2]["details"]["why"] == "api"

    # 2. Verify document SHA recording
    import hashlib

    sample_doc = tmp_path / "sample.docx"
    doc_bytes = b"PK\x03\x04test_docx_content_data_12345"
    sample_doc.write_bytes(doc_bytes)
    sha = record_document_sha(sample_doc, label="test_doc")
    assert len(sha) == 64
    assert sha == hashlib.sha256(doc_bytes).hexdigest()

    # 3. Verify breadcrumb summary formatting
    summary = recorder.format_breadcrumb_summary()
    assert "Document SHA Hashes:" in summary
    assert "test_doc:" in summary
    assert "Recent Action Sequence:" in summary
    assert "grid_viewport -> start_drag" in summary


def test_100_cycle_mixed_stress_replay(replay_runner: SubprocessReplayRunner) -> None:
    """Subprocess executes 100 mixed interaction cycles with zero crashes or leaks."""
    result = replay_runner.run(
        module="ledger",
        action="stress_interaction",
        extra_args=["--replay-iterations=100"],
        timeout=35.0,
    )
    assert result.status == "normal_exit", f"100-cycle mixed replay failed: {result.stderr}"
    assert result.exit_code == 0
    assert result.duration > 0.0


def test_captured_exception_registry(tmp_path: Path) -> None:
    """Diagnostic exception capture registry tracks unhandled exceptions cleanly."""
    clear_captured_exceptions()
    assert len(get_captured_exceptions()) == 0

    from atboffice.core.diagnostics import CrashDiagnostics

    test_log = tmp_path / "test_crash.log"
    diag = CrashDiagnostics(test_log)
    diag._handle_uncaught_exception(RuntimeError, RuntimeError("Test slot failure"), None)

    captured = get_captured_exceptions()
    assert len(captured) == 1
    assert str(captured[0]) == "Test slot failure"
    clear_captured_exceptions()
    assert len(get_captured_exceptions()) == 0
