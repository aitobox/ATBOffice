# Specification: Issue #313 — [phase8] feat(quire): Floating shapes text wrapping and page bottom footnotes layout

## 1. Overview & Problem Statement

In Quire, Microsoft Word documents frequently contain two critical typographic layout elements:
1. **Anchored Floating Drawings with Text Wrapping**: Drawings, pictures, and shapes with wrap modes (`square`, `tight`, `through`, `topAndBottom`, `behind`, `inFront`). While `wrap.py` defined basic obstacle calculation data structures, the pagination engine (`pagination.py`) and paragraph layout (`portions.py`) did not wire floating shape obstacles into line layout, nor did `canvas_view.py` render floating shapes and pictures onto the canvas view.
2. **Page-Bottom Footnotes & Separator Rule**: Word documents reference footnotes via `<w:footnoteReference>` (`NoteRefItem` in our model). However, `portions.py` ignored `NoteRefItem` (omitting footnote numbers from inline text), `pagination.py` did not reserve page-bottom space for referenced footnotes or calculate page capacity, and `canvas_view.py` lacked the standard 2-inch footnote separator line and footnote body text layout.

This feature implements complete end-to-end support for floating shape text wrapping and page-bottom footnote layout.

---

## 2. Technical Architecture & Design

### 2.1 Paragraph Decomposition & Note Reference Items (`portions.py`)
- Import `NoteRefItem` from `atboffice.modules.writer.models.document`.
- In `decompose_paragraph_to_portions()`:
  - Add explicit handling for `isinstance(item, NoteRefItem)`:
    - If `item.kind == "fn"` (footnote) or `"en"` (endnote):
      - Determine reference display string: `ref_str = item.custom_mark or str(item.note_id)`.
      - Calculate superscript font metrics:
        - `fn_font_sz = max(6.0, font_sz * 0.65)` (Word standard 65% ratio for footnote reference superscripts).
        - Measure text width and ascent/descent for `ref_str` at `fn_font_sz`.
        - Elevate baseline for superscript display: `superscript_shift = font_sz * 0.35`.
      - Append `Portion(type=PortionType.TEXT, text=ref_str, width=w, ascent=ascent + superscript_shift, descent=0.0, font_size=fn_font_sz, font_family=font_family, counts_for_height=True, data=item)`.
      - Advance `char_offset += len(ref_str)`.

### 2.2 Floating Shapes & Text Wrapping (`wrap.py` & `portions.py`)
- Enhance `layout_paragraph()` in `portions.py`:
  - Accept optional parameters:
    - `float_boxes: list[FloatBox] | None = None`
    - `y_offset: float = 0.0`
    - `col_left: float = 0.0`
  - When active `float_boxes` exist on the page:
    - As lines are generated, estimate current line top `cur_y = y_offset + line_top`.
    - Call `calculate_line_segments(col_left, col_left + container_width, cur_y, line_height, float_boxes)`.
    - If `WrapMode.TOP_BOTTOM` obstacle overlaps the line interval:
      - `calculate_line_segments` returns `[]`.
      - The layout engine skips down past the obstacle: `line_top = max(obs.y + obs.h + obs.dist.bottom - y_offset for obs in overlapping_obstacles)`.
    - If `WrapMode.SQUARE` / `TIGHT` / `THROUGH`:
      - Available horizontal text width is constrained to the calculated segment `(seg_start, seg_end)`.
      - Indent left is adjusted: `line.indent_left = seg_start - col_left`.
      - Available line width becomes `seg_end - seg_start`.

### 2.3 Page Footnote Space Reservation & Footnote Area (`pagination.py`)
- Define `PageFootnoteArea`:
  ```python
  @dataclass
  class PageFootnoteArea:
      y: float                     # Top y-coordinate on page where footnote area begins
      height: float                # Total height of footnote area (separator + notes)
      separator_width: float = 144.0  # 2 inches = 144.0 points (Word 2003 standard)
      separator_height: float = 14.0 # 1pt rule + padding
      fragments: list[PageFragment] = field(default_factory=list)
      note_ids: list[str] = field(default_factory=list)
  ```
- Add fields to `Page`:
  - `footnote_area: PageFootnoteArea | None = None`
  - `float_boxes: list[FloatBox] = field(default_factory=list)`
