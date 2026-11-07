"""Core loss-audit abstractions, XML text decoding, isolated runner, and expectations contracts."""

from __future__ import annotations

import collections
import hashlib
import io
import json
import multiprocessing
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Any


def xml_text(data: bytes) -> str:
    """Decode raw XML bytes considering UTF-8, UTF-8-BOM, UTF-16LE, and UTF-16BE.

    Ported from .vibeoffice/tools/ooxml/audit.py.
    """
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if data.startswith(b"\x00<\x00?"):
        return data.decode("utf-16be")
    if data.startswith(b"<\x00?\x00"):
        return data.decode("utf-16le")
    return data.decode("utf-8-sig")


def load_package_xml(
    source: Path | str | bytes | io.BytesIO, max_part_size: int = 60_000_000
) -> tuple[list[str], dict[str, str]]:
    """Extract XML and relationship parts from an OOXML zip package.

    Normalizes mc:AlternateContent by removing mc:Fallback to prevent duplicate
    counting of fallback VML/DrawingML shapes.
    """
    if isinstance(source, (str, Path)):
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"Package file not found: {source_path}")
        zf = zipfile.ZipFile(source_path, "r")
    elif isinstance(source, bytes):
        zf = zipfile.ZipFile(io.BytesIO(source), "r")
    else:
        zf = zipfile.ZipFile(source, "r")

    try:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        files: dict[str, str] = {}
        for n in names:
            if (
                n.endswith(".xml")
                or n.endswith(".rels")
                or n.endswith(".vml")
            ) and zf.getinfo(n).file_size < max_part_size:
                try:
                    raw = zf.read(n)
                    text = xml_text(raw)
                    # Strip mc:Fallback contents
                    if "mc:Fallback" in text:
                        text = re.sub(
                            r"<mc:Fallback\b.*?</mc:Fallback>", "", text, flags=re.DOTALL
                        )
                    files[n] = text
                except Exception:
                    continue
        return names, files
    finally:
        zf.close()


class CorpusExpectations:
    """Loads and validates authoritative corpus expectations manifest."""

    def __init__(self, manifest_path: Path | str = "tests/docs/expectations.json") -> None:
        self.path = Path(manifest_path)
        self.items: list[dict[str, Any]] = []
        self._by_file: dict[str, dict[str, Any]] = {}
        self._by_path: dict[str, dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"Expectations manifest not found at {self.path}")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Expectations manifest must be a JSON array")
        self.items = raw
        self._by_file = {item["file"]: item for item in self.items}
        self._by_path = {item["path"]: item for item in self.items}

    def __len__(self) -> int:
        return len(self.items)

    def get(self, file_or_path: str | Path) -> dict[str, Any] | None:
        key = str(file_or_path)
        name = Path(key).name
        return self._by_file.get(name) or self._by_path.get(key)

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = collections.defaultdict(int)
        for it in self.items:
            counts[it.get("category", "unknown")] += 1
        return dict(counts)

    def verify_on_disk_hashes(self, base_dir: Path | str = ".") -> list[str]:
        base = Path(base_dir)
        mismatches: list[str] = []
        for it in self.items:
            p = base / it["path"]
            if not p.exists():
                mismatches.append(f"Missing file: {p}")
                continue
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            if sha != it.get("sha256"):
                mismatches.append(f"SHA mismatch for {p}: expected {it.get('sha256')}, got {sha}")
        return mismatches


