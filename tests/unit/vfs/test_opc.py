import io
import zipfile
from pathlib import Path

import pytest

from atboffice.vfs.opc import PackageWriter, SourcePackage

NS_REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
NS_REL_WS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
NS_REL_VBA = "http://schemas.microsoft.com/office/2006/relationships/vbaProject"
CT_SHEET_MAIN = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
)
CT_WORKSHEET = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
)
CT_VBA = "application/vnd.ms-office.vbaProject"
CT_RELS = "application/vnd.openxmlformats-package.relationships+xml"


def make_sample_xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            f'  <Default Extension="rels" ContentType="{CT_RELS}"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            f'  <Default Extension="bin" ContentType="{CT_VBA}"/>\n'
            f'  <Override PartName="/xl/workbook.xml" ContentType="{CT_SHEET_MAIN}"/>\n'
            f'  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="{CT_WORKSHEET}"/>\n'
            '</Types>'
        )
        zf.writestr("[Content_Types].xml", content_types.encode("utf-8"))

        # _rels/.rels
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{NS_REL_DOC}" Target="xl/workbook.xml"/>\n'
            '</Relationships>'
        )
        zf.writestr("_rels/.rels", root_rels.encode("utf-8"))

        # xl/workbook.xml
        wb = '<workbook><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
        zf.writestr("xl/workbook.xml", wb.encode("utf-8"))

        # xl/_rels/workbook.xml.rels
        wb_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{NS_REL_WS}" Target="worksheets/sheet1.xml"/>\n'
            f'  <Relationship Id="rId2" Type="{NS_REL_VBA}" Target="vbaProject.bin"/>\n'
            '</Relationships>'
        )
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels.encode("utf-8"))

        # xl/worksheets/sheet1.xml
        ws = (
            '<worksheet><sheetData><row r="1">'
            '<c r="A1"><v>100</v></c>'
            '</row></sheetData></worksheet>'
        )
        zf.writestr("xl/worksheets/sheet1.xml", ws.encode("utf-8"))

        # xl/vbaProject.bin (binary macro part to test byte-for-byte carry)
        vba_raw = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1\x00\x01\x02\x03\xFF\xFE\x00\x01"
        zf.writestr("xl/vbaProject.bin", vba_raw)

    return buf.getvalue()


def test_source_package_inspection(tmp_path: Path):
    raw_data = make_sample_xlsx_bytes()
    file_path = tmp_path / "test.xlsx"
    file_path.write_bytes(raw_data)

    pkg = SourcePackage.open(file_path)
    assert pkg.has_part("xl/workbook.xml")
    assert pkg.has_part("/xl/workbook.xml")  # normalized with leading slash
    assert pkg.has_part("xl/vbaProject.bin")
    assert not pkg.has_part("nonexistent.xml")

    # Content types
    assert pkg.get_content_type("xl/workbook.xml") == CT_SHEET_MAIN
    assert pkg.get_content_type("xl/vbaProject.bin") == CT_VBA

    # Part reading
    assert b"100" in pkg.read_part("xl/worksheets/sheet1.xml")
    expected_vba = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1\x00\x01\x02\x03\xFF\xFE\x00\x01"
    assert pkg.read_part("xl/vbaProject.bin") == expected_vba

    # Relationships
    pkg_rels = pkg.get_relationships("")
    assert len(pkg_rels) == 1
    assert pkg_rels[0].target == "xl/workbook.xml"

    wb_rels = pkg.get_relationships("xl/workbook.xml")
    assert len(wb_rels) == 2
    targets = {r.target for r in wb_rels}
    assert "worksheets/sheet1.xml" in targets
    assert "vbaProject.bin" in targets


def test_package_writer_byte_for_byte_carry(tmp_path: Path):
    raw_data = make_sample_xlsx_bytes()
    pkg = SourcePackage.from_bytes(raw_data)

    writer = PackageWriter(source_package=pkg)
    # Modify worksheet content
    modified_ws = (
        b'<worksheet><sheetData><row r="1">'
        b'<c r="A1"><v>999</v></c>'
        b'</row></sheetData></worksheet>'
    )
    writer.replace_part("xl/worksheets/sheet1.xml", modified_ws)

    # Save to new file atomically
    target_path = tmp_path / "output.xlsx"
    writer.save(target_path)
    assert target_path.exists()

    # Verify output package
    saved_pkg = SourcePackage.open(target_path)
    # 1. Modified part has new content
    assert saved_pkg.read_part("xl/worksheets/sheet1.xml") == modified_ws
    # 2. Unmodified binary part is byte-for-byte identical
    expected_vba = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1\x00\x01\x02\x03\xFF\xFE\x00\x01"
    assert saved_pkg.read_part("xl/vbaProject.bin") == expected_vba
    # 3. Content types intact
    assert saved_pkg.get_content_type("xl/vbaProject.bin") == CT_VBA


def test_package_writer_add_and_delete_parts():
    raw_data = make_sample_xlsx_bytes()
    pkg = SourcePackage.from_bytes(raw_data)

    writer = PackageWriter(source_package=pkg)
    writer.add_part("xl/custom.xml", b"<custom/>", content_type="application/xml")
    writer.delete_part("xl/vbaProject.bin")

    out_bytes = writer.to_bytes()
    saved_pkg = SourcePackage.from_bytes(out_bytes)

    assert saved_pkg.has_part("xl/custom.xml")
    assert saved_pkg.read_part("xl/custom.xml") == b"<custom/>"
    assert not saved_pkg.has_part("xl/vbaProject.bin")


def test_source_package_invalid_file(tmp_path: Path):
    corrupt_file = tmp_path / "corrupt.xlsx"
    corrupt_file.write_bytes(b"not a zip file at all")
    with pytest.raises(ValueError, match="Not a valid ZIP/OPC package"):
        SourcePackage.open(corrupt_file)
