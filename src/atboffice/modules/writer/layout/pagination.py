"""Quire dynamic multi-page pagination & flow engine (Word 2003 port).

This module implements:
1. Physical page generation and geometry calculations (dimensions, margins, orientation).
2. Flowing paragraphs, tables, and runs across column frames and page regions.
3. Accurate hard break handling: page breaks, column breaks.
4. Section breaks: nextPage, oddPage, evenPage, and continuous with parity padding.
5. Orphan / Widow control (minimum 2 lines at page bottom, minimum 2 lines at page top).
6. Keep rules: pageBreakBefore, keepWithNext, and keepLines.
7. Headers and Footers resolution and dynamic margin adaptation.
8. Dynamic field evaluation: PAGE, NUMPAGES, SECTIONPAGES.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from atboffice.modules.writer.layout.portions import (
    LayoutLine,
    layout_paragraph,
)
from atboffice.modules.writer.layout.table_layout import (
    TableLayout,
    layout_table,
    split_table_for_page,
)
from atboffice.modules.writer.models.document import (
    BreakItem,
    Document,
    Paragraph,
    Story,
    Table,
    sections,
)
from atboffice.modules.writer.models.properties import (
    SectionProperties,
)
from atboffice.modules.writer.models.styles import resolve_p_props

# ---------------------------------------------------------------------------
# Number Formatting Helper
# ---------------------------------------------------------------------------


def _to_roman(n: int) -> str:
    """Convert positive integer to Roman numerals."""
    if n <= 0:
        return ""
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syb = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    res: list[str] = []
    i = 0
    while n > 0:
        for _ in range(n // val[i]):
            res.append(syb[i])
            n -= val[i]
        i += 1
    return "".join(res)


def _to_letters(n: int, lowercase: bool = False) -> str:
    """Convert positive integer to alphabetical sequence (1 -> A, 27 -> AA)."""
    if n <= 0:
        return ""
    base = 97 if lowercase else 65
    repeats = (n - 1) // 26 + 1
    char = chr(base + ((n - 1) % 26))
    return char * repeats


def _ordinal_suffix(n: int) -> str:
    """Return ordinal suffix for an integer (1st, 2nd, 3rd, 4th, 11th, etc.)."""
    if 11 <= (n % 100) <= 13:
        return "th"
    last = n % 10
    if last == 1:
        return "st"
    if last == 2:
        return "nd"
    if last == 3:
        return "rd"
    return "th"


def format_number(n: int, fmt: str = "decimal") -> str:
    """Format an integer according to Word numbering format specifications."""
    fmt = str(fmt or "decimal").lower()
    if fmt in ("upperroman", "roman"):
        return _to_roman(n)
    if fmt == "lowerroman":
        return _to_roman(n).lower()
    if fmt in ("upperletter", "alphabet"):
        return _to_letters(n, lowercase=False)
    if fmt == "lowerletter":
        return _to_letters(n, lowercase=True)
    if fmt == "decimalzero":
        return f"{n:02d}" if 0 <= n < 10 else str(n)
    if fmt == "ordinal":
        return f"{n}{_ordinal_suffix(n)}"
    return str(n)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class PageFragment:
    """Rendered portion of a paragraph (or block) placed on a column frame."""

    paragraph: Paragraph | None = None
    line_start_idx: int = 0
    line_end_idx: int = 0
    lines: list[LayoutLine] = field(default_factory=list)
    top: float = 0.0
    height: float = 0.0
    space_before: float = 0.0
    space_after: float = 0.0
    char_start: int = 0
    char_end: int = 0
    table_layout: TableLayout | None = None


@dataclass
class ColumnFrame:
    """An individual column on a page region."""

    index: int
    left: float
    top: float
    width: float
    height: float
    used_height: float = 0.0
    fragments: list[PageFragment] = field(default_factory=list)


@dataclass
class PageRegion:
    """A section region on a page (can hold one or more columns)."""

    section_index: int
    section: SectionProperties
    top: float
    height: float
    columns: list[ColumnFrame] = field(default_factory=list)


@dataclass
class PageHeaderFooter:
    """Header or footer layout and fragments on a page."""

    kind: str  # "header" or "footer"
    story: Story | None
    y: float
    width: float
    height: float
    fragments: list[PageFragment] = field(default_factory=list)


@dataclass
class Page:
    """A complete physical page with dimensions, margins, and placed regions."""

    index: int
    page_number: int
    page_number_format: str
    section_index: int
    section: SectionProperties
    width: float
    height: float
    body_left: float
    body_right: float
    body_top: float
    body_bottom_gap: float
    body_width: float
    body_height: float
    header: PageHeaderFooter | None = None
    footer: PageHeaderFooter | None = None
    regions: list[PageRegion] = field(default_factory=list)
    is_blank: bool = False


@dataclass
class PaginationResult:
    """Result of document pagination."""

    pages: list[Page] = field(default_factory=list)
    total_pages: int = 0
    section_pages: list[int] = field(default_factory=list)
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Header & Footer Layout & Resolution
# ---------------------------------------------------------------------------


def resolve_page_type(
    sect: SectionProperties,
    first_of_section: bool,
    page_number: int,
    even_odd_settings: bool = False,
) -> str:
    """Determine header/footer variant for the page ('first', 'even', or 'default')."""
    if sect.title_pg and first_of_section:
        return "first"
    if even_odd_settings and (page_number % 2 == 0):
        return "even"
    return "default"


def get_hf_story(
    sect_list: list[dict[str, Any]],
    sect_idx: int,
    kind: str,
    page_type: str,
    hf_dict: dict[str, Story],
) -> Story | None:
    """Find the active header/footer story by inspecting current and ancestor sections."""
    for k in range(sect_idx, -1, -1):
        sect = sect_list[k]["sect"]
        refs = getattr(sect, "refs", None) or {}
        kind_refs = refs.get(kind, {})
        story_id = kind_refs.get(page_type)
        if story_id and story_id in hf_dict:
            return hf_dict[story_id]
    if page_type == "default" and sect_idx > 0:
        s0_refs = getattr(sect_list[0]["sect"], "refs", {}).get(kind, {})
        s0_id = s0_refs.get("default")
        if s0_id and s0_id in hf_dict:
            return hf_dict[s0_id]
    return None


def _evaluate_hf_paragraph(
    p: Paragraph,
    doc: Document,
    page_number: int,
    total_pages: int,
    page_number_format: str = "decimal",
    section_index: int = 0,
    section_pages: int = 1,
) -> Paragraph:
    """Clone and evaluate dynamic fields for a header/footer paragraph on the active page."""
    import copy
    from atboffice.modules.writer.models.document import (
        FieldBeginItem,
        FieldEndItem,
        FieldSeparateItem,
        TextItem,
    )
    from atboffice.modules.writer.models.field import FieldContext, evaluate_field

    has_fields = any(
        isinstance(r, (FieldBeginItem, FieldEndItem, FieldSeparateItem)) for r in p.runs
    )
    has_tokens = any(
        isinstance(r, TextItem) and r.text in ("PAGE", "NUMPAGES", "SECTIONPAGES")
        for r in p.runs
    )
    if not has_fields and not has_tokens:
        return p

    ctx = FieldContext(
        page_number=page_number,
        total_pages=total_pages,
        section_index=section_index,
        section_pages=section_pages,
        page_number_format=page_number_format,
    )

    p_clone = copy.copy(p)
    runs_copy = copy.deepcopy(p.runs)
    fb_idx = -1
    fs_idx = -1
    i = 0
    while i < len(runs_copy):
        it = runs_copy[i]
        if isinstance(it, FieldBeginItem):
            fb_idx = i
            fs_idx = -1
        elif isinstance(it, FieldSeparateItem) and fb_idx >= 0:
            fs_idx = i
        elif isinstance(it, FieldEndItem) and fb_idx >= 0:
            fb_item = runs_copy[fb_idx]
            instr = fb_item.instr or fb_item.field_type or ""
            eval_res = evaluate_field(instr, doc, ctx)

            start_repl = (fs_idx + 1) if fs_idx >= 0 else (fb_idx + 1)
            end_repl = i

            runs_copy[start_repl:end_repl] = [
                TextItem(text=eval_res, r_pr=fb_item.r_pr)
            ]
            i = start_repl + 1
            fb_idx = -1
            fs_idx = -1
        elif isinstance(it, TextItem) and fb_idx < 0:
            if it.text == "PAGE":
                eval_res = evaluate_field("PAGE", doc, ctx)
                runs_copy[i] = TextItem(text=eval_res, r_pr=it.r_pr)
            elif it.text == "NUMPAGES":
                eval_res = evaluate_field("NUMPAGES", doc, ctx)
                runs_copy[i] = TextItem(text=eval_res, r_pr=it.r_pr)
            elif it.text == "SECTIONPAGES":
                eval_res = evaluate_field("SECTIONPAGES", doc, ctx)
                runs_copy[i] = TextItem(text=eval_res, r_pr=it.r_pr)
        i += 1

    p_clone.runs = runs_copy
    return p_clone


def layout_hf_story(
    doc: Document,
    story: Story | None,
    sect: SectionProperties,
    body_width: float,
    kind: str,
    y: float,
    page_number: int = 1,
    total_pages: int = 1,
    page_number_format: str = "decimal",
    section_index: int = 0,
    section_pages: int = 1,
) -> PageHeaderFooter:
    """Layout header or footer story and return PageHeaderFooter with computed height."""
    if not story or not story.blocks:
        return PageHeaderFooter(kind=kind, story=story, y=y, width=body_width, height=0.0)

    fragments: list[PageFragment] = []
    cur_y = 0.0
    for block in story.blocks:
        if isinstance(block, Paragraph):
            p_eval = _evaluate_hf_paragraph(
                block,
                doc,
                page_number=page_number,
                total_pages=total_pages,
                page_number_format=page_number_format,
                section_index=section_index,
                section_pages=section_pages,
            )
            p_layout = layout_paragraph(
                p=p_eval,
                container_width=body_width,
                section_props=sect,
                doc=doc,
            )
            h = p_layout.height + p_layout.space_before + p_layout.space_after
            frag = PageFragment(
                paragraph=block,
                line_start_idx=0,
                line_end_idx=len(p_layout.lines),
                lines=p_layout.lines,
                top=cur_y + p_layout.space_before,
                height=p_layout.height,
                space_before=p_layout.space_before,
                space_after=p_layout.space_after,
            )
            fragments.append(frag)
            cur_y += h

    actual_y = y
    if kind == "footer":
        actual_y = max(0.0, sect.pg_h - sect.ftr - cur_y)
    elif kind == "header":
        actual_y = sect.hdr

    return PageHeaderFooter(
        kind=kind,
        story=story,
        y=actual_y,
        width=body_width,
        height=cur_y,
        fragments=fragments,
    )


# ---------------------------------------------------------------------------
# Flow & Pagination Context
# ---------------------------------------------------------------------------


class _PaginationContext:
    """Stateful worker for document pagination."""

    def __init__(self, doc: Document) -> None:
        self.doc = doc
        self.sect_list = sections(doc)
        self.pages: list[Page] = []
        self.current_page: Page | None = None
        self.current_region: PageRegion | None = None
        self.current_col_idx: int = 0
        self.page_number: int = 1
        # Each entry: (b_idx, block, fragment, column_frame)
        self.keep_chain: list[tuple[int, Paragraph, PageFragment, ColumnFrame]] = []

    def current_column(self) -> ColumnFrame | None:
        if not self.current_region or not self.current_region.columns:
            return None
        if self.current_col_idx < len(self.current_region.columns):
            return self.current_region.columns[self.current_col_idx]
        return self.current_region.columns[-1]

    def get_current_region_bottom(self) -> float:
        """Return the bottom y position of the current page's content in body coordinates."""
        if not self.current_page or not self.current_page.regions:
            return 0.0
        reg = self.current_page.regions[-1]
        max_col_bottom = max((col.used_height for col in reg.columns), default=0.0)
        return reg.top + max_col_bottom

    def start_page(
        self,
        sect_idx: int,
        sect: SectionProperties,
        first_of_section: bool,
        is_blank: bool = False,
    ) -> Page:
        pg_idx = len(self.pages)
        even_odd = bool(
            self.doc.settings.get("evenAndOddHeaders", False)
            or self.doc.settings.get("evenOdd", False)
        )
        mirror = bool(
            self.doc.settings.get("mirror", False)
            or self.doc.settings.get("mirrorMargins", False)
        ) and (self.page_number % 2 == 0)
        ml = sect.mr if mirror else sect.ml
        mr = sect.ml if mirror else sect.mr
        ml += 0.0 if mirror else sect.gutter
        mr += sect.gutter if mirror else 0.0

        body_w = max(10.0, sect.pg_w - ml - mr)
        pg_fmt = (
            getattr(sect.pg_num, "fmt", "decimal") if getattr(sect, "pg_num", None) else "decimal"
        )

        page_type = resolve_page_type(sect, first_of_section, self.page_number, even_odd)
        hdr_story = get_hf_story(self.sect_list, sect_idx, "hdr", page_type, self.doc.hf)
        ftr_story = get_hf_story(self.sect_list, sect_idx, "ftr", page_type, self.doc.hf)

        total_pgs = (
            self.doc._last_pagination.total_pages
            if hasattr(self.doc, "_last_pagination") and self.doc._last_pagination
            else max(1, len(self.pages) + 1)
        )
        sec_pages = (
            self.doc._last_pagination.section_pages[sect_idx]
            if hasattr(self.doc, "_last_pagination")
            and self.doc._last_pagination
            and sect_idx < len(self.doc._last_pagination.section_pages)
            else 1
        )

        hdr_layout = layout_hf_story(
            self.doc,
            hdr_story,
            sect,
            body_w,
            "header",
            sect.hdr,
            page_number=self.page_number,
            total_pages=total_pgs,
            page_number_format=pg_fmt,
            section_index=sect_idx,
            section_pages=sec_pages,
        )
        ftr_y = max(0.0, sect.pg_h - sect.ftr)
        ftr_layout = layout_hf_story(
            self.doc,
            ftr_story,
            sect,
            body_w,
            "footer",
            ftr_y,
            page_number=self.page_number,
            total_pages=total_pgs,
            page_number_format=pg_fmt,
            section_index=sect_idx,
            section_pages=sec_pages,
        )

        top = sect.mt
        bottom_gap = sect.mb
        if sect.mt >= 0 and hdr_layout.height > 0 and (sect.hdr + hdr_layout.height > top):
            top = sect.hdr + hdr_layout.height
        if sect.mb >= 0 and ftr_layout.height > 0 and (sect.ftr + ftr_layout.height > bottom_gap):
            bottom_gap = sect.ftr + ftr_layout.height

        top = max(1.0, abs(top))
        bottom_gap = max(1.0, abs(bottom_gap))
        body_h = max(10.0, sect.pg_h - top - bottom_gap)

        page = Page(
            index=pg_idx,
            page_number=self.page_number,
            page_number_format=pg_fmt,
            section_index=sect_idx,
            section=sect,
            width=sect.pg_w,
            height=sect.pg_h,
            body_left=ml,
            body_right=mr,
            body_top=top,
            body_bottom_gap=bottom_gap,
            body_width=body_w,
            body_height=body_h,
            header=hdr_layout if hdr_story else None,
            footer=ftr_layout if ftr_story else None,
            regions=[],
            is_blank=is_blank,
        )
        self.pages.append(page)
        self.current_page = page
        self.page_number += 1

        self.start_region(sect_idx, sect, top=0.0, height=body_h)
        return page

    def start_region(
        self,
        sect_idx: int,
        sect: SectionProperties,
        top: float,
        height: float,
    ) -> PageRegion:
        body_w = self.current_page.body_width if self.current_page else sect.pg_w
        num_cols = getattr(sect.cols, "num", None) or getattr(sect.cols, "n", 1) or 1
        col_space = getattr(sect.cols, "space", 36.0) or 36.0
        total_space = (num_cols - 1) * col_space
        col_w = max(10.0, (body_w - total_space) / num_cols)

        columns: list[ColumnFrame] = []
        cur_x = 0.0
        for c in range(num_cols):
            columns.append(
                ColumnFrame(
                    index=c,
                    left=cur_x,
                    top=top,
                    width=col_w,
                    height=height,
                    used_height=0.0,
                    fragments=[],
                )
            )
            cur_x += col_w + col_space

        region = PageRegion(
            section_index=sect_idx,
            section=sect,
            top=top,
            height=height,
            columns=columns,
        )
        if self.current_page:
            self.current_page.regions.append(region)
        self.current_region = region
        self.current_col_idx = 0
        return region

    def advance_column_or_page(
        self,
        sect_idx: int,
        sect: SectionProperties,
    ) -> None:
        if self.current_region and self.current_col_idx + 1 < len(self.current_region.columns):
            self.current_col_idx += 1
        else:
            self.start_page(sect_idx, sect, first_of_section=False)