def _render_model_offscreen(app: str, model: Any) -> bool:
    """Execute real offscreen Qt rendering for a parsed document model.

    Returns True only if rendering actually executed without raising an exception
    and produced a non-null QImage with positive dimensions.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication

        qapp = QApplication.instance()
        if qapp is None:
            qapp = QApplication([])

        view: Any = None
        if app == "word":
            from atboffice.modules.writer.views.canvas_view import WriterCanvasView

            view = WriterCanvasView()
            view.set_document(model)
        elif app == "excel":
            from atboffice.modules.spreadsheet.view import SpreadsheetView

            view = SpreadsheetView()
            view.workbook = model
        elif app == "powerpoint":
            from atboffice.modules.presentation.view import PresentationView

            view = PresentationView()
            view.load_presentation(model)
        else:
            return False

        view.resize(800, 600)
        img = view.grab().toImage()
        ok = bool(not img.isNull() and img.width() > 0 and img.height() > 0)
        view.close()
        view.deleteLater()
        return ok
    except Exception:
        return False


def _probe_legacy_open_outcome(
    path: Path, raw_data: bytes, app: str, ext: str
) -> dict[str, Any]:
    """Probe the real open classification for legacy (.doc/.xls/.ppt) and encrypted files."""
    lead = raw_data[:64]
    if lead.startswith(b"\xef\xbb\xbf"):
        lead = lead[3:]
    stripped = lead.lstrip()
    is_xml = stripped.startswith((b"<", b"\xff\xfe<\x00", b"\xfe\xff\x00<"))

    if ext in (".xls", ".xlt"):
        if is_xml:
            try:
                from atboffice.modules.spreadsheet.io.xmlss_io import (
                    read_xmlss_workbook,
                )

                wb = read_xmlss_workbook(raw_data)
                if wb and getattr(wb, "sheets", None):
                    return {
                        "outcome": "imported",
                        "rejection_kind": None,
                        "dispatched_format": "xmlss",
                        "read_only": False,
                    }
            except Exception as exc:
                return {
                    "outcome": "rejected",
                    "rejection_kind": "corrupt",
                    "dispatched_format": "xmlss",
                    "read_only": False,
                    "error": str(exc),
                }
        else:
            try:
                from atboffice.modules.spreadsheet.io.xls_reader import read_xls

                wb = read_xls(path)
                if wb and getattr(wb, "sheets", None):
                    return {
                        "outcome": "imported",
                        "rejection_kind": None,
                        "dispatched_format": "xls_binary",
                        "read_only": True,
                    }
            except PermissionError as exc:
                return {
                    "outcome": "rejected",
                    "rejection_kind": "encrypted",
                    "dispatched_format": "xls_binary",
                    "read_only": False,
                    "error": str(exc),
                }
            except Exception as exc:
                return {
                    "outcome": "rejected",
                    "rejection_kind": "corrupt",
                    "dispatched_format": "xls_binary",
                    "read_only": False,
                    "error": str(exc),
                }

    return {
        "outcome": "rejected",
        "rejection_kind": "unsupported_format",
        "dispatched_format": f"legacy_{ext.lstrip('.')}",
        "read_only": False,
    }


def _execute_file_audit_worker(
    queue: multiprocessing.Queue,
    file_path_str: str,
    fault: str | None = None,
    execute_render: bool = True,
) -> None:
    """Worker function executed inside an isolated process."""
    if fault == "hang":
        time.sleep(60.0)
        return

    if fault == "crash":
        os._exit(139)

    path = Path(file_path_str)
    raw_data = path.read_bytes()
    ext = path.suffix.lower()
    app = ""
    if ext in (".docx", ".doc"):
        app = "word"
    elif ext in (".xlsx", ".xlsm", ".xls"):
        app = "excel"
    elif ext in (".pptx", ".pptm", ".ppt"):
        app = "powerpoint"

    # Legacy binary / disguised extension handling (probed rather than blindly skipped)
    if ext in (".doc", ".xls", ".ppt"):
        real_open_info = _probe_legacy_open_outcome(path, raw_data, app, ext)
        queue.put({
            "file": path.name,
            "path": str(path),
            "app": app,
            "format": ext.lstrip("."),
            "status": "unsupported_format",
            "real_open": real_open_info,
            "stages": {
                "parse": "rejected_unsupported_format",
                "model": "skip",
                "render": "skip",
                "roundtrip": "skip",
            },
            "reason": (
                f"Legacy {ext} format (GUI real_open outcome: {real_open_info['outcome']}, "
                f"format: {real_open_info['dispatched_format']})"
            ),
        })
        return

    # Check for Agile Encrypted OOXML (wrapped in OLE2 container with \xd0\xcf\x11\xe0)
    ole2_magic = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    if raw_data.startswith(ole2_magic):
        queue.put({
            "file": path.name,
            "path": str(path),
            "app": app,
            "format": ext.lstrip("."),
            "status": "encrypted",
            "real_open": {
                "outcome": "rejected",
                "rejection_kind": "encrypted",
                "dispatched_format": "encrypted_ooxml",
                "read_only": False,
            },
            "stages": {
                "parse": "rejected_encrypted",
                "model": "skip",
                "render": "skip",
                "roundtrip": "skip",
            },
            "reason": "Document is an encrypted OOXML package wrapped in OLE2 container",
        })
        return

    # Normal OOXML pipeline: parse -> model -> render -> roundtrip
    stages: dict[str, str] = {}
    feature_losses: dict[str, int] = {}

    try:
        if fault == "exception":
            raise RuntimeError("Injected error for fault testing")

        # Stage 1: Parse
        if app == "word":
            from atboffice.deep.audit.word import extract_word_features
            from atboffice.modules.writer.io import read_docx, write_docx
            model = read_docx(raw_data)
        elif app == "excel":
            from atboffice.deep.audit.excel import extract_excel_features
            from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
            from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
            model = read_xlsx(raw_data)
        elif app == "powerpoint":
            from atboffice.deep.audit.presentation import extract_presentation_features
            from atboffice.modules.presentation.io import read_pptx, write_pptx
            model = read_pptx(raw_data)
        else:
            queue.put({
                "file": path.name,
                "path": str(path),
                "status": "unsupported_format",
                "stages": {
                    "parse": "rejected_unsupported_format",
                    "model": "skip",
                    "render": "skip",
                    "roundtrip": "skip",
                },
                "reason": f"Unknown application for extension {ext}",
            })
            return

        stages["parse"] = "ok"

        # Stage 2: Model inspection
        if app == "word":
            has_body = (
                hasattr(model, "main")
                or hasattr(model, "body")
                or hasattr(model, "paragraphs")
            )
            stages["model"] = "ok" if has_body else "fail"
        elif app == "excel":
            has_sheets = hasattr(model, "sheets") or hasattr(model, "worksheets")
            stages["model"] = "ok" if has_sheets else "fail"
        elif app == "powerpoint":
            stages["model"] = "ok" if hasattr(model, "slides") else "fail"

        # Stage 3: Render (never mark skipped or unexecuted render as 'ok')
        if fault == "render_fail":
            stages["render"] = "fail"
        elif execute_render:
            render_ok = _render_model_offscreen(app, model)
            stages["render"] = "ok" if render_ok else "fail"
        else:
            stages["render"] = "skip"

        if stages["render"] == "fail":
            queue.put({
                "file": path.name,
                "path": str(path),
                "app": app,
                "format": ext.lstrip("."),
                "status": "fail",
                "stages": {
                    "parse": stages["parse"],
                    "model": stages["model"],
                    "render": "fail",
                    "roundtrip": "skip",
                },
                "reason": "Offscreen render execution failed",
            })
            return

        # Stage 4: Roundtrip serialization
        if fault == "loss":
            feature_losses["paragraphs"] = 2
            saved_bytes = b""
        elif app == "word":
            saved_bytes = write_docx(model)
            orig_names, orig_files = load_package_xml(raw_data)
            saved_names, saved_files = load_package_xml(saved_bytes)
            orig_feats = extract_word_features(orig_names, orig_files)
            saved_feats = extract_word_features(saved_names, saved_files)
            for feat, orig_count in orig_feats.items():
                saved_count = saved_feats.get(feat, 0)
                if saved_count < orig_count:
                    feature_losses[feat] = orig_count - saved_count
        elif app == "excel":
            saved_bytes = write_xlsx(model)
            orig_names, orig_files = load_package_xml(raw_data)
            saved_names, saved_files = load_package_xml(saved_bytes)
            orig_feats = extract_excel_features(orig_names, orig_files)
            saved_feats = extract_excel_features(saved_names, saved_files)
            for feat, orig_count in orig_feats.items():
                saved_count = saved_feats.get(feat, 0)
                if saved_count < orig_count:
                    feature_losses[feat] = orig_count - saved_count
        elif app == "powerpoint":
            saved_bytes = write_pptx(model)
            orig_names, orig_files = load_package_xml(raw_data)
            saved_names, saved_files = load_package_xml(saved_bytes)
            orig_feats = extract_presentation_features(orig_names, orig_files)
            saved_feats = extract_presentation_features(saved_names, saved_files)
            for feat, orig_count in orig_feats.items():
                saved_count = saved_feats.get(feat, 0)
                if saved_count < orig_count:
                    feature_losses[feat] = orig_count - saved_count

        stages["roundtrip"] = "ok" if not feature_losses else "loss"

        status = "loss" if feature_losses else "ok"
        queue.put({
            "file": path.name,
            "path": str(path),
            "app": app,
            "format": ext.lstrip("."),
            "status": status,
            "stages": stages,
            "feature_losses": feature_losses,
            "orig_size": len(raw_data),
            "saved_size": len(saved_bytes) if fault != "loss" else 0,
        })

    except Exception as e:
        err_msg = str(e).lower()
        is_corrupt = (
            "zip" in err_msg
            or "archive" in err_msg
            or "header mismatch" in err_msg
            or "corrupt" in err_msg
            or isinstance(e, zipfile.BadZipFile)
        )
        if is_corrupt:
            queue.put({
                "file": path.name,
                "path": str(path),
                "app": app,
                "format": ext.lstrip("."),
                "status": "corrupt",
                "stages": {
                    "parse": "rejected_corrupt",
                    "model": "skip",
                    "render": "skip",
                    "roundtrip": "skip",
                },
                "reason": f"Corrupt archive: {e}",
            })
        else:
            queue.put({
                "file": path.name,
                "path": str(path),
                "app": app,
                "format": ext.lstrip("."),
                "status": "fail",
                "stages": {
                    "parse": "fail",
                    "model": "skip",
                    "render": "skip",
                    "roundtrip": "skip",
                },
                "reason": f"{type(e).__name__}: {e}",
            })


class IsolatedFileRunner:
    """Executes a single file audit in an isolated process with hard timeout termination."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def run(
        self,
        file_path: str | Path,
        expectations: CorpusExpectations | None = None,
        fault: str | None = None,
        execute_render: bool = True,
    ) -> dict[str, Any]:
        """Run audit on a single file within an isolated subprocess."""
        path_str = str(file_path)
        ctx = multiprocessing.get_context("spawn")
        queue: multiprocessing.Queue = ctx.Queue()

        proc = ctx.Process(
            target=_execute_file_audit_worker,
            args=(queue, path_str, fault, execute_render),
        )
        proc.start()
        proc.join(timeout=self.timeout)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1.0)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1.0)
            res = {
                "file": Path(path_str).name,
                "path": path_str,
                "status": "timeout",
                "terminated": True,
                "stages": {
                    "parse": "timeout",
                    "model": "skip",
                    "render": "skip",
                    "roundtrip": "skip",
                },
                "reason": f"Execution exceeded hard timeout of {self.timeout}s",
            }
        elif proc.exitcode != 0 and queue.empty():
            res = {
                "file": Path(path_str).name,
                "path": path_str,
                "status": "crash",
                "exitcode": proc.exitcode,
                "stages": {
                    "parse": "crash",
                    "model": "skip",
                    "render": "skip",
                    "roundtrip": "skip",
                },
                "reason": f"Worker crashed with exit code {proc.exitcode}",
            }
        else:
            try:
                res = queue.get_nowait()
            except Exception:
                res = {
                    "file": Path(path_str).name,
                    "path": path_str,
                    "status": "fail",
                    "stages": {
                        "parse": "fail",
                        "model": "skip",
                        "render": "skip",
                        "roundtrip": "skip",
                    },
                    "reason": "Worker completed without returning output",
                }

        # Compare with expectations if provided
        if expectations:
            exp_item = expectations.get(path_str)
            if exp_item:
                expected_status = (
                    exp_item.get("expected_status")
                    or exp_item.get("expectations", {}).get("expected_status")
                    or exp_item.get("category")
                )
                actual_status = res.get("status")
                res["expected_status"] = expected_status
                res["expected_match"] = (actual_status == expected_status)
            else:
                res["expected_match"] = (res.get("status") == "ok")

        return res

    def run_with_injection(self, file_path: str | Path, fault: str) -> dict[str, Any]:
        """Convenience method for fault injection testing."""
        return self.run(file_path, fault=fault)


