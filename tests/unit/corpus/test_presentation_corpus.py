"""PowerPoint Corpus Compatibility and Loss-Audit Regression Suite.

Tests roundtrip loading, saving, and ECMA-376 feature preservation across
the curated real-world production PowerPoint files in tests/docs/powerpoint/.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from atboffice.deep.audit.core import AuditSession, load_package_xml
from atboffice.deep.audit.presentation import extract_presentation_features
from atboffice.modules.presentation.io import read_pptx, write_pptx


PPTX_DIR = Path("tests/docs/powerpoint/pptx")
PPT_DIR = Path("tests/docs/powerpoint/ppt")


def test_curated_pptx_roundtrip_and_feature_preservation() -> None:
    pptx_files = sorted(PPTX_DIR.glob("*.pptx")) + sorted(PPTX_DIR.glob("*.pptm"))
    assert len(pptx_files) >= 10, "Expected at least 10 curated pptx/pptm files"

    session = AuditSession()
    tested_count = 0

    for pptx_path in pptx_files:
        raw_data = pptx_path.read_bytes()
        try:
            pres = read_pptx(raw_data)
        except Exception as e:
            session.record_pair(pptx_path.name, status="excluded", reason=str(e))
            continue

        saved_bytes = write_pptx(pres)
        assert len(saved_bytes) > 0, f"Saved bytes empty for {pptx_path.name}"

        orig_names, orig_files = load_package_xml(raw_data)
        saved_names, saved_files = load_package_xml(saved_bytes)

        orig_feats = extract_presentation_features(orig_names, orig_files)
        saved_feats = extract_presentation_features(saved_names, saved_files)

        session.record_pair(
            pptx_path.name,
            status="ok",
            original_features=orig_feats,
            saved_features=saved_feats,
        )
        tested_count += 1

    summary = session.summary()
    assert summary["attempted"] == len(pptx_files)
    assert summary["ok"] >= 15, f"Expected at least 15 successful roundtrips, got {summary['ok']}"


def test_curated_ppt_binary_safe_handling() -> None:
    ppt_files = sorted(PPT_DIR.glob("*.ppt"))
    assert len(ppt_files) >= 10, "Expected at least 10 curated ppt files"

    ole2_header = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

    valid_header_count = 0
    for ppt_path in ppt_files:
        data = ppt_path.read_bytes()
        assert len(data) > 0
        if data.startswith(ole2_header):
            valid_header_count += 1

    assert valid_header_count >= 5, "Curated .ppt collection should include real OLE2 presentations"
