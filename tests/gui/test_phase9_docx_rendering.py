"""Phase 9 DOCX layout drift regression and visual parity tests.

Covers Issue #334 fixes across:
- framePr positioning & centered/bold-italic paragraph rendering (tdf105035)
- Qt QFontMetricsF text measurement parity & table cell wrapping (tdf113182)
- Multi-column sections & wrapped LayoutLine baseline_offset accuracy (tdf121670)
- Justified word spacing distribution across missing-font substitutions (tdf43100)
- Arabic RTL bidi alignment, spellcheck suppression on non-ASCII/open, & comment gutter (Comment066)
- Numbering bullet font metrics tuple unpacking & Portion color propagation (bullet-complex)
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from office_diff.capture import capture_single_document  # noqa: E402
from office_diff.comparator import compare_canvases, is_blank_canvas  # noqa: E402
from office_diff.models import DocumentTarget  # noqa: E402

from atboffice.modules.writer.io import read_docx  # noqa: E402
from atboffice.modules.writer.layout.pagination import paginate_document  # noqa: E402
from atboffice.modules.writer.layout.portions import (  # noqa: E402
    PortionType,
    layout_paragraph,
)
from atboffice.modules.writer.models.document import (  # noqa: E402
    Document,
    Paragraph,
    Story,
    TextItem,
    reindex,
)
from atboffice.modules.writer.models.properties import (  # noqa: E402
    ParagraphProperties,
    RunProperties,
)
from atboffice.modules.writer.models.styles import resolve_p_props  # noqa: E402
from atboffice.modules.writer.spell import SpellEngine  # noqa: E402
from atboffice.modules.writer.views.canvas_view import WriterCanvasView  # noqa: E402

DOCX_DIR = REPO_ROOT / "tests" / "docs" / "word" / "docx"
BASELINE_DIR = (
    REPO_ROOT / "screenshots" / "office_audit_20261106" / "vibeoffice" / "word"
)

TARGET_FILES: tuple[str, ...] = (
    "libreoffice__tdf105035_framePrB.docx",
    "libreoffice__tdf113182.docx",
    "libreoffice__tdf121670_columnsInSectionsOnly.docx",
    "libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx",
    "openxml-sdk__Comment066.docx",
    "openxml-sdk__bullet-complex.docx",
)


def test_phase9_six_docx_render_and_visual_parity(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Render all 6 phase9 DOCX files and verify parity >= 88% each / >= 91% avg."""
    saved_dialogs = (
        QMessageBox.critical,
        QMessageBox.warning,
        QMessageBox.information,
        QMessageBox.question,
        QMessageBox.exec,
        QMessageBox.exec_,
        QDialog.exec,
        QDialog.exec_,
    )
    similarities: list[float] = []

    try:
        for name in TARGET_FILES:
            doc_path = DOCX_DIR / name
            assert doc_path.exists(), f"Missing fixture: {doc_path}"

            target = DocumentTarget(
                file=name,
                path=doc_path,
                format="docx",
                app="word",
                expected_status="rendered",
                is_supported=True,
            )
            cap = capture_single_document(target, out_dir=tmp_path)
            assert cap.status == "captured", f"Capture failed for {name}: {cap.error}"
            assert cap.screenshot_path is not None

            rendered_png = Path(cap.screenshot_path)
            assert rendered_png.exists()

            img = QImage(str(rendered_png))
            assert not is_blank_canvas(img), (
                f"Rendered canvas unexpectedly blank for {name}"
            )

            baseline_png = BASELINE_DIR / f"{name}.png"
            if baseline_png.exists():
                diff = compare_canvases(
                    baseline_png, rendered_png, app="word", file_name=name
                )
                assert diff.similarity is not None
                assert diff.orig_size == diff.target_size, (
                    f"Viewport mismatch for {name}: "
                    f"orig={diff.orig_size} target={diff.target_size}"
                )
                assert diff.similarity >= 0.88, (
                    f"{name} similarity {diff.similarity * 100:.2f}% "
                    "below 88.0% threshold"
                )
                similarities.append(diff.similarity)

        if similarities:
            avg_sim = sum(similarities) / len(similarities)
            assert avg_sim >= 0.91, (
                f"Average similarity {avg_sim * 100:.2f}% across "
                f"{len(similarities)} docs below 91.0%"
            )
    finally:
        (
            QMessageBox.critical,
            QMessageBox.warning,
            QMessageBox.information,
            QMessageBox.question,
            QMessageBox.exec,
            QMessageBox.exec_,
            QDialog.exec,
            QDialog.exec_,
        ) = saved_dialogs


def test_layout_line_baseline_offset_and_wrapped_metrics() -> None:
    """Multi-line paragraphs preserve baseline_offset and monotonic line tops."""
    doc = Document()
    para = Paragraph(
        runs=[
            TextItem(
                text=(
                    "Word wrapping regression check across multiple lines to ensure "
                    "baseline_offset equals baseline minus top cleanly."
                ),
                r_pr=RunProperties(font="Times New Roman", sz=12.0),
            )
        ]
    )
    doc.main.blocks.append(para)
    reindex(doc)

    p_layout = layout_paragraph(para, container_width=140.0, doc=doc)
    assert len(p_layout.lines) >= 3
    for idx, line in enumerate(p_layout.lines):
        assert line.height > 0.0
        assert line.baseline_offset == line.baseline - line.top
        assert 0.0 < line.baseline_offset < line.height
        if idx > 0:
            assert line.top > p_layout.lines[idx - 1].top


