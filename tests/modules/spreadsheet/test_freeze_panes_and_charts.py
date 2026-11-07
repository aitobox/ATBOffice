"""Unit tests for spreadsheet freeze panes multi-viewport and DrawingML chart rendering."""

from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from atboffice.modules.presentation.chart.model import ChartData, SeriesData
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel, SheetGeometry
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport, HitZone
from atboffice.modules.spreadsheet.views.object_layer import (
    AnchorType,
    CellAnchorPoint,
    FloatingObject,
    SpreadsheetObjectLayer,
    object_to_rect,
)


class TestFloatingObjectAndChart:
    """Test FloatingObject chart_data model and vector rendering."""

    def test_floating_object_chart_data_serialization(self) -> None:
        chart_data = {
            "kind": "col",
            "title": "Quarterly Sales",
            "cats": ["Q1", "Q2", "Q3"],
            "series": [{"name": "Revenue", "vals": [100.0, 200.0, 300.0]}],
        }
        obj = FloatingObject(
            id=10,
            name="SalesChart",
            kind="chart",
            chart_data=chart_data,
        )

        d = obj.to_dict()
        assert d["kind"] == "chart"
        assert d["name"] == "SalesChart"
        assert d["chart_data"] == chart_data

        restored = FloatingObject.from_dict(d)
        assert restored.kind == "chart"
        assert restored.name == "SalesChart"
        assert restored.chart_data is not None
        assert restored.chart_data["title"] == "Quarterly Sales"

        cloned = obj.clone()
        assert cloned.chart_data == chart_data
        assert cloned is not obj

    def test_object_to_rect_with_freeze_panes(self) -> None:
        geom = SheetGeometry()
        obj_pinned = FloatingObject(
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=0, col_off=5, row=0, row_off=5),
            to_point=CellAnchorPoint(col=1, col_off=10, row=1, row_off=10),
        )
        obj_scrolling = FloatingObject(
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=5, col_off=5, row=5, row_off=5),
            to_point=CellAnchorPoint(col=8, col_off=10, row=8, row_off=10),
        )

        # When scroll_x=100, scroll_y=200, freeze_rows=1, freeze_cols=1
        r_pinned = object_to_rect(
            obj_pinned,
            geom,
            scroll_x=100,
            scroll_y=200,
            row_header_width=46,
            col_header_height=22,
            freeze_rows=1,
            freeze_cols=1,
        )
        r_scrolling = object_to_rect(
            obj_scrolling,
            geom,
            scroll_x=100,
            scroll_y=200,
            row_header_width=46,
            col_header_height=22,
            freeze_rows=1,
            freeze_cols=1,
        )

        # Pinned object's top-left ignores scroll
        assert r_pinned.left() == 46 + 5  # eff_sx is 0
        assert r_pinned.top() == 22 + 5   # eff_sy is 0

        # Scrolling object's top-left includes scroll offsets
        assert r_scrolling.left() == 46 + geom.col_pos(5) + 5 - 100
        assert r_scrolling.top() == 22 + geom.row_pos(5) + 5 - 200

    def test_spread_sheet_object_layer_draw_chart(self, qtbot) -> None:
        sheet = SheetDataModel(name="Sheet1")
        layer = SpreadsheetObjectLayer(model=sheet)
        qtbot.addWidget(layer)
        layer.resize(400, 300)

        chart = ChartData(
            kind="col",
            title="Test Bar Chart",
            cats=["Jan", "Feb", "Mar"],
            series=[SeriesData(name="Series 1", vals=[10.0, 20.0, 15.0])],
        )
        obj = FloatingObject(
            id=1,
            name="Chart1",
            kind="chart",
            abs_rect=(50, 50, 200, 150),
            anchor_type=AnchorType.ABSOLUTE,
            chart_data=chart.to_dict(),
        )
        sheet.drawings = [obj]

        pix = QPixmap(400, 300)
        pix.fill(Qt.GlobalColor.white)
        painter = QPainter(pix)
        try:
            layer._paint_object(painter, obj, QRect(50, 50, 200, 150))
        finally:
            painter.end()

        assert not pix.isNull()


