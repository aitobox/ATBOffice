"""Visual difference and similarity scoring engine for rendered office documents."""
# ruff: noqa: E402, E501

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import numpy as np  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - exercised in CI/no-numpy tests
    np = None  # type: ignore[assignment]

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from .models import DiffResult


@dataclass(frozen=True)
class ForegroundMetrics:
    """Foreground-weighted visual similarity metrics between two canvases."""

    recall: float
    precision: float
    color_hist_similarity: float
    color_hist_distance: float
    foreground_score: float
    fg_pixels_a: int
    fg_pixels_b: int


@dataclass(frozen=True)
class _RgbGrid:
    """Pure-Python fallback representation of a contiguous RGB image."""

    width: int
    height: int
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def shape(self) -> tuple[int, int, int]:
        return (self.height, self.width, 3)

    def crop(self, y0: int, y1: int, x0: int, x1: int) -> _RgbGrid:
        """Return a cropped RGB sub-grid covering [y0:y1, x0:x1]."""
        nw = max(0, x1 - x0)
        nh = max(0, y1 - y0)
        if nw == 0 or nh == 0:
            return _RgbGrid(0, 0, b"")
        stride = self.width * 3
        chunks = [
            self.data[y * stride + x0 * 3 : y * stride + x1 * 3] for y in range(y0, y1)
        ]
        return _RgbGrid(nw, nh, b"".join(chunks))


def _is_numpy_array(obj: Any) -> bool:
    return np is not None and isinstance(obj, np.ndarray)


def qimage_to_rgb_array(img: QImage) -> Any:
    """Convert a QImage into a contiguous (H, W, 3) uint8 RGB array or _RgbGrid."""
    if img.isNull() or img.width() == 0 or img.height() == 0:
        if np is not None:
            return np.zeros((0, 0, 3), dtype=np.uint8)
        return _RgbGrid(0, 0, b"")

    rgb_img = img.convertToFormat(QImage.Format.Format_RGB888)
    w, h = rgb_img.width(), rgb_img.height()
    bpl = rgb_img.bytesPerLine()
    raw = bytes(rgb_img.constBits())[: h * bpl]

    if np is not None:
        buf = np.frombuffer(raw, dtype=np.uint8, count=h * bpl)
        return buf.reshape(h, bpl)[:, : w * 3].reshape(h, w, 3).copy()

    if bpl == w * 3:
        return _RgbGrid(w, h, raw)
    rows = [raw[y * bpl : y * bpl + w * 3] for y in range(h)]
    return _RgbGrid(w, h, b"".join(rows))


def detect_background_color(rgb: Any) -> tuple[Any, float]:
    """Detect the dominant background color of an RGB image via 5-bit color binning."""
    if _is_numpy_array(rgb):
        if rgb.size == 0:
            return np.array([255.0, 255.0, 255.0], dtype=np.float64), 1.0
        pixels = rgb.reshape(-1, 3)
        q = (pixels >> 3).astype(np.int32)
        code = (q[:, 0] << 10) | (q[:, 1] << 5) | q[:, 2]
        bc = np.bincount(code, minlength=32768)
        best = int(np.argmax(bc))
        mask = code == best
        mean_rgb = pixels[mask].mean(axis=0).astype(np.float64)
        frac = float(bc[best]) / float(len(pixels))
        return mean_rgb, frac

    data: bytes = rgb.data
    n_px = len(data) // 3
    if n_px == 0:
        return (255.0, 255.0, 255.0), 1.0
    counts: dict[int, int] = {}
    sums: dict[int, list[int]] = {}
    for i in range(0, len(data), 3):
        r, g, b = data[i], data[i + 1], data[i + 2]
        code = ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)
        counts[code] = counts.get(code, 0) + 1
        acc = sums.get(code)
        if acc is None:
            sums[code] = [r, g, b]
        else:
            acc[0] += r
            acc[1] += g
            acc[2] += b
    best_code = max(counts, key=lambda k: counts[k])
    best_cnt = counts[best_code]
    sr, sg, sb = sums[best_code]
    return (sr / best_cnt, sg / best_cnt, sb / best_cnt), best_cnt / float(n_px)


