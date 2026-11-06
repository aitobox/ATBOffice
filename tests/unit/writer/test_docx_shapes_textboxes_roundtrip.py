"""Tests for DOCX Shapes, Textboxes, and Header Picture Roundtrip Preservation.

Tests issue #287:
- poi__headerPic.docx: header pictures, DrawingML, and media relationships preserved.
- libreoffice__textframe-borders.docx: VML pict and textbox roundtrip preserved (1 -> 1).
- libreoffice__nested-runs.docx: AlternateContent and wps:wsp preserved without text duplication.
- poi__60316.docx: all 5 wps:wsp preserved, header/footer relationships intact.
- libreoffice__tdf113183.docx: wps:wsp shapes preserved.
- DrawingObject.plain_text(): dynamic extraction of textbox content.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from atboffice.deep.audit.core import load_package_xml
from atboffice.deep.audit.word import extract_word_features
from atboffice.modules.writer.io.docx_reader import read_docx
from atboffice.modules.writer.io.docx_writer import write_docx
from atboffice.modules.writer.models.document import ptext, reindex
from atboffice.modules.writer.models.drawing import DrawingObject, PictureItem

DOCX_DIR = Path("tests/docs/word/docx")


def test_header_pic_media_and_rels_roundtrip():
    """Verify that header picture in poi__headerPic.docx is preserved along with rels and media."""
    path = DOCX_DIR / "poi__headerPic.docx"
    assert path.exists()

    doc = read_docx(path.read_bytes())
    reindex(doc)
    # Check that header has picture item
    header_pics = [
        r
        for story in doc.hf.values()
        for p in story.paras
        for r in p.runs
        if isinstance(r, PictureItem)
    ]
    assert len(header_pics) >= 1
    assert any("image" in p.image_part for p in header_pics)

    # Save and verify package contents
    out_bytes = write_docx(doc)
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        namelist = zf.namelist()
        assert "word/media/image1.jpeg" in namelist
        assert "word/_rels/header1.xml.rels" in namelist

        header_xml = zf.read("word/header1.xml").decode("utf-8")
        assert "pic:pic" in header_xml or "pic" in header_xml
        assert "rId1" in header_xml

        rels_xml = zf.read("word/_rels/header1.xml.rels").decode("utf-8")
        assert "media/image1.jpeg" in rels_xml

    # Re-open saved package and verify no crash
    reloaded = read_docx(out_bytes)
    assert len(reloaded.hf) >= 1


def test_textframe_borders_vml_roundtrip():
    """Verify that VML pict and textbox in libreoffice__textframe-borders.docx are preserved."""
    path = DOCX_DIR / "libreoffice__textframe-borders.docx"
    assert path.exists()

    raw_data = path.read_bytes()
    doc = read_docx(raw_data)
    reindex(doc)
    # Check plain_text on picture item
    p = doc.main.paras[0]
    pics = [r for r in p.runs if isinstance(r, PictureItem)]
    assert len(pics) >= 1
    assert pics[0].plain_text() == "aaa"
    assert "aaa" in ptext(p)

    out_bytes = write_docx(doc)
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "<w:pict>" in doc_xml
        assert "v:rect" in doc_xml
        assert "w:txbxContent" in doc_xml
        assert "aaa" in doc_xml

    # Check zero loss in word features audit
    orig_names, orig_files = load_package_xml(raw_data)
    saved_names, saved_files = load_package_xml(out_bytes)
    orig_feats = extract_word_features(orig_names, orig_files)
    saved_feats = extract_word_features(saved_names, saved_files)
    assert saved_feats.get("text boxes", 0) >= orig_feats.get("text boxes", 1)
    assert saved_feats.get("VML shapes", 0) >= orig_feats.get("VML shapes", 1)


def test_nested_runs_wps_roundtrip():
    """Verify that wps:wsp in nested-runs.docx is preserved without text duplication."""
    path = DOCX_DIR / "libreoffice__nested-runs.docx"
    assert path.exists()

    raw_data = path.read_bytes()
    doc = read_docx(raw_data)
    reindex(doc)
    p = doc.main.paras[0]
    pics = [r for r in p.runs if isinstance(r, PictureItem)]
    assert len(pics) >= 1
    assert pics[0].plain_text() == "Test text box"

    with zipfile.ZipFile(io.BytesIO(raw_data)) as orig_zf:
        orig_doc_xml = orig_zf.read("word/document.xml").decode("utf-8")

    out_bytes = write_docx(doc)
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "wps:wsp" in doc_xml
        # Verify text occurrences match original file (no extra redundant run outside drawing)
        assert doc_xml.count("Test text box") == orig_doc_xml.count("Test text box")

    orig_names, orig_files = load_package_xml(raw_data)
    saved_names, saved_files = load_package_xml(out_bytes)
    orig_feats = extract_word_features(orig_names, orig_files)
    saved_feats = extract_word_features(saved_names, saved_files)
    assert saved_feats.get("drawing shapes (wps)", 0) >= orig_feats.get("drawing shapes (wps)", 1)


def test_poi_60316_drawing_shapes_and_hf_rels():
    """Verify wps:wsp shapes and header/footer relationships in poi__60316.docx."""
    path = DOCX_DIR / "poi__60316.docx"
    assert path.exists()

    raw_data = path.read_bytes()
    doc = read_docx(raw_data)
    out_bytes = write_docx(doc)

    orig_names, orig_files = load_package_xml(raw_data)
    saved_names, saved_files = load_package_xml(out_bytes)
    orig_feats = extract_word_features(orig_names, orig_files)
    saved_feats = extract_word_features(saved_names, saved_files)
    assert saved_feats.get("drawing shapes (wps)", 0) >= orig_feats.get("drawing shapes (wps)", 5)

    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        namelist = zf.namelist()
        assert "word/_rels/settings.xml.rels" in namelist
        assert "customXml/_rels/item1.xml.rels" in namelist


def test_tdf113183_wps_roundtrip():
    """Verify that wps:wsp shapes in libreoffice__tdf113183.docx are preserved."""
    path = DOCX_DIR / "libreoffice__tdf113183.docx"
    assert path.exists()

    raw_data = path.read_bytes()
    doc = read_docx(raw_data)
    out_bytes = write_docx(doc)

    orig_names, orig_files = load_package_xml(raw_data)
    saved_names, saved_files = load_package_xml(out_bytes)
    orig_feats = extract_word_features(orig_names, orig_files)
    saved_feats = extract_word_features(saved_names, saved_files)
    assert saved_feats.get("drawing shapes (wps)", 0) >= orig_feats.get("drawing shapes (wps)", 2)


def test_drawing_plain_text_edge_cases():
    """Test plain_text on DrawingObject under various conditions."""
    obj = DrawingObject()
    assert obj.plain_text() == ""

    raw_no_txbx = "<w:drawing><wp:inline><a:graphic/></wp:inline></w:drawing>"
    obj_no_txbx = DrawingObject(raw_xml=raw_no_txbx)
    assert obj_no_txbx.plain_text() == ""

    xml_with_text = (
        '<w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:txbxContent><w:p><w:r><w:t>Hello </w:t><w:t>World!</w:t></w:r></w:p></w:txbxContent>"
        "</w:drawing>"
    )
    obj_with_text = DrawingObject(raw_xml=xml_with_text)
    assert obj_with_text.plain_text() == "Hello World!"
