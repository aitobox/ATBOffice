"""Lossless Open Packaging Conventions (OPC) Container Engine.

Provides immutable SourcePackage reading and lossless PackageWriter serialization
with byte-for-byte carry of untouched components and atomic saving.
"""

from __future__ import annotations

import io
import os
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Sequence, Union

from .xml_tree import parse_xml, serialize_xml

NS_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"


@dataclass(frozen=True)
class Relationship:
    """Represents an OPC relationship entry."""

    id: str
    type: str
    target: str
    target_mode: str = "Internal"

    @property
    def is_external(self) -> bool:
        return self.target_mode.lower() == "external"


def _normalize_part_name(part_name: str) -> str:
    """Normalize OPC part name by stripping leading/trailing slashes and whitespace."""
    normalized = part_name.strip()
    while normalized.startswith("/"):
        normalized = normalized[1:]
    return normalized


def _get_rels_path_for_part(part_name: str) -> str:
    """Return the corresponding .rels part name for a given part.
    
    Empty string '' corresponds to package-level '_rels/.rels'.
    'xl/workbook.xml' corresponds to 'xl/_rels/workbook.xml.rels'.
    """
    clean = _normalize_part_name(part_name)
    if not clean:
        return "_rels/.rels"
    slash_idx = clean.rfind("/")
    if slash_idx == -1:
        return f"_rels/{clean}.rels"
    dir_part = clean[:slash_idx]
    filename = clean[slash_idx + 1 :]
    return f"{dir_part}/_rels/{filename}.rels"


class SourcePackage:
    """Immutable reader for an Open Packaging Conventions (OPC) package."""

    def __init__(
        self,
        parts: Dict[str, bytes],
        defaults: Dict[str, str],
        overrides: Dict[str, str],
        relationships: Dict[str, List[Relationship]],
    ) -> None:
        self._parts = dict(parts)
        self._defaults = dict(defaults)
        self._overrides = dict(overrides)
        self._relationships = {k: list(v) for k, v in relationships.items()}

    @classmethod
    def open(cls, file_or_bytes: Union[Path, str, bytes, BinaryIO]) -> SourcePackage:
        """Open an OPC package from a file path, bytes, or file-like object."""
        if isinstance(file_or_bytes, (str, Path)):
            path = Path(file_or_bytes)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            raw_bytes = path.read_bytes()
        elif isinstance(file_or_bytes, bytes):
            raw_bytes = file_or_bytes
        else:
            raw_bytes = file_or_bytes.read()

        return cls.from_bytes(raw_bytes)

    @classmethod
    def from_bytes(cls, data: bytes) -> SourcePackage:
        """Construct a SourcePackage from in-memory bytes."""
        if not zipfile.is_zipfile(io.BytesIO(data)):
            raise ValueError("Not a valid ZIP/OPC package: magic signature mismatch")

        parts: Dict[str, bytes] = {}
        try:
            with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
                for zip_info in zf.infolist():
                    name = _normalize_part_name(zip_info.filename)
                    if name:
                        parts[name] = zf.read(zip_info.filename)
        except Exception as e:
            raise ValueError(f"Not a valid ZIP/OPC package: {e}") from e

        defaults: Dict[str, str] = {}
        overrides: Dict[str, str] = {}

        # Parse [Content_Types].xml
        ct_bytes = parts.get("[Content_Types].xml")
        if ct_bytes:
            try:
                root = parse_xml(ct_bytes)
                for child in root:
                    tag_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if tag_local == "Default":
                        ext = (child.get("Extension") or "").lower()
                        ct = child.get("ContentType") or ""
                        if ext:
                            defaults[ext] = ct
                    elif tag_local == "Override":
                        p_name = _normalize_part_name(child.get("PartName") or "")
                        ct = child.get("ContentType") or ""
                        if p_name:
                            overrides[p_name] = ct
            except Exception:
                pass

        # Parse relationships
        relationships: Dict[str, List[Relationship]] = {}
        for name, content in parts.items():
            if name.endswith(".rels"):
                # Determine owner
                if name == "_rels/.rels":
                    owner = ""
                else:
                    # e.g. xl/_rels/workbook.xml.rels -> xl/workbook.xml
                    owner = name.replace("/_rels/", "/")
                    if owner.endswith(".rels"):
                        owner = owner[:-5]
                owner = _normalize_part_name(owner)
                try:
                    rel_root = parse_xml(content)
                    rel_list: List[Relationship] = []
                    for child in rel_root:
                        tag_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                        if tag_local == "Relationship":
                            r_id = child.get("Id") or ""
                            r_type = child.get("Type") or ""
                            r_target = child.get("Target") or ""
                            r_mode = child.get("TargetMode") or "Internal"
                            if r_id and r_type:
                                rel_list.append(
                                    Relationship(
                                        id=r_id,
                                        type=r_type,
                                        target=r_target,
                                        target_mode=r_mode,
                                    )
                                )
                    relationships[owner] = rel_list
                except Exception:
                    pass

        return cls(
            parts=parts,
            defaults=defaults,
            overrides=overrides,
            relationships=relationships,
        )

    def has_part(self, part_name: str) -> bool:
        """Check whether a part exists in the package."""
        return _normalize_part_name(part_name) in self._parts

    def read_part(self, part_name: str) -> bytes:
        """Retrieve the exact raw bytes of a part."""
        norm = _normalize_part_name(part_name)
        if norm not in self._parts:
            raise KeyError(f"Part not found in package: {part_name}")
        return self._parts[norm]

    def get_content_type(self, part_name: str) -> Optional[str]:
        """Resolve the content type for a given part name."""
        norm = _normalize_part_name(part_name)
        if norm in self._overrides:
            return self._overrides[norm]
        dot_idx = norm.rfind(".")
        if dot_idx != -1:
            ext = norm[dot_idx + 1 :].lower()
            if ext in self._defaults:
                return self._defaults[ext]
        return None

    def get_relationships(self, part_name: str = "") -> List[Relationship]:
        """Return the list of relationships owned by part_name (empty string = package level)."""
        norm = _normalize_part_name(part_name)
        return list(self._relationships.get(norm, []))

    @property
    def part_names(self) -> List[str]:
        """List all normalized part names in the package."""
        return list(self._parts.keys())


