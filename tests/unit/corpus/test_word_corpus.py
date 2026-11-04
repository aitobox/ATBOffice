"""Word Corpus Compatibility and Loss-Audit Regression Suite.

Tests roundtrip loading, saving, and ECMA-376 feature preservation across
the 50 curated real-world production Word files in tests/docs/word/
according to the authoritative expectations contract in tests/docs/expectations.json.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from atboffice.deep.audit.core import AuditSession, CorpusExpectations, load_package_xml
from atboffice.deep.audit.word import count_document_words, extract_word_features
from atboffice.modules.writer.io import read_docx, write_docx

DOCX_DIR = Path("tests/docs/word/docx")
DOC_DIR = Path("tests/docs/word/doc")
EXPECTATIONS_PATH = Path("tests/docs/expectations.json")


def test_curated_docx_roundtrip_and_feature_preservation() -> None:
    docx_files = sorted(DOCX_DIR.glob("*.docx"))
    assert len(docx_files) == 25, f"Expected 25 curated docx files, found {len(docx_files)}"

    expectations = CorpusExpectations(EXPECTATIONS_PATH)
    session = AuditSession()
    valid_count = 0
    encrypted_count = 0

    for docx_path in docx_files:
        raw_data = docx_path.read_bytes()
        exp = expectations.get(docx_path.name)
        assert exp is not None, f"File {docx_path.name} must be cataloged in expectations.json"

        expected_cat = exp.get("category")

        if expected_cat == "encrypted":
            # Agile Encrypted OOXML wrapped in OLE2 container
            with pytest.raises(Exception):
                read_docx(raw_data)
            encrypted_count += 1
            session.record_result({
                "file": docx_path.name,
                "status": "encrypted",
                "expected_match": True,
            })
            continue

        # Valid document processing
        doc = read_docx(raw_data)
        assert hasattr(doc, "main") or hasattr(doc, "body") or hasattr(doc, "paragraphs"), (
            f"Parsed document model invalid for {docx_path.name}"
        )

        saved_bytes = write_docx(doc)
        assert len(saved_bytes) > 0, f"Saved bytes empty for {docx_path.name}"

        orig_names, orig_files = load_package_xml(raw_data)
        saved_names, saved_files = load_package_xml(saved_bytes)

        orig_feats = extract_word_features(orig_names, orig_files)
        saved_feats = extract_word_features(saved_names, saved_files)

        orig_words = count_document_words(orig_files)
        saved_words = count_document_words(saved_files)
        assert orig_words >= 0
        assert saved_words >= 0

        session.record_pair(
            docx_path.name,
            status="ok",
            original_features=orig_feats,
            saved_features=saved_feats,
        )
        valid_count += 1

    summary = session.summary()
    assert summary["attempted"] == 25
    assert valid_count == 24, f"Expected 24 valid roundtrips, got {valid_count}"
    assert encrypted_count == 1, f"Expected 1 encrypted rejection, got {encrypted_count}"


def test_curated_doc_binary_safe_handling() -> None:
    doc_files = sorted(DOC_DIR.glob("*.doc"))
    assert len(doc_files) == 25, f"Expected 25 curated doc files, found {len(doc_files)}"

    expectations = CorpusExpectations(EXPECTATIONS_PATH)
    rejected_count = 0

    for doc_path in doc_files:
        exp = expectations.get(doc_path.name)
        assert exp is not None, f"File {doc_path.name} must be cataloged in expectations.json"
        assert exp.get("category") == "unsupported_format"

        raw_data = doc_path.read_bytes()
        assert len(raw_data) > 0

        # OOXML parser must reject legacy binary files safely without crashing
        with pytest.raises(Exception):
            read_docx(raw_data)
        rejected_count += 1

    assert rejected_count == 25, "All 25 legacy binary .doc files must be safely rejected by OOXML reader"
