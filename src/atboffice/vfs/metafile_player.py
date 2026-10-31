"""Facade module for WMF and EMF metafile player and renderer."""

from .metafile import (
    EMFParser,
    MetafilePlayer,
    WMFParser,
    is_emf,
    is_wmf,
    play_metafile,
    render_metafile_to_bytes,
    render_metafile_to_image,
)

__all__ = [
    "MetafilePlayer",
    "WMFParser",
    "EMFParser",
    "is_wmf",
    "is_emf",
    "play_metafile",
    "render_metafile_to_image",
    "render_metafile_to_bytes",
]
