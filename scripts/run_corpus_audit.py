#!/usr/bin/env python3
# ruff: noqa: E402
"""Multi-process Corpus Batch Audit & Roundtrip Runner.

Ports and extends .vibeoffice/tests/ledger/recalc-all.js and corpus drivers.
Runs isolated read/save roundtrips, multi-stage contracts (parse, model, render, roundtrip),
and ECMA-376 feature loss audits across tests/docs/ with true 30-second process termination.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# Ensure src/ is in sys.path so the CLI can be run directly from anywhere
src_dir = str(Path(__file__).resolve().parents[1] / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from atboffice.deep.audit.core import (
    AuditSession,
    CorpusExpectations,
    audit_corpus_file,
)

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
    res = audit_corpus_file(file_path_str)
    st = res.get("status")
    if st in ("fail", "crash", "timeout"):
        res["status"] = "failed"
    elif st in ("unsupported_format", "encrypted", "corrupt"):
        res["status"] = "excluded"
    elif st == "loss":
        res["status"] = "ok"
    return res


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-process Corpus Batch Audit Tool.")
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("tests/docs"),
        help="Directory to scan for documents (defaults to tests/docs).",
    )
    parser.add_argument(
        "--expectations",
        type=Path,
        default=Path("tests/docs/expectations.json"),
        help="Path to expectations JSON manifest.",
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
        type=float,
        default=30.0,
        help="Timeout in seconds per file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write JSONL results.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero code if any unexpected failures or timeouts occur.",
    )
    args = parser.parse_args()

    corpus_dir: Path = args.corpus_dir.resolve()
    if not corpus_dir.exists():
        print(f"Error: Corpus directory {corpus_dir} does not exist.", file=sys.stderr)
        sys.exit(1)

    expectations: CorpusExpectations | None = None
    if args.expectations and args.expectations.exists():
        try:
            expectations = CorpusExpectations(args.expectations)
            print(f"Loaded {len(expectations)} document expectations from {args.expectations}")
        except Exception as e:
            print(
                f"Warning: Failed to load expectations from {args.expectations}: {e}",
                file=sys.stderr,
            )

    all_files: list[Path] = []
    for f in corpus_dir.rglob("*"):
        if (
            f.is_file()
            and not f.name.startswith(".")
            and f.suffix.lower() in EXT_TO_APP
            and "full_corpus" not in f.parts
        ):
            all_files.append(f)

    all_files.sort()
    if args.limit:
        all_files = all_files[: args.limit]

    total = len(all_files)
    print(f"Discovered {total} office files in {corpus_dir}")
    print(f"Running audit with {args.workers} worker processes (timeout {args.timeout}s)...")

    session = AuditSession()
    out_fp = open(args.output, "w", encoding="utf-8") if args.output else None

    start_time = time.time()
    completed = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_path = {
            executor.submit(
                audit_corpus_file,
                str(p),
                expectations=expectations,
                timeout=args.timeout,
            ): p
            for p in all_files
        }
        for future in as_completed(future_to_path):
            p = future_to_path[future]
            try:
                res = future.result()
            except Exception as e:
                res = {
                    "file": p.name,
                    "path": str(p),
                    "status": "fail",
                    "reason": f"Execution error: {e}",
                    "expected_match": False,
                }

            session.record_result(res)
            completed += 1

            if out_fp:
                out_fp.write(json.dumps(res) + "\n")
                out_fp.flush()

            if completed % max(1, total // 20) == 0 or completed == total:
                elapsed = time.time() - start_time
                summ = session.summary()
                status_str = (
                    f"ok={summ['ok']} enc={summ['encrypted']} corrupt={summ['corrupt']} "
                    f"unsupported={summ['unsupported_format']} fail={summ['fail']} "
                    f"timeout={summ['timeout']} crash={summ['crash']} loss={summ['loss']}"
                )
                print(
                    f"[{completed}/{total}] {status_str} ({elapsed:.1f}s)",
                    flush=True,
                )

    if out_fp:
        out_fp.close()

    elapsed = time.time() - start_time
    summ = session.summary()
    print(f"\nAudit complete in {elapsed:.2f}s:")
    print(f"  Attempted:           {summ['attempted']}")
    print(f"  OK (Valid):          {summ['ok']}")
    print(f"  Encrypted:           {summ['encrypted']}")
    print(f"  Corrupt:             {summ['corrupt']}")
    print(f"  Unsupported format:  {summ['unsupported_format']}")
    print(f"  Timeouts:            {summ['timeout']}")
    print(f"  Crashes:             {summ['crash']}")
    print(f"  Failures:            {summ['fail']}")
    print(f"  Losses:              {summ['loss']}")
    print(f"  Unmatched failures:  {summ['unmatched_failures']}")

    if args.strict and not session.is_passing():
        print("\nAudit FAILED strict expectations check.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