class TestXlsxReaderGraphicFrameChart:
    """Test parsing <xdr:graphicFrame> in xlsx_reader."""

    def test_read_xlsx_with_chart_graphic_frame(self) -> None:
        # Build minimal XLSX with a chart drawing
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                '  <Default Extension="xml" ContentType="application/xml"/>\n'
                '  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\n'
                '  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
                '  <Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>\n'
                '  <Override PartName="/xl/charts/chart1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>\n'
                "</Types>",
            )
            zf.writestr(
                "_rels/.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>\n'
                "</Relationships>",
            )
            zf.writestr(
                "xl/workbook.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
                '  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>\n'
                "</workbook>",
            )
            zf.writestr(
                "xl/_rels/workbook.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>\n'
                "</Relationships>",
            )
            zf.writestr(
                "xl/worksheets/sheet1.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
                '  <sheetData><row r="1"><c r="A1"><v>123</v></c></row></sheetData>\n'
                '  <drawing r:id="rIdDrw1"/>\n'
                "</worksheet>",
            )
            zf.writestr(
                "xl/worksheets/_rels/sheet1.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                '  <Relationship Id="rIdDrw1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/>\n'
                "</Relationships>",
            )
            zf.writestr(
                "xl/drawings/drawing1.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
                '  <xdr:twoCellAnchor editAs="twoCell">\n'
                '    <xdr:from><xdr:col>2</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>2</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>\n'
                '    <xdr:to><xdr:col>8</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>12</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>\n'
                '    <xdr:graphicFrame macro="">\n'
                '      <xdr:nvGraphicFramePr>\n'
                '        <xdr:cNvPr id="2" name="Revenue Chart"/>\n'
                '        <xdr:cNvGraphicFramePr/>\n'
                '      </xdr:nvGraphicFramePr>\n'
                '      <xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm>\n'
                '      <a:graphic>\n'
                '        <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">\n'
                '          <c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" r:id="rIdChart1"/>\n'
                '        </a:graphicData>\n'
                '      </a:graphic>\n'
                '    </xdr:graphicFrame>\n'
                '    <xdr:clientData/>\n'
                '  </xdr:twoCellAnchor>\n'
                "</xdr:wsDr>",
            )
            zf.writestr(
                "xl/drawings/_rels/drawing1.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                '  <Relationship Id="rIdChart1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="../charts/chart1.xml"/>\n'
                "</Relationships>",
            )
            zf.writestr(
                "xl/charts/chart1.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">\n'
                '  <c:chart>\n'
                '    <c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Quarterly Revenue</a:t></a:r></a:p></c:rich></c:tx></c:title>\n'
                '    <c:plotArea>\n'
                '      <c:barChart>\n'
                '        <c:barDir val="col"/>\n'
                '        <c:grouping val="clustered"/>\n'
                '        <c:ser>\n'
                '          <c:idx val="0"/>\n'
                '          <c:order val="0"/>\n'
                '          <c:tx><c:v>Sales</c:v></c:tx>\n'
                '          <c:cat><c:strLit><c:ptCount val="2"/><c:pt idx="0"><c:v>2025</c:v></c:pt><c:pt idx="1"><c:v>2026</c:v></c:pt></c:strLit></c:cat>\n'
                '          <c:val><c:numLit><c:ptCount val="2"/><c:pt idx="0"><c:v>500</c:v></c:pt><c:pt idx="1"><c:v>800</c:v></c:pt></c:numLit></c:val>\n'
                '        </c:ser>\n'
                '      </c:barChart>\n'
                '    </c:plotArea>\n'
                '  </c:chart>\n'
                "</c:chartSpace>",
            )

        buf.seek(0)
        wb = read_xlsx(buf)
        assert len(wb.sheets) == 1
        sh = wb.sheets[0]
        assert len(sh.drawings) == 1
        d = sh.drawings[0]
        assert d.kind == "chart"
        assert d.name == "Revenue Chart"
        assert d.chart_data is not None
        assert d.chart_data["title"] == "Quarterly Revenue"
        assert d.chart_data["kind"] == "col"


