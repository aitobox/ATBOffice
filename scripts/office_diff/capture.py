"""PySide6 offscreen document canvas capture with subprocess isolation."""
# ruff: noqa: E402, E501

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Ensure QT offscreen platform is set before any PySide6 import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from .corpus import find_repo_root
from .models import CaptureResult, DocumentTarget

repo_root = find_repo_root(Path(__file__))
if str(repo_root / "src") not in sys.path:
    sys.path.insert(0, str(repo_root / "src"))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from atboffice.core.app import create_application
from atboffice.core.window_manager import WindowManager

LAST_DIALOG_ERROR: str | None = None


def install_dialog_interceptors() -> None:
    """Globally intercept QMessageBox and QDialog modal popups to prevent blocking in headless mode."""
    global LAST_DIALOG_ERROR

    def _mock_critical(parent=None, title="", text="", *args, **kwargs):
        global LAST_DIALOG_ERROR
        LAST_DIALOG_ERROR = f"critical: {title} - {text}"
        return QMessageBox.StandardButton.Ok

    def _mock_warning(parent=None, title="", text="", *args, **kwargs):
        global LAST_DIALOG_ERROR
        LAST_DIALOG_ERROR = f"warning: {title} - {text}"
        return QMessageBox.StandardButton.Ok

    def _mock_info(parent=None, title="", text="", *args, **kwargs):
        return QMessageBox.StandardButton.Ok

    def _mock_question(parent=None, title="", text="", *args, **kwargs):
        return QMessageBox.StandardButton.Yes

    QMessageBox.critical = _mock_critical
    QMessageBox.warning = _mock_warning
    QMessageBox.information = _mock_info
    QMessageBox.question = _mock_question
    QMessageBox.exec = lambda self, *args, **kwargs: QMessageBox.StandardButton.Ok
    QMessageBox.exec_ = lambda self, *args, **kwargs: QMessageBox.StandardButton.Ok

    QDialog.exec = lambda self, *args, **kwargs: QDialog.DialogCode.Accepted
    QDialog.exec_ = lambda self, *args, **kwargs: QDialog.DialogCode.Accepted


def drain_event_loop(iterations: int = 5) -> None:
    """Process pending Qt events to ensure painting and layouts settle."""
    app = QApplication.instance()
    if not app:
        return
    for _ in range(iterations):
        app.processEvents()


def capture_single_document(
    target: DocumentTarget,
    out_dir: Path,
    viewport_size: tuple[int, int] = (1440, 900),
    canvas_only: bool = False,
) -> CaptureResult:
    """Render a single document in PySide6 offscreen mode and save its canvas snapshot."""
    global LAST_DIALOG_ERROR
    LAST_DIALOG_ERROR = None
    install_dialog_interceptors()

    app = QApplication.instance()
    if not app:
        app = create_application(["capture_atboffice", "-platform", "offscreen"])

    target_path = Path(target.path)
    if not target_path.exists():
        return CaptureResult(
            file=target.file,
            app=target.app,
            status="missing_file",
            error=f"File not found: {target_path}",
        )

    app_dir = out_dir / target.app
    app_dir.mkdir(parents=True, exist_ok=True)
    out_png = app_dir / f"{target.file}.png"

    wm = WindowManager.get_instance()
    window = None
    try:
        if target.app == "word":
            window = wm.open_quire(str(target_path))
        elif target.app == "excel":
            window = wm.open_ledger(str(target_path))
        elif target.app == "powerpoint":
            window = wm.open_lectern(str(target_path))
        else:
            window = wm.open_file_auto(str(target_path))

        if not window:
            return CaptureResult(
                file=target.file,
                app=target.app,
                status="failed_to_open",
                error=LAST_DIALOG_ERROR or "WindowManager returned None",
            )

        window.resize(viewport_size[0], viewport_size[1])
        window.show()
        drain_event_loop(10)

        if hasattr(window, "fit_to_window"):
            window.fit_to_window()
            drain_event_loop(5)

        grab_target = None
        if canvas_only:
            if target.app == "powerpoint" and hasattr(window, "presentation_view"):
                ws = getattr(window.presentation_view, "workspace", None)
                if ws and hasattr(ws, "canvas_view") and ws.canvas_view is not None:
                    grab_target = ws.canvas_view.viewport()
            elif target.app == "word" and hasattr(window, "writer_view"):
                cv = getattr(window.writer_view, "canvas_view", None)
                if cv and hasattr(cv, "viewport"):
                    grab_target = cv.viewport()
                else:
                    grab_target = window.writer_view
            elif target.app == "excel" and hasattr(window, "spreadsheet_view"):
                tv = getattr(window.spreadsheet_view, "table_view", None)
                if tv and hasattr(tv, "viewport"):
                    grab_target = tv.viewport()
                else:
                    grab_target = window.spreadsheet_view

        if grab_target is None:
            cw = window.centralWidget()
            grab_target = cw if cw is not None else window

        pixmap = grab_target.grab()

        if pixmap.isNull() or pixmap.width() == 0 or pixmap.height() == 0:
            return CaptureResult(
                file=target.file,
                app=target.app,
                status="empty_render",
                error="Grabbed pixmap is null or zero-sized",
            )

        saved = pixmap.save(str(out_png), "PNG")
        if not saved:
            return CaptureResult(
                file=target.file,
                app=target.app,
                status="save_error",
                error=f"Failed to save PNG to {out_png}",
            )

        return CaptureResult(
            file=target.file,
            app=target.app,
            status="dialog_warning" if LAST_DIALOG_ERROR else "captured",
            screenshot_path=str(out_png),
            width=pixmap.width(),
            height=pixmap.height(),
            dialog_warning=LAST_DIALOG_ERROR,
        )

    except Exception as exc:
        return CaptureResult(
            file=target.file,
            app=target.app,
            status="exception",
            error=str(exc),
        )
    finally:
        if window:
            try:
                window.close()
                drain_event_loop(2)
            except Exception:
                pass


