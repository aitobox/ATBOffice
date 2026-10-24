import pytest
from atboffice.vfs.crypto import is_encrypted_package, decrypt_package, encrypt_package


def test_is_encrypted_package_false_on_non_cfb():
    assert not is_encrypted_package(b"")
    assert not is_encrypted_package(b"PK\x03\x04plain_zip_data")
    assert not is_encrypted_package(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 504)


def test_agile_encryption_roundtrip():
    payload = b"PK\x03\x04test_xlsx_payload_content_1234567890"
    password = "OfficePassword2026!"
    encrypted = encrypt_package(payload, password=password, agile=True)

    assert is_encrypted_package(encrypted)
    decrypted = decrypt_package(encrypted, password=password)
    assert decrypted == payload


def test_agile_encryption_bad_password():
    payload = b"PK\x03\x04test_xlsx_payload_content"
    encrypted = encrypt_package(payload, password="CorrectPassword", agile=True)

    with pytest.raises(ValueError, match="Invalid password"):
        decrypt_package(encrypted, password="IncorrectPassword")


def test_agile_encryption_multisegment():
    # 4096-byte segments; test multi-segment crossing
    payload = b"PK\x03\x04" + (b"0123456789ABCDEF" * 1000)  # 16004 bytes
    password = "MultiSegmentPassword!"
    encrypted = encrypt_package(payload, password=password, agile=True)

    assert is_encrypted_package(encrypted)
    decrypted = decrypt_package(encrypted, password=password)
    assert decrypted == payload


def test_unicode_password_roundtrip():
    payload = b"PK\x03\x04unicode_password_payload"
    password = "测试密码_Office_2026_🌟"
    encrypted = encrypt_package(payload, password=password, agile=True)

    assert is_encrypted_package(encrypted)
    decrypted = decrypt_package(encrypted, password=password)
    assert decrypted == payload

    with pytest.raises(ValueError, match="Invalid password"):
        decrypt_package(encrypted, password="wrong_unicode_测试")


def test_empty_password_roundtrip():
    payload = b"PK\x03\x04empty_password_test"
    password = ""
    encrypted = encrypt_package(payload, password=password, agile=True)

    assert is_encrypted_package(encrypted)
    decrypted = decrypt_package(encrypted, password=password)
    assert decrypted == payload


def test_corrupt_data_raises_error():
    with pytest.raises(ValueError):
        decrypt_package(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1corrupt_truncated", "any_password")


def test_filepath_input(tmp_path):
    payload = b"PK\x03\x04test_filepath_payload_content"
    password = "FilepathPassword123"
    encrypted = encrypt_package(payload, password=password, agile=True)

    test_file = tmp_path / "protected.xlsx"
    test_file.write_bytes(encrypted)

    # Test Path object
    assert is_encrypted_package(test_file)
    assert decrypt_package(test_file, password) == payload

    # Test str object
    assert is_encrypted_package(str(test_file))
    assert decrypt_package(str(test_file), password) == payload


def test_large_payload_multi_block():
    payload = b"PK\x03\x04" + (b"EXCEL_ROW_DATA_SAMPLE_LINE_PADDING_123456\n" * 2000)  # ~84KB
    password = "LargeFilePassword2026!"
    encrypted = encrypt_package(payload, password=password, agile=True)

    assert is_encrypted_package(encrypted)
    decrypted = decrypt_package(encrypted, password=password)
    assert decrypted == payload


def test_non_cfb_file_input(tmp_path):
    plain_file = tmp_path / "plain.xlsx"
    plain_file.write_bytes(b"PK\x03\x04some_plain_zip_data")

    assert not is_encrypted_package(plain_file)
    with pytest.raises(ValueError, match="Corrupted encrypted package"):
        decrypt_package(plain_file, "password")

