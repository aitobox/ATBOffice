"""Quire shows charts, SmartArt and their caption lines in the page flow (#379)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from itertools import combinations
from pathlib import Path

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from atboffice.modules.writer.io.docx_graphics import (
    dml_text_story,
    normalize_percentages,
    read_chart,
    smartart_from_data,
)
from atboffice.modules.writer.io.docx_reader import read_docx
from atboffice.modules.writer.io.docx_shapes import load_theme_colors
from atboffice.modules.writer.layout.portions import PortionType
from atboffice.modules.writer.models import ChartItem, Paragraph, PictureItem, ShapeItem
from atboffice.modules.writer.models.document import plain_text
from atboffice.modules.writer.views.canvas_view import WriterCanvasView

DOCX_DIR = Path(__file__).parent / "docs" / "word" / "docx"
STRICT = DOCX_DIR / "libreoffice__strict.docx"
SMARTART_BOXES = DOCX_DIR / "libreoffice__tdf54095_SmartArtThemeTextColor.docx"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
DGM = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
THEME = load_theme_colors(None)


def _render(canvas: WriterCanvasView, page_index: int = 0) -> QImage:
    page = canvas.pagination.pages[page_index]
    img = QImage(int(page.width) + 1, int(page.height) + 1, QImage.Format.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    p = QPainter(img)
    try:
        canvas.render_page_to_painter(p, page)
    finally:
        p.end()
    return img


def _render_screen(canvas: WriterCanvasView, page_index: int = 0) -> QImage:
    page = canvas.pagination.pages[page_index]
    w, h = canvas.pt_to_px(page.width), canvas.pt_to_px(page.height)
    img = QImage(int(w) + 1, int(h) + 1, QImage.Format.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    p = QPainter(img)
    try:
        canvas._paint_page_content(p, QRectF(0, 0, w, h), page)
    finally:
        p.end()
    return img


def _body_rects(canvas: WriterCanvasView) -> dict[str, QRectF]:
    """Page-space rectangles of the strict fixture's visible objects, keyed by name."""
    page = canvas.pagination.pages[0]
    rects: dict[str, QRectF] = {}
    hdr = page.header
    assert hdr is not None and hdr.fragments
    line = hdr.fragments[0].lines[0]
    rects["header"] = QRectF(page.body_left, hdr.y + line.top, line.width, line.height)
    for fb in page.float_boxes:
        rects["picture"] = QRectF(fb.x, fb.y, fb.w, fb.h)
    col = page.regions[0].columns[0]
    for frag in col.fragments:
        top = page.body_top + col.top + frag.top
        for ln in frag.lines:
            x = page.body_left + col.left + ln.indent_left
            baseline = top + ln.baseline
            text = ""
            text_rect = QRectF()
            for po in ln.portions:
                if po.type == PortionType.GRAPHIC and isinstance(po.data, ChartItem):
                    rects["chart"] = QRectF(x, baseline - po.ascent, po.width, po.ascent)
                elif po.type == PortionType.GRAPHIC and isinstance(po.data, ShapeItem):
                    rects["diagram"] = QRectF(x, baseline - po.ascent, po.width, po.ascent)
                elif po.type == PortionType.TEXT and po.text:
                    text += po.text
                    r = QRectF(x, baseline - po.ascent, po.width, po.ascent + po.descent)
                    text_rect = r if text_rect.isNull() else text_rect.united(r)
                elif po.type == PortionType.BLANK:
                    text += " "
                x += po.width
            if text.strip():
                rects[text.strip()] = text_rect
    return rects


# --------------------------------------------------------------------------- reading


