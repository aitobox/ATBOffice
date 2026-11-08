"""Visual difference and similarity scoring engine for rendered office documents."""
# ruff: noqa: E402, E501

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from .models import DiffResult


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

    diff_map = QImage(norm_w, norm_h, QImage.Format.Format_ARGB32)
    diff_map.fill(QColor(255, 255, 255))

    total_diff = 0
    total_pixels = norm_w * norm_h
    roi_diff = 0
    roi_pixels = 0

    roi_x0 = int(norm_w * 0.2)
    roi_x1 = int(norm_w * 0.8)
    roi_y0 = int(norm_h * 0.2)
    roi_y1 = int(norm_h * 0.8)

    edge_diff_sum = 0
    edge_count = 0

    # Scan pixel lines
    for y in range(norm_h):
        for x in range(norm_w):
            c1 = scaled_a.pixelColor(x, y)
            c2 = scaled_b.pixelColor(x, y)

            dr = abs(c1.red() - c2.red())
            dg = abs(c1.green() - c2.green())
            db = abs(c1.blue() - c2.blue())
            d = (dr + dg + db) // 3
            total_diff += d

            if roi_x0 <= x <= roi_x1 and roi_y0 <= y <= roi_y1:
                roi_diff += d
                roi_pixels += 1

            if d > 10:
                # Highlight differences in red/magenta
                diff_map.setPixelColor(x, y, QColor(min(255, 120 + d), 40, 80))
            else:
                # Faded grayscale baseline
                lum = int(0.299 * c1.red() + 0.587 * c1.green() + 0.114 * c1.blue())
                diff_map.setPixelColor(x, y, QColor(lum, lum, lum, 180))

            if x < norm_w - 1 and y < norm_h - 1:
                c1_r = scaled_a.pixelColor(x + 1, y)
                c2_r = scaled_b.pixelColor(x + 1, y)
                grad1 = abs(c1.red() - c1_r.red())
                grad2 = abs(c2.red() - c2_r.red())
                edge_diff_sum += abs(grad1 - grad2)
                edge_count += 1

    mae = total_diff / float(total_pixels)
    similarity = max(0.0, 1.0 - (mae / 255.0))
    roi_mae = roi_diff / float(roi_pixels) if roi_pixels > 0 else mae
    roi_similarity = max(0.0, 1.0 - (roi_mae / 255.0))
    edge_similarity = max(0.0, 1.0 - (edge_diff_sum / (edge_count * 255.0))) if edge_count > 0 else similarity

    category = classify_similarity(similarity)

    diff_path_str: str | None = None
    if diff_out is not None:
        diff_out.parent.mkdir(parents=True, exist_ok=True)
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
        painter.drawText(norm_w + 20, 26, f"Candidate (ATBOffice) - {similarity * 100:.1f}%")
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
    )
