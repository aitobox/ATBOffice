"""Ledger HTML export (File > Save as Web Page) and HTML table import."""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


def _used_range(sheet: Any) -> tuple[int, int, int, int] | None:
    from atboffice.modules.spreadsheet.printing.layout import content_bounds

    if not sheet.cells and not sheet.merges:
        return None
    return content_bounds(sheet)


def _cell_style(cell: Any) -> str:
    if cell is None:
        return ""
    parts = []
    if getattr(cell, "bold", False):
        parts.append("font-weight:bold")
    if getattr(cell, "italic", False):
        parts.append("font-style:italic")
    if getattr(cell, "underline", False):
        parts.append("text-decoration:underline")
    if getattr(cell, "fg_color", None):
        parts.append(f"color:{cell.fg_color}")
    if getattr(cell, "bg_color", None):
        parts.append(f"background:{cell.bg_color}")
    align = cell.get_effective_align_h() if hasattr(cell, "get_effective_align_h") else None
    if align in ("left", "center", "right", "justify"):
        parts.append(f"text-align:{align}")
    family = getattr(cell, "font_family", None)
    if family and family != "Arial":
        parts.append(f"font-family:'{html.escape(family, quote=True)}'")
    size = getattr(cell, "font_size", None)
    if size and size != 10:
        parts.append(f"font-size:{size}pt")
    return ";".join(parts)


def sheet_to_html(sheet: Any) -> str:
    """One ``<table>`` for the used range, merges as rowspan/colspan, formats inline."""
    rng = _used_range(sheet)
    if rng is None:
        return "<table></table>"
    r1, c1, r2, c2 = rng
    covered: set[tuple[int, int]] = set()
    spans: dict[tuple[int, int], tuple[int, int]] = {}
    for mr1, mc1, mr2, mc2 in sheet.merges:
        spans[(mr1, mc1)] = (mr2 - mr1 + 1, mc2 - mc1 + 1)
        for rr in range(mr1, mr2 + 1):
            for cc in range(mc1, mc2 + 1):
                if (rr, cc) != (mr1, mc1):
                    covered.add((rr, cc))
    geo = sheet.geometry
    rows = ['<table border="1" cellspacing="0" cellpadding="2" '
            'style="border-collapse:collapse;font-family:Arial;font-size:10pt">']
    rows.append("<colgroup>" + "".join(
        f'<col style="width:{geo.col_size(c)}px">' for c in range(c1, c2 + 1)
    ) + "</colgroup>")
    for r in range(r1, r2 + 1):
        if geo.row_size(r) == 0:
            continue
        cells = []
        for c in range(c1, c2 + 1):
            if (r, c) in covered or geo.col_size(c) == 0:
                continue
            cell = sheet.get_cell(r, c)
            text = html.escape(sheet.get_formatted_text(r, c)) if cell is not None else ""
            attrs = ""
            if (r, c) in spans:
                rs, cs = spans[(r, c)]
                attrs += f' rowspan="{rs}"' if rs > 1 else ""
                attrs += f' colspan="{cs}"' if cs > 1 else ""
            style = _cell_style(cell)
            if style:
                attrs += f' style="{style}"'
            cells.append(f"<td{attrs}>{text or '&nbsp;'}</td>")
        rows.append(f'<tr style="height:{geo.row_size(r)}px">{"".join(cells)}</tr>')
    rows.append("</table>")
    return "\n".join(rows)


def write_html(workbook: Any, path: str | Path, active_only: bool = False) -> None:
    """Save the workbook as a web page: one heading + table per (visible) sheet."""
    sheets = [workbook.active_sheet] if active_only else list(workbook.sheets)
    body = []
    for sheet in sheets:
        if len(sheets) > 1:
            body.append(f"<h2>{html.escape(sheet.name)}</h2>")
        body.append(sheet_to_html(sheet))
    title = html.escape(Path(path).stem)
    doc = (
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
        f"<title>{title}</title></head><body>\n" + "\n".join(body) + "\n</body></html>\n"
    )
    Path(path).write_text(doc, encoding="utf-8")


# ---------------------------------------------------------------- import
@dataclass
class HtmlCell:
    text: str = ""
    rowspan: int = 1
    colspan: int = 1
    bold: bool = False


@dataclass
class HtmlTable:
    rows: list[list[HtmlCell]] = field(default_factory=list)


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[HtmlTable] = []
        self._stack: list[HtmlTable] = []
        self._cell: HtmlCell | None = None
        self._bold = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "table":
            self._stack.append(HtmlTable())
        elif tag == "tr" and self._stack:
            self._stack[-1].rows.append([])
        elif tag in ("td", "th") and self._stack:
            if not self._stack[-1].rows:
                self._stack[-1].rows.append([])

            def num(key: str) -> int:
                try:
                    return max(1, int(a.get(key, "1") or 1))
                except ValueError:
                    return 1

            self._cell = HtmlCell(rowspan=num("rowspan"), colspan=num("colspan"),
                                  bold=tag == "th" or "bold" in a.get("style", ""))
            self._stack[-1].rows[-1].append(self._cell)
        elif tag in ("b", "strong"):
            self._bold += 1
        elif tag == "br" and self._cell is not None:
            self._cell.text += "\n"

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._stack:
            self.tables.append(self._stack.pop())
        elif tag in ("td", "th"):
            if self._cell is not None:
                lines = [" ".join(line.split()) for line in self._cell.text.split("\n")]
                self._cell.text = "\n".join(line for line in lines if line)
            self._cell = None
        elif tag in ("b", "strong") and self._bold:
            self._bold -= 1

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.text += data
            if self._bold:
                self._cell.bold = True


def parse_html_tables(text: str) -> list[HtmlTable]:
    """Every ``<table>`` of an HTML document (nested tables are listed separately)."""
    parser = _TableParser()
    parser.feed(text)
    parser.close()
    return parser.tables


def read_html_file(path: str | Path) -> list[HtmlTable]:
    return parse_html_tables(Path(path).read_text(encoding="utf-8", errors="replace"))


def _parse_value(text: str) -> Any:
    t = text.strip().replace(" ", " ").strip()
    if not t:
        return None
    candidate = t.replace(",", "")
    try:
        return int(candidate)
    except ValueError:
        pass
    try:
        return float(candidate)
    except ValueError:
        return t


def import_table(sheet: Any, table: HtmlTable, at: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    """Write ``table`` into ``sheet`` from ``at`` (merges from spans); returns its size."""
    r0, c0 = at
    occupied: set[tuple[int, int]] = set()
    max_r = max_c = 0
    for i, row in enumerate(table.rows):
        c = 0
        for hc in row:
            while (i, c) in occupied:
                c += 1
            cell = sheet.ensure_cell(r0 + i, c0 + c)
            cell.value = _parse_value(hc.text)
            cell.formula = None
            cell.bold = hc.bold
            if hc.rowspan > 1 or hc.colspan > 1:
                sheet.merges.append((r0 + i, c0 + c, r0 + i + hc.rowspan - 1,
                                     c0 + c + hc.colspan - 1))
            for dr in range(hc.rowspan):
                for dc in range(hc.colspan):
                    occupied.add((i + dr, c + dc))
            max_r = max(max_r, i + hc.rowspan)
            max_c = max(max_c, c + hc.colspan)
            c += hc.colspan
    sheet.dirty = True
    return max_r, max_c
