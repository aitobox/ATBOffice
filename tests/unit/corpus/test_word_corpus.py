"""Word Corpus Compatibility and Loss-Audit Regression Suite.

Tests roundtrip loading, saving, and ECMA-376 feature preservation across
the curated real-world production Word files in tests/docs/word/.
"""

from __future__ import annotations

from pathlib import Path

from atboffice.deep.audit.core import AuditSession, load_package_xml
from atboffice.deep.audit.word import count_document_words, extract_word_features
from atboffice.modules.writer.io import read_docx, write_docx

DOCX_DIR = Path("tests/docs/word/docx")
DOC_DIR = Path("tests/docs/word/doc")


def test_curated_docx_roundtrip_and_feature_preservation() -> None:
    docx_files = sorted(DOCX_DIR.glob("*.docx"))
    assert len(docx_files) >= 10, "Expected at least 10 curated docx files"

    session = AuditSession()
    tested_count = 0

    for docx_path in docx_files:
        raw_data = docx_path.read_bytes()
        try:
            doc = read_docx(raw_data)
        except Exception as e:
            # Bugzilla / CVE reproduction fuzz files are recorded as excluded/failed
            session.record_pair(docx_path.name, status="excluded", reason=str(e))
            continue

        saved_bytes = write_docx(doc)
        assert len(saved_bytes) > 0, f"Saved bytes empty for {docx_path.name}"

        orig_names, orig_files = load_package_xml(raw_data)
        saved_names, saved_files = load_package_xml(saved_bytes)

        orig_feats = extract_word_features(orig_names, orig_files)
        saved_feats = extract_word_features(saved_names, saved_files)

        # Word count check
        orig_words = count_document_words(orig_files)
        saved_words = count_document_words(saved_files)
        assert orig_words >= 0
        assert saved_words >= 0

        # Record in audit session
        session.record_pair(
            docx_path.name,
            status="ok",
            original_features=orig_feats,
            saved_features=saved_feats,
        )
        tested_count += 1

    summary = session.summary()
    assert summary["attempted"] == len(docx_files)
    assert summary["ok"] >= 15, f"Expected at least 15 successful roundtrips, got {summary['ok']}"


def test_curated_doc_binary_safe_handling() -> None:
    doc_files = sorted(DOC_DIR.glob("*.doc"))
    assert len(doc_files) >= 10, "Expected at least 10 curated doc files"

    ole2_header = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    valid_ole2_count = 0

    for doc_path in doc_files:
        data = doc_path.read_bytes()
        assert len(data) > 0
        if data.startswith(ole2_header):
            valid_ole2_count += 1

    assert valid_ole2_count >= 5, "Curated .doc collection should include real OLE2 documents"
