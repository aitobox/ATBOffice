"""Strict Schema Ordering according to ECMA-376 for OOXML elements."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Sequence

# Canonical ECMA-376 child tag ordering tables
SCHEMA_ORDERS: dict[str, list[str]] = {
    # SpreadsheetML Worksheet: s:CT_Worksheet
    "spreadsheetml_worksheet": [
        "sheetPr",
        "dimension",
        "sheetViews",
        "sheetFormatPr",
        "cols",
        "sheetData",
        "sheetCalcPr",
        "sheetProtection",
        "protectedRanges",
        "scenarios",
        "autoFilter",
        "sortState",
        "dataConsolidate",
        "customSheetViews",
        "mergeCells",
        "phoneticPr",
        "conditionalFormatting",
        "dataValidations",
        "hyperlinks",
        "printOptions",
        "pageMargins",
        "pageSetup",
        "headerFooter",
        "rowBreaks",
        "colBreaks",
        "customProperties",
        "cellWatches",
        "ignoredErrors",
        "smartTags",
        "drawing",
        "legacyDrawing",
        "legacyDrawingHF",
        "drawingHF",
        "picture",
        "oleObjects",
        "controls",
        "webPublishItems",
        "tableParts",
        "extLst",
    ],
    # SpreadsheetML Workbook: s:CT_Workbook
    "spreadsheetml_workbook": [
        "fileVersion",
        "fileSharing",
        "workbookPr",
        "workbookProtection",
        "bookViews",
        "sheets",
        "functionGroups",
        "externalReferences",
        "definedNames",
        "calcPr",
        "oleSize",
        "customWorkbookViews",
        "pivotCaches",
        "smartTagPr",
        "smartTagTypes",
        "webPublishing",
        "fileRecoveryPr",
        "webPublishObjects",
        "extLst",
    ],
    # SpreadsheetML Stylesheet: s:CT_Stylesheet
    "spreadsheetml_styles": [
        "numFmts",
        "fonts",
        "fills",
        "borders",
        "cellStyleXfs",
        "cellXfs",
        "cellStyles",
        "dxfs",
        "tableStyles",
        "colors",
        "extLst",
    ],
    # Common WordprocessingML Paragraph Properties: w:CT_PPr
    "wordprocessingml_ppr": [
        "pStyle",
        "keepNext",
        "keepLines",
        "pageBreakBefore",
        "framePr",
        "widowControl",
        "numPr",
        "suppressLineNumbers",
        "pBdr",
        "shd",
        "tabs",
        "suppressAutoHyphens",
        "kinsoku",
        "wordWrap",
        "overflowPunct",
        "topLinePunct",
        "autoSpaceDE",
        "autoSpaceDN",
        "bidi",
        "adjustRightInd",
        "snapToGrid",
        "spacing",
        "ind",
        "contextualSpacing",
        "mirrorIndents",
        "suppressOverlap",
        "jc",
        "textDirection",
        "textAlignment",
        "textboxTightWrap",
        "outlineLvl",
        "divId",
        "cnfStyle",
        "rPr",
        "sectPr",
        "pPrChange",
    ],
    # Common WordprocessingML Run Properties: w:CT_RPr
    "wordprocessingml_rpr": [
        "rStyle",
        "rFonts",
        "b",
        "bCs",
        "i",
        "iCs",
        "caps",
        "smallCaps",
        "strike",
        "dstrike",
        "outline",
        "shadow",
        "emboss",
        "imprint",
        "noProof",
        "snapToGrid",
        "vanish",
        "webHidden",
        "color",
        "spacing",
        "w",
        "kern",
        "position",
        "sz",
        "szCs",
        "highlight",
        "u",
        "effect",
        "bdr",
        "shd",
        "fitText",
        "vertAlign",
        "rtl",
        "cs",
        "em",
        "lang",
        "eastAsianLayout",
        "specVanish",
        "oMath",
        "rPrChange",
    ],
}

# Aliases
SCHEMA_ORDERS["worksheet"] = SCHEMA_ORDERS["spreadsheetml_worksheet"]
SCHEMA_ORDERS["workbook"] = SCHEMA_ORDERS["spreadsheetml_workbook"]
SCHEMA_ORDERS["styles"] = SCHEMA_ORDERS["spreadsheetml_styles"]
SCHEMA_ORDERS["styleSheet"] = SCHEMA_ORDERS["spreadsheetml_styles"]


def _strip_ns(tag: str) -> str:
    """Extract local tag name from Clark notation or prefixed tag."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    if ":" in tag:
        return tag.split(":", 1)[1]
    return tag


def enforce_schema_order(root_element: ET.Element, schema_family: str) -> None:
    """Sort child elements of root_element in-place to adhere to ECMA-376 schema.
    
    Args:
        root_element: The XML Element whose immediate children need to be reordered.
        schema_family: The schema order family key (e.g. 'spreadsheetml_worksheet').

    Raises:
        KeyError: If the schema_family is not defined in SCHEMA_ORDERS.
    """
    if schema_family not in SCHEMA_ORDERS:
        raise KeyError(f"Unknown schema family: {schema_family}")

    order_list: Sequence[str] = SCHEMA_ORDERS[schema_family]
    order_index: dict[str, int] = {name: idx for idx, name in enumerate(order_list)}

    # Index children with original sequence to guarantee stable sort for unknown tags
    children_with_idx = list(enumerate(root_element))

    def sort_key(item: tuple[int, ET.Element]) -> tuple[int, int]:
        orig_idx, elem = item
        local_name = _strip_ns(elem.tag)
        if local_name in order_index:
            return (order_index[local_name], orig_idx)
        return (len(order_list), orig_idx)

    sorted_children = sorted(children_with_idx, key=sort_key)
    root_element[:] = [elem for _, elem in sorted_children]
