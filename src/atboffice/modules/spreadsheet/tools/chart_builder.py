"""Build chart data dictionaries from live worksheet cells.

The Chart Wizard collects a source range plus options; this module turns them into
the ``ChartData`` dictionary that ``ObjectLayerWidget`` renders through
``ChartPainter``, so charts show the user's numbers instead of sample data.
"""

from __future__ import annotations

from typing import Any

from atboffice.modules.presentation.chart.model import CH_PALETTE
from atboffice.modules.spreadsheet.calc.references import parse_range

# (wizard type id, wizard subtype id) -> ChartData.kind
_KIND_MAP: dict[str, str] = {
    "column": "col",
    "column/stacked": "colStacked",
    "column/percent_stacked": "colPct",
    "bar": "bar",
    "bar/stacked_bar": "barStacked",
    "bar/percent_stacked_bar": "barPct",
    "line": "line",
    "line/line_markers": "lineMarkers",
    "pie": "pie",
    "scatter": "scatter",
    "area": "area",
    "area/stacked_area": "areaStacked",
    "doughnut": "doughnut",
    "radar": "radar",
    "radar/radar_filled": "radarFilled",
}

_LEGEND_MAP = {"right": "r", "bottom": "b", "top": "t", "left": "l", "corner": "r"}


def chart_kind(type_id: str, subtype_id: str = "") -> str:
    """Map a wizard type/subtype pair onto a ``ChartData.kind`` value."""
    return _KIND_MAP.get(f"{type_id}/{subtype_id}") or _KIND_MAP.get(type_id, "col")


def split_sheet_ref(ref: str) -> tuple[str | None, str]:
    """Split ``=Sheet1!$A$1:$B$4`` / ``'My Sheet'!A1`` into (sheet name, local ref)."""
    text = (ref or "").strip().lstrip("=").strip()
    if "!" not in text:
        return None, text
    sheet, local = text.rsplit("!", 1)
    sheet = sheet.strip()
    if len(sheet) >= 2 and sheet[0] == sheet[-1] == "'":
        sheet = sheet[1:-1].replace("''", "'")
    return sheet or None, local.strip()


def resolve_range(
    ref: str, workbook: Any = None, default_sheet: Any = None
) -> tuple[Any, tuple[int, int, int, int]] | None:
    """Resolve a (possibly sheet-qualified) A1 range to (sheet model, (r1, c1, r2, c2))."""
    sheet_name, local = split_sheet_ref(ref)
    rng = parse_range(local) if local else None
    if rng is None:
        return None
    sheet = default_sheet
    if sheet_name and workbook is not None and hasattr(workbook, "get_sheet_by_name"):
        sheet = workbook.get_sheet_by_name(sheet_name) or default_sheet
    if sheet is None:
        return None
    return sheet, (rng["r1"], rng["c1"], rng["r2"], rng["c2"])


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return None
    return None


