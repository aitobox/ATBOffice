#!/usr/bin/env python3
# ruff: noqa: E402, E501
"""Visual similarity and image difference analysis tool for ATBOffice.

Compares PySide6 rendered screenshots with .vibeoffice/screenshots/ baselines,
calculating structural similarity scores and generating structured comparison reports.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

import numpy as np
from PIL import Image

repo_root = Path(__file__).resolve().parent.parent


class DiffResult(NamedTuple):
    module: str
    filename: str
    similarity: float
    passed: bool
    atb_size: tuple[int, int]
    orig_size: tuple[int, int]


def compare_images(img_a_path: Path, img_b_path: Path, threshold: float = 0.9) -> DiffResult:
    """Compare two images and return similarity score and pass status."""
    img_a = Image.open(img_a_path).convert("RGB")
    img_b = Image.open(img_b_path).convert("RGB")

    size_a = img_a.size
    size_b = img_b.size

    # Scale to match dimensions if needed (e.g. 2880x1800 vs 1440x900)
    target_size = (min(size_a[0], size_b[0]), min(size_a[1], size_b[1]))
    if img_a.size != target_size:
        img_a = img_a.resize(target_size, Image.Resampling.BILINEAR)
    if img_b.size != target_size:
        img_b = img_b.resize(target_size, Image.Resampling.BILINEAR)

    arr_a = np.asarray(img_a, dtype=np.float32)
    arr_b = np.asarray(img_b, dtype=np.float32)

    # Mean absolute difference normalized to [0, 1]
    diff = np.abs(arr_a - arr_b)
    mad = np.mean(diff) / 255.0
    similarity = max(0.0, min(1.0, 1.0 - mad))

    passed = similarity >= threshold
    mod = img_a_path.parent.name
    return DiffResult(
        module=mod,
        filename=img_a_path.name,
        similarity=float(similarity),
        passed=passed,
        atb_size=size_a,
        orig_size=size_b,
    )


def generate_report(results: list[DiffResult], threshold: float, report_path: Path):
    """Write comprehensive markdown imgdiff report."""
    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    pass_rate = (passed_count / total * 100) if total > 0 else 100.0
    avg_score = (sum(r.similarity for r in results) / total) if total > 0 else 1.0

    lines = [
        "# ATBOffice vs. VibeOffice UI 图像差异对比报告 (imgdiff)",
        "",
        "- **对比对标基准**: `.vibeoffice/screenshots/`",
        f"- **对比样本总数**: {total}",
        f"- **判定阈值**: `{threshold:.2f}` (Similarity >= {threshold * 100:.0f}%)",
        f"- **平均相似度**: `{avg_score * 100:.2f}%`",
        f"- **达标总数 (Pass)**: {passed_count} / {total} (`{pass_rate:.1f}%`)",
        "",
        "## 1. 模块相似度汇总",
        "",
        "| 模块 | 对比截图数 | 达标数 | 平均相似度 | 状态 |",
        "|---|---|---|---|---|",
    ]

    by_module: dict[str, list[DiffResult]] = {}
    for r in results:
        by_module.setdefault(r.module, []).append(r)

    for mod, mod_res in sorted(by_module.items()):
        m_pass = sum(1 for r in mod_res if r.passed)
        m_avg = sum(r.similarity for r in mod_res) / len(mod_res)
        m_status = "✅ 达标 (Pass)" if m_avg >= threshold else "⚠️ 需关注 (Review)"
        lines.append(f"| **{mod}** | {len(mod_res)} | {m_pass} / {len(mod_res)} | `{m_avg * 100:.2f}%` | {m_status} |")

    lines.extend([
        "",
        "## 2. 逐图详细对比结果",
        "",
        "| # | 模块 | 截图文件名 | PySide6 尺寸 | 原版尺寸 | 相似度得分 | 判定结果 |",
        "|---|---|---|---|---|---|---|",
    ])

    for i, r in enumerate(results, 1):
        status_badge = "✅ PASS" if r.passed else "⚠️ REVIEW"
        atb_sz = f"{r.atb_size[0]}×{r.atb_size[1]}"
        orig_sz = f"{r.orig_size[0]}×{r.orig_size[1]}"
        lines.append(
            f"| {i} | `{r.module}` | `{r.filename}` | {atb_sz} | {orig_sz} | `{r.similarity * 100:.2f}%` | {status_badge} |"
        )

    lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report generated at: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Calculate visual similarity difference between ATBOffice and baseline screenshots.")
    parser.add_argument("target_dir", nargs="?", default=None, help="Directory containing screenshots or evidence directory")
    parser.add_argument("--threshold", type=float, default=0.9, help="Similarity pass threshold (default: 0.9)")
    parser.add_argument("--baseline-dir", default=str(repo_root / ".vibeoffice" / "screenshots"), help="Baseline screenshots directory")
    parser.add_argument("--evidence-dir", default=None, help="Evidence screenshots directory")
    parser.add_argument("--report-path", default=None, help="Path to write output markdown report")
    args = parser.parse_args()

    # Resolve evidence dir
    evidence_dir = None
    if args.evidence_dir:
        evidence_dir = Path(args.evidence_dir)
    elif args.target_dir:
        t_path = Path(args.target_dir)
        if (t_path / "screenshots").exists():
            evidence_dir = t_path / "screenshots"
        else:
            evidence_dir = t_path
    else:
        evidence_dir = repo_root / "docs" / "clone" / "evidence" / "phase6" / "screenshots"

    baseline_dir = Path(args.baseline_dir)

    if not evidence_dir.exists():
        print(f"Error: Evidence directory {evidence_dir} does not exist.")
        sys.exit(1)
    if not baseline_dir.exists():
        print(f"Error: Baseline directory {baseline_dir} does not exist.")
        sys.exit(1)

    report_path = (
        Path(args.report_path)
        if args.report_path
        else (evidence_dir.parent / "IMGDIFF_REPORT.md")
    )

    print("Running imgdiff comparison...")
    print(f"Evidence: {evidence_dir}")
    print(f"Baseline: {baseline_dir}")
    print(f"Threshold: {args.threshold}")

    # Gather matching pngs
    evidence_pngs = sorted(evidence_dir.glob("*/*.png"))
    if not evidence_pngs:
        # Check flat dir
        evidence_pngs = sorted(evidence_dir.glob("*.png"))

    if not evidence_pngs:
        print(f"No PNG files found in {evidence_dir}")
        sys.exit(1)

    results: list[DiffResult] = []
    for ep in evidence_pngs:
        rel = ep.relative_to(evidence_dir)
        bp = baseline_dir / rel
        if not bp.exists():
            continue
        res = compare_images(ep, bp, threshold=args.threshold)
        results.append(res)
        status_str = "PASS" if res.passed else "REVIEW"
        print(f"[{status_str}] {rel}: {res.similarity * 100:.2f}%")

    if not results:
        print("Warning: No matching baseline files found to compare.")
        sys.exit(0)

    generate_report(results, args.threshold, report_path)
    avg_score = sum(r.similarity for r in results) / len(results)
    print(f"\nCompleted {len(results)} image comparisons. Average similarity: {avg_score * 100:.2f}%")


if __name__ == "__main__":
    main()
