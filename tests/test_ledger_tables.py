"""Issue #361 (TASK-DOC-L02): Excel tables, table styles and table filter buttons."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_tables import parse_table_part
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.color_utils import DEFAULT_THEME_COLORS, apply_tint
from atboffice.modules.spreadsheet.models.conditional_format import CFResult
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
    SheetDataModel,
    Table,
    TableStyleInfo,
)
from atboffice.modules.spreadsheet.models.table_style import (
    BUILTIN_TABLE_STYLE_NAMES,
    builtin_table_style,
    custom_table_style,
    overlay_table_style,
    resolve_table_style,
    table_style_at,
)

CORPUS = Path("tests/docs/excel/xlsx")
XMLMAP = CORPUS / "openxml-sdk__XMLMap.xlsx"
TOTALS_SHOWN = CORPUS / "libreoffice__totalsRowShown.xlsx"
TABLEREFS = CORPUS / "libreoffice__tablerefsnamed.xlsx"
TOTALS_FN = CORPUS / "libreoffice__totalsRowFunction.xlsx"

ACCENT1 = DEFAULT_THEME_COLORS[4]


def _table(style: str = "TableStyleMedium9", totals: int = 0, **kw: bool) -> Table:
    info = TableStyleInfo(name=style, show_row_stripes=True, **kw)
    return Table(
        id=1,
        name="T",
        r1=0,
        c1=0,
        r2=4,
        c2=2,
        totals_row_count=totals,
        style_info=info,
        spec=builtin_table_style(style),
    )


def _sheet_with(table: Table) -> SheetDataModel:
    sh = SheetDataModel("S")
    sh.tables.append(table)
    return sh


# ------------------------------------------------------------------ model


def test_model_table_at_bounds() -> None:
    sh = _sheet_with(_table())
    assert sh.table_at(0, 0) is sh.tables[0]
    assert sh.table_at(4, 2) is sh.tables[0]
    assert sh.table_at(5, 0) is None
    assert sh.table_at(0, 3) is None
    assert SheetDataModel().table_at(0, 0) is None


def test_model_header_and_totals_flags() -> None:
    t = _table(totals=1)
    assert t.has_header and t.has_totals
    t.header_row_count = 0
    assert not t.has_header


# ------------------------------------------------------------- style engine


def test_style_all_builtin_names_resolve() -> None:
    assert len(BUILTIN_TABLE_STYLE_NAMES) == 60
    for name in BUILTIN_TABLE_STYLE_NAMES:
        assert builtin_table_style(name) is not None, name
    assert builtin_table_style("NotAStyle") is None
    assert resolve_table_style(None) is None
    assert resolve_table_style("") is None


def test_style_medium9_header_bands_and_totals() -> None:
    sh = _sheet_with(_table(totals=1))
    head = table_style_at(sh, 0, 0)
    assert head.fill == ACCENT1 and head.font_color == "#FFFFFF" and head.bold
    assert table_style_at(sh, 1, 0).fill == apply_tint(ACCENT1, 0.6)  # first stripe
    assert table_style_at(sh, 2, 0).fill == apply_tint(ACCENT1, 0.8)  # whole-table fill
    total = table_style_at(sh, 4, 1)
    assert total.fill == ACCENT1 and total.bold
    assert total.borders["t"].style == "medium"
    assert table_style_at(sh, 5, 0) is None


def test_style_light8_black_header() -> None:
    sh = _sheet_with(_table("TableStyleLight8"))
    head = table_style_at(sh, 0, 1)
    assert head.fill == "#000000" and head.font_color == "#FFFFFF" and head.bold
    # data rows only carry the outline / stripe borders, no fill
    body = table_style_at(sh, 2, 0)
    assert body.fill is None and "l" in body.borders
    assert table_style_at(sh, 2, 1) is None  # interior second stripe: nothing to paint


def test_style_stripes_off_and_first_last_column() -> None:
    t = _table(show_first_column=True, show_last_column=True)
    t.style_info.show_row_stripes = False
    sh = _sheet_with(t)
    assert table_style_at(sh, 1, 1).fill == apply_tint(ACCENT1, 0.8)
    assert table_style_at(sh, 1, 0).fill == ACCENT1  # Medium 8-14 first column = accent
    assert table_style_at(sh, 1, 2).bold


def test_style_no_header_row_starts_stripes_at_top() -> None:
    t = _table()
    t.header_row_count = 0
    sh = _sheet_with(t)
    assert table_style_at(sh, 0, 0).fill == apply_tint(ACCENT1, 0.6)


def test_style_theme_colors_drive_accent() -> None:
    theme = list(DEFAULT_THEME_COLORS)
    theme[4] = "#123456"
    assert builtin_table_style("TableStyleMedium9", theme).header.fill == "#123456"


def test_style_custom_ignores_none_pattern_fill() -> None:
    styles = [
        {
            "name": "Mine",
            "elements": [
                {"type": "wholeTable", "dxf_id": 0},
                {"type": "headerRow", "dxf_id": 1},
                {"type": "bogus", "dxf_id": 1},
                {"type": "totalRow", "dxf_id": 99},
            ],
        }
    ]
    dxfs = [
        {"bg_color": "#000000", "pattern_type": "none", "fg_color": "#111111"},
        {"bg_color": "#ABCDEF", "bold": True},
    ]
    spec = custom_table_style("Mine", styles, dxfs)
    assert spec.whole.fill is None and spec.whole.font_color == "#111111"
    assert spec.header.fill == "#ABCDEF" and spec.header.bold
    assert spec.total is None
    assert custom_table_style("Other", styles, dxfs) is None
    # custom styles shadow built-ins of the same name
    styles[0]["name"] = "TableStyleMedium9"
    assert resolve_table_style("TableStyleMedium9", None, styles, dxfs).header.fill == "#ABCDEF"


def test_overlay_precedence() -> None:
    ts = table_style_at(_sheet_with(_table()), 0, 0)
    plain = overlay_table_style(None, ts, None)
    assert plain.bg_color == ACCENT1 and plain.fg_color == "#FFFFFF" and plain.bold
    own = overlay_table_style(None, ts, CellData(value="x", bg_color="#FF0000", fg_color="#00FF00"))
    assert own.bg_color is None and own.fg_color is None  # direct cell format wins
    cf = CFResult(bg_color="#0000FF")
    merged = overlay_table_style(cf, ts, None)
    assert merged.bg_color == "#0000FF" and cf.fg_color is None  # CF wins, input untouched
    assert overlay_table_style(cf, None, None) is cf
    # a colour equal to the workbook default font is not a deliberate override
    dflt = CellData(value="x", fg_color="#000000")
    assert overlay_table_style(None, ts, dflt, "#000000").fg_color == "#FFFFFF"
    assert overlay_table_style(None, ts, dflt, None).fg_color is None


# ------------------------------------------------------------------ reader


def test_read_table_part_rejects_bad_input() -> None:
    assert parse_table_part(b"<table", "p", 1) is None
    assert parse_table_part(b'<table xmlns="x" ref="nope"/>', "p", 1) is None
    t = parse_table_part(b'<table xmlns="x" id="3" ref="B2:C3"/>', "p", 1)
    assert (t.id, t.name, t.r1, t.c1, t.r2, t.c2) == (3, "Table1", 1, 1, 2, 2)
    assert t.style_info is None and t.spec is None and t.has_header


def test_read_xmlmap_table() -> None:
    sh = read_xlsx(XMLMAP)[0]
    assert len(sh.tables) == 1
    t = sh.tables[0]
    assert t.ref == "C6:E8" and (t.r1, t.c1, t.r2, t.c2) == (5, 2, 7, 4)
    assert t.style_info.name == "TableStyleMedium9"
    assert t.has_auto_filter and [c.name for c in t.columns] == ["Column1", "Column2", "Column3"]
    assert table_style_at(sh, 5, 2).fill == ACCENT1
    assert table_style_at(sh, 6, 2).fill != table_style_at(sh, 7, 2).fill


def test_read_totals_row_shown() -> None:
    wb = read_xlsx(TOTALS_SHOWN)
    t = next(t for s in wb.sheets for t in s.tables)
    assert t.ref == "B2:D5" and t.totals_row_count == 1 and t.has_totals
    sh = next(s for s in wb.sheets if s.tables)
    total = table_style_at(sh, 4, 1)
    assert total.fill == ACCENT1 and total.bold


def test_read_tablerefsnamed_light8() -> None:
    sh = read_xlsx(TABLEREFS)[0]
    t = sh.tables[0]
    assert t.style_info.name == "TableStyleLight8" and t.has_auto_filter
    for c in (0, 1):
        assert table_style_at(sh, 0, c).fill == "#000000"


def test_read_custom_table_style() -> None:
    wb = read_xlsx(TOTALS_FN)
    assert any(s["name"] == "Present planner table" for s in wb.extra["table_styles"])
    sh = next(s for s in wb.sheets if s.tables)
    t = sh.tables[0]
    assert t.style_info.name == "Present planner table" and t.spec is not None
    assert t.columns[4].totals_row_function == "sum"
    assert t.columns[0].totals_row_label == "Total"
    assert table_style_at(sh, t.r1, t.c1).fill is not None  # custom header fill


def test_read_sheet_without_tables_has_empty_list() -> None:
    wb = read_xlsx(CORPUS / "libreoffice__tablerefsnamed.xlsx")
    for sh in wb.sheets[1:]:
        assert sh.tables == []


# ---------------------------------------------------------------- rendering


def _grab(sheet: SheetDataModel, qtbot, w: int = 900, h: int = 500):
    from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport

    vp = GridViewport(model=sheet)
    qtbot.addWidget(vp)
    vp.resize(w, h)
    return vp, vp.grab().toImage()


def _center(vp, r: int, c: int):
    """A fill sample point clear of gridlines, the fill handle, text and filter buttons."""
    rect = vp.cell_rect(r, c)
    return rect.right() - 20, rect.top() + 3


def _close(actual, expected: str, tol: int = 3) -> bool:
    from PySide6.QtGui import QColor

    e = QColor(expected)
    return all(
        abs(a - b) <= tol
        for a, b in zip(
            (actual.red(), actual.green(), actual.blue()), (e.red(), e.green(), e.blue())
        )
    )


def _filter_button_drawn(img, rect) -> bool:
    """Bevel face (236,233,216) plus a dark arrow inside the 16px button area."""
    from PySide6.QtGui import QColor

    face = QColor(236, 233, 216)
    pts = [
        (x, y)
        for x in range(rect.right() - 17, rect.right() + 1)
        for y in range(rect.bottom() - 17, rect.bottom() + 1)
    ]
    return any(img.pixelColor(x, y) == face for x, y in pts) and any(
        img.pixelColor(x, y).value() < 60
        for x in range(rect.right() - 12, rect.right() - 4)
        for y in range(rect.bottom() - 12, rect.bottom() - 4)
    )


def test_render_xmlmap_header_bands_and_filter_button(qtbot) -> None:
    sh = read_xlsx(XMLMAP)[0]
    vp, img = _grab(sh, qtbot)
    assert _close(img.pixelColor(*_center(vp, 5, 2)), ACCENT1)
    assert _close(img.pixelColor(*_center(vp, 6, 2)), apply_tint(ACCENT1, 0.6))
    assert _close(img.pixelColor(*_center(vp, 7, 2)), apply_tint(ACCENT1, 0.8))
    for c in (2, 3, 4):
        assert _filter_button_drawn(img, vp.cell_rect(5, c))
    assert not _filter_button_drawn(img, vp.cell_rect(6, 2))


def test_render_totals_row(qtbot) -> None:
    wb = read_xlsx(TOTALS_SHOWN)
    sh = next(s for s in wb.sheets if s.tables)
    vp, img = _grab(sh, qtbot)
    # D5 has no CellData in the file: the table style still paints it
    assert sh.get_cell(4, 3) is None or sh.get_cell(4, 3).bg_color is None
    assert _close(img.pixelColor(*_center(vp, 4, 3)), ACCENT1)


def test_render_tablerefsnamed_black_header_with_buttons(qtbot) -> None:
    sh = read_xlsx(TABLEREFS)[0]
    vp, img = _grab(sh, qtbot)
    for c in (0, 1):
        assert _close(img.pixelColor(*_center(vp, 0, c)), "#000000")
        assert _filter_button_drawn(img, vp.cell_rect(0, c))
    # header text ("Name") is drawn in the table's white font, not the default black
    rect = vp.cell_rect(0, 0)
    assert any(
        img.pixelColor(x, y).value() > 200
        for x in range(rect.left() + 2, rect.left() + 30)
        for y in range(rect.top() + 3, rect.bottom() - 2)
    )


def test_render_cell_fill_overrides_band(qtbot) -> None:
    sh = _sheet_with(_table())
    sh.set_cell(1, 0, CellData(value="x", bg_color="#FF0000"))
    vp, img = _grab(sh, qtbot, 500, 300)
    assert _close(img.pixelColor(*_center(vp, 1, 0)), "#FF0000")
    assert _close(img.pixelColor(*_center(vp, 1, 1)), apply_tint(ACCENT1, 0.6))
    # a table without <autoFilter> draws no filter buttons
    assert not _filter_button_drawn(img, vp.cell_rect(0, 0))


# --------------------------------------------------------------- round-trip


def _table_parts(payload: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        return {n: z.read(n) for n in z.namelist() if n.startswith("xl/tables/table")}


@pytest.mark.parametrize("dirty", [False, True])
@pytest.mark.parametrize("path", [XMLMAP, TOTALS_SHOWN, TABLEREFS, TOTALS_FN])
def test_roundtrip_keeps_table_parts(path: Path, dirty: bool) -> None:
    src = _table_parts(path.read_bytes())
    wb = read_xlsx(path)
    if dirty:
        sh = next(s for s in wb.sheets if s.tables)
        sh.set_cell_value(sh.tables[0].r2 + 3, 0, "edited")
        sh.dirty = True
    out = write_xlsx(wb)
    dst = _table_parts(out)
    assert len(dst) == len(src)
    assert all(b"tableStyleInfo" in v for v in dst.values() if b"<table " in v)
    wb2 = read_xlsx(io.BytesIO(out))
    names = [t.style_info.name for s in wb2.sheets for t in s.tables]
    assert names == [t.style_info.name for s in wb.sheets for t in s.tables]