def _split_paragraph_by_hard_breaks(p: Paragraph) -> list[tuple[Paragraph, str | None]]:
    """Split paragraph into sub-paragraphs along hard BreakItems ('page' or 'column')."""
    sub_paras: list[tuple[Paragraph, str | None]] = []
    cur_runs = []
    for it in p.runs:
        if isinstance(it, BreakItem) and it.break_type in ("page", "column"):
            sub_p = Paragraph(
                id=p.id,
                runs=list(cur_runs),
                p_pr=p.p_pr,
                sect=p.sect,
            )
            sub_paras.append((sub_p, it.break_type))
            cur_runs = []
        else:
            cur_runs.append(it)

    # Only append trailing segment if it has runs or if no break occurred
    if cur_runs or not sub_paras:
        sub_p = Paragraph(
            id=p.id,
            runs=list(cur_runs),
            p_pr=p.p_pr,
            sect=p.sect,
        )
        sub_paras.append((sub_p, None))
    return sub_paras


def _apply_widow_orphan_rules(
    lines: list[LayoutLine],
    space_left: float,
    widow_control: bool,
    column_has_fragments: bool,
) -> int:
    """Calculate line cutoff k respecting widow/orphan rules."""
    nl = len(lines)
    accum_h = 0.0
    k = 0
    while k < nl:
        lh = lines[k].height
        if accum_h + lh > space_left + 0.5:
            break
        accum_h += lh
        k += 1

    if widow_control and nl > 1:
        if k == 1 and column_has_fragments:
            k = 0
        if nl - k == 1 and k >= 2:
            k -= 1
        if k == 1 and nl > 2 and column_has_fragments:
            k = 0

    return k


