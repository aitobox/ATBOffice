"""Layout and pagination engine package for ATBOffice Quire."""

from atboffice.modules.writer.layout.pagination import (
    ColumnFrame,
    Page,
    PageFragment,
    PageHeaderFooter,
    PageRegion,
    PaginationResult,
    format_number,
    paginate_document,
)
from atboffice.modules.writer.layout.portions import (
    FONT_LINE_FACTORS,
    LayoutLine,
    ParagraphLayout,
    Portion,
    PortionType,
    collapse_paragraph_spacing,
    compute_grid_line_height,
    decompose_paragraph_to_portions,
    get_line_factor,
    layout_paragraph,
    measure_text_width,
)

__all__ = [
    "ColumnFrame",
    "FONT_LINE_FACTORS",
    "LayoutLine",
    "Page",
    "PageFragment",
    "PageHeaderFooter",
    "PageRegion",
    "PaginationResult",
    "ParagraphLayout",
    "Portion",
    "PortionType",
    "collapse_paragraph_spacing",
    "compute_grid_line_height",
    "decompose_paragraph_to_portions",
    "format_number",
    "get_line_factor",
    "layout_paragraph",
    "measure_text_width",
    "paginate_document",
]
