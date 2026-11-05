"""Tests for XML Spreadsheet 2003 (SpreadsheetML) I/O and parity."""

from __future__ import annotations

import datetime

from atboffice.modules.spreadsheet.calc.errors import DIV0, NA, VALUE, ExcelError
from atboffice.modules.spreadsheet.io.xmlss_io import (
    from_r1c1,
    read_xmlss,
    read_xmlss_workbook,
    to_r1c1,
    write_xmlss,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellComment,
    CellData,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


def test_r1c1_conversions_advanced():
    # Relative from C3 (row=2, col=2)
    assert from_r1c1("R[-1]C[-1]", 2, 2) == "B2"
    assert from_r1c1("R1C1", 2, 2) == "$A$1"
    assert from_r1c1("RC[1]", 2, 2) == "D3"
    assert from_r1c1("=SUM(R[-2]C:R[-1]C)", 2, 2) == "SUM(C1:C2)"

    # Row ranges & Col ranges
    assert from_r1c1("R1:R5", 2, 2) == "$1:$5"
    assert from_r1c1("C1:C3", 2, 2) == "$A:$C"

    # Cross-sheet references
    assert from_r1c1("Sheet2!R1C1", 2, 2) == "Sheet2!$A$1"
    assert from_r1c1("'Quarter 1'!R[-1]C[-1]", 2, 2) == "'Quarter 1'!B2"

    # Preserving string literals
    f_str = '="Total: " & R[-1]C'
    assert from_r1c1(f_str, 2, 2) == '"Total: " & C2'

    # to_r1c1 conversions
    assert to_r1c1("B2", 2, 2) == "=R[-1]C[-1]"
    assert to_r1c1("$A$1", 2, 2) == "=R1C1"
    assert to_r1c1("SUM(C1:C2)", 2, 2) == "=SUM(R[-2]C:R[-1]C)"
    assert to_r1c1("Sheet2!$A$1", 2, 2) == "=Sheet2!R1C1"
    assert to_r1c1("'Quarter 1'!B2", 2, 2) == "='Quarter 1'!R[-1]C[-1]"
    assert to_r1c1("A:B", 2, 2) == "=C[-2]:C[-1]"
    assert to_r1c1("1:5", 2, 2) == "=R[-2]:R[2]"


def test_data_types_reading():
    xml_data = """<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="TypesTest">
  <Table>
   <Row>
    <Cell><Data ss:Type="String">Sample Text</Data></Cell>
    <Cell><Data ss:Type="Number">12345</Data></Cell>
    <Cell><Data ss:Type="Number">67.89</Data></Cell>
    <Cell><Data ss:Type="Boolean">1</Data></Cell>
    <Cell><Data ss:Type="Boolean">0</Data></Cell>
    <Cell><Data ss:Type="Error">#DIV/0!</Data></Cell>
    <Cell><Data ss:Type="DateTime">2003-05-12T10:30:00.000</Data></Cell>
   </Row>
  </Table>
 </Worksheet>
</Workbook>"""
    model = read_xmlss(xml_data)
    assert model.get_cell_value(0, 0) == "Sample Text"
    assert model.get_cell_value(0, 1) == 12345
    assert model.get_cell_value(0, 2) == 67.89
    assert model.get_cell_value(0, 3) is True
    assert model.get_cell_value(0, 4) is False
    err_val = model.get_cell_value(0, 5)
    assert err_val == "#DIV/0!" or (isinstance(err_val, ExcelError) and err_val == DIV0)
    # DateTime check
    dt_val = model.get_cell_value(0, 6)
    assert dt_val is not None
    # Serial or datetime should be close to May 12 2003
    if isinstance(dt_val, (int, float)):
        assert dt_val > 37000  # year 2003 is > 37000 in Excel serial


def test_multi_worksheet_read_and_active_sheet():
    xml_data = """<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <ActiveSheet>1</ActiveSheet>
 </ExcelWorkbook>
 <Worksheet ss:Name="FirstSheet">
  <Table>
   <Row><Cell><Data ss:Type="String">Page 1</Data></Cell></Row>
  </Table>
 </Worksheet>
 <Worksheet ss:Name="SecondSheet">
  <Table>
   <Row><Cell><Data ss:Type="String">Active Page</Data></Cell></Row>
  </Table>
  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <Selected/>
  </WorksheetOptions>
 </Worksheet>
 <Worksheet ss:Name="EmptySheet">
  <Table/>
 </Worksheet>
</Workbook>"""
    wb = read_xmlss_workbook(xml_data)
    assert isinstance(wb, WorkbookModel)
    assert len(wb.sheets) == 3
    assert wb.sheets[0].name == "FirstSheet"
    assert wb.sheets[1].name == "SecondSheet"
    assert wb.sheets[2].name == "EmptySheet"
    assert wb.active_sheet_index == 1
    assert wb.sheets[0].get_cell_value(0, 0) == "Page 1"
    assert wb.sheets[1].get_cell_value(0, 0) == "Active Page"
    assert len(wb.sheets[2].cells) == 0


def test_multi_worksheet_write():
    s1 = SheetDataModel(name="Summary")
    s1.set_cell(0, 0, CellData(value="Summary Data"))
    s2 = SheetDataModel(name="Details")
    s2.set_cell(0, 0, CellData(value="Detail 1"))
    s2.set_cell(1, 0, CellData(value=100))
    s3 = SheetDataModel(name="Blank")

    wb = WorkbookModel(sheets=[s1, s2, s3])
    wb.set_active_sheet_index(1)

    xml_out = write_xmlss(wb)
    assert 'ss:Name="Summary"' in xml_out
    assert 'ss:Name="Details"' in xml_out
    assert 'ss:Name="Blank"' in xml_out
    assert "<ActiveSheet>1</ActiveSheet>" in xml_out

    # Re-read
    wb_loaded = read_xmlss_workbook(xml_out)
    assert len(wb_loaded.sheets) == 3
    assert wb_loaded.sheets[0].name == "Summary"
    assert wb_loaded.sheets[1].name == "Details"
    assert wb_loaded.sheets[2].name == "Blank"
    assert wb_loaded.active_sheet_index == 1
    assert wb_loaded.sheets[0].get_cell_value(0, 0) == "Summary Data"
    assert wb_loaded.sheets[1].get_cell_value(0, 0) == "Detail 1"
    assert wb_loaded.sheets[1].get_cell_value(1, 0) == 100


def test_geometry_row_col_merges_fidelity():
    sheet = SheetDataModel(name="Layout")
    # Custom widths
    sheet.geometry.set_col_width(0, 120)
    sheet.geometry.set_col_width(1, 200)
    sheet.geometry.hidden_cols.add(2)

    # Custom row heights
    sheet.geometry.set_row_height(0, 40)
    sheet.geometry.hidden_rows.add(1)

    # Merges
    sheet.add_merge(0, 0, 0, 1)  # Merge across A1:B1
    sheet.set_cell(0, 0, CellData(value="Merged Header"))

    xml_out = write_xmlss(sheet)
    assert 'ss:MergeAcross="1"' in xml_out

    # Re-read
    loaded_sheet = read_xmlss(xml_out)
    assert loaded_sheet.get_cell_value(0, 0) == "Merged Header"
    assert loaded_sheet.is_merged(0, 0) is True
    assert loaded_sheet.get_merge_range(0, 0) == (0, 0, 0, 1)
    assert loaded_sheet.geometry.col_size(0) == 120 or abs(loaded_sheet.geometry.col_size(0) - 120) <= 2
    assert loaded_sheet.geometry.col_size(1) == 200 or abs(loaded_sheet.geometry.col_size(1) - 200) <= 2
    assert loaded_sheet.geometry.row_size(0) == 40 or abs(loaded_sheet.geometry.row_size(0) - 40) <= 2


def test_styles_borders_fills_fonts_fidelity():
    sheet = SheetDataModel(name="Styles")
    c = CellData(
        value="Styled Cell",
        bold=True,
        italic=True,
        underline=True,
        underline_style="single",
        strike=True,
        vert_align="superscript",
        fg_color="#FF0000",
        bg_color="#FFFF00",
        pattern="Solid",
        align_h="center",
        align_v="center",
        wrap_text=True,
        format_code="$#,##0.00",
        border_top=BorderStyle(style="thin", color="#000000"),
        border_bottom=BorderStyle(style="thick", color="#0000FF"),
    )
    sheet.set_cell(0, 0, c)

    xml_out = write_xmlss(sheet)
    assert 'ss:Bold="1"' in xml_out
    assert 'ss:Italic="1"' in xml_out
    assert 'ss:Underline="Single"' in xml_out
    assert 'ss:StrikeThrough="1"' in xml_out
    assert 'ss:VerticalAlign="Superscript"' in xml_out
    assert 'ss:Color="#FF0000"' in xml_out
    assert 'ss:Pattern="Solid"' in xml_out
    assert 'ss:Horizontal="Center"' in xml_out
    assert 'ss:Vertical="Center"' in xml_out
    assert 'ss:WrapText="1"' in xml_out

    loaded = read_xmlss(xml_out)
    loaded_cell = loaded.get_cell(0, 0)
    assert loaded_cell.bold is True
    assert loaded_cell.italic is True
    assert loaded_cell.underline is True
    assert loaded_cell.strike is True
    assert loaded_cell.vert_align == "superscript"
    assert loaded_cell.fg_color == "#FF0000"
    assert loaded_cell.bg_color == "#FFFF00"
    assert loaded_cell.align_h == "center"
    assert loaded_cell.align_v == "center"
    assert loaded_cell.wrap_text is True
    assert loaded_cell.border_top is not None
    assert loaded_cell.border_bottom is not None
    assert loaded_cell.border_bottom.style == "thick"


def test_cell_comments_roundtrip():
    sheet = SheetDataModel(name="Comments")
    sheet.set_cell(0, 0, CellData(value="With Comment"))
    sheet.set_comment(0, 0, text="Important note", author="Alice", visible=True)

    xml_out = write_xmlss(sheet)
    assert "Important note" in xml_out
    assert 'ss:Author="Alice"' in xml_out

    loaded = read_xmlss(xml_out)
    cm = loaded.get_comment(0, 0)
    assert cm is not None
    assert cm.text == "Important note"
    assert cm.author == "Alice"
    assert cm.visible is True


def test_round_trip_comprehensive():
    s1 = SheetDataModel(name="Financials")
    s1.set_cell(0, 0, CellData(value="Revenue", bold=True))
    s1.set_cell(0, 1, CellData(value=1000.50, format_code="$#,##0.00"))
    s1.set_cell(1, 0, CellData(value="Expenses", bold=True))
    s1.set_cell(1, 1, CellData(value=400.25, format_code="$#,##0.00"))
    s1.set_cell(2, 0, CellData(value="Net Profit", bold=True))
    s1.set_cell(2, 1, CellData(value=600.25, formula="B1-B2"))
    s1.add_merge(3, 0, 3, 1)
    s1.set_cell(3, 0, CellData(value="Confidential Report", italic=True, align_h="center"))

    s2 = SheetDataModel(name="Metadata")
    s2.set_cell(0, 0, CellData(value="IsAudited"))
    s2.set_cell(0, 1, CellData(value=True))
    s2.set_cell(1, 0, CellData(value="ErrorStatus"))
    s2.set_cell(1, 1, CellData(value=DIV0))

    wb = WorkbookModel(sheets=[s1, s2])
    wb.set_active_sheet_index(0)

    xml_text = write_xmlss(wb)
    wb2 = read_xmlss_workbook(xml_text)

    assert len(wb2.sheets) == 2
    assert wb2.active_sheet_index == 0

    fin = wb2.sheets[0]
    assert fin.get_cell_value(0, 0) == "Revenue"
    assert fin.get_cell(0, 0).bold is True
    assert fin.get_cell_value(0, 1) == 1000.50
    assert fin.get_cell_value(1, 1) == 400.25
    assert fin.get_cell_value(2, 0) == "Net Profit"
    assert fin.get_cell(2, 1).formula == "B1-B2"
    assert fin.is_merged(3, 0) is True

    meta = wb2.sheets[1]
    assert meta.get_cell_value(0, 1) is True
    assert meta.get_cell_value(1, 1) == "#DIV/0!" or meta.get_cell_value(1, 1) == DIV0
