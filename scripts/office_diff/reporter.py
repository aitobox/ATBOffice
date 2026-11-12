"""Deliverable report synthesizer and remediation task generator for office document diffs."""
# ruff: noqa: E402, E501

from __future__ import annotations

import datetime
from pathlib import Path

from .models import DiffResult


def _primary_score(item: DiffResult) -> float | None:
    """Return foreground-weighted score when available, falling back to legacy similarity."""
    return item.foreground_score if item.foreground_score is not None else item.similarity


def generate_task_card(
    task_num: int,
    item: DiffResult,
    priority: str = "medium",
    prev_task: str | None = None,
) -> str:
    """Generate a standard ATB Issue-Ready Remediation Task Card."""
    mod = item.app
    doc_file = item.file
    score = _primary_score(item)
    sim_str = f"{score * 100:.1f}%" if score is not None else "N/A"
    pixel_str = f"{item.similarity * 100:.1f}%" if item.similarity is not None else "N/A"
    notes = f"Foreground score {sim_str} (pixel MAE sim {pixel_str}, category: {item.category}) in {doc_file}"
    if item.error:
        notes += f" - {item.error}"

    target_map = {
        "word": [
            "src/atboffice/modules/writer/views/",
            "src/atboffice/modules/writer/layout/",
            "src/atboffice/modules/writer/io/",
        ],
        "excel": [
            "src/atboffice/modules/spreadsheet/views/",
            "src/atboffice/modules/spreadsheet/models/",
            "src/atboffice/modules/spreadsheet/io/",
        ],
        "powerpoint": [
            "src/atboffice/modules/presentation/views/",
            "src/atboffice/modules/presentation/panes/",
            "src/atboffice/modules/presentation/io/",
        ],
    }
    targets = target_map.get(mod, ["src/atboffice/modules/"])

    depends_on = f"`[{prev_task}]`" if prev_task else "None (Root task)"
    card_id = f"TASK-DOC-{task_num:02d}"

    card = f"""### [{card_id}] fix({mod}): Resolve rendering discrepancy in `{doc_file}`
- **Parent Epic**: Document Rendering Parity ({priority.upper()} Remediation)
- **Step**: Step {task_num} of N (Remediation Sequence)
- **Labels**: `type: bug`, `area: rendering`, `priority: {priority}`
- **Depends On**: {depends_on}
- **Blocks**: None
- **Target Files**:
"""
    for t in targets:
        card += f"  - `{t}`\n"

    diff_display = item.diff_path or "N/A"

    card += f"""- **Scope & Specification**:
  - Sample document: `{doc_file}`
  - Observed Divergence: {notes}
  - Visual Diff: `{diff_display}`
  - Baseline size: {item.orig_size}, Candidate size: {item.target_size}
- **Acceptance Criteria**:
  - [ ] 1. Document `{doc_file}` renders without errors or blank areas.
  - [ ] 2. Visual similarity with reference baseline improves to >= 90%.
  - [ ] 3. Automated regression test added in `tests/`.
"""
    return card


