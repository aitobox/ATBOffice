"""Unit tests for Lectern DrawingML vector charts, scaling algorithms, and datasheet dialog."""

from __future__ import annotations

import zipfile

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.chart.io import (
    chart_to_xml,
    create_embedded_workbook,
    parse_chart_xml,
)
from atboffice.modules.presentation.chart.model import (
    CH_KINDS,
    ChartData,
)
from atboffice.modules.presentation.chart.painter import ChartPainter
from atboffice.modules.presentation.chart.scale import format_val, nice_step, scale
from atboffice.modules.presentation.dialogs.datasheet_dialog import (
    ChartPreviewWidget,
    DatasheetDialog,
)
from atboffice.modules.presentation.io.pptx_reader import PptxReader
from atboffice.modules.presentation.io.pptx_writer import PptxWriter
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.views.chart_item import ChartGraphicsItem


@pytest.fixture(autouse=True, scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


class TestChartScale:
    """Test suite for automatic axis scale calculations."""

    def test_nice_step(self):
        assert nice_step(0.8) == 1.0
        assert nice_step(1.5) == 2.0
        assert nice_step(4.0) == 5.0
        assert nice_step(7.0) == 10.0
        assert nice_step(15.0) == 20.0
        assert nice_step(45.0) == 50.0
        assert nice_step(80.0) == 100.0
        assert nice_step(-10.0) == 1.0

    def test_scale_positive_range(self):
        res = scale(10.0, 95.0, length=200.0)
        assert res["min"] == 0.0
        assert res["max"] >= 95.0
        assert res["step"] > 0.0
        assert len(res["ticks"]) >= 2
        assert 0.0 in res["ticks"]

    def test_scale_spanning_zero(self):
        res = scale(-25.0, 45.0, length=200.0)
        assert res["min"] <= -25.0
        assert res["max"] >= 45.0
        assert 0.0 in res["ticks"]

    def test_scale_zero_span(self):
        res = scale(5.0, 5.0, length=100.0)
        assert res["min"] < res["max"]
        assert len(res["ticks"]) >= 2

    def test_scale_logarithmic(self):
        ax = {"log": 10.0}
        res = scale(1.0, 1000.0, ax=ax, length=200.0)
        assert res["log"] == 10.0
        assert res["min"] <= 1.0
        assert res["max"] >= 1000.0
        assert 1.0 in res["ticks"]
        assert 10.0 in res["ticks"]
        assert 100.0 in res["ticks"]

    def test_format_val(self):
        assert format_val(1234.5) in ("1234.5", "1,234.5", "1234.50")
        assert format_val(None) == ""
        assert format_val(0.0) == "0"


class TestChartDataModel:
    """Test suite for ChartData and SeriesData."""

    def test_sample_creation(self):
        c = ChartData.create_sample("col")
        assert c.kind == "col"
        assert len(c.cats) == 4
        assert len(c.series) == 3
        assert c.series[0].name == "East"

    def test_to_dict_and_from_dict_roundtrip(self):
        c = ChartData.create_sample("barStacked")
        c.title = "Sales Report"
        c.legend = "b"
        c.grid_y = False
        c.labels = True

        d = c.to_dict()
        c2 = ChartData.from_dict(d)

        assert c2.kind == "barStacked"
        assert c2.title == "Sales Report"
        assert c2.legend == "b"
        assert not c2.grid_y
        assert c2.labels
        assert len(c2.cats) == len(c.cats)
        assert len(c2.series) == len(c.series)


class TestChartRendering:
    """Test suite verifying vector rendering of all 17 chart kinds."""

    @pytest.mark.parametrize("kind_tuple", CH_KINDS)
    def test_render_each_kind(self, qapp, kind_tuple):
        kind_id, _ = kind_tuple
        chart = ChartData.create_sample(kind_id)
        chart.title = f"Test {kind_id}"

        # Setup sizes and secondary coordinate data for scatter/bubble
        if kind_id == "scatter":
            for s in chart.series:
                s.xs = [1.0, 2.5, 4.0, 6.0]
        elif kind_id == "bubble":
            for s in chart.series:
                s.xs = [1.0, 2.0, 3.0, 4.0]
                s.sizes = [5.0, 10.0, 15.0, 20.0]

        img = QImage(400, 300, QImage.Format.Format_ARGB32)
        img.fill(0)

        painter = QPainter(img)
        rect = QRectF(0, 0, 400, 300)
        ChartPainter.paint_chart(painter, chart, rect)
        painter.end()

        # Image should contain rendered pixels
        assert not img.isNull()
        has_pixel = any(
            img.pixelColor(x, y).alpha() > 0
            for x in range(0, 400, 10)
            for y in range(0, 300, 10)
        )
        assert has_pixel


class TestChartXMLIO:
    """Test suite for DrawingML XML generation, parsing, and XLSX workbook."""

    def test_chart_to_xml_and_parse(self):
        c = ChartData.create_sample("lineMarkers")
        c.title = "Growth Trend"
        xml_str = chart_to_xml(c)

        assert "<c:chartSpace" in xml_str
        assert "<c:lineChart" in xml_str
        assert "Growth Trend" in xml_str

        # Parse back
        c_parsed = parse_chart_xml(xml_str)
        assert c_parsed.kind == "lineMarkers"
        assert c_parsed.title == "Growth Trend"
        assert len(c_parsed.series) == 3

    def test_embedded_workbook_generation(self):
        c = ChartData.create_sample("col")
        wb_bytes = create_embedded_workbook(c)
        assert len(wb_bytes) > 100

        # Verify valid zip
        import io

        with zipfile.ZipFile(io.BytesIO(wb_bytes), "r") as z:
            names = z.namelist()
            assert "[Content_Types].xml" in names
            assert "xl/workbook.xml" in names
            assert "xl/worksheets/sheet1.xml" in names


class TestPresentationMLChartRoundtrip:
    """Test suite for saving and loading slides with charts in PPTX packages."""

    def test_pptx_chart_save_and_read(self, tmp_path):
        pres = Presentation()
        slide = Slide(id="slide_1")

        chart_shape = Shape(
            id="sh_chart_1",
            type="chart",
            name="Quarterly Revenue Chart",
            x=50.0,
            y=60.0,
            w=500.0,
            h=350.0,
            chart=ChartData.create_sample("colStacked").to_dict(),
        )
        slide.add_shape(chart_shape)
        pres.slides.append(slide)

        pptx_file = tmp_path / "chart_test.pptx"
        writer = PptxWriter(pres)
        writer.write_to(pptx_file)

        assert pptx_file.exists()
        assert pptx_file.stat().st_size > 1000

        # Read back
        pres_loaded = PptxReader.open(pptx_file)

        assert len(pres_loaded.slides) == 1
        s_read = pres_loaded.slides[0]
        assert len(s_read.shapes) == 1

        loaded_shape = s_read.shapes[0]
        assert loaded_shape.is_chart
        assert loaded_shape.chart is not None
        assert loaded_shape.chart.get("kind") == "colStacked"
        assert len(loaded_shape.chart.get("series", [])) == 3


class TestDatasheetDialogAndItem:
    """Test suite for DatasheetDialog GUI and ChartGraphicsItem."""

    def test_datasheet_dialog_mutations(self, qtbot):
        c = ChartData.create_sample("col")
        dlg = DatasheetDialog(c)
        qtbot.addWidget(dlg)

        # Mutate title
        dlg.txt_title.setText("Updated Sales Title")
        assert dlg.chart.title == "Updated Sales Title"

        # Add column
        initial_cols = len(dlg.chart.cats)
        dlg._add_column()
        assert len(dlg.chart.cats) == initial_cols + 1

        # Delete column
        dlg._delete_column()
        assert len(dlg.chart.cats) == initial_cols

        # Add row
        initial_rows = len(dlg.chart.series)
        dlg._add_row()
        assert len(dlg.chart.series) == initial_rows + 1

        # Delete row
        dlg._delete_row()
        assert len(dlg.chart.series) == initial_rows

    def test_chart_graphics_item(self, qtbot):
        c = ChartData.create_sample("pie")
        sh = Shape(id="sh_1", type="chart", w=300.0, h=200.0, chart=c.to_dict())
        item = ChartGraphicsItem(sh)

        assert item.chart_data.kind == "pie"
        assert item.shape.w == 300.0
        assert item.shape.h == 200.0

        # Change data
        c2 = ChartData.create_sample("line")
        item.set_chart_data(c2)
        assert item.chart_data.kind == "line"
        assert item.shape.chart["kind"] == "line"

    def test_chart_preview_widget(self, qtbot):
        c = ChartData.create_sample("doughnut")
        pw = ChartPreviewWidget(c)
        qtbot.addWidget(pw)
        assert pw.chart.kind == "doughnut"
        c2 = ChartData.create_sample("area")
        pw.set_chart(c2)
        assert pw.chart.kind == "area"
