"""Worksheet charts inherit Excel's chart-area and automatic-title defaults on import."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from atboffice.modules.presentation.chart.io import parse_chart_xml
from atboffice.modules.presentation.chart.model import ChartData
from atboffice.modules.presentation.chart.painter import ChartPainter
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx

FIXTURES = Path(__file__).resolve().parents[2] / "docs" / "excel" / "xlsx"
NS = (
    'xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
)
ONE_SERIES = (
    "<c:ser><c:tx><c:strRef><c:strCache><c:pt idx=\"0\"><c:v>Demo</c:v></c:pt>"
    "</c:strCache></c:strRef></c:tx>"
    '<c:val><c:numLit><c:pt idx="0"><c:v>1</c:v></c:pt></c:numLit></c:val></c:ser>'
)


def _xml(title: str = "", series: str = ONE_SERIES, space_props: str = "") -> str:
    return (
        f"<c:chartSpace {NS}><c:chart>{title}<c:plotArea><c:barChart>{series}</c:barChart>"
        f"</c:plotArea></c:chart>{space_props}</c:chartSpace>"
    )


def _worksheet_chart(xml: str) -> ChartData:
    return parse_chart_xml(xml, worksheet_defaults=True)


def _fixture_chart(name: str) -> dict:
    drawings = read_xlsx(str(FIXTURES / name)).sheets[0].drawings
    charts = [d for d in drawings if d.kind == "chart"]
    assert len(charts) == 1
    return charts[0].chart_data


class TestChartAreaFill:
    def test_missing_properties_use_opaque_white_with_border(self) -> None:
        chart = _worksheet_chart(_xml())
        assert QColor(chart.bg["c"]) == QColor("#FFFFFF")
        assert chart.border is not None and chart.border.get("t") != "none"

    def test_explicit_no_fill_stays_transparent(self) -> None:
        props = "<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>"
        chart = _worksheet_chart(_xml(space_props=props))
        assert chart.bg is None
        assert chart.border == {"t": "none"}

    def test_transparency_survives_the_drawing_round_trip(self) -> None:
        props = "<c:spPr><a:noFill/></c:spPr>"
        chart = _worksheet_chart(_xml(space_props=props))
        assert ChartData.from_dict(chart.to_dict()).bg is None

    def test_explicit_solid_fill_and_line_are_kept(self) -> None:
        props = (
            '<c:spPr><a:solidFill><a:srgbClr val="FFEE00"/></a:solidFill>'
            '<a:ln><a:solidFill><a:srgbClr val="112233"/></a:solidFill></a:ln></c:spPr>'
        )
        chart = _worksheet_chart(_xml(space_props=props))
        assert chart.bg == {"c": "#FFEE00"}
        assert chart.border == {"c": "#112233"}

    def test_theme_fill_is_kept(self) -> None:
        props = '<c:spPr><a:solidFill><a:schemeClr val="accent2"/></a:solidFill></c:spPr>'
        assert _worksheet_chart(_xml(space_props=props)).bg == {"c": "accent2"}

    def test_fill_alpha_is_kept_and_painted(self, qapp) -> None:
        props = (
            '<c:spPr><a:solidFill><a:srgbClr val="FF0000"><a:alpha val="50000"/>'
            "</a:srgbClr></a:solidFill><a:ln><a:noFill/></a:ln></c:spPr>"
        )
        chart = _worksheet_chart(_xml(space_props=props))
        assert chart.bg == {"c": "#FF0000", "a": 0.5}
        pixel = _paint_corner_pixel(chart, QColor("#FFFFFF"))
        assert pixel.green() == pytest.approx(128, abs=3)

    def test_unsupported_fill_falls_back_to_opaque_white(self) -> None:
        props = "<c:spPr><a:gradFill/></c:spPr>"
        assert QColor(_worksheet_chart(_xml(space_props=props)).bg["c"]) == QColor("#FFFFFF")


def _paint_corner_pixel(chart: ChartData, backdrop: QColor) -> QColor:
    image = QImage(200, 150, QImage.Format.Format_ARGB32)
    image.fill(backdrop)
    painter = QPainter(image)
    ChartPainter.paint_chart(painter, chart, QRectF(0, 0, 200, 150))
    painter.end()
    return image.pixelColor(3, 3)


class TestPaintedChartArea:
    def test_default_area_hides_cells_behind_it(self, qapp) -> None:
        pixel = _paint_corner_pixel(_worksheet_chart(_xml()), QColor("#FF0000"))
        assert pixel == QColor("#FFFFFF")

    def test_transparent_area_shows_cells_behind_it(self, qapp) -> None:
        props = "<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>"
        pixel = _paint_corner_pixel(_worksheet_chart(_xml(space_props=props)), QColor("#FF0000"))
        assert pixel == QColor("#FF0000")


class TestAutomaticTitle:
    def test_empty_title_uses_the_single_series_name(self) -> None:
        assert _worksheet_chart(_xml("<c:title><c:layout/></c:title>")).title == "Demo"

    def test_empty_title_with_several_series_uses_office_placeholder(self) -> None:
        xml = _xml("<c:title/>", series=ONE_SERIES * 2)
        assert _worksheet_chart(xml).title == "Chart Title"

    def test_missing_title_uses_the_single_series_name(self) -> None:
        assert _worksheet_chart(_xml()).title == "Demo"

    def test_missing_title_with_several_series_stays_empty(self) -> None:
        assert _worksheet_chart(_xml(series=ONE_SERIES * 2)).title == ""

    @pytest.mark.parametrize("flag", ['<c:autoTitleDeleted val="1"/>', "<c:autoTitleDeleted/>"])
    def test_deleted_automatic_title_stays_empty(self, flag: str) -> None:
        assert _worksheet_chart(_xml(flag)).title == ""

    def test_kept_automatic_title_flag_uses_the_series_name(self) -> None:
        assert _worksheet_chart(_xml('<c:autoTitleDeleted val="0"/>')).title == "Demo"

    def test_rich_title_wins(self) -> None:
        title = (
            "<c:title><c:tx><c:rich><a:p><a:r><a:t>Sales</a:t></a:r></a:p></c:rich></c:tx>"
            "</c:title>"
        )
        assert _worksheet_chart(_xml(title)).title == "Sales"

    def test_cell_linked_title_uses_its_cached_text(self) -> None:
        title = (
            "<c:title><c:tx><c:strRef><c:strCache><c:pt idx=\"0\"><c:v>Linked</c:v></c:pt>"
            "</c:strCache></c:strRef></c:tx></c:title>"
        )
        assert _worksheet_chart(_xml(title)).title == "Linked"


class TestOtherHostsUnchanged:
    def test_default_parse_adds_no_worksheet_defaults(self) -> None:
        chart = parse_chart_xml(_xml("<c:title/>"))
        assert chart.title == ""
        assert chart.bg is None
        assert chart.border is None


class TestAuditedFixtures:
    def test_no_ext_data_chart_area_is_opaque(self) -> None:
        data = _fixture_chart("openxml-sdk__NoExtDataB1.xlsx")
        assert QColor(data["bg"]["c"]) == QColor("#FFFFFF")
        assert data["kind"] == "bar"

    def test_poi_60509_shows_demo_title_and_eight_columns(self) -> None:
        data = _fixture_chart("poi__60509.xlsx")
        assert data["title"] == "Demo"
        assert QColor(data["bg"]["c"]) == QColor("#FFFFFF")
        assert data["cats"] == [str(year) for year in range(2005, 2013)]
        assert len(data["series"][0]["vals"]) == 8
