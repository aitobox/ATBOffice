"""Markup Compatibility (``mc:AlternateContent``) support for the Lectern PPTX I/O.

Reading: pick the branch of an ``mc:AlternateContent`` element the reader understands
(:func:`select_branch`).

Writing: an unedited top-level shape that was loaded from an ``mc:AlternateContent``
block is written back verbatim (:class:`AltContentSource`), with relationship ids and
``cNvPr/@id`` values remapped to the ones the writer allocates for the new part.
"""

from __future__ import annotations

import io
import json
import posixpath
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from atboffice.vfs import etree as ET

NS_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_IMAGE_SUFFIX = "/image"

# Namespace prefixes whose ``mc:Choice`` content the reader can interpret.
# a14 = DrawingML 2010 (inline OMML math via a14:m, plus ignorable drawing extensions).
SUPPORTED_REQUIRES: frozenset[str] = frozenset({"a14"})

# Well-known prefixes kept stable when an AlternateContent block is re-serialized, so
# that ``Requires="a14"`` still names a declared prefix in the written part.
_KNOWN_PREFIXES: dict[str, str] = {
    "mc": NS_MC,
    "a14": "http://schemas.microsoft.com/office/drawing/2010/main",
    "a16": "http://schemas.microsoft.com/office/drawing/2014/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
    "p15": "http://schemas.microsoft.com/office/powerpoint/2012/main",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag.split(":")[-1]


def _safe_register(prefix: str, uri: str) -> None:
    """Register ``prefix -> uri`` as the preferred prefix for newly created elements.

    Parsed elements keep their own prefixes (lxml), so this only matters for markup
    the writers create from scratch.
    """
    if not prefix or not uri:
        return
    try:
        ET.register_namespace(prefix, uri)
    except ValueError:  # reserved "ns<digits>" / "xml" prefixes
        pass


for _p, _u in _KNOWN_PREFIXES.items():
    _safe_register(_p, _u)


def is_alternate_content(elem: ET.Element) -> bool:
    return elem.tag == f"{{{NS_MC}}}AlternateContent"


def requires_prefixes(choice: ET.Element) -> list[str]:
    return (choice.get("Requires") or "").split()


def select_branch(ac: ET.Element) -> ET.Element | None:
    """Return the ``mc:Choice`` or ``mc:Fallback`` element to read, or None.

    The first Choice whose ``Requires`` prefixes are all supported wins; otherwise the
    Fallback is used. Empty branches yield None.
    """
    fallback: ET.Element | None = None
    for branch in ac:
        name = _local(branch.tag)
        if name == "Choice":
            reqs = requires_prefixes(branch)
            if reqs and all(r in SUPPORTED_REQUIRES for r in reqs):
                return branch if len(branch) else None
        elif name == "Fallback" and fallback is None:
            fallback = branch
    if fallback is not None and len(fallback):
        return fallback
    return None


def collect_namespaces(part_bytes: bytes) -> dict[str, str]:
    """Collect every ``prefix -> uri`` declaration of an XML part (first one wins)."""
    found: dict[str, str] = {}
    try:
        for _event, (prefix, uri) in ET.iterparse(io.BytesIO(part_bytes), events=("start-ns",)):
            found.setdefault(prefix, uri)
    except ET.ParseError:
        pass
    return found


def shape_fingerprint(shape: Any) -> str:
    return json.dumps(shape.to_dict(), sort_keys=True, default=str)


@dataclass
class AltContentSource:
    """Raw ``mc:AlternateContent`` block a shape was loaded from."""

    xml: str
    rels: dict[str, str] = field(default_factory=dict)  # rId -> media part path
    namespaces: dict[str, str] = field(default_factory=dict)  # Requires prefix -> uri
    fingerprint: str = ""


def capture(
    ac: ET.Element,
    slide_path: str,
    rel_map: dict[str, Any],
    part_namespaces: dict[str, str],
    read_media: Callable[[str], bytes | None],
) -> AltContentSource | None:
    """Snapshot an AlternateContent element for verbatim write-back.

    Returns None when the block references a relationship that cannot be carried over
    safely (external targets, hyperlinks, OLE objects, missing parts).
    """
    rels: dict[str, str] = {}
    for el in ac.iter():
        for key, val in el.attrib.items():
            if not key.startswith(f"{{{NS_R}}}") or not val:
                continue
            rel = rel_map.get(val)
            if rel is None or getattr(rel, "is_external", False):
                return None
            if not str(getattr(rel, "type", "")).endswith(REL_IMAGE_SUFFIX):
                return None
            target = posixpath.normpath(
                posixpath.join(posixpath.dirname(slide_path), rel.target)
            ).lstrip("/")
            if read_media(target) is None:
                return None
            rels[val] = target

    namespaces: dict[str, str] = {}
    for el in ac.iter(f"{{{NS_MC}}}Choice"):
        for prefix in requires_prefixes(el):
            uri = part_namespaces.get(prefix) or _KNOWN_PREFIXES.get(prefix)
            if not uri:
                return None
            namespaces[prefix] = uri
            _safe_register(prefix, uri)

    return AltContentSource(
        xml=ET.tostring(ac, encoding="unicode"),
        rels=rels,
        namespaces=namespaces,
    )


def render_preserved(
    shape: Any,
    id_resolver: Callable[[str], str],
    media_resolver: Callable[[str], str] | None,
) -> str | None:
    """Return the shape's original AlternateContent XML, or None if it must be re-serialized.

    The raw block is only reused while the shape still matches its load-time fingerprint.
    """
    src: AltContentSource | None = getattr(shape, "alt_content", None)
    if src is None or not src.fingerprint or shape_fingerprint(shape) != src.fingerprint:
        return None
    if src.rels and media_resolver is None:
        return None

    try:
        root = ET.fromstring(src.xml)
    except ET.ParseError:
        return None

    new_rids: dict[str, str] = {}
    for old_rid, media_key in src.rels.items():
        new_rid = media_resolver(media_key) if media_resolver else ""
        if not new_rid:
            return None
        new_rids[old_rid] = new_rid

    for el in root.iter():
        for key, val in list(el.attrib.items()):
            if key.startswith(f"{{{NS_R}}}") and val in new_rids:
                el.set(key, new_rids[val])

    # Choice and Fallback describe the same object: the n-th cNvPr of every branch maps
    # to the same new id, the first one to the shape's own id (used by animations).
    for branch in root:
        for n, c_nv_pr in enumerate(e for e in branch.iter() if _local(e.tag) == "cNvPr"):
            key = shape.id if n == 0 else f"{shape.id}#ac{n}"
            c_nv_pr.set("id", id_resolver(key))

    return ET.tostring(root, encoding="unicode")
