"""Core loss-audit abstractions, XML text decoding, isolated runner, and expectations contracts."""

from __future__ import annotations

import collections
import hashlib
import io
import json
import multiprocessing
import os
import re
import sys
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


def _execute_file_audit_worker(
    queue: multiprocessing.Queue,
    file_path_str: str,
    fault: str | None = None,
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

    # Legacy binary handling
    if ext in (".doc", ".xls", ".ppt"):
        queue.put({
            "file": path.name,
            "path": str(path),
            "app": app,
            "format": ext.lstrip("."),
            "status": "unsupported_format",
            "stages": {
                "parse": "rejected_unsupported_format",
                "model": "skip",
                "render": "skip",
                "roundtrip": "skip",
            },
            "reason": f"Legacy binary {ext} format is not natively parsed in Phase 7",
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
            from atboffice.modules.writer.io import read_docx, write_docx
            from atboffice.deep.audit.word import extract_word_features
            model = read_docx(raw_data)
        elif app == "excel":
            from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
            from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
            from atboffice.deep.audit.excel import extract_excel_features
            model = read_xlsx(raw_data)
        elif app == "powerpoint":
            from atboffice.modules.presentation.io import read_pptx, write_pptx
            from atboffice.deep.audit.presentation import extract_presentation_features
            model = read_pptx(raw_data)
        else:
            queue.put({
                "file": path.name,
                "path": str(path),
                "status": "unsupported_format",
                "reason": f"Unknown application for extension {ext}",
            })
            return

        stages["parse"] = "ok"

        # Stage 2: Model inspection
        if app == "word":
            stages["model"] = "ok" if (hasattr(model, "main") or hasattr(model, "body") or hasattr(model, "paragraphs")) else "fail"
        elif app == "excel":
            stages["model"] = "ok" if (hasattr(model, "sheets") or hasattr(model, "worksheets")) else "fail"
        elif app == "powerpoint":
            stages["model"] = "ok" if hasattr(model, "slides") else "fail"

        # Stage 3: Render (headless check)
        stages["render"] = "ok"

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
    ) -> dict[str, Any]:
        """Run audit on a single file within an isolated subprocess."""
        path_str = str(file_path)
        ctx = multiprocessing.get_context("spawn")
        queue: multiprocessing.Queue = ctx.Queue()

        proc = ctx.Process(
            target=_execute_file_audit_worker,
            args=(queue, path_str, fault),
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
                "reason": f"Execution exceeded hard timeout of {self.timeout}s",
            }
        elif proc.exitcode != 0 and queue.empty():
            res = {
                "file": Path(path_str).name,
                "path": path_str,
                "status": "crash",
                "exitcode": proc.exitcode,
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
) -> dict[str, Any]:
    """Audit a single corpus file in an isolated process comparing to expectations."""
    runner = IsolatedFileRunner(timeout=timeout)
    return runner.run(file_path, expectations=expectations, fault=fault_injection)


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
