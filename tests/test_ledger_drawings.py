"""Ledger drawing objects: groups, preset geometry, fills, anchors and pictures (#374)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from atboffice.drawing.dml import parse_cust_geom, parse_fill, resolve_color, theme_map
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.views.object_layer import (
    AnchorType,
    FloatingObject,
    SpreadsheetObjectLayer,
    object_to_rect,
)
from atboffice.modules.spreadsheet.views.object_painting import child_rect, fit_aspect_rect
from atboffice.vfs import etree as ET

FIXTURES = Path(__file__).parent / "docs" / "excel" / "xlsx"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"




def _xml(body: str) -> ET.Element:
    return ET.fromstring(f'<a:spPr xmlns:a="{A}">{body}</a:spPr>')


def _drawings(name: str):
    wb = read_xlsx(str(FIXTURES / name))
    sheet = wb.sheets[0]
    return sheet, list(sheet.drawings)


def _sheet_rect(obj: FloatingObject, sheet) -> QRect:
    return object_to_rect(obj, sheet.geometry, row_header_width=0, col_header_height=0)


def _cell_rect(sheet, c1: int, r1: int, c2: int, r2: int) -> QRect:
    g = sheet.geometry
    x1, y1 = g.col_pos(c1), g.row_pos(r1)
    return QRect(x1, y1, g.col_pos(c2 + 1) - x1, g.row_pos(r2 + 1) - y1)


def _render(obj: FloatingObject, rect: QRect, size: tuple[int, int]) -> QImage:
    img = QImage(size[0], size[1], QImage.Format.Format_ARGB32)
    img.fill(QColor("white"))
    painter = QPainter(img)
    SpreadsheetObjectLayer()._paint_object(painter, obj, rect)
    painter.end()
    return img


# ---------------------------------------------------------------- dml helpers


def test_scheme_color_with_mods_and_alpha():
    theme = theme_map(None)
    el = _xml(
        '<a:schemeClr val="accent1"><a:shade val="50000"/><a:alpha val="40000"/></a:schemeClr>'
    )[0]
    color, alpha = resolve_color(el, theme)
    assert color != theme["accent1"]
    assert alpha == pytest.approx(0.4)
    # tx1/bg1 aliases map onto dk1/lt1
    assert resolve_color(_xml('<a:schemeClr val="tx1"/>')[0], theme)[0] == theme["dk1"]


def test_sys_and_preset_colors():
    theme = theme_map(None)
    window = _xml('<a:sysClr val="window" lastClr="FEFEFE"/>')[0]
    assert resolve_color(window, theme)[0] == "#FEFEFE"
    assert resolve_color(_xml('<a:sysClr val="windowText"/>')[0], theme)[0] == "#000000"
    assert resolve_color(_xml('<a:prstClr val="red"/>')[0], theme)[0] == "#FF0000"


def test_fill_kinds():
    theme = theme_map(None)
    assert parse_fill(_xml("<a:noFill/>"), theme).kind == "none"
    assert parse_fill(_xml("<a:ln/>"), theme) is None
    grad = parse_fill(
        _xml(
            '<a:gradFill><a:gsLst><a:gs pos="100000"><a:srgbClr val="FF0000"/></a:gs>'
            '<a:gs pos="0"><a:schemeClr val="accent2"/></a:gs></a:gsLst>'
            '<a:lin ang="5400000"/></a:gradFill>'
        ),
        theme,
    )
    assert grad.kind == "gradient"
    assert grad.angle == pytest.approx(90.0)
    assert [s[0] for s in grad.stops] == [0.0, 1.0]
    assert grad.stops[0][1] == theme["accent2"]
    patt = parse_fill(
        _xml('<a:pattFill prst="dkHorz"><a:fgClr><a:srgbClr val="112233"/></a:fgClr></a:pattFill>'),
        theme,
    )
    assert (patt.kind, patt.pattern, patt.color, patt.bg_color) == (
        "pattern",
        "dkHorz",
        "#112233",
        "#FFFFFF",
    )


def test_grp_fill_inherits_group_fill():
    theme = theme_map(None)
    group = parse_fill(_xml('<a:solidFill><a:srgbClr val="00FF00"/></a:solidFill>'), theme)
    assert parse_fill(_xml("<a:grpFill/>"), theme, group).color == "#00FF00"


def test_cust_geom_literal_points_only():
    cust = ET.fromstring(
        f'<a:custGeom xmlns:a="{A}"><a:pathLst>'
        '<a:path w="10" h="10"><a:moveTo><a:pt x="0" y="0"/></a:moveTo>'
        '<a:lnTo><a:pt x="10" y="10"/></a:lnTo><a:close/></a:path>'
        '<a:path w="10" h="10"><a:moveTo><a:pt x="T0" y="T1"/></a:moveTo></a:path>'
        "</a:pathLst></a:custGeom>"
    )
    paths = parse_cust_geom(cust)["paths"]
    assert len(paths) == 1
    assert paths[0]["cmds"] == [["M", 0.0, 0.0], ["L", 10.0, 10.0], ["Z"]]


def test_geometry_helpers():
    assert child_rect(QRect(100, 100, 200, 100), (0.5, 0.5, 0.5, 0.5)) == QRect(200, 150, 100, 50)
    fitted = fit_aspect_rect(QRect(0, 0, 200, 200), 400, 100)
    assert (fitted.width(), fitted.height(), fitted.y()) == (200, 50, 75)


def test_floating_object_dict_roundtrip_keeps_group():
    child = FloatingObject(
        kind="rect",
        geometry="ellipse",
        fill_type="gradient",
        gradient_stops=[(0.0, "#FF0000", 1.0)],
        group_frac=(0.1, 0.2, 0.3, 0.4),
    )
    group = FloatingObject(kind="group", children=[child], anchor_resolved=False)
    back = FloatingObject.from_dict(group.to_dict())
    assert back.kind == "group" and not back.anchor_resolved
    assert back.children[0].geometry == "ellipse"
    assert back.children[0].group_frac == (0.1, 0.2, 0.3, 0.4)
    assert back.children[0].gradient_stops == [(0.0, "#FF0000", 1.0)]


# ---------------------------------------------------------------- fixtures


def test_group_with_child_rectangle_is_painted(qapp):
    sheet, objs = _drawings("openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx")
    assert len(objs) == 1
    group = objs[0]
    assert group.kind == "group"
    assert (group.from_point.col, group.from_point.row) == (2, 1)  # C2
    assert (group.to_point.col, group.to_point.row) == (7, 11)  # H12
    rects = [c for c in group.children if c.geometry == "rect"]
    assert len(rects) == 2
    connector = next(c for c in group.children if c.kind == "line")
    assert connector.geometry == "bentConnector3" and connector.tail_end == "arrow"

    first = rects[0]
    assert first.fill_type == "solid"  # grpFill -> group's accent1
    frame = _sheet_rect(group, sheet)
    assert frame.intersects(_cell_rect(sheet, 2, 1, 7, 11))
    sub = child_rect(frame, first.group_frac)
    assert frame.contains(sub)

    img = _render(group, frame, (frame.right() + 20, frame.bottom() + 20))
    assert img.pixelColor(sub.center()).name().upper() == QColor(first.fill_color).name().upper()


def test_gradient_right_arrow(qapp):
    sheet, objs = _drawings("libreoffice__tdf133595.xlsx")
    arrow = objs[0]
    assert arrow.geometry == "rightArrow"
    assert arrow.fill_type == "gradient"
    assert (arrow.from_point.col, arrow.from_point.row) == (6, 2)  # G3
    assert (arrow.to_point.col, arrow.to_point.row) == (17, 5)  # R6

    frame = _sheet_rect(arrow, sheet)
    assert frame.width() > 4 * frame.height()  # a wide arrow, not a thin line
    img = _render(arrow, frame, (frame.right() + 20, frame.bottom() + 20))
    probe = img.pixelColor(frame.x() + frame.width() // 4, frame.y() + frame.height() * 3 // 10)
    assert probe.red() > 200 and probe.green() > 150 and probe.blue() < 80  # yellow


def test_absolute_picture_not_at_origin(qapp):
    sheet, objs = _drawings("poi__49156.xlsx")
    pic = objs[0]
    assert pic.kind == "image" and pic.anchor_type == AnchorType.ABSOLUTE
    assert pic.fill_type == "none"
    a1_b2 = _cell_rect(sheet, 0, 0, 1, 1)
    for obj in objs:
        assert not _sheet_rect(obj, sheet).intersects(a1_b2)
    frame = _sheet_rect(pic, sheet)
    assert frame.y() >= sheet.geometry.row_pos(136)
    assert frame.y() < sheet.geometry.row_pos(137)
    assert frame.x() >= sheet.geometry.col_pos(9)


def test_undecodable_picture_has_no_shape_fill(qapp):
    _, objs = _drawings("poi__49156.xlsx")  # WMF picture, not decodable by Qt
    img = _render(objs[0], QRect(10, 10, 80, 40), (100, 60))
    centre = img.pixelColor(50, 30)
    assert abs(centre.red() - centre.blue()) < 10  # neutral, not the old #4F81BD box


def test_logo_keeps_aspect_ratio(qapp):
    sheet, objs = _drawings("poi__45540_form_Header.xlsx")
    logo = next(o for o in objs if o.kind == "image")
    assert logo.lock_aspect
    pix = QPixmap()
    assert pix.loadFromData(logo.image_data)
    src_aspect = pix.width() / pix.height()
    frame = _sheet_rect(logo, sheet)
    drawn = fit_aspect_rect(frame, pix.width(), pix.height())
    assert drawn.width() / drawn.height() == pytest.approx(src_aspect, rel=0.02)
    _, _, w, h = logo.abs_rect
    assert (w, h) == (1838325 // 9525, 447675 // 9525)  # xfrm size, not 120x80


def test_custom_geometry_group_children_parse():
    _, objs = _drawings("libreoffice__totalsRowFunction.xlsx")
    groups = [o for o in objs if o.kind == "group"]
    assert groups
    assert any(c.geometry == "custom" and c.custom_path for c in groups[0].children)


def test_write_roundtrip_keeps_group_and_gradient(tmp_path):
    from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx

    for name in (
        "openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx",
        "libreoffice__tdf133595.xlsx",
    ):
        wb = read_xlsx(str(FIXTURES / name))
        before = wb.sheets[0].drawings[0]
        out = tmp_path / name
        out.write_bytes(write_xlsx(wb))
        after = read_xlsx(str(out)).sheets[0].drawings[0]
        assert (after.kind, after.geometry, after.fill_type) == (
            before.kind,
            before.geometry,
            before.fill_type,
        )
        assert len(after.children) == len(before.children)
        for a, b in zip(after.children, before.children):
            assert a.geometry == b.geometry and a.fill_type == b.fill_type
            assert a.group_frac == pytest.approx(b.group_frac, abs=1e-4)
        if before.fill_type == "gradient":
            assert after.gradient_stops == before.gradient_stops
            assert after.gradient_angle == pytest.approx(before.gradient_angle)
            assert after.geometry_adj == before.geometry_adj


def test_format_dialog_new_color_replaces_gradient(qapp):
    from atboffice.modules.spreadsheet.dialogs.format_object_dialog import FormatObjectDialog

    obj = FloatingObject(
        fill_type="gradient",
        fill_color="#FFF200",
        line_visible=False,
        gradient_stops=[(0.0, "#FFF200", 1.0), (1.0, "#FF7A00", 1.0)],
    )
    dlg = FormatObjectDialog(obj)
    dlg._apply_and_accept()  # unchanged colors keep the imported gradient
    assert obj.fill_type == "gradient" and not obj.line_visible

    dlg = FormatObjectDialog(obj)
    dlg._current_fill_color = "#00ff00"
    dlg._current_line_color = "#123456"
    dlg._apply_and_accept()
    assert obj.fill_type == "solid" and obj.fill_color == "#00ff00"
    assert obj.line_visible
