"""Tests for Lossless OPC Container Engine & Part-level Byte Preservation.

Tests ECMA-376 Open Packaging Conventions (OPC) relationship resolution,
cycle-safe subtree traversal, exact ContentTypes, and byte-for-byte stream preservation.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from atboffice.vfs.opc import (
    PackageWriter,
    SourcePackage,
    get_owner_from_rels_path,
    get_rels_path,
    normalize_part_name,
    preserve_unmodified_parts,
    relative_part_uri,
    resolve_part_uri,
)

# Standard OOXML Relationship & Content Types
NS_REL_DOC = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
NS_REL_WS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
)
NS_REL_DRAWING = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
)
NS_REL_IMAGE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
)
NS_REL_VBA = "http://schemas.microsoft.com/office/2006/relationships/vbaProject"
NS_REL_HYPERLINK = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
)

CT_SHEET_MAIN = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
)
CT_WORKSHEET = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
)
CT_DRAWING = "application/vnd.openxmlformats-officedocument.drawing+xml"
CT_PNG = "image/png"
CT_VBA = "application/vnd.ms-office.vbaProject"
CT_RELS = "application/vnd.openxmlformats-package.relationships+xml"
CT_CUSTOM = "application/vnd.openxmlformats-officedocument.customXmlProperties+xml"


def make_complex_package_bytes() -> tuple[bytes, dict[str, str]]:
    """Build a rich OPC package with nested relationships, macros, and images."""
    buf = io.BytesIO()
    hashes: dict[str, str] = {}

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            f'  <Default Extension="rels" ContentType="{CT_RELS}"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            f'  <Default Extension="bin" ContentType="{CT_VBA}"/>\n'
            f'  <Default Extension="png" ContentType="{CT_PNG}"/>\n'
            f'  <Override PartName="/xl/workbook.xml" ContentType="{CT_SHEET_MAIN}"/>\n'
            f'  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="{CT_WORKSHEET}"/>\n'
            f'  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="{CT_WORKSHEET}"/>\n'
            f'  <Override PartName="/xl/drawings/drawing1.xml" ContentType="{CT_DRAWING}"/>\n'
            f'  <Override PartName="/customXml/item1.xml" ContentType="{CT_CUSTOM}"/>\n'
            '</Types>'
        )
        ct_bytes = content_types.encode()
        zf.writestr("[Content_Types].xml", ct_bytes)
        hashes["[Content_Types].xml"] = hashlib.sha256(ct_bytes).hexdigest()

        # _rels/.rels
        gh_url = "https://github.com/aitobox/ATBOffice"
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{NS_REL_DOC}" Target="xl/workbook.xml"/>\n'
            f'  <Relationship Id="rId2" Type="{NS_REL_HYPERLINK}" '
            f'Target="{gh_url}" TargetMode="External"/>\n'
            '</Relationships>'
        )
        r_rels_bytes = root_rels.encode()
        zf.writestr("_rels/.rels", r_rels_bytes)
        hashes["_rels/.rels"] = hashlib.sha256(r_rels_bytes).hexdigest()

        # xl/workbook.xml
        wb_bytes = (
            b'<workbook><sheets>'
            b'<sheet name="Sheet1" sheetId="1" r:id="rId1"/>'
            b'<sheet name="Sheet2" sheetId="2" r:id="rId2"/>'
            b'</sheets></workbook>'
        )
        zf.writestr("xl/workbook.xml", wb_bytes)
        hashes["xl/workbook.xml"] = hashlib.sha256(wb_bytes).hexdigest()

        # xl/_rels/workbook.xml.rels
        wb_rels_bytes = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{NS_REL_WS}" Target="worksheets/sheet1.xml"/>\n'
            f'  <Relationship Id="rId2" Type="{NS_REL_WS}" Target="worksheets/sheet2.xml"/>\n'
            f'  <Relationship Id="rId3" Type="{NS_REL_VBA}" Target="vbaProject.bin"/>\n'
            '</Relationships>'
        ).encode()
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels_bytes)
        hashes["xl/_rels/workbook.xml.rels"] = hashlib.sha256(wb_rels_bytes).hexdigest()

        # xl/worksheets/sheet1.xml
        ws1_bytes = (
            b'<worksheet><sheetData><row r="1">'
            b'<c r="A1"><v>123</v></c>'
            b'</row></sheetData></worksheet>'
        )
        zf.writestr("xl/worksheets/sheet1.xml", ws1_bytes)
        hashes["xl/worksheets/sheet1.xml"] = hashlib.sha256(ws1_bytes).hexdigest()

        # xl/worksheets/_rels/sheet1.xml.rels
        ws1_rels_bytes = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{NS_REL_DRAWING}" '
            f'Target="../drawings/drawing1.xml"/>\n'
            '</Relationships>'
        ).encode()
        zf.writestr("xl/worksheets/_rels/sheet1.xml.rels", ws1_rels_bytes)
        hashes["xl/worksheets/_rels/sheet1.xml.rels"] = hashlib.sha256(ws1_rels_bytes).hexdigest()

        # xl/worksheets/sheet2.xml
        ws2_bytes = (
            b'<worksheet><sheetData><row r="1">'
            b'<c r="A1"><v>456</v></c>'
            b'</row></sheetData></worksheet>'
        )
        zf.writestr("xl/worksheets/sheet2.xml", ws2_bytes)
        hashes["xl/worksheets/sheet2.xml"] = hashlib.sha256(ws2_bytes).hexdigest()

        # xl/drawings/drawing1.xml
        drw_bytes = (
            b'<xdr:wsDr '
            b'xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"/>'
        )
        zf.writestr("xl/drawings/drawing1.xml", drw_bytes)
        hashes["xl/drawings/drawing1.xml"] = hashlib.sha256(drw_bytes).hexdigest()

        # xl/drawings/_rels/drawing1.xml.rels
        drw_rels_bytes = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{NS_REL_IMAGE}" '
            f'Target="../media/image1.png"/>\n'
            '</Relationships>'
        ).encode()
        zf.writestr("xl/drawings/_rels/drawing1.xml.rels", drw_rels_bytes)
        hashes["xl/drawings/_rels/drawing1.xml.rels"] = hashlib.sha256(drw_rels_bytes).hexdigest()

        # xl/media/image1.png (Binary payload)
        img_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        )
        zf.writestr("xl/media/image1.png", img_bytes)
        hashes["xl/media/image1.png"] = hashlib.sha256(img_bytes).hexdigest()

        # xl/vbaProject.bin (Binary macro payload)
        vba_bytes = (
            b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x3E\x00\x03\x00\xFE\xFF"
        )
        zf.writestr("xl/vbaProject.bin", vba_bytes)
        hashes["xl/vbaProject.bin"] = hashlib.sha256(vba_bytes).hexdigest()

        # customXml/item1.xml
        custom_bytes = b"<custom><node attr='preserved'/></custom>"
        zf.writestr("customXml/item1.xml", custom_bytes)
        hashes["customXml/item1.xml"] = hashlib.sha256(custom_bytes).hexdigest()

    return buf.getvalue(), hashes


def test_part_name_normalization_and_uri_resolution():
    """Verify robust part name normalization, slashes, and relative URI resolution."""
    assert normalize_part_name("/xl/workbook.xml") == "xl/workbook.xml"
    assert normalize_part_name("xl\\workbook.xml") == "xl/workbook.xml"
    assert normalize_part_name("xl/worksheets/../workbook.xml") == "xl/workbook.xml"
    assert normalize_part_name("/./xl//worksheets/sheet1.xml") == "xl/worksheets/sheet1.xml"

    # Relative resolution within package
    assert (
        resolve_part_uri("xl/workbook.xml", "worksheets/sheet1.xml")
        == "xl/worksheets/sheet1.xml"
    )
    assert (
        resolve_part_uri("xl/worksheets/sheet1.xml", "../drawings/drawing1.xml")
        == "xl/drawings/drawing1.xml"
    )
    assert (
        resolve_part_uri("xl/drawings/drawing1.xml", "../media/image1.png")
        == "xl/media/image1.png"
    )
    assert resolve_part_uri("", "xl/workbook.xml") == "xl/workbook.xml"
    assert (
        resolve_part_uri("xl/workbook.xml", "/xl/worksheets/sheet1.xml")
        == "xl/worksheets/sheet1.xml"
    )

    # Fragments
    resolved, frag = resolve_part_uri(
        "xl/workbook.xml", "sheet2.xml#Sheet2!A1", return_fragment=True
    )
    assert resolved == "xl/sheet2.xml"
    assert frag == "Sheet2!A1"

    # Bounds escape protection
    with pytest.raises(ValueError, match="escapes package"):
        resolve_part_uri("xl/workbook.xml", "../../outside.xml")

    with pytest.raises(ValueError, match="escapes package"):
        resolve_part_uri("", "../outside.xml")


def test_relative_part_uri():
    """Verify relative URI generation from owner to target."""
    assert (
        relative_part_uri("xl/workbook.xml", "xl/worksheets/sheet1.xml")
        == "worksheets/sheet1.xml"
    )
    assert (
        relative_part_uri("xl/worksheets/sheet1.xml", "xl/drawings/drawing1.xml")
        == "../drawings/drawing1.xml"
    )
    assert relative_part_uri("", "xl/workbook.xml") == "xl/workbook.xml"
    assert (
        relative_part_uri("xl/drawings/drawing1.xml", "xl/media/image1.png")
        == "../media/image1.png"
    )


def test_rels_path_mapping():
    """Verify owner part <-> rels part bidirectional mapping."""
    assert get_rels_path("") == "_rels/.rels"
    assert get_rels_path("xl/workbook.xml") == "xl/_rels/workbook.xml.rels"
    assert get_rels_path("workbook.xml") == "_rels/workbook.xml.rels"

    assert get_owner_from_rels_path("_rels/.rels") == ""
    assert get_owner_from_rels_path("xl/_rels/workbook.xml.rels") == "xl/workbook.xml"
    assert get_owner_from_rels_path("_rels/foo.xml.rels") == "foo.xml"


def test_relationship_resolution_and_subtree():
    """Verify deep tree traversal and cycle detection."""
    pkg_bytes, _ = make_complex_package_bytes()
    pkg = SourcePackage.from_bytes(pkg_bytes)

    # Root tree reaches all connected internal parts
    reachable = set(pkg.subtree(""))
    assert "xl/workbook.xml" in reachable
    assert "xl/worksheets/sheet1.xml" in reachable
    assert "xl/worksheets/sheet2.xml" in reachable
    assert "xl/drawings/drawing1.xml" in reachable
    assert "xl/media/image1.png" in reachable
    assert "xl/vbaProject.bin" in reachable
    # customXml is not linked in _rels/.rels, so not in root subtree
    assert "customXml/item1.xml" not in reachable

    # Subtree starting from sheet1
    s1_reachable = set(pkg.subtree("xl/worksheets/sheet1.xml"))
    assert s1_reachable == {
        "xl/worksheets/sheet1.xml",
        "xl/drawings/drawing1.xml",
        "xl/media/image1.png",
    }

    # Find referrers
    img_referrers = pkg.find_referrers("xl/media/image1.png")
    assert len(img_referrers) == 1
    assert img_referrers[0][0] == "xl/drawings/drawing1.xml"
    assert img_referrers[0][1].type == NS_REL_IMAGE


def test_content_type_resolution():
    """Verify ContentType resolution with case-insensitive defaults and overrides."""
    pkg_bytes, _ = make_complex_package_bytes()
    pkg = SourcePackage.from_bytes(pkg_bytes)

    # Overrides
    assert pkg.get_content_type("xl/workbook.xml") == CT_SHEET_MAIN
    assert pkg.get_content_type("xl/worksheets/sheet1.xml") == CT_WORKSHEET
    assert pkg.get_content_type("customXml/item1.xml") == CT_CUSTOM

    # Case-insensitive Defaults
    assert pkg.get_content_type("xl/media/image1.png") == CT_PNG
    assert pkg.get_content_type("xl/media/IMAGE2.PNG") == CT_PNG
    assert pkg.get_content_type("xl/vbaProject.bin") == CT_VBA
    assert pkg.get_content_type("xl/binary.BIN") == CT_VBA

    # Unmapped extension
    assert pkg.get_content_type("unknown.xyz") is None


def test_preserve_unmodified_parts_function():
    """Verify standalone preserve_unmodified_parts function."""
    pkg_bytes, original_hashes = make_complex_package_bytes()

    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as target_zip:
        # User modified sheet1.xml
        target_zip.writestr(
            "xl/worksheets/sheet1.xml", b"<worksheet><sheetData/></worksheet>"
        )

        # Preserve everything else
        preserved = preserve_unmodified_parts(
            source=pkg_bytes,
            target_zip=target_zip,
            modified_parts={"xl/worksheets/sheet1.xml"},
        )

    assert "xl/vbaProject.bin" in preserved
    assert "xl/media/image1.png" in preserved
    assert "xl/worksheets/sheet2.xml" in preserved
    assert "xl/worksheets/sheet1.xml" not in preserved

    # Inspect target zip contents and verify exact SHA256 hashes
    out_buf.seek(0)
    with zipfile.ZipFile(out_buf, "r") as zf:
        for name in preserved:
            saved_data = zf.read(name)
            saved_hash = hashlib.sha256(saved_data).hexdigest()
            assert saved_hash == original_hashes[name], (
                f"SHA256 mismatch for preserved part {name}"
            )


def test_package_writer_byte_for_byte_sha256(tmp_path: Path):
    """Verify PackageWriter preserves byte-for-byte SHA256 integrity on unmodified parts."""
    pkg_bytes, original_hashes = make_complex_package_bytes()
    pkg = SourcePackage.from_bytes(pkg_bytes)

    writer = PackageWriter(source_package=pkg)
    # Modify only sheet1.xml
    new_sheet1 = (
        b'<worksheet><sheetData><row r="1">'
        b'<c r="A1"><v>99999</v></c>'
        b'</row></sheetData></worksheet>'
    )
    writer.replace_part("xl/worksheets/sheet1.xml", new_sheet1)

    target_file = tmp_path / "saved.xlsx"
    writer.save(target_file)

    saved_pkg = SourcePackage.open(target_file)

    # 1. Modified part has changed
    assert saved_pkg.read_part("xl/worksheets/sheet1.xml") == new_sheet1
    modified_hash = hashlib.sha256(
        saved_pkg.read_part("xl/worksheets/sheet1.xml")
    ).hexdigest()
    assert modified_hash != original_hashes["xl/worksheets/sheet1.xml"]

    # 2. All unmodified parts match 100% byte-for-byte SHA256 hashes
    unmodified_parts = [
        "xl/workbook.xml",
        "xl/_rels/workbook.xml.rels",
        "xl/worksheets/sheet2.xml",
        "xl/drawings/drawing1.xml",
        "xl/drawings/_rels/drawing1.xml.rels",
        "xl/media/image1.png",
        "xl/vbaProject.bin",
        "customXml/item1.xml",
    ]

    for part_name in unmodified_parts:
        data = saved_pkg.read_part(part_name)
        current_hash = hashlib.sha256(data).hexdigest()
        assert current_hash == original_hashes[part_name], (
            f"Part {part_name} byte stream was modified! Expected SHA256 "
            f"{original_hashes[part_name]}, got {current_hash}"
        )

    # 3. Content types intact
    assert saved_pkg.get_content_type("xl/vbaProject.bin") == CT_VBA
    assert saved_pkg.get_content_type("xl/media/image1.png") == CT_PNG
    assert saved_pkg.get_content_type("customXml/item1.xml") == CT_CUSTOM
