"""Excel ECMA-376 feature extraction and workbook audit engine.

Ported and refined from .vibeoffice/tests/ledger/loss-audit.py.
"""

from __future__ import annotations

import re
from collections.abc import Callable

SHEETS = r"xl/worksheets/sheet\d+\.xml$"


def _part(files: dict[str, str], pat: str) -> str:
    return "\n".join(x for n, x in files.items() if re.search(pat, n))


def _cnt(
    pat: str, where: str = SHEETS
) -> Callable[[list[str], dict[str, str]], int]:
    return lambda names, f: len(re.findall(pat, _part(f, where)))


def _parts(pat: str) -> Callable[[list[str], dict[str, str]], int]:
    return lambda names, f: sum(1 for n in names if re.search(pat, n))


EXCEL_FEATURES: dict[str, Callable[[list[str], dict[str, str]], int]] = {
    "worksheets": _parts(SHEETS),
    "chart sheets": _parts(r"xl/chartsheets/sheet\d+\.xml$"),
    "merged cells": _cnt(r"<mergeCell\b"),
    "data validation": _cnt(r"<dataValidation\b|<x14:dataValidation\b"),
    "conditional formatting": _cnt(
        r"<conditionalFormatting\b|<x14:conditionalFormatting\b"
    ),
    "data bars / icon sets (Excel 2010 extensions)": _cnt(
        r"<x14:dataBar\b|<x14:iconSet\b"
    ),
    "notes (comments)": _cnt(r"<comment\b", r"xl/comments\d*\.xml$"),
    "threaded comments": _cnt(r"<threadedComment\b", r"xl/threadedComments/"),
    "hyperlinks": _cnt(r"<hyperlink\b"),
    "defined names": _cnt(r"<definedName\b", r"xl/workbook\.xml$"),
    "charts": _parts(r"xl/charts/chart\d+\.xml$"),
    "pivot tables": _parts(r"xl/pivotTables/pivotTable\d+\.xml$"),
    "pivot caches": _parts(r"xl/pivotCache/pivotCacheDefinition\d+\.xml$"),
    "slicers": _parts(r"xl/slicers/slicer\d+\.xml$"),
    "timelines": _parts(r"xl/timelines/timeline\d+\.xml$"),
    "query tables": _parts(r"xl/queryTables/queryTable\d+\.xml$"),
    "table columns": _cnt(r"<tableColumn\b", r"xl/tables/table\d+\.xml$"),
    "drawing shapes": _cnt(r"<xdr:sp\b", r"xl/drawings/drawing\d+\.xml$"),
    "pictures": _cnt(r"<xdr:pic\b", r"xl/drawings/drawing\d+\.xml$"),
    "controls / ActiveX": _cnt(r"<mc:Choice\b[^>]*><xdr:sp\b|<v:shape\b"),
    "custom XML parts": lambda names, f: sum(
        1 for n in names if re.match(r"customXml/item\d+\.xml$", n)
    ),
    "custom document properties": lambda names, f: int(
        "docProps/custom.xml" in names
    ),
    "VBA macros": lambda names, f: sum(
        1 for n in names if n.lower().endswith("vbaproject.bin")
    ),
    "auto filter": _cnt(r"<autoFilter\b"),
    "sparklines": _cnt(r"<x14:sparkline\b"),
    "sheet protection": _cnt(r"<sheetProtection\b"),
    "freeze panes": _cnt(r'<pane\b[^>]*state="frozen"'),
    "sort state": _cnt(r"<sortState\b"),
}


def extract_excel_features(
    names: list[str], files: dict[str, str]
) -> dict[str, int]:
    """Extract all ECMA-376 feature counts from loaded Excel package XML parts."""
    return {feat: fn(names, files) for feat, fn in EXCEL_FEATURES.items()}
