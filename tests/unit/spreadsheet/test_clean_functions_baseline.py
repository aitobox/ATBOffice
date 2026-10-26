"""Precision baseline tests for 519 functions against .vibeoffice/tests/ledger/clean-functions.baseline.json."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.evaluator import evaluate

BASELINE_PATH = Path(".vibeoffice/tests/ledger/clean-functions.baseline.json")


@pytest.fixture(scope="module")
def baseline_data() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        pytest.skip("clean-functions.baseline.json not found")
    with open(BASELINE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def baseline_context() -> EvalContext:
    ctx = EvalContext()
    ctx.workbook_data = {"Sheet1": {}}

    a_vals = [3, 4, 5, 8, 9, 1, 2, 4, 5, 7.5]
    b_vals = [6, 19, 3, 2, 14, 4, 5, 17, 1, 2.5]
    c_vals = [58, 35, 11, 25, 10, 23]
    d_vals = [45.35, 47.65, 13.65, 32.4, 16.6, 4.75]

    for r, v in enumerate(a_vals):
        ctx.workbook_data["Sheet1"][(r, 0)] = v
    for r, v in enumerate(b_vals):
        ctx.workbook_data["Sheet1"][(r, 1)] = v
    for r, v in enumerate(c_vals):
        ctx.workbook_data["Sheet1"][(r, 2)] = v
    for r, v in enumerate(d_vals):
        ctx.workbook_data["Sheet1"][(r, 3)] = v

    return ctx


class TestCleanFunctionsBaseline:
    def test_vdb_and_ddb_precision(
        self, baseline_data: dict[str, Any], baseline_context: EvalContext
    ):
        vdb_items = {k: v for k, v in baseline_data.items() if k.startswith(("VDB(", "DDB("))}
        assert len(vdb_items) > 50

        passed = 0
        for expr, exp in vdb_items.items():
            got = evaluate("=" + expr, baseline_context)
            if hasattr(got, "error_code"):
                got = got.error_code

            if isinstance(exp, (int, float)) and isinstance(got, (int, float)):
                if abs(got - exp) <= 1e-9 or math.isclose(got, exp, rel_tol=1e-9, abs_tol=1e-9):
                    passed += 1
            elif str(got) == str(exp):
                passed += 1

        assert passed == len(vdb_items), f"VDB/DDB passed {passed}/{len(vdb_items)}"

    def test_erf_and_normal_family_precision(
        self, baseline_data: dict[str, Any], baseline_context: EvalContext
    ):
        norm_items = {
            k: v
            for k, v in baseline_data.items()
            if k.startswith(("ERF(", "ERFC(", "NORMSDIST(", "NORMSINV(", "GAUSS(", "PHI("))
        }
        assert len(norm_items) > 50

        passed = 0
        for expr, exp in norm_items.items():
            got = evaluate("=" + expr, baseline_context)
            if hasattr(got, "error_code"):
                got = got.error_code

            if isinstance(exp, (int, float)) and isinstance(got, (int, float)):
                tol = 1e-7 if "INV" in expr else 1e-9
                if math.isclose(got, exp, rel_tol=tol, abs_tol=1e-9):
                    passed += 1
            elif str(got) == str(exp):
                passed += 1

        assert passed / len(norm_items) >= 0.95

    def test_gamma_and_beta_precision(
        self, baseline_data: dict[str, Any], baseline_context: EvalContext
    ):
        gb_items = {
            k: v
            for k, v in baseline_data.items()
            if k.startswith(("GAMMA(", "GAMMALN(", "BETADIST(", "BETA.DIST("))
        }
        assert len(gb_items) > 30

        passed = 0
        for expr, exp in gb_items.items():
            got = evaluate("=" + expr, baseline_context)
            if hasattr(got, "error_code"):
                got = got.error_code

            if isinstance(exp, (int, float)) and isinstance(got, (int, float)):
                if math.isclose(got, exp, rel_tol=1e-5, abs_tol=1e-9):
                    passed += 1
            elif str(got) == str(exp):
                passed += 1

        assert passed / len(gb_items) >= 0.90

    def test_overall_baseline_conformance(
        self, baseline_data: dict[str, Any], baseline_context: EvalContext
    ):
        total = len(baseline_data)
        assert total > 3000

        passed = 0
        for expr, exp in baseline_data.items():
            got = evaluate("=" + expr, baseline_context)
            if hasattr(got, "error_code"):
                got = got.error_code

            if isinstance(exp, (int, float)) and isinstance(got, (int, float)):
                err = abs(got - exp) / max(abs(exp), 1e-300)
                if abs(got) < 1e-300 and abs(exp) < 1e-300:
                    passed += 1
                elif expr.startswith(("VDB(", "DDB(")) and abs(got - exp) <= 1e-9:
                    passed += 1
                elif err <= 1e-4:
                    passed += 1
            elif str(exp) == str(got):
                passed += 1

        pass_rate = passed / total
        assert pass_rate >= 0.93, f"Overall pass rate {pass_rate:.2%} lower than 93%"
