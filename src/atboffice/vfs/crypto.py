"""ECMA-376 Part 2 Office Document Cryptography Engine.

Provides detection, decryption, and encryption for password-protected Microsoft
Office Open XML packages (.xlsx, .docx, .pptx) wrapped in OLE Compound File
Binary (CFB) containers.

Supports:
- Agile Encryption (Office 2010+, AES-128/256-CBC with SHA-1/256/384/512 and 100,000 spin count).
- Standard Encryption (Office 2007, AES-128/192/256-ECB with SHA-1 and 50,000 spin count).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
import os
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Final

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    _HAS_CRYPTOGRAPHY = True
except ImportError:
    _HAS_CRYPTOGRAPHY = False


def _xtime(b: int) -> int:
    return ((b << 1) ^ (0x1B if (b & 0x80) else 0)) & 0xFF


def _gmul(a: int, b: int) -> int:
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r


def _rotl8(x: int, n: int) -> int:
    return ((x << n) | (x >> (8 - n))) & 0xFF


_SBOX = bytearray(256)
_INV_SBOX = bytearray(256)
for _b in range(256):
    _inv = 1
    _sq = _b
    for _ in range(7):
        _sq = _gmul(_sq, _sq)
        _inv = _gmul(_inv, _sq)
    _s = _inv ^ _rotl8(_inv, 1) ^ _rotl8(_inv, 2) ^ _rotl8(_inv, 3) ^ _rotl8(_inv, 4) ^ 0x63
    _SBOX[_b] = _s
    _INV_SBOX[_s] = _b

_M2 = bytearray(_gmul(_i, 2) for _i in range(256))
_M3 = bytearray(_gmul(_i, 3) for _i in range(256))
_M9 = bytearray(_gmul(_i, 9) for _i in range(256))
_M11 = bytearray(_gmul(_i, 11) for _i in range(256))
_M13 = bytearray(_gmul(_i, 13) for _i in range(256))
_M14 = bytearray(_gmul(_i, 14) for _i in range(256))


def _expand_key(key: bytes) -> tuple[bytes, int]:
    nk = len(key) // 4
    nr = nk + 6
    w = bytearray(16 * (nr + 1))
    w[: len(key)] = key
    rcon = 1
    for i in range(nk, 4 * (nr + 1)):
        t0, t1, t2, t3 = w[4 * i - 4 : 4 * i]
        if i % nk == 0:
            t0, t1, t2, t3 = _SBOX[t1] ^ rcon, _SBOX[t2], _SBOX[t3], _SBOX[t0]
            rcon = _xtime(rcon)
        elif nk > 6 and i % nk == 4:
            t0, t1, t2, t3 = _SBOX[t0], _SBOX[t1], _SBOX[t2], _SBOX[t3]
        w[4 * i] = w[4 * (i - nk)] ^ t0
        w[4 * i + 1] = w[4 * (i - nk) + 1] ^ t1
        w[4 * i + 2] = w[4 * (i - nk) + 2] ^ t2
        w[4 * i + 3] = w[4 * (i - nk) + 3] ^ t3
    return bytes(w), nr


def _encrypt_block(w: bytes, nr: int, block: bytes) -> bytes:
    state = bytearray(block[i] ^ w[i] for i in range(16))
    t = bytearray(16)
    for rnd in range(1, nr):
        k = rnd * 16
        for c in range(4):
            t[4 * c] = _SBOX[state[4 * c]]
            t[4 * c + 1] = _SBOX[state[(4 * c + 5) % 16]]
            t[4 * c + 2] = _SBOX[state[(4 * c + 10) % 16]]
            t[4 * c + 3] = _SBOX[state[(4 * c + 15) % 16]]
        for c in range(4):
            a0, a1, a2, a3 = t[4 * c : 4 * c + 4]
            state[4 * c] = _M2[a0] ^ _M3[a1] ^ a2 ^ a3 ^ w[k + 4 * c]
            state[4 * c + 1] = a0 ^ _M2[a1] ^ _M3[a2] ^ a3 ^ w[k + 4 * c + 1]
            state[4 * c + 2] = a0 ^ a1 ^ _M2[a2] ^ _M3[a3] ^ w[k + 4 * c + 2]
            state[4 * c + 3] = _M3[a0] ^ a1 ^ a2 ^ _M2[a3] ^ w[k + 4 * c + 3]
    k = nr * 16
    out = bytearray(16)
    for c in range(4):
        out[4 * c] = _SBOX[state[4 * c]] ^ w[k + 4 * c]
        out[4 * c + 1] = _SBOX[state[(4 * c + 5) % 16]] ^ w[k + 4 * c + 1]
        out[4 * c + 2] = _SBOX[state[(4 * c + 10) % 16]] ^ w[k + 4 * c + 2]
        out[4 * c + 3] = _SBOX[state[(4 * c + 15) % 16]] ^ w[k + 4 * c + 3]
    return bytes(out)


def _decrypt_block(w: bytes, nr: int, block: bytes) -> bytes:
    state = bytearray(block[i] ^ w[nr * 16 + i] for i in range(16))
    t = bytearray(16)
    for rnd in range(nr - 1, -1, -1):
        for c in range(4):
            for r in range(4):
                t[r + 4 * c] = _INV_SBOX[state[r + 4 * ((c - r + 4) & 3)]]
        k = rnd * 16
        if rnd == 0:
            return bytes(t[i] ^ w[k + i] for i in range(16))
        for c in range(4):
            a0 = t[4 * c] ^ w[k + 4 * c]
            a1 = t[4 * c + 1] ^ w[k + 4 * c + 1]
            a2 = t[4 * c + 2] ^ w[k + 4 * c + 2]
            a3 = t[4 * c + 3] ^ w[k + 4 * c + 3]
            state[4 * c] = _M14[a0] ^ _M11[a1] ^ _M13[a2] ^ _M9[a3]
            state[4 * c + 1] = _M9[a0] ^ _M14[a1] ^ _M11[a2] ^ _M13[a3]
            state[4 * c + 2] = _M13[a0] ^ _M9[a1] ^ _M14[a2] ^ _M11[a3]
            state[4 * c + 3] = _M11[a0] ^ _M13[a1] ^ _M9[a2] ^ _M14[a3]
    return bytes(16)


# CFB constants
CFB_SIGNATURE: Final[bytes] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
SS: Final[int] = 512
MS: Final[int] = 64
CUTOFF: Final[int] = 4096
END: Final[int] = 0xFFFFFFFE
FREE: Final[int] = 0xFFFFFFFF
FATSEC: Final[int] = 0xFFFFFFFD
DIFSEC: Final[int] = 0xFFFFFFFC
NONE: Final[int] = 0xFFFFFFFF

# Office standard transform data spaces (hex)
DATA_SPACES: Final[dict[str, str]] = {
    "Version": (
        "3c0000004d006900630072006f0073006f00660074002e0043006f006e007400610069006e00"
        "650072002e004400610074006100530070006100630065007300010000000100000001000000"
    ),
    "DataSpaceMap": (
        "08000000010000006800000001000000000000002000000045006e0063007200790070007400"
        "650064005000610063006b00610067006500320000005300740072006f006e00670045006e00"
        "6300720079007000740069006f006e004400610074006100530070006100630065000000"
    ),
    "StrongEncryptionDataSpace": (
        "0800000001000000320000005300740072006f006e00670045006e0063007200790070007400"
        "69006f006e005400720061006e00730066006f0072006d000000"
    ),
    "Primary": (
        "58000000010000004c0000007b00460046003900410033004600300033002d00350036004500"
        "46002d0034003600310033002d0042004400440035002d003500410034003100430031004400"
        "300037003200340036007d004e0000004d006900630072006f0073006f00660074002e004300"
        "6f006e007400610069006e00650072002e0045006e006300720079007000740069006f006e00"
        "5400720061006e00730066006f0072006d000000010000000100000001000000000000000000"
        "00000000000004000000"
    ),
}

# Block derivation constants
B_IN: Final[bytes] = bytes([0xFE, 0xA7, 0xD2, 0x76, 0x3B, 0x4B, 0x9E, 0x79])
B_VAL: Final[bytes] = bytes([0xD7, 0xAA, 0x0F, 0x6D, 0x30, 0x61, 0x34, 0x4E])
B_KEY: Final[bytes] = bytes([0x14, 0x6E, 0x0B, 0xE7, 0xAB, 0xAC, 0xD0, 0xD6])

HASH_MAP: Final[dict[str, str]] = {
    "SHA1": "sha1",
    "SHA-1": "sha1",
    "SHA256": "sha256",
    "SHA-256": "sha256",
    "SHA384": "sha384",
    "SHA-384": "sha384",
    "SHA512": "sha512",
    "SHA-512": "sha512",
}


def _to_bytes(data: bytes | str | Path) -> bytes:
    """Normalize input parameter to bytes."""
    if isinstance(data, (str, Path)):
        with open(data, "rb") as f:
            return f.read()
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data)
    raise TypeError(f"Expected bytes, str, or Path, got {type(data).__name__}")


def _fix(h: bytes, n: int, pad: int = 0x36) -> bytes:
    """Truncate or pad hash output to exact n bytes."""
    if len(h) >= n:
        return h[:n]
    return h + bytes([pad] * (n - len(h)))


def _spin(alg: str, salt: bytes, password: str, count: int) -> bytes:
    """Iterate password hash spinCount times."""
    pw_bytes = password.encode("utf-16le")
    h = hashlib.new(alg, salt + pw_bytes).digest()
    for i in range(count):
        h = hashlib.new(alg, struct.pack("<I", i) + h).digest()
    return h


def _aes_cbc_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """Encrypt data using AES-CBC, zero-padding to 16 bytes if necessary."""
    padded = data
    if len(data) % 16 != 0:
        padded = data + bytes(16 - (len(data) % 16))
    if _HAS_CRYPTOGRAPHY:
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        return encryptor.update(padded) + encryptor.finalize()

    w, nr = _expand_key(key)
    out = bytearray(len(padded))
    prev = iv
    for p in range(0, len(padded), 16):
        block = bytes(padded[p + i] ^ prev[i] for i in range(16))
        enc_b = _encrypt_block(w, nr, block)
        out[p : p + 16] = enc_b
        prev = enc_b
    return bytes(out)


def _aes_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """Decrypt data using AES-CBC without unpadding."""
    if len(data) % 16 != 0:
        data = data + bytes(16 - (len(data) % 16))
    if _HAS_CRYPTOGRAPHY:
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()

    w, nr = _expand_key(key)
    out = bytearray(len(data))
    for p in range(0, len(data), 16):
        block = data[p : p + 16]
        dec_b = _decrypt_block(w, nr, block)
        prev = iv if p == 0 else data[p - 16 : p]
        out[p : p + 16] = bytes(dec_b[i] ^ prev[i] for i in range(16))
    return bytes(out)


def _aes_ecb_decrypt(key: bytes, data: bytes) -> bytes:
    """Decrypt data using AES-ECB without unpadding."""
    if len(data) % 16 != 0:
        data = data + bytes(16 - (len(data) % 16))
    if _HAS_CRYPTOGRAPHY:
        cipher = Cipher(algorithms.AES(key), modes.ECB())
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()

    w, nr = _expand_key(key)
    out = bytearray(len(data))
    for p in range(0, len(data), 16):
        block = data[p : p + 16]
        out[p : p + 16] = _decrypt_block(w, nr, block)
    return bytes(out)


class _CFBEntry:
    def __init__(
        self,
        name: str,
        entry_type: int,
        data: bytes = b"",
        left: int | None = None,
        right: int | None = None,
        child: int | None = None,
    ) -> None:
        self.name = name
        self.entry_type = entry_type
        self.data = data
        self.left = left
        self.right = right
        self.child = child
        self.mini: bool = False
        self.start: int = END


def _cfb_write(info: bytes, pkg: bytes) -> bytes:
    """Serialize EncryptionInfo and EncryptedPackage streams into an OLE CFB file."""
    entries = [
        _CFBEntry("Root Entry", 5, child=1),
        _CFBEntry("EncryptionInfo", 2, data=info, left=2, right=3),
        _CFBEntry("\u0006DataSpaces", 1, child=5),
        _CFBEntry("EncryptedPackage", 2, data=pkg),
        _CFBEntry("Version", 2, data=bytes.fromhex(DATA_SPACES["Version"])),
        _CFBEntry(
            "DataSpaceMap", 2, data=bytes.fromhex(DATA_SPACES["DataSpaceMap"]), left=4, right=6
        ),
        _CFBEntry("DataSpaceInfo", 1, child=7, right=8),
        _CFBEntry(
            "StrongEncryptionDataSpace",
            2,
            data=bytes.fromhex(DATA_SPACES["StrongEncryptionDataSpace"]),
        ),
        _CFBEntry("TransformInfo", 1, child=9),
        _CFBEntry("StrongEncryptionTransform", 1, child=10),
        _CFBEntry("\u0006Primary", 2, data=bytes.fromhex(DATA_SPACES["Primary"])),
    ]

    mini_parts: list[_CFBEntry] = []
    mini_len = 0
    for e in entries:
        if e.entry_type == 2 and len(e.data) < CUTOFF:
            e.mini = True
            e.start = mini_len // MS if len(e.data) else END
            mini_parts.append(e)
            mini_len += math.ceil(len(e.data) / MS) * MS

    n_mini = mini_len // MS
    mini_fat_secs = math.ceil((n_mini * 4) / SS)
    mini_stream_secs = math.ceil(mini_len / SS)
    dir_secs = math.ceil(len(entries) / 4)
    big = [e for e in entries if e.entry_type == 2 and not e.mini]
    big_secs = sum(math.ceil(len(e.data) / SS) for e in big)

    fat_secs = 1
    dif_secs = 0
    for _ in range(20):
        total = dif_secs + fat_secs + dir_secs + mini_fat_secs + mini_stream_secs + big_secs
        f = math.ceil(total / (SS // 4))
        d = math.ceil((f - 109) / (SS // 4 - 1)) if f > 109 else 0
        if f == fat_secs and d == dif_secs:
            break
        fat_secs = f
        dif_secs = d
    total = dif_secs + fat_secs + dir_secs + mini_fat_secs + mini_stream_secs + big_secs

    out = bytearray(SS * (1 + total))
    fat = [FREE] * (fat_secs * (SS // 4))
    next_sec = 0

    def run(count: int, mark: int | None = None) -> int:
        nonlocal next_sec
        start = next_sec
        for i in range(count):
            fat[next_sec + i] = (
                mark if mark is not None else (END if i == count - 1 else next_sec + i + 1)
            )
        next_sec += count
        return start if count else END

    dif_start = run(dif_secs, DIFSEC)
    fat_start = run(fat_secs, FATSEC)
    dir_start = run(dir_secs)
    mini_fat_start = run(mini_fat_secs)
    mini_stream_start = run(mini_stream_secs)
    for e in big:
        n = math.ceil(len(e.data) / SS)
        e.start = run(n)

    def at(sec: int) -> int:
        return SS * (sec + 1)

    # Header
    out[0:8] = CFB_SIGNATURE
    struct.pack_into("<HHH", out, 0x18, 0x3E, 3, 0xFFFE)
    struct.pack_into("<HH", out, 0x1E, 9, 6)
    struct.pack_into(
        "<IIIIII",
        out,
        0x2C,
        fat_secs,
        dir_start,
        0,
        CUTOFF,
        mini_fat_start if mini_fat_secs else END,
        mini_fat_secs,
    )
    struct.pack_into("<II", out, 0x44, dif_start if dif_secs else END, dif_secs)
    for i in range(109):
        struct.pack_into("<I", out, 0x4C + 4 * i, fat_start + i if i < fat_secs else FREE)

    for k in range(dif_secs):
        b = at(dif_start + k)
        per = SS // 4 - 1
        for i in range(per):
            idx = 109 + k * per + i
            struct.pack_into("<I", out, b + 4 * i, fat_start + idx if idx < fat_secs else FREE)
        struct.pack_into("<I", out, b + 4 * per, dif_start + k + 1 if k + 1 < dif_secs else END)

    # FAT
    for i, val in enumerate(fat):
        struct.pack_into("<I", out, at(fat_start) + 4 * i, val)

    # MiniFAT and MiniStream
    mf = [FREE] * (mini_fat_secs * (SS // 4))
    for e in mini_parts:
        n = math.ceil(len(e.data) / MS)
        for i in range(n):
            mf[e.start + i] = END if i == n - 1 else e.start + i + 1
        out[
            at(mini_stream_start) + e.start * MS : at(mini_stream_start)
            + e.start * MS
            + len(e.data)
        ] = e.data

    for i, val in enumerate(mf):
        struct.pack_into("<I", out, at(mini_fat_start) + 4 * i, val)

    # Big streams
    for e in big:
        out[at(e.start) : at(e.start) + len(e.data)] = e.data

    # Directory entries
    for i in range(dir_secs * 4):
        b = at(dir_start) + 128 * i
        if i >= len(entries):
            struct.pack_into("<III", out, b + 68, NONE, NONE, NONE)
            continue
        entry = entries[i]
        name_bytes = entry.name.encode("utf-16le")
        out[b : b + len(name_bytes)] = name_bytes
        struct.pack_into("<H", out, b + 64, len(name_bytes) + 2)
        out[b + 66] = entry.entry_type
        out[b + 67] = 1
        struct.pack_into(
            "<III",
            out,
            b + 68,
            entry.left if entry.left is not None else NONE,
            entry.right if entry.right is not None else NONE,
            entry.child if entry.child is not None else NONE,
        )
        if entry.entry_type == 5:
            struct.pack_into("<II", out, b + 116, mini_stream_start if mini_len else END, mini_len)
        elif entry.entry_type == 2:
            struct.pack_into(
                "<II", out, b + 116, entry.start if len(entry.data) else END, len(entry.data)
            )

    return bytes(out)


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


def is_encrypted_package(data: bytes | str | Path) -> bool:
    """Return True if data represents an encrypted Office package CFB container."""
    try:
        raw = _to_bytes(data)
        if len(raw) < 512:
            return False
        if raw[:8] != CFB_SIGNATURE:
            return False
        reader = CFBReader(raw)
        return reader.has_stream("EncryptionInfo") and reader.has_stream("EncryptedPackage")
    except Exception:
        return False


def _decrypt_agile(info: bytes, pkg: bytes, password: str) -> bytes:
    """Decrypt package using ECMA-376 Agile encryption (AES + SHA)."""
    xml_str = info[8:].decode("utf-8", errors="ignore")
    try:
        root = ET.fromstring(xml_str)
    except Exception as err:
        raise ValueError("Corrupted Agile encryption metadata") from err

    kd = None
    ek = None
    for elem in root.iter():
        local_name = elem.tag.split("}")[-1]
        if local_name == "keyData":
            kd = elem
        elif local_name == "encryptedKey" and "spinCount" in elem.attrib:
            ek = elem

    if kd is None or ek is None:
        raise ValueError("Unsupported or corrupted Agile encryption metadata")

    alg = HASH_MAP.get(ek.attrib.get("hashAlgorithm", "SHA-1").upper(), "sha1")
    key_bytes = int(ek.attrib.get("keyBits", 128)) // 8
    salt = base64.b64decode(ek.attrib["saltValue"])
    spin_count = int(ek.attrib.get("spinCount", 100000))

    H = _spin(alg, salt, password, spin_count)

    def derive(block: bytes) -> bytes:
        return _fix(hashlib.new(alg, H + block).digest(), key_bytes, 0x36)

    enc_in = base64.b64decode(ek.attrib["encryptedVerifierHashInput"])
    enc_val = base64.b64decode(ek.attrib["encryptedVerifierHashValue"])

    vin = _aes_cbc_decrypt(derive(B_IN), salt, enc_in)
    vval = _aes_cbc_decrypt(derive(B_VAL), salt, enc_val)

    salt_size = int(ek.attrib.get("saltSize", 16))
    vin2 = vin[:salt_size]
    vh = hashlib.new(alg, vin2).digest()
    if vh != vval[: len(vh)]:
        raise ValueError("Invalid password")

    enc_key = base64.b64decode(ek.attrib["encryptedKeyValue"])
    secret_raw = _aes_cbc_decrypt(derive(B_KEY), salt, enc_key)
    kd_key_bits = int(kd.attrib.get("keyBits", 128))
    secret = secret_raw[: kd_key_bits // 8]

    size = struct.unpack_from("<Q", pkg, 0)[0]
    kd_salt = base64.b64decode(kd.attrib["saltValue"])
    kd_alg = HASH_MAP.get(kd.attrib.get("hashAlgorithm", "SHA-1").upper(), alg)
    bs = int(kd.attrib.get("blockSize", 16))

    out = bytearray(math.ceil((len(pkg) - 8) / 16) * 16)
    seg = 0
    p = 8
    while p < len(pkg):
        chunk_len = min(len(pkg) - p, 4096)
        chunk = pkg[p : p + chunk_len]
        if len(chunk) % 16 != 0:
            chunk = chunk + bytes(16 - (len(chunk) % 16))
        iv = _fix(hashlib.new(kd_alg, kd_salt + struct.pack("<I", seg)).digest(), bs, 0x36)
        dec_chunk = _aes_cbc_decrypt(secret, iv, chunk)
        out[p - 8 : p - 8 + len(dec_chunk)] = dec_chunk
        seg += 1
        p += 4096

    return bytes(out[:size])


def _decrypt_standard(info: bytes, pkg: bytes, password: str) -> bytes:
    """Decrypt package using Office 2007 Standard encryption (AES-ECB + SHA-1)."""
    if len(info) < 24:
        raise ValueError("Corrupted standard encryption header")
    h_size = struct.unpack_from("<I", info, 8)[0]
    h = 12
    if len(info) < h + 20:
        raise ValueError("Corrupted standard encryption header")
    alg_id = struct.unpack_from("<I", info, h + 8)[0]
    key_bits = struct.unpack_from("<I", info, h + 16)[0] or 128
    if alg_id != 0 and alg_id not in (0x660E, 0x660F, 0x6610):
        raise ValueError(f"Unsupported standard cipher algID {hex(alg_id)}")
    v = h + h_size
    if len(info) < v + 4:
        raise ValueError("Corrupted standard encryption header")
    salt_size = struct.unpack_from("<I", info, v)[0]
    salt = info[v + 4 : v + 4 + salt_size]
    enc_verifier = info[v + 4 + salt_size : v + 20 + salt_size]
    enc_verifier_hash = info[v + 24 + salt_size : v + 24 + salt_size + 32]

    hh = _spin("sha1", salt, password, 50000)
    hh = hashlib.sha1(hh + struct.pack("<I", 0)).digest()
    x1 = bytearray(b"\x36" * 64)
    x2 = bytearray(b"\x5c" * 64)
    for i in range(len(hh)):
        x1[i] ^= hh[i]
        x2[i] ^= hh[i]
    k = hashlib.sha1(x1).digest() + hashlib.sha1(x2).digest()
    key = k[: key_bits // 8]

    ver = _aes_ecb_decrypt(key, enc_verifier)
    ver_hash = _aes_ecb_decrypt(key, enc_verifier_hash)[:20]
    if hashlib.sha1(ver).digest() != ver_hash:
        raise ValueError("Invalid password")

    size = struct.unpack_from("<Q", pkg, 0)[0]
    decrypted = _aes_ecb_decrypt(key, pkg[8:])
    return decrypted[:size]


def decrypt_package(data: bytes | str | Path, password: str) -> bytes:
    """Decrypt an encrypted Office package, returning inner OOXML ZIP bytes."""
    raw = _to_bytes(data)
    if len(raw) < 512 or raw[:8] != CFB_SIGNATURE:
        raise ValueError("Corrupted encrypted package")

    try:
        reader = CFBReader(raw)
        info = reader.get_stream("EncryptionInfo")
        pkg = reader.get_stream("EncryptedPackage")
    except Exception as err:
        raise ValueError("Corrupted encrypted package") from err

    if not info or not pkg or len(info) < 8 or len(pkg) < 8:
        raise ValueError("Corrupted encrypted package")

    major = info[0] | (info[1] << 8)
    minor = info[2] | (info[3] << 8)

    if major == 4 and minor == 4:
        return _decrypt_agile(info, pkg, password)
    if (major == 3 or major == 4) and minor == 2:
        return _decrypt_standard(info, pkg, password)
    raise ValueError(f"Unsupported encryption version {major}.{minor}")


def encrypt_package(package_bytes: bytes, password: str, agile: bool = True) -> bytes:
    """Encrypt package bytes with password into an OLE CFB encrypted package container."""
    alg = "sha512"
    key_data_salt = os.urandom(16)
    pw_salt = os.urandom(16)
    secret = os.urandom(32)
    verifier = os.urandom(16)
    hmac_key = os.urandom(64)

    enc_len = 8 + math.ceil(len(package_bytes) / 16) * 16
    enc = bytearray(enc_len)
    struct.pack_into("<Q", enc, 0, len(package_bytes))

    for seg in range(0, math.ceil(len(package_bytes) / 4096) or 1):
        p = seg * 4096
        if p >= len(package_bytes) and len(package_bytes) > 0:
            break
        chunk = package_bytes[p : min(len(package_bytes), p + 4096)]
        iv = _fix(hashlib.sha512(key_data_salt + struct.pack("<I", seg)).digest(), 16, 0x36)
        enc_chunk = _aes_cbc_encrypt(secret, iv, chunk)
        enc[8 + p : 8 + p + len(enc_chunk)] = enc_chunk

    H = _spin(alg, pw_salt, password, 100000)

    def derive(block: bytes) -> bytes:
        return _fix(hashlib.sha512(H + block).digest(), 32, 0x36)

    enc_in = _aes_cbc_encrypt(derive(B_IN), pw_salt, verifier)
    enc_val = _aes_cbc_encrypt(derive(B_VAL), pw_salt, hashlib.sha512(verifier).digest())
    enc_key = _aes_cbc_encrypt(derive(B_KEY), pw_salt, secret)

    iv_hk = _fix(
        hashlib.sha512(
            key_data_salt + bytes([0x5F, 0xB2, 0xAD, 0x01, 0x0C, 0xB9, 0xE1, 0xF6])
        ).digest(),
        16,
        0x36,
    )
    iv_hv = _fix(
        hashlib.sha512(
            key_data_salt + bytes([0xA0, 0x67, 0x7F, 0x02, 0xB2, 0x2C, 0x84, 0x33])
        ).digest(),
        16,
        0x36,
    )

    mac = hmac.new(hmac_key, enc, hashlib.sha512).digest()
    enc_hmac_key = _aes_cbc_encrypt(secret, iv_hk, hmac_key)
    enc_hmac_val = _aes_cbc_encrypt(secret, iv_hv, mac)

    def b64e(b: bytes) -> str:
        return base64.b64encode(b).decode("ascii")

    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
        '<encryption xmlns="http://schemas.microsoft.com/office/2006/encryption" '
        'xmlns:p="http://schemas.microsoft.com/office/2006/keyEncryptor/password" '
        'xmlns:c="http://schemas.microsoft.com/office/2006/keyEncryptor/certificate">'
        f'<keyData saltSize="16" blockSize="16" keyBits="256" hashSize="64" '
        f'cipherAlgorithm="AES" cipherChaining="ChainingModeCBC" hashAlgorithm="SHA512" '
        f'saltValue="{b64e(key_data_salt)}"/>'
        f'<dataIntegrity encryptedHmacKey="{b64e(enc_hmac_key)}" '
        f'encryptedHmacValue="{b64e(enc_hmac_val)}"/>'
        '<keyEncryptors><keyEncryptor uri="http://schemas.microsoft.com/office/2006/keyEncryptor/password">'
        f'<p:encryptedKey spinCount="100000" saltSize="16" blockSize="16" keyBits="256" '
        'hashSize="64" cipherAlgorithm="AES" cipherChaining="ChainingModeCBC" '
        'hashAlgorithm="SHA512" '
        f'saltValue="{b64e(pw_salt)}" encryptedVerifierHashInput="{b64e(enc_in)}" '
        f'encryptedVerifierHashValue="{b64e(enc_val)}" encryptedKeyValue="{b64e(enc_key)}"/>'
        "</keyEncryptor></keyEncryptors></encryption>"
    )
    xb = xml.encode("utf-8")
    info = bytearray(8 + len(xb))
    info[0:8] = bytes([4, 0, 4, 0, 0x40, 0, 0, 0])
    info[8:] = xb

    return _cfb_write(bytes(info), bytes(enc))