def _crop_desk_framed_canvas(
    ia: Any,
    ib: Any,
    desk_sample_a: Any,
    desk_sample_b: Any,
) -> tuple[Any, Any]:
    """Crop outer desk backdrop to page/slide interior when desk framing is detected."""
    desk_a, frac_a = detect_background_color(desk_sample_a)
    desk_b, frac_b = detect_background_color(desk_sample_b)
    if frac_a <= 0.5 or frac_b <= 0.5:
        return ia, ib

    if _is_numpy_array(ia):
        pa = np.max(np.abs(ia.astype(np.int16) - desk_a), axis=2) > 25
        pb = np.max(np.abs(ib.astype(np.int16) - desk_b), axis=2) > 25
        area = float(ia.shape[0] * ia.shape[1])
        if pa.sum() < 0.15 * area or pb.sum() < 0.15 * area:
            return ia, ib
        bg_inner_a, _ = detect_background_color(ia[pa])
        bg_inner_b, _ = detect_background_color(ib[pb])
        if np.max(np.abs(bg_inner_a - desk_a)) <= 25 or np.max(np.abs(bg_inner_b - desk_b)) <= 25:
            return ia, ib
        ysa, xsa = np.where(pa)
        ysb, xsb = np.where(pb)
        ya0, ya1, xa0, xa1 = int(ysa.min()) + 6, int(ysa.max()) - 6, int(xsa.min()) + 6, int(xsa.max()) - 6
        yb0, yb1, xb0, xb1 = int(ysb.min()) + 6, int(ysb.max()) - 6, int(xsb.min()) + 6, int(xsb.max()) - 6
        pw = min(xa1 - xa0, xb1 - xb0)
        ph = min(ya1 - ya0, yb1 - yb0)
        if pw <= 100 or ph <= 100:
            return ia, ib
        if abs(ya0 - yb0) <= 15 and abs(xa0 - xb0) <= 15:
            return ia[ya0 : ya0 + ph, xa0 : xa0 + pw], ib[yb0 : yb0 + ph, xb0 : xb0 + pw]
        return ia, ib

    def _find_non_desk(grid: _RgbGrid, desk: tuple[float, float, float]) -> tuple[int, int, int, int, int, bytes]:
        dr0, dg0, db0 = desk
        w, h, data = grid.width, grid.height, grid.data
        x_min, y_min, x_max, y_max = w, h, -1, -1
        cnt = 0
        inner_bytes = bytearray()
        for y in range(h):
            row_off = y * w * 3
            for x in range(w):
                idx = row_off + x * 3
                r, g, b = data[idx], data[idx + 1], data[idx + 2]
                if max(abs(r - dr0), abs(g - dg0), abs(b - db0)) > 25:
                    cnt += 1
                    inner_bytes.extend((r, g, b))
                    if x < x_min:
                        x_min = x
                    if x > x_max:
                        x_max = x
                    if y < y_min:
                        y_min = y
                    if y > y_max:
                        y_max = y
        return cnt, x_min, y_min, x_max, y_max, bytes(inner_bytes)

    area = float(ia.width * ia.height)
    ca, xa0, ya0, xa1, ya1, ba = _find_non_desk(ia, desk_a)
    cb, xb0, yb0, xb1, yb1, bb = _find_non_desk(ib, desk_b)
    if ca < 0.15 * area or cb < 0.15 * area:
        return ia, ib
    bg_inner_a, _ = detect_background_color(_RgbGrid(ca, 1, ba))
    bg_inner_b, _ = detect_background_color(_RgbGrid(cb, 1, bb))
    if max(abs(bg_inner_a[i] - desk_a[i]) for i in range(3)) <= 25:
        return ia, ib
    if max(abs(bg_inner_b[i] - desk_b[i]) for i in range(3)) <= 25:
        return ia, ib
    ya0, ya1, xa0, xa1 = ya0 + 6, ya1 - 6, xa0 + 6, xa1 - 6
    yb0, yb1, xb0, xb1 = yb0 + 6, yb1 - 6, xb0 + 6, xb1 - 6
    pw = min(xa1 - xa0, xb1 - xb0)
    ph = min(ya1 - ya0, yb1 - yb0)
    if pw <= 100 or ph <= 100:
        return ia, ib
    if abs(ya0 - yb0) <= 15 and abs(xa0 - xb0) <= 15:
        return ia.crop(ya0, ya0 + ph, xa0, xa0 + pw), ib.crop(yb0, yb0 + ph, xb0, xb0 + pw)
    return ia, ib


