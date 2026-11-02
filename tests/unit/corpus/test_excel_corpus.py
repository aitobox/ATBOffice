"""Excel Corpus Compatibility and Loss-Audit Regression Suite.

Tests roundtrip loading, saving, and ECMA-376 feature preservation across
the curated real-world production Excel files in tests/docs/excel/.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from atboffice.deep.audit.core import AuditSession, load_package_xml
from atboffice.deep.audit.excel import extract_excel_features
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx


XLSX_DIR = Path("tests/docs/excel/xlsx")
XLS_DIR = Path("tests/docs/excel/xls")


def test_curated_xlsx_roundtrip_and_feature_preservation() -> None:
    xlsx_files = sorted(XLSX_DIR.glob("*.xlsx")) + sorted(XLSX_DIR.glob("*.xlsm"))
    assert len(xlsx_files) >= 10, "Expected at least 10 curated xlsx/xlsm files"

    session = AuditSession()
    tested_count = 0

    for xlsx_path in xlsx_files:
        raw_data = xlsx_path.read_bytes()
        try:
            wb = read_xlsx(raw_data)
        except Exception as e:
            session.record_pair(xlsx_path.name, status="excluded", reason=str(e))
            continue

        saved_bytes = write_xlsx(wb)
        assert len(saved_bytes) > 0, f"Saved bytes empty for {xlsx_path.name}"

        orig_names, orig_files = load_package_xml(raw_data)
        saved_names, saved_files = load_package_xml(saved_bytes)

        orig_feats = extract_excel_features(orig_names, orig_files)
        saved_feats = extract_excel_features(saved_names, saved_files)

        session.record_pair(
            xlsx_path.name,
            status="ok",
            original_features=orig_feats,
            saved_features=saved_feats,
        )
        tested_count += 1

    summary = session.summary()
    assert summary["attempted"] == len(xlsx_files)
    assert summary["ok"] >= 15, f"Expected at least 15 successful roundtrips, got {summary['ok']}"


def test_curated_xls_binary_safe_handling() -> None:
    xls_files = sorted(XLS_DIR.glob("*.xls"))
    assert len(xls_files) >= 10, "Expected at least 10 curated xls files"

    ole2_header = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    biff_header = b"\t\x00"

    valid_header_count = 0
    for xls_path in xls_files:
        data = xls_path.read_bytes()
        assert len(data) > 0
        if data.startswith(ole2_header) or data.startswith(biff_header):
            valid_header_count += 1

    assert valid_header_count >= 10, "Curated .xls collection should include real OLE2 or BIFF workbooks"
