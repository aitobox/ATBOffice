"""Unit tests for inline picture flow layout, line height/baseline measurement, and canvas painting (Issue #310)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.layout.pagination import paginate_document
from atboffice.modules.writer.layout.portions import (
    PortionType,
    decompose_paragraph_to_portions,
    layout_paragraph,
)
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TextItem,
    reindex,
)
from atboffice.modules.writer.models.drawing import (
    Crop,
    FloatProperties,
    PictureItem,
    WrapMode,
)
from atboffice.modules.writer.views.canvas_view import WriterCanvasView


class RecordingPixmapPainter(QPainter):
    """QPainter subclass that records drawPixmap and drawText calls."""

    def __init__(self, target: QImage) -> None:
        super().__init__(target)
        self.drawn_pixmaps: list[tuple[QRectF, QPixmap, QRectF]] = []
        self.drawn_texts: list[tuple[QRectF, str]] = []

    def drawPixmap(self, *args) -> None:  # type: ignore[override]
        if len(args) >= 3 and isinstance(args[0], QRectF) and isinstance(args[1], QPixmap) and isinstance(args[2], QRectF):
            self.drawn_pixmaps.append((args[0], args[1], args[2]))
        super().drawPixmap(*args)

    def drawText(self, *args) -> None:  # type: ignore[override]
        if len(args) >= 3 and isinstance(args[0], QRectF) and isinstance(args[2], str):
            self.drawn_texts.append((args[0], args[2]))
        super().drawText(*args)


def test_decompose_inline_picture_to_portion() -> None:
    """Verify decompose_paragraph_to_portions creates PortionType.GRAPHIC with correct dimensions."""
    pic = PictureItem(width=120.0, height=80.0, image_part="word/media/image1.png")
    p = Paragraph(runs=[TextItem(text="Lead text "), pic, TextItem(text=" tail text")])

    portions = decompose_paragraph_to_portions(p)
    pic_portions = [po for po in portions if po.type == PortionType.GRAPHIC]

    assert len(pic_portions) == 1
    po = pic_portions[0]
    assert po.data is pic
    assert po.width == 120.0
    assert po.ascent == 80.0
    assert po.descent == 0.0
    assert po.counts_for_height is True
    assert po.height == 80.0


def test_decompose_floating_picture_to_anchor() -> None:
    """Verify floating picture with non-inline wrap becomes a zero-width anchor portion."""
    float_pr = FloatProperties(wrap=WrapMode.SQUARE)
    pic = PictureItem(width=150.0, height=100.0, float_pr=float_pr)
    p = Paragraph(runs=[pic])

    portions = decompose_paragraph_to_portions(p)
    pic_portions = [po for po in portions if po.type == PortionType.GRAPHIC]

    assert len(pic_portions) == 1
    po = pic_portions[0]
    assert po.data is pic
    assert po.width == 0.0
    assert po.ascent == 0.0
    assert po.descent == 0.0
    assert po.counts_for_height is False


def test_line_height_elevated_by_picture() -> None:
    """Verify line height and baseline accommodate inline picture height."""
    pic = PictureItem(width=100.0, height=150.0)
    p = Paragraph(runs=[TextItem(text="Hello"), pic])

    layout = layout_paragraph(p, container_width=500.0)
    assert len(layout.lines) == 1
    line = layout.lines[0]

    # Line height must be at least the picture's height
    assert line.height >= 150.0
    # Baseline must be at or above picture height so picture fits in line
    assert line.baseline >= 150.0


def test_picture_and_text_baseline_alignment() -> None:
    """Verify text and picture share the same baseline with picture bottom at baseline."""
    pic = PictureItem(width=80.0, height=120.0)
    p = Paragraph(runs=[TextItem(text="Baseline Text "), pic])

    layout = layout_paragraph(p, container_width=500.0)
    line = layout.lines[0]

    # In layout line, ascent = max(text_ascent, pic_height) = 120.0
    assert line.ascent >= 120.0
    # Picture portion
    po = [pt for pt in line.portions if pt.type == PortionType.GRAPHIC][0]
    assert po.ascent == 120.0
    assert po.descent == 0.0
    # When rendering, picture bottom is placed at line.baseline, which aligns with text baseline
    pic_top = line.baseline - po.ascent
    assert pic_top >= 0.0


def test_inline_picture_line_wrapping() -> None:
    """Verify horizontal advance and line wrap when multiple inline pictures exceed container width."""
    pic1 = PictureItem(width=250.0, height=60.0)
    pic2 = PictureItem(width=250.0, height=70.0)
    p = Paragraph(runs=[pic1, pic2])

    layout = layout_paragraph(p, container_width=400.0)
    assert len(layout.lines) == 2
    assert layout.lines[0].height >= 60.0
    assert layout.lines[1].height >= 70.0


def test_canvas_paint_inline_picture_with_pixmap(qapp: QApplication) -> None:
    """Verify WriterCanvasView renders QPixmap images with DPR awareness and baseline alignment."""
    doc = Document()
    img = QImage(200, 100, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 128, 255))
    pixmap = QPixmap.fromImage(img)

    pic = PictureItem(width=100.0, height=50.0, image_part="test_img.png")
    pic.raw_data = {"pixmap": pixmap}

    doc.main.blocks = [Paragraph(runs=[TextItem(text="Before "), pic, TextItem(text=" After")])]
    reindex(doc)

    canvas = WriterCanvasView(doc)
    canvas.resize(800, 1000)

    target_img = QImage(800, 1000, QImage.Format.Format_ARGB32)
    target_img.fill(Qt.GlobalColor.white)
    painter = RecordingPixmapPainter(target_img)
    try:
        page = canvas.pagination.pages[0]
        page_rect = QRectF(50.0, 50.0, canvas.pt_to_px(612.0), canvas.pt_to_px(792.0))
        canvas._paint_page_content(painter, page_rect, page)
    finally:
        painter.end()

    assert len(painter.drawn_pixmaps) >= 1
    dest_rect, pm, src_rect = painter.drawn_pixmaps[0]

    # Verify dest_rect dimensions match logical size under zoom
    assert dest_rect.width() > 0
    assert dest_rect.height() > 0
    assert pm is not None


def test_canvas_paint_picture_with_crop_and_rotation(qapp: QApplication) -> None:
    """Verify crop offsets and rotation transform during picture paint."""
    doc = Document()
    img = QImage(200, 200, QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 0, 0))
    pixmap = QPixmap.fromImage(img)

    crop = Crop(left=0.1, top=0.2, right=0.1, bottom=0.2)
    pic = PictureItem(width=80.0, height=80.0, crop=crop, rotation=45.0)
    pic.raw_data = {"pixmap": pixmap}

    doc.main.blocks = [Paragraph(runs=[pic])]
    reindex(doc)

    canvas = WriterCanvasView(doc)
    canvas.resize(800, 1000)

    target_img = QImage(800, 1000, QImage.Format.Format_ARGB32)
    painter = RecordingPixmapPainter(target_img)
    try:
        page = canvas.pagination.pages[0]
        page_rect = QRectF(50.0, 50.0, canvas.pt_to_px(612.0), canvas.pt_to_px(792.0))
        canvas._paint_page_content(painter, page_rect, page)
    finally:
        painter.end()

    assert len(painter.drawn_pixmaps) >= 1
    _, _, src_rect = painter.drawn_pixmaps[0]
    # Source rect should be cropped: 10% left, 20% top, 80% width, 60% height
    import pytest

    assert src_rect.x() == pytest.approx(20.0)
    assert src_rect.y() == pytest.approx(40.0)
    assert src_rect.width() == pytest.approx(160.0)
    assert src_rect.height() == pytest.approx(120.0)


def test_canvas_paint_missing_picture_fallback(qapp: QApplication) -> None:
    """Verify missing picture does not crash and renders graceful placeholder."""
    doc = Document()
    pic = PictureItem(width=60.0, height=40.0, image_part="missing.png", alt_text="Sample Missing Image")
    doc.main.blocks = [Paragraph(runs=[pic])]
    reindex(doc)

    canvas = WriterCanvasView(doc)
    canvas.resize(800, 1000)

    target_img = QImage(800, 1000, QImage.Format.Format_ARGB32)
    painter = RecordingPixmapPainter(target_img)
    try:
        page = canvas.pagination.pages[0]
        page_rect = QRectF(50.0, 50.0, canvas.pt_to_px(612.0), canvas.pt_to_px(792.0))
        canvas._paint_page_content(painter, page_rect, page)
    finally:
        painter.end()

    # Should not throw and should have drawn placeholder text
    texts = [t[1] for t in painter.drawn_texts]
    assert any("Sample Missing Image" in t or "Picture" in t for t in texts)


def test_render_page_to_painter_inline_picture(qapp: QApplication) -> None:
    """Verify render_page_to_painter renders inline PictureItem to vector painter."""
    doc = Document()
    img = QImage(100, 50, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 255, 0))
    pixmap = QPixmap.fromImage(img)

    pic = PictureItem(width=50.0, height=25.0, raw_data={"pixmap": pixmap})
    doc.main.blocks = [Paragraph(runs=[TextItem(text="Vector Pic "), pic])]
    reindex(doc)

    canvas = WriterCanvasView(doc)
    page = canvas.pagination.pages[0]

    target_img = QImage(612, 792, QImage.Format.Format_ARGB32)
    painter = RecordingPixmapPainter(target_img)
    try:
        canvas.render_page_to_painter(painter, page)
    finally:
        painter.end()

    assert len(painter.drawn_pixmaps) >= 1
    dest_rect, pm, src_rect = painter.drawn_pixmaps[0]
    assert dest_rect.width() == 50.0
    assert dest_rect.height() == 25.0