def run_isolated_capture(
    target: DocumentTarget,
    out_dir: Path,
    timeout: int = 30,
    canvas_only: bool = False,
    viewport_size: tuple[int, int] = (1440, 900),
) -> CaptureResult:
    """Execute capture of a single file in an isolated Python subprocess."""
    cmd = [
        sys.executable,
        "-m",
        "scripts.office_diff.capture",
        "--file",
        str(target.path),
        "--app",
        target.app,
        "--out",
        str(out_dir),
        "--width",
        str(viewport_size[0]),
        "--height",
        str(viewport_size[1]),
        "--json-single",
    ]
    if canvas_only:
        cmd.append("--canvas-only")

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root}/src:{repo_root}"
    env["QT_QPA_PLATFORM"] = "offscreen"

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if proc.returncode != 0:
            return CaptureResult(
                file=target.file,
                app=target.app,
                status="crash",
                error=f"Process exited with code {proc.returncode}: {proc.stderr.strip()}",
            )
        for line in reversed(proc.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    return CaptureResult(
                        file=data.get("file", target.file),
                        app=data.get("app", target.app),
                        status=data.get("status", "unknown"),
                        screenshot_path=data.get("screenshot_path"),
                        width=data.get("width", 0),
                        height=data.get("height", 0),
                        error=data.get("error"),
                        dialog_warning=data.get("dialog_warning"),
                    )
                except Exception:
                    pass
        return CaptureResult(
            file=target.file,
            app=target.app,
            status="parse_error",
            error=f"No valid JSON output. Raw stdout: {proc.stdout[:200]}",
        )
    except subprocess.TimeoutExpired:
        return CaptureResult(
            file=target.file,
            app=target.app,
            status="timeout",
            error=f"Timed out after {timeout} seconds",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="ATBOffice Offscreen Canvas Capture Worker")
    parser.add_argument("--file", required=True, help="Path to document file")
    parser.add_argument("--app", choices=["word", "excel", "powerpoint"], required=True, help="App type")
    parser.add_argument("--out", default=str(repo_root / "screenshots" / "atboffice_docs"), help="Output directory")
    parser.add_argument("--width", type=int, default=1440, help="Viewport width")
    parser.add_argument("--height", type=int, default=900, help="Viewport height")
    parser.add_argument("--canvas-only", action="store_true", help="Capture only canvas")
    parser.add_argument("--json-single", action="store_true", help="Output JSON and exit")
    args = parser.parse_args()

    fpath = Path(args.file).resolve()
    target = DocumentTarget(
        file=fpath.name,
        path=fpath,
        format=fpath.suffix.lstrip(".").lower(),
        app=args.app,
        expected_status="ok",
        is_supported=True,
    )
    res = capture_single_document(
        target=target,
        out_dir=Path(args.out),
        viewport_size=(args.width, args.height),
        canvas_only=args.canvas_only,
    )

    if args.json_single:
        print(json.dumps(res.to_dict()))
    else:
        print(f"Captured {target.file}: status={res.status}")


if __name__ == "__main__":
    main()
