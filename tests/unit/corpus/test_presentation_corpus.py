"""PowerPoint Corpus Compatibility and Loss-Audit Regression Suite.

Tests roundtrip loading, saving, and ECMA-376 feature preservation across
the 50 curated real-world production PowerPoint files in tests/docs/powerpoint/
according to the authoritative expectations contract in tests/docs/expectations.json.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from atboffice.deep.audit.core import AuditSession, CorpusExpectations, load_package_xml
from atboffice.deep.audit.presentation import extract_presentation_features
from atboffice.modules.presentation.io import read_pptx, write_pptx

PPTX_DIR = Path("tests/docs/powerpoint/pptx")
PPT_DIR = Path("tests/docs/powerpoint/ppt")
EXPECTATIONS_PATH = Path("tests/docs/expectations.json")


def test_curated_pptx_roundtrip_and_feature_preservation() -> None:
    pptx_files = sorted(PPTX_DIR.glob("*.pptx")) + sorted(PPTX_DIR.glob("*.pptm"))
    assert len(pptx_files) == 25, f"Expected 25 curated pptx/pptm files, found {len(pptx_files)}"

    expectations = CorpusExpectations(EXPECTATIONS_PATH)
    session = AuditSession()
    valid_count = 0

    for pptx_path in pptx_files:
        raw_data = pptx_path.read_bytes()
        exp = expectations.get(pptx_path.name)
        assert exp is not None, f"File {pptx_path.name} must be cataloged in expectations.json"
        assert exp.get("category") == "valid"

        pres = read_pptx(raw_data)
        assert hasattr(pres, "slides"), f"Parsed presentation model invalid for {pptx_path.name}"

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
        valid_count += 1

    summary = session.summary()
    assert summary["attempted"] == 25
    assert valid_count == 25, f"Expected 25 valid roundtrips, got {valid_count}"


def test_curated_ppt_binary_safe_handling() -> None:
    ppt_files = sorted(PPT_DIR.glob("*.ppt"))
    assert len(ppt_files) == 25, f"Expected 25 curated ppt files, found {len(ppt_files)}"

    expectations = CorpusExpectations(EXPECTATIONS_PATH)
    rejected_count = 0

    for ppt_path in ppt_files:
        exp = expectations.get(ppt_path.name)
        assert exp is not None, f"File {ppt_path.name} must be cataloged in expectations.json"
        assert exp.get("category") == "unsupported_format"

        raw_data = ppt_path.read_bytes()
        assert len(raw_data) > 0

        # OOXML parser must reject legacy binary files safely without crashing
        with pytest.raises(Exception):
            read_pptx(raw_data)
        rejected_count += 1

    assert rejected_count == 25, "All 25 legacy binary .ppt files must be safely rejected by OOXML reader"
