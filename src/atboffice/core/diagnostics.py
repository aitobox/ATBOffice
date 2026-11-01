"""Crash diagnostics, environmental telemetry, and fault reporting."""

from __future__ import annotations

import faulthandler
import logging
import os
import platform
import re
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6 import QtCore
from PySide6.QtCore import QCoreApplication, QEvent

logger = logging.getLogger(__name__)

# Fallback known commit hashes
ORIG_REPO_SHA_FALLBACK = "32ff53a5da0e75ebac11acdb0251cd3d8c7bf408"
CLONE_REPO_SHA_FALLBACK = "38664cabd0dcb88dabec91855eb0357dc30f0cdd"


def _get_git_commit(repo_dir: Path | str, fallback: str = "") -> str:
    """Safely obtain git commit hash for a repository directory."""
    path = Path(repo_dir)
    if not (path / ".git").exists():
        return fallback
    try:
        res = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return fallback


def _get_platform_crash_dir() -> Path:
    """Return platform-specific crash report directory."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Logs" / "DiagnosticReports"
    elif system == "Linux":
        return Path("/var/crash")
    elif system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "CrashDumps"
        return Path.home() / "AppData" / "Local" / "CrashDumps"
    return Path.home()


def get_environment_telemetry() -> dict[str, str]:
    """Collect runtime environment metadata and version signatures."""
    import PySide6

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    orig_root = project_root / ".vibeoffice"

    clone_sha = _get_git_commit(project_root, CLONE_REPO_SHA_FALLBACK)
    orig_sha = _get_git_commit(orig_root, ORIG_REPO_SHA_FALLBACK)

    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "pyside_version": getattr(PySide6, "__version__", "unknown"),
        "qt_version": QtCore.qVersion(),
        "clone_sha": clone_sha,
        "orig_sha": orig_sha,
        "crash_report_dir": str(_get_platform_crash_dir()),
    }


def sanitize_traceback(tb_str: str) -> str:
    """Sanitize traceback text to prevent document contents from leaking.

    Keeps file paths, line numbers, function names, and exception types, while
    scrubbing string payloads and value dumps.
    """
    lines = tb_str.splitlines()
    sanitized_lines = []

    for line in lines:
        # Standard traceback line format: File "...", line X, in Y
        if line.strip().startswith("File ") and ", line " in line and ", in " in line:
            sanitized_lines.append(line)
            continue

        if line.strip().startswith("Traceback (most recent call last):"):
            sanitized_lines.append(line)
            continue

        # Redact double/single-quoted strings longer than 10 characters in code snippets
        line_clean = re.sub(r'("[^"\\]{10,}")|(\'[^\'\\]{10,}\')', '"[REDACTED_CONTENT]"', line)

        # Redact payload text following exception colon
        # e.g., ValueError: Sensitive document text -> ValueError: [REDACTED_PAYLOAD]
        exc_match = re.match(r"^(\s*[a-zA-Z0-9_]+Error|\s*Exception):\s*(.*)$", line_clean)
        if exc_match:
            exc_type = exc_match.group(1)
            msg = exc_match.group(2)
            # If msg contains specific strings, scrub them
            if any(term in msg for term in ("CONFIDENTIAL", "payload", "Document", "secret")):
                line_clean = f"{exc_type}: [REDACTED_PAYLOAD]"

        sanitized_lines.append(line_clean)

    return "\n".join(sanitized_lines)


class CrashDiagnostics:
    """Crash diagnostics manager configuring faulthandler and uncaught exception capture."""

    def __init__(self, log_path: Path | str | None = None) -> None:
        self.log_path = Path(log_path) if log_path else Path("crash.log")
        self._original_excepthook = sys.excepthook
        self._faulthandler_file: Any = None
        self._enabled = False

    def enable(self) -> None:
        """Enable faulthandler and install custom excepthook."""
        if self._enabled:
            return

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._faulthandler_file = open(self.log_path, "a", encoding="utf-8")  # noqa: SIM115
            faulthandler.enable(file=self._faulthandler_file, all_threads=True)
        except Exception as exc:
            logger.warning("Could not enable faulthandler with file %s: %s", self.log_path, exc)
            faulthandler.enable()

        self._original_excepthook = sys.excepthook
        sys.excepthook = self._handle_uncaught_exception
        self._enabled = True

    def disable(self) -> None:
        """Disable faulthandler and restore original excepthook."""
        if not self._enabled:
            return

        try:
            faulthandler.disable()
        except Exception:
            pass

        if self._faulthandler_file is not None:
            try:
                self._faulthandler_file.close()
            except Exception:
                pass
            self._faulthandler_file = None

        sys.excepthook = self._original_excepthook
        self._enabled = False

    def _handle_uncaught_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: Any,
    ) -> None:
        """Log uncaught exception with sanitized traceback and environment telemetry."""
        raw_tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        sanitized_tb = sanitize_traceback(raw_tb)
        telemetry = get_environment_telemetry()

        report = [
            f"=== ATBOffice Crash Diagnostic Report ({datetime.now().isoformat()}) ===",
            "Environment Telemetry:",
            *(f"  {k}: {v}" for k, v in telemetry.items()),
            "\nSanitized Traceback:",
            sanitized_tb,
            "==========================================================\n",
        ]
        report_text = "\n".join(report)

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(report_text)
        except Exception as err:
            sys.stderr.write(f"Failed to write crash log: {err}\n")

        sys.stderr.write(report_text)

    def find_recent_crash_reports(self, since_timestamp: float | None = None) -> list[Path]:
        """Locate OS-level crash reports (e.g. .ips / .crash files on macOS)."""
        crash_dir = _get_platform_crash_dir()
        if not crash_dir.exists() or not crash_dir.is_dir():
            return []

        candidates: list[Path] = []
        try:
            for item in crash_dir.iterdir():
                if not item.is_file():
                    continue
                name_lower = item.name.lower()
                if "atboffice" in name_lower or "python" in name_lower:
                    if since_timestamp is None or item.stat().st_mtime >= since_timestamp:
                        candidates.append(item)
        except Exception as exc:
            logger.debug("Failed scanning crash directory %s: %s", crash_dir, exc)

        return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)


def drain_event_loop(max_iterations: int = 5) -> None:
    """Drain pending Qt events and deferred deletions during window closing or shutdown."""
    app = QCoreApplication.instance()
    if app is None:
        return

    for _ in range(max_iterations):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