def test_strict_auto_line_spacing_with_units_is_a_multiplier(qapp) -> None:
    # docDefaults: <w:spacing w:line="12.95pt" w:lineRule="auto"/> is 1.079 lines, not 12.95
    canvas = WriterCanvasView(doc=read_docx(STRICT))
    page = canvas.pagination.pages[0]
    # A 12.95x multiple would push the content across many pages. With the docDefaults
    # 8pt space after kept, the closing math line now lands on page 2 (VibeOffice keeps it
    # on page 1 because it does not scale inline-graphic lines by the multiple).
    assert len(canvas.pagination.pages) <= 2
    assert page.body_top == pytest.approx(72.0)  # header (36pt + one line) fits the margin
    assert page.header is not None and page.header.height < 40
    text_lines = [
        ln
        for f in page.regions[0].columns[0].fragments
        for ln in f.lines
        if all(po.type != PortionType.GRAPHIC for po in ln.portions)
    ]
    assert text_lines and all(ln.height < 30 for ln in text_lines)


def test_doc_grid_without_type_does_not_snap_lines() -> None:
    doc = read_docx(STRICT)
    sects = [b.sect for b in doc.main.blocks if isinstance(b, Paragraph) and b.sect]
    sect = sects[-1] if sects else doc.sect
    assert sect.doc_grid.type == "default"


def test_chart_frame_becomes_chart_item() -> None:
    doc = read_docx(STRICT)
    charts = [
        r
        for b in doc.main.blocks
        if isinstance(b, Paragraph)
        for r in b.runs
        if isinstance(r, ChartItem)
    ]
    assert len(charts) == 1
    chart = charts[0]
    assert chart.width == pytest.approx(360.0) and chart.height == pytest.approx(216.0)
    assert chart.chart.cats == ["1", "2", "3"]
    assert chart.chart.series[0].vals == [1.0, 2.0, 3.0]
    assert chart.chart.title == "Series 1"  # auto title from the only series
    assert chart.raw_xml and "chart" in chart.raw_xml  # round-trips verbatim


def test_unreadable_chart_part_keeps_picture_fallback() -> None:
    assert read_chart("<c:chartSpace xmlns:c='urn:x'/>") is None
    assert read_chart("not xml") is None


def test_smartart_frame_uses_stored_drawing() -> None:
    doc = read_docx(STRICT)
    (diagram,) = [
        r
        for b in doc.main.blocks
        if isinstance(b, Paragraph)
        for r in b.runs
        if isinstance(r, ShapeItem)
    ]
    ellipses = [c.item for c in diagram.children if c.item.geometry == "ellipse"]
    arrows = [c.item for c in diagram.children if c.item.geometry == "rightArrow"]
    assert len(ellipses) == 3 and len(arrows) == 3
    texts = sorted(plain_text(s.story.blocks[0]) for s in ellipses)
    assert texts == ["a", "b", "c"]
    assert ellipses[0].fill.kind == "solid"
    # Strict "60%" tint is honored: arrows are lighter than the circles
    assert arrows[0].fill.color != ellipses[0].fill.color


def test_smartart_boxes_are_outlined_rectangles() -> None:
    doc = read_docx(SMARTART_BOXES)
    (diagram,) = [
        r
        for b in doc.main.blocks
        if isinstance(b, Paragraph)
        for r in b.runs
        if isinstance(r, ShapeItem)
    ]
    assert diagram.float_pr is not None
    boxes = [c.item for c in diagram.children]
    assert len(boxes) == 3
    assert all(b.geometry == "rect" and b.line.visible for b in boxes)


def test_dml_text_story_runs_and_alignment() -> None:
    tx = ET.fromstring(
        f'<dsp:txBody xmlns:dsp="urn:dsp" xmlns:a="{A}"><a:bodyPr/>'
        '<a:p><a:pPr algn="r"/><a:r><a:rPr sz="2400" b="1"><a:solidFill>'
        '<a:srgbClr val="FF0000"/></a:solidFill></a:rPr><a:t>Hi</a:t></a:r></a:p>'
        '<a:p><a:endParaRPr sz="1000"/></a:p></dsp:txBody>'
    )
    story = dml_text_story(tx, THEME)
    assert story is not None and len(story.blocks) == 2
    first = story.blocks[0]
    assert first.p_pr.jc == "right"
    run = first.runs[0]
    assert (run.text, run.r_pr.sz, run.r_pr.b, run.r_pr.color) == ("Hi", 24.0, True, "FF0000")
    assert story.blocks[1].r_pr.sz == 10.0  # empty paragraph keeps its mark size


