"""Lossless Open Packaging Conventions (OPC) Container Engine.

Provides immutable source package inspection and byte-for-byte carry
for unmodified package parts according to ECMA-376 Open Packaging Conventions.
"""

from __future__ import annotations

import io
import os
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Standard OPC Namespaces
NS_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_OFFICE_RELATIONSHIPS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_STRICT_RELATIONSHIPS = "http://purl.oclc.org/ooxml/officeDocument/relationships"


def normalize_part_name(part_name: str) -> str:
    """Normalize OPC part name by stripping leading slashes, converting Windows separators,
    and resolving redundant dot segments.
    """
    if not part_name:
        return ""
    clean = part_name.replace("\\", "/").strip()
    clean = urllib.parse.unquote(clean)
    clean = clean.lstrip("/")

    segments: list[str] = []
    for seg in clean.split("/"):
        if not seg or seg == ".":
            continue
        elif seg == "..":
            if segments:
                segments.pop()
        else:
            segments.append(seg)
    return "/".join(segments)


# Backwards compatibility alias
_normalize_part_name = normalize_part_name


def resolve_part_uri(
    owner_part: str, uri: str, return_fragment: bool = False
) -> str | tuple[str, str]:
    """Resolve an internal part URI relative to its owner part within the package.

    Raises ValueError if target URI attempts to escape package bounds (e.g. '../..').
    """
    if not uri:
        return ("", "") if return_fragment else ""

    # Extract anchor / fragment if present
    fragment = ""
    target = uri
    if "#" in target:
        target, fragment = target.split("#", 1)

    target = urllib.parse.unquote(target).replace("\\", "/").strip()

    if target.startswith("/"):
        base_segments: list[str] = []
        target = target.lstrip("/")
    else:
        owner_norm = normalize_part_name(owner_part)
        if "/" in owner_norm:
            base_segments = owner_norm.rsplit("/", 1)[0].split("/")
        else:
            base_segments = []

    res_segments = list(base_segments)
    for seg in target.split("/"):
        if not seg or seg == ".":
            continue
        elif seg == "..":
            if not res_segments:
                raise ValueError(
                    f"Part URI escapes package bounds: owner='{owner_part}', uri='{uri}'"
                )
            res_segments.pop()
        else:
            res_segments.append(seg)

    resolved = "/".join(res_segments)
    if return_fragment:
        return resolved, fragment
    return resolved


def relative_part_uri(owner_part: str, target_part: str) -> str:
    """Compute relative URI path from owner part directory to target part."""
    owner_norm = normalize_part_name(owner_part)
    target_norm = normalize_part_name(target_part)

    if not owner_norm:
        return target_norm

    from_dirs = owner_norm.split("/")[:-1] if "/" in owner_norm else []
    to_parts = target_norm.split("/")

    # Strip common leading directory components
    while from_dirs and to_parts and from_dirs[0] == to_parts[0]:
        from_dirs.pop(0)
        to_parts.pop(0)

    prefix = "../" * len(from_dirs)
    return prefix + "/".join(to_parts)


def get_rels_path(owner_part: str) -> str:
    """Compute the path of the .rels part for a given owner part name.

    Package-level root ('') -> '_rels/.rels'
    'xl/workbook.xml' -> 'xl/_rels/workbook.xml.rels'
    'workbook.xml' -> '_rels/workbook.xml.rels'
    """
    owner = normalize_part_name(owner_part)
    if not owner:
        return "_rels/.rels"
    if "/" in owner:
        dir_name, file_name = owner.rsplit("/", 1)
        return f"{dir_name}/_rels/{file_name}.rels"
    return f"_rels/{owner}.rels"


# Backwards compatibility alias
_get_rels_path = get_rels_path


def get_owner_from_rels_path(rels_path: str) -> str:
    """Compute owner part name from a .rels part path.

    '_rels/.rels' -> ''
    'xl/_rels/workbook.xml.rels' -> 'xl/workbook.xml'
    '_rels/foo.xml.rels' -> 'foo.xml'
    """
    path = normalize_part_name(rels_path)
    if path == "_rels/.rels":
        return ""
    if "/_rels/" in path:
        dir_name, rels_name = path.rsplit("/_rels/", 1)
        if rels_name.endswith(".rels"):
            part_name = rels_name[:-5]
            return f"{dir_name}/{part_name}" if dir_name else part_name
    elif path.startswith("_rels/") and path.endswith(".rels"):
        return path[6:-5]
    return ""


