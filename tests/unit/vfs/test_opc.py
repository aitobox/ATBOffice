import io
import zipfile
from pathlib import Path
import pytest

from atboffice.vfs.opc import SourcePackage, PackageWriter, Relationship


def make_sample_xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        )
        zf.writestr("[Content_Types].xml", content_types.encode("utf-8"))

        # _rels/.rels
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        )
        zf.writestr("_rels/.rels", root_rels.encode("utf-8"))

        # xl/workbook.xml
        wb = '<workbook><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
        zf.writestr("xl/workbook.xml", wb.encode("utf-8"))

        # xl/_rels/workbook.xml.rels
        wb_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/>'
            '</Relationships>'
        )
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels.encode("utf-8"))

        # xl/worksheets/sheet1.xml
        ws = '<worksheet><sheetData><row r="1"><c r="A1"><v>100</v></c></row></sheetData></worksheet>'
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
    assert pkg.get_content_type("xl/workbook.xml") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
    assert pkg.get_content_type("xl/vbaProject.bin") == "application/vnd.ms-office.vbaProject"

    # Part reading
    assert b"100" in pkg.read_part("xl/worksheets/sheet1.xml")
    assert pkg.read_part("xl/vbaProject.bin") == b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1\x00\x01\x02\x03\xFF\xFE\x00\x01"

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
    modified_ws = '<worksheet><sheetData><row r="1"><c r="A1"><v>999</v></c></row></sheetData></worksheet>'.encode("utf-8")
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
    assert saved_pkg.read_part("xl/vbaProject.bin") == b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1\x00\x01\x02\x03\xFF\xFE\x00\x01"
    # 3. Content types intact
    assert saved_pkg.get_content_type("xl/vbaProject.bin") == "application/vnd.ms-office.vbaProject"


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