class PackageWriter:
    """Lossless writer for an OPC package.
    
    Copies unmodified components byte-for-byte and atomically commits writes to disk.
    """

    def __init__(self, source_package: Optional[SourcePackage] = None) -> None:
        self._source = source_package
        self._parts: Dict[str, bytes] = {}
        self._defaults: Dict[str, str] = {}
        self._overrides: Dict[str, str] = {}
        self._deleted: set[str] = set()

        if source_package:
            for name in source_package.part_names:
                self._parts[name] = source_package.read_part(name)
            self._defaults.update(source_package._defaults)
            self._overrides.update(source_package._overrides)
        else:
            # Standard package defaults
            self._defaults.setdefault(
                "rels", "application/vnd.openxmlformats-package.relationships+xml"
            )
            self._defaults.setdefault("xml", "application/xml")

    def has_part(self, part_name: str) -> bool:
        """Check if part exists and has not been deleted."""
        norm = _normalize_part_name(part_name)
        return norm in self._parts and norm not in self._deleted

    def read_part(self, part_name: str) -> bytes:
        """Read current content of a part."""
        norm = _normalize_part_name(part_name)
        if norm not in self._parts or norm in self._deleted:
            raise KeyError(f"Part not found in package writer: {part_name}")
        return self._parts[norm]

    def replace_part(
        self,
        part_name: str,
        content: bytes,
        content_type: Optional[str] = None,
    ) -> None:
        """Replace or set content of an existing part, carrying existing content type if omitted."""
        norm = _normalize_part_name(part_name)
        self._parts[norm] = content
        self._deleted.discard(norm)
        if content_type:
            self._overrides[norm] = content_type

    def add_part(
        self,
        part_name: str,
        content: bytes,
        content_type: str,
    ) -> None:
        """Add a new part to the package with explicit content type."""
        norm = _normalize_part_name(part_name)
        self._parts[norm] = content
        self._deleted.discard(norm)
        self._overrides[norm] = content_type

    def delete_part(self, part_name: str) -> None:
        """Mark a part for deletion from the package."""
        norm = _normalize_part_name(part_name)
        self._parts.pop(norm, None)
        self._overrides.pop(norm, None)
        self._deleted.add(norm)

    def _generate_content_types_xml(self) -> bytes:
        """Synthesize [Content_Types].xml representing active parts, defaults, and overrides."""
        root = ET.Element("Types", {"xmlns": NS_CONTENT_TYPES})

        # Ensure all existing extensions in parts have a default if not overridden
        active_parts = {k: v for k, v in self._parts.items() if k not in self._deleted}
        for name in active_parts:
            if name == "[Content_Types].xml":
                continue
            if name not in self._overrides:
                dot = name.rfind(".")
                if dot != -1:
                    ext = name[dot + 1 :].lower()
                    if ext not in self._defaults:
                        # Fallback default
                        self._defaults[ext] = "application/xml" if ext == "xml" else "application/octet-stream"

        for ext, ct in sorted(self._defaults.items()):
            ET.SubElement(root, "Default", {"Extension": ext, "ContentType": ct})

        for p_name, ct in sorted(self._overrides.items()):
            if p_name in active_parts and p_name != "[Content_Types].xml":
                ET.SubElement(
                    root,
                    "Override",
                    {"PartName": f"/{p_name}", "ContentType": ct},
                )

        return serialize_xml(root, standalone=True)

    def to_bytes(self) -> bytes:
        """Serialize the entire OPC package into ZIP archive bytes."""
        buf = io.BytesIO()
        active_parts = {k: v for k, v in self._parts.items() if k not in self._deleted}

        # Automatically update [Content_Types].xml
        active_parts["[Content_Types].xml"] = self._generate_content_types_xml()

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write [Content_Types].xml first per OPC convention
            zf.writestr("[Content_Types].xml", active_parts["[Content_Types].xml"])

            # Write _rels/.rels next if present
            if "_rels/.rels" in active_parts:
                zf.writestr("_rels/.rels", active_parts["_rels/.rels"])

            # Write all other parts
            for name, content in active_parts.items():
                if name not in ("[Content_Types].xml", "_rels/.rels"):
                    zf.writestr(name, content)

        return buf.getvalue()

    def save(self, target_path: Union[Path, str]) -> None:
        """Atomically write the OPC package to target_path using a temporary file and replace."""
        dest = Path(target_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        data = self.to_bytes()

        # Atomic write pattern
        tmp_file = tempfile.NamedTemporaryFile(
            dir=dest.parent,
            prefix=".tmp_pkg_",
            suffix=".tmp",
            delete=False,
        )
        try:
            tmp_file.write(data)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
            tmp_file.close()
            os.replace(tmp_file.name, dest)
        except Exception:
            if os.path.exists(tmp_file.name):
                try:
                    os.remove(tmp_file.name)
                except OSError:
                    pass
            raise
