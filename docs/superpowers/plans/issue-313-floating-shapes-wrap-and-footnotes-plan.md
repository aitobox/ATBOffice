# Implementation Plan: Issue #313 — Floating Shapes Wrap and Footnotes Layout

## Proposed Changes

### 1. `src/atboffice/modules/writer/layout/portions.py`
- Import `NoteRefItem` from `atboffice.modules.writer.models.document`.
- In `decompose_paragraph_to_portions()`:
  - Add support for `NoteRefItem`:
    - Create a portion with superscript font size (0.65x base size), shifted ascent for superscript placement, and `data=item`.
- In `layout_paragraph()`:
  - Add optional parameters `float_boxes: list[FloatBox] | None = None`, `y_offset: float = 0.0`, `col_left: float = 0.0`.
  - When active `float_boxes` overlap lines vertically:
    - If `WrapMode.TOP_BOTTOM`: push line position below the obstacle.
    - If `WrapMode.SQUARE` / `TIGHT` / `THROUGH`: adapt line indentation and width to the obstacle span.

### 2. `src/atboffice/modules/writer/layout/pagination.py`
- Define `PageFootnoteArea` data structure.
- Add `footnote_area: PageFootnoteArea | None = None` and `float_boxes: list[FloatBox] = field(default_factory=list)` to `Page`.
- In `_execute_single_pagination_pass()`:
  - Detect floating shapes anchored in paragraphs via `resolve_float_box()`, adding to `page.float_boxes`.
  - Pass active `float_boxes` to `layout_paragraph()`.
  - Detect `NoteRefItem` in placed paragraphs:
    - Retrieve footnote story from `doc.fn`.
    - Calculate required footnote area height (including standard 2-inch separator rule).
    - Check available page height and push paragraph to next page if capacity is exceeded.
    - Lay out footnote paragraphs and record `page.footnote_area`.
    - Adjust column available height so main text does not collide with footnote area.

### 3. `src/atboffice/modules/writer/views/canvas_view.py`
- In `_paint_page_content()`:
  - Paint background floating shapes (`behind == True`).
  - Paint foreground floating shapes (`behind == False`).
  - If `page.footnote_area`:
    - Paint 2-inch separator line (`144.0` pt width, 0.75 pt black pen).
    - Paint footnote paragraph fragments and line portions.
- In `render_page_to_painter()`:
  - Vector painting for 2-inch footnote separator rule, footnote paragraphs, and floating shapes.

### 4. `tests/unit/writer/test_shape_wrap_and_footnotes.py`
- Comprehensive test suite testing all four acceptance criteria.

---

## Step-by-Step Execution Plan

### Step 1: Write TDD test suite
- File: `tests/unit/writer/test_shape_wrap_and_footnotes.py`
- Test cases:
  1. `test_note_ref_item_portion_decomposition`
  2. `test_floating_shape_square_and_top_bottom_wrap`
  3. `test_footnote_space_reservation_and_pagination`
  4. `test_footnote_overflow_to_next_page`
  5. `test_canvas_view_paint_footnotes_and_shapes`
- Run test to confirm failure (Red state).

### Step 2: Implement `NoteRefItem` support and shape wrap in `portions.py`
- Update `decompose_paragraph_to_portions()` to handle `NoteRefItem`.
- Update `layout_paragraph()` with `float_boxes` obstacle avoidance.
- Verify tests 1 and 2 pass.

### Step 3: Implement `PageFootnoteArea` and pagination reservation in `pagination.py`
- Define `PageFootnoteArea`.
- Update `Page` with `footnote_area` and `float_boxes`.
- Update `_execute_single_pagination_pass()` with floating shape accumulation and footnote space reservation.
- Verify tests 3 and 4 pass.

### Step 4: Implement CanvasView and Vector Painter Rendering in `canvas_view.py`
- Add footnote separator rule and footnote paragraphs painting to `_paint_page_content()` and `render_page_to_painter()`.
- Add floating shape rendering (background and foreground) to `_paint_page_content()` and `render_page_to_painter()`.
- Verify test 5 passes.

### Step 5: Full verification & review transition
- Run all writer unit tests to ensure zero regressions.
- Transition state to `reviewing` and trigger `atb-github-code-reviewer`.
