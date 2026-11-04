"""Phase 7 DOCX Strict and complex structure rendering verification.

Covers TASK-705 (Issue #239):
- Strict OpenXML reading and rendering (7 text nodes in libreoffice__strict.docx)
- Text box extraction in nested runs
- Structured Document Tags (SDT) in footers and sections
- Header/footer part-relative image relationship resolution
- Track revisions (ins/del) extraction
- Offscreen and native Qt painting verification without unhandled exceptions
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.io import read_docx, write_docx
from atboffice.modules.writer.models.document import all_paragraphs, ptext, reindex
from atboffice.modules.writer.models.drawing import PictureItem
from atboffice.modules.writer.models.omml import OfficeMathItem
from atboffice.modules.writer.views.canvas_view import WriterCanvasView

DOCX_DIR = Path("tests/docs/word/docx")


def _collect_all_doc_texts(doc) -> list[str]:
    """Collect plain text from all paragraphs and math items across all stories."""
    texts: list[str] = []
    reindex(doc)
    paras = all_paragraphs(doc, all_stories=True)
    for p in paras:
        pt = ptext(p)
        if pt.strip():
            texts.append(pt.strip())
        for r in p.runs:
            if isinstance(r, OfficeMathItem):
                for node in r.nodes:
                    txt = getattr(node, "text", "")
                    if txt:
                        texts.append(txt)
    return texts


def test_strict_docx_nodes_parsed_and_rendered(qapp: QApplication) -> None:
    strict_path = DOCX_DIR / "libreoffice__strict.docx"
    assert strict_path.exists(), f"Missing corpus file: {strict_path}"

    data = strict_path.read_bytes()
    doc = read_docx(data)
    reindex(doc)

    assert len(doc.main.blocks) >= 4, "Strict document body blocks must not be empty fallback"

    # All 7 source text nodes must enter the document model
    expected_texts = [
        "Hello world!",
        "This is a chart:",
        "And this is a smart-art:",
        "This is math:",
        "A=π",
        "r",
        "2",
    ]
    all_texts = _collect_all_doc_texts(doc)
    combined = " ".join(all_texts)
    for expected in expected_texts:
        assert expected in combined, (
            f"Expected text node {expected!r} missing from parsed strict doc"
        )

    # Verify rendering on canvas without unhandled Qt exceptions
    view = WriterCanvasView(doc=doc)
    view.resize(900, 1100)
    assert len(view.pagination.pages) >= 1

    img = QImage(900, 1100, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    try:
        view.render(painter, QPoint())
    finally:
        painter.end()


def test_nested_runs_textbox_extracted() -> None:
    path = DOCX_DIR / "libreoffice__nested-runs.docx"
    assert path.exists()

    doc = read_docx(path.read_bytes())
    reindex(doc)

    all_texts = _collect_all_doc_texts(doc)
    combined = " ".join(all_texts)
    assert "Test text box" in combined, "Text box content must be extracted from drawing/pict"


def test_sdt_ignored_footer_and_sections() -> None:
    path = DOCX_DIR / "libreoffice__sdt-ignored-footer.docx"
    assert path.exists()

    doc = read_docx(path.read_bytes())
    reindex(doc)

    main_texts = [ptext(p) for p in doc.main.paras if ptext(p).strip()]
    assert any("First section" in t for t in main_texts)
    assert any("Second section" in t for t in main_texts)

    # Footer containing date in SDT
    all_texts = _collect_all_doc_texts(doc)
    combined = " ".join(all_texts)
    assert "September 22, 2014" in combined, "Footer date inside SDT must be extracted"


def test_header_picture_resolved() -> None:
    path = DOCX_DIR / "poi__headerPic.docx"
    assert path.exists()

    doc = read_docx(path.read_bytes())
    reindex(doc)

    # Check that pictures inside headers have valid image_part resolved
    header_pics: list[PictureItem] = []
    for hf_story in doc.hf.values():
        for p in hf_story.paras:
            for r in p.runs:
                if isinstance(r, PictureItem):
                    header_pics.append(r)

    assert len(header_pics) >= 1, "Expected picture item in header story"
    assert any("image" in p.image_part for p in header_pics), (
        "Header picture must resolve image part"
    )


def test_tdf125881_revisions_extracted() -> None:
    path = DOCX_DIR / "libreoffice__tdf125881.docx"
    assert path.exists()

    doc = read_docx(path.read_bytes())
    reindex(doc)

    all_texts = _collect_all_doc_texts(doc)
    assert len(all_texts) == 4, "Document paragraphs must be extracted"
    assert len(doc.main.paras) >= 10, "Revisions (ins/del) and paragraphs must be preserved"


def test_strict_docx_roundtrip() -> None:
    path = DOCX_DIR / "libreoffice__strict.docx"
    data = path.read_bytes()
    doc = read_docx(data)

    saved_bytes = write_docx(doc)
    assert len(saved_bytes) > 0

    reloaded_doc = read_docx(saved_bytes)
    reindex(reloaded_doc)

    all_texts = _collect_all_doc_texts(reloaded_doc)
    combined = " ".join(all_texts)
    assert "Hello world!" in combined
