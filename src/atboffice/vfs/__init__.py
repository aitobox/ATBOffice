"""Virtual File System and OPC Packaging subsystem for ATBOffice."""

from .crypto import decrypt_package, encrypt_package, is_encrypted_package
from .metafile_player import (
    MetafilePlayer,
    is_emf,
    is_wmf,
    play_metafile,
    render_metafile_to_bytes,
    render_metafile_to_image,
)
from .opc import PackageWriter, Relationship, SourcePackage
from .order import SCHEMA_ORDERS, enforce_schema_order

__all__ = [
    "SourcePackage",
    "PackageWriter",
    "Relationship",
    "enforce_schema_order",
    "SCHEMA_ORDERS",
    "is_encrypted_package",
    "decrypt_package",
    "encrypt_package",
    "MetafilePlayer",
    "is_wmf",
    "is_emf",
    "play_metafile",
    "render_metafile_to_image",
    "render_metafile_to_bytes",
]
