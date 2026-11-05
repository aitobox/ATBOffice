"""Virtual File System and OPC Packaging subsystem for ATBOffice."""

from .crypto import (
    FileFormatInspection,
    decrypt_package,
    detect_ole_format,
    encrypt_package,
    inspect_file_format,
    is_encrypted_package,
    is_ole_compound_file,
)
from .metafile_player import (
    MetafilePlayer,
    is_emf,
    is_wmf,
    play_metafile,
    render_metafile_to_bytes,
    render_metafile_to_image,
)
from .opc import OleCompoundFileError, PackageWriter, Relationship, SourcePackage
from .order import SCHEMA_ORDERS, enforce_schema_order

__all__ = [
    "SourcePackage",
    "OleCompoundFileError",
    "PackageWriter",
    "Relationship",
    "enforce_schema_order",
    "SCHEMA_ORDERS",
    "is_ole_compound_file",
    "detect_ole_format",
    "inspect_file_format",
    "FileFormatInspection",
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
