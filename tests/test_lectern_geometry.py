"""Tests for Lectern shape geometry, flips, picture crop and connector handles.

Covers Issue #371:
- Custom geometry path coordinates scale from the path's (w, h) space to the shape box.
- arcTo derives the ellipse centre from the current point (DrawingML semantics).
- flipH / flipV are parsed, mirror geometry, compose with groups, and round-trip.
- tdf164622.pptx: the cropped (srcRect) picture fills its xfrm extent.
- connector-shape-animations.pptx: the flipV connector ascends left-to-right and
  opening the deck does not select a shape (so no handles are painted).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.io.pptx_reader import PptxReader, read_pptx
from atboffice.modules.presentation.io.writer_shapes import _src_rect_xml
from atboffice.modules.presentation.io.xml_utils import transform_to_xml
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.views.geometry_helper import (
    connector_local_endpoints,
    create_shape_path,
    flip_transform,
)

CORPUS_DIR = Path("tests/docs/powerpoint/pptx")
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
EMU = 12700


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _reader() -> PptxReader:
    return PptxReader.__new__(PptxReader)


def _xml(fragment: str) -> ET.Element:
    return ET.fromstring(f'<root xmlns:a="{A_NS}" xmlns:p="{P_NS}">{fragment}</root>')[0]


# --------------------------------------------------------------------------
# Custom geometry
# --------------------------------------------------------------------------


def test_custom_path_scales_from_path_space_to_shape_box():
    """A path with w=100 h=50 on a 200x100 shape scales x2 in both axes."""
    custom = {
        "paths": [
            {
                "w": 100.0,
                "h": 50.0,
                "cmds": [["M", 0.0, 0.0], ["L", 100.0, 0.0], ["L", 100.0, 50.0], ["Z"]],
            }
        ]
    }
    path = create_shape_path("custom", 200.0, 100.0, None, custom)
    pts = [(path.elementAt(i).x, path.elementAt(i).y) for i in range(3)]
    assert pts == [(0.0, 0.0), (200.0, 0.0), (200.0, 100.0)]
    assert path.boundingRect() == QRectF(0.0, 0.0, 200.0, 100.0)


def test_parsed_custom_geometry_fills_xfrm_extent():
    """Parsed custGeom with its own path space paints exactly the shape extent."""
    sp_pr = _xml(
        "<p:spPr><a:xfrm><a:off x='0' y='0'/><a:ext cx='2540000' cy='1270000'/></a:xfrm>"
        "<a:custGeom><a:pathLst><a:path w='1000' h='500'>"
        "<a:moveTo><a:pt x='0' y='0'/></a:moveTo><a:lnTo><a:pt x='1000' y='0'/></a:lnTo>"
        "<a:lnTo><a:pt x='1000' y='500'/></a:lnTo><a:lnTo><a:pt x='0' y='500'/></a:lnTo>"
        "<a:close/></a:path><a:path w='100' h='100'>"
        "<a:moveTo><a:pt x='50' y='0'/></a:moveTo><a:lnTo><a:pt x='50' y='100'/></a:lnTo>"
        "</a:path></a:pathLst></a:custGeom></p:spPr>"
    )
    geom, custom = _reader()._parse_geometry(sp_pr)
    assert geom == "custom" and custom is not None
    w, h = 2540000 / EMU, 1270000 / EMU
    rect = create_shape_path(geom, w, h, None, custom).boundingRect()
    assert abs(rect.width() - w) <= 2.0 and abs(rect.height() - h) <= 2.0
    # The second path (different w/h space) lands on the box's vertical centre line.
    second = create_shape_path(geom, w, h, None, {"paths": custom["paths"][1:]})
    assert abs(second.elementAt(0).x - w / 2.0) < 0.01
    assert abs(second.elementAt(1).y - h) < 0.01


def test_arc_to_starts_at_current_point():
    """arcTo continues from the current point: a quarter arc from the top of a circle."""
    custom = {
        "paths": [
            {
                "w": 100.0,
                "h": 100.0,
                # Start at the circle's top (stAng 270° = -90°, y-down), sweep 90° clockwise.
                "cmds": [["M", 50.0, 0.0], ["A", 50.0, 50.0, 270.0, 90.0]],
            }
        ]
    }
    path = create_shape_path("custom", 100.0, 100.0, None, custom)
    start = path.pointAtPercent(0.0)
    end = path.pointAtPercent(1.0)
    assert abs(start.x() - 50.0) < 0.01 and abs(start.y()) < 0.01
    # Clockwise from the top of a circle centred at (50, 50) ends at its right edge.
    assert abs(end.x() - 100.0) < 0.01 and abs(end.y() - 50.0) < 0.01


# --------------------------------------------------------------------------
# Flips
# --------------------------------------------------------------------------


def test_flip_v_mirrors_path_across_horizontal_axis():
    """flipV with no rotation mirrors the path across the horizontal centre line."""
    base = create_shape_path("rtTriangle", 100.0, 50.0)
    flipped = flip_transform(100.0, 50.0, False, True).map(base)
    for i in range(base.elementCount()):
        b, f = base.elementAt(i), flipped.elementAt(i)
        assert abs(f.x - b.x) < 1e-6
        assert abs(f.y - (50.0 - b.y)) < 1e-6
    assert flipped.boundingRect() == base.boundingRect()


def test_flip_h_mirrors_path_across_vertical_axis():
    base = create_shape_path("rtTriangle", 100.0, 50.0)
    flipped = flip_transform(100.0, 50.0, True, False).map(base)
    for i in range(base.elementCount()):
        b, f = base.elementAt(i), flipped.elementAt(i)
        assert abs(f.x - (100.0 - b.x)) < 1e-6 and abs(f.y - b.y) < 1e-6


def test_connector_local_endpoints_follow_flips():
    assert connector_local_endpoints(10.0, 4.0) == ((0.0, 0.0), (10.0, 4.0))
    assert connector_local_endpoints(10.0, 4.0, flip_v=True) == ((0.0, 4.0), (10.0, 0.0))
    assert connector_local_endpoints(10.0, 4.0, flip_h=True) == ((10.0, 0.0), (0.0, 4.0))


def test_flip_parsed_from_xfrm_and_round_trips():
    sp_pr = _xml("<p:spPr><a:xfrm flipH='1' flipV='true'/></p:spPr>")
    assert PptxReader._parse_flip(sp_pr) == (True, True)
    assert PptxReader._parse_flip(_xml("<p:spPr><a:xfrm/></p:spPr>")) == (False, False)
    assert PptxReader._parse_flip(None) == (False, False)

    sh = Shape(id="1", flip_v=True)
    assert 'flipV="1"' in transform_to_xml(sh) and "flipH" not in transform_to_xml(sh)
    restored = Shape.from_dict(sh.to_dict())
    assert restored.flip_v is True and restored.flip_h is False


def test_flipped_group_mirrors_children():
    """A flipH group reflects child positions and toggles their flips."""
    grp = _xml(
        "<p:grpSp><p:nvGrpSpPr><p:cNvPr id='9' name='G'/></p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm flipH='1'><a:off x='0' y='0'/><a:ext cx='1270000' cy='1270000'/>"
        "<a:chOff x='0' y='0'/><a:chExt cx='1270000' cy='1270000'/></a:xfrm></p:grpSpPr>"
        "<p:cxnSp><p:nvCxnSpPr><p:cNvPr id='10' name='C'/></p:nvCxnSpPr>"
        "<p:spPr><a:xfrm rot='600000'><a:off x='0' y='0'/><a:ext cx='254000' cy='127000'/>"
        "</a:xfrm><a:prstGeom prst='line'/></p:spPr></p:cxnSp></p:grpSp>"
    )
    reader = _reader()
    reader._resolve_theme_context = lambda *a, **k: ({}, None, {}, None)  # type: ignore[method-assign]
    reader._parse_fill = lambda *a, **k: type("F", (), {"type": "none"})()  # type: ignore[method-assign]
    kid = Shape(id="10", type="line", geom="line", w=20.0, h=10.0, rot=10.0)
    reader._parse_shape = lambda *a, **k: kid  # type: ignore[method-assign]
    group = reader._parse_group_element(grp, "ppt/slides/slide1.xml", {})
    assert group.kids == [kid], "cxnSp children of a group must be parsed"
    assert kid.x == 80.0 and kid.y == 0.0
    assert kid.flip_h is True and kid.flip_v is False
    assert kid.rot == 350.0


# --------------------------------------------------------------------------
# Picture crop (srcRect)
# --------------------------------------------------------------------------


def test_src_rect_parsed_and_serialized():
    bf = _xml("<p:blipFill><a:blip/><a:srcRect b='41860'/><a:stretch/></p:blipFill>")
    crop = PptxReader._parse_src_rect(bf)
    assert crop == {"l": 0.0, "t": 0.0, "r": 0.0, "b": 0.4186}
    assert _src_rect_xml(Shape(id="1", type="image", crop=crop)) == '<a:srcRect b="41860"/>'
    assert PptxReader._parse_src_rect(_xml("<p:blipFill><a:srcRect/></p:blipFill>")) is None
    degenerate = _xml("<p:blipFill><a:srcRect l='60000' r='50000'/></p:blipFill>")
    assert PptxReader._parse_src_rect(degenerate) is None
    assert _src_rect_xml(Shape(id="1", type="image", crop=True)) == ""  # type: ignore[arg-type]


def _render_scene(qapp, pres, slide) -> QImage:
    from atboffice.modules.presentation.views.slide_canvas import SlideScene

    scene = SlideScene(slide, pres.w, pres.h, presentation=pres)
    img = QImage(int(pres.w), int(pres.h), QImage.Format.Format_ARGB32)
    img.fill(QColor("white"))
    painter = QPainter(img)
    scene.render(painter, QRectF(0, 0, pres.w, pres.h), QRectF(0, 0, pres.w, pres.h))
    painter.end()
    return img


def _ink_bbox(img: QImage, rect: QRectF, is_ink) -> tuple[int, int, int, int] | None:
    xs, ys = [], []
    for y in range(int(rect.top()), int(rect.bottom())):
        for x in range(int(rect.left()), int(rect.right())):
            if is_ink(img.pixelColor(x, y)):
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def test_tdf164622_cropped_picture_fills_extent(qapp):
    """The cropped outline picture's painted box matches its xfrm within 2 px."""
    pres = read_pptx(CORPUS_DIR / "libreoffice__tdf164622.pptx")
    slide = pres.slides[0]
    pic = next(s for s in slide.shapes if s.type == "image")
    assert pic.crop and abs(pic.crop["b"] - 0.4186) < 1e-6

    img = _render_scene(qapp, pres, slide)

    def green(c: QColor) -> bool:
        return c.green() > 120 and c.red() < 150 and c.green() - c.red() > 50

    box = _ink_bbox(img, QRectF(pic.x - 4, pic.y - 4, pic.w + 8, pic.h + 8), green)
    assert box is not None, "outline picture not painted"
    x0, y0, x1, y1 = box
    # The visible outline reaches the frame's left, top and right edges and the
    # bottom of the cropped area (the bottom stroke ends where the crop cuts it).
    assert abs((x1 - x0 + 1) - pic.w) <= 2.0 + pic.w * 0.06
    assert abs((y1 - y0 + 1) - pic.h) <= 2.0 + pic.h * 0.06
    assert (y1 - y0 + 1) > pic.h * 0.9, "picture is squashed; srcRect crop ignored"


