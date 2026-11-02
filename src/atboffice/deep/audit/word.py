"""Word ECMA-376 feature extraction and text audit engine.

Ported and refined from .vibeoffice/tests/quire/loss-audit.py.
"""

from __future__ import annotations

import re
from collections.abc import Callable

BODY = r"word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$"


def _part(files: dict[str, str], pat: str) -> str:
    return "\n".join(x for n, x in files.items() if re.search(pat, n))


def _cnt(
    pat: str, where: str = BODY, flags: int = 0
) -> Callable[[list[str], dict[str, str]], int]:
    return lambda names, f: len(re.findall(pat, _part(f, where), flags))


WORD_FEATURES: dict[str, Callable[[list[str], dict[str, str]], int]] = {
    "comments": _cnt(r"<w:comment\b", r"word/comments\.xml$"),
    "comment replies / resolved state (commentsExtended)": _cnt(
        r"<w15:commentEx\b", r"word/commentsExtended\.xml$"
    ),
    "footnotes": _cnt(r"<w:footnote\b(?![^>]*w:type=)", r"word/footnotes\.xml$"),
    "endnotes": _cnt(r"<w:endnote\b(?![^>]*w:type=)", r"word/endnotes\.xml$"),
    "headers / footers": lambda names, f: sum(
        1 for n in names if re.match(r"word/(header|footer)\d*\.xml$", n)
    ),
    "tracked insertions / deletions": _cnt(r"<w:(ins|del)\b"),
    "tracked formatting changes": _cnt(
        r"<w:(rPrChange|pPrChange|sectPrChange|tblPrChange)\b"
    ),
    "fields (TOC, PAGE, REF, …)": _cnt(
        r'<w:fldSimple\b|<w:fldChar\b[^>]*w:fldCharType="begin"'
    ),
    "content controls": _cnt(r"<w:sdt>|<w:sdt\b"),
    "legacy form fields": _cnt(r"<w:ffData\b"),
    "bookmarks": _cnt(r'<w:bookmarkStart\b(?![^>]*w:name="_GoBack")'),
    "hyperlinks": _cnt(r"<w:hyperlink\b"),
    "pictures": _cnt(r"<pic:pic\b|<v:imagedata\b"),
    "text boxes": _cnt(r"<w:txbxContent\b"),
    "drawing shapes (wps)": _cnt(r"<wps:wsp\b"),
    "VML shapes": _cnt(r"<v:(shape|rect|oval|roundrect|line|polyline)\b"),
    "equations": _cnt(r"<m:oMath\b"),
    "tables": _cnt(r"<w:tbl>"),
    "sections": _cnt(r"<w:sectPr\b", r"word/document\.xml$"),
    "multi-column sections": _cnt(r'<w:cols\b[^>]*w:num="[2-9]'),
    "page borders": _cnt(r"<w:pgBorders\b", r"word/document\.xml$"),
    "line numbering": _cnt(r"<w:lnNumType\b", r"word/document\.xml$"),
    "document background colour": _cnt(r"<w:background\b", r"word/document\.xml$"),
    "drop caps / frames": _cnt(r"<w:framePr\b"),
    "embedded OLE objects": _cnt(r"<o:OLEObject\b|<w:object\b"),
    "charts": lambda names, f: sum(
        1 for n in names if re.match(r"word/charts/chart\d+\.xml$", n)
    ),
    "SmartArt": lambda names, f: sum(
        1 for n in names if re.match(r"word/diagrams/data\d+\.xml$", n)
    ),
    "Word 2010+ text effects": _cnt(
        r"<w14:(glow|textOutline|textFill|ligatures|shadow|reflection)\b"
    ),
    "smart tags / custom XML markup": _cnt(r"<w:(smartTag|customXml)\b"),
    "permission ranges": _cnt(r"<w:permStart\b"),
    "ruby (phonetic guide)": _cnt(r"<w:ruby>"),
    "embedded HTML/RTF chunks (altChunk)": _cnt(
        r"<w:altChunk\b", r"word/document\.xml$"
    ),
    "glossary (building blocks, AutoText)": lambda names, f: int(
        any(n.startswith("word/glossary/") for n in names)
    ),
    "custom XML data parts": lambda names, f: sum(
        1 for n in names if re.match(r"customXml/item\d+\.xml$", n)
    ),
    "custom document properties": lambda names, f: int("docProps/custom.xml" in names),
    "VBA macros": lambda names, f: sum(
        1 for n in names if n.lower().endswith("vbaproject.bin")
    ),
    "embedded fonts": lambda names, f: sum(
        1 for n in names if re.match(r"word/fonts/", n)
    ),
    "document protection": _cnt(r"<w:documentProtection\b", r"word/settings\.xml$"),
    "attached template": _cnt(r"<w:attachedTemplate\b", r"word/settings\.xml$"),
    "paragraph styles defined": _cnt(
        r'<w:style\b[^>]*w:type="paragraph"', r"word/styles\.xml$"
    ),
    "character styles defined": _cnt(
        r'<w:style\b[^>]*w:type="character"', r"word/styles\.xml$"
    ),
    "table styles defined": _cnt(
        r'<w:style\b[^>]*w:type="table"', r"word/styles\.xml$"
    ),
    "list definitions": _cnt(r"<w:abstractNum\b", r"word/numbering\.xml$"),
    "picture bullet definitions": _cnt(
        r"<w:numPicBullet\b", r"word/numbering\.xml$"
    ),
    "picture bullet references": _cnt(
        r"<w:lvlPicBulletId\b", r"word/numbering\.xml$"
    ),
    "list identities (nsid)": _cnt(r"<w:nsid\b", r"word/numbering\.xml$"),
}


def extract_word_features(
    names: list[str], files: dict[str, str]
) -> dict[str, int]:
    """Extract all ECMA-376 feature counts from loaded Word package XML parts."""
    return {feat: fn(names, files) for feat, fn in WORD_FEATURES.items()}


def count_document_words(files: dict[str, str]) -> int:
    """Count visible words across body, headers, footers, and footnotes."""
    body_xml = _part(files, BODY)
    # Extract text content inside <w:t> tags
    texts = re.findall(r"<w:t\b[^>]*>(.*?)</w:t>", body_xml, flags=re.DOTALL)
    full_text = " ".join(texts)
    # Split by whitespace and count non-empty tokens
    words = [w for w in re.split(r"\s+", full_text) if w]
    return len(words)
