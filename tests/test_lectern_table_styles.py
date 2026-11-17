"""Tests for PowerPoint table styles (tableStyles.xml) in Lectern (issue #370)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.presentation.io.pptx_reader import read_pptx
from atboffice.modules.presentation.io.pptx_writer import write_pptx

FIXTURES = Path(__file__).parent / "docs" / "powerpoint" / "pptx"
POI = FIXTURES / "poi__table-with-different-font-colors.pptx"
LIBRE = FIXTURES / "libreoffice__connector-shape-animations.pptx"

MEDIUM2_ACCENT1 = "{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"


def _tables(pres):
    return [sh for s in pres.slides for sh in s.shapes if sh.type == "table" and sh.tbl]


def _cell(tbl, r, c):
    return tbl["rows"][r]["cells"][c]


def _run(cell):
    return cell["tx"].paragraphs[0].runs[0]


def _hex(fill):
    assert fill and fill.get("t") == "solid", fill
    return str(fill["c"]).upper()


def _luma(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


@pytest.fixture(scope="module")
def poi():
    return read_pptx(POI)


# ---------------------------------------------------------------- reader: poi fixture


def test_style_id_and_flags_are_kept(poi):
    t1, t2 = (sh.tbl for sh in _tables(poi))
    assert t1["style_id"] == MEDIUM2_ACCENT1
    assert t1["firstRow"] and t1["bandRow"] and t1["lastRow"]
    assert not t1.get("firstCol")
    assert t2["firstCol"] and t2["lastCol"] and t2["bandCol"]


def test_first_row_dark_fill_and_bold_yellow_text(poi):
    tbl = _tables(poi)[0].tbl
    head = _cell(tbl, 0, 0)
    body = _cell(tbl, 1, 0)
    # firstRow fill is plain accent1 (dark), body cells are tinted (light)
    assert _luma(_hex(head["fill"])) < _luma(_hex(body["fill"]))
    assert _luma(_hex(head["fill"])) < 160
    run = _run(head)
    assert run.color.upper() == "#FFFF00"
    assert run.bold is True


def test_text_colors_follow_style_parts(poi):
    tbl = _tables(poi)[0].tbl
    assert _run(_cell(tbl, 1, 0)).color.upper() == "#777777"  # band1H -> wholeTbl gray
    assert _run(_cell(tbl, 2, 0)).color.upper() == "#00FFFF"  # band2H cyan
    last = _run(_cell(tbl, 3, 0))
    assert last.color.upper() == "#0000FF" and last.bold  # lastRow blue bold


def test_run_level_colors_override_style(poi):
    tbl = _tables(poi)[0].tbl
    t3 = _run(_cell(tbl, 0, 2))
    assert t3.color.upper() == "#00B050"  # explicit green wins over firstRow yellow
    t11 = _run(_cell(tbl, 2, 2))
    assert t11.color.upper() == "#FF0000" and t11.italic


def test_band_rows_alternate_fill(poi):
    tbl = _tables(poi)[0].tbl
    band1 = _hex(_cell(tbl, 1, 1)["fill"])  # band1H tint 40%
    band2 = _hex(_cell(tbl, 2, 1)["fill"])  # band2H has no fill -> wholeTbl tint 20%
    assert band1 != band2
    assert _luma(band2) > _luma(band1)


def test_column_flags_on_second_table(poi):
    tbl = _tables(poi)[1].tbl
    first = _run(_cell(tbl, 0, 0))
    assert first.color.upper() == "#00FF00" and first.bold
    last = _run(_cell(tbl, 0, 3))
    assert last.color.upper() == "#FF0000" and last.bold
    assert _run(_cell(tbl, 0, 1)).color.upper() == "#777777"  # band1V -> wholeTbl text
    assert _run(_cell(tbl, 0, 2)).color.upper() == "#00FFFF"  # band2V cyan


def test_style_borders_present(poi):
    tbl = _tables(poi)[0].tbl
    bd = _cell(tbl, 1, 1)["bd"]
    assert set(bd) >= {"l", "r", "t", "b"}
    assert bd["l"]["w"] == pytest.approx(1.0)


# ---------------------------------------------------------------- reader: libreoffice fixture


def test_libreoffice_cell_fills_are_light_gray():
    pres = read_pptx(LIBRE)
    tables = _tables(pres)
    assert tables
    tbl = tables[0].tbl
    fill = _cell(tbl, 0, 0)["fill"]
    assert fill["t"] == "solid"
    color = str(fill["c"])
    # bg2 (scheme token or resolved hex) is a light gray
    assert color == "bg2" or color.lower() in ("lt2",) or _luma(color) > 180
    assert _cell(tbl, 0, 0)["own"]["fill"] is True
    assert "l" in _cell(tbl, 0, 0)["bd"]


# ---------------------------------------------------------------- synthetic packages


def _patch_pptx(src: Path, edits: dict[str, callable]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename in edits:
                data = edits[item.filename](data)
            zout.writestr(item, data)
    return out.getvalue()


def test_unknown_style_id_falls_back_to_default():
    data = _patch_pptx(
        POI,
        {
            "ppt/slides/slide1.xml": lambda b: b.replace(
                MEDIUM2_ACCENT1.encode(), b"{00000000-DEAD-BEEF-0000-000000000000}"
            )
        },
    )
    pres = read_pptx(io.BytesIO(data))
    tbl = _tables(pres)[0].tbl
    assert tbl["style_id"] == "{00000000-DEAD-BEEF-0000-000000000000}"
    run = _run(_cell(tbl, 0, 0))
    assert run.color.upper() == "#FFFF00" and run.bold  # def style from tableStyles.xml


def test_missing_table_styles_part_uses_builtin():
    out = io.BytesIO()
    with zipfile.ZipFile(POI) as zin, zipfile.ZipFile(out, "w") as zout:
        for item in zin.infolist():
            if item.filename == "ppt/tableStyles.xml":
                continue
            zout.writestr(item, zin.read(item.filename))
    pres = read_pptx(io.BytesIO(out.getvalue()))
    tbl = _tables(pres)[0].tbl
    head = _cell(tbl, 0, 0)
    assert head["fill"]["t"] == "solid"
    run = _run(head)
    assert run.bold
    assert run.color is not None


def test_merged_cells_carry_span_flags():
    def merge(b: bytes) -> bytes:
        s = b.decode("utf-8")
        first_tc = s.index("<a:tc>")
        s = s[:first_tc] + '<a:tc gridSpan="2">' + s[first_tc + len("<a:tc>") :]
        second_tc = s.index("<a:tc>", first_tc + 10)
        s = s[:second_tc] + '<a:tc hMerge="1">' + s[second_tc + len("<a:tc>") :]
        return s.encode("utf-8")

    data = _patch_pptx(POI, {"ppt/slides/slide1.xml": merge})
    pres = read_pptx(io.BytesIO(data))
    tbl = _tables(pres)[0].tbl
    assert _cell(tbl, 0, 0)["gs"] == 2
    assert _cell(tbl, 0, 1)["hm"] is True


# ---------------------------------------------------------------- round trip


def _mark_dirty(pres) -> None:
    """Force re-serialization so the table writer itself is exercised."""
    for slide in pres.slides:
        slide.is_dirty = True


def test_round_trip_keeps_style_id_flags_and_style_part(tmp_path):
    poi = read_pptx(POI)
    _mark_dirty(poi)
    out = tmp_path / "rt.pptx"
    write_pptx(poi, out)
    with zipfile.ZipFile(out) as z:
        slide = z.read("ppt/slides/slide1.xml").decode("utf-8")
        styles = z.read("ppt/tableStyles.xml").decode("utf-8")
    assert MEDIUM2_ACCENT1 in slide
    assert 'firstRow="1"' in slide and 'lastRow="1"' in slide and 'bandRow="1"' in slide
    assert "FFFF00" in styles  # custom firstRow text color survives

    again = read_pptx(out)
    tbl = _tables(again)[0].tbl
    assert tbl["style_id"] == MEDIUM2_ACCENT1
    run = _run(_cell(tbl, 0, 0))
    assert run.color.upper() == "#FFFF00" and run.bold
    # style fills are not baked into tcPr
    assert _cell(tbl, 1, 1)["own"]["fill"] is False


def test_round_trip_keeps_own_cell_fill_and_merges(tmp_path):
    pres = read_pptx(LIBRE)
    tbl = _tables(pres)[0].tbl
    tbl["rows"][0]["cells"][0]["gs"] = 2
    tbl["rows"][0]["cells"][1]["hm"] = True
    _mark_dirty(pres)
    out = tmp_path / "rt2.pptx"
    write_pptx(pres, out)
    again = read_pptx(out)
    t2 = _tables(again)[0].tbl
    c0 = _cell(t2, 0, 0)
    assert c0["own"]["fill"] is True and c0["fill"]["t"] == "solid"
    assert c0["gs"] == 2
    assert _cell(t2, 0, 1)["hm"] is True


# ---------------------------------------------------------------- rendering


def _render_table(shape):
    from PySide6.QtGui import QImage, QPainter

    from atboffice.modules.presentation.views.shape_item import ShapeGraphicsItem

    item = ShapeGraphicsItem(shape)
    img = QImage(int(shape.w) + 2, int(shape.h) + 2, QImage.Format.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    item._paint_table(painter, shape.w, shape.h)
    painter.end()
    return img


def test_paint_table_merged_origin_spans_and_continuation_is_skipped(qtbot):
    shape = _tables(read_pptx(POI))[0]
    tbl = shape.tbl
    origin = tbl["rows"][1]["cells"][0]
    cont = tbl["rows"][1]["cells"][1]
    origin.update(gs=2, fill={"t": "solid", "c": "#000000", "a": 1.0})
    cont.update(hm=True, fill={"t": "solid", "c": "#FFFFFF", "a": 1.0})
    img = _render_table(shape)
    sx = shape.w / sum(tbl["cols"])
    y = int(tbl["rows"][0]["h"] + tbl["rows"][1]["h"] / 2)
    px = img.pixelColor(int(tbl["cols"][0] * sx * 1.5), y)
    assert px.name().upper() == "#000000"


def test_paint_table_vertical_merge(qtbot):
    shape = _tables(read_pptx(POI))[0]
    tbl = shape.tbl
    tbl["rows"][1]["cells"][3].update(rs=2, fill={"t": "solid", "c": "#000000", "a": 1.0})
    tbl["rows"][2]["cells"][3].update(vm=True, fill={"t": "solid", "c": "#FFFFFF", "a": 1.0})
    img = _render_table(shape)
    sx = shape.w / sum(tbl["cols"])
    x = int((sum(tbl["cols"][:3]) + tbl["cols"][3] / 2) * sx)
    y = int(sum(r["h"] for r in tbl["rows"][:2]) + tbl["rows"][2]["h"] / 2)
    assert img.pixelColor(x, y).name().upper() == "#000000"


def test_paint_table_draws_style_fill(qtbot):
    shape = _tables(read_pptx(POI))[0]
    img = _render_table(shape)
    sx = shape.w / sum(shape.tbl["cols"])
    px = img.pixelColor(int(shape.tbl["cols"][0] * sx) - 4, int(shape.tbl["rows"][0]["h"] / 2))
    assert px.alpha() > 0 and _luma(px.name()) < 160


def test_paint_table_fill_does_not_cover_neighbour_border(qtbot):
    shape = _tables(read_pptx(POI))[0]
    tbl = shape.tbl
    for row in tbl["rows"]:
        for cell in row["cells"]:
            cell["fill"] = {"t": "solid", "c": "#000000", "a": 1.0}
            cell["bd"] = {"r": {"c": "#FF0000", "w": 4.0, "dash": "solid"}}
            cell["tx"] = None
            cell["text"] = ""
    img = _render_table(shape)
    sx = shape.w / sum(tbl["cols"])
    edge = int(tbl["cols"][0] * sx)
    y = int(tbl["rows"][1]["h"] / 2 + tbl["rows"][0]["h"])
    # the right half of cell(0)'s border lies inside cell(1) and must survive its fill
    assert img.pixelColor(edge + 1, y).name().upper() == "#FF0000"
