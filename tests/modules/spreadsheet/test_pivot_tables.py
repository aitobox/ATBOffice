"""Unit and integration tests for Pivot Table models, OPC preservation, and wizard dialog."""

import io
import xml.etree.ElementTree as ET
import zipfile

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.dialogs.pivot_dialog import (
    PivotTableWizardDialog,
)
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.pivot_model import (
    PivotConfig,
    PivotContainer,
    build_pivot_table,
)
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def create_sample_sales_workbook() -> tuple[WorkbookModel, SheetDataModel]:
    """Create a sample workbook with a 4-column sales dataset."""
    wb = WorkbookModel()
    sheet = wb[0]
    sheet.name = "SalesData"

    data = [
        ["Region", "Product", "Quarter", "Sales"],
        ["East", "Widget", "Q1", 100],
        ["East", "Gadget", "Q1", 200],
        ["West", "Widget", "Q1", 150],
        ["West", "Gadget", "Q2", 300],
        ["East", "Widget", "Q2", 120],
        ["North", "Gadget", "Q2", 250],
        ["North", "Widget", "Q1", 180],
    ]
    for r, row in enumerate(data):
        for c, val in enumerate(row):
            sheet.set_cell_value(r, c, val)

    return wb, sheet


def test_pivot_calculation_sum():
    """Verify cross-tabulation static calculation with SUM aggregation."""
    wb, sheet = create_sample_sales_workbook()
    cfg = PivotConfig(
        source_sheet="SalesData",
        source_range=(0, 0, 7, 3),
        row_field_col=0,  # Region
        col_field_col=1,  # Product
        data_field_col=3,  # Sales
        agg_func="sum",
        target_sheet="new",
    )
    dst_sheet, bbox = build_pivot_table(wb, cfg)

    assert len(wb) == 2
    assert wb.active_sheet == dst_sheet
    r0, c0, end_r, end_c = bbox

    # Header title
    assert "Sum of Sales" in str(dst_sheet.get_cell_value(r0, c0))
    assert dst_sheet.get_cell_value(r0, c0 + 1) == "Product"

    # Region header & product headers
    hr = r0 + 1
    assert dst_sheet.get_cell_value(hr, c0) == "Region"
    assert dst_sheet.get_cell_value(hr, c0 + 1) == "Gadget"
    assert dst_sheet.get_cell_value(hr, c0 + 2) == "Widget"
    assert dst_sheet.get_cell_value(hr, c0 + 3) == "Grand Total"

    # Row 1: East -> Gadget 200, Widget 220, Total 420
    assert dst_sheet.get_cell_value(hr + 1, c0) == "East"
    assert dst_sheet.get_cell_value(hr + 1, c0 + 1) == 200.0
    assert dst_sheet.get_cell_value(hr + 1, c0 + 2) == 220.0
    assert dst_sheet.get_cell_value(hr + 1, c0 + 3) == 420.0

    # Row 2: North -> Gadget 250, Widget 180, Total 430
    assert dst_sheet.get_cell_value(hr + 2, c0) == "North"
    assert dst_sheet.get_cell_value(hr + 2, c0 + 1) == 250.0
    assert dst_sheet.get_cell_value(hr + 2, c0 + 2) == 180.0
    assert dst_sheet.get_cell_value(hr + 2, c0 + 3) == 430.0

    # Row 3: West -> Gadget 300, Widget 150, Total 450
    assert dst_sheet.get_cell_value(hr + 3, c0) == "West"
    assert dst_sheet.get_cell_value(hr + 3, c0 + 1) == 300.0
    assert dst_sheet.get_cell_value(hr + 3, c0 + 2) == 150.0
    assert dst_sheet.get_cell_value(hr + 3, c0 + 3) == 450.0

    # Grand Total row
    gr = hr + 4
    assert dst_sheet.get_cell_value(gr, c0) == "Grand Total"
    assert dst_sheet.get_cell_value(gr, c0 + 1) == 750.0
    assert dst_sheet.get_cell_value(gr, c0 + 2) == 550.0
    assert dst_sheet.get_cell_value(gr, c0 + 3) == 1300.0


