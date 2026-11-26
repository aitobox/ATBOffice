import io
import sys
import zipfile
from pathlib import Path

import pytest

from atboffice.vfs.crypto import (
    InvalidPasswordError,
    decrypt_package,
    encrypt_package,
    is_encrypted_package,
)

CORPUS = Path(__file__).resolve().parents[2] / "docs"


def _members(data: bytes) -> dict[str, bytes]:
    """ZIP contents; tiny packages gain a padding comment when they are encrypted."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


def _ooxml(content: bytes) -> bytes:
    """A minimal OOXML package carrying ``content`` (msoffcrypto checks the inner ZIP)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns='
            '"http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        z.writestr("payload.bin", content)
    return buf.getvalue()


def test_is_encrypted_package_false_on_non_cfb():
    assert not is_encrypted_package(b"")
    assert not is_encrypted_package(b"PK\x03\x04plain_zip_data")
    assert not is_encrypted_package(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 504)


def test_agile_encryption_roundtrip():
    payload = _ooxml(b"PK\x03\x04test_xlsx_payload_content_1234567890")
    doc_key = "OfficePassword2026!"
    encrypted = encrypt_package(payload, passcode=doc_key)

    assert is_encrypted_package(encrypted)
    decrypted = decrypt_package(encrypted, passcode=doc_key)
    assert _members(decrypted) == _members(payload)


def test_agile_encryption_bad_passcode():
    payload = _ooxml(b"PK\x03\x04test_xlsx_payload_content")
    encrypted = encrypt_package(payload, passcode="CorrectPassword")

    with pytest.raises(ValueError, match="Invalid password"):
        decrypt_package(encrypted, passcode="IncorrectPassword")


def test_agile_encryption_multisegment():
    # 4096-byte segments; test multi-segment crossing
    payload = _ooxml(b"0123456789ABCDEF" * 1000)  # spans several 4096-byte segments
    doc_key = "MultiSegmentPassword!"
    encrypted = encrypt_package(payload, passcode=doc_key)

    assert is_encrypted_package(encrypted)
    decrypted = decrypt_package(encrypted, passcode=doc_key)
    assert _members(decrypted) == _members(payload)


def test_unicode_passcode_roundtrip():
    payload = _ooxml(b"PK\x03\x04unicode_password_payload")
    doc_key = "测试密码_Office_2026_🌟"
    encrypted = encrypt_package(payload, passcode=doc_key)

    assert is_encrypted_package(encrypted)
    decrypted = decrypt_package(encrypted, passcode=doc_key)
    assert _members(decrypted) == _members(payload)

    with pytest.raises(ValueError, match="Invalid password"):
        decrypt_package(encrypted, passcode="wrong_unicode_测试")


def test_empty_passcode_is_rejected():
    with pytest.raises(ValueError):
        encrypt_package(_ooxml(b"x"), passcode="")


def test_tampered_package_is_detected():
    from atboffice.vfs.crypto import CFBReader

    payload = _ooxml(b"integrity" * 2000)
    encrypted = bytearray(encrypt_package(payload, passcode="pw"))
    # Flip one byte deep inside the EncryptedPackage stream.
    stream = CFBReader(bytes(encrypted)).get_stream("EncryptedPackage")
    offset = bytes(encrypted).find(stream[4000:4064])
    assert offset > 0
    encrypted[offset] ^= 0xFF
    with pytest.raises(ValueError):
        decrypt_package(bytes(encrypted), passcode="pw")


def test_wrong_password_raises_invalid_password_error():
    encrypted = encrypt_package(_ooxml(b"x"), passcode="right")
    with pytest.raises(InvalidPasswordError):
        decrypt_package(encrypted, passcode="wrong")


def test_corpus_agile_file_opens_despite_failed_hmac():
    path = CORPUS / "word" / "docx" / "poi__protected_agile.docx"
    if not path.exists():
        pytest.skip("corpus file missing")
    data = decrypt_package(path, passcode="VelvetSweatshop")
    assert zipfile.is_zipfile(io.BytesIO(data))


def test_corrupt_data_raises_error():
    with pytest.raises(ValueError):
        decrypt_package(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1corrupt_truncated", "any_doc_key")


def test_filepath_input(tmp_path):
    payload = _ooxml(b"PK\x03\x04test_filepath_payload_content")
    doc_key = "FilepathPassword123"
    encrypted = encrypt_package(payload, passcode=doc_key)

    test_file = tmp_path / "protected.xlsx"
    test_file.write_bytes(encrypted)

    # Test Path object
    assert is_encrypted_package(test_file)
    assert _members(decrypt_package(test_file, passcode=doc_key)) == _members(payload)

    # Test str object
    assert is_encrypted_package(str(test_file))
    assert _members(decrypt_package(str(test_file), passcode=doc_key)) == _members(payload)


def test_large_payload_multi_block():
    payload = _ooxml(b"EXCEL_ROW_DATA_SAMPLE_LINE_PADDING_123456\n" * 2000)  # ~84KB
    doc_key = "LargeFilePassword2026!"
    encrypted = encrypt_package(payload, passcode=doc_key)

    assert is_encrypted_package(encrypted)
    decrypted = decrypt_package(encrypted, passcode=doc_key)
    assert _members(decrypted) == _members(payload)


def test_non_cfb_file_input(tmp_path):
    plain_file = tmp_path / "plain.xlsx"
    plain_file.write_bytes(b"PK\x03\x04some_plain_zip_data")

    assert not is_encrypted_package(plain_file)
    with pytest.raises(ValueError, match="Corrupted encrypted package"):
        decrypt_package(plain_file, "some_key")


def test_legacy_binary_detection_and_errors():
    from atboffice.vfs.crypto import decrypt_legacy_binary, is_encrypted_legacy_binary

    xls = CORPUS / "excel" / "xls" / "libreoffice__dsum.xls"
    if not xls.exists():
        pytest.skip("corpus file missing")
    assert not is_encrypted_legacy_binary(xls)
    assert not is_encrypted_legacy_binary(b"PK\x03\x04")
    with pytest.raises(ValueError):
        decrypt_legacy_binary(b"not an office file")


def test_crypto_lazy_msoffcrypto_import(monkeypatch):
    """Unencrypted checks work without msoffcrypto; crypto ops raise a clear ImportError."""
    monkeypatch.setitem(sys.modules, "msoffcrypto", None)
    monkeypatch.setitem(sys.modules, "msoffcrypto.exceptions", None)
    monkeypatch.setitem(sys.modules, "msoffcrypto.method", None)
    monkeypatch.setitem(sys.modules, "msoffcrypto.method.ecma376_agile", None)

    assert not is_encrypted_package(b"PK\x03\x04plain")

    with pytest.raises(ImportError, match="msoffcrypto-tool"):
        decrypt_package(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 504, passcode="pw")

    with pytest.raises(ImportError, match="msoffcrypto-tool"):
        encrypt_package(_ooxml(b"x"), passcode="pw")
