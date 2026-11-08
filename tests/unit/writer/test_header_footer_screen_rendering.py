"""Unit tests for Quire screen canvas header/footer rendering and dynamic fields (Issue #309)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.layout.pagination import (
    paginate_document,
)
from atboffice.modules.writer.models.document import (
    BreakItem,
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    Story,
    TextItem,
    reindex,
)
from atboffice.modules.writer.views.canvas_view import WriterCanvasView


class RecordingPainter(QPainter):
    """QPainter subclass that intercepts and records drawText calls and active pens."""

    def __init__(self, target: QImage) -> None:
        super().__init__(target)
        self.drawn_texts: list[tuple[QPointF, str, QColor, float]] = []

    def drawText(self, *args) -> None:  # type: ignore[override]
        # Match QPointF, text
        if len(args) >= 2:
            pt = args[0]
            txt = args[1]
            if isinstance(pt, QPointF) and isinstance(txt, str):
                pen_color = self.pen().color()
                font_pt_sz = self.font().pointSizeF()
                self.drawn_texts.append((pt, txt, pen_color, font_pt_sz))
        super().drawText(*args)


def test_canvas_view_paints_header_and_footer_in_subdued_gray(qapp: QApplication) -> None:
    """Verify that WriterCanvasView paints header and footer text on screen in subdued gray."""
    doc = Document()
    doc.sect.pg_w = 612.0
    doc.sect.pg_h = 792.0
    doc.sect.hdr = 36.0
    doc.sect.ftr = 36.0
    doc.sect.mt = 72.0
    doc.sect.mb = 72.0

    doc.sect.refs["hdr"]["default"] = "hdr_def"
    doc.sect.refs["ftr"]["default"] = "ftr_def"
    doc.hf["hdr_def"] = Story(
        kind="header",
        blocks=[Paragraph(runs=[TextItem(text="Confidential Screen Header")])],
    )
    doc.hf["ftr_def"] = Story(
        kind="footer",
        blocks=[Paragraph(runs=[TextItem(text="Internal Use Only Footer")])],
    )
    doc.main.blocks = [Paragraph(runs=[TextItem(text="Body text paragraph")])]
    reindex(doc)

    canvas = WriterCanvasView(doc=doc)
    canvas.resize(800, 1000)

    # Verify pages paginated with header and footer
    assert len(canvas.pagination.pages) == 1
    page = canvas.pagination.pages[0]
    assert page.header is not None
    assert page.footer is not None

    img = QImage(800, 1000, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    painter = RecordingPainter(img)
    page_rect = QRectF(50.0, 50.0, canvas.pt_to_px(612.0), canvas.pt_to_px(792.0))

    canvas._paint_page_content(painter, page_rect, page)
    painter.end()

    texts = [t[1] for t in painter.drawn_texts]
    assert "Confidential" in texts and "Header" in texts
    assert "Internal" in texts and "Footer" in texts
    assert "Body" in texts and "paragraph" in texts

    # Verify header and footer are drawn in subdued gray #666666
    for pt, txt, col, sz in painter.drawn_texts:
        if txt in ("Confidential", "Screen", "Header", "Internal", "Use", "Only", "Footer"):
            assert col.name().lower() == "#666666"


def test_dynamic_page_number_fields_in_header_footer(qapp: QApplication) -> None:
    """Verify dynamic PAGE and NUMPAGES fields evaluate per-page in header and footer."""
    doc = Document()
    doc.sect.pg_w = 612.0
    doc.sect.pg_h = 792.0
    doc.sect.refs["ftr"]["default"] = "ftr_def"

    fb_page = FieldBeginItem(field_type="PAGE", instr="PAGE")
    fe_page = FieldEndItem()
    fb_num = FieldBeginItem(field_type="NUMPAGES", instr="NUMPAGES")
    fe_num = FieldEndItem()

    footer_para = Paragraph(
        runs=[
            TextItem(text="Page "),
            fb_page,
            FieldSeparateItem(),
            TextItem(text=""),
            fe_page,
            TextItem(text=" of "),
            fb_num,
            FieldSeparateItem(),
            TextItem(text=""),
            fe_num,
        ]
    )
    doc.hf["ftr_def"] = Story(kind="footer", blocks=[footer_para])

    # 2 pages: page 1 has a page break
    p1 = Paragraph(runs=[TextItem(text="Page 1 body"), BreakItem(break_type="page")])
    p2 = Paragraph(runs=[TextItem(text="Page 2 body")])
    doc.main.blocks = [p1, p2]
    reindex(doc)

    canvas = WriterCanvasView(doc=doc)
    assert len(canvas.pagination.pages) == 2

    # Check Page 1
    page1 = canvas.pagination.pages[0]
    img1 = QImage(800, 1000, QImage.Format.Format_ARGB32)
    painter1 = RecordingPainter(img1)
    rect1 = QRectF(50.0, 50.0, canvas.pt_to_px(612.0), canvas.pt_to_px(792.0))
    canvas._paint_page_content(painter1, rect1, page1)
    painter1.end()
    texts1 = [t[1] for t in painter1.drawn_texts]

    # Check Page 2
    page2 = canvas.pagination.pages[1]
    img2 = QImage(800, 1000, QImage.Format.Format_ARGB32)
    painter2 = RecordingPainter(img2)
    rect2 = QRectF(50.0, 50.0, canvas.pt_to_px(612.0), canvas.pt_to_px(792.0))
    canvas._paint_page_content(painter2, rect2, page2)
    painter2.end()
    texts2 = [t[1] for t in painter2.drawn_texts]

    # Verify page 1 rendered "Page", "1", "of", "2"
    assert "1" in texts1
    assert "2" in texts1
    # Verify page 2 rendered "Page", "2", "of", "2"
    assert "2" in texts2
    # Ensure page 1 has "Page1of2" and page 2 has "Page2of2"
    joined1 = "".join(texts1)
    joined2 = "".join(texts2)
    assert "Page1of2" in joined1
    assert "Page2of2" in joined2


def test_different_first_page_header_footer(qapp: QApplication) -> None:
    """Verify different first page (w:titlePg) displays first page header on page 1."""
    doc = Document()
    doc.sect.pg_w = 612.0
    doc.sect.pg_h = 792.0
    doc.sect.title_pg = True
    doc.sect.refs["hdr"]["first"] = "hdr_first"
    doc.sect.refs["hdr"]["default"] = "hdr_default"

    doc.hf["hdr_first"] = Story(
        kind="header",
        blocks=[Paragraph(runs=[TextItem(text="Cover Page Header")])],
    )
    doc.hf["hdr_default"] = Story(
        kind="header",
        blocks=[Paragraph(runs=[TextItem(text="Body Chapter Header")])],
    )

    p1 = Paragraph(runs=[TextItem(text="First page text"), BreakItem(break_type="page")])
    p2 = Paragraph(runs=[TextItem(text="Second page text")])
    doc.main.blocks = [p1, p2]
    reindex(doc)

    canvas = WriterCanvasView(doc=doc)
    assert len(canvas.pagination.pages) == 2

    # Render page 1
    img1 = QImage(800, 1000, QImage.Format.Format_ARGB32)
    painter1 = RecordingPainter(img1)
    rect1 = QRectF(50.0, 50.0, canvas.pt_to_px(612.0), canvas.pt_to_px(792.0))
    canvas._paint_page_content(painter1, rect1, canvas.pagination.pages[0])
    painter1.end()
    texts1 = [t[1] for t in painter1.drawn_texts]
    assert "Cover" in texts1 and "Header" in texts1
    assert "Chapter" not in texts1

    # Render page 2
    img2 = QImage(800, 1000, QImage.Format.Format_ARGB32)
    painter2 = RecordingPainter(img2)
    rect2 = QRectF(50.0, 50.0, canvas.pt_to_px(612.0), canvas.pt_to_px(792.0))
    canvas._paint_page_content(painter2, rect2, canvas.pagination.pages[1])
    painter2.end()
    texts2 = [t[1] for t in painter2.drawn_texts]
    assert "Chapter" in texts2 and "Header" in texts2
    assert "Cover" not in texts2


def test_even_odd_headers_rendering(qapp: QApplication) -> None:
    """Verify evenAndOddHeaders setting displays odd header on page 1 and even header on page 2."""
    doc = Document()
    doc.sect.pg_w = 612.0
    doc.sect.pg_h = 792.0
    doc.settings["evenAndOddHeaders"] = True
    doc.sect.refs["hdr"]["default"] = "hdr_odd"
    doc.sect.refs["hdr"]["even"] = "hdr_even"

    doc.hf["hdr_odd"] = Story(
        kind="header",
        blocks=[Paragraph(runs=[TextItem(text="Odd Page Header")])],
    )
    doc.hf["hdr_even"] = Story(
        kind="header",
        blocks=[Paragraph(runs=[TextItem(text="Even Page Header")])],
    )

    p1 = Paragraph(runs=[TextItem(text="Odd page body"), BreakItem(break_type="page")])
    p2 = Paragraph(runs=[TextItem(text="Even page body")])
    doc.main.blocks = [p1, p2]
    reindex(doc)

    canvas = WriterCanvasView(doc=doc)
    assert len(canvas.pagination.pages) == 2

    # Render page 1 (odd)
    img1 = QImage(800, 1000, QImage.Format.Format_ARGB32)
    painter1 = RecordingPainter(img1)
    rect1 = QRectF(50.0, 50.0, canvas.pt_to_px(612.0), canvas.pt_to_px(792.0))
    canvas._paint_page_content(painter1, rect1, canvas.pagination.pages[0])
    painter1.end()
    texts1 = [t[1] for t in painter1.drawn_texts]
    assert "Odd" in texts1 and "Header" in texts1
    assert "Even" not in texts1

    # Render page 2 (even)
    img2 = QImage(800, 1000, QImage.Format.Format_ARGB32)
    painter2 = RecordingPainter(img2)
    rect2 = QRectF(50.0, 50.0, canvas.pt_to_px(612.0), canvas.pt_to_px(792.0))
    canvas._paint_page_content(painter2, rect2, canvas.pagination.pages[1])
    painter2.end()
    texts2 = [t[1] for t in painter2.drawn_texts]
    assert "Even" in texts2 and "Header" in texts2
    assert "Odd" not in texts2


def test_header_footer_no_body_overlap() -> None:
    """Verify that tall headers and footers expand margins and never overlap body content."""
    doc = Document()
    doc.sect.pg_w = 612.0
    doc.sect.pg_h = 792.0
    doc.sect.hdr = 20.0
    doc.sect.ftr = 20.0
    doc.sect.mt = 50.0
    doc.sect.mb = 50.0

    doc.sect.refs["hdr"]["default"] = "hdr_tall"
    doc.sect.refs["ftr"]["default"] = "ftr_tall"

    # Header with 4 lines (~60 pt)
    hdr_text = "Header Line 1\nHeader Line 2\nHeader Line 3\nHeader Line 4"
    doc.hf["hdr_tall"] = Story(
        kind="header",
        blocks=[Paragraph(runs=[TextItem(text=hdr_text)])],
    )
    # Footer with 3 lines (~45 pt)
    ftr_text = "Footer Line 1\nFooter Line 2\nFooter Line 3"
    doc.hf["ftr_tall"] = Story(
        kind="footer",
        blocks=[Paragraph(runs=[TextItem(text=ftr_text)])],
    )
    doc.main.blocks = [Paragraph(runs=[TextItem(text="Document Body")])]
    reindex(doc)

    res = paginate_document(doc)
    page = res.pages[0]

    assert page.header is not None
    assert page.footer is not None

    # Header bottom must not exceed page.body_top
    header_bottom = page.header.y + page.header.height
    assert page.body_top >= header_bottom, (
        f"Overlap: body_top={page.body_top} < header_bottom={header_bottom}"
    )

    # Body bottom must not exceed footer.y
    body_bottom = page.body_top + page.body_height
    assert page.footer.y >= body_bottom - 0.01, (
        f"Overlap: footer.y={page.footer.y} < body_bottom={body_bottom}"
    )