def test_pivot_calculation_count_average_and_filters():
    """Verify COUNT, AVERAGE, single-axis pivot, and Page filtering."""
    wb, sheet = create_sample_sales_workbook()

    # 1. Single-axis pivot (no column field) with COUNT
    cfg_single = PivotConfig(
        source_sheet="SalesData",
        source_range=(0, 0, 7, 3),
        row_field_col=0,  # Region
        col_field_col=None,  # No column breakdown
        data_field_col=3,
        agg_func="count",
        target_sheet="SummaryCount",
    )
    dst_count, bbox = build_pivot_table(wb, cfg_single)
    r0, c0, end_r, end_c = bbox

    hr = r0 + 1
    assert dst_count.get_cell_value(hr, c0) == "Region"
    assert dst_count.get_cell_value(hr, c0 + 1) == "Total"
    assert dst_count.get_cell_value(hr + 1, c0) == "East"
    assert dst_count.get_cell_value(hr + 1, c0 + 1) == 3  # 3 sales in East
    assert dst_count.get_cell_value(hr + 2, c0) == "North"
    assert dst_count.get_cell_value(hr + 2, c0 + 1) == 2  # 2 sales in North
    assert dst_count.get_cell_value(hr + 3, c0) == "West"
    assert dst_count.get_cell_value(hr + 3, c0 + 1) == 2  # 2 sales in West
    assert dst_count.get_cell_value(hr + 4, c0) == "Grand Total"
    assert dst_count.get_cell_value(hr + 4, c0 + 1) == 7

    # 2. Pivot with Page Filter (Quarter = Q1 only) and AVERAGE
    cfg_filter = PivotConfig(
        source_sheet="SalesData",
        source_range=(0, 0, 7, 3),
        row_field_col=0,
        col_field_col=1,
        data_field_col=3,
        agg_func="average",
        page_field_col=2,  # Quarter
        page_filter_val="Q1",
        target_sheet="AvgQ1",
    )
    dst_avg, bbox_avg = build_pivot_table(wb, cfg_filter)
    r0, c0, end_r, end_c = bbox_avg

    # East Q1: Widget 100, Gadget 200 -> Average 150.0
    hr = r0 + 1
    assert dst_avg.get_cell_value(hr + 1, c0) == "East"
    assert dst_avg.get_cell_value(hr + 1, c0 + 1) == 200.0  # Gadget
    assert dst_avg.get_cell_value(hr + 1, c0 + 2) == 100.0  # Widget
    assert dst_avg.get_cell_value(hr + 1, c0 + 3) == 150.0  # East Q1 Avg


