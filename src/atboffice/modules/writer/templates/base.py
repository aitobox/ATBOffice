"""Shared builder utilities, fields, styles, and tables for Quire templates."""

from __future__ import annotations

import datetime
from typing import Any

from atboffice.modules.writer.models.document import (
    Cell,
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    Row,
    RunItem,
    Table,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    CellProperties,
    ParagraphProperties,
    RowProperties,
    RunProperties,
    ShadingProperties,
    TableProperties,
)
from atboffice.modules.writer.models.styles import Style


def format_word_date(dt: datetime.datetime, fmt: str) -> str:
    """Format a datetime according to common Word date format patterns."""
    day = dt.day
    month = dt.month
    year = dt.year
    weekday_full = dt.strftime("%A")
    month_full = dt.strftime("%B")
    month_abbr = dt.strftime("%b")

    res = fmt.replace("dddd", weekday_full)
    res = res.replace("MMMM", month_full)
    res = res.replace("MMM", month_abbr)
    res = res.replace("yyyy", str(year))
    res = res.replace("M/d/yyyy", f"{month}/{day}/{year}")
    res = res.replace("M", str(month))
    res = res.replace("d", str(day))
    return res


def placeholder(label: str, r_pr: RunProperties | None = None) -> list[RunItem]:
    """Generate a MACROBUTTON placeholder run construct [Click here and type ...]."""
    rp = r_pr or RunProperties()
    return [
        FieldBeginItem(
            field_type="MACROBUTTON",
            instr=f" MACROBUTTON  DoFieldClick [{label}] ",
            r_pr=rp,
        ),
        FieldSeparateItem(r_pr=rp),
        TextItem(text=f"[{label}]", r_pr=rp),
        FieldEndItem(r_pr=rp),
    ]


def field_run(instr: str, result: str, r_pr: RunProperties | None = None) -> list[RunItem]:
    """Generate an inline dynamic field construct with cached result string."""
    rp = r_pr or RunProperties()
    return [
        FieldBeginItem(instr=f" {instr} ", r_pr=rp),
        FieldSeparateItem(r_pr=rp),
        TextItem(text=result, r_pr=rp),
        FieldEndItem(r_pr=rp),
    ]


def date_field(fmt: str, r_pr: RunProperties | None = None) -> list[RunItem]:
    """Generate a DATE field formatted with today's date."""
    now = datetime.datetime.now()
    formatted = format_word_date(now, fmt)
    return field_run(f'DATE \\@ "{fmt}"', formatted, r_pr)


def define_style(
    doc: Document,
    style_id: str,
    name: str,
    p_pr: ParagraphProperties | None = None,
    r_pr: RunProperties | None = None,
    based_on: str = "Normal",
) -> Style:
    """Register or update a custom paragraph style in the document."""
    st = Style(
        id=style_id,
        name=name,
        style_type="paragraph",
        based_on=based_on,
        p_pr=p_pr or ParagraphProperties(),
        r_pr=r_pr or RunProperties(),
        builtin=False,
    )
    doc.styles[style_id] = st
    return st


def simple_table(
    rows: list[list[str | None]],
    widths: list[float],
    header_fill: str | None = None,
    p_style: str | None = None,
) -> Table:
    """Build a structured table with header row styling and column widths."""
    tbl = Table()
    tbl.grid = list(widths)
    total_w = sum(widths)
    tbl.tbl_pr = TableProperties(w=total_w, w_type="dxa", style="TableNormal")

    for r_idx, row_data in enumerate(rows):
        is_header = r_idx == 0
        r_props = RowProperties(tbl_header=is_header)
        cells: list[Cell] = []

        for c_idx, cell_text in enumerate(row_data):
            cell_w = widths[c_idx] if c_idx < len(widths) else 72.0
            c_props = CellProperties(w=cell_w, w_type="dxa")
            if is_header and header_fill:
                c_props.shd = ShadingProperties(val="clear", fill=header_fill)

            p_props = ParagraphProperties()
            if p_style:
                p_props.style = p_style

            runs: list[RunItem] = []
            if cell_text:
                r_pr = (
                    RunProperties(b=True, color="FFFFFF")
                    if is_header
                    else RunProperties()
                )
                runs.append(TextItem(text=cell_text, r_pr=r_pr))

            cell_para = Paragraph(runs=runs, p_pr=p_props)
            cell = Cell(tc_pr=c_props, blocks=[cell_para])
            cells.append(cell)

        tbl.rows.append(Row(tr_pr=r_props, cells=cells))

    return tbl


def make_bullet_abs(ch: str = "•", font: str = "Symbol", raw: str = "") -> dict[str, Any]:
    """Generate an abstract bullet list numbering definition."""
    cycle = [(ch, font, raw or ch), ("o", "Courier New", "o"), ("▪", "Wingdings", "")]
    levels: list[dict[str, Any]] = []
    for i in range(9):
        c = cycle[0] if i == 0 else cycle[i % 3]
        levels.append(
            {
                "start": 1,
                "fmt": "bullet",
                "text": c[2],
                "glyph": c[0],
                "jc": "left",
                "ind": {"l": 36 + i * 36, "fl": -18},
                "r_pr": {"font": c[1]} if c[1] else {},
                "suff": "tab",
            }
        )
    return {"levels": levels, "multi": "hybridMultilevel"}


def make_number_abs(fmt: str = "decimal", text: str = "%1.") -> dict[str, Any]:
    """Generate an abstract decimal / numbered list definition."""
    fm = [fmt or "decimal", "lowerLetter", "lowerRoman"]
    levels: list[dict[str, Any]] = []
    for i in range(9):
        f = fm[0] if i == 0 else fm[i % 3]
        t = text if i == 0 else f"%{i + 1}."
        lv: dict[str, Any] = {
            "start": 1,
            "fmt": f,
            "text": t,
            "jc": "left",
            "ind": {"l": 36 + i * 36, "fl": -18},
            "r_pr": {},
            "suff": "tab",
        }
        if f in {"lowerRoman", "upperRoman"}:
            lv["jc"] = "right"
            lv["ind"] = {"l": 36 + i * 36, "fl": -9}
        levels.append(lv)
    return {"levels": levels, "multi": "hybridMultilevel"}


def add_num(doc: Document, abs_def: dict[str, Any]) -> str:
    """Register an abstract numbering definition and create an instance in doc.numbering."""
    nb = doc.numbering
    if "abs" not in nb:
        nb["abs"] = {}
    if "nums" not in nb:
        nb["nums"] = {}

    aid = 0
    while aid in nb["abs"]:
        aid += 1
    abs_def_copy = dict(abs_def)
    abs_def_copy["id"] = aid
    nb["abs"][aid] = abs_def_copy

    nid = 1
    while nid in nb["nums"] or str(nid) in nb["nums"]:
        nid += 1
    nb["nums"][nid] = {"abs": aid, "ov": {}}
    return str(nid)