def extract_comparable_canvases(
    rgb_a: Any,
    rgb_b: Any,
    app: str = "office",
) -> tuple[Any, Any]:
    """Strip asymmetric viewport chrome (rulers, notes pane, desk) when present."""
    if _is_numpy_array(rgb_a) and _is_numpy_array(rgb_b):
        if rgb_a.shape != rgb_b.shape or rgb_a.ndim != 3:
            return rgb_a, rgb_b
        h, w, _ = rgb_a.shape
        if w < 800 or h < 600:
            return rgb_a, rgb_b
        if app == "word":
            ia = rgb_a[30 : h - 24, 24 : w - 20]
            ib = rgb_b[30 : h - 24, 24 : w - 20]
            return _crop_desk_framed_canvas(ia, ib, ia[:, :20], ib[:, :20])
        if app == "powerpoint" and h >= 650:
            bottom_b = rgb_b[648:, :, :]
            if int(np.ptp(bottom_b)) <= 10:
                ia = rgb_a[:646, :]
                ib = rgb_b[:646, :]
                return _crop_desk_framed_canvas(ia, ib, ia[:20, :], ib[:20, :])
            return _crop_desk_framed_canvas(rgb_a, rgb_b, rgb_a[:20, :], rgb_b[:20, :])
        if app == "excel":
            top_a_bg, _ = detect_background_color(rgb_a[:20, :])
            if float(np.mean(top_a_bg)) < 248.0:
                return rgb_a[22 : h - 24, 45 : w - 18], rgb_b[22 : h - 24, 45 : w - 18]
        return rgb_a, rgb_b

    if isinstance(rgb_a, _RgbGrid) and isinstance(rgb_b, _RgbGrid):
        if rgb_a.shape != rgb_b.shape:
            return rgb_a, rgb_b
        h, w = rgb_a.height, rgb_a.width
        if w < 800 or h < 600:
            return rgb_a, rgb_b
        if app == "word":
            ia = rgb_a.crop(30, h - 24, 24, w - 20)
            ib = rgb_b.crop(30, h - 24, 24, w - 20)
            return _crop_desk_framed_canvas(ia, ib, ia.crop(0, ia.height, 0, 20), ib.crop(0, ib.height, 0, 20))
        if app == "powerpoint" and h >= 650:
            bottom_b = rgb_b.crop(648, h, 0, w).data
            if bottom_b and (max(bottom_b) - min(bottom_b)) <= 10:
                ia = rgb_a.crop(0, 646, 0, w)
                ib = rgb_b.crop(0, 646, 0, w)
                return _crop_desk_framed_canvas(ia, ib, ia.crop(0, 20, 0, w), ib.crop(0, 20, 0, w))
            return _crop_desk_framed_canvas(rgb_a, rgb_b, rgb_a.crop(0, 20, 0, w), rgb_b.crop(0, 20, 0, w))
        if app == "excel":
            top_a_bg, _ = detect_background_color(rgb_a.crop(0, 20, 0, w))
            if sum(top_a_bg) / 3.0 < 248.0:
                return rgb_a.crop(22, h - 24, 45, w - 18), rgb_b.crop(22, h - 24, 45, w - 18)

    return rgb_a, rgb_b


