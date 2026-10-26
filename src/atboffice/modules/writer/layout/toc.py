"""Automated Table of Contents (TOC) generator and updater for Quire (Word 2003 port).

Scans heading paragraphs and outline levels, creates hidden target bookmarks (_Toc...),
generates formatted TOC paragraphs with dot-leader tab stops, and inserts dynamic
PAGEREF fields with hyperlink navigation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from atboffice.modules.writer.models.document import (
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    RunItem,
    TabItem,
    TextItem,
    plain_text,
)
from atboffice.modules.writer.models.field import (
    ensure_para_bookmark,
    parse_field_instruction,
)
from atboffice.modules.writer.models.properties import (
    ParagraphProperties,
    RunProperties,
    TabStop,
)

if TYPE_CHECKING:
    from atboffice.modules.writer.layout.pagination import PaginationResult


@dataclass
class TOCEntry:
    """An individual entry gathered for the Table of Contents."""

    paragraph: Paragraph
    level: int
    text: str
    page_number: int = 1


def get_paragraph_heading_level(doc: Document, p: Paragraph) -> int | None:
    """Determine heading level (1-9) of paragraph from style name or outline level."""
    # 1. Check explicit outline level
    if p.p_pr.outline_level is not None:
        return p.p_pr.outline_level + 1

    # 2. Check paragraph style
    style_id = p.p_pr.style or "Normal"
    st = doc.styles.get(style_id)
    s_name = (st.name if st else style_id).lower()

    m = re.search(r"heading\s*(\d)", s_name)
    if m:
        lvl = int(m.group(1))
        if 1 <= lvl <= 9:
            return lvl

    # Check style's outline_level if set
    if st and st.p_pr and st.p_pr.outline_level is not None:
        return st.p_pr.outline_level + 1

    return None


def collect_toc_entries(
    doc: Document,
    instr: str = 'TOC \\o "1-3" \\h \\z \\u',
    pagination_result: PaginationResult | None = None,
) -> list[TOCEntry]:
    """Scan document paragraphs and collect headings within requested levels."""
    f = parse_field_instruction(instr)

    # Parse \o level range
    lo, hi = 1, 3
    o_val = f.sw.get(r"\o")
    if isinstance(o_val, str):
        m = re.search(r"(\d)\s*-\s*(\d)", o_val)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
    elif o_val is True:
        lo, hi = 1, 9

    use_outline = (r"\u" in f.sw) or (r"\o" in f.sw)

    # Custom style mapping \t "Style1,1,Style2,2"
    style_map: dict[str, int] = {}
    t_val = f.sw.get(r"\t")
    if isinstance(t_val, str):
        parts = [p.strip() for p in re.split(r"[,;]", t_val)]
        for i in range(0, len(parts) - 1, 2):
            try:
                style_map[parts[i].lower()] = int(parts[i + 1])
            except ValueError:
                pass

    # Map paragraph to page number
    para_page_map: dict[int, int] = {}
    if pagination_result:
        for pg in pagination_result.pages:
            for reg in pg.regions:
                for col in reg.columns:
                    for fr in col.fragments:
                        if fr.paragraph and fr.paragraph.id not in para_page_map:
                            para_page_map[fr.paragraph.id] = pg.page_number

    # Skip paragraphs that belong to existing TOC
    skip_paras: set[int] = set()
    for p in doc.main.paras:
        style_id = (p.p_pr.style or "").upper()
        if style_id.startswith("TOC") or any(
            isinstance(it, FieldBeginItem) and "TOC" in (it.field_type or it.instr).upper()
            for it in p.runs
        ):
            skip_paras.add(p.id)

    entries: list[TOCEntry] = []
    for p in doc.main.paras:
        if p.id in skip_paras:
            continue

        text = plain_text(p).strip()
        if not text:
            continue

        lvl: int | None = None
        st_obj = doc.styles.get(p.p_pr.style or "Normal")
        s_name = (st_obj.name if st_obj else (p.p_pr.style or "")).lower()
        if s_name in style_map:
            lvl = style_map[s_name]
        elif use_outline:
            lvl = get_paragraph_heading_level(doc, p)

        if lvl is not None and lo <= lvl <= hi:
            pg_num = para_page_map.get(p.id, 1)
            entries.append(
                TOCEntry(
                    paragraph=p,
                    level=lvl,
                    text=text,
                    page_number=pg_num,
                )
            )

    return entries


def build_toc(
    doc: Document,
    instr: str = 'TOC \\o "1-3" \\h \\z \\u',
    pagination_result: PaginationResult | None = None,
) -> list[Paragraph]:
    """Build formatted TOC paragraph list according to instruction switches."""
    f = parse_field_instruction(instr)
    entries = collect_toc_entries(doc, instr, pagination_result)

    links = bool(f.sw.get(r"\h", False))
    sep_tab = r"\p" not in f.sw

    # Calculate printable text width of section
    sect = doc.sect
    text_width = sect.pg_w - sect.ml - sect.mr - (sect.gutter or 0.0)
    if text_width <= 0:
        text_width = 451.3  # Standard A4/Letter default (points)

    if not entries:
        p_empty = Paragraph(
            runs=[TextItem(text="No table of contents entries found.", r_pr=RunProperties(b=True))],
            p_pr=ParagraphProperties(style="TOC1"),
        )
        return [p_empty]

    blocks: list[Paragraph] = []
    for e in entries:
        bm_name = ensure_para_bookmark(doc, e.paragraph, prefix="_Toc")
        style_id = f"TOC{e.level}"
        if style_id not in doc.styles:
            from atboffice.modules.writer.models.styles import builtin_styles

            doc.styles[style_id] = builtin_styles().get(style_id)

        link_dict = {"anchor": bm_name} if links else None
        r_pr = RunProperties(link=link_dict)

        runs: list[RunItem] = [TextItem(text=e.text, r_pr=r_pr)]

        # Tab with dot leader
        if sep_tab:
            runs.append(TabItem(r_pr=r_pr))
        else:
            runs.append(TextItem(text=str(f.sw.get(r"\p", " ")), r_pr=r_pr))

        # Dynamic PAGEREF field
        page_str = str(e.page_number)
        runs.extend(
            [
                FieldBeginItem(
                    field_type="PAGEREF",
                    instr=f'PAGEREF {bm_name} \\h',
                    r_pr=r_pr,
                ),
                FieldSeparateItem(r_pr=r_pr),
                TextItem(text=page_str, r_pr=r_pr),
                FieldEndItem(r_pr=r_pr),
            ]
        )

        tab_stop = TabStop(
            pos=round(text_width, 1),
            align="right",
            leader="dot" if sep_tab else "none",
        )

        p = Paragraph(
            runs=runs,
            p_pr=ParagraphProperties(
                style=style_id,
                tabs=[tab_stop],
            ),
        )
        blocks.append(p)

    return blocks


def insert_or_update_toc(
    doc: Document,
    instr: str = 'TOC \\o "1-3" \\h \\z \\u',
    at_idx: int | None = None,
    pagination_result: PaginationResult | None = None,
) -> list[Paragraph]:
    """Insert or update Table of Contents paragraphs in document main story."""
    toc_blocks = build_toc(doc, instr, pagination_result)
    if not toc_blocks:
        return []

    # Find existing TOC range in doc.main.paras
    first_toc_idx = -1
    last_toc_idx = -1
    for idx, p in enumerate(doc.main.paras):
        is_toc = (p.p_pr.style or "").upper().startswith("TOC")
        if is_toc:
            if first_toc_idx == -1:
                first_toc_idx = idx
            last_toc_idx = idx

    if first_toc_idx != -1 and last_toc_idx != -1:
        # Replace existing TOC paragraphs
        doc.main.paras[first_toc_idx : last_toc_idx + 1] = toc_blocks
    else:
        # Insert at target index or document beginning
        target_pos = 0 if at_idx is None else at_idx
        doc.main.paras[target_pos:target_pos] = toc_blocks

    # Reindex story paragraphs
    doc.main.blocks = list(doc.main.paras)
    for idx, p in enumerate(doc.main.paras):
        p._o = idx

    return toc_blocks
