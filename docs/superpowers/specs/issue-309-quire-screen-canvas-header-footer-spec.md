# Design Specification: Issue #309 - Screen Canvas Header & Footer Rendering & Margin Positioning

## 1. Problem Statement & Objective
In Quire (`src/atboffice/modules/writer/views/canvas_view.py`), `render_page_to_painter` (used for print preview and PDF export) supports laying out and rendering document headers and footers. However, within the interactive screen canvas rendering loop (`_paint_page_content`), only `page.regions` (body content) is painted—`page.header` and `page.footer` are omitted entirely. Users in standard editing view cannot see or verify document headers, footers, or dynamic page number fields (`PAGE` / `NUMPAGES`).

Objective:
1. Connect `page.header` and `page.footer` into `canvas_view.py:_paint_page_content`.
2. Render header and footer text in standard subdued gray (`#666666`) at proper margins (`w:header` / `w:footer`) without overlapping body text under any zoom level.
3. Support different first page (`w:titlePg`) and different odd/even pages (`w:evenAndOddHeaders`).
4. Evaluate dynamic page number fields (`PAGE`, `NUMPAGES`) for the active page index.
5. Deliver a comprehensive unit test suite in `tests/unit/writer/test_header_footer_screen_rendering.py`.

## 2. Architecture & Implementation Design

### 2.1 Screen Canvas Rendering (`canvas_view.py`)
Add `_paint_header_footer` helper in `QuireCanvasView`:
```python
def _paint_header_footer(
    self,
    painter: QPainter,
    page_rect: QRectF,
    page: Page,
    hf: PageHeaderFooter | None,
    is_header: bool,
) -> None:
```
- Converts logical points to pixels using `self.pt_to_px(pt)`.
- Paints text portions in `#666666` font color with `font_size_pt * self._zoom`.
- Supports text formatting (bold, italic, underline, strikethrough).
- Supports tab stops with leaders (dots, hyphens, underscores).
- Supports embedded math items (`OfficeMathItem`).
- Evaluates dynamic field placeholders (`PAGE` -> `format_number(page.page_number, page.page_number_format)`, `NUMPAGES` -> `total_pages`).
- Invoked in `_paint_page_content` before body regions (for `page.header`) and after body regions (for `page.footer`).

### 2.2 Pagination & Dynamic Field Resolution (`pagination.py`)
1. **Even/Odd Settings Detection**:
   Inspect `doc.settings.get("evenAndOddHeaders")` in addition to `"evenOdd"`.
2. **Footer Positioning (`y`)**:
   Set `PageHeaderFooter.y = max(0.0, sect.pg_h - sect.ftr - cur_y)` so that the footer's bottom margin is exactly `sect.ftr` and its top edge matches `bottom_gap` adjustments.
3. **Per-Page Header/Footer Field Layout**:
   In `layout_hf_story`, clone and evaluate dynamic field instructions (`PAGE`, `NUMPAGES`, `SECTIONPAGES`) using `FieldContext(page_number=page_number, total_pages=total_pages, section_index=section_index, section_pages=section_pages, page_number_format=page_number_format)`.

## 3. Edge Cases & Safeguards
- **Empty or missing headers/footers**: Cleanly skip with early returns when `hf is None` or `not hf.fragments`.
- **Different First Page (`titlePg`)**: First page receives `first` header/footer or `None` if not configured; subsequent pages receive `default`.
- **Odd / Even Page Headers (`evenAndOddHeaders`)**: Odd pages (1, 3, 5...) use `default`; even pages (2, 4, 6...) use `even` (or `None` if not provided).
- **Zoom scaling**: All positions, font sizes, baseline offsets, and line decorations scale faithfully with `self._zoom`.
- **No body text overlap**: `top` and `bottom_gap` expand dynamically if header/footer height exceeds standard margins.

## 4. Verification Plan
- Unit tests in `tests/unit/writer/test_header_footer_screen_rendering.py`:
  - Canvas rendering paints `page.header` and `page.footer` on offscreen `QPixmap` / `QPainter`.
  - Header / footer text rendered in subdued gray `#666666`.
  - Dynamic `PAGE` and `NUMPAGES` evaluate correctly across multi-page documents (Page 1 of 3, Page 2 of 3, Page 3 of 3).
  - First page and odd/even page headers and footers render distinct content.
  - Header and footer do not overlap body content.
- Full test suite regression test:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/`
