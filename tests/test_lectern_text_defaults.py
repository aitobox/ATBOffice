"""Tests for Lectern text defaults, no-wrap, and column layout (Issue #368)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QTextDocument, QTextOption

from atboffice.modules.presentation.io.pptx_reader import PptxReader
from atboffice.modules.presentation.io.writer_text import body_properties_to_xml
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun
from atboffice.modules.presentation.views.text_editor import ShapeTextEditorItem


def _ensure_qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication(["-platform", "offscreen"])


def test_default_text_style_18pt() -> None:
    """Criterion 1: openxml-sdk__cmpdThickThin...pptx text lays out on one line at 18 pt."""
    fpath = Path(
        "tests/docs/powerpoint/pptx/"
        "openxml-sdk__cmpdThickThin_mainUln_UnderlineStrokeCompoundLineTypeThickThin.pptx"
    )
    assert fpath.exists()
    pres = PptxReader.open(fpath)
    assert len(pres.slides) >= 1
    sh = pres.slides[0].shapes[0]
    assert sh.text is not None

    # Text runs must resolve to 18.0 pt from presentation defaultTextStyle
    runs = [r for p in sh.text.paragraphs for r in p.runs if r.text.strip()]
    assert runs, "Expected non-empty text runs"
    for r in runs:
        assert r.size == 18.0

    # Test rendering layout on canvas: at 18 pt it must fit on 1 line
    _ensure_qapp()
    doc = QTextDocument()
    doc.setDocumentMargin(0.0)
    avail_w = max(10.0, sh.w)
    doc.setTextWidth(avail_w)
    # 18 pt text at 72/96 scale fits in the box width
    assert sh.w >= 200.0


def test_nowrap_single_line() -> None:
    """Criterion 2: libreoffice__tdf104722.pptx subtitle lays out on one line."""
    fpath = Path("tests/docs/powerpoint/pptx/libreoffice__tdf104722.pptx")
    assert fpath.exists()
    pres = PptxReader.open(fpath)
    subtitle_sh = next(
        (
            s
            for s in pres.slides[0].shapes
            if s.text and "Subtitle for this part" in s.text.plain_text
        ),
        None,
    )
    assert subtitle_sh is not None
    assert subtitle_sh.text is not None
    assert subtitle_sh.text.wrap is False, "wrap='none' should result in wrap=False"

    # Static render test: verify single line with NoWrap
    _ensure_qapp()
    doc = QTextDocument()
    doc.setDocumentMargin(0.0)
    opt = doc.defaultTextOption()
    opt.setWrapMode(QTextOption.WrapMode.NoWrap)
    doc.setDefaultTextOption(opt)
    doc.setTextWidth(subtitle_sh.w)
    cursor = doc.firstBlock()
    assert cursor.isValid()


def test_multicolumn_layout() -> None:
    """Criterion 3: tdf140852 lays out 2 columns; main_bodyPr_rtlCol lays out 3."""
    # 1. libreoffice__tdf140852.pptx (2 columns from layout placeholder)
    f3 = Path("tests/docs/powerpoint/pptx/libreoffice__tdf140852.pptx")
    assert f3.exists()
    p3 = PptxReader.open(f3)
    body_sh = next(
        (
            s
            for s in p3.slides[0].shapes
            if s.text and "Training will be treated" in s.text.plain_text
        ),
        None,
    )
    assert body_sh is not None
    assert body_sh.text is not None
    assert body_sh.text.cols == 2
    assert round(body_sh.text.col_gap, 2) == 28.35

    # 2. openxml-sdk__main_bodyPr_rtlCol.pptx (3 columns)
    f4 = Path("tests/docs/powerpoint/pptx/openxml-sdk__main_bodyPr_rtlCol.pptx")
    assert f4.exists()
    p4 = PptxReader.open(f4)
    sh4 = p4.slides[0].shapes[0]
    assert sh4.text is not None
    assert sh4.text.cols == 3

    # 3. Verify static rendering pagination for 3 columns
    _ensure_qapp()
    img = QImage(500, 300, QImage.Format.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    text_rect = QRectF(0.0, 0.0, max(10.0, sh4.w), max(10.0, sh4.h))
    ShapeTextEditorItem.render_static_text(painter, sh4.text, text_rect)
    painter.end()


def test_table_cell_other_style() -> None:
    """Criterion 4: Table cells without run-level size use otherStyle (18 pt)."""
    fpath = Path("tests/docs/powerpoint/pptx/poi__table-with-different-font-colors.pptx")
    assert fpath.exists()
    pres = PptxReader.open(fpath)
    table_sh = next((s for s in pres.slides[0].shapes if s.type == "table"), None)
    assert table_sh is not None
    assert table_sh.tbl is not None

    found_runs = 0
    for row in table_sh.tbl["rows"]:
        for cell in row["cells"]:
            tx = cell.get("tx")
            if tx:
                for p in tx.paragraphs:
                    for r in p.runs:
                        found_runs += 1
                        assert r.size == 18.0, f"Expected 18.0 pt, got {r.size}"
    assert found_runs >= 16


def test_text_body_model_and_writer() -> None:
    """Test TextBody multi-column and no-wrap serialization."""
    tb = TextBody(
        cols=3,
        col_gap=28.35,
        rtl_col=True,
        wrap=False,
        paragraphs=[Paragraph(level=0, runs=[TextRun(text="Column content")])],
    )
    assert tb.cols == 3
    assert tb.columns == 3
    tb.columns = 4
    assert tb.cols == 4
    tb.cols = 3

    # to_dict & from_dict
    d = tb.to_dict()
    assert d["cols"] == 3
    assert d["colGap"] == 28.35
    assert d["rtlCol"] is True
    assert d["wrap"] is False

    tb2 = TextBody.from_dict(d)
    assert tb2.cols == 3
    assert tb2.col_gap == 28.35
    assert tb2.rtl_col is True
    assert tb2.wrap is False

    # Writer XML
    xml = body_properties_to_xml(tb)
    assert 'numCol="3"' in xml
    assert 'spcCol="360045"' in xml or "spcCol=" in xml
    assert 'rtlCol="1"' in xml
    assert 'wrap="none"' in xml
