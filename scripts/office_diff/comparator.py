"""Visual difference and similarity scoring engine for rendered office documents."""
# ruff: noqa: E402, E501

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
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


def qimage_to_rgb_array(img: QImage) -> np.ndarray:
    """Convert a QImage into a contiguous (H, W, 3) uint8 RGB numpy array."""
    if img.isNull() or img.width() == 0 or img.height() == 0:
        return np.zeros((0, 0, 3), dtype=np.uint8)
    rgb_img = img.convertToFormat(QImage.Format.Format_RGB888)
    w, h = rgb_img.width(), rgb_img.height()
    bpl = rgb_img.bytesPerLine()
    buf = np.frombuffer(rgb_img.constBits(), dtype=np.uint8, count=h * bpl)
    return buf.reshape(h, bpl)[:, : w * 3].reshape(h, w, 3).copy()


def detect_background_color(rgb: np.ndarray) -> tuple[np.ndarray, float]:
    """Detect the dominant background color of an RGB image via 5-bit color binning."""
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


def _crop_desk_framed_canvas(
    ia: np.ndarray,
    ib: np.ndarray,
    desk_sample_a: np.ndarray,
    desk_sample_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Crop outer desk backdrop to page/slide interior when desk framing is detected."""
    desk_a, frac_a = detect_background_color(desk_sample_a)
    desk_b, frac_b = detect_background_color(desk_sample_b)
    if frac_a <= 0.5 or frac_b <= 0.5:
        return ia, ib

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


def extract_comparable_canvases(
    rgb_a: np.ndarray,
    rgb_b: np.ndarray,
    app: str = "office",
) -> tuple[np.ndarray, np.ndarray]:
    """Strip asymmetric viewport chrome (rulers, notes pane, desk) when present."""
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


def build_foreground_mask(
    rgb: np.ndarray,
    bg_rgb: np.ndarray,
    tolerance: int = 35,
) -> np.ndarray:
    """Build a boolean foreground ink mask by subtracting pixels close to bg_rgb."""
    if rgb.size == 0:
        return np.zeros((0, 0), dtype=bool)
    mask = np.max(np.abs(rgb.astype(np.int16) - bg_rgb.astype(np.int16)), axis=2) > tolerance
    cnt = int(mask.sum())
    # Suppress isolated faint neutral corner margin ticks (<=120 px, no dark/colored ink)
    if 0 < cnt <= 120:
        px = rgb[mask]
        if bool(np.all(px >= 150)) and bool(np.all((px.max(axis=1) - px.min(axis=1)) <= 10)):
            mask[:] = False
    return mask


def dilate_mask(mask: np.ndarray, radius: int = 3) -> np.ndarray:
    """Dilate a boolean mask with a square structuring element for anti-aliasing tolerance."""
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


def compute_color_histogram_similarity(
    rgb_a: np.ndarray,
    mask_a: np.ndarray,
    rgb_b: np.ndarray,
    mask_b: np.ndarray,
    bg_a: np.ndarray,
    bg_b: np.ndarray,
    bg_tol: int = 35,
) -> float:
    """Compute foreground color-histogram similarity (Bhattacharyya) plus background check."""
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

    if bg_mismatch:
        return min(hist_sim, bg_sim)
    return hist_sim


def compute_foreground_metrics(
    rgb_a: np.ndarray,
    rgb_b: np.ndarray,
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
    na = int(fa.sum())
    nb = int(fb.sum())

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
    recall = float((fa & fb_d).sum()) / float(na)
    precision = float((fb & fa_d).sum()) / float(nb)
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
    # Sample a fine grid of 1024 points (32x32)
    colors: list[int] = []
    step_x = max(1, w // 32)
    step_y = max(1, h // 32)
    for y in range(0, h, step_y):
        for x in range(0, w, step_x):
            rgb = img.pixel(x, y)
            colors.append(rgb & 0xFFFFFF)
    return len(set(colors)) <= tolerance


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

    # Check for blank abnormal images
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

    # Strict Size Guardrail
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

    a16 = rgb_a.astype(np.int32)
    b16 = rgb_b.astype(np.int32)
    diff_rgb = np.abs(a16 - b16)
    d = (diff_rgb[..., 0] + diff_rgb[..., 1] + diff_rgb[..., 2]) // 3

    total_pixels = max(1, norm_w * norm_h)
    mae = float(d.sum()) / float(total_pixels)
    similarity = max(0.0, 1.0 - (mae / 255.0))

    roi_x0 = int(norm_w * 0.2)
    roi_x1 = int(norm_w * 0.8)
    roi_y0 = int(norm_h * 0.2)
    roi_y1 = int(norm_h * 0.8)
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

    category = classify_similarity(fg.foreground_score)

    diff_path_str: str | None = None
    if diff_out is not None:
        diff_out.parent.mkdir(parents=True, exist_ok=True)
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

        # Create side-by-side composite image: [Baseline | Candidate | Diff Map]
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
