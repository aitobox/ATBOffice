"""Office document encryption: detection, decryption and encryption.

Detection of OLE Compound File containers (legacy binary 97-2003 documents and
password-protected OOXML packages) is implemented here with a small, guarded CFB
reader. The cryptography itself is delegated to ``msoffcrypto-tool``:

- OOXML Agile (Office 2010+) and Standard (Office 2007) decryption, with HMAC
  integrity verification;
- OOXML Agile encryption on save;
- legacy RC4 / CryptoAPI / XOR decryption of .xls, .doc and .ppt files.
"""

from __future__ import annotations

import io
import logging
import math
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import msoffcrypto
from msoffcrypto import exceptions as _msoff_errors

logger = logging.getLogger(__name__)

#: Password Excel uses for workbooks that are encrypted but have no password set.
EXCEL_DEFAULT_PASSWORD: Final[str] = "VelvetSweatshop"

CFB_SIGNATURE: Final[bytes] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
SS: Final[int] = 512
MS: Final[int] = 64
CUTOFF: Final[int] = 4096
END: Final[int] = 0xFFFFFFFE
FREE: Final[int] = 0xFFFFFFFF
FATSEC: Final[int] = 0xFFFFFFFD
DIFSEC: Final[int] = 0xFFFFFFFC
NONE: Final[int] = 0xFFFFFFFF


def _to_bytes(data: bytes | str | Path) -> bytes:
    """Normalize input parameter to bytes."""
    if isinstance(data, (str, Path)):
        with open(data, "rb") as f:
            return f.read()
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data)
    raise TypeError(f"Expected bytes, str, or Path, got {type(data).__name__}")