def build_foreground_mask(
    rgb: Any,
    bg_rgb: Any,
    tolerance: int = 35,
) -> Any:
    """Build a boolean foreground ink mask by subtracting pixels close to bg_rgb."""
    if _is_numpy_array(rgb):
        if rgb.size == 0:
            return np.zeros((0, 0), dtype=bool)
        mask = np.max(np.abs(rgb.astype(np.int16) - bg_rgb.astype(np.int16)), axis=2) > tolerance
        cnt = int(mask.sum())
        if 0 < cnt <= 120:
            px = rgb[mask]
            if bool(np.all(px >= 150)) and bool(np.all((px.max(axis=1) - px.min(axis=1)) <= 10)):
                mask[:] = False
        return mask

    w, h, data = rgb.width, rgb.height, rgb.data
    if w == 0 or h == 0:
        return []
    br, bg, bb = bg_rgb
    mask_rows: list[list[bool]] = []
    fg_coords: list[tuple[int, int, int, int, int]] = []
    for y in range(h):
        row: list[bool] = [False] * w
        off = y * w * 3
        for x in range(w):
            i = off + x * 3
            r, g, b = data[i], data[i + 1], data[i + 2]
            if max(abs(r - br), abs(g - bg), abs(b - bb)) > tolerance:
                row[x] = True
                fg_coords.append((y, x, r, g, b))
        mask_rows.append(row)
    if 0 < len(fg_coords) <= 120:
        if all(min(r, g, b) >= 150 and (max(r, g, b) - min(r, g, b)) <= 10 for _, _, r, g, b in fg_coords):
            for y, x, _, _, _ in fg_coords:
                mask_rows[y][x] = False
    return mask_rows


def dilate_mask(mask: Any, radius: int = 3) -> Any:
    """Dilate a boolean mask with a square structuring element for anti-aliasing tolerance."""
    if _is_numpy_array(mask):
        if mask.size == 0 or radius <= 0:
            return mask.copy()
        h, w = mask.shape
        tmp = mask.copy()
        for dx in range(-radius, radius + 1):
            if dx == 0:
                continue
            x0_s, x1_s = max(0, -dx), min(w, w - dx)
            x0_d, x1_d = max(0, dx), min(w, w + dx)
            if x1_s > x0_s:
                tmp[:, x0_d:x1_d] |= mask[:, x0_s:x1_s]
        out = tmp.copy()
        for dy in range(-radius, radius + 1):
            if dy == 0:
                continue
            y0_s, y1_s = max(0, -dy), min(h, h - dy)
            y0_d, y1_d = max(0, dy), min(h, h + dy)
            if y1_s > y0_s:
                out[y0_d:y1_d, :] |= tmp[y0_s:y1_s, :]
        return out

    h = len(mask)
    w = len(mask[0]) if h > 0 else 0
    if h == 0 or w == 0 or radius <= 0:
        return [row[:] for row in mask]
    tmp = [row[:] for row in mask]
    for y in range(h):
        src_row = mask[y]
        dst_row = tmp[y]
        for x in range(w):
            if src_row[x]:
                x0 = max(0, x - radius)
                x1 = min(w, x + radius + 1)
                for xx in range(x0, x1):
                    dst_row[xx] = True
    out = [row[:] for row in tmp]
    for y in range(h):
        src_row = tmp[y]
        y0 = max(0, y - radius)
        y1 = min(h, y + radius + 1)
        for x in range(w):
            if src_row[x]:
                for yy in range(y0, y1):
                    out[yy][x] = True
    return out


def compute_color_histogram_similarity(
    rgb_a: Any,
    mask_a: Any,
    rgb_b: Any,
    mask_b: Any,
    bg_a: Any,
    bg_b: Any,
    bg_tol: int = 35,
) -> float:
    """Compute foreground color-histogram similarity (Bhattacharyya) plus background check."""
    if _is_numpy_array(rgb_a):
        bg_mismatch = float(np.max(np.abs(bg_a - bg_b))) > float(bg_tol)
        bg_sim = max(0.0, 1.0 - float(np.mean(np.abs(bg_a - bg_b))) / 255.0)
        na = int(mask_a.sum())
        nb = int(mask_b.sum())
        if na == 0 and nb == 0:
            return bg_sim if bg_mismatch else 1.0
        if na == 0 or nb == 0:
            return 0.0
        pa = rgb_a[mask_a] >> 6
        pb = rgb_b[mask_b] >> 6
        ca = (pa[:, 0].astype(np.int32) << 4) | (pa[:, 1].astype(np.int32) << 2) | pa[:, 2].astype(np.int32)
        cb = (pb[:, 0].astype(np.int32) << 4) | (pb[:, 1].astype(np.int32) << 2) | pb[:, 2].astype(np.int32)
        ha = np.bincount(ca, minlength=64).astype(np.float64) / float(na)
        hb = np.bincount(cb, minlength=64).astype(np.float64) / float(nb)
        hist_sim = float(np.clip(np.sum(np.sqrt(ha * hb)), 0.0, 1.0))
        return min(hist_sim, bg_sim) if bg_mismatch else hist_sim

    bg_diffs = [abs(bg_a[i] - bg_b[i]) for i in range(3)]
    bg_mismatch = max(bg_diffs) > float(bg_tol)
    bg_sim = max(0.0, 1.0 - (sum(bg_diffs) / 3.0) / 255.0)

    def _hist(grid: _RgbGrid, mask_rows: list[list[bool]]) -> tuple[int, list[float]]:
        bins = [0] * 64
        cnt = 0
        w, data = grid.width, grid.data
        for y, row in enumerate(mask_rows):
            off = y * w * 3
            for x, flag in enumerate(row):
                if flag:
                    i = off + x * 3
                    code = ((data[i] >> 6) << 4) | ((data[i + 1] >> 6) << 2) | (data[i + 2] >> 6)
                    bins[code] += 1
                    cnt += 1
        if cnt == 0:
            return 0, [0.0] * 64
        return cnt, [b / float(cnt) for b in bins]

    na, ha = _hist(rgb_a, mask_a)
    nb, hb = _hist(rgb_b, mask_b)
    if na == 0 and nb == 0:
        return bg_sim if bg_mismatch else 1.0
    if na == 0 or nb == 0:
        return 0.0
    hist_sim = min(1.0, max(0.0, sum(math.sqrt(a * b) for a, b in zip(ha, hb))))
    return min(hist_sim, bg_sim) if bg_mismatch else hist_sim


