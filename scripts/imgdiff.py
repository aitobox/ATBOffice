#!/usr/bin/env python3
# ruff: noqa: E402, E501
"""Visual similarity and image difference analysis tool for ATBOffice (TASK-701 / Issue #235).

Compares PySide6 rendered screenshots with .vibeoffice/screenshots/ baselines,
calculating dual metrics:
- Pixel MAE Similarity (normalized pixel difference: 1.0 - MAE / 255)
- Central ROI Similarity (Region-Of-Interest comparison for dialog/toolbars)
Strictly avoids conflating Pixel MAE with Structural Similarity (SSIM).
Uses pure PySide6 and standard library (zero external third-party dependencies).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

repo_root = Path(__file__).resolve().parent.parent


class DiffResult(NamedTuple):
    module: str
    filename: str
    pixel_mae_similarity: float
    roi_similarity: float
    similarity: float  # Alias to pixel_mae_similarity for backward compatibility
    passed: bool
    atb_size: tuple[int, int]
    orig_size: tuple[int, int]


def compare_images(
    img_a_path: Path,
    img_b_path: Path,
    threshold: float = 0.85,
    sample_size: tuple[int, int] = (320, 200),
) -> DiffResult:
    """Compare two images using PySide6 and return dual similarity metrics and pass status."""
    img_a = QImage(str(img_a_path))
    img_b = QImage(str(img_b_path))

    if img_a.isNull() or img_b.isNull():
        return DiffResult(
            module=img_a_path.parent.name,
            filename=img_a_path.name,
            pixel_mae_similarity=0.0,
            roi_similarity=0.0,
            similarity=0.0,
            passed=False,
            atb_size=(img_a.width(), img_a.height()),
            orig_size=(img_b.width(), img_b.height()),
        )

    size_a = (img_a.width(), img_a.height())
    size_b = (img_b.width(), img_b.height())

    # Rescale both images to sample_size for fast and normalized pixel comparison
    scaled_a = img_a.scaled(
        sample_size[0], sample_size[1], Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
    ).convertToFormat(QImage.Format.Format_RGB888)

    scaled_b = img_b.scaled(
        sample_size[0], sample_size[1], Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
    ).convertToFormat(QImage.Format.Format_RGB888)

    bytes_a = bytes(scaled_a.constBits())
    bytes_b = bytes(scaled_b.constBits())

    # 1. Whole image Pixel MAE comparison
    min_len = min(len(bytes_a), len(bytes_b))
    if min_len == 0:
        pixel_mae_sim = 0.0
    else:
        diff_sum = sum(abs(a - b) for a, b in zip(bytes_a[:min_len], bytes_b[:min_len]))
        pixel_mae_sim = 1.0 - (diff_sum / (min_len * 255.0))

    # 2. Central Region-Of-Interest (ROI) comparison (middle 60% x 60%)
    roi_w = int(sample_size[0] * 0.6)
    roi_h = int(sample_size[1] * 0.6)
    roi_x = int(sample_size[0] * 0.2)
    roi_y = int(sample_size[1] * 0.2)

    roi_a = scaled_a.copy(roi_x, roi_y, roi_w, roi_h)
    roi_b = scaled_b.copy(roi_x, roi_y, roi_w, roi_h)

    roi_bytes_a = bytes(roi_a.constBits())
    roi_bytes_b = bytes(roi_b.constBits())
    min_roi_len = min(len(roi_bytes_a), len(roi_bytes_b))

    if min_roi_len == 0:
        roi_sim = 0.0
    else:
        roi_diff_sum = sum(abs(a - b) for a, b in zip(roi_bytes_a[:min_roi_len], roi_bytes_b[:min_roi_len]))
        roi_sim = 1.0 - (roi_diff_sum / (min_roi_len * 255.0))

    # Pass condition requires both full-image and ROI to meet threshold
    passed = pixel_mae_sim >= threshold and roi_sim >= threshold

    return DiffResult(
        module=img_a_path.parent.name,
        filename=img_a_path.name,
        pixel_mae_similarity=pixel_mae_sim,
        roi_similarity=roi_sim,
        similarity=pixel_mae_sim,
        passed=passed,
        atb_size=size_a,
        orig_size=size_b,
    )


def generate_report(results: list[DiffResult], threshold: float = 0.85) -> str:
    """Generate Markdown comparison report distinguishing Pixel MAE from ROI metrics."""
    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    avg_pixel_mae = (sum(r.pixel_mae_similarity for r in results) / total) if total > 0 else 0.0
    avg_roi = (sum(r.roi_similarity for r in results) / total) if total > 0 else 0.0

    lines = [
        "# ATBOffice vs. VibeOffice UI 图像差异对比报告 (imgdiff)",
        "",
        "> [!NOTE]",
        "> 本报告严格区分 **Pixel MAE 相似度** 与 **ROI 核心区几何相似度**，不将归一化 MAE 宣称为结构相似度 (SSIM)。",
        "",
        "- **对比对标基准**: `.vibeoffice/screenshots/`",
        f"- **对比样本总数**: {total}",
        f"- **判定阈值**: `{threshold:.2f}` (Pixel MAE & ROI >= {threshold * 100:.0f}%)",
        f"- **平均 Pixel MAE 相似度**: `{avg_pixel_mae * 100:.2f}%`",
        f"- **平均 ROI 核心区相似度**: `{avg_roi * 100:.2f}%`",
        f"- **达标总数 (Pass)**: {passed_count} / {total} (`{(passed_count / total * 100.0) if total > 0 else 0.0:.1f}%`)",
        "",
        "## 1. 模块相似度汇总",
        "",
        "| 模块 | 对比截图数 | 达标数 | 平均 Pixel MAE | 平均 ROI 相似度 | 状态 |",
        "|---|---|---|---|---|---|",
    ]

    # Group by module
    modules: dict[str, list[DiffResult]] = {}
    for r in results:
        modules.setdefault(r.module, []).append(r)

    for mod in sorted(modules.keys()):
        m_results = modules[mod]
        m_total = len(m_results)
        m_passed = sum(1 for r in m_results if r.passed)
        m_avg_mae = sum(r.pixel_mae_similarity for r in m_results) / m_total if m_total > 0 else 0.0
        m_avg_roi = sum(r.roi_similarity for r in m_results) / m_total if m_total > 0 else 0.0
        status = "✅ 达标 (Pass)" if (m_avg_mae >= threshold and m_avg_roi >= threshold) else "⚠️ 需关注 (Review)"
        lines.append(
            f"| **{mod}** | {m_total} | {m_passed} / {m_total} | `{m_avg_mae * 100:.2f}%` | `{m_avg_roi * 100:.2f}%` | {status} |"
        )

    lines.extend([
        "",
        "## 2. 逐图详细对比结果",
        "",
        "| # | 模块 | 截图文件名 | PySide6 尺寸 | 原版尺寸 | Pixel MAE 相似度 | ROI 相似度 | 判定结果 |",
        "|---|---|---|---|---|---|---|---|",
    ])

    for i, r in enumerate(results, 1):
        status_badge = "✅ PASS" if r.passed else "⚠️ REVIEW"
        lines.append(
            f"| {i} | `{r.module}` | `{r.filename}` | {r.atb_size[0]}×{r.atb_size[1]} | "
            f"{r.orig_size[0]}×{r.orig_size[1]} | `{r.pixel_mae_similarity * 100:.2f}%` | `{r.roi_similarity * 100:.2f}%` | {status_badge} |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="ATBOffice Screenshot imgdiff analyzer")
    parser.add_argument(
        "evidence_dir",
        type=Path,
        nargs="?",
        default=repo_root / "docs" / "clone" / "evidence" / "phase6",
        help="Path to phase evidence directory",
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=repo_root / ".vibeoffice" / "screenshots",
        help="Path to .vibeoffice/screenshots baseline directory",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Similarity pass threshold (default: 0.85)",
    )
    parser.add_argument(
        "--report-name",
        type=str,
        default="IMGDIFF_REPORT.md",
        help="Output report markdown filename",
    )

    args = parser.parse_args()

    evidence_dir = args.evidence_dir
    baseline_dir = args.baseline_dir
    threshold = args.threshold
    screenshots_dir = evidence_dir / "screenshots"

    if not screenshots_dir.exists():
        print(f"Error: Screenshots directory not found: {screenshots_dir}")
        sys.exit(1)

    print("Running imgdiff comparison with dual metrics (Pixel MAE & ROI)...")
    print(f"Evidence: {screenshots_dir}")
    print(f"Baseline: {baseline_dir}")
    print(f"Threshold: {threshold}")

    atb_images = sorted(screenshots_dir.rglob("*.png"))
    if not atb_images:
        print(f"No PNG screenshots found in {screenshots_dir}")
        sys.exit(1)

    results: list[DiffResult] = []
    for atb_img in atb_images:
        rel = atb_img.relative_to(screenshots_dir)
        orig_img = baseline_dir / rel

        if not orig_img.exists():
            continue

        res = compare_images(atb_img, orig_img, threshold=threshold)
        results.append(res)
        tag = "PASS" if res.passed else "REVIEW"
        print(f"[{tag}] {rel}: MAE={res.pixel_mae_similarity * 100:.2f}%, ROI={res.roi_similarity * 100:.2f}%")

    report_path = evidence_dir / args.report_name
    report_content = generate_report(results, threshold=threshold)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"Report generated at: {report_path}")
    avg_score = (sum(r.pixel_mae_similarity for r in results) / len(results)) if results else 0.0
    print(f"\nCompleted {len(results)} image comparisons. Average Pixel MAE similarity: {avg_score * 100:.2f}%")


if __name__ == "__main__":
    main()
