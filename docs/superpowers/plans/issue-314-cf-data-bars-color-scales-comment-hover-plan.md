# Implementation Plan: Issue #314 - Conditional Formatting Data Bars, Color Scales, and Comment Hover Callouts

## Tasks Breakdown

### Task 1: Comprehensive TDD Unit Test Suite
- **File**: `tests/unit/spreadsheet/test_cf_bars_and_comment_bubble.py`
- **Details**:
  - Test 2-color and 3-color scale interpolation across various numeric distributions, boundary values, and zero-span ranges.
  - Test Data Bar relative percentage calculation, min_len / max_len thresholds, negative values, and stop_if_true.
  - Test `GridViewport` rendering with Data Bars (verifying gradient fill and border).
  - Test `GridViewport` mouse hover event logic triggering comment hover card and leader arrow rendering.
  - Test `leaveEvent` resets comment hover card.

### Task 2: Conditional Formatting Evaluation Engine Hardening
- **File**: `src/atboffice/modules/spreadsheet/models/conditional_format.py`
- **Details**:
  - Enhance `DataBarRule` and `evaluate_cf_for_cell` to calculate relative value percentage with full precision, including negative value flags and gradient metadata.
  - Ensure `mix_colors` and 2-color/3-color scale logic handles identical threshold endpoints gracefully without ZeroDivisionError.
  - Return comprehensive `data_bar` dict in `CFResult` with keys `frac`, `color`, `neg_color`, `show_value`, `gradient`, `border_color`, `is_negative`.

### Task 3: Grid Viewport Rendering of Gradient Data Bars and Comment Hover Callout
- **File**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **Details**:
  - In `GridViewport.__init__`: initialize `self._hover_comment_cell: tuple[int, int] | None = None`.
  - In `mouseMoveEvent`: update `self._hover_comment_cell` when hovering over a cell with a comment, and trigger viewport update.
  - In `leaveEvent`: clear `self._hover_comment_cell = None` and trigger viewport update.
  - In `paintEvent` Data Bar drawing:
    - Apply `QLinearGradient` from left to right transitioning from base color to lighter tint.
    - Draw 1px border around the data bar.
    - Ensure text is drawn on top of the bar unless `show_value is False`.
  - In `paintEvent` Comment Callout drawing:
    - Include comments where `cm.visible or show_all or (self._hover_comment_cell == (cr, cc))`.
    - Draw drop shadow with `QColor(0, 0, 0, 45)` offset by (3, 3).
    - Draw pastel yellow note box `QColor(255, 255, 225)` with boundary border.
    - Draw leader line and arrow head pointing to cell top-right corner `(cx + cw, cy)`.
    - Format author name in bold and comment text with word wrap.

### Task 4: Verification & Regression Testing
- Run `pytest tests/unit/spreadsheet/test_cf_bars_and_comment_bubble.py -v`.
- Run full spreadsheet test suite to verify zero regressions.