def compute_foreground_metrics(
    rgb_a: Any,
    rgb_b: Any,
    app: str = "office",
    tolerance: int = 35,
    dilation_radius: int = 3,
) -> ForegroundMetrics:
    """Compute foreground recall, precision, color-histogram similarity, and min score."""
    if rgb_a.size == 0 or rgb_b.size == 0:
        return ForegroundMetrics(1.0, 1.0, 1.0, 0.0, 1.0, 0, 0)

    ca, cb = extract_comparable_canvases(rgb_a, rgb_b, app=app)
    bg_a, _ = detect_background_color(ca)
    bg_b, _ = detect_background_color(cb)

    fa = build_foreground_mask(ca, bg_a, tolerance=tolerance)
    fb = build_foreground_mask(cb, bg_b, tolerance=tolerance)

    if _is_numpy_array(fa):
        na = int(fa.sum())
        nb = int(fb.sum())
    else:
        na = sum(1 for row in fa for v in row if v)
        nb = sum(1 for row in fb for v in row if v)

    hist_sim = compute_color_histogram_similarity(
        ca, fa, cb, fb, bg_a, bg_b, bg_tol=tolerance
    )
    hist_dist = max(0.0, 1.0 - hist_sim)

    if na == 0 and nb == 0:
        return ForegroundMetrics(
            recall=1.0,
            precision=1.0,
            color_hist_similarity=hist_sim,
            color_hist_distance=hist_dist,
            foreground_score=hist_sim,
            fg_pixels_a=0,
            fg_pixels_b=0,
        )
    if na == 0 or nb == 0:
        return ForegroundMetrics(
            recall=0.0,
            precision=0.0,
            color_hist_similarity=0.0,
            color_hist_distance=1.0,
            foreground_score=0.0,
            fg_pixels_a=na,
            fg_pixels_b=nb,
        )

    fa_d = dilate_mask(fa, radius=dilation_radius)
    fb_d = dilate_mask(fb, radius=dilation_radius)
    if _is_numpy_array(fa):
        recall = float((fa & fb_d).sum()) / float(na)
        precision = float((fb & fa_d).sum()) / float(nb)
    else:
        rec_hits = sum(
            1
            for y in range(len(fa))
            for x in range(len(fa[0]))
            if fa[y][x] and fb_d[y][x]
        )
        prec_hits = sum(
            1
            for y in range(len(fb))
            for x in range(len(fb[0]))
            if fb[y][x] and fa_d[y][x]
        )
        recall = rec_hits / float(na)
        precision = prec_hits / float(nb)

    fg_score = min(recall, precision, hist_sim)
    return ForegroundMetrics(
        recall=recall,
        precision=precision,
        color_hist_similarity=hist_sim,
        color_hist_distance=hist_dist,
        foreground_score=fg_score,
        fg_pixels_a=na,
        fg_pixels_b=nb,
    )


