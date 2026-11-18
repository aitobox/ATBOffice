"""Picture decoding and painting shared by the slide canvas and the slideshow renderer."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap

from atboffice.modules.presentation.views.geometry_helper import (
    create_shape_path,
    flip_transform,
)
from atboffice.vfs.metafile import is_emf, is_wmf, render_metafile_to_image

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation
    from atboffice.modules.presentation.models.shape import Shape

# Longest side, in pixels, a WMF/EMF picture is rasterized to (sharp when zoomed, bounded memory).
METAFILE_RASTER_MAX_PX = 2048


@lru_cache(maxsize=32)
def decode_picture_bytes(data: bytes) -> QImage | None:
    """Decode picture bytes, rasterizing WMF/EMF metafiles that Qt cannot read.

    Metafiles are recognized by content, not part name: PowerPoint files may store an
    EMF in a ``.wmf`` part. Returns None when the bytes cannot be decoded. Results are
    cached because the slideshow re-renders a slide for every animation frame.
    """
    qimg = QImage.fromData(data)
    if not qimg.isNull():
        return qimg
    if is_emf(data) or is_wmf(data):
        try:
            qimg = render_metafile_to_image(data, max_px=METAFILE_RASTER_MAX_PX)
        except Exception:  # a malformed metafile must never break painting
            return None
        if qimg is not None and not qimg.isNull():
            return qimg
    return None


def picture_bytes(shape: Shape, presentation: Presentation | None) -> bytes | None:
    """Return the poster frame or embedded picture bytes a shape displays."""
    m_item = shape.media_item
    if m_item and m_item.poster_bytes:
        return m_item.poster_bytes
    if shape.media and presentation:
        return presentation.props.get("_media_map", {}).get(shape.media)
    return None


def picture_target_rect(crop: dict[str, float] | None, w: float, h: float) -> QRectF:
    """Where the whole picture lands so its srcRect crop fills the frame.

    The visible fraction (1 - l - r, 1 - t - b) is stretched to the frame and the
    rest falls outside it (or, for negative crops, leaves padding inside it).
    """
    crop = crop if isinstance(crop, dict) else None
    if not crop:
        return QRectF(0.0, 0.0, w, h)
    cl = float(crop.get("l", 0.0) or 0.0)
    ct = float(crop.get("t", 0.0) or 0.0)
    cr = float(crop.get("r", 0.0) or 0.0)
    cb = float(crop.get("b", 0.0) or 0.0)
    vis_w = 1.0 - cl - cr
    vis_h = 1.0 - ct - cb
    if vis_w <= 0.001 or vis_h <= 0.001:
        return QRectF(0.0, 0.0, w, h)
    full_w = w / vis_w
    full_h = h / vis_h
    return QRectF(-cl * full_w, -ct * full_h, full_w, full_h)


def paint_picture(
    painter: QPainter,
    picture: QImage | QPixmap,
    shape: Shape,
    w: float,
    h: float,
    clip_path: QPainterPath | None = None,
) -> None:
    """Paint a decoded picture into the local box (0, 0, w, h) with crop and flips."""
    painter.save()
    if clip_path is not None:
        painter.setClipPath(clip_path, Qt.ClipOperation.IntersectClip)
    painter.setTransform(flip_transform(w, h, shape.flip_h, shape.flip_v), True)
    painter.setClipRect(QRectF(0.0, 0.0, w, h), Qt.ClipOperation.IntersectClip)
    target = picture_target_rect(shape.crop, w, h)
    if isinstance(picture, QPixmap):
        painter.drawPixmap(target, picture, QRectF(picture.rect()))
    else:
        painter.drawImage(target, picture, QRectF(picture.rect()))
    painter.restore()


def paint_missing_picture(painter: QPainter, w: float, h: float) -> None:
    """Paint the placeholder frame of a picture that is absent or cannot be decoded."""
    painter.setPen(QPen(QColor(200, 200, 200), 1.0, Qt.PenStyle.DashLine))
    painter.setBrush(QBrush(QColor(245, 245, 245)))
    painter.drawRect(QRectF(0.0, 0.0, w, h))


def paint_picture_shape(
    painter: QPainter,
    shape: Shape,
    rect: QRectF,
    presentation: Presentation,
    line_scale: float,
) -> bool:
    """Paint a picture or media poster into ``rect``; return False for any other shape.

    Used by the renderers that draw a whole slide in one pass (slideshow, thumbnails).
    """
    data = picture_bytes(shape, presentation)
    picture = decode_picture_bytes(data) if data else None
    if picture is None and shape.type != "image":
        return False

    w = max(1.0, rect.width())
    h = max(1.0, rect.height())
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.translate(rect.topLeft())
    if shape.rot:
        painter.translate(w / 2.0, h / 2.0)
        painter.rotate(shape.rot)
        painter.translate(-w / 2.0, -h / 2.0)

    outline = flip_transform(w, h, shape.flip_h, shape.flip_v).map(
        create_shape_path(shape.geom, w, h, shape.adj, shape.custom_path)
    )
    if picture is None:
        paint_missing_picture(painter, w, h)
    else:
        clip_path = outline if shape.geom and shape.geom != "rect" else None
        paint_picture(painter, picture, shape, w, h, clip_path)

    if shape.line and shape.line.type != "none" and shape.line.width > 0:
        painter.setPen(QPen(QColor(shape.line.color), max(1.0, shape.line.width * line_scale)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(outline)
    painter.restore()
    return True
