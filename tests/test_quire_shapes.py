"""Quire DrawingML / VML shapes and text boxes render instead of placeholder boxes (#365)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from atboffice.drawing.shape_style import (
    parse_shape_geometry,
    resolve_shape_fill,
    resolve_shape_line,
)
from atboffice.modules.writer.io.docx_reader import read_docx
from atboffice.modules.writer.io.docx_shapes import load_theme_colors, vml_color
from atboffice.modules.writer.models import Paragraph, PictureItem, ShapeItem
from atboffice.modules.writer.models.document import plain_text
from atboffice.modules.writer.views.canvas_view import WriterCanvasView

DOCX_DIR = Path(__file__).parent / "docs" / "word" / "docx"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
THEME = load_theme_colors(None)


def _el(xml: str) -> ET.Element:
    return ET.fromstring(f'<wps:wsp xmlns:a="{A}" xmlns:wps="{WPS}">{xml}</wps:wsp>')


def _shapes(doc) -> list[ShapeItem]:
    out: list[ShapeItem] = []
    for block in doc.main.blocks:
        if isinstance(block, Paragraph):
            out.extend(r for r in block.runs if isinstance(r, ShapeItem))
    return out


def _story_text(shape: ShapeItem) -> str:
    blocks = shape.story.blocks if shape.story else []
    return "\n".join(plain_text(b) for b in blocks if isinstance(b, Paragraph))


def _readable_fixtures() -> list[tuple[Path, object]]:
    docs = []
    for path in sorted(DOCX_DIR.glob("*.docx")):
        try:
            docs.append((path, read_docx(path)))
        except Exception:  # password-protected / corrupt fixtures are out of scope
            continue
    return docs


def _render_vector(canvas: WriterCanvasView, page_index: int = 0) -> QImage:
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


# --------------------------------------------------------------------------- style parsing


def test_geometry_fill_and_line_from_style_refs() -> None:
    wsp = _el(
        '<wps:spPr><a:prstGeom prst="star5"><a:avLst/></a:prstGeom></wps:spPr>'
        '<wps:style><a:lnRef idx="2"><a:schemeClr val="accent1"><a:shade val="50000"/>'
        '</a:schemeClr></a:lnRef><a:fillRef idx="1"><a:schemeClr val="accent1"/></a:fillRef>'
        "</wps:style>"
    )
    sp_pr, style = wsp[0], wsp[1]
    assert parse_shape_geometry(sp_pr)[0] == "star5"
    fill = resolve_shape_fill(sp_pr, style, THEME)
    assert (fill.kind, fill.color) == ("solid", THEME["accent1"])
    line = resolve_shape_line(sp_pr, style, THEME)
    assert line.visible and line.width == 2.0


def test_explicit_no_fill_and_no_line_override_style() -> None:
    wsp = _el(
        '<wps:spPr><a:noFill/><a:ln w="12700"><a:noFill/></a:ln></wps:spPr>'
        '<wps:style><a:lnRef idx="2"><a:schemeClr val="accent1"/></a:lnRef>'
        '<a:fillRef idx="1"><a:schemeClr val="accent1"/></a:fillRef></wps:style>'
    )
    assert resolve_shape_fill(wsp[0], wsp[1], THEME).kind == "none"
    line = resolve_shape_line(wsp[0], wsp[1], THEME)
    assert not line.visible and line.width == pytest.approx(1.0)


def test_missing_style_means_no_fill_and_no_line() -> None:
    assert resolve_shape_fill(None, None, THEME).kind == "none"
    assert not resolve_shape_line(None, None, THEME).visible
    assert parse_shape_geometry(None)[0] == "rect"


def test_vml_color_formats() -> None:
    assert vml_color("#d99594 [1941]") == "#D99594"
    assert vml_color("#abc") == "#AABBCC"
    assert vml_color("red") == "#FF0000"
    assert vml_color("") is None


# --------------------------------------------------------------------------- model


def test_invisible_shape_detection() -> None:
    from atboffice.drawing.dml import DmlFill
    from atboffice.drawing.shape_style import DmlLine

    bare = ShapeItem(fill=DmlFill(kind="none"), line=DmlLine(visible=False))
    assert bare.is_invisible
    assert isinstance(bare, PictureItem) and bare.t == "shape"
    assert not ShapeItem(fill=DmlFill(kind="solid", color="#FF0000"), line=DmlLine()).is_invisible


# --------------------------------------------------------------------------- reader


def test_tdf113183_star_and_triangle_presets() -> None:
    doc = read_docx(DOCX_DIR / "libreoffice__tdf113183.docx")
    shapes = _shapes(doc)
    assert sorted(s.geometry for s in shapes) == ["star5", "triangle"]
    for s in shapes:
        assert s.fill.kind == "solid" and s.fill.color == "#4F81BD"  # theme accent1
        assert s.line.visible
        assert s.raw_xml and "wsp" in s.raw_xml  # verbatim round-trip kept


def test_nested_runs_text_frame_has_text_but_no_fill_or_line() -> None:
    doc = read_docx(DOCX_DIR / "libreoffice__nested-runs.docx")
    (shape,) = _shapes(doc)
    assert shape.fill.kind == "none" and not shape.line.visible
    assert "Test text box" in _story_text(shape)
    assert shape.insets == (0.0, 0.0, 0.0, 0.0)
    assert not shape.is_invisible


def test_poi_60316_group_with_text_box_children() -> None:
    doc = read_docx(DOCX_DIR / "poi__60316.docx")
    (group,) = _shapes(doc)
    assert group.is_group and len(group.children) == 2
    assert _story_text(group.children[0].item).startswith("Allison, Timothy B.")
    # wp14:pctPosHOffset from mc:Choice wins over the mc:Fallback posOffset
    assert group.float_pr.pos_h.rel == "page"
    assert group.float_pr.pos_h.percent == pytest.approx(5.9)
    # child space (1905000 x 8677275 EMU) is mapped into the group extent
    second = group.children[1]
    assert second.x == pytest.approx(0.0)
    assert 0 < second.y < group.height


def test_textframe_borders_vml_rect() -> None:
    doc = read_docx(DOCX_DIR / "libreoffice__textframe-borders.docx")
    (shape,) = _shapes(doc)
    assert shape.geometry == "rect"
    assert shape.fill.color == "#D99594"
    assert shape.line.visible and shape.line.color == "#C0504D"
    assert _story_text(shape) == "aaa"


def test_every_drawingml_shape_becomes_a_shape_item() -> None:
    """No wps/wgp drawing is left as an image-less PictureItem (the placeholder case)."""
    fixtures = _readable_fixtures()
    assert len(fixtures) >= 20
    for path, doc in fixtures:
        for block in doc.main.blocks:
            if not isinstance(block, Paragraph):
                continue
            for run in block.runs:
                if type(run) is PictureItem and not run.image_part and run.raw_xml:
                    raw = run.raw_xml
                    assert "wordprocessingShape" not in raw and "wordprocessingGroup" not in raw, (
                        f"{path.name}: shape left as placeholder picture"
                    )


# --------------------------------------------------------------------------- layout & painting


def test_column_relative_frame_stays_on_page(qapp) -> None:
    doc = read_docx(DOCX_DIR / "libreoffice__textframe-borders.docx")
    canvas = WriterCanvasView(doc=doc)
    page = canvas.pagination.pages[0]
    (fb,) = [fb for fb in page.float_boxes if isinstance(fb.item, ShapeItem)]
    # margin-left:-27pt relative to the column (left margin 70.85pt)
    assert fb.x == pytest.approx(1417 / 20 - 27, abs=0.1)
    assert fb.x >= 0 and fb.x + fb.w <= page.width


def test_star_center_painted_in_theme_accent(qapp) -> None:
    doc = read_docx(DOCX_DIR / "libreoffice__tdf113183.docx")
    canvas = WriterCanvasView(doc=doc)
    page = canvas.pagination.pages[0]
    (fb,) = [fb for fb in page.float_boxes if getattr(fb.item, "geometry", "") == "star5"]
    cx, cy = fb.x + fb.w / 2, fb.y + fb.h / 2

    img = _render_vector(canvas)
    assert QColor(img.pixel(int(cx), int(cy))).name().upper() == "#4F81BD"
    # a star, not a rectangle: the box corner between two points stays white
    corner = QColor(img.pixel(int(fb.x + 4), int(fb.y + 4))).name().upper()
    assert corner == "#FFFFFF"

    img = _render_screen(canvas)
    px = img.pixel(int(canvas.pt_to_px(cx)), int(canvas.pt_to_px(cy)))
    assert QColor(px).name().upper() == "#4F81BD"


def test_textframe_paints_fill_and_text(qapp, monkeypatch) -> None:
    doc = read_docx(DOCX_DIR / "libreoffice__textframe-borders.docx")
    canvas = WriterCanvasView(doc=doc)
    painted: list[str] = []
    real = canvas._paint_line_portions

    def spy(painter, page_rect, line, x, y, check_spell=True):
        painted.append("".join(po.text or "" for po in line.portions))
        return real(painter, page_rect, line, x, y, check_spell=check_spell)

    monkeypatch.setattr(canvas, "_paint_line_portions", spy)
    img = _render_screen(canvas)
    assert any("aaa" in t for t in painted)
    page = canvas.pagination.pages[0]
    (fb,) = [fb for fb in page.float_boxes if isinstance(fb.item, ShapeItem)]
    # a point inside the frame, away from the text, carries the fill color
    x = canvas.pt_to_px(fb.x + fb.w - 20)
    y = canvas.pt_to_px(fb.y + fb.h - 10)
    assert QColor(img.pixel(int(x), int(y))).name().upper() == "#D99594"


def test_poi_60316_sidebar_text_in_left_column(qapp, monkeypatch) -> None:
    doc = read_docx(DOCX_DIR / "poi__60316.docx")
    canvas = WriterCanvasView(doc=doc)
    page = canvas.pagination.pages[0]
    (fb,) = [fb for fb in page.float_boxes if isinstance(fb.item, ShapeItem)]
    assert fb.x == pytest.approx(page.width * 0.059, abs=0.5)
    assert fb.x + fb.w < page.width / 2  # the sidebar is the left column

    positions: list[tuple[str, float]] = []
    real = canvas._paint_line_portions

    def spy(painter, page_rect, line, x, y, check_spell=True):
        text = "".join(po.text or "" for po in line.portions)
        positions.append((text, page_rect.left() + canvas.pt_to_px(x)))
        return real(painter, page_rect, line, x, y, check_spell=check_spell)

    monkeypatch.setattr(canvas, "_paint_line_portions", spy)
    _render_screen(canvas)
    hits = [x for t, x in positions if "Allison" in t]
    assert hits and all(x < canvas.pt_to_px(page.width / 2) for x in hits)


def test_shapes_never_reach_the_placeholder(qapp, monkeypatch) -> None:
    """Rendering every Word fixture never asks for a pixmap for an image-less shape."""
    for path, doc in _readable_fixtures():
        canvas = WriterCanvasView(doc=doc)
        asked: list[str] = []
        real = canvas._resolve_pixmap

        def spy(pic, _asked=asked, _real=real):
            if isinstance(pic, ShapeItem) and not pic.image_part:
                _asked.append(pic.name)
            return _real(pic)

        monkeypatch.setattr(canvas, "_resolve_pixmap", spy)
        for i in range(min(2, len(canvas.pagination.pages))):
            _render_screen(canvas, i)
            _render_vector(canvas, i)
        assert not asked, f"{path.name}: placeholder requested for {asked}"


def test_invisible_shape_paints_nothing(qapp) -> None:
    from atboffice.drawing.dml import DmlFill
    from atboffice.drawing.shape_style import DmlLine
    from atboffice.modules.writer.views.shape_painter import paint_shape

    img = QImage(50, 50, QImage.Format.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    p = QPainter(img)
    shape = ShapeItem(width=40, height=40, fill=DmlFill(kind="none"), line=DmlLine())
    paint_shape(p, shape, QRectF(5, 5, 40, 40), 1.0)
    p.end()
    assert all(
        QColor(img.pixel(x, y)).name() == "#ffffff" for x in range(0, 50, 3) for y in range(0, 50, 3)
    )


def test_shapes_survive_docx_round_trip() -> None:
    import io

    from atboffice.modules.writer.io.docx_writer import write_docx

    for name in ("libreoffice__tdf113183", "poi__60316", "libreoffice__textframe-borders"):
        doc = read_docx(DOCX_DIR / f"{name}.docx")
        buf = io.BytesIO()
        write_docx(doc, buf)
        again = read_docx(io.BytesIO(buf.getvalue()))
        assert [s.geometry for s in _shapes(again)] == [s.geometry for s in _shapes(doc)]
        assert [_story_text(s) for s in _shapes(again)] == [_story_text(s) for s in _shapes(doc)]
