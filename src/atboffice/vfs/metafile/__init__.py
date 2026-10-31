"""Metafile package for Windows Metafile (WMF) and Enhanced Metafile (EMF) rendering."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from .emf_parser import EMFParser
from .player import MetafilePlayer
from .wmf_parser import WMFParser


def is_wmf(data: bytes) -> bool:
    """Check if byte sequence represents a valid WMF file."""
    return WMFParser.is_wmf(data)


def is_emf(data: bytes) -> bool:
    """Check if byte sequence represents a valid EMF file."""
    return EMFParser.is_emf(data)


def play_metafile(
    data: bytes,
    painter: QPainter,
    target_rect: QRectF | None = None,
    kind: str = "auto",
) -> bool:
    """Play WMF/EMF records onto a QPainter."""
    player = MetafilePlayer()
    return player.play(data, painter, target_rect=target_rect, kind=kind)


def render_metafile_to_image(
    data: bytes,
    kind: str = "auto",
    max_px: int = 1200,
) -> QImage | None:
    """Render WMF/EMF records into a QImage."""
    player = MetafilePlayer()
    return player.render_to_image(data, kind=kind, max_px=max_px)


def render_metafile_to_bytes(
    data: bytes,
    kind: str = "auto",
    format: str = "PNG",
    max_px: int = 1200,
) -> bytes | None:
    """Render WMF/EMF records into image bytes (PNG, JPEG, etc.)."""
    player = MetafilePlayer()
    return player.render_to_bytes(data, kind=kind, format=format, max_px=max_px)


__all__ = [
    "EMFParser",
    "MetafilePlayer",
    "WMFParser",
    "is_emf",
    "is_wmf",
    "play_metafile",
    "render_metafile_to_bytes",
    "render_metafile_to_image",
]
