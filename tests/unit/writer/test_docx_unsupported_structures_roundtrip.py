"""Tests for DOCX Frame Properties (framePr), Strict Math/Picture, and Background Roundtrip.

Tests issue #288:
- libreoffice__fdo55381.docx: framePr (drop caps / frames) roundtrip preserved (4 -> 4).
- libreoffice__tdf105035_framePrB.docx: framePr roundtrip preserved (2 -> 2).
- libreoffice__tdf113182.docx: framePr roundtrip preserved (1 -> 1).
- openxml-sdk__bullet-complex.docx: footer framePr roundtrip preserved (2 -> 2).
- libreoffice__strict.docx: ISO/IEC 29500 Strict equations and pictures normalized
  to standard Transitional prefixes and preserved without feature loss.
- libreoffice__tdf153255.docx: document background (<w:background>) preserved.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from atboffice.deep.audit.core import audit_corpus_file, load_package_xml
from atboffice.deep.audit.word import extract_word_features
from atboffice.modules.writer.io.docx_reader import read_docx
from atboffice.modules.writer.io.docx_writer import write_docx
from atboffice.modules.writer.models.document import Document, Paragraph, Story, TextItem
from atboffice.modules.writer.models.properties import ParagraphProperties

DOCX_DIR = Path("tests/docs/word/docx")


def test_frame_pr_model_and_roundtrip():
    """Verify that paragraph frame_pr property is parsed and serialized correctly."""
    doc = Document()
    p1 = Paragraph(
        runs=[TextItem(text="Paragraph with full framePr")],
        p_pr=ParagraphProperties(
            frame_pr={
                "w:w": "4253",
                "w:h": "1724",
                "w:hRule": "exact",
                "w:wrap": "notBeside",
                "w:vAnchor": "page",
                "w:hAnchor": "page",
                "w:x": "1021",
                "w:y": "2461",
            }
        ),
    )
    p2 = Paragraph(
        runs=[TextItem(text="Paragraph with empty framePr")],
        p_pr=ParagraphProperties(frame_pr={}),
    )
    doc.main = Story(kind="main", blocks=[p1, p2])

    out_bytes = write_docx(doc)
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "<w:framePr" in doc_xml
        assert 'w:wrap="notBeside"' in doc_xml
        assert 'w:w="4253"' in doc_xml

    reloaded = read_docx(out_bytes)
    blocks = reloaded.main.blocks
    assert len(blocks) == 2
    assert isinstance(blocks[0], Paragraph)
    assert blocks[0].p_pr.frame_pr is not None
    w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    wrap_val = blocks[0].p_pr.frame_pr.get(f"{w_ns}wrap") or blocks[0].p_pr.frame_pr.get("w:wrap")
    assert wrap_val == "notBeside"
    assert blocks[1].p_pr.frame_pr is not None


def test_fdo55381_frame_pr_corpus_roundtrip():
    """Verify that all 4 framePr instances in libreoffice__fdo55381.docx are preserved."""
    path = DOCX_DIR / "libreoffice__fdo55381.docx"
    assert path.exists()

    raw_data = path.read_bytes()
    orig_names, orig_files = load_package_xml(raw_data)
    orig_feats = extract_word_features(orig_names, orig_files)
    assert orig_feats["drop caps / frames"] == 4

    doc = read_docx(raw_data)
    out_bytes = write_docx(doc)
    saved_names, saved_files = load_package_xml(out_bytes)
    saved_feats = extract_word_features(saved_names, saved_files)
    assert saved_feats["drop caps / frames"] == 4

    # Full audit validation
    res = audit_corpus_file(str(path))
    assert res.get("status") == "ok"
    assert not res.get("feature_losses")


def test_tdf105035_and_tdf113182_frame_pr_roundtrip():
    """Verify framePr roundtrip on tdf105035 and tdf113182."""
    for filename, expected_count in [
        ("libreoffice__tdf105035_framePrB.docx", 2),
        ("libreoffice__tdf113182.docx", 1),
    ]:
        path = DOCX_DIR / filename
        assert path.exists()

        raw_data = path.read_bytes()
        orig_names, orig_files = load_package_xml(raw_data)
        orig_feats = extract_word_features(orig_names, orig_files)
        assert orig_feats["drop caps / frames"] == expected_count

        doc = read_docx(raw_data)
        out_bytes = write_docx(doc)
        saved_names, saved_files = load_package_xml(out_bytes)
        saved_feats = extract_word_features(saved_names, saved_files)
        assert saved_feats["drop caps / frames"] == expected_count

        res = audit_corpus_file(str(path))
        assert res.get("status") == "ok"
        assert not res.get("feature_losses")


def test_bullet_complex_footer_frame_pr_roundtrip():
    """Verify footer framePr in openxml-sdk__bullet-complex.docx is preserved."""
    path = DOCX_DIR / "openxml-sdk__bullet-complex.docx"
    assert path.exists()

    raw_data = path.read_bytes()
    orig_names, orig_files = load_package_xml(raw_data)
    orig_feats = extract_word_features(orig_names, orig_files)
    assert orig_feats["drop caps / frames"] == 2

    doc = read_docx(raw_data)
    out_bytes = write_docx(doc)
    saved_names, saved_files = load_package_xml(out_bytes)
    saved_feats = extract_word_features(saved_names, saved_files)
    assert saved_feats["drop caps / frames"] == 2

    res = audit_corpus_file(str(path))
    assert res.get("status") == "ok"
    assert not res.get("feature_losses")


def test_strict_docx_math_and_pictures_roundtrip():
    """Verify equations and pictures in Strict libreoffice__strict.docx are preserved."""
    path = DOCX_DIR / "libreoffice__strict.docx"
    assert path.exists()

    raw_data = path.read_bytes()
    orig_names, orig_files = load_package_xml(raw_data)
    orig_feats = extract_word_features(orig_names, orig_files)
    assert orig_feats["equations"] == 1
    assert orig_feats["pictures"] == 1

    doc = read_docx(raw_data)
    out_bytes = write_docx(doc)
    saved_names, saved_files = load_package_xml(out_bytes)
    saved_feats = extract_word_features(saved_names, saved_files)
    assert saved_feats["equations"] == 1
    assert saved_feats["pictures"] == 1

    # Check XML serialized with standard prefixes
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "<m:oMath" in doc_xml or "<m:oMathPara" in doc_xml
        assert "<pic:pic" in doc_xml

    res = audit_corpus_file(str(path))
    assert res.get("status") == "ok"
    assert not res.get("feature_losses")


def test_document_background_colour_roundtrip():
    """Verify that document background in libreoffice__tdf153255.docx is preserved."""
    path = DOCX_DIR / "libreoffice__tdf153255.docx"
    assert path.exists()

    raw_data = path.read_bytes()
    orig_names, orig_files = load_package_xml(raw_data)
    orig_feats = extract_word_features(orig_names, orig_files)
    assert orig_feats["document background colour"] == 1

    doc = read_docx(raw_data)
    assert "background" in doc.keep

    out_bytes = write_docx(doc)
    saved_names, saved_files = load_package_xml(out_bytes)
    saved_feats = extract_word_features(saved_names, saved_files)
    assert saved_feats["document background colour"] == 1

    # Verify background is placed before body in document.xml
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        bg_pos = doc_xml.find("<w:background")
        body_pos = doc_xml.find("<w:body")
        assert bg_pos != -1
        assert body_pos != -1
        assert bg_pos < body_pos

    res = audit_corpus_file(str(path))
    assert res.get("status") == "ok"
    assert not res.get("feature_losses")
