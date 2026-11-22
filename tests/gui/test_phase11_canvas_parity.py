"""Regression tests for issue #441: canvas geometry and colour parity with the reference app."""

from __future__ import annotations

import glob
import xml.etree.ElementTree as ET

import pytest
from PySide6.QtGui import QColor, QImage

from atboffice.modules.presentation.io.pptx_reader import _diagram_color_style
from atboffice.modules.presentation.smartart.palettes import color_spec, paint_shape
from atboffice.modules.spreadsheet.models.selection_model import SelectionRange
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport

# ---------------------------------------------------------------------------
# Ledger header geometry & colours (ledger/js/render.js RD.frame / COL)
# ---------------------------------------------------------------------------


@pytest.fixture
def grid(qtbot) -> GridViewport:
    vp = GridViewport()
    qtbot.addWidget(vp)
    vp.resize(800, 600)
    vp.show()
    vp.update_header_dimensions()
    return vp


def test_row_header_fits_visible_row_numbers(grid: GridViewport) -> None:
    # Two-digit row numbers: the 25px minimum (render.js) instead of the old fixed 46px.
    assert grid.MIN_ROW_HEADER_WIDTH <= grid.row_header_width <= 30
    assert grid.col_header_height == max(17, grid.geometry_mapper.default_row_height)


def test_row_header_grows_with_row_number_digits(grid: GridViewport) -> None:
    narrow = grid.row_header_width
    grid.verticalScrollBar().setMaximum(10_000_000)
    grid.verticalScrollBar().setValue(grid.geometry_mapper.row_pos(99_990))

    assert grid.update_header_dimensions() is True
    assert grid.row_header_width > narrow


def test_column_header_matches_default_row_height(qtbot) -> None:
    vp = GridViewport()
    qtbot.addWidget(vp)
    vp.geometry_mapper.default_row_height = 17
    vp.update_header_dimensions()
    assert vp.col_header_height == 17

    vp.geometry_mapper.default_row_height = 30
    vp.update_header_dimensions()
    assert vp.col_header_height == 30


def test_header_change_resyncs_object_layer(qtbot) -> None:
    view = SpreadsheetView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    view.grid.verticalScrollBar().setMaximum(10_000_000)
    view.grid.verticalScrollBar().setValue(view.grid.geometry_mapper.row_pos(99_990))

    view.grid.update_header_dimensions()

    layer = view.object_layer
    assert (layer.row_header_width, layer.col_header_height) == (
        view.grid.row_header_width,
        view.grid.col_header_height,
    )


def test_reference_colours(grid: GridViewport) -> None:
    assert grid.COLOR_GRIDLINE == QColor("#C0C0C0")
    assert grid.COLOR_HDR_BORDER == QColor("#9EB6CE")
    assert grid.COLOR_ACTIVE_BORDER == QColor("#000000")


def _render(grid: GridViewport) -> QImage:
    grid.viewport().update()
    return grid.viewport().grab().toImage()


def _cell_center(grid: GridViewport, r: int, c: int) -> tuple[int, int]:
    geo = grid.geometry_mapper
    x = grid.row_header_width + geo.col_pos(c) + geo.col_size(c) // 2
    y = grid.col_header_height + geo.row_pos(r) + geo.row_size(r) // 2
    return x, y


def test_single_cell_selection_is_not_shaded(grid: GridViewport) -> None:
    grid.selection.select_cell(2, 2)
    img = _render(grid)
    x, y = _cell_center(grid, 2, 2)
    assert QColor(img.pixel(x, y)) == QColor("#FFFFFF")


def test_range_selection_shades_all_but_active_cell(grid: GridViewport) -> None:
    grid.selection.clear()
    grid.selection.add_range(SelectionRange(2, 2, 4, 4))
    grid.selection.set_active_cell(2, 2)
    img = _render(grid)

    ax, ay = _cell_center(grid, 2, 2)
    sx, sy = _cell_center(grid, 3, 3)
    assert QColor(img.pixel(ax, ay)) == QColor("#FFFFFF")
    assert QColor(img.pixel(sx, sy)) != QColor("#FFFFFF")


# ---------------------------------------------------------------------------
# Lectern workspace chrome
# ---------------------------------------------------------------------------


def test_notes_pane_defaults_to_reference_height(qtbot) -> None:
    from atboffice.modules.presentation.models.presentation import Presentation
    from atboffice.modules.presentation.views.workspace import LecternWorkspace

    pres = Presentation.create_new(title="Parity", empty=True)
    pres.add_slide()
    ws = LecternWorkspace(presentation=pres)
    qtbot.addWidget(ws)
    ws.resize(1100, 800)
    ws.show()
    qtbot.waitExposed(ws)

    assert ws.notes_pane.sizeHint().height() == 92
    assert ws.notes_pane.height() == 92
    assert not ws.notes_pane.title_label.isVisible()


# ---------------------------------------------------------------------------
# SmartArt theme colours
# ---------------------------------------------------------------------------

_THEME = {
    "dk1": "#000000",
    "lt1": "#FFFFFF",
    "dk2": "#1F497D",
    "accent1": "#4F81BD",
    "accent2": "#C0504D",
    "accent3": "#9BBB59",
}


def _prset_xml(cs: str, qs: str) -> ET.Element:
    ns = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
    return ET.fromstring(
        f'<dgm:dataModel xmlns:dgm="{ns}"><dgm:ptLst><dgm:pt type="doc">'
        f'<dgm:prSet csTypeId="{cs}" qsTypeId="{qs}"/></dgm:pt></dgm:ptLst></dgm:dataModel>'
    )


@pytest.mark.parametrize(
    ("cs", "qs", "expected"),
    [
        ("colors/accent1_2", "quickstyle/simple1", ("accent1", None)),
        ("colors/accent3_4", "quickstyle/simple3", ("accent3", "subtle")),
        ("colors/colorful1", "quickstyle/3d2", ("colorful", "intense")),
        ("colors/colorful5", "quickstyle/moderate1", ("colorful", "moderate")),
        ("colors/unknown", "quickstyle/other", (None, None)),
    ],
)
def test_diagram_colour_and_style_ids(cs: str, qs: str, expected) -> None:
    urn = "urn:microsoft.com/office/officeart/2005/8/"
    assert _diagram_color_style(_prset_xml(urn + cs, urn + qs)) == expected


def test_theme_colour_spec() -> None:
    accent = color_spec("accent1", _THEME)
    assert accent["base"] == "#4F81BD"
    assert accent["meth"] == "repeat"

    colorful = color_spec("colorful", _THEME)
    assert colorful["cols"][:3] == ["#4F81BD", "#C0504D", "#9BBB59"]
    assert colorful["meth"] == "cycle"

    # Without a theme the engine keeps its own default palette.
    assert color_spec("accent1")["name"] == "Ocean"


def test_paint_shape_uses_attached_theme() -> None:
    painted = paint_shape({"role": "node"}, {"colors": "accent1", "theme": _THEME})
    assert painted["fill"]["c"] == "#4F81BD"


def test_imported_smartart_is_coloured_from_theme(qapp) -> None:
    from atboffice.modules.presentation.io.pptx_reader import read_pptx

    paths = glob.glob("tests/docs/**/libreoffice__smartart-text.pptx", recursive=True)
    if not paths:
        pytest.skip("smartart-text.pptx sample not available")
    pres = read_pptx(paths[0])
    diagrams = [sh for s in pres.slides for sh in s.shapes if getattr(sh, "sa", None)]
    assert diagrams
    sa = diagrams[0].sa
    assert sa["colors"] == "accent1"
    assert sa["theme"]["accent1"] == "#4F81BD"
