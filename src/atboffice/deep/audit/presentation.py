"""PowerPoint ECMA-376 feature extraction and presentation audit engine.

Ported and refined from .vibeoffice/tests/lectern/loss-audit.py.
"""

from __future__ import annotations

import collections
import re
from collections.abc import Callable

SLIDES = r"ppt/slides/slide\d+\.xml$"


def _part(files: dict[str, str], pat: str) -> str:
    return "\n".join(x for n, x in files.items() if re.search(pat, n))


def _cnt(
    pat: str, where: str = SLIDES
) -> Callable[[list[str], dict[str, str]], int]:
    return lambda names, f: len(re.findall(pat, _part(f, where)))


def _parts(pat: str) -> Callable[[list[str], dict[str, str]], int]:
    return lambda names, f: sum(1 for n in names if re.search(pat, n))


def _rel_targets(files: dict[str, str], prefix: str) -> collections.Counter[str]:
    c: collections.Counter[str] = collections.Counter()
    for n, x in files.items():
        if n.endswith(".rels") and re.match(prefix, n):
            for t in re.findall(r'Type="[^"]*/([^"/]+)"', x):
                c[t] += 1
    return c


PRESENTATION_FEATURES: dict[str, Callable[[list[str], dict[str, str]], int]] = {
    "slides": _parts(SLIDES),
    "slide masters": _parts(r"ppt/slideMasters/slideMaster\d+\.xml$"),
    "slide layouts": _parts(r"ppt/slideLayouts/slideLayout\d+\.xml$"),
    "comments": lambda names, f: (
        _rel_targets(f, r"ppt/slides/_rels/")["comments"]
        + len(re.findall(r"<p188:cm\b|<p:cm\b", _part(f, r"ppt/comments/")))
    ),
    "video / audio on a slide": lambda names, f: sum(
        _rel_targets(f, r"ppt/slides/_rels/")[k]
        for k in ("video", "audio", "media")
    ),
    "VBA macros": lambda names, f: sum(
        1 for n in names if n.lower().endswith("vbaproject.bin")
    ),
    "custom XML parts / tags": lambda names, f: sum(
        1
        for n in names
        if n.startswith("customXml/") or n.startswith("ppt/tags/")
    ),
    "custom document properties": lambda names, f: int(
        "docProps/custom.xml" in names
    ),
    "slide transitions": _cnt(r"<p:transition\b"),
    "slide timing / animations": _cnt(r"<p:timing\b"),
    "speaker notes": _parts(r"ppt/notesSlides/notesSlide\d+\.xml$"),
    "SmartArt": lambda names, f: sum(
        1 for n in names if re.match(r"ppt/diagrams/data\d+\.xml$", n)
    ),
    "charts": lambda names, f: sum(
        1 for n in names if re.match(r"ppt/charts/chart\d+\.xml$", n)
    ),
    "tables": _cnt(r"<a:tbl\b"),
    "AutoShapes": _cnt(r"<p:sp\b"),
    "pictures": _cnt(r"<p:pic\b"),
    "group shapes": _cnt(r"<p:grpSp\b"),
    "hyperlinks": _cnt(r'<a:hlinkClick\b|<a:hlinkHover\b'),
    "themes": _parts(r"ppt/theme/theme\d+\.xml$"),
    "handout master": _parts(r"ppt/handoutMasters/handoutMaster\d+\.xml$"),
    "notes master": _parts(r"ppt/notesMasters/notesMaster\d+\.xml$"),
}


def extract_presentation_features(
    names: list[str], files: dict[str, str]
) -> dict[str, int]:
    """Extract all ECMA-376 feature counts from loaded PowerPoint package XML parts."""
    return {feat: fn(names, files) for feat, fn in PRESENTATION_FEATURES.items()}