def test_pivot_ooxml_roundtrip_lossless():
    """Verify that an XLSX package with pivotTable and pivotCache is read and preserved."""
    # Construct a minimal XLSX package with pivotCache and pivotTable in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        types_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\n'
            '  <Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
            '  <Override PartName="/xl/pivotCaches/pivotCacheDefinition1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml"/>\n'
            '  <Override PartName="/xl/pivotCaches/pivotCacheRecords1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheRecords+xml"/>\n'
            '  <Override PartName="/xl/pivotTables/pivotTable1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"/>\n'
            "</Types>"
        )
        z.writestr("[Content_Types].xml", types_xml)
        rel_office = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
        )
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{rel_office}" Target="xl/workbook.xml"/>\n'
            "</Relationships>"
        )
        z.writestr("_rels/.rels", root_rels)
        wb_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
            '  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>\n'
            '  <pivotCaches><pivotCache cacheId="1" r:id="rIdCache1"/></pivotCaches>\n'
            "</workbook>"
        )
        z.writestr("xl/workbook.xml", wb_xml)
        rel_cache = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheDefinition"
        )
        rel_ws = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
        wb_rels = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{rel_ws}" Target="worksheets/sheet1.xml"/>\n'
            f'  <Relationship Id="rIdCache1" Type="{rel_cache}" '
            'Target="pivotCaches/pivotCacheDefinition1.xml"/>\n'
            "</Relationships>"
        )
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        ws_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n'
            "  <sheetData>\n"
            '    <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>\n'
            '    <row r="2"><c r="A2"><v>10</v></c><c r="B2"><v>20</v></c></row>\n'
            "  </sheetData>\n"
            "</worksheet>"
        )
        z.writestr("xl/worksheets/sheet1.xml", ws_xml)
        rel_pt = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotTable"
        )
        ws_rels = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rIdPivot1" Type="{rel_pt}" '
            'Target="../pivotTables/pivotTable1.xml"/>\n'
            "</Relationships>"
        )
        z.writestr("xl/worksheets/_rels/sheet1.xml.rels", ws_rels)
        # Mock definition parts
        cache_xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>\n'
            b'<pivotCacheDefinition '
            b'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" recordCount="1">\n'
            b'  <cacheSource type="worksheet">'
            b'<worksheetSource ref="A1:B2" sheet="Sheet1"/></cacheSource>\n'
            b'  <cacheFields count="2">\n'
            b'    <cacheField name="ColA"/><cacheField name="ColB"/>\n'
            b'  </cacheFields>\n'
            b"</pivotCacheDefinition>"
        )
        records_xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<pivotCacheRecords '
            b'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'
        )
        table_xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>\n'
            b'<pivotTableDefinition '
            b'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            b'name="PivotTable1" cacheId="1">\n'
            b'  <location ref="C1:E5" firstHeaderRow="1" firstDataRow="2" firstDataCol="1"/>\n'
            b'  <pivotFields count="2"><pivotField axis="axisRow"/>'
            b'<pivotField dataField="1"/></pivotFields>\n'
            b"</pivotTableDefinition>"
        )
        z.writestr("xl/pivotCaches/pivotCacheDefinition1.xml", cache_xml)
        z.writestr("xl/pivotCaches/pivotCacheRecords1.xml", records_xml)
        z.writestr("xl/pivotTables/pivotTable1.xml", table_xml)

    raw_zip = buf.getvalue()

    # 1. Read
    wb = read_xlsx(raw_zip)
    assert "pivots" in wb.extra
    pivots: PivotContainer = wb.extra["pivots"]
    assert len(pivots.caches) == 1
    assert pivots.caches[0].cache_id == 1
    assert pivots.caches[0].sources[0].sheet_name == "Sheet1"
    assert pivots.caches[0].sources[0].original_ref == "A1:B2"

    assert len(pivots.tables) == 1
    assert pivots.tables[0].name == "PivotTable1"
    assert pivots.tables[0].cache_id == 1

    # 2. Write without mutations: verify all parts carried
    out_bytes = write_xlsx(wb, source_opc=raw_zip)
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as z_out:
        names = z_out.namelist()
        assert "xl/pivotCaches/pivotCacheDefinition1.xml" in names
        assert "xl/pivotCaches/pivotCacheRecords1.xml" in names
        assert "xl/pivotTables/pivotTable1.xml" in names

        # Unmodified bytes match
        assert z_out.read("xl/pivotCaches/pivotCacheDefinition1.xml") == cache_xml
        assert z_out.read("xl/pivotCaches/pivotCacheRecords1.xml") == records_xml
        assert z_out.read("xl/pivotTables/pivotTable1.xml") == table_xml

        # Check relationships in workbook.xml.rels
        wb_rels_xml = z_out.read("xl/_rels/workbook.xml.rels").decode()
        assert "pivotCacheDefinition" in wb_rels_xml
        assert "pivotCaches/pivotCacheDefinition1.xml" in wb_rels_xml

        # Check relationships in sheet1.xml.rels
        sheet_rels_xml = z_out.read("xl/worksheets/_rels/sheet1.xml.rels").decode()
        assert "pivotTable" in sheet_rels_xml
        assert "../pivotTables/pivotTable1.xml" in sheet_rels_xml


