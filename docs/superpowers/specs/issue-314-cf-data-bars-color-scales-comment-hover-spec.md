# Specification: Issue #314 - Conditional Formatting Data Bars, Color Scales, and Comment Hover Callouts

## 1. Overview & Objective
Enhance ATBOffice Ledger's spreadsheet conditional formatting visual fidelity and interactive commenting experience:
1. **Data Bars**: Calculate relative value percentage within range and render horizontal gradient Data Bars inside cells in `grid_viewport.py` with smooth color transitions, borders, and negative value awareness.
2. **Color Scales**: Ensure accurate linear RGB interpolation across 2-color and 3-color Color Scale thresholds in `conditional_format.py` and seamless background rendering in `grid_viewport.py`.
3. **Comment Hover Callout Card**: Implement a floating comment callout card on cell hover in `grid_viewport.py`, featuring:
   - Author name (bold) & message text (with word wrap).
   - Semi-transparent drop shadow for depth.
   - Leader arrow pointing towards the cell's top-right red indicator triangle.
   - Seamless hover state tracking in `mouseMoveEvent` and `leaveEvent`.

## 2. Architecture & Design

### 2.1 Conditional Formatting Engine (`conditional_format.py`)
- **DataBar Calculation**:
  - Extract all numeric values across CF ranges to determine range min and max.
  - Compute relative percentage `t = (val - lo) / (hi - lo)` (clamped to `[0.0, 1.0]`, fallback to 1.0 if span is zero).
  - Compute fraction `frac = min_len + (max_len - min_len) * t`.
  - Package `CFResult.data_bar` with `{frac, color, neg_color, show_value, gradient, is_negative, border_color}`.
- **ColorScale Calculation**:
  - 2-color scale: interpolate between `cols[0]` and `cols[1]` across threshold interval `[th0, th1]`.
  - 3-color scale:
    - If `val <= th1`: interpolate between `cols[0]` and `cols[1]` across `[th0, th1]`.
    - Else: interpolate between `cols[1]` and `cols[2]` across `[th1, th2]`.
  - Handle edge cases: zero spans, out-of-bound values, missing values.

### 2.2 Viewport Rendering (`grid_viewport.py`)
- **Data Bar Rendering**:
  - Position within `cell_rect`: `col_x + 1`, `row_y + 1`, `bar_w = int((col_w - 2) * bar_frac)`, `row_h - 2`.
  - If gradient is enabled (default `True`): create `QLinearGradient(bx, by, bx + bar_w, by)` transitioning from base color to a lighter tint (`QColor(base_col).lighter(160)` or `#FFFFFF` fade).
  - Stroke 1px border with `bar_color` or `border_color`.
  - Value text drawn on top of data bar unless `show_value == False`.
- **Comment Hover Callout Card**:
  - State: `self._hover_comment_cell: tuple[int, int] | None = None`.
  - Event Handling:
    - In `mouseMoveEvent`: check `hit.row`, `hit.col`. If cell has a comment, set `self._hover_comment_cell = (hit.row, hit.col)` and trigger `self.viewport().update()`. If cell changes or has no comment, update and trigger repaint.
    - In `leaveEvent`: clear `self._hover_comment_cell = None` and trigger `self.viewport().update()`.
  - Rendering in `paintEvent`:
    - Draw comments matching `cm.visible or show_all or (self._hover_comment_cell == (cr, cc))`.
    - Render callout card:
      1. Drop shadow: `QRect(bx + 3, by + 3, bw, bh)` filled with `QColor(0, 0, 0, 45)`.
      2. Card box: `QRect(bx, by, bw, bh)` with pastel yellow fill `QColor(255, 255, 225)` and subtle gray border `QPen(QColor(160, 160, 160), 1)`.
      3. Leader arrow: line from card edge `(bx, by + 8)` to cell top-right corner `(cx + cw, cy)` with a directional arrow head pointing to the cell corner.
      4. Header & Body: Author name in bold font, followed by comment text with word wrap.

## 3. Edge Cases & Resilience
- **Division by zero**: Range has uniform values (`max == min`), guard `span == 0` defaulting to `t = 1.0` or `0.5`.
- **Non-numeric cells**: Safely skipped by CF numeric extractions.
- **Scroll & Zoom**: All positions derived via `geometry_mapper` with scroll offsets `psx`, `psy`.
- **i18n & Locales**: All user-visible dialog/strings wrapped in `safe_tr()`.
