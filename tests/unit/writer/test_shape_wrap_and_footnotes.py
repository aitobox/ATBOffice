"""Unit tests for Quire floating shapes text wrapping and page bottom footnotes layout."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPainter, QPixmap

from atboffice.modules.writer.layout.pagination import (
    paginate_document,
)
from atboffice.modules.writer.layout.portions import (
    PortionType,
    decompose_paragraph_to_portions,
    layout_paragraph,
)
from atboffice.modules.writer.layout.wrap import FloatBox
from atboffice.modules.writer.models.document import (
    Document,
    NoteRefItem,
    Paragraph,
    Story,
    TextItem,
)
from atboffice.modules.writer.models.drawing import (
    FloatProperties,
    PictureItem,
    PositionH,
    PositionV,
    WrapDist,
    WrapMode,
    WrapSide,
)


def test_note_ref_item_portion_decomposition():
    """Verify NoteRefItem generates a superscript portion with note_id reference."""
    note_ref = NoteRefItem(kind="fn", note_id="1")
    p = Paragraph(runs=[TextItem(text="Hello world"), note_ref])

    portions = decompose_paragraph_to_portions(p)
    assert len(portions) >= 2

    # Find the footnote reference portion
    fn_portion = next((po for po in portions if getattr(po, "data", None) is note_ref), None)
    assert fn_portion is not None
    assert fn_portion.type == PortionType.TEXT
    assert fn_portion.text == "1"
    assert fn_portion.counts_for_height is True
    # Word standard: 65% of base font size (12.0 * 0.65 = 7.8)
    assert round(fn_portion.font_size, 1) == 7.8
    # Should have shifted ascent for superscript placement
    assert fn_portion.ascent > 8.0


def test_floating_shape_square_and_top_bottom_wrap():
    """Verify paragraph lines wrap around square obstacles and push down for obstacles."""
    # 1. Square wrap obstacle
    fb_square = FloatBox(
        x=150.0,
        y=20.0,
        w=100.0,
        h=40.0,
        wrap_mode=WrapMode.SQUARE,
        side=WrapSide.BOTH,
        dist=WrapDist(top=5.0, bottom=5.0, left=5.0, right=5.0),
    )

    long_text = "The quick brown fox jumps over the lazy dog. " * 8
    p = Paragraph(runs=[TextItem(text=long_text)])

    # Layout with square obstacle at col_left=72.0, container_width=400.0
    p_layout_sq = layout_paragraph(
        p,
        container_width=400.0,
        float_boxes=[fb_square],
        y_offset=10.0,
        col_left=72.0,
    )
    assert len(p_layout_sq.lines) >= 2

    # At least one line within vertical span of fb_square [15.0, 65.0] must avoid the obstacle
    wrapped_lines = [
        ln
        for ln in p_layout_sq.lines
        if (10.0 + ln.top + ln.height > 15.0 and 10.0 + ln.top < 65.0)
    ]
    assert len(wrapped_lines) > 0
    # Line width must be constrained by the obstacle (smaller than container width)
    for ln in wrapped_lines:
        assert ln.width < 400.0 or ln.indent_left > 0.0

    # 2. Top-Bottom wrap obstacle: lines are pushed down past the obstacle
    fb_tb = FloatBox(
        x=72.0,
        y=20.0,
        w=150.0,
        h=30.0,
        wrap_mode=WrapMode.TOP_BOTTOM,
        side=WrapSide.BOTH,
        dist=WrapDist(top=5.0, bottom=5.0, left=5.0, right=5.0),
    )
    p_layout_tb = layout_paragraph(
        p,
        container_width=400.0,
        float_boxes=[fb_tb],
        y_offset=10.0,
        col_left=72.0,
    )
    # Lines must not overlap vertical interval [15.0, 55.0]
    for ln in p_layout_tb.lines:
        ln_top = 10.0 + ln.top
        ln_bot = ln_top + ln.height
        # Must not be placed inside [15.0, 55.0]
        assert not (ln_bot > 15.0 and ln_top < 55.0)


def test_footnote_space_reservation_and_pagination():
    """Verify paginate_document reserves bottom space for footnotes with a 2-inch separator rule."""
    doc = Document()
    doc.fn["1"] = Story(
        kind="footnote",
        blocks=[Paragraph(runs=[TextItem(text="This is the first footnote text.")])],
    )

    doc.main.blocks = [
        Paragraph(
            runs=[
                TextItem(text="Body paragraph referencing footnote 1."),
                NoteRefItem(kind="fn", note_id="1"),
            ]
        ),
        Paragraph(runs=[TextItem(text="Another regular paragraph in the body.")]),
    ]

    res = paginate_document(doc)
    assert len(res.pages) >= 1
    page = res.pages[0]

    assert page.footnote_area is not None
    assert page.footnote_area.separator_width == 144.0  # Exactly 2 inches
    assert "1" in page.footnote_area.note_ids
    assert len(page.footnote_area.fragments) >= 1
    assert page.footnote_area.y > 0.0
    assert page.footnote_area.height > 0.0
    # Footnote area must be positioned near the bottom of the page
    assert page.footnote_area.y + page.footnote_area.height <= page.height - page.section.mb + 2.0


def test_footnote_overflow_to_next_page():
    """Verify that when body text + footnote exceed page capacity, clean pagination occurs."""
    doc = Document()
    sect = doc.sect
    # Set a compact page height so paragraphs + footnotes cleanly overflow page 1
    sect.pg_h = 140.0
    sect.pg_w = 400.0
    sect.mt = 30.0
    sect.mb = 30.0

    doc.fn["1"] = Story(
        kind="footnote",
        blocks=[Paragraph(runs=[TextItem(text="Footnote 1 text.")])],
    )
    doc.fn["2"] = Story(
        kind="footnote",
        blocks=[Paragraph(runs=[TextItem(text="Footnote 2 detailed reference text.")])],
    )

    # Fill page 1 with paragraphs
    doc.main.blocks = [
        Paragraph(runs=[TextItem(text="Line 1 of body text.")]),
        Paragraph(runs=[TextItem(text="Line 2 of body text.")]),
        Paragraph(runs=[TextItem(text="Line 3 of body text.")]),
        Paragraph(
            runs=[
                TextItem(text="Line 4 of body text with note 1."),
                NoteRefItem(kind="fn", note_id="1"),
            ]
        ),
        Paragraph(
            runs=[
                TextItem(text="Line 5 of body text with note 2."),
                NoteRefItem(kind="fn", note_id="2"),
            ]
        ),
        Paragraph(runs=[TextItem(text="Line 6 of body text.")]),
    ]

    res = paginate_document(doc)
    # Must paginate across at least 2 pages
    assert len(res.pages) >= 2


def test_canvas_view_paint_footnotes_and_shapes(qtbot):
    """Verify WriterCanvasView paints footnote separator rule, footnote text, and shapes."""
    from atboffice.modules.writer.views.canvas_view import WriterCanvasView

    doc = Document()
    doc.fn["1"] = Story(
        kind="footnote",
        blocks=[Paragraph(runs=[TextItem(text="Footnote explanation text.")])],
    )

    # Add floating picture and footnote reference
    pic = PictureItem(
        width=80.0,
        height=60.0,
        float_pr=FloatProperties(
            wrap=WrapMode.SQUARE,
            pos_h=PositionH(rel="column", offset=50.0),
            pos_v=PositionV(rel="paragraph", offset=0.0),
        ),
    )

    doc.main.blocks = [
        Paragraph(
            runs=[
                TextItem(text="Paragraph with floating pic:"),
                pic,
                NoteRefItem(kind="fn", note_id="1"),
            ]
        ),
        Paragraph(
            runs=[TextItem(text="Follow-up paragraph wrapping nicely around floating objects.")]
        ),
    ]

    view = WriterCanvasView(doc=doc)
    view.resize(800, 600)
    qtbot.addWidget(view)

    # Test rendering directly onto a QPixmap via QPainter
    pix = QPixmap(800, 600)
    pix.fill(QColor(255, 255, 255))
    painter = QPainter(pix)
    page = view.pagination.pages[0]
    view.render_page_to_painter(painter, page, 0.0, 0.0)
    painter.end()

    # Ensure page has footnote area
    assert page.footnote_area is not None
    assert len(page.float_boxes) >= 1
