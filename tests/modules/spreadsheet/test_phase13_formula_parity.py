"""Phase 13A tests for Ledger ENCODEURL, offline FILTERXML/EUROCONVERT, and 520-function parity."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import DIV0, NA, NAME, VALUE, ExcelError
from atboffice.modules.spreadsheet.calc.evaluator import evaluate
from atboffice.modules.spreadsheet.calc.fn_info import ALL_FUNCTIONS_CATALOG
from atboffice.modules.spreadsheet.calc.functions import FUNCTION_REGISTRY, call_function
from atboffice.modules.spreadsheet.calc.parser import FUTURE, store_name


def _find_vibeoffice_fninfo() -> Path | None:
    """Locate `.vibeoffice/public/ledger/js/fninfo.js` in repo or parent repo (worktree-safe)."""
    here = Path(__file__).resolve()
    for base in here.parents:
        candidate = base / ".vibeoffice" / "public" / "ledger" / "js" / "fninfo.js"
        if candidate.is_file():
            return candidate
    return None


# ---------------------------------------------------------------------------
# ENCODEURL
# ---------------------------------------------------------------------------


def test_encodeurl_encoding_rules_coercion_and_formula_eval() -> None:
    """ENCODEURL percent-encodes UTF-8 reserved chars and preserves unreserved."""
    assert call_function("ENCODEURL", ["hello world"]) == "hello%20world"
    assert call_function("ENCODEURL", ["a/b?k=1&m=a+b#frag"]) == "a%2Fb%3Fk%3D1%26m%3Da%2Bb%23frag"
    assert call_function("ENCODEURL", ["AZaz09-_.~"]) == "AZaz09-_.~"
    assert call_function("ENCODEURL", ["中文"]) == "%E4%B8%AD%E6%96%87"
    assert call_function("ENCODEURL", [42]) == "42"
    assert call_function("ENCODEURL", [True]) == "TRUE"
    assert call_function("ENCODEURL", [""]) == ""

    # Error propagation & arity checks
    assert call_function("ENCODEURL", [DIV0]) == DIV0
    assert call_function("ENCODEURL", []) == VALUE
    assert call_function("ENCODEURL", ["a", "b"]) == VALUE

    # Ref dereferencing and end-to-end evaluator + _xlfn prefix
    ctx = EvalContext()
    ctx.workbook_data["Sheet1"] = {(0, 0): "foo bar/baz"}
    ctx.current_sheet = "Sheet1"
    assert evaluate('=ENCODEURL("a b&c")', ctx) == "a%20b%26c"
    assert evaluate("=ENCODEURL(A1)", ctx) == "foo%20bar%2Fbaz"
    assert "ENCODEURL" in FUTURE
    assert store_name("ENCODEURL") == "_xlfn.ENCODEURL"


# ---------------------------------------------------------------------------
# FILTERXML
# ---------------------------------------------------------------------------


_SAMPLE_XML = (
    "<catalog>"
    '<book id="1"><title>Alpha</title><price>12.5</price><qty>3</qty></book>'
    '<book id="2"><title>Beta</title><price>40</price><qty>7</qty></book>'
    "</catalog>"
)


def test_filterxml_scalar_array_xpath_and_security() -> None:
    """FILTERXML evaluates offline XPath, spills multi-node results, and blocks XXE/DTD payloads."""
    # Single node scalar string & numeric coercion
    assert call_function("FILTERXML", [_SAMPLE_XML, "//book[1]/title"]) == "Alpha"
    assert call_function("FILTERXML", [_SAMPLE_XML, "//book[1]/qty"]) == 3
    assert isinstance(call_function("FILTERXML", [_SAMPLE_XML, "//book[1]/qty"]), int)
    assert call_function("FILTERXML", [_SAMPLE_XML, "//book[1]/price"]) == pytest.approx(12.5)
    assert call_function("FILTERXML", [_SAMPLE_XML, "//book[2]/@id"]) == 2

    # Multi-node result returns vertical Arr
    titles = call_function("FILTERXML", [_SAMPLE_XML, "//book/title"])
    assert isinstance(titles, Arr)
    assert titles.data == [["Alpha"], ["Beta"]]

    qtys = call_function("FILTERXML", [_SAMPLE_XML, "//book/qty"])
    assert isinstance(qtys, Arr)
    assert qtys.data == [[3], [7]]

    # XPath scalar functions (count / boolean / string)
    assert call_function("FILTERXML", [_SAMPLE_XML, "count(//book)"]) == 2
    assert call_function("FILTERXML", [_SAMPLE_XML, "boolean(//book)"]) is True

    # No matching node -> #N/A
    assert call_function("FILTERXML", [_SAMPLE_XML, "//nonexistent"]) == NA

    # Malformed XML / invalid XPath / empty args / wrong arity -> #VALUE!
    assert call_function("FILTERXML", ["<broken>", "//a"]) == VALUE
    assert call_function("FILTERXML", [_SAMPLE_XML, "///[invalid"]) == VALUE
    assert call_function("FILTERXML", ["", "//a"]) == VALUE
    assert call_function("FILTERXML", [_SAMPLE_XML, ""]) == VALUE
    assert call_function("FILTERXML", [_SAMPLE_XML]) == VALUE

    # XXE & external entity declarations rejected safely offline
    xxe_payload = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE root [<!ENTITY secret SYSTEM "file:///etc/passwd">]>'
        "<root>&secret;</root>"
    )
    assert call_function("FILTERXML", [xxe_payload, "//root"]) == VALUE

    # Error propagation and Ref support
    assert call_function("FILTERXML", [NA, "//a"]) == NA
    assert call_function("FILTERXML", [_SAMPLE_XML, DIV0]) == DIV0

    ctx = EvalContext()
    ctx.workbook_data["Sheet1"] = {(0, 0): _SAMPLE_XML, (0, 1): "//book[2]/title"}
    ctx.current_sheet = "Sheet1"
    assert evaluate("=FILTERXML(A1, B1)", ctx) == "Beta"


# ---------------------------------------------------------------------------
# EUROCONVERT
# ---------------------------------------------------------------------------


def test_euroconvert_rates_triangulation_precision_and_errors() -> None:
    """EUROCONVERT converts across all 21 official EU currencies with triangulation & rounding."""
    # Direct EUR <-> legacy member currency conversions
    assert call_function("EUROCONVERT", [100, "EUR", "DEM"]) == pytest.approx(195.58)
    assert call_function("EUROCONVERT", [100, "EUR", "DEM", True]) == pytest.approx(195.583)
    assert call_function("EUROCONVERT", [195.583, "DEM", "EUR"]) == pytest.approx(100.0)
    assert call_function("EUROCONVERT", [100, "eur", "dem", True]) == pytest.approx(195.583)

    # Zero-decimal currencies (ITL, BEF, LUF, ESP, GRD, PTE)
    assert call_function("EUROCONVERT", [1, "EUR", "ITL"]) == 1936
    assert call_function("EUROCONVERT", [1, "EUR", "ITL", True]) == pytest.approx(1936.27)
    assert call_function("EUROCONVERT", [1, "EUR", "BEF"]) == 40

    # Same currency identity
    assert call_function("EUROCONVERT", [123.456, "DEM", "DEM"]) == pytest.approx(123.46)
    assert call_function("EUROCONVERT", [123.456, "DEM", "DEM", True]) == pytest.approx(123.456)

    # Triangulation: 100 FRF -> EUR (rounded to triangulation_precision) -> DEM
    # 100 / 6.55957 = 15.2449017... -> 3 decimals: 15.245 -> * 1.95583 = 29.81662835
    assert call_function("EUROCONVERT", [100, "FRF", "DEM", True, 3]) == pytest.approx(29.81662835)
    assert call_function("EUROCONVERT", [100, "FRF", "DEM", False, 3]) == pytest.approx(29.82)

    # All 20 fixed legacy rates + EUR work cleanly
    for code in (
        "ATS",
        "BEF",
        "CYP",
        "DEM",
        "EEK",
        "ESP",
        "FIM",
        "FRF",
        "GRD",
        "HRK",
        "IEP",
        "ITL",
        "LTL",
        "LUF",
        "LVL",
        "MTL",
        "NLG",
        "PTE",
        "SIT",
        "SKK",
    ):
        res = call_function("EUROCONVERT", [10, "EUR", code, True])
        assert isinstance(res, float) and res > 0

    # Invalid inputs & error propagation
    assert call_function("EUROCONVERT", [10, "USD", "EUR"]) == VALUE
    assert call_function("EUROCONVERT", [10, "EUR", "JPY"]) == VALUE
    assert call_function("EUROCONVERT", [10, "", "EUR"]) == VALUE
    assert call_function("EUROCONVERT", [100, "FRF", "DEM", False, 2]) == VALUE
    assert call_function("EUROCONVERT", ["not-num", "EUR", "DEM"]) == VALUE
    assert call_function("EUROCONVERT", [10, "EUR"]) == VALUE
    assert call_function("EUROCONVERT", [DIV0, "EUR", "DEM"]) == DIV0
    ref_val = Ref("Sheet1", 0, 0, 0, 0, lambda s, r, c: 50)
    assert call_function("EUROCONVERT", [ref_val, "EUR", "DEM"]) == pytest.approx(97.79)

    assert evaluate('=EUROCONVERT(1, "EUR", "DEM", TRUE)') == pytest.approx(1.95583)


# ---------------------------------------------------------------------------
# 520-Function & .vibeoffice 498-Function Parity Gate
# ---------------------------------------------------------------------------


def test_ledger_520_function_registry_and_catalog_parity() -> None:
    """FUNCTION_REGISTRY and ALL_FUNCTIONS_CATALOG match 1-to-1 with 520 callable entries."""
    reg_keys = set(FUNCTION_REGISTRY.keys())
    cat_keys = set(ALL_FUNCTIONS_CATALOG.keys())

    assert reg_keys == cat_keys, (
        f"Registry/Catalog mismatch: only_in_reg={sorted(reg_keys - cat_keys)}, "
        f"only_in_cat={sorted(cat_keys - reg_keys)}"
    )
    assert len(reg_keys) == 520

    # Smoke-call every registered function with empty args: must return value or ExcelError
    for name in sorted(reg_keys):
        res = call_function(name, [])
        assert res != NAME, f"{name} returned #NAME? unexpectedly"
        assert res is None or isinstance(res, (int, float, str, bool, ExcelError, Arr, Ref))


def test_vibeoffice_498_functions_100_percent_covered() -> None:
    """All 498 functions documented in `.vibeoffice/public/ledger/js/fninfo.js` are registered."""
    fninfo_path = _find_vibeoffice_fninfo()
    if fninfo_path is None:
        pytest.skip(".vibeoffice reference directory not present")

    text = fninfo_path.read_text(encoding="utf-8")
    vibe_names = set(re.findall(r"^([A-Z][A-Z0-9_.]+)\|", text, re.MULTILINE))
    assert len(vibe_names) == 498

    missing = sorted(vibe_names - set(FUNCTION_REGISTRY.keys()))
    assert missing == [], f"Functions in .vibeoffice missing from Ledger: {missing}"
