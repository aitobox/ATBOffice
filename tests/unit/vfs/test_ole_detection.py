"""Unit tests for OLE / CFB detection, classification, and file format inspection."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from atboffice.vfs.crypto import (
    CFB_SIGNATURE,
    FileFormatInspection,
    detect_ole_format,
    encrypt_package,
    inspect_file_format,
    is_encrypted_package,
    is_ole_compound_file,
)
from atboffice.vfs.opc import OleCompoundFileError, SourcePackage


def _create_mock_cfb_with_stream_name(stream_name: str) -> bytes:
    """Helper to create a minimal CFB structure containing the given stream name in UTF-16LE."""
    # Header: 8 bytes magic + 504 bytes header fields
    header = bytearray(512)
    header[:8] = CFB_SIGNATURE
    header[0x1E:0x20] = (9).to_bytes(2, "little")  # sector size = 512
    header[0x20:0x22] = (6).to_bytes(2, "little")  # mini sector size = 64
    header[0x2C:0x30] = (1).to_bytes(4, "little")  # 1 FAT sector
    header[0x30:0x34] = (0).to_bytes(4, "little")  # directory start at sector 0
    header[0x38:0x3C] = (4096).to_bytes(4, "little")  # cutoff
    header[0x3C:0x40] = (0xFFFFFFFE).to_bytes(4, "little")  # no mini FAT
    header[0x44:0x48] = (0xFFFFFFFE).to_bytes(4, "little")  # no DIFAT
    header[0x4C:0x50] = (1).to_bytes(4, "little")  # FAT sector is sector 1

    # Sector 0: Directory entry sector (128 bytes per entry)
    dir_sector = bytearray(512)
    # Entry 0: Root Entry (type 5)
    root_name = "Root Entry\x00".encode("utf-16le")
    dir_sector[0 : len(root_name)] = root_name
    dir_sector[64:66] = len(root_name).to_bytes(2, "little")
    dir_sector[66] = 5  # root storage

    # Entry 1: Target Stream (type 2)
    entry_offset = 128
    encoded_name = f"{stream_name}\x00".encode("utf-16le")
    dir_sector[entry_offset : entry_offset + len(encoded_name)] = encoded_name
    dir_sector[entry_offset + 64 : entry_offset + 66] = len(encoded_name).to_bytes(2, "little")
    dir_sector[entry_offset + 66] = 2  # stream
    dir_sector[entry_offset + 116 : entry_offset + 120] = (0xFFFFFFFE).to_bytes(4, "little")
    dir_sector[entry_offset + 120 : entry_offset + 124] = (0).to_bytes(4, "little")

    # Sector 1: FAT sector
    fat_sector = bytearray(512)
    # Sector 0 is end-of-chain for directory, sector 1 is FAT
    fat_sector[0:4] = (0xFFFFFFFE).to_bytes(4, "little")
    fat_sector[4:8] = (0xFFFFFFFD).to_bytes(4, "little")

    return bytes(header + dir_sector + fat_sector)


def test_is_ole_compound_file_truthy_and_falsy(tmp_path: Path):
    """Test is_ole_compound_file with various byte inputs and file paths."""
    assert is_ole_compound_file(b"") is False
    assert is_ole_compound_file(b"PK\x03\x04" + b"\x00" * 20) is False
    assert is_ole_compound_file(b"\x00" * 512) is False

    cfb_header = CFB_SIGNATURE + b"\x00" * 504
    assert is_ole_compound_file(cfb_header) is True

    f_cfb = tmp_path / "test.cfb"
    f_cfb.write_bytes(cfb_header)
    assert is_ole_compound_file(f_cfb) is True
    assert is_ole_compound_file(str(f_cfb)) is True

    f_non_cfb = tmp_path / "test.txt"
    f_non_cfb.write_bytes(b"hello world")
    assert is_ole_compound_file(f_non_cfb) is False


def test_detect_ole_format_classified():
    """Test detect_ole_format identifies specific Office 97-2003 and encrypted formats."""
    # Non-CFB
    assert detect_ole_format(b"PK\x03\x04zip") == "none"

    # Encrypted OOXML package
    plain_zip = b"PK\x03\x04" + b"\x00" * 26
    encrypted = encrypt_package(plain_zip, passcode="Secret123")
    assert detect_ole_format(encrypted) == "encrypted_ooxml"

    # Word 97-2003 (.doc)
    doc_cfb = _create_mock_cfb_with_stream_name("WordDocument")
    assert detect_ole_format(doc_cfb) == "word97"

    # Excel 97-2003 (.xls)
    xls_cfb = _create_mock_cfb_with_stream_name("Workbook")
    assert detect_ole_format(xls_cfb) == "excel97"

    # PowerPoint 97-2003 (.ppt)
    ppt_cfb = _create_mock_cfb_with_stream_name("PowerPoint Document")
    assert detect_ole_format(ppt_cfb) == "powerpoint97"

    # Generic / Unidentified OLE
    other_cfb = _create_mock_cfb_with_stream_name("CustomStream")
    assert detect_ole_format(other_cfb) == "legacy_binary"


def test_detect_ole_format_corrupted_directory_probe_fallback():
    """Test fallback regex probe when directory structure cannot be parsed."""
    damaged = bytearray(CFB_SIGNATURE + b"\x00" * 504)
    # Append stream names encoded as UTF-16LE in raw sectors
    damaged.extend("WordDocument".encode("utf-16le"))
    assert detect_ole_format(bytes(damaged)) == "word97"

    damaged_xls = bytearray(CFB_SIGNATURE + b"\x00" * 504)
    damaged_xls.extend("Workbook".encode("utf-16le"))
    assert detect_ole_format(bytes(damaged_xls)) == "excel97"


def test_inspect_file_format_disguised_extensions(tmp_path: Path):
    """Test inspect_file_format correctly detects disguised extensions and generates guidance."""
    # Disguised .doc as .docx
    doc_bytes = _create_mock_cfb_with_stream_name("WordDocument")
    f_docx = tmp_path / "report.docx"
    f_docx.write_bytes(doc_bytes)

    insp = inspect_file_format(f_docx, expected_app="quire")
    assert insp.is_ole is True
    assert insp.is_encrypted is False
    assert insp.ole_format == "word97"
    assert insp.is_disguised is True
    assert insp.guidance_message is not None
    assert ".docx" in insp.guidance_message
    assert ".doc" in insp.guidance_message

    # Disguised .xls as .xlsx
    xls_bytes = _create_mock_cfb_with_stream_name("Workbook")
    f_xlsx = tmp_path / "sheet.xlsx"
    f_xlsx.write_bytes(xls_bytes)

    insp = inspect_file_format(f_xlsx, expected_app="ledger")
    assert insp.is_ole is True
    assert insp.is_encrypted is False
    assert insp.ole_format == "excel97"
    assert insp.is_disguised is True
    assert ".xlsx" in insp.guidance_message
    assert ".xls" in insp.guidance_message

    # Disguised .ppt as .pptx
    ppt_bytes = _create_mock_cfb_with_stream_name("PowerPoint Document")
    f_pptx = tmp_path / "slides.pptx"
    f_pptx.write_bytes(ppt_bytes)

    insp = inspect_file_format(f_pptx, expected_app="lectern")
    assert insp.is_ole is True
    assert insp.is_encrypted is False
    assert insp.ole_format == "powerpoint97"
    assert insp.is_disguised is True
    assert ".pptx" in insp.guidance_message
    assert ".ppt" in insp.guidance_message


def test_inspect_file_format_cross_module_mismatch(tmp_path: Path):
    """Test inspect_file_format when opening wrong Office document type in an app."""
    # Opening PPT in Quire
    ppt_bytes = _create_mock_cfb_with_stream_name("PowerPoint Document")
    f_ppt = tmp_path / "presentation.ppt"
    f_ppt.write_bytes(ppt_bytes)

    insp = inspect_file_format(f_ppt, expected_app="quire")
    assert insp.is_ole is True
    assert insp.ole_format == "powerpoint97"
    assert insp.guidance_message is not None
    assert "PowerPoint" in insp.guidance_message
    assert "Word" in insp.guidance_message


def test_source_package_raises_ole_compound_file_error():
    """SourcePackage.from_bytes must raise OleCompoundFileError when receiving OLE CFB data."""
    cfb_bytes = CFB_SIGNATURE + b"\x00" * 504
    with pytest.raises(OleCompoundFileError) as exc_info:
        SourcePackage.from_bytes(cfb_bytes)
    assert issubclass(OleCompoundFileError, ValueError)
    assert exc_info.value.is_encrypted is False