def _label(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _is_label(value: Any) -> bool:
    return value is not None and value != "" and _number(value) is None


def _clamp_used(sheet: Any, r1: int, c1: int, r2: int, c2: int) -> tuple[int, int, int, int]:
    """Shrink whole-row/whole-column ranges to the populated cells."""
    cells = getattr(sheet, "cells", {}) or {}
    if r2 - r1 > 5000 or c2 - c1 > 500:
        used = [
            (r, c)
            for (r, c), cell in cells.items()
            if r1 <= r <= r2 and c1 <= c <= c2 and getattr(cell, "value", None) is not None
        ]
        if used:
            r2 = min(r2, max(r for r, _ in used))
            c2 = min(c2, max(c for _, c in used))
        else:
            r2, c2 = r1, c1
    return r1, c1, r2, c2


def table_from_range(
    sheet: Any, rect: tuple[int, int, int, int], series_in_rows: bool = False
) -> tuple[list[str], list[tuple[str, list[float]]]]:
    """Read categories and (name, values) series from a rectangular block.

    A first row / first column made of text labels is treated as series names and
    category labels, mirroring how Excel's wizard interprets a selected table.
    """
    r1, c1, r2, c2 = _clamp_used(sheet, *rect)
    grid = [[sheet.get_cell_value(r, c) for c in range(c1, c2 + 1)] for r in range(r1, r2 + 1)]
    if series_in_rows:
        grid = [list(col) for col in zip(*grid, strict=False)] if grid else []

    if not grid:
        return [], []
    n_rows, n_cols = len(grid), len(grid[0])

    header_row = (
        n_rows > 1
        and all(_is_label(v) or v in (None, "") for v in grid[0][1 if n_cols > 1 else 0 :])
        and any(_is_label(v) for v in grid[0])
    )
    header_col = (
        n_cols > 1
        and all(_is_label(row[0]) or row[0] in (None, "") for row in grid[1 if header_row else 0 :])
        and any(_is_label(row[0]) for row in grid[1 if header_row else 0 :])
    )

    data_rows = grid[1:] if header_row else grid
    first_data_col = 1 if header_col else 0

    cats = (
        [_label(row[0]) for row in data_rows]
        if header_col
        else [str(i + 1) for i in range(len(data_rows))]
    )
    series: list[tuple[str, list[float]]] = []
    for col in range(first_data_col, n_cols):
        name = _label(grid[0][col]) if header_row else ""
        vals = [_number(row[col]) or 0.0 for row in data_rows]
        series.append((name, vals))
    return cats, series


def build_chart_data(
    spec: dict[str, Any], workbook: Any = None, default_sheet: Any = None
) -> dict[str, Any]:
    """Build a ``ChartData`` dictionary for a Chart Wizard ``get_chart_spec()`` result."""
    cats: list[str] = []
    series: list[tuple[str, list[float]]] = []
    custom = spec.get("custom_series") or []
    if custom:
        for idx, item in enumerate(custom):
            vals_ref = resolve_range(item.get("values", ""), workbook, default_sheet)
            if vals_ref is None:
                continue
            sh, (r1, c1, r2, c2) = vals_ref
            vals = [
                _number(sh.get_cell_value(r, c)) or 0.0
                for r in range(r1, r2 + 1)
                for c in range(c1, c2 + 1)
            ]
            name = _series_name(item.get("name", ""), workbook, default_sheet) or f"系列{idx + 1}"
            series.append((name, vals))
            if not cats:
                x_ref = resolve_range(item.get("x_values", ""), workbook, default_sheet)
                if x_ref is not None:
                    xs, (xr1, xc1, xr2, xc2) = x_ref
                    cats = [
                        _label(xs.get_cell_value(r, c))
                        for r in range(xr1, xr2 + 1)
                        for c in range(xc1, xc2 + 1)
                    ]
        if series and not cats:
            cats = [str(i + 1) for i in range(max(len(v) for _, v in series))]
    else:
        resolved = resolve_range(spec.get("data_range", ""), workbook, default_sheet)
        if resolved is not None:
            sh, rect = resolved
            cats, series = table_from_range(sh, rect, spec.get("series_in") == "rows")

    kind = chart_kind(str(spec.get("type", "column")), str(spec.get("sub_type", "")))
    legend = _LEGEND_MAP.get(str(spec.get("legend_placement", "right")), "r")
    if not spec.get("show_legend", True):
        legend = "none"
    data: dict[str, Any] = {
        "v": 2,
        "kind": kind,
        "title": spec.get("title", "") or "",
        "legend": legend,
        "gridY": bool(spec.get("show_major_y_grid", True)),
        "labels": spec.get("data_labels", "none") not in ("none", "", None),
        "cats": cats,
        "series": [
            {"name": name or f"系列{i + 1}", "vals": vals, "color": CH_PALETTE[i % len(CH_PALETTE)]}
            for i, (name, vals) in enumerate(series)
        ],
        "fsz": 10.0,
        "ax": {"c": {"tick": "out", "rev": False}, "v": {}},
    }
    if spec.get("show_major_y_grid", True):
        data["ax"]["v"]["grid"] = {"c": "#D9D9D9", "w": 0.75}
    if spec.get("show_major_x_grid"):
        data["ax"]["c"]["grid"] = {"c": "#D9D9D9", "w": 0.75}
    # Axis titles are kept with the chart so a later editor/writer can show them.
    if spec.get("x_axis_title"):
        data["ax"]["c"]["title"] = spec["x_axis_title"]
    if spec.get("y_axis_title"):
        data["ax"]["v"]["title"] = spec["y_axis_title"]
    return data


def _series_name(ref: str, workbook: Any, default_sheet: Any) -> str:
    text = (ref or "").strip()
    if not text.startswith("="):
        return text
    resolved = resolve_range(text, workbook, default_sheet)
    if resolved is None:
        return text.lstrip("=")
    sh, (r1, c1, _, _) = resolved
    return _label(sh.get_cell_value(r1, c1))