def generate_report(
    results: list[DiffResult],
    out_path: Path,
    min_similarity: float = 0.90,
    min_single: float = 0.85,
) -> str:
    """Generate complete OFFICE_DOCS_DIFF.md deliverable from diff metrics."""
    now_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    total = len(results)
    comparable = [r for r in results if _primary_score(r) is not None]
    incomparable = [r for r in results if _primary_score(r) is None]

    avg_sim = (
        sum(_primary_score(r) or 0.0 for r in comparable) / len(comparable)
        if comparable
        else 0.0
    )
    pixel_comparable = [r for r in results if r.similarity is not None]
    avg_pixel_sim = (
        sum(r.similarity or 0.0 for r in pixel_comparable) / len(pixel_comparable)
        if pixel_comparable
        else 0.0
    )

    parity_matches = sum(1 for r in results if r.category == "PARITY_MATCH")
    cosmetic_minors = sum(1 for r in results if r.category == "COSMETIC_MINOR")
    layout_drifts = sum(1 for r in results if r.category == "LAYOUT_DRIFT")
    critical_mismatches = sum(1 for r in results if r.category == "CRITICAL_MISMATCH")
    incomparable_sizes = sum(1 for r in results if r.category == "INCOMPARABLE_SIZE")
    missing_count = sum(1 for r in results if r.category == "MISSING")

    # Quality Gate Verdict
    meets_avg = avg_sim >= min_similarity if comparable else False
    failing_singles = [r for r in comparable if (_primary_score(r) or 0.0) < min_single]
    gate_passed = meets_avg and len(failing_singles) == 0 and len(incomparable) == 0

    verdict_badge = "✅ PASS" if gate_passed else "⚠️ NEEDS_REMEDIATION"

    lines: list[str] = [
        "# ATBOffice vs. VibeOffice Visual Document Rendering Parity Report",
        "",
        f"> **Generated**: {now_str}  ",
        f"> **Quality Gate Verdict**: **{verdict_badge}** (Target: Avg >= {min_similarity*100:.1f}%, Single >= {min_single*100:.1f}%)",
        "",
        "## 1. Executive Summary",
        "",
        "| Metric | Value | Target / Requirement |",
        "|---|---|---|",
        f"| **Evaluated Documents** | `{total}` | 73 Core Supported OOXML |",
        f"| **Comparable Documents** | `{len(comparable)}` | Size & Region Aligned |",
        f"| **Incomparable / Missing** | `{len(incomparable)}` | 0 Blockers |",
        f"| **Average Visual Similarity** | `{avg_sim*100:.2f}%` | >= {min_similarity*100:.1f}% (Foreground-Weighted) |",
        f"| **Average Pixel Similarity (MAE)** | `{avg_pixel_sim*100:.2f}%` | Secondary Reference |",
        f"| **Parity Matches (>=95%)** | `{parity_matches}` | High Fidelity |",
        f"| **Cosmetic Minor (85%-95%)** | `{cosmetic_minors}` | Acceptable |",
        f"| **Layout Drifts (70%-85%)** | `{layout_drifts}` | Needs Polish |",
        f"| **Critical Mismatches (<70%)** | `{critical_mismatches}` | P0/P1 Defects |",
        f"| **Size Incomparable** | `{incomparable_sizes}` | Viewport Alignment Required |",
        f"| **Missing Files** | `{missing_count}` | 0 Missing |",
        "",
        "---",
        "",
        "## 2. Partitioning & Guardrails",
        "",
        "- **73 Core Supported OOXML Documents** (`.docx`, `.xlsx`, `.pptx`): Evaluated for visual canvas fidelity.",
        "- **77 Legacy Binary & Corrupt Documents** (`.doc`, `.xls`, `.ppt`): Strictly separated; require real application error-dialog and integrity verification per 2026-11-06 audit.",
        "- **Dimension & Viewport Guardrail**: Missing images or dimension mismatches are reported as `INCOMPARABLE_SIZE` without artificial scores.",
        "",
        "---",
        "",
        "## 3. Detailed Results by Document",
        "",
        "| App | File | Category | Foreground | Recall | Precision | Color Hist | Pixel Sim (MAE) | MAE | Baseline Size | ATB Size | Diff Map |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    def _fmt_pct(val: float | None) -> str:
        return f"{val * 100:.1f}%" if val is not None else "N/A"

    for r in sorted(results, key=lambda x: (x.app, x.file)):
        fg_text = _fmt_pct(_primary_score(r))
        rec_text = _fmt_pct(r.recall)
        prec_text = _fmt_pct(r.precision)
        hist_text = _fmt_pct(r.color_hist_similarity)
        pix_text = _fmt_pct(r.similarity)
        diff_text = f"[`diff`]({r.diff_path})" if r.diff_path else "-"
        orig_s = f"{r.orig_size[0]}x{r.orig_size[1]}" if r.orig_size != (0, 0) else "-"
        target_s = f"{r.target_size[0]}x{r.target_size[1]}" if r.target_size != (0, 0) else "-"
        lines.append(
            f"| {r.app} | `{r.file}` | `{r.category}` | **{fg_text}** | {rec_text} | {prec_text} | {hist_text} | {pix_text} | {r.mae:.1f} | {orig_s} | {target_s} | {diff_text} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Remediation Action Cards",
        "",
    ])

    remediation_items = [r for r in results if r.category in ("CRITICAL_MISMATCH", "LAYOUT_DRIFT", "INCOMPARABLE_SIZE")][:10]
    if remediation_items:
        prev_card = None
        for i, item in enumerate(remediation_items, start=1):
            prio = "high" if item.category == "CRITICAL_MISMATCH" else "medium"
            card = generate_task_card(i, item, priority=prio, prev_task=prev_card)
            lines.append(card)
            prev_card = f"TASK-DOC-{i:02d}"
    else:
        lines.append("No active visual rendering defects detected. All evaluated documents meet parity thresholds.")

    content = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return content