- In `_execute_single_pagination_pass()`:
  - Maintain active floating shapes on the page:
    - When placing a paragraph, inspect its `runs` for `DrawingObject` instances where `float_pr.wrap != WrapMode.INLINE`.
    - Compute `FloatBox` via `resolve_float_box()` and attach to `ctx.current_page.float_boxes`.
  - Maintain footnote reservation per page:
    - As paragraphs are laid out, inspect portions for `NoteRefItem(kind="fn")`.
    - For each referenced `note_id`:
      - Look up `doc.fn.get(note_id)`.
      - If found and not yet laid out on this page:
        - Measure height of footnote paragraphs (formatted with footnote text style, 10pt font, standard indents).
        - Required footnote height = (separator_height if first note on page else 0.0) + sum(fn_p_heights).
        - Dynamic Page Capacity Gate:
          - Check if `col.used_height + frag_height + required_footnote_height > page.body_height`.
          - If capacity is exceeded, trigger page break to advance the paragraph and its footnote to the next page.
        - Once committed to the page:
          - Lay out footnote paragraphs into `PageFragment` items.
          - Record into `page.footnote_area`:
            `y = page.height - page.section.mar_b - total_fn_area_height`
            `height = total_fn_area_height`
            `fragments = fn_fragments`
            `note_ids.append(note_id)`
          - Reduce effective column height available for remaining body text on this page:
            `col.height = page.body_height - page.footnote_area.height`.

### 2.4 Canvas & Vector Rendering (`canvas_view.py`)
- **Footnote Rendering**:
  - In `_paint_page_content()` and `render_page_to_painter()`:
    - If `page.footnote_area` is present:
      - Draw the standard 2-inch separator line:
        - Position: `x = page_rect.left() + pt_to_px(page.body_left)`
        - `y = page_rect.top() + pt_to_px(page.footnote_area.y)`
        - Line: `(x, y)` to `(x + pt_to_px(144.0), y)`
        - Pen: Solid black line, width 0.75 pt.
      - Render footnote fragments:
        - Draw line portions for footnote paragraphs below the separator line.
- **Floating Shapes Rendering**:
  - In `_paint_page_content()` and `render_page_to_painter()`:
    - Pass 1 (Background): Render floating shapes with `behind == True` before drawing text.
    - Pass 2: Render standard page content (paragraphs, tables, inline pictures).
    - Pass 3 (Foreground): Render floating shapes with `behind == False` (`in_front`, `square`, `top_bottom`).
    - For `PictureItem` floating objects: call `_paint_picture()`.
    - For `TextBoxItem` and shape items: draw shape fill, stroke, and inner story paragraphs.

---

## 3. Verification Plan

### 3.1 Unit & GUI Tests (`tests/unit/writer/test_shape_wrap_and_footnotes.py`)
- Test 1: `test_note_ref_item_portion_decomposition`:
  - Verify `NoteRefItem` decomposes into a portion with superscript sizing, height tracking, and note_id preservation.
- Test 2: `test_floating_shape_square_and_top_bottom_wrap`:
  - Create a page with square-wrapped and top-bottom-wrapped shapes.
  - Verify that text lines avoid the square obstacle bounding box and top-bottom pushes text below the obstacle.
- Test 3: `test_footnote_space_reservation_and_pagination`:
  - Create a document with body paragraphs referencing footnotes in `doc.fn`.
  - Verify `page.footnote_area` is created with 2-inch (144.0 pt) separator width and correct vertical position.
  - Verify available page body height is reduced by footnote area height.
- Test 4: `test_footnote_overflow_to_next_page`:
  - When footnote + body text exceeds page height, verify clean page split.
- Test 5: `test_canvas_paint_footnotes_and_floating_shapes`:
  - Offscreen QPainter rendering of `CanvasView` and `render_page_to_painter` verifying zero crashes and correct separator line + shapes rendering.

### 3.2 Regression Verification
- Run:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_shape_wrap_and_footnotes.py -v`
- Run existing writer test suite:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_drawing_wrap.py tests/unit/writer/test_pagination.py tests/unit/writer/test_portions.py -v`
