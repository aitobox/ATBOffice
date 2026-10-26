"""Unit and GUI tests for CSV / TXT import wizard and XML Spreadsheet 2003 I/O."""

import pytest
from atboffice.modules.spreadsheet.io.csv_io import (
    convert_cell_value,
    decode_bytes,
    export_csv,
    guess_fixed_breaks,
    parse_delimited,
    parse_fixed_width,
    populate_sheet,
    sniff_delimiter,
)
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def test_decode_bytes_bom():
    # UTF-8 BOM
    utf8_data = b"\xef\xbb\xbfHello,World\n1,2"
    text, enc = decode_bytes(utf8_data)
    assert enc == "utf-8"
    assert text.startswith("Hello,World")
    assert not text.startswith("\ufeff")

    # UTF-16LE BOM
    utf16le_data = "\ufeffName,Score\nAlice,100".encode("utf-16le")
    text, enc = decode_bytes(utf16le_data)
    assert enc == "utf-16le"
    assert "Alice,100" in text

    # UTF-16BE BOM
    utf16be_data = "\ufeffName,Score\nBob,90".encode("utf-16be")
    text, enc = decode_bytes(utf16be_data)
    assert enc == "utf-16be"
    assert "Bob,90" in text


def test_decode_bytes_utf16_no_bom():
    raw_le = "ID,Value\n1,10\n2,20\n3,30\n".encode("utf-16le")
    text, enc = decode_bytes(raw_le)
    assert enc == "utf-16le"
    assert "ID,Value" in text


def test_decode_bytes_gb18030():
    chinese_text = "姓名,部门,薪资\n张三,研发部,15000\n李四,市场部,12000\n"
    gb_data = chinese_text.encode("gb18030")
    text, enc = decode_bytes(gb_data)
    assert enc == "gb18030"
    assert "张三" in text
    assert "研发部" in text


def test_decode_bytes_windows1252():
    # Byte 0x80 is Euro sign in Windows-1252 (not valid UTF-8)
    w1252_data = b"Price\n\x80100\n\x80200"
    text, enc = decode_bytes(w1252_data)
    assert enc == "windows-1252"
    assert "100" in text


def test_decode_bytes_explicit():
    sample = "Col1,Col2\nA,B".encode("utf-8")
    text, enc = decode_bytes(sample, encoding="utf-8")
    assert enc == "utf-8"
    assert text == "Col1,Col2\nA,B"


def test_sniff_delimiter():
    csv_text = "A,B,C\n1,2,3\n4,5,6"
    assert sniff_delimiter(csv_text) == ","

    tsv_text = "A\tB\tC\n1\t2\t3\n4\t5\t6"
    assert sniff_delimiter(tsv_text) == "\t"

    semicolon_text = "A;B;C\n1;2;3\n4;5;6"
    assert sniff_delimiter(semicolon_text) == ";"

    pipe_text = "A|B|C\n1|2|3\n4|5|6"
    assert sniff_delimiter(pipe_text) == "|"


def test_guess_fixed_breaks():
    lines = [
        "1001   Alice Smith     Engineering   ",
        "1002   Bob Jones       Marketing     ",
        "1003   Charlie Brown   Sales         ",
    ]
    text = "\n".join(lines)
    breaks = guess_fixed_breaks(text)
    assert len(breaks) >= 2
    assert 4 in breaks or 7 in breaks


def test_parse_delimited_standard():
    text = 'Name,Age,City\n"Smith, John",30,New York\n"Jane ""Doe""",25,"Los\nAngeles"'
    rows = parse_delimited(text)
    assert len(rows) == 3
    assert rows[0] == ["Name", "Age", "City"]
    assert rows[1] == ["Smith, John", "30", "New York"]
    assert rows[2] == ['Jane "Doe"', "25", "Los\nAngeles"]


def test_parse_delimited_merge_consecutive():
    text = "Col1   Col2   Col3\nA    B    C\n"
    rows = parse_delimited(text, delims=" ", merge=True)
    assert len(rows) == 2
    assert rows[0] == ["Col1", "Col2", "Col3"]
    assert rows[1] == ["A", "B", "C"]


def test_parse_fixed_width():
    lines = [
        "1001Alice Smith    Finance",
        "1002Bob Jones      Marketing",
    ]
    text = "\n".join(lines)
    rows = parse_fixed_width(text, breaks=[4, 19])
    assert len(rows) == 2
    assert rows[0] == ["1001", "Alice Smith", "Finance"]
    assert rows[1] == ["1002", "Bob Jones", "Marketing"]


