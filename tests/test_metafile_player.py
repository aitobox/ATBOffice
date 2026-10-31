"""Tests for pure Python WMF/EMF metafile player and renderer."""

import struct

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter


def create_synthetic_wmf() -> bytes:
    """Build a minimal valid placeable WMF file with rectangle and text records."""
    # Placeable header (22 bytes)
    key = 0x9AC6CDD7
    hmf = 0
    left, top, right, bottom = 0, 0, 100, 100
    inch = 1440
    reserved = 0

    # Calculate checksum: XOR of the 10 16-bit words
    header_words = struct.pack("<IHhhhhHI", key, hmf, left, top, right, bottom, inch, reserved)
    words = struct.unpack("<10H", header_words)
    checksum = 0
    for w in words:
        checksum ^= w

    placeable_hdr = header_words + struct.pack("<H", checksum)

    # Standard WMF Header (18 bytes = 9 words)
    # file_type=1 (memory), header_size=9, version=0x0300, file_size (words)
    # num_objects=2, max_record_size, num_params=0
    # We will compute file_size and max_record_size after accumulating records
    records = bytearray()

    def add_rec(fn: int, params: bytes):
        size_words = 3 + len(params) // 2
        records.extend(struct.pack("<IH", size_words, fn) + params)

    # SETWINDOWORG: y=0, x=0
    add_rec(0x020B, struct.pack("<hh", 0, 0))
    # SETWINDOWEXT: y=100, x=100
    add_rec(0x020C, struct.pack("<hh", 100, 100))
    # CREATEPENINDIRECT: style=0, width=2, color=0x000000FF (Red in BGR)
    add_rec(0x02FA, struct.pack("<HhHH", 0, 2, 0x00FF, 0x0000))
    # SELECTOBJECT: index=0
    add_rec(0x012D, struct.pack("<H", 0))
    # CREATEBRUSHINDIRECT: style=0 (solid), color=0x0000FF00 (Green in BGR), hatch=0
    add_rec(0x02FC, struct.pack("<HIH", 0, 0x0000FF00, 0))
    # SELECTOBJECT: index=1
    add_rec(0x012D, struct.pack("<H", 1))
    # RECTANGLE: b=80, r=80, t=20, l=20
    add_rec(0x041B, struct.pack("<hhhh", 80, 80, 20, 20))
    # ELLIPSE: b=70, r=70, t=30, l=30
    add_rec(0x0418, struct.pack("<hhhh", 70, 70, 30, 30))
    # POLYGON: count=3, pts: (25, 25), (75, 25), (50, 75)
    add_rec(0x0324, struct.pack("<h", 3) + struct.pack("<6h", 25, 25, 75, 25, 50, 75))
    # EOF: fn=0x0000
    add_rec(0x0000, b"")

    total_words = 9 + len(records) // 2
    wmf_hdr = struct.pack("<HHHIHIH", 1, 9, 0x0300, total_words, 2, 32, 0)

    return placeable_hdr + wmf_hdr + bytes(records)


