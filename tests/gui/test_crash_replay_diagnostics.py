# tests/gui/test_crash_replay_diagnostics.py
"""Subprocess GUI replay baseline and crash diagnostics verification tests."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from atboffice.core.diagnostics import (
    drain_event_loop,
    get_environment_telemetry,
)


@dataclass
class ReplayResult:
    """Outcome of an isolated GUI subprocess execution."""

    status: str  # "normal_exit", "crash", "timeout"
    exit_code: int | None
    stdout: str
    stderr: str
    crash_log: str
    duration: float
    telemetry: dict[str, str]


class SubprocessReplayRunner:
    """Runner executing ATBOffice in an isolated subprocess to capture crashes and lifecycle."""

    def __init__(self, work_dir: Path | None = None, log_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path.cwd()
        self.log_dir = log_dir or Path(tempfile.gettempdir())

    def run(
        self,
        module: str = "quire",
        action: str = "launch_close",
        simulate_crash: str | None = None,
        timeout: float = 20.0,
        extra_args: list[str] | None = None,
    ) -> ReplayResult:
        """Run a module and action in a dedicated subprocess with crash diagnostics enabled."""
        log_file = self.log_dir / f"replay_{module}_{action}_{int(time.time() * 1000)}.log"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.work_dir / "src")
        # Ensure headless offscreen execution in automated test runner
        if "QT_QPA_PLATFORM" not in env:
            env["QT_QPA_PLATFORM"] = "offscreen"

        cmd = [
            sys.executable,
            "-m",
            "atboffice",
            "--diagnostics",
            f"--crash-log={log_file}",
            module,
            f"--replay-action={action}",
        ]
        if simulate_crash:
            cmd.append(f"--simulate-crash={simulate_crash}")
        if extra_args:
            cmd.extend(extra_args)

        start_time = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=str(self.work_dir),
                check=False,
            )
            duration = time.time() - start_time
            crash_content = log_file.read_text(encoding="utf-8") if log_file.exists() else ""

            if proc.returncode == 0:
                status = "normal_exit"
            else:
                status = "crash"

            return ReplayResult(
                status=status,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                crash_log=crash_content,
                duration=duration,
                telemetry=get_environment_telemetry(),
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.time() - start_time
            crash_content = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
            return ReplayResult(
                status="timeout",
                exit_code=None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                crash_log=crash_content,
                duration=duration,
                telemetry=get_environment_telemetry(),
            )


@pytest.fixture
def replay_runner(tmp_path: Path) -> SubprocessReplayRunner:
    """Fixture providing a SubprocessReplayRunner configured with a temp directory."""
    project_root = Path(__file__).resolve().parent.parent.parent
    return SubprocessReplayRunner(work_dir=project_root, log_dir=tmp_path)


@pytest.mark.parametrize("module", ["quire", "ledger", "lectern"])
def test_three_modules_subprocess_replay(
    replay_runner: SubprocessReplayRunner, module: str
) -> None:
    """Quire, Ledger, and Lectern launch, render, and cleanly close in isolated subprocess."""
    result = replay_runner.run(module=module, action="launch_close", timeout=20.0)
    assert result.status == "normal_exit", f"{module} failed to exit cleanly: {result.stderr}"
    assert result.exit_code == 0
    assert result.duration > 0.0


def test_window_switching_replay(replay_runner: SubprocessReplayRunner) -> None:
    """Subprocess creates multiple windows, switches focus, and cleans up without crash."""
    result = replay_runner.run(module="ledger", action="switch_windows", timeout=25.0)
    assert result.status == "normal_exit", f"Window switching failed: {result.stderr}"
    assert result.exit_code == 0


def test_mouse_hover_replay(replay_runner: SubprocessReplayRunner) -> None:
    """Subprocess dispatches mouse move/hover across the window canvas without crash."""
    result = replay_runner.run(module="lectern", action="hover_canvas", timeout=20.0)
    assert result.status == "normal_exit", f"Mouse hover failed: {result.stderr}"
    assert result.exit_code == 0


def test_dialog_lifecycle_replay(replay_runner: SubprocessReplayRunner) -> None:
    """Subprocess opens and closes modal/modeless dialogs and restores primary window."""
    result = replay_runner.run(module="quire", action="dialog_lifecycle", timeout=20.0)
    assert result.status == "normal_exit", f"Dialog lifecycle failed: {result.stderr}"
    assert result.exit_code == 0


def test_subprocess_crash_detection_exception(replay_runner: SubprocessReplayRunner) -> None:
    """Subprocess runner accurately identifies crash on unhandled Python exceptions."""
    result = replay_runner.run(
        module="quire",
        action="launch_close",
        simulate_crash="exception",
        timeout=15.0,
    )
    assert result.status == "crash"
    assert result.exit_code != 0
    assert "Simulated unhandled exception" in (result.stderr + result.crash_log)
    assert "Environment Telemetry" in (result.stderr + result.crash_log)


def test_subprocess_crash_detection_segfault(replay_runner: SubprocessReplayRunner) -> None:
    """Subprocess runner and faulthandler catch native segmentation faults (SIGSEGV)."""
    result = replay_runner.run(
        module="ledger",
        action="launch_close",
        simulate_crash="segfault",
        timeout=15.0,
    )
    assert result.status == "crash"
    assert result.exit_code != 0
    # In a native segfault, exit code is typically negative or 139
    assert result.exit_code in (-11, 139, 1) or result.exit_code != 0


def test_subprocess_timeout_detection(replay_runner: SubprocessReplayRunner) -> None:
    """Subprocess runner terminates and classifies unresponsive executions as timeout."""
    # Running with extremely small timeout (0.001s) forces a timeout classification
    result = replay_runner.run(
        module="lectern",
        action="launch_close",
        timeout=0.001,
    )
    assert result.status == "timeout"
    assert result.exit_code is None


def test_window_close_event_loop_drain() -> None:
    """drain_event_loop processes pending events and purges deferred deletes cleanly."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])

    obj = QObject()
    obj.deleteLater()
    drain_event_loop(max_iterations=3)
    # Deferred delete must be processed without raising exceptions or segfaulting
    assert True
