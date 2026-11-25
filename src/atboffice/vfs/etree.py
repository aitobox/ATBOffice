"""ElementTree-compatible XML API backed by lxml.

All OOXML code imports ``from atboffice.vfs import etree as ET`` instead of
``xml.etree.ElementTree``. lxml (the engine behind python-docx and python-pptx)
keeps the original namespace prefixes and declarations of every element it parses,
so markup that is carried through a save (``mc:AlternateContent`` with
``Requires="wp14"``, ``mc:Ignorable`` lists, vendor extensions) stays valid. The
standard library rewrites unknown prefixes to ``ns0``, ``ns1``... which breaks those
references.

The parser is configured safely: no network access, no entity expansion, and
comments / processing instructions are dropped so that iterating over children only
yields elements, as with ElementTree.
"""

from __future__ import annotations

from typing import Any

from lxml import etree as _lx
from lxml.etree import (  # noqa: F401 - re-exported API
    Comment,
    Element,
    ElementTree,
    ParseError,
    QName,
    SubElement,
    XMLSyntaxError,
    iterparse,
    register_namespace,
    tostring,
)

_PARSER = _lx.XMLParser(
    resolve_entities=False,
    no_network=True,
    huge_tree=True,
    remove_comments=True,
    remove_pis=True,
)

#: The element class, for ``isinstance`` checks and annotations.
ElementType = _lx._Element


def fromstring(text: str | bytes, parser: Any = None) -> Any:
    """Parse XML from a string or bytes with the safe parser.

    Unlike lxml, ElementTree accepts ``str`` input that carries an encoding
    declaration; that case is handled by encoding the text first.
    """
    if isinstance(text, str):
        text = text.encode("utf-8")
    return _lx.fromstring(text, parser=parser or _PARSER)


XML = fromstring


def parse(source: Any, parser: Any = None) -> Any:
    """Parse a file or file-like object into an ElementTree."""
    return _lx.parse(source, parser=parser or _PARSER)


def iselement(obj: Any) -> bool:
    """Return True for parsed or created elements (not comments)."""
    return isinstance(obj, _lx._Element) and isinstance(obj.tag, str)


def hoist_namespaces(root: Any) -> Any:
    """Declare every namespace used in ``root``'s subtree once, on ``root``.

    Writers assemble documents from new elements and from carried original
    fragments; each carried fragment brings its own ``xmlns`` declarations. Hoisting
    them gives compact output, and keeping every prefix declared at the top means
    prefixes that are referenced only inside attribute values (``mc:Ignorable``,
    ``mc:Choice Requires="wp14"``) stay resolvable.
    """
    top: dict[str, str] = {}
    for el in root.iter():
        for prefix, uri in el.nsmap.items():
            if prefix is not None:
                top.setdefault(prefix, uri)
    _lx.cleanup_namespaces(root, top_nsmap=top, keep_ns_prefixes=list(top))
    return root
