"""Device-Independent Bitmap (DIB) decoder and raster operations."""

from __future__ import annotations

import struct

from PySide6.QtGui import QImage


def decode_dib_to_image(
    data: bytes,
    off: int,
    bits_off: int | None = None,
    usage: int = 0,
    end: int | None = None,
    ext_pal: list[list[int]] | None = None,
) -> QImage | None:
    """Decode a Windows Device-Independent Bitmap (DIB) structure to a QImage."""
    try:
        if off + 4 > len(data):
            return None
        hs = struct.unpack_from("<I", data, off)[0]

        if hs == 12:
            # BITMAPCOREHEADER (OS/2 / Windows 2.x)
            if off + 12 > len(data):
                return None
            w, h_raw, planes, bpp = struct.unpack_from("<HHhH", data, off + 4)
            h = int(h_raw)
            comp = 0
            clr_used = 0
            pal_entry_size = 3
        else:
            # BITMAPINFOHEADER (Windows 3.x / NT)
            if off + 40 > len(data):
                return None
            (
                w,
                h,
                planes,
                bpp,
                comp,
                size_img,
                xpels,
                ypels,
                clr_used,
                clr_important,
            ) = struct.unpack_from("<iiHHIIiiII", data, off + 4)
            pal_entry_size = 4

        if not (w > 0) or not h or abs(h) > 20000 or w > 20000:
            return None
        if comp not in (0, 3):
            # Compressed formats like RLE, JPEG, PNG in DIB are not handled
            return None

        n_pal = (clr_used or (1 << bpp)) if bpp <= 8 else 0
        pal_off = off + hs + (12 if (comp == 3 and hs == 40) else 0)
        ah = abs(h)
        stride = ((w * bpp + 31) // 32) * 4

        # Check if color table is omitted
        no_table = (
            bits_off is None
            and end is not None
            and (pal_off + n_pal * pal_entry_size + stride * ah > end)
            and (pal_off + stride * ah <= end)
        )

        pal: list[list[int]] = []
        for i in range(n_pal):
            if no_table or usage == 1:
                q = ext_pal[i] if (ext_pal and i < len(ext_pal)) else [i, i, i]
                pal.append(q[:3])
                continue
            p = pal_off + i * pal_entry_size
            if p + 3 <= len(data):
                b = data[p]
                g = data[p + 1]
                r = data[p + 2]
                pal.append([r, g, b])
            else:
                pal.append([i, i, i])

        table_bytes = 0 if no_table else n_pal * pal_entry_size
        bits = bits_off if bits_off is not None else (pal_off + table_bytes)
        if bits + stride * ah > len(data) + stride:
            return None

        out_buf = bytearray(w * ah * 4)
        for row in range(ah):
            sy = (ah - 1 - row) if h > 0 else row
            rp = bits + sy * stride
            out_row_off = row * w * 4

            if bpp == 24:
                for col in range(w):
                    p = rp + col * 3
                    if p + 3 <= len(data):
                        b = data[p]
                        g = data[p + 1]
                        r = data[p + 2]
                    else:
                        r = g = b = 0
                    o = out_row_off + col * 4
                    out_buf[o] = r
                    out_buf[o + 1] = g
                    out_buf[o + 2] = b
                    out_buf[o + 3] = 255
            elif bpp == 32:
                for col in range(w):
                    p = rp + col * 4
                    if p + 4 <= len(data):
                        b = data[p]
                        g = data[p + 1]
                        r = data[p + 2]
                    else:
                        r = g = b = 0
                    o = out_row_off + col * 4
                    out_buf[o] = r
                    out_buf[o + 1] = g
                    out_buf[o + 2] = b
                    out_buf[o + 3] = 255
            elif bpp == 16:
                for col in range(w):
                    p = rp + col * 2
                    if p + 2 <= len(data):
                        v = data[p] | (data[p + 1] << 8)
                        r = ((v >> 10) & 31) << 3
                        g = ((v >> 5) & 31) << 3
                        b = (v & 31) << 3
                    else:
                        r = g = b = 0
                    o = out_row_off + col * 4
                    out_buf[o] = r
                    out_buf[o + 1] = g
                    out_buf[o + 2] = b
                    out_buf[o + 3] = 255
            elif bpp == 8:
                for col in range(w):
                    idx = data[rp + col] if (rp + col < len(data)) else 0
                    q = pal[idx] if idx < len(pal) else [0, 0, 0]
                    o = out_row_off + col * 4
                    out_buf[o] = q[0]
                    out_buf[o + 1] = q[1]
                    out_buf[o + 2] = q[2]
                    out_buf[o + 3] = 255
            elif bpp == 4:
                for col in range(w):
                    byte_val = data[rp + (col >> 1)] if (rp + (col >> 1) < len(data)) else 0
                    idx = (byte_val & 0x0F) if (col & 1) else (byte_val >> 4)
                    q = pal[idx] if idx < len(pal) else [0, 0, 0]
                    o = out_row_off + col * 4
                    out_buf[o] = q[0]
                    out_buf[o + 1] = q[1]
                    out_buf[o + 2] = q[2]
                    out_buf[o + 3] = 255
            elif bpp == 1:
                for col in range(w):
                    byte_val = data[rp + (col >> 3)] if (rp + (col >> 3) < len(data)) else 0
                    idx = (byte_val >> (7 - (col & 7))) & 1
                    q = pal[idx] if idx < len(pal) else [0, 0, 0]
                    o = out_row_off + col * 4
                    out_buf[o] = q[0]
                    out_buf[o + 1] = q[1]
                    out_buf[o + 2] = q[2]
                    out_buf[o + 3] = 255

        img = QImage(bytes(out_buf), w, ah, w * 4, QImage.Format.Format_RGBA8888).copy()
        return img
    except Exception:
        return None


def crop_image_to(
    src: QImage,
    sx: int,
    sy: int,
    sw: int,
    sh: int,
    target_w: int,
    target_h: int,
) -> QImage:
    """Crop a sub-rectangle from source image and scale to target dimensions."""
    src_w = src.width()
    src_h = src.height()
    safe_sx = max(0, sx)
    safe_sy = max(0, sy)
    safe_sw = max(1, min(abs(sw) or src_w, src_w - safe_sx))
    safe_sh = max(1, min(abs(sh) or src_h, src_h - safe_sy))

    cropped = src.copy(safe_sx, safe_sy, safe_sw, safe_sh)
    if cropped.width() == target_w and cropped.height() == target_h:
        return cropped
    return cropped.scaled(target_w, target_h)


def compose_mask_xor(
    mask_img: QImage,
    xor_img: QImage,
    sw: int,
    sh: int,
    msw: int,
    msh: int,
) -> QImage:
    """Compose GDI AND-mask + XOR-image pair into a 32-bit transparent RGBA image."""
    tw = max(abs(sw) or xor_img.width(), abs(msw) or mask_img.width())
    th = max(abs(sh) or xor_img.height(), abs(msh) or mask_img.height())

    fmt = QImage.Format.Format_RGBA8888
    mc = crop_image_to(mask_img, 0, 0, msw, msh, tw, th).convertToFormat(fmt)
    xc = crop_image_to(xor_img, 0, 0, sw, sh, tw, th).convertToFormat(fmt)

    mc_bytes = bytearray(mc.constBits().tobytes())
    xc_bytes = bytearray(xc.constBits().tobytes())

    total_pixels = tw * th
    for i in range(total_pixels):
        o = i * 4
        m_r, m_g, m_b = mc_bytes[o], mc_bytes[o + 1], mc_bytes[o + 2]
        x_r, x_g, x_b = xc_bytes[o], xc_bytes[o + 1], xc_bytes[o + 2]

        mask_dark = (m_r + m_g + m_b) < 384
        xor_black = (x_r + x_g + x_b) < 24

        xc_bytes[o + 3] = 255 if (mask_dark or not xor_black) else 0

    return QImage(bytes(xc_bytes), tw, th, tw * 4, QImage.Format.Format_RGBA8888).copy()