# --------------------------------------------------------------------------
# Connector direction & handles
# --------------------------------------------------------------------------


def test_connector_flip_v_ascends_left_to_right(qapp):
    pres = read_pptx(CORPUS_DIR / "libreoffice__connector-shape-animations.pptx")
    slide = pres.slides[0]
    conn = next(s for s in slide.shapes if s.is_connector)
    assert conn.flip_v is True and conn.flip_h is False

    img = _render_scene(qapp, pres, slide)

    def ink(c: QColor) -> bool:
        return c.red() < 245 or c.green() < 245 or c.blue() < 245

    def column_mid_y(x: float) -> float:
        rows = range(int(conn.y) - 3, int(conn.y + conn.h) + 3)
        ys = [y for y in rows if ink(img.pixelColor(int(x), y))]
        assert ys, f"no connector ink at x={x}"
        return sum(ys) / len(ys)

    left = column_mid_y(conn.x + conn.w * 0.1)
    right = column_mid_y(conn.x + conn.w * 0.9)
    assert left > right, f"left end y={left} should be lower than right end y={right}"


def test_open_deck_selects_nothing_and_paints_no_handles(qapp):
    """Opening a deck with animations must not select the first animated shape."""
    from atboffice.modules.presentation.views.shape_item import TransformHandleItem
    from atboffice.modules.presentation.views.workspace import LecternWorkspace

    pres = read_pptx(CORPUS_DIR / "libreoffice__connector-shape-animations.pptx")
    assert pres.slides[0].animations, "fixture must carry animations"
    ws = LecternWorkspace()
    ws.load_presentation(pres)
    qapp.processEvents()
    assert ws.scene.selectedItems() == []
    visible = [
        it for it in ws.scene.items() if isinstance(it, TransformHandleItem) and it.isVisible()
    ]
    assert visible == []
    # The animation list still shows its first entry as current.
    assert ws.animation_pane.list_anims.currentRow() == 0
