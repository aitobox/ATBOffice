import xml.etree.ElementTree as ET

import pytest

from atboffice.vfs.order import enforce_schema_order


def test_worksheet_schema_ordering():
    # Intentionally out of order: mergeCells before sheetData, dimension last
    raw = "<worksheet><mergeCells/><sheetData/><dimension ref='A1'/></worksheet>"
    root = ET.fromstring(raw)
    enforce_schema_order(root, "spreadsheetml_worksheet")
    tags = [elem.tag for elem in root]
    assert tags == ["dimension", "sheetData", "mergeCells"]


def test_worksheet_schema_ordering_with_namespace():
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    raw = (
        f'<worksheet xmlns="{ns}">'
        f'<mergeCells xmlns="{ns}"/>'
        f'<cols xmlns="{ns}"/>'
        f'<sheetData xmlns="{ns}"/>'
        f'<sheetPr xmlns="{ns}"/>'
        f'</worksheet>'
    )
    root = ET.fromstring(raw)
    enforce_schema_order(root, "spreadsheetml_worksheet")
    expected = [
        f"{{{ns}}}sheetPr",
        f"{{{ns}}}cols",
        f"{{{ns}}}sheetData",
        f"{{{ns}}}mergeCells",
    ]
    assert [elem.tag for elem in root] == expected


def test_workbook_schema_ordering():
    raw = "<workbook><calcPr/><sheets/><fileVersion/></workbook>"
    root = ET.fromstring(raw)
    enforce_schema_order(root, "spreadsheetml_workbook")
    assert [elem.tag for elem in root] == ["fileVersion", "sheets", "calcPr"]


def test_styles_schema_ordering():
    raw = "<styleSheet><cellXfs/><fonts/><numFmts/><borders/></styleSheet>"
    root = ET.fromstring(raw)
    enforce_schema_order(root, "spreadsheetml_styles")
    assert [elem.tag for elem in root] == ["numFmts", "fonts", "borders", "cellXfs"]


def test_unknown_elements_preserved_at_end():
    raw = "<worksheet><customExt/><sheetData/><dimension ref='A1'/></worksheet>"
    root = ET.fromstring(raw)
    enforce_schema_order(root, "spreadsheetml_worksheet")
    assert [elem.tag for elem in root] == ["dimension", "sheetData", "customExt"]


def test_invalid_schema_family_raises_key_error():
    root = ET.fromstring("<root><child/></root>")
    with pytest.raises(KeyError):
        enforce_schema_order(root, "non_existent_schema")