def test_convert_cell_value():
    assert convert_cell_value("") is None
    assert convert_cell_value("   ") is None
    assert convert_cell_value("TRUE") is True
    assert convert_cell_value("false") is False
    assert convert_cell_value("123") == 123
    assert convert_cell_value("-45.67") == -45.67
    assert convert_cell_value("1.5e3") == 1500.0
    assert convert_cell_value("25%") == 0.25
    assert convert_cell_value("1,234.50") == 1234.50
    assert convert_cell_value("Hello World") == "Hello World"
    assert convert_cell_value("01234", col_type="Text") == "01234"


def test_populate_sheet_and_export_csv():
    model = SheetDataModel()
    rows = [
        ["Item", "Qty", "Price"],
        ["Widget, Large", "10", "12.5"],
        ["Gadget", "5", "100"],
    ]
    populate_sheet(model, rows)
    assert model.get_cell_value(0, 0) == "Item"
    assert model.get_cell_value(1, 0) == "Widget, Large"
    assert model.get_cell_value(1, 1) == 10
    assert model.get_cell_value(1, 2) == 12.5

    exported = export_csv(model)
    assert '"Widget, Large",10,12.5' in exported
    assert "Gadget,5,100" in exported


from atboffice.modules.spreadsheet.io.xmlss_io import (
    from_r1c1,
    read_xmlss,
    to_r1c1,
    write_xmlss,
)


def test_r1c1_conversions():
    # Relative from (2, 2) which is C3
    assert from_r1c1("R[-1]C[-1]", 2, 2) == "B2"
    assert from_r1c1("R1C1", 2, 2) == "$A$1"
    assert from_r1c1("RC[1]", 2, 2) == "D3"
    assert from_r1c1("=SUM(R[-2]C:R[-1]C)", 2, 2) == "SUM(C1:C2)"

    # to_r1c1 from C3 (2, 2)
    assert to_r1c1("B2", 2, 2) == "=R[-1]C[-1]"
    assert to_r1c1("$A$1", 2, 2) == "=R1C1"
    assert to_r1c1("SUM(C1:C2)", 2, 2) == "=SUM(R[-2]C:R[-1]C)"


def test_xmlss_read_write_roundtrip():
    xml_data = """<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Styles>
  <Style ss:ID="Default" ss:Name="Normal">
   <Alignment ss:Vertical="Bottom"/>
   <Font ss:FontName="Arial" ss:Size="10"/>
  </Style>
  <Style ss:ID="sBold">
   <Font ss:Bold="1" ss:FontName="Arial" ss:Size="10"/>
  </Style>
 </Styles>
 <Worksheet ss:Name="Sheet1">
  <Table>
   <Row>
    <Cell ss:StyleID="sBold"><Data ss:Type="String">Header 1</Data></Cell>
    <Cell ss:MergeAcross="1" ss:StyleID="sBold"><Data ss:Type="String">Merged</Data></Cell>
   </Row>
   <Row>
    <Cell><Data ss:Type="Number">10</Data></Cell>
    <Cell><Data ss:Type="Number">20</Data></Cell>
    <Cell ss:Formula="=SUM(RC[-2]:RC[-1])"><Data ss:Type="Number">30</Data></Cell>
   </Row>
  </Table>
 </Worksheet>
</Workbook>"""
    model = read_xmlss(xml_data)
    assert model.get_cell_value(0, 0) == "Header 1"
    cell_0_0 = model.get_cell(0, 0)
    assert cell_0_0.bold is True

    # Check merge
    assert model.is_merged(0, 1) is True
    assert model.get_merge_range(0, 1) == (0, 1, 0, 2)

    assert model.get_cell_value(1, 0) == 10
    assert model.get_cell_value(1, 1) == 20
    assert model.get_cell(1, 2).formula == "SUM(A2:B2)"

    # Export to XMLSS
    out_xml = write_xmlss(model, sheet_name="Sheet1")
    assert "<Workbook" in out_xml
    assert "Header 1" in out_xml
    assert 'ss:MergeAcross="1"' in out_xml

    # Re-read exported XMLSS
    model2 = read_xmlss(out_xml)
    assert model2.get_cell_value(0, 0) == "Header 1"
    assert model2.get_cell(0, 0).bold is True
    assert model2.get_merge_range(0, 1) == (0, 1, 0, 2)
    assert model2.get_cell_value(1, 0) == 10
    assert model2.get_cell(1, 2).formula == "SUM(A2:B2)"