# Backwards compatibility alias
_get_owner_from_rels_path = get_owner_from_rels_path


@dataclass(frozen=True)
class Relationship:
    """Represents an OPC part relationship item."""

    id: str
    type: str
    target: str
    target_mode: str = "Internal"
    fragment: str = ""

    @property
    def is_external(self) -> bool:
        """Check if relationship points outside the package container."""
        return self.target_mode.strip().lower() == "external"

    def resolve_target(self, owner_part: str) -> str:
        """Resolve internal target part name relative to owner_part."""
        if self.is_external:
            return self.target
        return resolve_part_uri(owner_part, self.target)


def preserve_unmodified_parts(
    source: SourcePackage | zipfile.ZipFile | bytes | Path | str,
    target_zip: zipfile.ZipFile,
    modified_parts: set[str] | dict[str, Any],
    deleted_parts: set[str] | None = None,
) -> list[str]:
    """Copy unmodified parts directly from source container into target_zip byte-for-byte.

    Returns the list of preserved part names.
    """
    mod_set = {normalize_part_name(p) for p in modified_parts}
    del_set = {normalize_part_name(p) for p in (deleted_parts or set())}

    preserved: list[str] = []

    if isinstance(source, SourcePackage):
        for name, data in source._parts_data.items():
            norm = normalize_part_name(name)
            if norm not in mod_set and norm not in del_set:
                target_zip.writestr(name, data)
                preserved.append(norm)
    elif isinstance(source, zipfile.ZipFile):
        for info in source.infolist():
            if not info.is_dir():
                norm = normalize_part_name(info.filename)
                if norm not in mod_set and norm not in del_set:
                    target_zip.writestr(info.filename, source.read(info.filename))
                    preserved.append(norm)
    else:
        pkg = (
            SourcePackage.from_bytes(source)
            if isinstance(source, bytes)
            else SourcePackage.open(source)
        )
        for name, data in pkg._parts_data.items():
            norm = normalize_part_name(name)
            if norm not in mod_set and norm not in del_set:
                target_zip.writestr(name, data)
                preserved.append(norm)

    return preserved