def create_synthetic_emf() -> bytes:
    """Build a minimal valid EMF file with EMR_HEADER, EMR_RECTANGLE, EMR_POLYGON16 and EMR_EOF."""
    records = bytearray()

    def add_rec(rec_type: int, payload: bytes):
        size = 8 + len(payload)
        # 4-byte align payload
        pad = (4 - (len(payload) % 4)) % 4
        size += pad
        records.extend(struct.pack("<II", rec_type, size) + payload + (b"\x00" * pad))

    # EMR_SETMAPMODE (17)
    add_rec(17, struct.pack("<I", 1))  # MM_TEXT
    # EMR_SELECTOBJECT (37): Stock BLACK_PEN (0x80000007)
    add_rec(37, struct.pack("<I", 0x80000007))
    # EMR_SELECTOBJECT (37): Stock LTGRAY_BRUSH (0x80000001)
    add_rec(37, struct.pack("<I", 0x80000001))
    # EMR_RECTANGLE (43): bounds left=10, top=10, right=90, bottom=90
    add_rec(43, struct.pack("<iiii", 10, 10, 90, 90))
    # EMR_ELLIPSE (42): bounds left=20, top=20, right=80, bottom=80
    add_rec(42, struct.pack("<iiii", 20, 20, 80, 80))
    # EMR_POLYGON16 (86): rclBounds (4*4), count=3, pts: (15, 15), (85, 15), (50, 85)
    poly_payload = (
        struct.pack("<iiii", 15, 15, 85, 85)
        + struct.pack("<I", 3)
        + struct.pack("<6h", 15, 15, 85, 15, 50, 85)
    )
    add_rec(86, poly_payload)
    # EMR_EOF (14): nPalEntries=0, offPalEntries=0, nSizeLast=0
    add_rec(14, struct.pack("<III", 0, 0, 0))

    # EMF Header: EMR_HEADER (type=1)
    # Header total size = 88 bytes
    header_size = 88
    total_bytes = header_size + len(records)
    num_records = 1 + 7  # header + 7 added records

    # rclBounds = (0, 0, 100, 100)
    # rclFrame = (0, 0, 2540, 2540)  # 25.4mm = 1 inch
    # dSignature = 0x464D4520 (' EMF')
    # nVersion = 0x00010000
    # nBytes = total_bytes
    # nRecords = num_records
    # nHandles = 5
    # sReserved = 0
    # nDescription = 0, offDescription = 0
    # nPalEntries = 0
    # szlDevice = (1920, 1080)
    # szlMillimeters = (508, 285)
    emf_hdr = (
        struct.pack("<II", 1, header_size)
        + struct.pack("<iiii", 0, 0, 100, 100)
        + struct.pack("<iiii", 0, 0, 2540, 2540)
        + struct.pack("<IIII", 0x464D4520, 0x00010000, total_bytes, num_records)
        + struct.pack("<HHII", 5, 0, 0, 0)
        + struct.pack("<I", 0)
        + struct.pack("<ii", 1920, 1080)
        + struct.pack("<ii", 508, 285)
    )

    return emf_hdr + bytes(records)


def test_import_metafile_player():
    from atboffice.vfs.metafile_player import (
        MetafilePlayer,
        is_emf,
        is_wmf,
    )

    assert MetafilePlayer is not None
    assert is_wmf is not None
    assert is_emf is not None


def test_format_detection():
    from atboffice.vfs.metafile_player import is_emf, is_wmf

    wmf_bytes = create_synthetic_wmf()
    emf_bytes = create_synthetic_emf()

    assert is_wmf(wmf_bytes) is True
    assert is_emf(wmf_bytes) is False

    assert is_emf(emf_bytes) is True
    assert is_wmf(emf_bytes) is False

    assert is_wmf(b"invalid data") is False
    assert is_emf(b"invalid data") is False
    assert is_wmf(b"") is False
    assert is_emf(b"") is False


def test_wmf_rendering():
    from atboffice.vfs.metafile_player import MetafilePlayer, render_metafile_to_image

    wmf_bytes = create_synthetic_wmf()

    img = render_metafile_to_image(wmf_bytes, kind="wmf", max_px=200)
    assert isinstance(img, QImage)
    assert img.width() > 0
    assert img.height() > 0
    assert not img.isNull()

    # Check player class direct invocation
    player = MetafilePlayer()
    out_img = QImage(120, 120, QImage.Format.Format_ARGB32)
    out_img.fill(0)
    p = QPainter(out_img)
    ok = player.play(wmf_bytes, p, QRectF(0, 0, 120, 120), kind="wmf")
    p.end()

    assert ok is True


def test_emf_rendering():
    from atboffice.vfs.metafile_player import render_metafile_to_image

    emf_bytes = create_synthetic_emf()

    img = render_metafile_to_image(emf_bytes, kind="emf", max_px=200)
    assert isinstance(img, QImage)
    assert img.width() > 0
    assert img.height() > 0
    assert not img.isNull()

    # Check player direct rendering to bytes (PNG)
    from atboffice.vfs.metafile_player import render_metafile_to_bytes

    png_bytes = render_metafile_to_bytes(emf_bytes, kind="emf", format="PNG", max_px=150)
    assert png_bytes is not None
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_invalid_and_corrupt_data():
    from atboffice.vfs.metafile_player import (
        MetafilePlayer,
        render_metafile_to_bytes,
        render_metafile_to_image,
    )

    assert render_metafile_to_image(b"") is None
    assert render_metafile_to_image(b"random gibberish string") is None
    assert render_metafile_to_bytes(b"short", max_px=100) is None

    player = MetafilePlayer()
    out_img = QImage(50, 50, QImage.Format.Format_ARGB32)
    p = QPainter(out_img)
    assert player.play(b"", p) is False
    assert player.play(b"truncate", p) is False
    p.end()


