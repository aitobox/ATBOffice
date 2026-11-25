"""OPC container safety and fidelity regressions."""

from __future__ import annotations

import io
import zipfile

import pytest

from atboffice.vfs.opc import PackageWriter, SourcePackage

CT = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/Word/Document.xml" ContentType="application/test+xml"/>'
    "</Types>"
)


def _zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_percent_encoded_part_names_are_written_back_unchanged() -> None:
    data = _zip({"[Content_Types].xml": CT, "word/media/my%20image.png": b"png"})
    pkg = SourcePackage.from_bytes(data)
    assert pkg.has_part("word/media/my image.png")
    out = PackageWriter(pkg).to_bytes()
    assert "word/media/my%20image.png" in zipfile.ZipFile(io.BytesIO(out)).namelist()


def test_content_type_overrides_match_case_insensitively() -> None:
    data = _zip({"[Content_Types].xml": CT, "word/document.xml": b"<x/>"})
    pkg = SourcePackage.from_bytes(data)
    assert pkg.get_content_type("word/document.xml") == "application/test+xml"


def test_zip_bombs_are_refused() -> None:
    bomb = _zip({"[Content_Types].xml": CT, "xl/big.xml": b"\0" * (200 * 1024 * 1024)})
    assert len(bomb) < 1024 * 1024
    with pytest.raises(ValueError, match="(?i)too large|compression"):
        SourcePackage.from_bytes(bomb)
