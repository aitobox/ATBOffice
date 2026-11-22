"""Picture shape creation: embed image bytes and size the frame like PowerPoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtGui import QImage

from atboffice.modules.presentation.models.shape import Line, Shape

IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff", "webp")


def image_size(data: bytes) -> tuple[int, int] | None:
    """Pixel size of encoded image ``data``; None when Qt cannot decode it."""
    img = QImage.fromData(data)
    if img.isNull():
        return None
    return img.width(), img.height()


def unique_shape_id(slide: Any, prefix: str) -> str:
    used = {getattr(s, "id", "") for s in getattr(slide, "shapes", [])}
    n = len(used) + 1
    while f"{prefix}_{n}" in used:
        n += 1
    return f"{prefix}_{n}"


def _media_key(presentation: Any, ext: str) -> str:
    media = presentation.props.setdefault("_media_map", {})
    n = len(media) + 1
    while f"ppt/media/inserted{n}.{ext}" in media:
        n += 1
    return f"ppt/media/inserted{n}.{ext}"


def fit_size(
    px_w: int, px_h: int, max_w: float, max_h: float
) -> tuple[float, float]:
    """Natural size in points (96 dpi pixels -> 72 dpi points), shrunk to fit the box."""
    w = px_w * 0.75
    h = px_h * 0.75
    scale = min(1.0, max_w / w if w else 1.0, max_h / h if h else 1.0)
    return max(1.0, w * scale), max(1.0, h * scale)


def picture_shape_from_bytes(
    presentation: Any,
    slide: Any,
    data: bytes,
    ext: str = "png",
    name: str = "",
    box: tuple[float, float, float, float] | None = None,
) -> Shape:
    """Create a picture shape whose bytes live in the presentation media map.

    ``box`` (x, y, w, h) fits the picture inside that rectangle; otherwise it is centred
    on the slide at its natural size (capped at 80 % of the slide).
    Raises ValueError when ``data`` is not a decodable image.
    """
    size = image_size(data)
    if size is None:
        raise ValueError("not an image")
    ext = (ext or "png").lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    key = _media_key(presentation, ext)
    presentation.props["_media_map"][key] = data

    slide_w = float(getattr(presentation, "w", 960.0) or 960.0)
    slide_h = float(getattr(presentation, "h", 540.0) or 540.0)
    if box is not None:
        bx, by, bw, bh = box
        w, h = fit_size(size[0], size[1], bw, bh)
        x, y = bx + (bw - w) / 2.0, by + (bh - h) / 2.0
    else:
        w, h = fit_size(size[0], size[1], slide_w * 0.8, slide_h * 0.8)
        x, y = (slide_w - w) / 2.0, (slide_h - h) / 2.0

    sid = unique_shape_id(slide, "pic")
    return Shape(
        id=sid,
        type="image",
        name=name or f"Picture {sid.split('_')[-1]}",
        x=x,
        y=y,
        w=w,
        h=h,
        media=key,
        line=Line.none(),
    )


def picture_shape_from_file(
    presentation: Any,
    slide: Any,
    path: str | Path,
    box: tuple[float, float, float, float] | None = None,
) -> Shape:
    """Read ``path`` and build a picture shape. Raises OSError / ValueError."""
    p = Path(path)
    data = p.read_bytes()
    return picture_shape_from_bytes(
        presentation, slide, data, ext=p.suffix or "png", name=p.stem, box=box
    )
