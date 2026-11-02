from __future__ import annotations

import io
from pathlib import Path
import zipfile

import pytest

from atboffice.deep.audit.core import AuditSession, load_package_xml, xml_text


def test_xml_text_encodings() -> None:
    assert xml_text(b"<?xml?>hello") == "<?xml?>hello"
    assert xml_text(b"\xef\xbb\xbf<?xml?>bom") == "<?xml?>bom"
    assert xml_text("<?xml?>utf16".encode("utf-16le")) == "<?xml?>utf16"
    assert xml_text("<?xml?>utf16be".encode("utf-16be")) == "<?xml?>utf16be"


def test_load_package_xml_alternate_content() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "word/document.xml",
            "<mc:AlternateContent><mc:Choice>A</mc:Choice><mc:Fallback>B</mc:Fallback></mc:AlternateContent>",
        )
        z.writestr("word/binary.bin", b"\x00\x01\x02\x03")
    names, files = load_package_xml(buf.getvalue())
    assert "word/document.xml" in files
    assert "B" not in files["word/document.xml"]
    assert "A" in files["word/document.xml"]
    assert "word/binary.bin" in names
    assert "word/binary.bin" not in files


def test_audit_session_metrics() -> None:
    session = AuditSession()
    session.record_pair("doc1.docx", status="ok", original_features={"comments": 2}, saved_features={"comments": 2})
    session.record_pair("doc2.docx", status="failed", reason="Missing part", original_features={"comments": 1}, saved_features={"comments": 0})
    session.record_pair("doc3.docx", status="excluded", reason="Fuzz malformed file")
    report = session.summary()
    assert report["attempted"] == 3
    assert report["ok"] == 1
    assert report["failed"] == 1
    assert report["excluded"] == 1
    assert report["feature_losses"]["comments"] == 1


def test_audit_single_file_helper() -> None:
    from scripts.run_corpus_audit import audit_single_file

    sample = next(Path("tests/docs/word/docx").glob("*.docx"))
    res = audit_single_file(str(sample), "word")
    assert res["status"] in ("ok", "failed", "excluded")
    assert "file" in res