def test_paragraph_center_right_and_bidi_alignment() -> None:
    """Center/right justification and bidi default right alignment shift indent_left."""
    doc = Document()

    centered = Paragraph(
        runs=[TextItem(text="Centered Title", r_pr=RunProperties(sz=12.0))],
        p_pr=ParagraphProperties(jc="center", jc_explicit=True),
    )
    right_aligned = Paragraph(
        runs=[TextItem(text="Right Text", r_pr=RunProperties(sz=12.0))],
        p_pr=ParagraphProperties(jc="right", jc_explicit=True),
    )
    bidi_implicit = Paragraph(
        runs=[TextItem(text="فقرة عربية", r_pr=RunProperties(sz=12.0, rtl=True))],
        p_pr=ParagraphProperties(bidi=True, jc="left", jc_explicit=False),
    )
    bidi_explicit_left = Paragraph(
        runs=[TextItem(text="Explicit Left", r_pr=RunProperties(sz=12.0))],
        p_pr=ParagraphProperties(bidi=True, jc="left", jc_explicit=True),
    )
    doc.main.blocks.extend([centered, right_aligned, bidi_implicit, bidi_explicit_left])
    reindex(doc)

    c_line = layout_paragraph(centered, container_width=400.0, doc=doc).lines[0]
    r_line = layout_paragraph(right_aligned, container_width=400.0, doc=doc).lines[0]
    b_line = layout_paragraph(bidi_implicit, container_width=400.0, doc=doc).lines[0]

    assert 100.0 < c_line.indent_left < r_line.indent_left
    assert b_line.is_rtl is True
    assert resolve_p_props(doc, bidi_implicit).jc == "right"
    assert resolve_p_props(doc, bidi_explicit_left).jc == "left"
    assert b_line.indent_left > 250.0


def test_docx_reader_bidi_hide_spelling_and_comments_extended() -> None:
    """Comment066 parses bidi paragraphs, hide_spelling_errors, and reply parent_id."""
    comment_path = DOCX_DIR / "openxml-sdk__Comment066.docx"
    doc = read_docx(comment_path.read_bytes())
    reindex(doc)

    assert doc.hide_spelling_errors is True
    bidi_paras = [p for p in doc.main.paras if getattr(p.p_pr, "bidi", None) is True]
    assert len(bidi_paras) >= 1

    reply_comments = [c for c in doc.comments.values() if c.parent_id]
    assert len(reply_comments) >= 1


def test_spell_engine_ignores_non_ascii_in_en_us() -> None:
    """en_US SpellEngine must not flag non-ASCII Arabic words as misspelled."""
    engine = SpellEngine()
    engine.loaded_lang = "en_US"
    assert engine._check_word_raw("العراق") is True
    assert engine._check_word_raw("بغداد") is True


def test_bullet_complex_layout_and_non_blank_canvas(qapp: QApplication) -> None:
    """bullet-complex parses numbering metrics cleanly and paints non-blank pages."""
    bullet_path = DOCX_DIR / "openxml-sdk__bullet-complex.docx"
    doc = read_docx(bullet_path.read_bytes())
    reindex(doc)

    pages = paginate_document(doc)
    assert len(pages.pages) >= 1
    placed_lines = [
        line
        for reg in pages.pages[0].regions
        for col in reg.columns
        for frag in col.fragments
        for line in frag.lines
    ]
    assert any(line.portions for line in placed_lines)

    # Check Portion.color propagates on colored runs
    p_props = Paragraph(
        runs=[TextItem(text="Colored", r_pr=RunProperties(color="#1F497D"))]
    )
    colored_lines = layout_paragraph(p_props, container_width=300.0, doc=doc).lines
    text_portions = [
        pt for pt in colored_lines[0].portions if pt.type == PortionType.TEXT
    ]
    assert text_portions and text_portions[0].color == "#1F497D"

    view = WriterCanvasView(doc=doc)
    view.resize(1178, 767)
    img = QImage(1178, 767, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    try:
        view.render(painter, QPoint())
    finally:
        painter.end()
    assert not is_blank_canvas(img)


def test_canvas_view_comment_gutter_and_justified_render(qapp: QApplication) -> None:
    """Comments reserve right gutter and justified lines render cleanly under Calibri."""
    doc = Document()
    doc.main.blocks.append(
        Paragraph(
            runs=[
                TextItem(
                    text="JUSTIFIED1row multiple spaces across justified paragraph",
                    r_pr=RunProperties(font="Calibri", sz=11.0),
                )
            ],
            p_pr=ParagraphProperties(jc="both", jc_explicit=True),
        )
    )
    reply_story = Story(
        id="c1",
        author="Reviewer",
        initials="RV",
        parent_id="",
        blocks=[Paragraph(runs=[TextItem(text="Sample comment")])],
    )
    doc.comments["1"] = reply_story
    reindex(doc)

    view = WriterCanvasView(doc=doc)
    view.resize(1178, 767)
    assert view._comment_gutter_px() > 0.0
    total_w = view.total_canvas_size().width()
    assert total_w >= view.pt_to_px(doc.sect.pg_w) + view._comment_gutter_px()

    img = QImage(1178, 767, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    try:
        view.render(painter, QPoint())
    finally:
        painter.end()
    assert not is_blank_canvas(img)