def test_dib_decoding_and_mask():
    from atboffice.vfs.metafile.dib import compose_mask_xor, decode_dib_to_image

    # 1. Test 24bpp DIB (BITMAPINFOHEADER)
    # 2x2 image, 24bpp, BI_RGB
    header_size = 40
    w, h = 2, 2
    bpp = 24
    stride = ((w * bpp + 31) // 32) * 4  # 8 bytes per row
    bmi = struct.pack("<iiHHIIiiII", w, h, 1, bpp, 0, stride * h, 0, 0, 0, 0)
    hdr = struct.pack("<I", header_size) + bmi
    # Row 0: Red, Green + 2 pad bytes. Row 1: Blue, White + 2 pad bytes.
    pixel_data = b"\x00\x00\xff\x00\xff\x00\x00\x00\xff\x00\x00\xff\xff\xff\x00\x00"
    dib_bytes = hdr + pixel_data
    img = decode_dib_to_image(dib_bytes, 0)
    assert img is not None
    assert img.width() == 2
    assert img.height() == 2

    # 2. Test 8bpp indexed DIB
    bpp8 = 8
    stride8 = ((w * bpp8 + 31) // 32) * 4  # 4 bytes per row
    bmi8 = struct.pack("<iiHHIIiiII", w, h, 1, bpp8, 0, stride8 * h, 0, 0, 2, 0)
    # Color 0=Black, 1=White
    pal8 = struct.pack("<4B", 0, 0, 0, 0) + struct.pack("<4B", 255, 255, 255, 0)
    pixel_data8 = b"\x00\x01\x00\x00\x01\x00\x00\x00"
    dib8_bytes = struct.pack("<I", header_size) + bmi8 + pal8 + pixel_data8
    img8 = decode_dib_to_image(dib8_bytes, 0)
    assert img8 is not None
    assert img8.width() == 2
    assert img8.height() == 2

    # 3. Test AND-mask + XOR composition
    mask_img = QImage(2, 2, QImage.Format.Format_ARGB32)
    mask_img.fill(QColor(255, 255, 255))  # White mask (transparent)
    xor_img = QImage(2, 2, QImage.Format.Format_ARGB32)
    xor_img.fill(QColor(0, 0, 0))  # Black background
    composed = compose_mask_xor(mask_img, xor_img, 2, 2, 2, 2)
    assert composed is not None
    assert composed.width() == 2
    assert composed.height() == 2


def test_wmf_without_placeable_header():
    from atboffice.vfs.metafile_player import is_wmf, render_metafile_to_image

    records = bytearray()

    def add_rec(fn: int, params: bytes):
        size_words = 3 + len(params) // 2
        records.extend(struct.pack("<IH", size_words, fn) + params)

    add_rec(0x020B, struct.pack("<hh", 0, 0))  # SETWINDOWORG
    add_rec(0x020C, struct.pack("<hh", 50, 50))  # SETWINDOWEXT
    add_rec(0x041B, struct.pack("<hhhh", 40, 40, 10, 10))  # RECTANGLE
    add_rec(0x0000, b"")  # EOF

    total_words = 9 + len(records) // 2
    wmf_hdr = struct.pack("<HHHIHIH", 1, 9, 0x0300, total_words, 1, 32, 0)
    raw_wmf = wmf_hdr + bytes(records)

    assert is_wmf(raw_wmf) is True
    img = render_metafile_to_image(raw_wmf, kind="wmf", max_px=100)
    assert img is not None
    assert img.width() > 0
    assert img.height() > 0


def test_metafile_dimensions_and_submodules():
    import atboffice.vfs.metafile.constants as constants
    import atboffice.vfs.metafile.dib as dib
    import atboffice.vfs.metafile.emf_parser as emf_parser
    import atboffice.vfs.metafile.player as player_mod
    import atboffice.vfs.metafile.state as state
    import atboffice.vfs.metafile.wmf_parser as wmf_parser
    from atboffice.vfs.metafile import (
        MetafilePlayer,
    )

    # Verify modular architecture
    assert constants is not None
    assert dib is not None
    assert emf_parser is not None
    assert player_mod is not None
    assert state is not None
    assert wmf_parser is not None

    wmf_bytes = create_synthetic_wmf()
    emf_bytes = create_synthetic_emf()

    player = MetafilePlayer()
    wmf_dims = player.get_dimensions(wmf_bytes, kind="wmf")
    assert wmf_dims is not None
    assert wmf_dims[0] > 0 and wmf_dims[1] > 0

    emf_dims = player.get_dimensions(emf_bytes, kind="emf")
    assert emf_dims is not None
    assert emf_dims[0] > 0 and emf_dims[1] > 0
