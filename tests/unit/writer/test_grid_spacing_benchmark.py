"""Benchmark regression tests for Word document line grid spacing (Issue #11).

Validates compute_grid_line_height against all 90 Microsoft Word PDF rasterized line heights
from tests/fixtures/benchmarks/word.json.
Ported from .vibeoffice/tests/from-issues/11/grid-spacing.test.mjs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atboffice.modules.writer.layout.portions import compute_grid_line_height

BENCHMARK_FILE = Path(__file__).resolve().parents[2] / "fixtures" / "benchmarks" / "word.json"


@pytest.fixture(scope="module")
def word_benchmark() -> dict:
    if not BENCHMARK_FILE.exists():
        pytest.skip(f"Benchmark file not found: {BENCHMARK_FILE}")
    with open(BENCHMARK_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_issue_11_specific_cases():
    """Issue 11: 14pt text at 1.7 lines takes two pitches of a 15.6pt grid (31.2pt).

    1.5 lines of smaller text takes 1.5 pitches (23.4pt).
    """
    assert compute_grid_line_height(15.6, 1.7, 14.0, "Times New Roman") == 31.2
    assert compute_grid_line_height(15.6, 1.5, 10.5, "SimSun") == 23.4


def test_all_90_word_linegrid_benchmark_cases(word_benchmark: dict):
    """Verify compute_grid_line_height against all 90 Word-rendered cases.

    Tolerance is within 0.15pt.
    """
    lines = word_benchmark.get("lines", {})
    assert len(lines) == 90, f"Expected 90 benchmark cases, found {len(lines)}"

    for key, expected_pt in lines.items():
        # Key format: "[pitch/sz/mult]" e.g. "[15.6/14/1.7]"
        parts = key.strip("[]").split("/")
        pitch = float(parts[0])
        sz = float(parts[1])
        mult = float(parts[2])

        computed_pt = compute_grid_line_height(pitch, mult, sz, "Times New Roman")
        assert abs(computed_pt - expected_pt) < 0.15, (
            f"Case {key}: computed {computed_pt}pt, Word reference {expected_pt}pt"
        )