def test_pivot_cache_refresh_on_edit():
    """Verify editing a cell inside source range sets refreshOnLoad='1'."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        types_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\n'
            '  <Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
            '  <Override PartName="/xl/pivotCaches/pivotCacheDefinition1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml"/>\n'
            '  <Override PartName="/xl/pivotTables/pivotTable1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"/>\n'
            "</Types>"
        )
        z.writestr("[Content_Types].xml", types_xml)
        rel_office = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
        )
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{rel_office}" Target="xl/workbook.xml"/>\n'
            "</Relationships>"
        )
        z.writestr("_rels/.rels", root_rels)
        wb_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
            '  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>\n'
            '  <pivotCaches><pivotCache cacheId="1" r:id="rIdCache1"/></pivotCaches>\n'
            "</workbook>"
        )
        z.writestr("xl/workbook.xml", wb_xml)
        rel_cache = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheDefinition"
        )
        rel_ws = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
        wb_rels = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{rel_ws}" Target="worksheets/sheet1.xml"/>\n'
            f'  <Relationship Id="rIdCache1" Type="{rel_cache}" '
            'Target="pivotCaches/pivotCacheDefinition1.xml"/>\n'
            "</Relationships>"
        )
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        ws_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n'
            '  <sheetData><row r="1"><c r="A1"><v>1</v></c></row></sheetData>\n'
            "</worksheet>"
        )
        z.writestr("xl/worksheets/sheet1.xml", ws_xml)
        rel_pt = (
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotTable"
        )
        ws_rels = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rIdPivot1" Type="{rel_pt}" '
            'Target="../pivotTables/pivotTable1.xml"/>\n'
            "</Relationships>"
        )
        z.writestr("xl/worksheets/_rels/sheet1.xml.rels", ws_rels)
        cache_xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>\n'
            b'<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n'
            b'  <cacheSource type="worksheet">'
            b'<worksheetSource ref="A1:B2" sheet="Sheet1"/></cacheSource>\n'
            b"</pivotCacheDefinition>"
        )
        table_xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>\n'
            b'<pivotTableDefinition '
            b'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            b'name="PivotTable1" cacheId="1">\n'
            b'  <location ref="C1:E5"/>\n'
            b"</pivotTableDefinition>"
        )
        z.writestr("xl/pivotCaches/pivotCacheDefinition1.xml", cache_xml)
        z.writestr("xl/pivotTables/pivotTable1.xml", table_xml)

    wb = read_xlsx(buf.getvalue())
    pivots: PivotContainer = wb.extra["pivots"]
    assert pivots.caches[0].refresh is False

    # Edit cell inside A1:B2 (e.g. A1 is r=0, c=0)
    pivots.notify_cell_changed("Sheet1", 0, 0)
    assert pivots.caches[0].refresh is True

    # Serialize
    out = write_xlsx(wb, source_opc=buf.getvalue())
    with zipfile.ZipFile(io.BytesIO(out)) as z_out:
        updated_cache = z_out.read("xl/pivotCaches/pivotCacheDefinition1.xml")
        root = ET.fromstring(updated_cache)
        assert root.attrib.get("refreshOnLoad") == "1"


def test_pivot_dialog_lifecycle(qapp):
    """Test PivotTableWizardDialog initialization, validation, and execution."""
    wb, sheet = create_sample_sales_workbook()
    dlg = PivotTableWizardDialog(
        workbook=wb,
        initial_sheet_name=sheet.name,
        initial_range=(0, 0, 7, 3),
    )

    # Check that comboboxes populated with headers
    assert dlg.combo_row.count() == 4
    assert dlg.combo_row.itemText(0) == "Region"
    assert dlg.combo_data.count() == 4

    # Select fields
    dlg.combo_row.setCurrentIndex(0)  # Region
    dlg.combo_col.setCurrentIndex(1)  # (无) is 0, Product is 1
    dlg.combo_data.setCurrentIndex(3)  # Sales
    dlg.radio_new_sheet.setChecked(True)

    # Trigger finish
    dlg._on_finish()
    assert dlg.created_sheet is not None
    assert len(wb) == 2


def test_ledger_window_action_registration(qapp):
    """Verify that ledger_window registers pivot actions properly."""
    from atboffice.ui.shell.ledger_window import LedgerWindow

    win = LedgerWindow()
    # Check that action handlers exist in registry
    assert "data_pivottable" in win.action_registry._handlers
    assert "pivotTable" in win.action_registry._handlers
    win.close()