class TestFreezePanesGridViewport:
    """Test multi-viewport coordinate mapping, hit testing, reveal, and painting."""

    def test_cell_rect_freeze_panes(self, qtbot) -> None:
        wb = WorkbookModel()
        sheet = wb.sheets[0]
        sheet.freeze_rows = 2
        sheet.freeze_cols = 1

        viewport = GridViewport(model=sheet)
        qtbot.addWidget(viewport)
        viewport.resize(800, 600)

        # Scroll 150px down, 100px right
        viewport.horizontalScrollBar().setValue(100)
        viewport.verticalScrollBar().setValue(150)

        # Cell (0, 0) is in the corner frozen pane
        r_0_0 = viewport.cell_rect(0, 0)
        assert r_0_0.left() == viewport.row_header_width
        assert r_0_0.top() == viewport.col_header_height

        # Cell (1, 5) is in the top frozen pane (row 1 is frozen, col 5 is scrolling)
        r_1_5 = viewport.cell_rect(1, 5)
        assert r_1_5.top() == viewport.col_header_height + viewport.geometry_mapper.row_pos(1)
        assert r_1_5.left() == viewport.row_header_width + viewport.geometry_mapper.col_pos(5) - 100

        # Cell (5, 0) is in the left frozen pane (row 5 is scrolling, col 0 is frozen)
        r_5_0 = viewport.cell_rect(5, 0)
        assert r_5_0.left() == viewport.row_header_width
        assert r_5_0.top() == viewport.col_header_height + viewport.geometry_mapper.row_pos(5) - 150

        # Cell (5, 5) is in the main scrolling pane
        r_5_5 = viewport.cell_rect(5, 5)
        assert r_5_5.left() == viewport.row_header_width + viewport.geometry_mapper.col_pos(5) - 100
        assert r_5_5.top() == viewport.col_header_height + viewport.geometry_mapper.row_pos(5) - 150

    def test_hit_test_freeze_panes(self, qtbot) -> None:
        wb = WorkbookModel()
        sheet = wb.sheets[0]
        sheet.freeze_rows = 2
        sheet.freeze_cols = 1

        viewport = GridViewport(model=sheet)
        qtbot.addWidget(viewport)
        viewport.resize(800, 600)

        viewport.horizontalScrollBar().setValue(100)
        viewport.verticalScrollBar().setValue(150)

        x0 = viewport.row_header_width
        y0 = viewport.col_header_height

        # Point inside frozen corner pane (row 0, col 0)
        hit_corner = viewport.hit_test(x0 + 10, y0 + 10)
        assert hit_corner.zone == HitZone.CELL
        assert hit_corner.row == 0
        assert hit_corner.col == 0

        # Point inside frozen top pane (row 0, scrollable column)
        hit_top = viewport.hit_test(x0 + 200, y0 + 10)
        assert hit_top.zone == HitZone.CELL
        assert hit_top.row == 0
        expected_col = viewport.geometry_mapper.find_col_at(100 + 200)
        assert hit_top.col == expected_col

        # Point inside frozen left pane (scrollable row, col 0)
        hit_left = viewport.hit_test(x0 + 10, y0 + 150)
        assert hit_left.zone == HitZone.CELL
        assert hit_left.col == 0
        expected_row = viewport.geometry_mapper.find_row_at(150 + 150)
        assert hit_left.row == expected_row

        # Point in column header area (frozen col 0)
        hit_hdr_col = viewport.hit_test(x0 + 10, 5)
        assert hit_hdr_col.zone == HitZone.COL_HEADER
        assert hit_hdr_col.col == 0

        # Point in row header area (frozen row 0)
        hit_hdr_row = viewport.hit_test(5, y0 + 10)
        assert hit_hdr_row.zone == HitZone.ROW_HEADER
        assert hit_hdr_row.row == 0

    def test_reveal_with_freeze_panes(self, qtbot) -> None:
        wb = WorkbookModel()
        sheet = wb.sheets[0]
        sheet.freeze_rows = 2
        sheet.freeze_cols = 2

        viewport = GridViewport(model=sheet)
        qtbot.addWidget(viewport)
        viewport.resize(500, 400)

        viewport.verticalScrollBar().setValue(100)
        viewport.horizontalScrollBar().setValue(100)

        # Revealing frozen cell (1, 1) should not change scroll position
        viewport.reveal(1, 1)
        assert viewport.verticalScrollBar().value() == 100
        assert viewport.horizontalScrollBar().value() == 100

        # Revealing cell far down should update scrollbar
        viewport.reveal(50, 20)
        assert viewport.verticalScrollBar().value() > 100
        assert viewport.horizontalScrollBar().value() > 100

    def test_freeze_panes_rendering_no_crash(self, qtbot) -> None:
        wb = WorkbookModel()
        sheet = wb.sheets[0]
        sheet.freeze_rows = 2
        sheet.freeze_cols = 1
        sheet.set_cell_value(0, 0, "Header A1")
        sheet.set_cell_value(1, 0, "Header A2")
        sheet.set_cell_value(5, 5, "Data F6")

        viewport = GridViewport(model=sheet)
        qtbot.addWidget(viewport)
        viewport.resize(600, 400)

        viewport.verticalScrollBar().setValue(50)
        viewport.horizontalScrollBar().setValue(50)

        pix = QPixmap(600, 400)
        viewport.render(pix)
        assert not pix.isNull()
