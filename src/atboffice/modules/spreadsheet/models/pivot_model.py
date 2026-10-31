"""Pivot Table model, OOXML OPC preservation engine, and static summary calculation.

Replicates and extends .vibeoffice/public/ledger/js/pivots.js and dialogs2.js:
- Preserves xl/pivotCaches/pivotCacheDefinition*.xml and xl/pivotTables/pivotTable*.xml
  byte-for-byte when unmodified.
- Detects cell mutations in source ranges to trigger refreshOnLoad="1".
- Handles sheet/column deletion and line shifts.
- Provides a static cross-tabulation calculation engine (SUM, COUNT, AVERAGE, MAX, MIN, COUNTNUMS).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from typing import Any

from atboffice.modules.spreadsheet.calc.references import (
    col_name,
    parse_range,
    range_name,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    FormatDelta,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.vfs.opc import PackageWriter

NS_SPREADSHEETML = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_RELATIONSHIPS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"

REL_PIVOT_TABLE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotTable"
REL_PIVOT_CACHE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheDefinition"
)
REL_PIVOT_RECORDS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheRecords"
)

CT_PIVOT_TABLE = "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"
CT_PIVOT_CACHE_DEF = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml"
)
CT_PIVOT_CACHE_RECORDS = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheRecords+xml"
)


def _clean_tag(tag: str) -> str:
    """Strip XML namespace prefix from tag name."""
    return tag.split("}")[-1] if "}" in tag else tag


def _find_child(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    for child in element:
        if _clean_tag(child.tag) == name:
            return child
    return None


def _find_children(element: ET.Element | None, name: str) -> list[ET.Element]:
    if element is None:
        return []
    return [c for c in element if _clean_tag(c.tag) == name]


def _attr(element: ET.Element | None, name: str, default: str | None = None) -> str | None:
    if element is None:
        return default
    for k, v in element.attrib.items():
        if _clean_tag(k) == name or k == name:
            return v
    return default


def _parse_range_tuple(ref_str: str | None) -> tuple[int, int, int, int] | None:
    if not ref_str:
        return None
    parsed = parse_range(ref_str)
    if not parsed:
        return None
    return (parsed["r1"], parsed["c1"], parsed["r2"], parsed["c2"])


@dataclass
class PivotCacheSource:
    kind: str  # "worksheet", "consolidation", "external", "unknown"
    sheet_name: str
    ref: tuple[int, int, int, int] | None
    original_ref: str = ""
    name: str | None = None


@dataclass
class PivotCache:
    cache_id: int
    part_name: str
    sources: list[PivotCacheSource] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    records_part: str | None = None
    refresh: bool = False
    drop: str | None = None
    opaque: bool = False
    raw_bytes: bytes | None = None
    records_raw_bytes: bytes | None = None
    rel_id: str | None = None  # r:id in workbook.xml


@dataclass
class PivotTable:
    part_name: str
    name: str
    sheet_name: str
    cache_id: int
    location_ref: tuple[int, int, int, int] | None = None
    offsets: dict[str, int] = field(default_factory=dict)
    used_fields: list[int] = field(default_factory=list)
    drop: str | None = None
    notify: bool = False
    reshaped: bool = False
    edited: bool = False
    raw_bytes: bytes | None = None
    rel_id: str | None = None


@dataclass
class PivotContainer:
    caches: list[PivotCache] = field(default_factory=list)
    tables: list[PivotTable] = field(default_factory=list)

    def find_cache(self, cache_id: int) -> PivotCache | None:
        for c in self.caches:
            if c.cache_id == cache_id:
                return c
        return None

    def notify_cell_changed(self, sheet_name: str, r: int, c: int) -> None:
        """Mark associated cache for refreshOnLoad if cell inside source range changed."""
        for cache in self.caches:
            if cache.drop:
                continue
            for src in cache.sources:
                if src.sheet_name.lower() == sheet_name.lower() and src.ref:
                    r1, c1, r2, c2 = src.ref
                    if r1 <= r <= r2 and c1 <= c <= c2:
                        cache.refresh = True

    def notify_sheet_deleted(self, sheet_name: str) -> None:
        """Mark pivot tables or caches dropped if sheet is deleted."""
        for table in self.tables:
            if table.sheet_name.lower() == sheet_name.lower():
                table.drop = "The worksheet containing the pivot table was deleted."
                table.notify = False

        for cache in self.caches:
            for src in cache.sources:
                if src.sheet_name.lower() == sheet_name.lower():
                    cache.drop = "The pivot source was deleted."

    def notify_lines_shifted(self, sheet_name: str, axis: str, at: int, n: int) -> None:
        """Shift table location refs and source ranges when rows/cols inserted/deleted."""
        # axis: 'r' for rows, 'c' for columns
        for cache in self.caches:
            if cache.drop:
                continue
            for src in cache.sources:
                if src.sheet_name.lower() != sheet_name.lower() or not src.ref:
                    continue
                r1, c1, r2, c2 = src.ref
                if axis == "r":
                    if n > 0:
                        if at <= r1:
                            r1 += n
                            r2 += n
                        elif at <= r2:
                            r2 += n
                    else:
                        # Deletion
                        del_count = -n
                        if at + del_count <= r1:
                            r1 += n
                            r2 += n
                        elif at <= r1 and at + del_count > r2:
                            cache.drop = "The complete pivot source range was deleted."
                            continue
                        elif at <= r2:
                            r2 = max(r1, r2 + n)
                else:
                    if n > 0:
                        if at <= c1:
                            c1 += n
                            c2 += n
                        elif at <= c2:
                            c2 += n
                    else:
                        del_count = -n
                        if at + del_count <= c1:
                            c1 += n
                            c2 += n
                        elif at <= c1 and at + del_count > c2:
                            cache.drop = "The complete pivot source range was deleted."
                            continue
                        elif at <= c2:
                            c2 = max(c1, c2 + n)
                src.ref = (r1, c1, r2, c2)
                cache.refresh = True

        for table in self.tables:
            if table.drop or table.sheet_name.lower() != sheet_name.lower():
                continue
            if not table.location_ref:
                continue
            r1, c1, r2, c2 = table.location_ref
            if axis == "r":
                if n > 0:
                    if at <= r1:
                        r1 += n
                        r2 += n
                    elif at <= r2:
                        r2 += n
                else:
                    del_count = -n
                    if at + del_count <= r1:
                        r1 += n
                        r2 += n
                    elif at <= r1 and at + del_count > r2:
                        table.drop = "The complete pivot table output was deleted."
                        continue
                    elif at <= r2:
                        r2 = max(r1, r2 + n)
            else:
                if n > 0:
                    if at <= c1:
                        c1 += n
                        c2 += n
                    elif at <= c2:
                        c2 += n
                else:
                    del_count = -n
                    if at + del_count <= c1:
                        c1 += n
                        c2 += n
                    elif at <= c1 and at + del_count > c2:
                        table.drop = "The complete pivot table output was deleted."
                        continue
                    elif at <= c2:
                        c2 = max(c1, c2 + n)
            table.location_ref = (r1, c1, r2, c2)
            table.reshaped = True


# ==============================================================================
# OOXML Reader & Writer Functions
# ==============================================================================


def read_pivots_from_zip(z: zipfile.ZipFile, workbook: WorkbookModel) -> PivotContainer | None:
    """Discover, parse, and store PivotCache and PivotTable definitions from an XLSX zip archive."""
    caches: list[PivotCache] = []
    tables: list[PivotTable] = []

    # 1. Discover workbook.xml and its rels
    wb_part = "xl/workbook.xml"
    if wb_part not in z.namelist():
        for name in z.namelist():
            if name.lower().endswith("workbook.xml"):
                wb_part = name
                break

    if wb_part not in z.namelist():
        return None

    wb_dir = wb_part.rsplit("/", 1)[0] if "/" in wb_part else ""
    wb_file = wb_part.rsplit("/", 1)[-1]
    wb_rels_part = f"{wb_dir}/_rels/{wb_file}.rels" if wb_dir else f"_rels/{wb_part}.rels"

    wb_rels: dict[str, tuple[str, str]] = {}
    if wb_rels_part in z.namelist():
        try:
            root = ET.fromstring(z.read(wb_rels_part))
            for elem in root:
                rid = elem.get("Id")
                rel_type = _clean_tag(elem.get("Type", ""))
                target = elem.get("Target", "")
                if "/" in target and not target.startswith("/"):
                    # Resolve relative path
                    base = wb_dir
                    target_norm = f"{base}/{target}" if base else target
                elif target.startswith("/"):
                    target_norm = target.lstrip("/")
                else:
                    target_norm = f"{wb_dir}/{target}" if wb_dir else target
                # Normalize double dots
                segments: list[str] = []
                for s in target_norm.split("/"):
                    if not s or s == ".":
                        continue
                    elif s == "..":
                        if segments:
                            segments.pop()
                    else:
                        segments.append(s)
                resolved = "/".join(segments)
                if rid:
                    wb_rels[rid] = (rel_type, resolved)
        except Exception:
            pass

    # Read pivotCaches from workbook.xml
    try:
        wb_root = ET.fromstring(z.read(wb_part))
        pc_list_el = _find_child(wb_root, "pivotCaches")
        if pc_list_el is not None:
            for pc_el in _find_children(pc_list_el, "pivotCache"):
                cache_id = int(_attr(pc_el, "cacheId", "0") or "0")
                rid = _attr(pc_el, "id") or ""
                part_target = wb_rels.get(rid, (None, None))[1] if rid else None
                if not part_target or part_target not in z.namelist():
                    continue

                raw_bytes = z.read(part_target)
                cache_obj = PivotCache(
                    cache_id=cache_id,
                    part_name=part_target,
                    raw_bytes=raw_bytes,
                    rel_id=rid,
                )

                # Parse cache definition details
                try:
                    c_root = ET.fromstring(raw_bytes)
                    cs_el = _find_child(c_root, "cacheSource")
                    c_kind = _attr(cs_el, "type", "worksheet") or "worksheet"
                    cache_obj.sources = []
                    if c_kind == "worksheet":
                        ws_src_el = _find_child(cs_el, "worksheetSource")
                        s_name = _attr(ws_src_el, "sheet", "Sheet1") or "Sheet1"
                        ref_str = _attr(ws_src_el, "ref", "") or ""
                        parsed_ref = _parse_range_tuple(ref_str)
                        tbl_name = _attr(ws_src_el, "name")
                        cache_obj.sources.append(
                            PivotCacheSource(
                                kind="worksheet",
                                sheet_name=s_name,
                                ref=parsed_ref,
                                original_ref=ref_str,
                                name=tbl_name,
                            )
                        )
                    elif c_kind == "consolidation":
                        cache_obj.sources.append(
                            PivotCacheSource(kind="consolidation", sheet_name="", ref=None)
                        )
                    else:
                        cache_obj.sources.append(
                            PivotCacheSource(kind=c_kind, sheet_name="", ref=None)
                        )

                    cf_list_el = _find_child(c_root, "cacheFields")
                    if cf_list_el is not None:
                        cache_obj.fields = [
                            _attr(f, "name", "") or ""
                            for f in _find_children(cf_list_el, "cacheField")
                        ]
                except Exception:
                    cache_obj.opaque = True

                # Check cache definition rels for records part
                c_dir = part_target.rsplit("/", 1)[0] if "/" in part_target else ""
                c_file = part_target.rsplit("/", 1)[-1]
                c_rels_part = (
                    f"{c_dir}/_rels/{c_file}.rels" if c_dir else f"_rels/{part_target}.rels"
                )
                if c_rels_part in z.namelist():
                    try:
                        c_rels_root = ET.fromstring(z.read(c_rels_part))
                        for rel in c_rels_root:
                            if "pivotCacheRecords" in rel.get("Type", ""):
                                tgt = rel.get("Target", "")
                                tgt_norm = f"{c_dir}/{tgt}" if c_dir else tgt
                                segs: list[str] = []
                                for s in tgt_norm.split("/"):
                                    if not s or s == ".":
                                        continue
                                    elif s == "..":
                                        if segs:
                                            segs.pop()
                                    else:
                                        segs.append(s)
                                rec_part = "/".join(segs)
                                if rec_part in z.namelist():
                                    cache_obj.records_part = rec_part
                                    cache_obj.records_raw_bytes = z.read(rec_part)
                    except Exception:
                        pass

                caches.append(cache_obj)
    except Exception:
        pass

    # 2. Discover pivotTable definitions in worksheets
    for sheet_idx, sheet in enumerate(workbook.sheets, start=1):
        ws_dir = "xl/worksheets"
        ws_rels_part = f"{ws_dir}/_rels/sheet{sheet_idx}.xml.rels"

        if ws_rels_part not in z.namelist():
            continue

        try:
            ws_rels_root = ET.fromstring(z.read(ws_rels_part))
            for rel in ws_rels_root:
                rel_type = rel.get("Type", "")
                if "pivotTable" in rel_type:
                    tgt = rel.get("Target", "")
                    tgt_norm = f"{ws_dir}/{tgt}"
                    segs: list[str] = []
                    for s in tgt_norm.split("/"):
                        if not s or s == ".":
                            continue
                        elif s == "..":
                            if segs:
                                segs.pop()
                        else:
                            segs.append(s)
                    pt_part = "/".join(segs)
                    if pt_part not in z.namelist():
                        continue

                    raw_bytes = z.read(pt_part)
                    pt_root = ET.fromstring(raw_bytes)
                    name = _attr(pt_root, "name", f"PivotTable{len(tables) + 1}") or ""
                    cache_id = int(_attr(pt_root, "cacheId", "0") or "0")

                    loc_el = _find_child(pt_root, "location")
                    ref_str = _attr(loc_el, "ref") if loc_el is not None else ""
                    loc_ref = _parse_range_tuple(ref_str)

                    offsets: dict[str, int] = {}
                    if loc_el is not None:
                        for k in ("firstHeaderRow", "firstDataRow", "firstDataCol"):
                            v = _attr(loc_el, k)
                            if v is not None:
                                offsets[k] = int(v)

                    used_fields: list[int] = []
                    pf_list_el = _find_child(pt_root, "pivotFields")
                    if pf_list_el is not None:
                        for idx, pf in enumerate(_find_children(pf_list_el, "pivotField")):
                            if _attr(pf, "axis") or _attr(pf, "dataField") in ("1", "true"):
                                used_fields.append(idx)

                    tables.append(
                        PivotTable(
                            part_name=pt_part,
                            name=name,
                            sheet_name=sheet.name,
                            cache_id=cache_id,
                            location_ref=loc_ref,
                            offsets=offsets,
                            used_fields=used_fields,
                            raw_bytes=raw_bytes,
                            rel_id=rel.get("Id"),
                        )
                    )
        except Exception:
            pass

    if not caches and not tables:
        return None

    return PivotContainer(caches=caches, tables=tables)


def write_pivots_to_package(
    pkg_writer: PackageWriter,
    workbook: WorkbookModel,
    pivots: PivotContainer,
) -> None:
    """Serialize and write PivotCache and PivotTable parts into package with lossless carry."""
    retained_cache_ids = {t.cache_id for t in pivots.tables if not t.drop}

    for cache in pivots.caches:
        if cache.drop or cache.cache_id not in retained_cache_ids:
            pkg_writer.delete_part(cache.part_name)
            if cache.records_part:
                pkg_writer.delete_part(cache.records_part)
            continue

        if cache.refresh and cache.raw_bytes:
            # Set refreshOnLoad="1" on root <pivotCacheDefinition>
            try:
                root = ET.fromstring(cache.raw_bytes)
                root.attrib["refreshOnLoad"] = "1"
                # Update worksheetSource if sheet renamed
                cs_el = _find_child(root, "cacheSource")
                if cs_el is not None:
                    ws_src_el = _find_child(cs_el, "worksheetSource")
                    if ws_src_el is not None and cache.sources:
                        src = cache.sources[0]
                        ws_src_el.attrib["sheet"] = src.sheet_name
                        if src.ref:
                            r1, c1, r2, c2 = src.ref
                            ws_src_el.attrib["ref"] = range_name(
                                {"r1": r1, "c1": c1, "r2": r2, "c2": c2}
                            )
                modified_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                pkg_writer.add_part(cache.part_name, modified_bytes, CT_PIVOT_CACHE_DEF)
            except Exception:
                pkg_writer.add_part(cache.part_name, cache.raw_bytes, CT_PIVOT_CACHE_DEF)
        elif cache.raw_bytes:
            pkg_writer.add_part(cache.part_name, cache.raw_bytes, CT_PIVOT_CACHE_DEF)

        if cache.records_part and cache.records_raw_bytes:
            pkg_writer.add_part(cache.records_part, cache.records_raw_bytes, CT_PIVOT_CACHE_RECORDS)

    for table in pivots.tables:
        if table.drop:
            pkg_writer.delete_part(table.part_name)
            continue

        # If table was shifted/reshaped, update location ref
        if table.reshaped and table.raw_bytes:
            try:
                root = ET.fromstring(table.raw_bytes)
                loc_el = _find_child(root, "location")
                if loc_el is not None and table.location_ref:
                    r1, c1, r2, c2 = table.location_ref
                    new_ref = range_name({"r1": r1, "c1": c1, "r2": r2, "c2": c2})
                    loc_el.attrib["ref"] = new_ref
                table_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                pkg_writer.add_part(table.part_name, table_bytes, CT_PIVOT_TABLE)
            except Exception:
                pkg_writer.add_part(table.part_name, table.raw_bytes, CT_PIVOT_TABLE)
        elif table.raw_bytes:
            pkg_writer.add_part(table.part_name, table.raw_bytes, CT_PIVOT_TABLE)


# ==============================================================================
# Static Summary & Cross-Tabulation Calculation Engine
# ==============================================================================


@dataclass
class PivotConfig:
    source_sheet: str
    source_range: tuple[int, int, int, int]  # (r1, c1, r2, c2)
    row_field_col: int
    data_field_col: int
    col_field_col: int | None = None
    agg_func: str = "sum"  # "sum", "count", "average", "max", "min", "countNums"
    page_field_col: int | None = None
    page_filter_val: str | None = None
    target_sheet: str = "new"  # "new" or existing sheet name
    target_cell: tuple[int, int] = (0, 0)


AGG_FUNC_LABELS: dict[str, str] = {
    "sum": "Sum",
    "count": "Count",
    "average": "Average",
    "max": "Max",
    "min": "Min",
    "countNums": "Count Nums",
}


def _aggregate_values(vals: list[Any], func: str) -> Any:
    """Calculate the aggregated scalar value from a list of cell values."""
    nums: list[float] = []
    for v in vals:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            nums.append(float(v))
        elif isinstance(v, str):
            try:
                nums.append(float(v))
            except ValueError:
                pass

    match func.lower():
        case "count":
            return len([x for x in vals if x is not None and str(x) != ""])
        case "countnums":
            return len(nums)
        case "average":
            return (sum(nums) / len(nums)) if nums else "#DIV/0!"
        case "max":
            return max(nums) if nums else 0
        case "min":
            return min(nums) if nums else 0
        case _:  # default "sum"
            return sum(nums) if nums else 0


def build_pivot_table(
    workbook: WorkbookModel, config: PivotConfig
) -> tuple[SheetDataModel, tuple[int, int, int, int]]:
    """Generate a formatted cross-tabulation PivotTable report and render it to a worksheet.

    Replicates dialogs2.js: D.buildPivot.

    Returns:
        (target_sheet_model, bounding_box_tuple(r0, c0, end_r, end_c))
    """
    src_sheet = workbook.get_sheet_by_name(config.source_sheet)
    if not src_sheet:
        raise ValueError(f"Source worksheet '{config.source_sheet}' not found.")

    r1, c1, r2, c2 = config.source_range
    if r2 <= r1:
        raise ValueError("Source data range must contain at least one header row and one data row.")

    # Extract column headers
    def col_header(col_idx: int) -> str:
        val = src_sheet.get_cell_value(r1, col_idx)
        return str(val) if val is not None and str(val).strip() else col_name(col_idx)

    # Key extraction helper
    def key_of(row_idx: int, col_idx: int) -> str:
        val = src_sheet.get_cell_value(row_idx, col_idx)
        if val is None or str(val).strip() == "":
            return "(blank)"
        return str(val)

    # Collect and group data
    row_keys: list[str] = []
    col_keys: list[str] = []
    seen_row_keys: set[str] = set()
    seen_col_keys: set[str] = set()

    cells: dict[str, list[Any]] = {}
    row_tot: dict[str, list[Any]] = {}
    col_tot: dict[str, list[Any]] = {}
    grand_all: list[Any] = []

    has_col = config.col_field_col is not None

    for r in range(r1 + 1, r2 + 1):
        # Page/Filter field check
        if (
            config.page_field_col is not None
            and config.page_filter_val
            and config.page_filter_val != "(All)"
        ):
            if key_of(r, config.page_field_col) != config.page_filter_val:
                continue

        rk = key_of(r, config.row_field_col)
        if rk not in seen_row_keys:
            seen_row_keys.add(rk)
            row_keys.append(rk)

        ck = ""
        if has_col:
            ck = key_of(r, config.col_field_col)
            if ck not in seen_col_keys:
                seen_col_keys.add(ck)
                col_keys.append(ck)

        val = src_sheet.get_cell_value(r, config.data_field_col)
        cell_k = f"{rk}\x01{ck}"

        cells.setdefault(cell_k, []).append(val)
        row_tot.setdefault(rk, []).append(val)
        if has_col:
            col_tot.setdefault(ck, []).append(val)
        grand_all.append(val)

    # Sort keys naturally
    def sort_key(s: str) -> Any:
        try:
            return (0, float(s))
        except ValueError:
            return (1, s.lower())

    row_keys.sort(key=sort_key)
    col_keys.sort(key=sort_key)

    # Target destination resolution
    if config.target_sheet == "new":
        dst_sheet = workbook.add_sheet()
        r0, c0 = 2, 0
    else:
        existing = workbook.get_sheet_by_name(config.target_sheet)
        if existing is None:
            dst_sheet = workbook.add_sheet(name=config.target_sheet)
        else:
            dst_sheet = existing
        r0, c0 = config.target_cell

    # Styles
    BOLD = FormatDelta(bold=True)
    HEAD = FormatDelta(
        bold=True,
        bg_color="#C0C0C0",
        border_top=BorderStyle(style="thin", color="#808080"),
        border_bottom=BorderStyle(style="thin", color="#808080"),
    )
    TOT = FormatDelta(
        bold=True,
        bg_color="#E3E3E3",
        border_top=BorderStyle(style="thin", color="#808080"),
        border_bottom=BorderStyle(style="double", color="#808080"),
    )

    def put(r: int, c: int, v: Any, fmt: FormatDelta | None = None) -> None:
        cell = dst_sheet.get_cell(r, c) or CellData()
        cell.value = v
        if fmt:
            cell.format = fmt
        dst_sheet.set_cell(r, c, cell)

    fn_label = AGG_FUNC_LABELS.get(config.agg_func, config.agg_func.capitalize())
    head_data = col_header(config.data_field_col)
    head_row = col_header(config.row_field_col)

    # Optional Page Filter Header
    curr_r = r0
    if config.page_field_col is not None:
        p_row = max(0, r0 - 2)
        put(p_row, c0, col_header(config.page_field_col), BOLD)
        put(p_row, c0 + 1, config.page_filter_val or "(All)")

    # Title header: "Sum of Sales"
    put(curr_r, c0, f"{fn_label} of {head_data}", HEAD)
    if has_col and config.col_field_col is not None:
        put(curr_r, c0 + 1, col_header(config.col_field_col), HEAD)

    # Field labels row
    hr = curr_r + 1
    put(hr, c0, head_row, HEAD)

    show_cols = col_keys if has_col else ["Total"]
    for j, ck in enumerate(show_cols):
        put(hr, c0 + 1 + j, ck, HEAD)

    if has_col:
        put(hr, c0 + 1 + len(show_cols), "Grand Total", HEAD)

    # Data rows
    for i, rk in enumerate(row_keys):
        row_idx = hr + 1 + i
        put(row_idx, c0, rk)
        for j, ck in enumerate(show_cols):
            lookup_k = f"{rk}\x01{ck}" if has_col else f"{rk}\x01"
            v_list = cells.get(lookup_k, [])
            if v_list:
                agg_val = _aggregate_values(v_list, config.agg_func)
                put(row_idx, c0 + 1 + j, agg_val)

        if has_col:
            r_tot_val = _aggregate_values(row_tot.get(rk, []), config.agg_func)
            put(row_idx, c0 + 1 + len(show_cols), r_tot_val, BOLD)

    # Grand Total row
    gr = hr + 1 + len(row_keys)
    put(gr, c0, "Grand Total", TOT)
    for j, ck in enumerate(show_cols):
        c_list = col_tot.get(ck, []) if has_col else grand_all
        c_tot_val = _aggregate_values(c_list, config.agg_func)
        put(gr, c0 + 1 + j, c_tot_val, TOT)

    if has_col:
        grand_val = _aggregate_values(grand_all, config.agg_func)
        put(gr, c0 + 1 + len(show_cols), grand_val, TOT)

    max_c = c0 + (len(show_cols) + 1 if has_col else len(show_cols))
    bbox = (r0, c0, gr, max_c)

    # Set as active sheet
    workbook.set_active_sheet(dst_sheet)
    return dst_sheet, bbox
