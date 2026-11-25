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
from .regions import baseline_target_size, default_region, region_names, resolve_region_widget

repo_root = find_repo_root(Path(__file__))
if str(repo_root / "src") not in sys.path:
    sys.path.insert(0, str(repo_root / "src"))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from atboffice.core.app import create_application
from atboffice.core.window_manager import WindowManager

LAST_DIALOG_ERROR: str | None = None

FIT_ATTEMPTS = 8


def resolve_capture_widget(window: object, app_name: str, region: str) -> object:
    """Widget for ``region``; falls back to the central widget for unknown windows."""
    widget = resolve_region_widget(window, app_name, region)
    if widget is not None:
        return widget
    cw = getattr(window, "centralWidget", lambda: None)()
    return cw if cw is not None else window


def fit_region_to_size(
    window: object,
    app_name: str,
    region: str,
    target_size: tuple[int, int],
) -> object:
    """Resize ``window`` until the region widget is exactly ``target_size``.

    Splitters and layouts do not always hand the whole window delta to the region,
    so the delta is re-measured on every pass. Returns the (re-resolved) widget.
    """
    widget = resolve_capture_widget(window, app_name, region)
    for _ in range(FIT_ATTEMPTS):
        drain_event_loop(3)
        dw = target_size[0] - widget.width()
        dh = target_size[1] - widget.height()
        if dw == 0 and dh == 0:
            break
        window.resize(max(1, window.width() + dw), max(1, window.height() + dh))
        drain_event_loop(3)
        if hasattr(window, "fit_to_window"):
            window.fit_to_window()
        widget = resolve_capture_widget(window, app_name, region)
    return widget


def crop_to_size(pixmap: QPixmap, target_size: tuple[int, int]) -> QPixmap:
    """Crop a grab that came out larger than the baseline. Never pads."""
    w = min(pixmap.width(), target_size[0])
    h = min(pixmap.height(), target_size[1])
    if (w, h) == (pixmap.width(), pixmap.height()):
        return pixmap
    return pixmap.copy(0, 0, w, h)


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
    region: str | None = None,
    baseline_dir: Path | None = None,
) -> CaptureResult:
    """Render one document offscreen and save the named region.

    The region widget is resized to the baseline size from ``baseline_dir`` so both
    engines capture the same pixels. ``canvas_only`` is an alias for ``region="canvas"``.
    """
    global LAST_DIALOG_ERROR
    LAST_DIALOG_ERROR = None
    install_dialog_interceptors()
    region = "canvas" if canvas_only else (region or default_region())

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

        target_size = baseline_target_size(baseline_dir, target.app, target.file, region)
        if target_size is not None:
            grab_target = fit_region_to_size(window, target.app, region, target_size)
        else:
            grab_target = resolve_capture_widget(window, target.app, region)
        drain_event_loop(3)
        pixmap = grab_target.grab()

        if pixmap.isNull() or pixmap.width() == 0 or pixmap.height() == 0:
            return CaptureResult(
                file=target.file,
                app=target.app,
                status="empty_render",
                error="Grabbed pixmap is null or zero-sized",
            )

        status = "dialog_warning" if LAST_DIALOG_ERROR else "captured"
        error = None
        if target_size is not None:
            pixmap = crop_to_size(pixmap, target_size)
            if (pixmap.width(), pixmap.height()) != target_size:
                status = "size_mismatch"
                error = (
                    f"Region '{region}' is {pixmap.width()}x{pixmap.height()}, "
                    f"baseline is {target_size[0]}x{target_size[1]}"
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
            status=status,
            screenshot_path=str(out_png),
            width=pixmap.width(),
            height=pixmap.height(),
            error=error,
            dialog_warning=LAST_DIALOG_ERROR,
            region=region,
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
    region: str | None = None,
    baseline_dir: Path | None = None,
) -> CaptureResult:
    """Execute capture of a single file in an isolated Python subprocess."""
    region = "canvas" if canvas_only else (region or default_region())
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
        "--region",
        region,
        "--json-single",
    ]
    if baseline_dir is not None:
        cmd += ["--baseline-dir", str(baseline_dir)]

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
                        region=data.get("region", region),
                    )
                except Exception:
                    pass
        return CaptureResult(
            file=target.file,
            app=target.app,
            status="parse_error",
            error=f"No valid JSON output. Raw stdout: {proc.stdout[:200]}",
            region=region,
        )
    except subprocess.TimeoutExpired:
        return CaptureResult(
            file=target.file,
            app=target.app,
            status="timeout",
            error=f"Timed out after {timeout} seconds",
            region=region,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="ATBOffice Offscreen Canvas Capture Worker")
    parser.add_argument("--file", required=True, help="Path to document file")
    parser.add_argument(
        "--app", choices=["word", "excel", "powerpoint"], required=True, help="App type"
    )
    parser.add_argument(
        "--out", default=str(repo_root / "screenshots" / "atboffice_docs"), help="Output directory"
    )
    parser.add_argument("--width", type=int, default=1440, help="Viewport width")
    parser.add_argument("--height", type=int, default=900, help="Viewport height")
    parser.add_argument("--canvas-only", action="store_true", help="Alias for --region canvas")
    parser.add_argument(
        "--region",
        choices=region_names(),
        default=None,
        help="Named capture region (default from regions.json)",
    )
    parser.add_argument(
        "--baseline-dir", default=None, help="Baseline directory whose sizes the capture must match"
    )
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
        region=args.region,
        baseline_dir=Path(args.baseline_dir) if args.baseline_dir else None,
    )

    if args.json_single:
        print(json.dumps(res.to_dict()))
    else:
        print(f"Captured {target.file}: status={res.status}")


if __name__ == "__main__":
    main()