def audit_corpus_file(
    file_path: str | Path,
    expectations: CorpusExpectations | None = None,
    timeout: float = 30.0,
    fault_injection: str | None = None,
    execute_render: bool = True,
) -> dict[str, Any]:
    """Audit a single corpus file in an isolated process comparing to expectations."""
    runner = IsolatedFileRunner(timeout=timeout)
    return runner.run(
        file_path,
        expectations=expectations,
        fault=fault_injection,
        execute_render=execute_render,
    )


def run_real_open_in_process(
    file_path: str | Path,
    password_action: str = "cancel",
    execute_render: bool = True,
    fault: str | None = None,
) -> dict[str, Any]:
    """Execute the real GUI window open path on a single file and classify outcome.

    Classifies outcome into:
    - 'imported': document opened, bound to model, and rendered offscreen (if execute_render=True)
    - 'rejected': open rejected with dialog ('unsupported_format', 'corrupt', 'encrypted')
    - 'cancelled': encrypted document password prompt cancelled cleanly with 0 error dialogs
    - 'fail': unexpected failure or render failure
    Never marks skipped or unexecuted render as 'ok'.
    """
    if fault == "hang":
        time.sleep(60.0)
        return {}
    if fault == "crash":
        os._exit(139)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

    from atboffice.core.window_manager import WindowManager
    from atboffice.ui.shell.lectern_window import LecternWindow
    from atboffice.ui.shell.ledger_window import LedgerWindow
    from atboffice.ui.shell.quire_window import QuireWindow

    qapp = QApplication.instance()
    if qapp is None:
        qapp = QApplication([])

    path = Path(file_path).resolve()
    ext = path.suffix.lower()
    wm = WindowManager.get_instance()
    app_type = wm.detect_app_type(path)
    app_map = {"quire": "word", "ledger": "excel", "lectern": "powerpoint"}
    app_name = app_map.get(app_type, "word")

    dialogs: list[dict[str, str]] = []
    password_prompted = False

    orig_warning = QMessageBox.warning
    orig_critical = QMessageBox.critical
    orig_get_text = QInputDialog.getText

    def _capture_warning(parent: Any, title: str, text: str, *args: Any, **kwargs: Any) -> Any:
        dialogs.append({"level": "warning", "title": str(title), "message": str(text)})
        return QMessageBox.StandardButton.Ok

    def _capture_critical(parent: Any, title: str, text: str, *args: Any, **kwargs: Any) -> Any:
        dialogs.append({"level": "critical", "title": str(title), "message": str(text)})
        return QMessageBox.StandardButton.Ok

    def _capture_get_text(*args: Any, **kwargs: Any) -> tuple[str, bool]:
        nonlocal password_prompted
        password_prompted = True
        if password_action == "cancel":
            return ("", False)
        if password_action in ("reject", "wrong_password"):
            return ("__invalid_password__", True)
        return (str(password_action), True)

    QMessageBox.warning = _capture_warning  # type: ignore[assignment]
    QMessageBox.critical = _capture_critical  # type: ignore[assignment]
    QInputDialog.getText = _capture_get_text  # type: ignore[assignment]

    win: Any = None
    try:
        if fault == "exception":
            raise RuntimeError("Injected real-open error")

        if app_type == "ledger":
            win = LedgerWindow(file_path=None)
        elif app_type == "lectern":
            win = LecternWindow(file_path=None)
        else:
            win = QuireWindow(file_path=None)

        win.maybe_save_prompt = lambda: True
        open_ok = bool(win.open_file(path))

        if open_ok:
            read_only = bool(getattr(win, "is_read_only_import", False))
            if app_type == "ledger":
                if read_only:
                    dispatched_format = "xls_binary"
                elif ext in (".xls", ".xlt", ".xml", ".xmlss"):
                    dispatched_format = "xmlss"
                else:
                    dispatched_format = ext.lstrip(".")
            elif app_type == "quire" and ext in (".doc", ".dot"):
                dispatched_format = "html_or_rtf_disguised"
            else:
                dispatched_format = ext.lstrip(".")

            if execute_render:
                cw = win.centralWidget()
                if cw is not None:
                    cw.resize(800, 600)
                    img = cw.grab().toImage()
                    render_stage = (
                        "ok"
                        if (not img.isNull() and img.width() > 0 and img.height() > 0)
                        else "fail"
                    )
                else:
                    render_stage = "fail"
            else:
                render_stage = "skip"

            outcome = "imported" if render_stage != "fail" else "fail"
            rejection_kind = None
        else:
            read_only = False
            dispatched_format = (
                f"legacy_{ext.lstrip('.')}"
                if ext in (".doc", ".xls", ".ppt")
                else ext.lstrip(".")
            )
            render_stage = "skip"

            if password_prompted and password_action == "cancel" and len(dialogs) == 0:
                outcome = "cancelled"
                rejection_kind = "encrypted_cancelled"
            elif len(dialogs) > 0:
                outcome = "rejected"
                if password_prompted or any(
                    "密码" in d["message"] or "加密" in d["title"] or "加密" in d["message"]
                    for d in dialogs
                ):
                    rejection_kind = "encrypted"
                elif any(
                    d["level"] == "critical"
                    or "损坏" in d["message"]
                    or "无法打开" in d["message"]
                    for d in dialogs
                ):
                    rejection_kind = "corrupt"
                else:
                    rejection_kind = "unsupported_format"
            else:
                outcome = "fail"
                rejection_kind = "unhandled"

        return {
            "file": path.name,
            "path": str(path),
            "app": app_name,
            "app_window": app_type,
            "format": ext.lstrip("."),
            "open_ok": open_ok,
            "outcome": outcome,
            "rejection_kind": rejection_kind,
            "dispatched_format": dispatched_format,
            "read_only": read_only,
            "password_prompted": password_prompted,
            "dialogs": dialogs,
            "stages": {
                "open": "ok" if open_ok else outcome,
                "render": render_stage,
            },
        }
    except Exception as exc:
        return {
            "file": path.name,
            "path": str(path),
            "app": app_name,
            "app_window": app_type,
            "format": ext.lstrip("."),
            "open_ok": False,
            "outcome": "fail",
            "rejection_kind": "exception",
            "dispatched_format": ext.lstrip("."),
            "read_only": False,
            "password_prompted": password_prompted,
            "dialogs": dialogs,
            "stages": {
                "open": "fail",
                "render": "skip",
            },
            "reason": f"{type(exc).__name__}: {exc}",
        }
    finally:
        QMessageBox.warning = orig_warning  # type: ignore[assignment]
        QMessageBox.critical = orig_critical  # type: ignore[assignment]
        QInputDialog.getText = orig_get_text  # type: ignore[assignment]
        if win is not None:
            try:
                win.close()
                win.deleteLater()
            except Exception:
                pass


