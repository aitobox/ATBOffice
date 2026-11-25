"""Read Excel tables (``xl/tables/table*.xml``) and custom ``<tableStyles>``.

Port of ``ledger/js/xlsx-read.js`` ``readTable`` and the ``tableStyles`` branch of
``readStyles``. Table parts themselves are carried verbatim by the writer through the
source package, so only the information needed for rendering is modelled here.
"""

from __future__ import annotations

import logging
import zipfile
from collections.abc import Sequence
from typing import Any

from atboffice.modules.spreadsheet.calc.references import parse_range
from atboffice.modules.spreadsheet.models.sheet_model import (
    SheetDataModel,
    Table,
    TableColumn,
    TableStyleInfo,
)
from atboffice.modules.spreadsheet.models.table_style import resolve_table_style
from atboffice.vfs import etree as ET

logger = logging.getLogger(__name__)

_R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _int(el: ET.Element, name: str, default: int) -> int:
    try:
        return int(el.get(name, default))
    except (TypeError, ValueError):
        return default


def _bool(el: ET.Element, name: str, default: bool = False) -> bool:
    v = el.get(name)
    if v is None:
        return default
    return v.lower() in ("1", "true")


def parse_table_styles(styles_root: ET.Element | None) -> list[dict[str, Any]]:
    """Custom ``<tableStyle>`` definitions.

    Returns ``[{name, pivot, table, elements: [{type, dxf_id}]}]``.
    """
    if styles_root is None:
        return []
    ts_el = styles_root.find("{*}tableStyles")
    if ts_el is None:
        return []
    out: list[dict[str, Any]] = []
    for st in ts_el.findall("{*}tableStyle"):
        name = st.get("name")
        if not name:
            continue
        out.append(
            {
                "name": name,
                "pivot": st.get("pivot") != "0",
                "table": st.get("table") != "0",
                "elements": [
                    {"type": e.get("type", ""), "dxf_id": _int(e, "dxfId", -1)}
                    for e in st.findall("{*}tableStyleElement")
                ],
            }
        )
    return out


def parse_table_part(
    content: bytes,
    part: str,
    index: int,
    theme_colors: Sequence[str] | None = None,
    custom_styles: Sequence[dict[str, Any]] | None = None,
    dxfs: Sequence[dict[str, Any]] | None = None,
) -> Table | None:
    """Parse one table part; returns None when the part or its ``ref`` is unusable."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        logger.warning("Skipping malformed table part %s", part)
        return None
    ref = root.get("ref") or ""
    rg = parse_range(ref) if ref else None
    if rg is None:
        logger.warning("Skipping table part %s with invalid ref %r", part, ref)
        return None

    name = root.get("name") or root.get("displayName") or f"Table{index}"
    table = Table(
        id=_int(root, "id", index),
        name=name,
        display_name=root.get("displayName") or name,
        ref=ref,
        r1=rg["r1"],
        c1=rg["c1"],
        r2=rg["r2"],
        c2=rg["c2"],
        header_row_count=_int(root, "headerRowCount", 1),
        totals_row_count=_int(root, "totalsRowCount", 0),
        has_auto_filter=root.find("{*}autoFilter") is not None,
        part=part,
    )
    cols_el = root.find("{*}tableColumns")
    if cols_el is not None:
        for i, col in enumerate(cols_el.findall("{*}tableColumn"), start=1):
            table.columns.append(
                TableColumn(
                    id=_int(col, "id", i),
                    name=col.get("name", ""),
                    totals_row_function=col.get("totalsRowFunction"),
                    totals_row_label=col.get("totalsRowLabel"),
                )
            )
    si = root.find("{*}tableStyleInfo")
    if si is not None:
        table.style_info = TableStyleInfo(
            name=si.get("name") or "",
            show_first_column=_bool(si, "showFirstColumn"),
            show_last_column=_bool(si, "showLastColumn"),
            show_row_stripes=_bool(si, "showRowStripes"),
            show_column_stripes=_bool(si, "showColumnStripes"),
        )
        table.spec = resolve_table_style(table.style_info.name, theme_colors, custom_styles, dxfs)
    return table


def parse_worksheet_tables(
    zip_file: zipfile.ZipFile,
    ws_root: ET.Element,
    sheet: SheetDataModel,
    sheet_rels: dict[str, tuple[str, str]],
    theme_colors: Sequence[str] | None = None,
    custom_styles: Sequence[dict[str, Any]] | None = None,
    dxfs: Sequence[dict[str, Any]] | None = None,
) -> None:
    """Read every ``<tablePart r:id>`` of a worksheet into ``sheet.tables``."""
    parts_el = ws_root.find("{*}tableParts")
    if parts_el is None:
        return
    names = set(zip_file.namelist())
    for tp in parts_el.findall("{*}tablePart"):
        rel = sheet_rels.get(tp.get(_R_ID) or "")
        if rel is None or rel[1] not in names:
            continue
        try:
            content = zip_file.read(rel[1])
        except (KeyError, zipfile.BadZipFile, OSError):
            logger.warning("Skipping unreadable table part %s", rel[1])
            continue
        table = parse_table_part(
            content,
            rel[1],
            len(sheet.tables) + 1,
            theme_colors,
            custom_styles,
            dxfs,
        )
        if table is not None:
            sheet.tables.append(table)