def _update_dynamic_fields(
    doc: Document,
    pages: list[Page],
    section_pages: list[int],
) -> bool:
    """Evaluate and update text values of dynamic fields across all pages."""
    from atboffice.modules.writer.models.field import update_fields

    p_res = PaginationResult(
        pages=pages,
        total_pages=len(pages),
        section_pages=section_pages,
    )
    return update_fields(doc, p_res)


def _execute_single_pagination_pass(doc: Document) -> PaginationResult:
    """Execute complete multi-page pagination for a Document without field backfill."""
    t0 = time.perf_counter()
    ctx = _PaginationContext(doc)

    for si, sec_info in enumerate(ctx.sect_list):
        sect = sec_info["sect"]
        start_num = getattr(sect.pg_num, "start", None) if getattr(sect, "pg_num", None) else None

        if si == 0:
            if start_num is not None:
                ctx.page_number = start_num
            ctx.start_page(si, sect, first_of_section=True)
        else:
            prev_sect = ctx.sect_list[si - 1]["sect"]
            s_type = (
                getattr(sect, "sect_type", None)
                or getattr(sect, "type", "nextPage")
                or "nextPage"
            )
            same_geom = (
                abs(sect.pg_w - prev_sect.pg_w) < 1.0
                and abs(sect.pg_h - prev_sect.pg_h) < 1.0
            )

            is_valid_continuous = (
                s_type == "continuous"
                and same_geom
                and ctx.current_page
                and not ctx.current_page.is_blank
            )
            if is_valid_continuous:
                bottom_y = ctx.get_current_region_bottom()
                avail_h = ctx.current_page.body_height - bottom_y
                if avail_h >= 20.0:
                    ctx.start_region(si, sect, top=bottom_y, height=avail_h)
                else:
                    if start_num is not None:
                        ctx.page_number = start_num
                    ctx.start_page(si, sect, first_of_section=True)
            elif s_type == "nextColumn":
                if ctx.current_region and ctx.current_col_idx + 1 < len(ctx.current_region.columns):
                    ctx.current_col_idx += 1
                else:
                    if start_num is not None:
                        ctx.page_number = start_num
                    ctx.start_page(si, sect, first_of_section=True)
            elif s_type in ("oddPage", "evenPage"):
                next_pno = ctx.page_number
                if s_type == "oddPage" and (next_pno % 2 == 0):
                    ctx.start_page(si - 1, prev_sect, first_of_section=False, is_blank=True)
                elif s_type == "evenPage" and (next_pno % 2 != 0):
                    ctx.start_page(si - 1, prev_sect, first_of_section=False, is_blank=True)
                if start_num is not None:
                    ctx.page_number = start_num
                ctx.start_page(si, sect, first_of_section=True)
            else:  # "nextPage"
                if start_num is not None:
                    ctx.page_number = start_num
                ctx.start_page(si, sect, first_of_section=True)

        from_idx = sec_info["from"]
        to_idx = sec_info["to"]
        blocks = doc.main.blocks[from_idx:to_idx]

        b_idx = 0
        guard = 0
        while b_idx < len(blocks):
            guard += 1
            if guard > 20000:
                break
            block = blocks[b_idx]
            if isinstance(block, Table):
                col = ctx.current_column()
                col_w = col.width if col else ctx.current_page.body_width
                t_layout = layout_table(block, container_width=col_w, doc=doc)

                start_row = 0
                is_first_slice = True
                while start_row is not None and start_row < len(t_layout.rows):
                    col = ctx.current_column()
                    space_left = col.height - col.used_height
                    if space_left < 20.0 and col.fragments:
                        ctx.advance_column_or_page(si, sect)
                        col = ctx.current_column()
                        space_left = col.height - col.used_height

                    sliced_tbl, next_row = split_table_for_page(
                        t_layout,
                        start_row=start_row,
                        avail_height=space_left,
                        is_first_page=is_first_slice,
                    )
                    if sliced_tbl is None or not sliced_tbl.rows:
                        break

                    frag = PageFragment(
                        paragraph=None,
                        top=col.used_height,
                        height=sliced_tbl.height,
                        table_layout=sliced_tbl,
                    )
                    col.fragments.append(frag)
                    col.used_height += sliced_tbl.height

                    start_row = next_row
                    is_first_slice = False
                    if start_row is not None:
                        ctx.advance_column_or_page(si, sect)

                b_idx += 1
                continue

            if not isinstance(block, Paragraph):
                b_idx += 1
                continue

            segments = _split_paragraph_by_hard_breaks(block)
            restarted_b_idx = False

            for seg_idx, (p_seg, hard_break) in enumerate(segments):
                p_pr = resolve_p_props(doc, p_seg)

                col = ctx.current_column()
                if p_pr.page_break_before and col and col.fragments:
                    ctx.advance_column_or_page(si, sect)
                    col = ctx.current_column()

                col_w = col.width if col else ctx.current_page.body_width
                is_top = (col.used_height == 0.0) if col else True
                p_layout = layout_paragraph(
                    p=p_seg,
                    container_width=col_w,
                    section_props=sect,
                    doc=doc,
                    is_page_top=is_top,
                )

                lines_to_place = list(p_layout.lines)
                line_offset = 0

                while lines_to_place:
                    col = ctx.current_column()
                    space_left = col.height - col.used_height

                    sp_before = p_layout.effective_space_before if is_top else p_layout.space_before
                    if col.used_height == 0.0:
                        sp_before = 0.0

                    avail_h = space_left - sp_before

                    # keep_lines rule
                    if p_pr.keep_lines and col.fragments:
                        total_p_h = sum(ln.height for ln in lines_to_place)
                        if total_p_h > avail_h + 0.5:
                            if ctx.keep_chain:
                                first_b_idx = ctx.keep_chain[0][0]
                                for _, _, kfrag, kcol in reversed(ctx.keep_chain):
                                    if kfrag in kcol.fragments:
                                        kcol.fragments.remove(kfrag)
                                        kcol.used_height -= kfrag.height + kfrag.space_before
                                ctx.keep_chain.clear()
                                ctx.advance_column_or_page(si, sect)
                                b_idx = first_b_idx
                                restarted_b_idx = True
                                break
                            ctx.advance_column_or_page(si, sect)
                            continue

                    # Widow / Orphan cutoff
                    k = _apply_widow_orphan_rules(
                        lines_to_place,
                        avail_h,
                        p_pr.widow_control,
                        bool(col.fragments),
                    )

                    if k == 0:
                        if not col.fragments:
                            k = 1
                        else:
                            # KeepWithNext rollback check
                            if ctx.keep_chain:
                                first_b_idx = ctx.keep_chain[0][0]
                                for _, _, kfrag, kcol in reversed(ctx.keep_chain):
                                    if kfrag in kcol.fragments:
                                        kcol.fragments.remove(kfrag)
                                        kcol.used_height -= kfrag.height + kfrag.space_before
                                ctx.keep_chain.clear()
                                ctx.advance_column_or_page(si, sect)
                                b_idx = first_b_idx
                                restarted_b_idx = True
                                break

                            ctx.advance_column_or_page(si, sect)
                            continue

                    placed_lines = lines_to_place[:k]
                    frag_h = sum(ln.height for ln in placed_lines)
                    frag = PageFragment(
                        paragraph=block,  # Keep reference to original block
                        line_start_idx=line_offset,
                        line_end_idx=line_offset + k,
                        lines=placed_lines,
                        top=col.used_height + sp_before,
                        height=frag_h,
                        space_before=sp_before,
                        space_after=p_layout.space_after if k == len(lines_to_place) else 0.0,
                    )
                    col.fragments.append(frag)
                    col.used_height += frag_h + sp_before

                    # Manage keepWithNext
                    if p_pr.keep_next and k == len(lines_to_place):
                        ctx.keep_chain.append((b_idx, block, frag, col))
                    else:
                        ctx.keep_chain.clear()

                    line_offset += k
                    lines_to_place = lines_to_place[k:]

                    if lines_to_place:
                        ctx.advance_column_or_page(si, sect)
                        is_top = True

                if restarted_b_idx:
                    break

                if hard_break == "page":
                    ctx.start_page(si, sect, first_of_section=False)
                elif hard_break == "column":
                    ctx.advance_column_or_page(si, sect)

            if restarted_b_idx:
                continue

            b_idx += 1

    total_pgs = len(ctx.pages)
    sec_pages: list[int] = [0] * len(ctx.sect_list)
    for pg in ctx.pages:
        seen_secs: set[int] = set()
        if 0 <= pg.section_index < len(sec_pages):
            seen_secs.add(pg.section_index)
        for reg in pg.regions:
            if 0 <= reg.section_index < len(sec_pages):
                seen_secs.add(reg.section_index)
        for s_idx in seen_secs:
            sec_pages[s_idx] += 1

    dur = (time.perf_counter() - t0) * 1000.0
    return PaginationResult(
        pages=ctx.pages,
        total_pages=total_pgs,
        section_pages=sec_pages,
        duration_ms=dur,
    )


def paginate_document(doc: Document, max_passes: int = 2) -> PaginationResult:
    """Execute multi-page pagination with dynamic field evaluation and two-pass verification."""
    t0 = time.perf_counter()
    from atboffice.modules.writer.models.field import update_fields

    # Pass 1: Initial layout
    res = _execute_single_pagination_pass(doc)
    doc._last_pagination = res  # type: ignore[attr-defined]

    # Evaluate dynamic fields with Pass 1 geometry
    changed = update_fields(doc, res)

    # Pass 2: Repaginate if field expansions occurred or if multi-page to stabilize header/footer page numbers
    has_hf = bool(doc.hf)
    if (changed or (has_hf and res.total_pages > 1)) and max_passes > 1:
        res2 = _execute_single_pagination_pass(doc)
        doc._last_pagination = res2  # type: ignore[attr-defined]
        update_fields(doc, res2)
        res = res2

    res.duration_ms = (time.perf_counter() - t0) * 1000.0
    return res