def ensure_gui_app() -> QApplication:
    """Ensure a QApplication instance exists for QImage, QPainter, and widget operations."""
    app = QApplication.instance()
    if not app:
        app = QApplication(["office_diff_comparator", "-platform", "offscreen"])
    return app


def classify_similarity(sim: float | None, override: str | None = None) -> str:
    """Categorize visual similarity score into standard parity tiers."""
    if override:
        return override
    if sim is None:
        return "UNVERIFIED"
    if sim >= 0.95:
        return "PARITY_MATCH"
    if sim >= 0.85:
        return "COSMETIC_MINOR"
    if sim >= 0.70:
        return "LAYOUT_DRIFT"
    return "CRITICAL_MISMATCH"


def fit_to_canvas(img: QImage, target_w: int, target_h: int) -> QImage:
    """Scale image preserving aspect ratio and center on neutral canvas."""
    canvas = QImage(target_w, target_h, QImage.Format.Format_ARGB32)
    canvas.fill(QColor(245, 245, 245))

    scaled = img.scaled(
        target_w,
        target_h,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    scaled = scaled.convertToFormat(QImage.Format.Format_ARGB32)

    x = (target_w - scaled.width()) // 2
    y = (target_h - scaled.height()) // 2

    painter = QPainter(canvas)
    painter.drawImage(x, y, scaled)
    painter.end()

    return canvas


def is_blank_canvas(img: QImage, tolerance: int = 1) -> bool:
    """Check if image is essentially blank/monochrome (e.g. solid white or black)."""
    if img.isNull() or img.width() == 0 or img.height() == 0:
        return True
    w, h = img.width(), img.height()
    colors: list[int] = []
    step_x = max(1, w // 32)
    step_y = max(1, h // 32)
    for y in range(0, h, step_y):
        for x in range(0, w, step_x):
            rgb = img.pixel(x, y)
            colors.append(rgb & 0xFFFFFF)
    return len(set(colors)) <= tolerance


def _compute_mae_and_diff_map(
    rgb_a: Any,
    rgb_b: Any,
    norm_w: int,
    norm_h: int,
    need_diff_map: bool,
) -> tuple[float, float, float, float, QImage | None]:
    """Compute legacy whole-image MAE, ROI similarity, edge similarity, and diff map."""
    roi_x0 = int(norm_w * 0.2)
    roi_x1 = int(norm_w * 0.8)
    roi_y0 = int(norm_h * 0.2)
    roi_y1 = int(norm_h * 0.8)
    total_pixels = max(1, norm_w * norm_h)

    if _is_numpy_array(rgb_a):
        a16 = rgb_a.astype(np.int32)
        b16 = rgb_b.astype(np.int32)
        diff_rgb = np.abs(a16 - b16)
        d = (diff_rgb[..., 0] + diff_rgb[..., 1] + diff_rgb[..., 2]) // 3
        mae = float(d.sum()) / float(total_pixels)
        similarity = max(0.0, 1.0 - (mae / 255.0))

        roi_slice = d[roi_y0 : roi_y1 + 1, roi_x0 : roi_x1 + 1]
        roi_mae = float(roi_slice.mean()) if roi_slice.size > 0 else mae
        roi_similarity = max(0.0, 1.0 - (roi_mae / 255.0))

        if norm_w > 1 and norm_h > 1:
            grad1 = np.abs(a16[:-1, :-1, 0] - a16[:-1, 1:, 0])
            grad2 = np.abs(b16[:-1, :-1, 0] - b16[:-1, 1:, 0])
            edge_diff_sum = float(np.abs(grad1 - grad2).sum())
            edge_count = (norm_w - 1) * (norm_h - 1)
            edge_similarity = max(0.0, 1.0 - (edge_diff_sum / (edge_count * 255.0)))
        else:
            edge_similarity = similarity

        diff_map: QImage | None = None
        if need_diff_map:
            diff_rgba = np.empty((norm_h, norm_w, 4), dtype=np.uint8)
            lum = (0.299 * a16[..., 0] + 0.587 * a16[..., 1] + 0.114 * a16[..., 2]).astype(np.uint8)
            diff_rgba[..., 0] = lum
            diff_rgba[..., 1] = lum
            diff_rgba[..., 2] = lum
            diff_rgba[..., 3] = 180
            hi = d > 10
            diff_rgba[hi, 0] = np.minimum(255, 120 + d[hi]).astype(np.uint8)
            diff_rgba[hi, 1] = 40
            diff_rgba[hi, 2] = 80
            diff_rgba[hi, 3] = 255
            diff_map = QImage(
                diff_rgba.data, norm_w, norm_h, norm_w * 4, QImage.Format.Format_RGBA8888
            ).copy()
        return mae, similarity, roi_similarity, edge_similarity, diff_map

    # Pure-Python fallback
    da: bytes = rgb_a.data
    db: bytes = rgb_b.data
    total_diff = 0
    roi_diff = 0
    roi_pixels = 0
    edge_diff_sum = 0
    edge_count = 0
    diff_buf = bytearray(norm_w * norm_h * 4) if need_diff_map else bytearray()

    for y in range(norm_h):
        row_off = y * norm_w * 3
        for x in range(norm_w):
            i = row_off + x * 3
            r1, g1, b1 = da[i], da[i + 1], da[i + 2]
            r2, g2, b2 = db[i], db[i + 1], db[i + 2]
            d = (abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)) // 3
            total_diff += d
            if roi_x0 <= x <= roi_x1 and roi_y0 <= y <= roi_y1:
                roi_diff += d
                roi_pixels += 1
            if need_diff_map:
                out_i = (y * norm_w + x) * 4
                if d > 10:
                    diff_buf[out_i] = min(255, 120 + d)
                    diff_buf[out_i + 1] = 40
                    diff_buf[out_i + 2] = 80
                    diff_buf[out_i + 3] = 255
                else:
                    lum = int(0.299 * r1 + 0.587 * g1 + 0.114 * b1)
                    diff_buf[out_i] = lum
                    diff_buf[out_i + 1] = lum
                    diff_buf[out_i + 2] = lum
                    diff_buf[out_i + 3] = 180
            if x < norm_w - 1 and y < norm_h - 1:
                grad1 = abs(r1 - da[i + 3])
                grad2 = abs(r2 - db[i + 3])
                edge_diff_sum += abs(grad1 - grad2)
                edge_count += 1

    mae = total_diff / float(total_pixels)
    similarity = max(0.0, 1.0 - (mae / 255.0))
    roi_mae = roi_diff / float(roi_pixels) if roi_pixels > 0 else mae
    roi_similarity = max(0.0, 1.0 - (roi_mae / 255.0))
    edge_similarity = (
        max(0.0, 1.0 - (edge_diff_sum / (edge_count * 255.0))) if edge_count > 0 else similarity
    )
    diff_map = (
        QImage(bytes(diff_buf), norm_w, norm_h, norm_w * 4, QImage.Format.Format_RGBA8888).copy()
        if need_diff_map
        else None
    )
    return mae, similarity, roi_similarity, edge_similarity, diff_map


def compare_canvases(
    orig_png: Path,
    target_png: Path,
    app: str = "office",
    file_name: str | None = None,
    diff_out: Path | None = None,
    sample_size: tuple[int, int] = (1440, 900),
    normalize_size: bool = False,
) -> DiffResult:
    """Compare two rendered document canvas images and generate visual difference map."""
    ensure_gui_app()
    doc_name = file_name or orig_png.name.removesuffix(".png")

    if not orig_png.exists() or not target_png.exists():
        missing_name = orig_png.name if not orig_png.exists() else target_png.name
        return DiffResult(
            file=doc_name,
            app=app,
            similarity=None,
            mae=255.0,
            edge_similarity=0.0,
            roi_similarity=0.0,
            category="MISSING",
            orig_size=(0, 0),
            target_size=(0, 0),
            error=f"Image file missing: {missing_name}",
        )

    img_a = QImage(str(orig_png))
    img_b = QImage(str(target_png))

    if img_a.isNull() or img_b.isNull():
        return DiffResult(
            file=doc_name,
            app=app,
            similarity=None,
            mae=255.0,
            edge_similarity=0.0,
            roi_similarity=0.0,
            category="CRITICAL_MISMATCH",
            orig_size=(img_a.width() if not img_a.isNull() else 0, img_a.height() if not img_a.isNull() else 0),
            target_size=(img_b.width() if not img_b.isNull() else 0, img_b.height() if not img_b.isNull() else 0),
            error="Could not decode image PNG",
        )

    orig_size = (img_a.width(), img_a.height())
    target_size = (img_b.width(), img_b.height())

    if is_blank_canvas(img_b) and not is_blank_canvas(img_a):
        return DiffResult(
            file=doc_name,
            app=app,
            similarity=0.0,
            mae=255.0,
            edge_similarity=0.0,
            roi_similarity=0.0,
            category="CRITICAL_MISMATCH",
            orig_size=orig_size,
            target_size=target_size,
            error="Candidate render is an empty/blank canvas",
            foreground_score=0.0,
            recall=0.0,
            precision=0.0,
            color_hist_similarity=0.0,
            tier="CRITICAL_MISMATCH",
        )

    if orig_size != target_size and not normalize_size:
        return DiffResult(
            file=doc_name,
            app=app,
            similarity=None,
            mae=255.0,
            edge_similarity=0.0,
            roi_similarity=0.0,
            category="INCOMPARABLE_SIZE",
            orig_size=orig_size,
            target_size=target_size,
            normalized=False,
            error=f"Dimensions mismatch: baseline {orig_size} vs candidate {target_size}",
        )

    norm_w, norm_h = sample_size
    if orig_size == target_size and orig_size == (norm_w, norm_h):
        scaled_a = img_a.convertToFormat(QImage.Format.Format_ARGB32)
        scaled_b = img_b.convertToFormat(QImage.Format.Format_ARGB32)
        is_norm = False
    elif orig_size == target_size:
        norm_w, norm_h = orig_size
        scaled_a = img_a.convertToFormat(QImage.Format.Format_ARGB32)
        scaled_b = img_b.convertToFormat(QImage.Format.Format_ARGB32)
        is_norm = False
    else:
        scaled_a = fit_to_canvas(img_a, norm_w, norm_h)
        scaled_b = fit_to_canvas(img_b, norm_w, norm_h)
        is_norm = True

    rgb_a = qimage_to_rgb_array(scaled_a)
    rgb_b = qimage_to_rgb_array(scaled_b)

    fg = compute_foreground_metrics(rgb_a, rgb_b, app=app)
    mae, similarity, roi_similarity, edge_similarity, diff_map = _compute_mae_and_diff_map(
        rgb_a, rgb_b, norm_w, norm_h, need_diff_map=diff_out is not None
    )
    category = classify_similarity(fg.foreground_score)

    diff_path_str: str | None = None
    if diff_out is not None and diff_map is not None:
        diff_out.parent.mkdir(parents=True, exist_ok=True)
        comp_w = norm_w * 3
        comp_h = norm_h + 40
        composite = QImage(comp_w, comp_h, QImage.Format.Format_ARGB32)
        composite.fill(QColor(240, 240, 240))

        painter = QPainter(composite)
        painter.drawImage(0, 40, scaled_a)
        painter.drawImage(norm_w, 40, scaled_b)
        painter.drawImage(norm_w * 2, 40, diff_map)

        painter.setPen(QColor(40, 40, 40))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(20, 26, f"Baseline (.vibeoffice) - {doc_name}")
        painter.drawText(
            norm_w + 20,
            26,
            f"Candidate (ATBOffice) - FG {fg.foreground_score * 100:.1f}% (MAE {similarity * 100:.1f}%)",
        )
        painter.drawText(norm_w * 2 + 20, 26, f"Diff Heatmap ({category})")
        painter.end()

        composite.save(str(diff_out), "PNG")
        diff_path_str = str(diff_out)

    return DiffResult(
        file=doc_name,
        app=app,
        similarity=similarity,
        mae=mae,
        edge_similarity=edge_similarity,
        roi_similarity=roi_similarity,
        category=category,
        orig_size=orig_size,
        target_size=target_size,
        diff_path=diff_path_str,
        normalized=is_norm,
        foreground_score=fg.foreground_score,
        recall=fg.recall,
        precision=fg.precision,
        color_hist_similarity=fg.color_hist_similarity,
        tier=category,
    )