def test_normalize_percentages() -> None:
    el = ET.fromstring('<x val="60%"><y val="-12.5%" other="7"/></x>')
    normalize_percentages(el)
    assert el.get("val") == "60000"
    assert el[0].get("val") == "-12500" and el[0].get("other") == "7"


def _data_model(texts: list[str]) -> ET.Element:
    pts = '<dgm:pt modelId="0" type="doc"/>' + "".join(
        f'<dgm:pt modelId="{i + 1}"><dgm:t><a:p><a:r><a:t>{t}</a:t></a:r></a:p></dgm:t></dgm:pt>'
        for i, t in enumerate(texts)
    )
    cxns = "".join(
        f'<dgm:cxn modelId="c{i}" srcId="0" destId="{i + 1}" srcOrd="{i}"/>'
        for i in range(len(texts))
    )
    return ET.fromstring(
        f'<dgm:dataModel xmlns:dgm="{DGM}" xmlns:a="{A}"><dgm:ptLst>{pts}</dgm:ptLst>'
        f"<dgm:cxnLst>{cxns}</dgm:cxnLst></dgm:dataModel>"
    )


@pytest.mark.parametrize(
    ("layout", "boxes", "arrows"),
    [
        ("urn:microsoft.com/office/officeart/2005/8/layout/process1", 3, 2),
        ("urn:microsoft.com/office/officeart/2005/8/layout/cycle2", 3, 0),
        ("urn:microsoft.com/office/officeart/2005/8/layout/hierarchy1", 3, 0),
        ("urn:microsoft.com/office/officeart/2005/8/layout/vList2", 3, 0),
    ],
)
def test_smartart_without_drawing_is_laid_out_from_data(layout, boxes, arrows) -> None:
    group = smartart_from_data(_data_model(["A", "B", "C"]), layout, 300.0, 120.0, THEME)
    assert group is not None
    kinds = [c.item.geometry for c in group.children]
    assert kinds.count("rightArrow") == arrows
    assert len(kinds) - arrows == boxes
    for c in group.children:  # every box stays inside the frame
        assert c.x >= -0.01 and c.y >= -0.01
        assert c.x + c.item.width <= 300.01 and c.y + c.item.height <= 120.01
    texts = [plain_text(c.item.story.blocks[0]) for c in group.children if c.item.story]
    assert texts == ["A", "B", "C"]


def test_smartart_data_without_nodes_returns_none() -> None:
    assert smartart_from_data(_data_model([]), "", 100.0, 100.0, THEME) is None


# --------------------------------------------------------------------------- layout & paint


def test_strict_page_order_and_no_overlap(qapp) -> None:
    canvas = WriterCanvasView(doc=read_docx(STRICT))
    rects = _body_rects(canvas)
    order = [
        "header",
        "Hello world!",
        "picture",
        "chart",
        "This is a chart:",
        "And this is a smart-art:",
        "diagram",
    ]
    for name in order:
        assert name in rects, name
    tops = [rects[n].top() for n in order]
    assert tops == sorted(tops), dict(zip(order, tops))
    for a, b in combinations(order, 2):
        inter = rects[a].intersected(rects[b])
        assert inter.width() < 0.5 or inter.height() < 0.5, (a, b)


def _blue_runs(img: QImage, y: int, x0: int, x1: int) -> int:
    runs, inside = 0, False
    for x in range(x0, x1):
        c = QColor(img.pixel(x, y))
        blue = c.blue() > c.red() + 40 and c.blue() > 120
        if blue and not inside:
            runs += 1
        inside = blue
    return runs