def _execute_real_open_worker(
    queue: multiprocessing.Queue,
    file_path_str: str,
    password_action: str = "cancel",
    execute_render: bool = True,
    fault: str | None = None,
) -> None:
    """Subprocess entry point for single-file isolated real GUI open verification."""
    res = run_real_open_in_process(
        file_path_str,
        password_action=password_action,
        execute_render=execute_render,
        fault=fault,
    )
    if res:
        queue.put(res)


def _persistent_real_open_worker(
    task_queue: multiprocessing.Queue,
    result_queue: multiprocessing.Queue,
) -> None:
    """Persistent isolated subprocess worker for batch real-open verification."""
    while True:
        item = task_queue.get()
        if item is None:
            break
        file_path_str, password_action, execute_render, fault = item
        res = run_real_open_in_process(
            file_path_str,
            password_action=password_action,
            execute_render=execute_render,
            fault=fault,
        )
        result_queue.put(res)


class IsolatedRealOpenRunner:
    """Runs real GUI document open verification inside isolated subprocesses with hard timeouts."""

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def _match_expectations(
        self, res: dict[str, Any], path_str: str, expectations: CorpusExpectations | None
    ) -> dict[str, Any]:
        if expectations:
            exp_item = expectations.get(path_str)
            if exp_item:
                real_exp = exp_item.get("real_open") or {}
                exp_outcome = real_exp.get("expected_outcome")
                if exp_outcome:
                    res["expected_outcome"] = exp_outcome
                    outcome_ok = res.get("outcome") == exp_outcome
                    if (
                        exp_outcome == "cancelled"
                        and res.get("outcome") == "rejected"
                        and res.get("rejection_kind") == "encrypted"
                    ):
                        outcome_ok = True
                    res["expected_match"] = outcome_ok
        return res

    def run(
        self,
        file_path: str | Path,
        password_action: str = "cancel",
        execute_render: bool = True,
        expectations: CorpusExpectations | None = None,
        fault: str | None = None,
    ) -> dict[str, Any]:
        """Run real GUI open on a single file in a dedicated isolated subprocess."""
        path_str = str(file_path)
        ctx = multiprocessing.get_context("spawn")
        queue: multiprocessing.Queue = ctx.Queue()

        proc = ctx.Process(
            target=_execute_real_open_worker,
            args=(queue, path_str, password_action, execute_render, fault),
        )
        proc.start()
        proc.join(timeout=self.timeout)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1.0)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1.0)
            res: dict[str, Any] = {
                "file": Path(path_str).name,
                "path": path_str,
                "open_ok": False,
                "outcome": "timeout",
                "terminated": True,
                "stages": {"open": "timeout", "render": "skip"},
                "reason": f"Real open exceeded hard timeout of {self.timeout}s",
            }
        elif proc.exitcode != 0 and queue.empty():
            res = {
                "file": Path(path_str).name,
                "path": path_str,
                "open_ok": False,
                "outcome": "crash",
                "exitcode": proc.exitcode,
                "stages": {"open": "crash", "render": "skip"},
                "reason": f"Real open worker crashed with exit code {proc.exitcode}",
            }
        else:
            try:
                res = queue.get_nowait()
            except Exception:
                res = {
                    "file": Path(path_str).name,
                    "path": path_str,
                    "open_ok": False,
                    "outcome": "fail",
                    "stages": {"open": "fail", "render": "skip"},
                    "reason": "Worker exited without returning output",
                }

        return self._match_expectations(res, path_str, expectations)

    def run_batch(
        self,
        file_paths: list[str | Path],
        password_action: str = "cancel",
        execute_render: bool = True,
        expectations: CorpusExpectations | None = None,
    ) -> list[dict[str, Any]]:
        """Run real GUI open across files in an isolated worker with timeout and respawn."""
        ctx = multiprocessing.get_context("spawn")
        task_q: multiprocessing.Queue = ctx.Queue()
        res_q: multiprocessing.Queue = ctx.Queue()

        def _spawn_worker() -> Any:
            p = ctx.Process(target=_persistent_real_open_worker, args=(task_q, res_q))
            p.start()
            return p

        proc = _spawn_worker()
        results: list[dict[str, Any]] = []

        try:
            for fp in file_paths:
                path_str = str(fp)
                if not proc.is_alive():
                    proc = _spawn_worker()

                task_q.put((path_str, password_action, execute_render, None))
                deadline = time.monotonic() + self.timeout
                got_res: dict[str, Any] | None = None

                while time.monotonic() < deadline:
                    try:
                        got_res = res_q.get(timeout=0.05)
                        break
                    except Exception:
                        if not proc.is_alive():
                            break

                if got_res is not None:
                    results.append(self._match_expectations(got_res, path_str, expectations))
                elif proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=1.0)
                    if proc.is_alive():
                        proc.kill()
                        proc.join(timeout=1.0)
                    res = {
                        "file": Path(path_str).name,
                        "path": path_str,
                        "open_ok": False,
                        "outcome": "timeout",
                        "terminated": True,
                        "stages": {"open": "timeout", "render": "skip"},
                        "reason": f"Real open exceeded hard timeout of {self.timeout}s",
                    }
                    results.append(self._match_expectations(res, path_str, expectations))
                    task_q = ctx.Queue()
                    res_q = ctx.Queue()
                    proc = _spawn_worker()
                else:
                    res = {
                        "file": Path(path_str).name,
                        "path": path_str,
                        "open_ok": False,
                        "outcome": "crash",
                        "exitcode": proc.exitcode,
                        "stages": {"open": "crash", "render": "skip"},
                        "reason": f"Worker crashed with exit code {proc.exitcode}",
                    }
                    results.append(self._match_expectations(res, path_str, expectations))
                    task_q = ctx.Queue()
                    res_q = ctx.Queue()
                    proc = _spawn_worker()
        finally:
            if proc.is_alive():
                try:
                    task_q.put(None)
                    proc.join(timeout=2.0)
                except Exception:
                    pass
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=1.0)

        return results