class SourcePackage:
    """Immutable inspection wrapper over an OOXML / OPC ZIP container."""

    def __init__(
        self,
        parts_data: dict[str, bytes],
        content_types: dict[str, str],
        default_content_types: dict[str, str],
        relationships: dict[str, list[Relationship]],
    ) -> None:
        self._parts_data = parts_data
        self._content_types = content_types
        self._default_content_types = default_content_types
        self._relationships = relationships

    @classmethod
    def open(cls, file_path: Path | str) -> SourcePackage:
        """Open an OPC package from file path."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"Failed to read file: {exc}") from exc
        return cls.from_bytes(raw_bytes)

    @classmethod
    def from_bytes(cls, data: bytes) -> SourcePackage:
        """Open an OPC package from raw bytes."""
        try:
            buf = io.BytesIO(data)
            if not zipfile.is_zipfile(buf):
                raise ValueError("Not a valid ZIP/OPC package (header mismatch)")
            buf.seek(0)
            with zipfile.ZipFile(buf, "r") as zf:
                parts_data: dict[str, bytes] = {}
                for info in zf.infolist():
                    if not info.is_dir():
                        norm_name = normalize_part_name(info.filename)
                        parts_data[norm_name] = zf.read(info.filename)
        except zipfile.BadZipFile as exc:
            raise ValueError(f"Not a valid ZIP/OPC package: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"Not a valid ZIP/OPC package: {exc}") from exc

        content_types: dict[str, str] = {}
        default_content_types: dict[str, str] = {}
        relationships: dict[str, list[Relationship]] = {}

        # Parse [Content_Types].xml
        ct_bytes = parts_data.get("[Content_Types].xml")
        if ct_bytes:
            try:
                root = ET.fromstring(ct_bytes)
                for elem in root:
                    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if tag == "Default":
                        ext = (elem.get("Extension") or "").lower()
                        ct = elem.get("ContentType") or ""
                        if ext and ct:
                            default_content_types[ext] = ct
                    elif tag == "Override":
                        part_name = normalize_part_name(elem.get("PartName") or "")
                        ct = elem.get("ContentType") or ""
                        if part_name and ct:
                            content_types[part_name] = ct
            except Exception:
                pass

        # Parse .rels files
        for name, r_bytes in parts_data.items():
            if name.endswith(".rels"):
                owner = get_owner_from_rels_path(name)
                rels_list: list[Relationship] = []
                try:
                    root = ET.fromstring(r_bytes)
                    for elem in root:
                        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        if tag == "Relationship":
                            r_id = elem.get("Id") or ""
                            r_type = elem.get("Type") or ""
                            r_target = elem.get("Target") or ""
                            r_mode = elem.get("TargetMode") or "Internal"
                            frag = ""
                            if "#" in r_target:
                                _, frag = r_target.split("#", 1)
                            if r_id and r_type and r_target:
                                rels_list.append(
                                    Relationship(
                                        id=r_id,
                                        type=r_type,
                                        target=r_target,
                                        target_mode=r_mode,
                                        fragment=frag,
                                    )
                                )
                except Exception:
                    pass
                relationships[owner] = rels_list

        return cls(
            parts_data=parts_data,
            content_types=content_types,
            default_content_types=default_content_types,
            relationships=relationships,
        )

    def has_part(self, part_name: str) -> bool:
        """Check if part exists in package."""
        return normalize_part_name(part_name) in self._parts_data

    def read_part(self, part_name: str) -> bytes:
        """Read raw bytes of a package part."""
        norm_name = normalize_part_name(part_name)
        if norm_name not in self._parts_data:
            raise KeyError(f"Part not found in package: {part_name}")
        return self._parts_data[norm_name]

    def get_content_type(self, part_name: str) -> str | None:
        """Resolve content type for a given part name."""
        norm_name = normalize_part_name(part_name)
        if norm_name in self._content_types:
            return self._content_types[norm_name]
        ext = norm_name.rsplit(".", 1)[-1].lower() if "." in norm_name else ""
        return self._default_content_types.get(ext)

    def get_relationships(self, owner_part: str = "") -> list[Relationship]:
        """Get relationships defined for an owner part ('' for root relationships)."""
        norm_owner = normalize_part_name(owner_part)
        return list(self._relationships.get(norm_owner, []))

    def parts(self) -> list[str]:
        """List all normalized part names."""
        return list(self._parts_data.keys())

    def subtree(self, start_part: str = "") -> list[str]:
        """Traverse relationship DAG from start_part ('' for package root).

        Returns all reachable internal parts with cycle protection.
        """
        visited: set[str] = set()
        queue: list[str] = []
        ordered_parts: list[str] = []

        norm_start = normalize_part_name(start_part)
        if norm_start:
            visited.add(norm_start)
            ordered_parts.append(norm_start)
            queue.append(norm_start)
        else:
            queue.append("")

        while queue:
            curr = queue.pop(0)
            rels = self.get_relationships(curr)
            for r in rels:
                if r.is_external:
                    continue
                try:
                    target = resolve_part_uri(curr, r.target)
                    if target and target not in visited:
                        visited.add(target)
                        ordered_parts.append(target)
                        queue.append(target)
                except ValueError:
                    continue

        return ordered_parts

    def find_referrers(self, part_name: str) -> list[tuple[str, Relationship]]:
        """Find all (owner_part, relationship) pairs that point to part_name."""
        norm_target = normalize_part_name(part_name)
        referrers: list[tuple[str, Relationship]] = []

        for owner, rels in self._relationships.items():
            for r in rels:
                if not r.is_external:
                    try:
                        resolved = resolve_part_uri(owner, r.target)
                        if resolved == norm_target:
                            referrers.append((owner, r))
                    except ValueError:
                        pass
        return referrers


class PackageWriter:
    """Incrementally writes OPC packages carrying unmodified parts byte-for-byte."""

    def __init__(self, source_package: SourcePackage | None = None) -> None:
        self._source = source_package
        self._modified_parts: dict[str, bytes] = {}
        self._added_parts: dict[str, bytes] = {}
        self._deleted_parts: set[str] = set()
        self._part_content_types: dict[str, str] = {}

    def replace_part(
        self, part_name: str, content: bytes, content_type: str | None = None
    ) -> None:
        """Replace an existing part with new content."""
        norm = normalize_part_name(part_name)
        self._modified_parts[norm] = content
        self._deleted_parts.discard(norm)
        if content_type:
            self._part_content_types[norm] = content_type

    def add_part(
        self, part_name: str, content: bytes, content_type: str = "application/xml"
    ) -> None:
        """Add a new part to package."""
        norm = normalize_part_name(part_name)
        self._added_parts[norm] = content
        self._deleted_parts.discard(norm)
        self._part_content_types[norm] = content_type

    def delete_part(self, part_name: str) -> None:
        """Mark a part for deletion from package."""
        norm = normalize_part_name(part_name)
        self._deleted_parts.add(norm)
        self._modified_parts.pop(norm, None)
        self._added_parts.pop(norm, None)
        self._part_content_types.pop(norm, None)

    def _build_content_types_xml(
        self, active_parts: dict[str, bytes]
    ) -> bytes:
        """Reconstruct [Content_Types].xml reflecting all additions, overrides, and deletions."""
        defaults: dict[str, str] = {}
        overrides: dict[str, str] = {}

        if self._source:
            defaults.update(self._source._default_content_types)
            for part, ct in self._source._content_types.items():
                if part in active_parts and part != "[Content_Types].xml":
                    overrides[part] = ct

        # Standard baseline defaults if missing
        if "rels" not in defaults:
            defaults["rels"] = "application/vnd.openxmlformats-package.relationships+xml"
        if "xml" not in defaults:
            defaults["xml"] = "application/xml"

        # Apply specific content types from writer
        for part, ct in self._part_content_types.items():
            if part in active_parts and part != "[Content_Types].xml":
                overrides[part] = ct

        root = ET.Element(
            "Types",
            xmlns=NS_CONTENT_TYPES,
        )
        for ext in sorted(defaults.keys()):
            ET.SubElement(root, "Default", Extension=ext, ContentType=defaults[ext])

        for part in sorted(overrides.keys()):
            ET.SubElement(
                root, "Override", PartName=f"/{part}", ContentType=overrides[part]
            )

        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    def to_bytes(self) -> bytes:
        """Serialize package into a complete ZIP byte buffer with byte-for-byte carry."""
        active_parts: dict[str, bytes] = {}

        # 1. Carry unmodified parts from source package byte-for-byte
        if self._source:
            for part_name, raw_bytes in self._source._parts_data.items():
                if (
                    part_name not in self._deleted_parts
                    and part_name not in self._modified_parts
                    and part_name != "[Content_Types].xml"
                ):
                    active_parts[part_name] = raw_bytes

        # 2. Add modified parts
        for part_name, raw_bytes in self._modified_parts.items():
            if part_name != "[Content_Types].xml":
                active_parts[part_name] = raw_bytes

        # 3. Add newly added parts
        for part_name, raw_bytes in self._added_parts.items():
            if part_name != "[Content_Types].xml":
                active_parts[part_name] = raw_bytes

        # 4. Handle [Content_Types].xml
        has_mutations = bool(
            self._added_parts
            or self._deleted_parts
            or self._part_content_types
            or not self._source
        )
        if "[Content_Types].xml" in self._modified_parts:
            active_parts["[Content_Types].xml"] = self._modified_parts["[Content_Types].xml"]
        elif has_mutations:
            active_parts["[Content_Types].xml"] = self._build_content_types_xml(active_parts)
        elif self._source and "[Content_Types].xml" in self._source._parts_data:
            active_parts["[Content_Types].xml"] = self._source._parts_data["[Content_Types].xml"]
        else:
            active_parts["[Content_Types].xml"] = self._build_content_types_xml(active_parts)

        # 5. Pack into ZIP archive with deterministic ordering
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Always write [Content_Types].xml first per OPC convention
            if "[Content_Types].xml" in active_parts:
                zf.writestr("[Content_Types].xml", active_parts["[Content_Types].xml"])

            # Write _rels/.rels next if present
            if "_rels/.rels" in active_parts:
                zf.writestr("_rels/.rels", active_parts["_rels/.rels"])

            # Write remaining parts in deterministic sorted order
            for part_name in sorted(active_parts.keys()):
                if part_name not in ("[Content_Types].xml", "_rels/.rels"):
                    zf.writestr(part_name, active_parts[part_name])

        return buf.getvalue()

    def save(self, target_path: Path | str) -> None:
        """Atomically save the package to disk avoiding corruption."""
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = self.to_bytes()

        # Atomic write: write to NamedTemporaryFile in same directory, fsync, then atomic replace
        temp_file = tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".tmp_opc_", delete=False
        )
        temp_path = Path(temp_file.name)
        try:
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()
            os.replace(temp_path, path)
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise
