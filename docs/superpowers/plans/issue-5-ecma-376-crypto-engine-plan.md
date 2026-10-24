# Implementation Plan: Issue #5 ECMA-376 Agile & Standard AES 加解密引擎

## User Review Required
None. High confidence (>=90%) autonomous execution.

---

## Tasks Breakdown

### Task 1: TDD Unit Tests for Office Encryption (`tests/unit/vfs/test_crypto.py`)
- Test FIPS 197 AES test vectors and random round-trip tests (ECB and CBC modes, 128/192/256-bit keys).
- Test `is_encrypted_package`:
  - Returns `False` for arbitrary bytes, plain text, and standard ZIP / OOXML files.
  - Returns `False` for empty or truncated data.
  - Returns `True` for valid encrypted packages.
- Test `encrypt_package` and `decrypt_package` roundtrip:
  - Roundtrip small payload with password.
  - Roundtrip realistic OOXML ZIP payload with password.
  - Verify decrypted bytes exactly match original bytes.
- Test error handling:
  - Wrong password raises `ValueError("Invalid password")`.
  - Empty or invalid password handling.
  - Non-encrypted package passed to `decrypt_package` raises `ValueError`.
  - Corrupted package stream handling.
- Test Agile vs Standard encryption:
  - Test Agile encryption parsing, key derivation, and decryption.
  - Test Standard encryption parsing, key derivation, and decryption.

### Task 2: Implement OLE Compound Document (CFB) Reader and Writer (`src/atboffice/vfs/crypto.py`)
- Implement `CFBReader`:
  - Validates 8-byte header `\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1`.
  - Reads FAT, DIFAT, Directory entries, MiniFAT, and MiniStream.
  - Provides `get_stream(name: str) -> bytes | None` (case-insensitive stream lookup).
- Implement `cfb_write(info_bytes: bytes, pkg_bytes: bytes) -> bytes`:
  - Constructs standard 512-byte sector OLE container.
  - Writes root directory, `EncryptionInfo`, `EncryptedPackage`, and `\x06DataSpaces` hierarchy.

### Task 3: Implement AES Cipher, Hash Spin & Agile/Standard Engines (`src/atboffice/vfs/crypto.py`)
- Implement password spin function:
  - 100,000 iterations for Agile (SHA-512 / SHA-256 / SHA-1).
  - 50,000 iterations for Standard (SHA-1).
- Implement `_decrypt_agile(info: bytes, pkg: bytes, password: str) -> bytes`:
  - Parse `EncryptionInfo` XML (keyData, encryptedKey, saltValue, spinCount, verifier hashes).
  - Verify password with `encryptedVerifierHashInput` and `encryptedVerifierHashValue`.
  - Decrypt `encryptedKeyValue` to obtain package key.
  - Decrypt segmented chunks (4096-byte segments) with derived IVs.
- Implement `_decrypt_standard(info: bytes, pkg: bytes, password: str) -> bytes`:
  - Parse binary header, salt, verifiers.
  - Verify password and derive key.
  - Decrypt payload with AES-ECB.
- Implement `encrypt_package(package_bytes: bytes, password: str) -> bytes`:
  - Agile AES-256-CBC with SHA-512.
  - Generate XML and package in CFB.

### Task 4: Expose APIs & Integrate with Package Module (`src/atboffice/vfs/__init__.py`)
- Export `is_encrypted_package`, `decrypt_package`, `encrypt_package` in `src/atboffice/vfs/__init__.py`.

### Task 5: Full Test Suite Verification
- Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/vfs/test_crypto.py -v`
- Run all tests: `PYTHONPATH=src conda run -n ATBOffice pytest tests/`
- Verify 100% pass with zero regressions.
