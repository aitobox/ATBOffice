"""XML Parsing and Serialization utilities preserving UTF-8 declarations and schemas."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET


def parse_xml(content: str | bytes) -> ET.Element:
    """Parse XML string or bytes into an ElementTree Element."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return ET.fromstring(content)


def serialize_xml(
    element: ET.Element,
    encoding: str = "utf-8",
    xml_declaration: bool = True,
    standalone: bool = True,
) -> bytes:
    """Serialize an XML element to bytes.
    
    Ensures correct XML header declaration.
    """
    buf = io.BytesIO()
    tree = ET.ElementTree(element)
    tree.write(
        buf,
        encoding=encoding,
        xml_declaration=xml_declaration,
        default_namespace="",
        method="xml",
    )
    data = buf.getvalue()
    if xml_declaration and standalone and data.startswith(b"<?xml"):
        # Ensure standalone="yes" is preserved if needed
        end_decl = data.find(b"?>")
        if end_decl != -1 and b"standalone" not in data[:end_decl]:
            decl = data[:end_decl].rstrip() + b' standalone="yes"?>'
            data = decl + data[end_decl + 2:]
    return data


# ---------------------------------------------------------------------------
# lxml helpers for editing original package XML in place.
#
# ``xml.etree`` rewrites namespace prefixes (``wp14`` becomes ``ns3``) and drops
# anything a hand-written serializer does not model. Editing the original lxml
# tree keeps every element, attribute and prefix that we do not touch, which is
# the same technique python-docx and python-pptx use.
# ---------------------------------------------------------------------------

from lxml import etree as LET  # noqa: E402

# No network access, no entity expansion, but allow large worksheets.
_LXML_PARSER = LET.XMLParser(
    resolve_entities=False,
    no_network=True,
    huge_tree=True,
    remove_blank_text=False,
)


def parse_lxml(content: str | bytes) -> LET._Element:
    """Parse package XML with lxml using a safe parser."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return LET.fromstring(content, parser=_LXML_PARSER)


def serialize_lxml(root: LET._Element) -> bytes:
    """Serialize an lxml tree with the standard OOXML declaration."""
    return LET.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def local_name(element: LET._Element) -> str:
    """Return the tag name of an element without its namespace."""
    tag = element.tag
    if not isinstance(tag, str):  # comments and processing instructions
        return ""
    return tag.rsplit("}", 1)[-1]


def namespace_of(element: LET._Element) -> str:
    """Return the namespace URI of an element (``""`` when it has none)."""
    tag = element.tag
    return tag[1:].split("}", 1)[0] if isinstance(tag, str) and tag.startswith("{") else ""


def find_local(parent: LET._Element | None, name: str) -> LET._Element | None:
    """Return the first direct child whose local name is ``name``."""
    if parent is None:
        return None
    for child in parent:
        if local_name(child) == name:
            return child
    return None


def find_all_local(parent: LET._Element | None, name: str) -> list[LET._Element]:
    """Return every direct child whose local name is ``name``."""
    if parent is None:
        return []
    return [child for child in parent if local_name(child) == name]


def parse_fragment(
    xml: str, namespace: str, prefixes: dict[str, str] | None = None
) -> list[LET._Element]:
    """Parse unprefixed element markup as children of ``namespace``.

    Writers generate markup such as ``<font><b/></font>``. Wrapping it in an element
    that declares ``namespace`` as the default puts the fragment in the same
    namespace as the document it is inserted into.
    """
    decls = "".join(f' xmlns:{p}="{uri}"' for p, uri in (prefixes or {}).items())
    wrapper = parse_lxml(f'<w xmlns="{namespace}"{decls}>{xml}</w>')
    return list(wrapper)


def insert_in_order(parent: LET._Element, child: LET._Element, order: list[str]) -> None:
    """Insert ``child`` before the first sibling that must follow it in ``order``."""
    name = local_name(child)
    try:
        rank = order.index(name)
    except ValueError:
        parent.append(child)
        return
    following = set(order[rank + 1 :])
    for index, sibling in enumerate(parent):
        if local_name(sibling) in following:
            parent.insert(index, child)
            return
    parent.append(child)


def ensure_child(parent: LET._Element, name: str, order: list[str]) -> LET._Element:
    """Return the child called ``name``, creating it in schema order when missing."""
    existing = find_local(parent, name)
    if existing is not None:
        return existing
    ns = namespace_of(parent)
    child = LET.Element(f"{{{ns}}}{name}" if ns else name)
    insert_in_order(parent, child, order)
    return child
