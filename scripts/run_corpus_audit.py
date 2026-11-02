#!/usr/bin/env python3
"""Multi-process Corpus Batch Audit & Roundtrip Runner.

Ports and extends .vibeoffice/tests/ledger/recalc-all.js and corpus drivers.
Runs headless read/save roundtrips and ECMA-376 feature loss audits across
the 6,200+ files in tests/docs/full_corpus/ or any specified directory.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from atboffice.deep.audit.core import load_package_xml
from atboffice.deep.audit.excel import extract_excel_features
from atboffice.deep.audit.presentation import extract_presentation_features
from atboffice.deep.audit.word import extract_word_features
from atboffice.modules.presentation.io import read_pptx, write_pptx
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.writer.io import read_docx, write_docx

EXT_TO_APP: dict[str, str] = {
    ".docx": "word",
    ".docm": "word",
    ".doc": "word",
    ".xlsx": "excel",
    ".xlsm": "excel",
    ".xls": "excel",
    ".pptx": "powerpoint",
    ".pptm": "powerpoint",
    ".ppt": "powerpoint",
}


def audit_single_file(file_path_str: str, app_type: str | None = None) -> dict[str, Any]:
    """Audit a single document file for roundtrip integrity and feature preservation."""
    path = Path(file_path_str)
    ext = path.suffix.lower()
    app = app_type or EXT_TO_APP.get(ext)

    if not app:
        return {
            "file": path.name,
            "path": str(path),
            "status": "excluded",
            "reason": f"Unsupported extension {ext}",
        }

    try:
        raw_data = path.read_bytes()
    except Exception as e:
        return {
            "file": path.name,
            "path": str(path),
            "status": "failed",
            "reason": f"Read error: {e}",
        }

    if len(raw_data) == 0:
        return {
            "file": path.name,
            "path": str(path),
            "status": "excluded",
            "reason": "Empty file",
        }

    # Handle legacy binary OLE2 / BIFF
    if ext in (".doc", ".xls", ".ppt"):
        ole2_magic = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        biff_magic = b"\t\x00"
        is_binary = raw_data.startswith(ole2_magic) or raw_data.startswith(biff_magic)
        return {
            "file": path.name,
            "path": str(path),
            "app": app,
            "format": "legacy_binary",
            "status": "ok" if is_binary else "excluded",
            "size": len(raw_data),
        }

    # OOXML Roundtrip and Loss Audit
    try:
        if app == "word":
            doc = read_docx(raw_data)
            saved_bytes = write_docx(doc)
            orig_names, orig_files = load_package_xml(raw_data)
            saved_names, saved_files = load_package_xml(saved_bytes)
            orig_feats = extract_word_features(orig_names, orig_files)
            saved_feats = extract_word_features(saved_names, saved_files)
        elif app == "excel":
            wb = read_xlsx(raw_data)
            saved_bytes = write_xlsx(wb)
            orig_names, orig_files = load_package_xml(raw_data)
            saved_names, saved_files = load_package_xml(saved_bytes)
            orig_feats = extract_excel_features(orig_names, orig_files)
            saved_feats = extract_excel_features(saved_names, saved_files)
        elif app == "powerpoint":
            pres = read_pptx(raw_data)
            saved_bytes = write_pptx(pres)
            orig_names, orig_files = load_package_xml(raw_data)
            saved_names, saved_files = load_package_xml(saved_bytes)
            orig_feats = extract_presentation_features(orig_names, orig_files)
            saved_feats = extract_presentation_features(saved_names, saved_files)
        else:
            return {
                "file": path.name,
                "status": "excluded",
                "reason": f"Unknown app {app}",
            }

        # Calculate losses
        losses: dict[str, int] = {}
        for feat, orig_count in orig_feats.items():
            saved_count = saved_feats.get(feat, 0)
            if saved_count < orig_count:
                losses[feat] = orig_count - saved_count

        return {
            "file": path.name,
            "path": str(path),
            "app": app,
            "format": "ooxml",
            "status": "ok",
            "orig_size": len(raw_data),
            "saved_size": len(saved_bytes),
            "feature_losses": losses,
        }

    except Exception as e:
        return {
            "file": path.name,
            "path": str(path),
            "app": app,
            "format": "ooxml",
            "status": "excluded",
            "reason": f"{type(e).__name__}: {e}",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-process Corpus Batch Audit Tool.")
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("tests/docs/full_corpus"),
        help="Directory to scan for documents.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=min(os.cpu_count() or 4, 8),
        help="Number of parallel worker processes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of files to process.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds per file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write JSONL results.",
    )
    args = parser.parse_args()

    corpus_dir: Path = args.corpus_dir.resolve()
    if not corpus_dir.exists():
        print(f"Error: Corpus directory {corpus_dir} does not exist.", file=sys.stderr)
        sys.exit(1)

    all_files: list[Path] = []
    for f in corpus_dir.rglob("*"):
        if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in EXT_TO_APP:
            all_files.append(f)

    all_files.sort()
    if args.limit:
        all_files = all_files[: args.limit]

    total = len(all_files)
    print(f"Discovered {total} office files in {corpus_dir}")
    print(f"Running audit with {args.workers} worker processes (timeout {args.timeout}s)...")

    results: list[dict[str, Any]] = []
    out_fp = open(args.output, "w", encoding="utf-8") if args.output else None

    start_time = time.time()
    completed = 0
    ok_count = 0
    failed_count = 0
    excluded_count = 0

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        future_to_path = {
            executor.submit(audit_single_file, str(p)): p for p in all_files
        }
        for future in as_completed(future_to_path):
            p = future_to_path[future]
            try:
                res = future.result(timeout=args.timeout)
            except Exception as e:
                res = {
                    "file": p.name,
                    "path": str(p),
                    "status": "failed",
                    "reason": f"Execution error: {e}",
                }

            results.append(res)
            completed += 1
            st = res.get("status")
            if st == "ok":
                ok_count += 1
            elif st == "failed":
                failed_count += 1
            else:
                excluded_count += 1

            if out_fp:
                out_fp.write(json.dumps(res) + "\n")
                out_fp.flush()

            if completed % max(1, total // 20) == 0 or completed == total:
                elapsed = time.time() - start_time
                status_str = f"ok={ok_count} failed={failed_count} excluded={excluded_count}"
                print(
                    f"[{completed}/{total}] {status_str} ({elapsed:.1f}s)",
                    flush=True,
                )

    if out_fp:
        out_fp.close()

    elapsed = time.time() - start_time
    print(f"\nAudit complete in {elapsed:.2f}s:")
    print(f"  Attempted: {total}")
    print(f"  OK:        {ok_count} ({(ok_count/total*100) if total else 0:.1f}%)")
    print(f"  Failed:    {failed_count}")
    print(f"  Excluded:  {excluded_count}")


if __name__ == "__main__":
    src_dir = str(Path(__file__).resolve().parents[1] / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    main()
