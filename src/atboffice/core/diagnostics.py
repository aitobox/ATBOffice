"""Crash diagnostics, environmental telemetry, and fault reporting."""

from __future__ import annotations

import collections
import faulthandler
import hashlib
import logging
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
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

_CAPTURED_EXCEPTIONS: list[tuple[type[BaseException], BaseException, Any]] = []


def get_captured_exceptions() -> list[BaseException]:
    """Return all uncaught exceptions captured by the diagnostics handler."""
    return [exc[1] for exc in _CAPTURED_EXCEPTIONS]


def clear_captured_exceptions() -> None:
    """Clear list of captured exceptions."""
    _CAPTURED_EXCEPTIONS.clear()


class ActionRecorder:
    """Thread-safe circular recorder tracking recent user actions and command breadcrumbs."""

    _instance: ActionRecorder | None = None
    _class_lock = threading.Lock()

    def __init__(self, max_actions: int = 50) -> None:
        self.max_actions = max_actions
        self._actions: collections.deque[dict[str, Any]] = collections.deque(maxlen=max_actions)
        self._lock = threading.Lock()
        self._document_shas: dict[str, str] = {}

    @classmethod
    def get_instance(cls) -> ActionRecorder:
        """Return singleton ActionRecorder instance."""
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton ActionRecorder instance."""
        with cls._class_lock:
            cls._instance = None

    def record_action(
        self, action: str, component: str = "", details: dict[str, Any] | None = None
    ) -> None:
        """Record an action event with ISO timestamp and optional details."""
        with self._lock:
            self._actions.append({
                "time": datetime.now().isoformat(),
                "action": action,
                "component": component,
                "details": details or {},
            })

    def get_recent_actions(self) -> list[dict[str, Any]]:
        """Return a copy of recent recorded actions in chronological order."""
        with self._lock:
            return list(self._actions)

    def record_document_sha(
        self, doc_path_or_bytes: str | Path | bytes, label: str = "active_document"
    ) -> str:
        """Compute and store SHA-256 for a document to aid debugging without leaking content."""
        sha = ""
        if isinstance(doc_path_or_bytes, bytes):
            sha = hashlib.sha256(doc_path_or_bytes).hexdigest()
        else:
            p = Path(doc_path_or_bytes)
            if p.exists() and p.is_file():
                try:
                    content = p.read_bytes()
                    sha = hashlib.sha256(content).hexdigest()
                except Exception:
                    sha = f"unavailable_read_error:{p.name}"
            else:
                sha = f"not_found:{p.name}"

        with self._lock:
            self._document_shas[label] = sha
        return sha

    def get_document_shas(self) -> dict[str, str]:
        """Return registered document SHA hashes."""
        with self._lock:
            return dict(self._document_shas)

    def format_breadcrumb_summary(self) -> str:
        """Format recent actions and document SHAs into a sanitized text summary."""
        lines = []
        with self._lock:
            if self._document_shas:
                lines.append("Document SHA Hashes:")
                for lbl, sha in self._document_shas.items():
                    lines.append(f"  {lbl}: {sha}")
            lines.append("Recent Action Sequence:")
            if not self._actions:
                lines.append("  (none recorded)")
            for entry in self._actions:
                det = f" {entry['details']}" if entry["details"] else ""
                lines.append(f"  [{entry['time']}] {entry['component']} -> {entry['action']}{det}")
        return "\n".join(lines)


def record_action(
    action: str, component: str = "", details: dict[str, Any] | None = None
) -> None:
    """Convenience helper to record an action on the singleton ActionRecorder."""
    ActionRecorder.get_instance().record_action(action, component=component, details=details)


def record_document_sha(
    doc_path_or_bytes: str | Path | bytes, label: str = "active_document"
) -> str:
    """Convenience helper to register a document SHA hash."""
    return ActionRecorder.get_instance().record_document_sha(doc_path_or_bytes, label=label)


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
        """Log uncaught exception with sanitized traceback, telemetry, and action breadcrumbs."""
        _CAPTURED_EXCEPTIONS.append((exc_type, exc_value, exc_traceback))

        raw_tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        sanitized_tb = sanitize_traceback(raw_tb)
        telemetry = get_environment_telemetry()
        breadcrumbs = ActionRecorder.get_instance().format_breadcrumb_summary()

        report = [
            f"=== ATBOffice Crash Diagnostic Report ({datetime.now().isoformat()}) ===",
            "Environment Telemetry:",
            *(f"  {k}: {v}" for k, v in telemetry.items()),
            "\n" + breadcrumbs,
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


_DEFAULT_CRASH_HANDLER: CrashDiagnostics | None = None


def install_default_crash_handler(log_dir: Path | str | None = None) -> CrashDiagnostics:
    """Install default background crash handler logging to user config directory or given path."""
    global _DEFAULT_CRASH_HANDLER
    if _DEFAULT_CRASH_HANDLER is not None and _DEFAULT_CRASH_HANDLER._enabled:
        return _DEFAULT_CRASH_HANDLER

    if log_dir is None:
        crash_dir = Path.home() / ".atboffice" / "logs"
    else:
        crash_dir = Path(log_dir)

    try:
        crash_dir.mkdir(parents=True, exist_ok=True)
        log_file = crash_dir / "crash.log"
    except Exception:
        log_file = Path(tempfile.gettempdir()) / "atboffice_crash.log"

    _DEFAULT_CRASH_HANDLER = CrashDiagnostics(log_file)
    _DEFAULT_CRASH_HANDLER.enable()
    return _DEFAULT_CRASH_HANDLER


_DRAINING_EVENT_LOOP: bool = False


def drain_event_loop(max_iterations: int = 5) -> None:
    """Drain pending Qt events and deferred deletions during window closing or shutdown.

    Protected with a re-entrancy guard to prevent recursive event loop spinning
    when called during closeEvent, deferred deletions, or rapid lifecycle transitions.
    """
    global _DRAINING_EVENT_LOOP
    if _DRAINING_EVENT_LOOP:
        return

    app = QCoreApplication.instance()
    if app is None:
        return

    _DRAINING_EVENT_LOOP = True
    try:
        for _ in range(max(1, max_iterations)):
            app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    finally:
        _DRAINING_EVENT_LOOP = False
