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
