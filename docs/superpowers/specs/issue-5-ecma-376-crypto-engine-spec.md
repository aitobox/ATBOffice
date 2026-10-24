# Specification: Issue #5 ECMA-376 Agile & Standard AES 加解密引擎

## 1. Overview & Problem Statement
Office Open XML (ECMA-376 Part 2) documents (`.xlsx`, `.docx`, `.pptx`) protected by passwords are encrypted using an OLE Compound File Binary (CFB) wrapper encapsulating two key streams:
1. `EncryptionInfo`: Contains cryptographic metadata (version header, XML descriptor for Agile Encryption or binary structures for Standard Encryption, salt, spin count, and verifier hashes).
2. `EncryptedPackage`: Contains the encrypted payload (an 8-byte unencrypted payload size header followed by block-encrypted ciphertext).

To support enterprise spreadsheet workflows in ATBOffice:
- The system must detect whether a file or byte stream is an encrypted Office package without throwing exceptions on plain files.
- The system must decrypt Agile-encrypted packages (Office 2010+, AES-128/256 with SHA-1/SHA-256/SHA-512 and 100,000 spin count).
- The system must decrypt Standard-encrypted packages (Office 2007, AES-ECB with SHA-1 and 50,000 spin count).
- The system must encrypt plaintext OOXML packages using Agile Encryption (AES-256-CBC + SHA-512 + HMAC-SHA512 data integrity verification in a valid OLE CFB container).
- The system must provide robust error handling: invalid passwords must raise a clear, catchable `ValueError("Invalid password")`, while non-encrypted or corrupted streams must raise descriptive errors without causing crashes.

---

## 2. Requirements & Acceptance Criteria
- **Module Path**: `src/atboffice/vfs/crypto.py`
- **Core APIs**:
  - `is_encrypted_package(data: bytes | str | Path) -> bool`:
    - Checks for the OLE compound file signature (`\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1`).
    - Verifies the presence of `EncryptionInfo` and `EncryptedPackage` streams.
    - Returns `False` safely on normal ZIP/OOXML files, corrupt files, or non-file input.
  - `decrypt_package(data: bytes | str | Path, password: str) -> bytes`:
    - Reads `EncryptionInfo` and parses major/minor version numbers:
      - Major 4, Minor 4: Agile Encryption.
      - Major 3 or 4, Minor 2: Standard Encryption.
    - Derives keys using the specified spin count (e.g. 100,000 iterations for Agile, 50,000 for Standard).
    - Checks the verifier hash against the decrypted verifier value.
    - If passwords do not match, raises `ValueError("Invalid password")`.
    - Decrypts the package stream using the derived secret key and segment-specific IVs.
    - Truncates to original plaintext size and returns unencrypted OOXML bytes (valid ZIP).
  - `encrypt_package(package_bytes: bytes, password: str) -> bytes`:
    - Generates cryptographically secure random salts and secret keys using `secrets` or `os.urandom`.
    - Uses Agile Encryption (AES-256-CBC, SHA-512, 100,000 spin count).
    - Encrypts package payload in 4096-byte segments, each with IV derived from segment index.
    - Computes HMAC-SHA512 data integrity signature.
    - Generates valid ECMA-376 `EncryptionInfo` XML and 8-byte version prefix (`\x04\x00\x04\x00\x40\x00\x00\x00`).
    - Packages streams into an OLE CFB file structure (`cfb_write`) with standard `\x06DataSpaces` hierarchy.
    - Returned bytes roundtrip cleanly with `decrypt_package`.

---

## 3. Architecture & Cryptographic Implementation
- **OLE Compound Document Parser & Writer**:
  - Pure Python sector reader supporting FAT, DIFAT, MiniFAT, MiniStream, and Directory tree traversal.
  - Sector writer constructing standard 512-byte sector CFB files with MiniStream for streams < 4096 bytes and standard FAT for larger streams.
- **Key Derivation & Password Spin**:
  - Fast iterative hashing using Python's built-in `hashlib`.
  - Spin loop:
    $$H_0 = \text{Hash}(\text{salt} + \text{UTF-16LE}(\text{password}))$$
    $$H_{i+1} = \text{Hash}(\text{uint32\_le}(i) + H_i) \quad \text{for } i = 0 \dots (\text{spinCount} - 1)$$
  - Intermediate block key derivation for verifier input, verifier value, and package key.
- **AES Cipher Engine**:
  - Uses `cryptography.hazmat.primitives.ciphers` (`AES`, `modes.CBC`, `modes.ECB`) for constant-time, hardware-accelerated block encryption and decryption.

---

## 4. Edge Cases & Robustness
- **Invalid Password**: Throws exact `ValueError("Invalid password")`.
- **Empty / Truncated Data**: Safely raises `ValueError("Corrupted encrypted package")` or returns `False` in `is_encrypted_package`.
- **Unsupported Algorithm / Version**: Raises `ValueError("Unsupported encryption version ...")`.
- **Unicode Passwords**: Correctly encodes passwords to UTF-16LE matching Microsoft Office behavior.
- **Large Packages**: Streams and segments chunks in 4096-byte blocks with segment-derived IVs.
- **Type Annotations**: 100% type-annotated with Python 3.12+ syntax.