class CFBReader:
    """OLE Compound File Binary (CFB) reader."""

    def __init__(self, raw: bytes) -> None:
        if len(raw) < 512:
            raise ValueError("Invalid CFB length")
        if raw[:8] != CFB_SIGNATURE:
            raise ValueError("Not a compound file")
        self.raw = raw
        self.ssz = 1 << struct.unpack_from("<H", raw, 0x1E)[0]
        self.mssz = 1 << struct.unpack_from("<H", raw, 0x20)[0]
        self.n_fat = struct.unpack_from("<I", raw, 0x2C)[0]
        self.dir_start = struct.unpack_from("<I", raw, 0x30)[0]
        self.cutoff = struct.unpack_from("<I", raw, 0x38)[0]
        self.mini_fat_start = struct.unpack_from("<I", raw, 0x3C)[0]
        self.difat_start = struct.unpack_from("<I", raw, 0x44)[0]
        self.n_difat = struct.unpack_from("<I", raw, 0x48)[0]

        fat_secs: list[int] = []
        for i in range(min(109, self.n_fat)):
            sec = struct.unpack_from("<I", raw, 0x4C + 4 * i)[0]
            if sec < 0xFFFFFFFA:
                fat_secs.append(sec)

        d = self.difat_start
        guard = 0
        per = self.ssz // 4 - 1
        while d < 0xFFFFFFFA and guard < self.n_difat + 1 and len(fat_secs) < self.n_fat:
            guard += 1
            base = self._off(d)
            for i in range(per):
                if len(fat_secs) >= self.n_fat:
                    break
                sec = struct.unpack_from("<I", raw, base + 4 * i)[0]
                if sec < 0xFFFFFFFA:
                    fat_secs.append(sec)
            d = struct.unpack_from("<I", raw, base + 4 * per)[0]

        self.fat: list[int] = []
        for s in fat_secs:
            b = self._off(s)
            for k in range(self.ssz // 4):
                self.fat.append(struct.unpack_from("<I", raw, b + 4 * k)[0])

        self.entries: dict[str, dict[str, int | str]] = {}
        self.root_entry: dict[str, int | str] | None = None
        self._read_directory()

        self.mini: bytes | None = None
        self.mini_fat: list[int] | None = None

    def _off(self, sec: int) -> int:
        return (sec + 1) * self.ssz

    def _chain(self, start: int, limit: int = 1_000_000) -> list[int]:
        out: list[int] = []
        s = start
        visited: set[int] = set()
        while s < 0xFFFFFFFA and len(out) <= limit:
            if s in visited or s >= len(self.fat):
                break
            visited.add(s)
            out.append(s)
            s = self.fat[s]
        return out

    def _read_chain(self, start: int, size: int | None = None) -> bytes:
        limit = math.ceil((size or 10**9) / self.ssz) + 1
        secs = self._chain(start, limit)
        buf = bytearray(len(secs) * self.ssz)
        for i, s in enumerate(secs):
            b = self._off(s)
            chunk = self.raw[b : min(len(self.raw), b + self.ssz)]
            buf[i * self.ssz : i * self.ssz + len(chunk)] = chunk
        return bytes(buf[:size]) if size is not None else bytes(buf)

    def _read_directory(self) -> None:
        dir_bytes = self._read_chain(self.dir_start)
        for p in range(0, len(dir_bytes) - 127, 128):
            name_len = struct.unpack_from("<H", dir_bytes, p + 64)[0]
            entry_type = dir_bytes[p + 66]
            if not entry_type:
                continue
            name_raw = dir_bytes[p : p + max(0, name_len - 2)]
            name = name_raw.decode("utf-16le", errors="ignore")
            start_sec = struct.unpack_from("<I", dir_bytes, p + 116)[0]
            size = struct.unpack_from("<I", dir_bytes, p + 120)[0]
            entry: dict[str, int | str] = {
                "name": name,
                "type": entry_type,
                "start": start_sec,
                "size": size,
            }
            if entry_type == 5:
                self.root_entry = entry
            elif entry_type == 2:
                self.entries[name.lower()] = entry

    def _load_mini(self) -> None:
        if self.mini is None and self.root_entry:
            root_start = int(self.root_entry["start"])
            root_size = int(self.root_entry["size"])
            self.mini = self._read_chain(root_start, root_size)
            if self.mini_fat_start < 0xFFFFFFFA:
                mf_bytes = self._read_chain(self.mini_fat_start)
                self.mini_fat = [
                    struct.unpack_from("<I", mf_bytes, 4 * i)[0] for i in range(len(mf_bytes) // 4)
                ]
            else:
                self.mini_fat = []

    def get_stream(self, name: str) -> bytes | None:
        """Retrieve stream bytes by entry name (case-insensitive)."""
        e = self.entries.get(name.lower())
        if not e:
            return None
        size = int(e["size"])
        start = int(e["start"])
        if size < self.cutoff:
            self._load_mini()
            if not self.mini or self.mini_fat is None:
                return b""
            out = bytearray(size)
            s = start
            pos = 0
            visited: set[int] = set()
            while s < 0xFFFFFFFA and pos < size:
                if s in visited or s >= len(self.mini_fat):
                    break
                visited.add(s)
                chunk = self.mini[s * self.mssz : s * self.mssz + min(self.mssz, size - pos)]
                out[pos : pos + len(chunk)] = chunk
                pos += len(chunk)
                s = self.mini_fat[s]
            return bytes(out)
        return self._read_chain(start, size)

    def has_stream(self, name: str) -> bool:
        """Check if stream entry exists."""
        return name.lower() in self.entries


@dataclass(frozen=True)
class FileFormatInspection:
    """Result of inspecting an Office document file format, OLE streams, and extension."""

    is_ole: bool
    is_encrypted: bool
    ole_format: str  # word97, excel97, powerpoint97, encrypted_ooxml, legacy_binary, none
    ext: str
    is_disguised: bool
    guidance_title: str | None = None
    guidance_message: str | None = None

    @property
    def should_reject(self) -> bool:
        """Return True if the file is an unsupported legacy/disguised format requiring rejection."""
        return (self.guidance_message is not None) and (not self.is_encrypted)


def is_ole_compound_file(data: bytes | str | Path) -> bool:
    """Return True if data starts with the OLE CFB 8-byte signature."""
    try:
        raw = _to_bytes(data)
        return len(raw) >= 8 and raw[:8] == CFB_SIGNATURE
    except Exception:
        return False


def detect_ole_format(data: bytes | str | Path) -> str:
    """Identify the specific format inside an OLE compound document.

    Returns:
        - "encrypted_ooxml": Contains EncryptionInfo and EncryptedPackage streams.
        - "word97": Contains WordDocument stream (Word 97-2003 .doc).
        - "excel97": Contains Workbook or Book stream (Excel 97-2003 .xls).
        - "powerpoint97": Contains PowerPoint Document or Current User stream (.ppt).
        - "legacy_binary": Unidentified or generic OLE compound file.
        - "none": Not an OLE compound file.
    """
    try:
        raw = _to_bytes(data)
        if len(raw) < 8 or raw[:8] != CFB_SIGNATURE:
            return "none"

        # 1. Attempt structured directory parsing via CFBReader
        try:
            reader = CFBReader(raw)
            if reader.has_stream("encryptioninfo") and reader.has_stream("encryptedpackage"):
                return "encrypted_ooxml"
            if reader.has_stream("worddocument"):
                return "word97"
            if reader.has_stream("workbook") or reader.has_stream("book"):
                return "excel97"
            if reader.has_stream("powerpoint document") or reader.has_stream("current user"):
                return "powerpoint97"
            if reader.entries:
                return "legacy_binary"
        except Exception:
            pass

        # 2. Fallback heuristic: UTF-16LE substring probe in the first 1MB
        # (aligned with .vibeoffice zip.js)
        probe_limit = min(len(raw), 1 << 20)
        probe_bytes = raw[:probe_limit]

        enc_probe = "EncryptedPackage".encode("utf-16le")
        doc_probe = "WordDocument".encode("utf-16le")
        xls_probe = "Workbook".encode("utf-16le")
        book_probe = "Book".encode("utf-16le")
        ppt_probe = "PowerPoint Document".encode("utf-16le")
        user_probe = "Current User".encode("utf-16le")

        if enc_probe in probe_bytes:
            return "encrypted_ooxml"
        if doc_probe in probe_bytes:
            return "word97"
        if xls_probe in probe_bytes or book_probe in probe_bytes:
            return "excel97"
        if ppt_probe in probe_bytes or user_probe in probe_bytes:
            return "powerpoint97"

        return "legacy_binary"
    except Exception:
        return "none"


def is_encrypted_package(data: bytes | str | Path) -> bool:
    """Return True if data represents an encrypted Office package CFB container."""
    return detect_ole_format(data) == "encrypted_ooxml"


def inspect_file_format(
    path_or_bytes: bytes | str | Path,
    expected_app: str | None = None,
    allow_excel97: bool = False,
) -> FileFormatInspection:
    """Inspect file header, OLE streams, and extension to provide accurate guidance."""
    from atboffice.core.i18n import safe_tr

    name = ""
    ext = ""
    if isinstance(path_or_bytes, (str, Path)):
        p = Path(path_or_bytes)
        name = p.name
        ext = p.suffix.lower()

    is_ole = is_ole_compound_file(path_or_bytes)
    app = (expected_app or "").lower().strip()

    if not is_ole:
        header_prefix = b""
        try:
            raw_sample = _to_bytes(path_or_bytes)[:64]
            if raw_sample.startswith(b"\xef\xbb\xbf"):
                raw_sample = raw_sample[3:]
            header_prefix = raw_sample.lstrip()
        except Exception:
            pass

        is_xml_or_html = header_prefix.startswith(
            (b"<", b"\xff\xfe<\x00", b"\xfe\xff\x00<")
        )
        is_rtf_header = header_prefix.startswith(b"{\\rtf")

        if app == "quire" and ext in {".doc", ".dot"}:
            if not (is_xml_or_html or is_rtf_header):
                return FileFormatInspection(
                    is_ole=False,
                    is_encrypted=False,
                    ole_format="word97",
                    ext=ext,
                    is_disguised=False,
                    guidance_title=safe_tr("文件格式提示"),
                    guidance_message=safe_tr(
                        "“{name}”是旧版二进制 Word 97–2003 文档 (.doc)。"
                        "Quire 原生支持 .docx、.html、.rtf、.md 和纯文本文件。"
                        "请在 Word 或 LibreOffice 中将其另存为 .docx 格式后再打开。"
                    ).format(name=name),
                )

        if app == "lectern" and ext in {".ppt", ".pps", ".pot"}:
            return FileFormatInspection(
                is_ole=False,
                is_encrypted=False,
                ole_format="powerpoint97",
                ext=ext,
                is_disguised=False,
                guidance_title=safe_tr("文件格式提示"),
                guidance_message=safe_tr(
                    "“{name}”是旧版二进制 PowerPoint 97–2003 演示文稿 (.ppt)。"
                    "Lectern 原生支持 .pptx 演示文稿。"
                    "请在 PowerPoint 或 LibreOffice 中将其另存为 .pptx 格式后再打开。"
                ).format(name=name),
            )

        if app == "ledger" and ext in {".xls", ".xlt"}:
            # If it starts with '<' (XMLSS or HTML table), allow it to pass to XMLSS/HTML parsers
            if not is_xml_or_html:
                if allow_excel97:
                    return FileFormatInspection(
                        is_ole=False,
                        is_encrypted=False,
                        ole_format="excel97",
                        ext=ext,
                        is_disguised=False,
                    )
                return FileFormatInspection(
                    is_ole=False,
                    is_encrypted=False,
                    ole_format="excel97",
                    ext=ext,
                    is_disguised=False,
                    guidance_title=safe_tr("文件格式提示"),
                    guidance_message=safe_tr(
                        "“{name}”是旧版二进制 Excel 97–2003 工作簿 (.xls)。"
                        "Ledger 原生支持 .xlsx、.xlsm、.csv、.tsv 和 XML 电子表格。"
                        "请在 Excel 或 LibreOffice 中将其另存为 .xlsx 格式后再打开。"
                    ).format(name=name),
                )

        return FileFormatInspection(
            is_ole=False,
            is_encrypted=False,
            ole_format="none",
            ext=ext,
            is_disguised=False,
        )

    ole_fmt = detect_ole_format(path_or_bytes)
    is_enc = (ole_fmt == "encrypted_ooxml")
    if is_enc:
        return FileFormatInspection(
            is_ole=True,
            is_encrypted=True,
            ole_format=ole_fmt,
            ext=ext,
            is_disguised=False,
        )

    # It is an unencrypted legacy OLE binary file
    app = (expected_app or "").lower().strip()
    is_disguised = False
    guidance_title = safe_tr("文件格式提示")
    guidance_msg = None

    # Modern OOXML extensions
    ooxml_word_exts = {".docx", ".docm", ".dotx"}
    ooxml_excel_exts = {".xlsx", ".xlsm", ".xltx"}
    ooxml_ppt_exts = {".pptx", ".ppsx", ".potx"}

    if app == "quire":
        if ole_fmt == "powerpoint97":
            guidance_msg = safe_tr(
                "“{name}”是 PowerPoint 97–2003 演示文稿，而非 Word 文档。"
                "Quire 仅支持打开文字处理文档。"
            ).format(name=name)
        elif ole_fmt == "excel97":
            guidance_msg = safe_tr(
                "“{name}”是 Excel 97–2003 工作簿，而非 Word 文档。"
                "Quire 仅支持打开文字处理文档。"
            ).format(name=name)
        elif ext in ooxml_word_exts or (ext and ext not in {".doc", ".dot"}):
            is_disguised = True
            guidance_msg = safe_tr(
                "“{name}”是旧版二进制 Word 97–2003 文档 (.doc)，但扩展名为 {ext}。"
                "请先在 Word、Pages、Google 文档或 LibreOffice 中将其另存为 .docx 格式。"
            ).format(name=name, ext=ext or safe_tr("其他"))
        else:
            guidance_msg = safe_tr(
                "“{name}”是旧版二进制 Word 97–2003 文档 (.doc)。"
                "Quire 原生支持 .docx、.html、.rtf、.md 和纯文本文件。"
                "请在 Word 或 LibreOffice 中将其另存为 .docx 格式后再打开。"
            ).format(name=name)

    elif app == "ledger":
        if ole_fmt == "word97":
            guidance_msg = safe_tr(
                "“{name}”是 Word 97–2003 文档，而非 Excel 工作簿。"
                "Ledger 仅支持打开电子表格文件。"
            ).format(name=name)
        elif ole_fmt == "powerpoint97":
            guidance_msg = safe_tr(
                "“{name}”是 PowerPoint 97–2003 演示文稿，而非 Excel 工作簿。"
                "Ledger 仅支持打开电子表格文件。"
            ).format(name=name)
        elif ext in ooxml_excel_exts or (ext and ext not in {".xls", ".xlt"}):
            is_disguised = True
            guidance_msg = safe_tr(
                "“{name}”是旧版二进制 Excel 97–2003 工作簿 (.xls)，但扩展名为 {ext}。"
                "请先在 Excel 或 LibreOffice 中将其另存为 .xlsx 格式。"
            ).format(name=name, ext=ext or safe_tr("其他"))
        else:
            if not allow_excel97:
                guidance_msg = safe_tr(
                    "“{name}”是旧版二进制 Excel 97–2003 工作簿 (.xls)。"
                    "Ledger 原生支持 .xlsx、.xlsm、.csv、.tsv 和 XML 电子表格。"
                    "请在 Excel 或 LibreOffice 中将其另存为 .xlsx 格式后再打开。"
                ).format(name=name)

    elif app == "lectern":
        if ole_fmt == "word97":
            guidance_msg = safe_tr(
                "“{name}”是 Word 97–2003 文档，而非 PowerPoint 演示文稿。"
                "Lectern 仅支持打开演示文稿。"
            ).format(name=name)
        elif ole_fmt == "excel97":
            guidance_msg = safe_tr(
                "“{name}”是 Excel 97–2003 工作簿，而非 PowerPoint 演示文稿。"
                "Lectern 仅支持打开演示文稿。"
            ).format(name=name)
        elif ext in ooxml_ppt_exts or (ext and ext not in {".ppt", ".pps", ".pot"}):
            is_disguised = True
            guidance_msg = safe_tr(
                "“{name}”是旧版二进制 PowerPoint 97–2003 演示文稿 (.ppt)，但扩展名为 {ext}。"
                "请先在 PowerPoint、Keynote、Google 幻灯片或 LibreOffice 中将其另存为 .pptx 格式。"
            ).format(name=name, ext=ext or safe_tr("其他"))
        else:
            guidance_msg = safe_tr(
                "“{name}”是旧版二进制 PowerPoint 97–2003 演示文稿 (.ppt)。"
                "Lectern 原生支持 .pptx 演示文稿。"
                "请在 PowerPoint 或 LibreOffice 中将其另存为 .pptx 格式后再打开。"
            ).format(name=name)

    else:
        guidance_msg = safe_tr(
            "“{name}”是旧版二进制 Office 97–2003 文件，当前模块无法直接读取。"
            "请先在现代 Office 软件中将其转换为新版 Open XML 格式后再打开。"
        ).format(name=name)

    return FileFormatInspection(
        is_ole=True,
        is_encrypted=False,
        ole_format=ole_fmt,
        ext=ext,
        is_disguised=is_disguised,
        guidance_title=guidance_title,
        guidance_message=guidance_msg,
    )



class InvalidPasswordError(ValueError):
    """The password does not open the document."""

    def __init__(self, message: str = "Invalid password") -> None:
        super().__init__(message)


def _office_file(raw: bytes) -> msoffcrypto.OfficeFile:
    try:
        return msoffcrypto.OfficeFile(io.BytesIO(raw))
    except Exception as err:  # unsupported or damaged container
        raise ValueError("Corrupted encrypted package") from err


def decrypt_package(
    data: bytes | str | Path,
    passcode: str = "",
    **kwargs: str,
) -> bytes:
    """Decrypt a password-protected OOXML package, returning the inner ZIP bytes.

    The HMAC integrity check is applied first. A few producers write packages whose
    HMAC does not verify although the content is intact; for those the package is
    decrypted without the check and accepted only if the result is a valid ZIP.

    Raises:
        InvalidPasswordError: the password is wrong (a ``ValueError`` subclass).
        ValueError: the container is damaged or uses an unsupported scheme.
    """
    password = kwargs.get("password", passcode) or ""
    raw = _to_bytes(data)
    if len(raw) < 512 or raw[:8] != CFB_SIGNATURE:
        raise ValueError("Corrupted encrypted package")

    if not password:
        raise InvalidPasswordError()

    def _run(verify: bool) -> bytes:
        office = _office_file(raw)
        office.load_key(password=password)
        out = io.BytesIO()
        office.decrypt(out, verify_integrity=verify)
        return out.getvalue()

    try:
        return _run(verify=True)
    except _msoff_errors.InvalidKeyError as err:
        if "integrity" not in str(err).lower():
            raise InvalidPasswordError() from err
        integrity_error: Exception = err
    except (_msoff_errors.FileFormatError, _msoff_errors.ParseError) as err:
        raise ValueError(f"Unsupported encryption: {err}") from err
    except Exception as err:
        raise ValueError(f"Corrupted encrypted package: {err}") from err

    # The password was right but the HMAC did not verify. Some producers write a bad
    # HMAC over intact content, so accept the package only if it decrypts to a ZIP
    # whose members all pass their CRC check.
    logger.warning("Encrypted package failed its integrity check: %s", integrity_error)
    try:
        payload = _run(verify=False)
    except _msoff_errors.InvalidKeyError as err:
        # Agile packages do not verify the password before the HMAC check, so a
        # wrong password surfaces as an integrity failure first and is only
        # recognised here, when the decrypted bytes are not a package.
        raise InvalidPasswordError() from err
    except Exception as err:
        raise ValueError(f"Corrupted encrypted package: {err}") from err
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            if zf.testzip() is not None:
                raise zipfile.BadZipFile("member CRC mismatch")
    except Exception as err:
        raise ValueError("Encrypted package is damaged or was tampered with") from err
    return payload


def encrypt_package(package_bytes: bytes, passcode: str = "", **kwargs: str) -> bytes:
    """Encrypt OOXML package bytes with Agile encryption (AES-256, SHA-512)."""
    from msoffcrypto.method.ecma376_agile import ECMA376Agile

    password = kwargs.get("password", passcode) or ""
    if not password:
        raise ValueError("A password is required to encrypt a document")
    return ECMA376Agile.encrypt(password, io.BytesIO(_pad_small_package(package_bytes)))


_MIN_ENCRYPTED_PACKAGE = 4096


def _pad_small_package(package: bytes) -> bytes:
    """Grow packages below 4 KiB with a ZIP archive comment.

    msoffcrypto-tool (6.1) writes ``EncryptedPackage`` streams smaller than the CFB
    mini-stream cutoff (4096 bytes) incorrectly, so tiny packages would not decrypt.
    A ZIP comment is ignored by every consumer and does not change any member.
    """
    if len(package) >= _MIN_ENCRYPTED_PACKAGE:
        return package
    eocd = package.rfind(b"PK\x05\x06")
    if eocd < 0 or eocd + 22 != len(package):  # not a ZIP, or it already has a comment
        return package
    pad = _MIN_ENCRYPTED_PACKAGE - len(package)
    return package[: eocd + 20] + struct.pack("<H", pad) + b" " * pad


def is_encrypted_legacy_binary(data: bytes | str | Path) -> bool:
    """True for an encrypted .xls / .doc / .ppt (binary 97-2003) document."""
    raw = _to_bytes(data)
    if raw[:8] != CFB_SIGNATURE:
        return False
    try:
        office = msoffcrypto.OfficeFile(io.BytesIO(raw))
        return office.format != "ooxml" and bool(office.is_encrypted())
    except Exception:
        return False


def decrypt_legacy_binary(data: bytes | str | Path, password: str | None = None) -> bytes:
    """Decrypt an encrypted .xls / .doc / .ppt, returning the plain binary document.

    With no password, Excel's built-in default password is tried, which opens
    workbooks that were only protected against modification.

    Raises:
        InvalidPasswordError: the password (or the default) does not open the file.
        ValueError: the encryption scheme is unsupported or the file is damaged.
    """
    raw = _to_bytes(data)
    office = _office_file(raw)
    try:
        office.load_key(password=password if password is not None else EXCEL_DEFAULT_PASSWORD)
        out = io.BytesIO()
        office.decrypt(out)
    except _msoff_errors.InvalidKeyError as err:
        raise InvalidPasswordError() from err
    except _msoff_errors.DecryptionError as err:
        if "password" in str(err).lower() or "key" in str(err).lower():
            raise InvalidPasswordError() from err
        raise ValueError(f"Cannot decrypt document: {err}") from err
    except (_msoff_errors.FileFormatError, _msoff_errors.ParseError) as err:
        raise ValueError(f"Unsupported encryption: {err}") from err
    return out.getvalue()
