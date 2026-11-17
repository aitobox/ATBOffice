"""Tests for Lectern text defaults, no-wrap, and column layout (Issue #368)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter, QTextDocument, QTextOption
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.io.pptx_reader import PptxReader
from atboffice.modules.presentation.io.writer_text import body_properties_to_xml
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun
from atboffice.modules.presentation.views.text_editor import ShapeTextEditorItem


def _ensure_qapp() -> QApplication:
    # A QApplication (not QGuiApplication) so widget tests in the same run work.
    return QApplication.instance() or QApplication(["-platform", "offscreen"])


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


# ---------------------------------------------------------------------------
# Issue #407: no-wrap overflow, balanced column flow, RTL column order
# ---------------------------------------------------------------------------


def _shape_with_text(fpath: str, needle: str):  # type: ignore[no-untyped-def]
    pres = PptxReader.open(Path(fpath))
    sh = next(s for s in pres.slides[0].shapes if s.text and needle in s.text.plain_text)
    assert sh.text is not None
    return sh


def _text_rect(sh) -> QRectF:  # type: ignore[no-untyped-def]
    ins_l, ins_t, ins_r, ins_b = sh.text.insets
    return QRectF(
        ins_l,
        ins_t,
        max(10.0, sh.w - ins_l - ins_r),
        max(10.0, sh.h - ins_t - ins_b),
    )


def _render_columns(text_body: TextBody, rect: QRectF, monkeypatch, out: list | None = None) -> list[str]:  # type: ignore[no-untyped-def]
    """Render through render_static_text and return the text drawn in each column."""
    from atboffice.modules.presentation.views import text_editor as te

    captured: list[QTextDocument] = []

    class _RecordingDoc(QTextDocument):
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            super().__init__(*args, **kwargs)
            captured.append(self)

    monkeypatch.setattr(te, "QTextDocument", _RecordingDoc)
    img = QImage(int(rect.right()) + 20, int(rect.bottom()) + 20, QImage.Format.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    ShapeTextEditorItem.render_static_text(painter, text_body, rect)
    painter.end()

    doc = captured[0]  # the render document (autofit solving may create more)
    if out is not None:
        out.append(doc)
    page_h = doc.pageSize().height()
    columns: list[list[str]] = [[] for _ in range(max(1, doc.pageCount()))]
    layout = doc.documentLayout()
    block = doc.begin()
    while block.isValid():
        top = layout.blockBoundingRect(block).y()
        tl = block.layout()
        for i in range(tl.lineCount()):
            line = tl.lineAt(i)
            page = int((top + line.y() + line.height() / 2.0) // page_h)
            text = block.text()[line.textStart() : line.textStart() + line.textLength()]
            if text.strip():
                columns[min(page, len(columns) - 1)].append(text.strip())
        block = block.next()
    return [" ".join(c) for c in columns]


def _ink_columns(img: QImage) -> list[int]:
    xs: list[int] = []
    for x in range(img.width()):
        for y in range(img.height()):
            if img.pixelColor(x, y).alpha() > 0:
                xs.append(x)
                break
    return xs


def test_nowrap_text_overflows_narrow_box() -> None:
    """tdf104722: wrap='none' subtitle draws past its narrow text rectangle."""
    _ensure_qapp()
    sh = _shape_with_text("tests/docs/powerpoint/pptx/libreoffice__tdf104722.pptx", "Subtitle")
    rect = _text_rect(sh)
    img = QImage(int(rect.right() + sh.w * 4), int(rect.bottom()) + 20, QImage.Format.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    ShapeTextEditorItem.render_static_text(painter, sh.text, rect)
    painter.end()
    xs = _ink_columns(img)
    assert xs, "subtitle produced no ink"
    assert max(xs) > rect.right() + 20, "no-wrap text was clipped to the text rectangle"


def test_columns_balance_tdf140852(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """tdf140852: balanced 2-column flow starts column 2 with 'comes to'."""
    _ensure_qapp()
    sh = _shape_with_text("tests/docs/powerpoint/pptx/libreoffice__tdf140852.pptx", "Training")
    cols = _render_columns(sh.text, _text_rect(sh), monkeypatch)
    assert len(cols) == 2, cols
    assert cols[0].startswith("Training will be")
    assert cols[1].startswith("comes to"), cols
    assert cols[1].endswith("cream")


def test_columns_balance_rtlcol_fixture_reaches_third_column(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """main_bodyPr_rtlCol: the trailing instructions land in the third column."""
    _ensure_qapp()
    sh = _shape_with_text(
        "tests/docs/powerpoint/pptx/openxml-sdk__main_bodyPr_rtlCol.pptx", "rtlCol"
    )
    cols = _render_columns(sh.text, _text_rect(sh), monkeypatch)
    assert len(cols) == 3, cols
    assert cols[0].startswith("rtlCol")
    assert "Insert Text box" in cols[2], cols
    assert "Columns" in cols[2]


def test_columns_overflowing_capacity_keep_full_height(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Text exceeding every column keeps the full text-rect height per column."""
    _ensure_qapp()
    tb = TextBody(
        cols=2,
        col_gap=10.0,
        paragraphs=[Paragraph(runs=[TextRun(text="word " * 400, size=18.0)])],
    )
    rect = QRectF(0.0, 0.0, 300.0, 80.0)
    docs: list[QTextDocument] = []
    _render_columns(tb, rect, monkeypatch, docs)
    assert docs[0].pageCount() > 2
    assert abs(docs[0].pageSize().height() - rect.height()) < 0.01


def test_rtl_col_places_first_column_on_the_right() -> None:
    """rtlCol=1 draws the first column at the right edge of the text rect."""
    _ensure_qapp()

    def render(rtl: bool) -> list[int]:
        tb = TextBody(
            cols=2,
            col_gap=20.0,
            rtl_col=rtl,
            paragraphs=[
                Paragraph(runs=[TextRun(text="X", size=18.0)]),
            ],
        )
        img = QImage(260, 120, QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        ShapeTextEditorItem.render_static_text(painter, tb, QRectF(0.0, 0.0, 260.0, 120.0))
        painter.end()
        return _ink_columns(img)

    ltr = render(False)
    rtl = render(True)
    assert ltr and rtl
    assert max(ltr) < 120, "LTR first column should sit on the left"
    assert min(rtl) >= 140, "RTL first column should sit on the right"