def test_chart_paints_three_bars_and_diagram_a_filled_circle(qapp) -> None:
    canvas = WriterCanvasView(doc=read_docx(STRICT))
    rects = _body_rects(canvas)
    img = _render(canvas)

    chart = rects["chart"]
    y = int(chart.bottom() - chart.height() * 0.2)
    assert _blue_runs(img, y, int(chart.left()), int(chart.right())) == 3

    page = canvas.pagination.pages[0]
    diagram_rect = rects["diagram"]
    diagram = next(
        r
        for b in canvas.doc.main.blocks
        if isinstance(b, Paragraph)
        for r in b.runs
        if isinstance(r, ShapeItem)
    )
    circle = next(c for c in diagram.children if c.item.geometry == "ellipse")
    cx = diagram_rect.left() + circle.x + circle.item.width * 0.2
    cy = diagram_rect.top() + circle.y + circle.item.height * 0.5
    fill = QColor(img.pixel(int(cx), int(cy))).name().upper()
    assert fill == circle.item.fill.color.upper()
    # an ellipse, not its bounding box: the box corner stays white
    corner = QColor(
        img.pixel(int(diagram_rect.left() + circle.x + 3), int(diagram_rect.top() + circle.y + 3))
    )
    assert corner.name().upper() == "#FFFFFF"
    assert page.width > 0

    screen = _render_screen(canvas)
    sy = int(canvas.pt_to_px(y))
    assert (
        _blue_runs(
            screen, sy, int(canvas.pt_to_px(chart.left())), int(canvas.pt_to_px(chart.right()))
        )
        == 3
    )


def test_smartart_boxes_paint_outlines_not_placeholder(qapp, monkeypatch) -> None:
    canvas = WriterCanvasView(doc=read_docx(SMARTART_BOXES))
    resolved: list[object] = []
    real = canvas._resolve_pixmap
    monkeypatch.setattr(canvas, "_resolve_pixmap", lambda pic: resolved.append(pic) or real(pic))
    page = canvas.pagination.pages[0]
    (fb,) = [fb for fb in page.float_boxes if isinstance(fb.item, ShapeItem)]
    img = _render(canvas)
    assert not resolved  # the placeholder path (no pixmap) is never taken

    outlined = 0
    for ch in fb.item.children:
        x0, y0 = fb.x + ch.x, fb.y + ch.y
        w, h = ch.item.width, ch.item.height
        edge = QColor(img.pixel(int(x0 + w / 2), int(y0 + 1)))
        center = QColor(img.pixel(int(x0 + w / 2), int(y0 + h / 2)))
        if edge.name().upper() != "#FFFFFF" and center.name().upper() == "#FFFFFF":
            outlined += 1
    assert outlined == 3


def test_picture_items_still_render_as_pictures() -> None:
    doc = read_docx(STRICT)
    first = doc.main.blocks[0].runs[0]
    assert type(first) is PictureItem and first.image_part.endswith("image1.gif")


@pytest.mark.parametrize("path", [STRICT, SMARTART_BOXES])
def test_charts_and_diagrams_survive_docx_round_trip(path: Path) -> None:
    from atboffice.modules.writer.io.docx_writer import write_docx

    def kinds(doc) -> list[str]:
        return [
            type(r).__name__
            for b in doc.main.blocks
            if isinstance(b, Paragraph)
            for r in b.runs
            if isinstance(r, PictureItem)
        ]

    doc = read_docx(path)
    assert kinds(read_docx(write_docx(doc))) == kinds(doc)


def test_dml_text_line_break_and_empty_body() -> None:
    from atboffice.modules.writer.models.document import BreakItem

    tx = ET.fromstring(
        f'<dsp:txBody xmlns:dsp="urn:dsp" xmlns:a="{A}"><a:p><a:r><a:t>a</a:t></a:r><a:br/>'
        "<a:r><a:t>b</a:t></a:r></a:p></dsp:txBody>"
    )
    story = dml_text_story(tx, THEME)
    assert [type(r).__name__ for r in story.blocks[0].runs] == ["TextItem", "BreakItem", "TextItem"]
    assert isinstance(story.blocks[0].runs[1], BreakItem)
    assert dml_text_story(ET.fromstring(f'<x xmlns:a="{A}"/>'), THEME) is None
    assert dml_text_story(None, THEME) is None