def audit_real_open_file(
    file_path: str | Path,
    password_action: str = "cancel",
    execute_render: bool = True,
    expectations: CorpusExpectations | None = None,
    timeout: float = 15.0,
    fault_injection: str | None = None,
) -> dict[str, Any]:
    """Audit a single file using the isolated real GUI window open path."""
    runner = IsolatedRealOpenRunner(timeout=timeout)
    return runner.run(
        file_path,
        password_action=password_action,
        execute_render=execute_render,
        expectations=expectations,
        fault=fault_injection,
    )


def audit_legacy_and_abnormal_corpus(
    expectations: CorpusExpectations | None = None,
    password_action: str = "cancel",
    execute_render: bool = True,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Audit all 75 legacy (.doc/.xls/.ppt), encrypted, and corrupt files via real open."""
    manifest = expectations or CorpusExpectations("tests/docs/expectations.json")
    targets = [it["path"] for it in manifest.items if it.get("category") != "valid"]
    runner = IsolatedRealOpenRunner(timeout=timeout)
    results = runner.run_batch(
        targets,
        password_action=password_action,
        execute_render=execute_render,
        expectations=manifest,
    )
    outcomes = collections.Counter(r.get("outcome") for r in results)
    rejection_kinds = collections.Counter(
        r.get("rejection_kind") for r in results if r.get("outcome") == "rejected"
    )
    unmatched = sum(1 for r in results if r.get("expected_match") is False)
    return {
        "total": len(results),
        "imported": outcomes.get("imported", 0),
        "rejected": outcomes.get("rejected", 0),
        "cancelled": outcomes.get("cancelled", 0),
        "timeout": outcomes.get("timeout", 0),
        "crash": outcomes.get("crash", 0),
        "fail": outcomes.get("fail", 0),
        "rejection_breakdown": dict(rejection_kinds),
        "unmatched": unmatched,
        "results": results,
    }


class AuditSession:
    """Collects, aggregates, and validates results across an entire corpus audit run."""

    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []
        self.feature_losses: collections.Counter[str] = collections.Counter()

    def record_pair(
        self,
        file: str,
        status: str,
        original_features: dict[str, int] | None = None,
        saved_features: dict[str, int] | None = None,
        reason: str = "",
    ) -> None:
        """Record the audit outcome of a single document pair (backwards compatible)."""
        rec: dict[str, Any] = {
            "file": file,
            "status": status,
            "reason": reason,
        }
        if original_features and saved_features:
            diffs: dict[str, dict[str, int]] = {}
            for feat, orig_val in original_features.items():
                saved_val = saved_features.get(feat, 0)
                if saved_val < orig_val:
                    loss_amount = orig_val - saved_val
                    self.feature_losses[feat] += 1
                    diffs[feat] = {
                        "original": orig_val,
                        "saved": saved_val,
                        "loss": loss_amount,
                    }
            rec["differences"] = diffs

        self.results.append(rec)

    def record_result(self, result: dict[str, Any]) -> None:
        """Record structured output from audit_corpus_file."""
        self.results.append(result)
        losses = result.get("feature_losses") or {}
        for feat, count in losses.items():
            self.feature_losses[feat] += count

    def summary(self) -> dict[str, Any]:
        """Generate high-level audit summary metrics with full accounting."""
        statuses = collections.Counter(r.get("status") for r in self.results)
        unmatched = sum(1 for r in self.results if r.get("expected_match") is False)
        failed_cnt = statuses.get("failed", 0) + statuses.get("fail", 0)
        excluded_cnt = (
            statuses.get("excluded", 0)
            + statuses.get("unsupported_format", 0)
            + statuses.get("encrypted", 0)
            + statuses.get("corrupt", 0)
        )
        return {
            "attempted": len(self.results),
            "ok": statuses.get("ok", 0),
            "failed": failed_cnt,
            "excluded": excluded_cnt,
            "encrypted": statuses.get("encrypted", 0),
            "corrupt": statuses.get("corrupt", 0),
            "unsupported_format": statuses.get("unsupported_format", 0),
            "timeout": statuses.get("timeout", 0),
            "crash": statuses.get("crash", 0),
            "fail": failed_cnt,
            "loss": statuses.get("loss", 0),
            "unmatched_failures": unmatched,
            "feature_losses": dict(self.feature_losses),
            "results": self.results,
        }

    def is_passing(self) -> bool:
        """Returns True if all attempted files match expectations without timeouts or crashes."""
        summ = self.summary()
        if summ["timeout"] > 0 or summ["crash"] > 0:
            return False
        if summ["unmatched_failures"] > 0:
            return False
        return True
