#!/usr/bin/env python3
# ruff: noqa: E402, E501
"""Standardized office document visual rendering diff and parity verification runner.

Usage:
    python scripts/run_office_diff.py --all
    python scripts/run_office_diff.py --app word
    python scripts/run_office_diff.py --file tests/docs/word/docx/sample.docx
    python scripts/run_office_diff.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add repo root and src to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.office_diff.capture import run_isolated_capture
from scripts.office_diff.comparator import compare_canvases
from scripts.office_diff.corpus import load_expectations, partition_corpus
from scripts.office_diff.models import DiffResult, DocumentTarget
from scripts.office_diff.reporter import generate_report


def _resolve_audit_subdir(user_dir: str | None, repo_root: Path, sub: str, fallbacks: list[Path]) -> Path:
    """Locate the newest available audit screenshot directory or fallback."""
    if user_dir:
        return Path(user_dir).resolve()
    audit_dirs = sorted(
        (p / sub for p in (repo_root / "screenshots").glob("office_audit_*") if (p / sub).is_dir()),
        reverse=True,
    )
    candidates = [*audit_dirs, *fallbacks]
    best_dir = candidates[0] if candidates else (repo_root / "screenshots" / sub)
    max_count = -1
    for c in candidates:
        if c.exists():
            cnt = len(list(c.rglob("*.png")))
            if cnt > max_count:
                max_count = cnt
                best_dir = c
                if cnt >= 73 and c in audit_dirs:
                    break
    return best_dir


def resolve_baseline_dir(user_dir: str | None, repo_root: Path) -> Path:
    """Find the best available baseline screenshot directory."""
    return _resolve_audit_subdir(
        user_dir,
        repo_root,
        "vibeoffice",
        [
            repo_root / "screenshots" / "vibeoffice_docs",
            repo_root / "tests" / "docs" / "baselines",
        ],
    )


def resolve_candidate_dir(user_dir: str | None, repo_root: Path) -> Path:
    """Find or create candidate screenshot directory with highest available snapshot count."""
    return _resolve_audit_subdir(
        user_dir,
        repo_root,
        "atboffice",
        [repo_root / "screenshots" / "atboffice_docs"],
    )


def run_diff_suite(
    targets: list[DocumentTarget],
    baseline_dir: Path,
    candidate_dir: Path,
    diff_dir: Path,
    do_capture: bool = False,
    normalize_size: bool = False,
    canvas_only: bool = False,
    timeout: int = 30,
) -> list[DiffResult]:
    """Execute capture (optional) and visual diff comparison across document targets."""
    results: list[DiffResult] = []

    for idx, target in enumerate(targets, start=1):
        # 1. Capture candidate if requested
        if do_capture:
            print(f"[{idx}/{len(targets)}] Capturing {target.app}: {target.file} ...", end=" ", flush=True)
            cap_res = run_isolated_capture(
                target=target,
                out_dir=candidate_dir,
                timeout=timeout,
                canvas_only=canvas_only,
            )
            print(f"status={cap_res.status}")

        # 2. Locate baseline PNG
        orig_png = baseline_dir / target.app / f"{target.file}.png"
        if not orig_png.exists():
            # Check flat layout
            orig_png = baseline_dir / f"{target.file}.png"

        # 3. Locate candidate PNG
        cand_png = candidate_dir / target.app / f"{target.file}.png"
        if not cand_png.exists():
            cand_png = candidate_dir / f"{target.file}.png"

        diff_out = diff_dir / target.app / f"{target.file}_diff.png"

        diff_res = compare_canvases(
            orig_png=orig_png,
            target_png=cand_png,
            app=target.app,
            file_name=target.file,
            diff_out=diff_out,
            normalize_size=normalize_size,
        )
        results.append(diff_res)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ATBOffice Document Visual Diff and Parity Verification CLI"
    )
    parser.add_argument("--all", action="store_true", help="Run across all 73 supported OOXML documents")
    parser.add_argument("--app", choices=["word", "excel", "powerpoint"], help="Filter by application")
    parser.add_argument("--file", help="Path to single document to evaluate")
    parser.add_argument("--min-similarity", type=float, default=0.90, help="Global average similarity threshold (default: 0.90)")
    parser.add_argument("--min-single-similarity", type=float, default=0.85, help="Single file similarity threshold (default: 0.85)")
    parser.add_argument("--baseline-dir", help="Directory containing reference baseline PNGs")
    parser.add_argument("--candidate-dir", help="Directory containing candidate ATBOffice PNGs")
    parser.add_argument("--diff-dir", help="Directory for generated diff heatmap images")
    parser.add_argument("--out", help="Output path for markdown deliverable report")
    parser.add_argument("--capture", action="store_true", help="Perform offscreen capture before comparison")
    parser.add_argument("--score-only", action="store_true", help="Score existing screenshots without capturing")
    parser.add_argument("--json", help="Optional path to write diff results JSON")
    parser.add_argument("--canvas-only", action="store_true", help="Capture only inner document canvas")
    parser.add_argument("--normalize-size", action="store_true", help="Normalize sample dimensions during comparison")
    parser.add_argument("--strict", action="store_true", help="Exit with non-zero code if quality gates fail")
    parser.add_argument("--dry-run", action="store_true", help="Parse corpus and display plan without executing")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to evaluate")
    args = parser.parse_args()

    repo_root = REPO_ROOT
    docs_root = repo_root / "tests" / "docs"
    exp_file = docs_root / "expectations.json"

    if not exp_file.exists():
        print(f"Error: Expectations file not found at {exp_file}", file=sys.stderr)
        return 1

    expectations = load_expectations(exp_file)
    supported, unsupported = partition_corpus(expectations, docs_root)

    targets: list[DocumentTarget] = []
    if args.file:
        fpath = Path(args.file).resolve()
        app_name = args.app
        if not app_name:
            ext = fpath.suffix.lower()
            if ext in (".doc", ".docx", ".docm"):
                app_name = "word"
            elif ext in (".xls", ".xlsx", ".xlsm"):
                app_name = "excel"
            else:
                app_name = "powerpoint"
        targets = [
            DocumentTarget(
                file=fpath.name,
                path=fpath,
                format=fpath.suffix.lstrip(".").lower(),
                app=app_name,
                expected_status="ok",
                is_supported=True,
            )
        ]
    else:
        targets = supported
        if args.app:
            targets = [t for t in targets if t.app == args.app]

    if args.limit and args.limit > 0:
        targets = targets[: args.limit]

    baseline_dir = resolve_baseline_dir(args.baseline_dir, repo_root)
    candidate_dir = resolve_candidate_dir(args.candidate_dir, repo_root)
    if args.diff_dir:
        diff_dir = Path(args.diff_dir).resolve()
    elif baseline_dir.parent.name.startswith("office_audit_"):
        diff_dir = baseline_dir.parent / "diff"
    else:
        diff_dir = repo_root / "screenshots" / "docs_diff"
    report_out = Path(args.out).resolve() if args.out else (repo_root / "docs" / "clone" / "OFFICE_DOCS_DIFF.md")

    print("=== ATBOffice Document Visual Diff Runner ===")
    print(f"Corpus: {len(supported)} supported OOXML, {len(unsupported)} legacy/corrupt")
    print(f"Active targets: {len(targets)}")
    print(f"Baseline directory:  {baseline_dir}")
    print(f"Candidate directory: {candidate_dir}")
    print(f"Report output:       {report_out}")

    if args.dry_run:
        print("\n[DRY RUN] Target summary:")
        for t in targets[:5]:
            print(f"  - [{t.app}] {t.file} -> {t.path}")
        if len(targets) > 5:
            print(f"  ... and {len(targets) - 5} more.")
        print("[DRY RUN] Completed without modifications.")
        return 0

    do_capture = bool(args.capture and not args.score_only)
    results = run_diff_suite(
        targets=targets,
        baseline_dir=baseline_dir,
        candidate_dir=candidate_dir,
        diff_dir=diff_dir,
        do_capture=do_capture,
        normalize_size=args.normalize_size,
        canvas_only=args.canvas_only,
    )

    json_out = Path(args.json).resolve() if args.json else (diff_dir / "diff_results.json" if args.score_only else None)
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps([r.to_dict() for r in results], indent=2),
            encoding="utf-8",
        )
        print(f"JSON results written: {json_out}")

    generate_report(
        results=results,
        out_path=report_out,
        min_similarity=args.min_similarity,
        min_single=args.min_single_similarity,
    )

    print(f"\nReport generated: {report_out}")

    def _score_of(r: DiffResult) -> float | None:
        return r.foreground_score if r.foreground_score is not None else r.similarity

    comparable = [r for r in results if _score_of(r) is not None]
    avg_sim = (sum(_score_of(r) or 0.0 for r in comparable) / len(comparable)) if comparable else 0.0
    failing = [r for r in comparable if (_score_of(r) or 0.0) < args.min_single_similarity]
    incomp = [r for r in results if _score_of(r) is None]

    print(f"Summary: {len(comparable)}/{len(results)} comparable, foreground_avg={avg_sim*100:.2f}%")
    print(f"Status: {len(failing)} below single threshold, {len(incomp)} incomparable/missing")

    if args.strict and (avg_sim < args.min_similarity or len(failing) > 0 or len(incomp) > 0):
        print("Quality gate failed in strict mode.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
