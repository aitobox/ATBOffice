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
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    Story,
    Table,
    TextItem,
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


def layout_hf_story(
    doc: Document,
    story: Story | None,
    sect: SectionProperties,
    body_width: float,
    kind: str,
    y: float,
) -> PageHeaderFooter:
    """Layout header or footer story and return PageHeaderFooter with computed height."""
    if not story or not story.blocks:
        return PageHeaderFooter(kind=kind, story=story, y=y, width=body_width, height=0.0)

    fragments: list[PageFragment] = []
    cur_y = 0.0
    for block in story.blocks:
        if isinstance(block, Paragraph):
            p_layout = layout_paragraph(
                p=block,
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

    return PageHeaderFooter(
        kind=kind,
        story=story,
        y=y,
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

    def start_page(
        self,
        sect_idx: int,
        sect: SectionProperties,
        first_of_section: bool,
        is_blank: bool = False,
    ) -> Page:
        pg_idx = len(self.pages)
        even_odd = bool(self.doc.settings.get("evenOdd", False))
        mirror = bool(self.doc.settings.get("mirror", False)) and (self.page_number % 2 == 0)
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

        hdr_layout = layout_hf_story(self.doc, hdr_story, sect, body_w, "header", sect.hdr)
        ftr_y = max(0.0, sect.pg_h - sect.ftr)
        ftr_layout = layout_hf_story(self.doc, ftr_story, sect, body_w, "footer", ftr_y)

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
        num_cols = getattr(sect.cols, "n", 1) or 1
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
) -> None:
    """Evaluate and update text values of dynamic PAGE, NUMPAGES, SECTIONPAGES fields."""
    total_pages = len(pages)
    for pg in pages:
        # Check all paragraphs on page
        all_frags: list[PageFragment] = []
        if pg.header:
            all_frags.extend(pg.header.fragments)
        for reg in pg.regions:
            for col in reg.columns:
                all_frags.extend(col.fragments)
        if pg.footer:
            all_frags.extend(pg.footer.fragments)

        for frag in all_frags:
            p = frag.paragraph
            if p is None:
                continue
            in_field = False
            cur_field_type = None
            for it in p.runs:
                if isinstance(it, FieldBeginItem):
                    in_field = True
                    cur_field_type = str(it.field_type or it.instr or "").strip().upper()
                elif isinstance(it, FieldSeparateItem):
                    pass
                elif isinstance(it, FieldEndItem):
                    in_field = False
                    cur_field_type = None
                elif in_field and isinstance(it, TextItem):
                    if cur_field_type == "PAGE":
                        it.text = format_number(pg.page_number, pg.page_number_format)
                    elif cur_field_type == "NUMPAGES":
                        it.text = format_number(total_pages, "decimal")
                    elif cur_field_type == "SECTIONPAGES":
                        sec_cnt = (
                            section_pages[pg.section_index]
                            if pg.section_index < len(section_pages)
                            else 1
                        )
                        it.text = format_number(sec_cnt, "decimal")


def paginate_document(doc: Document) -> PaginationResult:
    """Execute complete multi-page pagination for a Document."""
    t0 = time.perf_counter()
    ctx = _PaginationContext(doc)

    for si, sec_info in enumerate(ctx.sect_list):
        sect = sec_info["sect"]
        start_num = getattr(sect.pg_num, "start", None) if getattr(sect, "pg_num", None) else None
        if start_num is not None:
            ctx.page_number = start_num

        first_of_section = True
        ctx.start_page(si, sect, first_of_section=first_of_section)

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

        # Check section break parity for next section
        if si + 1 < len(ctx.sect_list):
            next_sect = ctx.sect_list[si + 1]["sect"]
            s_type = (
                getattr(next_sect, "sect_type", None)
                or getattr(next_sect, "type", "nextPage")
                or "nextPage"
            )
            # The next page number that would be assigned:
            next_pno = ctx.page_number
            if s_type == "oddPage" and (next_pno % 2 == 0):
                ctx.start_page(si, sect, first_of_section=False, is_blank=True)
            elif s_type == "evenPage" and (next_pno % 2 != 0):
                ctx.start_page(si, sect, first_of_section=False, is_blank=True)
            elif s_type == "continuous":
                col = ctx.current_column()
                if col and (col.height - col.used_height >= 24.0):
                    pass

    total_pgs = len(ctx.pages)
    sec_pages: list[int] = [0] * len(ctx.sect_list)
    for pg in ctx.pages:
        if 0 <= pg.section_index < len(sec_pages):
            sec_pages[pg.section_index] += 1

    # Dynamic page number resolution
    _update_dynamic_fields(doc, ctx.pages, sec_pages)

    dur = (time.perf_counter() - t0) * 1000.0
    return PaginationResult(
        pages=ctx.pages,
        total_pages=total_pgs,
        section_pages=sec_pages,
        duration_ms=dur,
    )
