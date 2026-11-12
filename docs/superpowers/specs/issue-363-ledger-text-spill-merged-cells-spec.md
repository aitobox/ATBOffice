# Issue #363 Design Specification: Ledger Text Spill, Merged Cell Blocks, and Non-Wrapped Line Breaks

**Issue:** [#363 — [TASK-DOC-L06] fix(ledger): text spill into empty neighbors, merged cell blocks](https://github.com/aitobox/ATBOffice/issues/363)
**Branch:** `agent/issue-363-ledger-text-spill-merged-cells`
**Date:** 2026-11-12

---

## 1. Problem Analysis & Root Causes

Visual inspection and code audit of `GridViewport._paint_pane` (`src/atboffice/modules/spreadsheet/views/grid_viewport.py`) and `read_xlsx` (`src/atboffice/modules/spreadsheet/io/xlsx_reader.py`) against the `.vibeoffice/public/ledger/js/render.js` reference revealed four root causes:

1. **Single-pass cell rendering overwrites spilled text:**
   `_paint_pane` iterates columns left-to-right and draws each cell's background fill, borders, and text in the same loop. When cell `(r, c)` spills text into empty neighbor `(r, c+1)` that carries a background fill (e.g., `#FFFFFF` in `poi__45540_form_Header.xlsx` or `#1594A0` in `libreoffice__totalsRowFunction.xlsx`), the next loop iteration paints `(r, c+1)`'s fill directly on top of the spilled text.
2. **Unidirectional spill & missing offscreen spill:**
   `calculate_overflow_span` only calculates rightward spill for `eff_h == "left"`, ignoring `right` (spill left) and `center` / `centerContinuous` (spill both ways from anchor center). It also fails to stop at merged regions (`self.model.is_merged`), and `_paint_pane` never renders spill entering the viewport from offscreen cells left of `pc_start` or right of `pc_end`.
3. **Merged cell blocks ignored during rendering & `wrap_text` missing `TextWordWrap`:**
   `_paint_pane` does not aggregate `self.model.merges` into merged cell rects. Each cell in a merge renders only within its single column width (e.g., `K1` = 26px instead of `K1:O1` = 318px, `A3` = 38px instead of `A3:O3` = 726px), internal gridlines are not suppressed inside unfilled merges, merges anchored above/left of the viewport are skipped, and `align_flag` omits `Qt.TextFlag.TextWordWrap` when `cell.wrap_text` is `True`.
4. **Line breaks in unwrapped cells & omitted cell style `s` attribute:**
   `QPainter.drawText(QRect, flags, text)` breaks on `\n` even when `wrap_text=False`, whereas Excel/VibeOffice renders `\n` as a space on one line (`libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx` `B2`). In addition, `xlsx_reader._parse_worksheet` skips `style_deltas` when `<c>` omits the `s` attribute, causing `B2` to render in `CellData`'s hardcoded `Arial 10` instead of `cellXfs[0]` (`Calibri 11`).

---

## 2. Design & Architecture

### 2.1 Autonomous Architectural Decisions (>= 90% Confidence)

- **Decision 1 — Three-Pass Pane Rendering in `GridViewport._paint_pane`:**
  Split cell rendering in `_paint_pane` into three distinct passes matching `render.js:353-443`:
  1. **Collect Pane Items (`_collect_pane_items`)**: Build a fast cell-to-merge map for `self.model.merges` (supporting both 4-tuple `(r1, c1, r2, c2)` and `SelectionRange`), include all merges overlapping `[pr_start, pr_end] x [pc_start, pc_end]` (even if `r1 < pr_start` or `c1 < pc_start`), skip non-anchor cells inside merges, and collect visible non-merged cells.
  2. **Pass 1 — Fills, Patterns, Data Bars, and Merge Internal Gridline Erasure**: Paint background fills, patterns, and data bars across each item's full rect (full merged rect for merges). For unfilled merges, erase internal vertical and horizontal gridlines strictly inside the merge (`c1+1..c2` and `r1+1..r2`) with white 1px lines so outer gridlines and selection highlights remain intact.
  3. **Pass 2 — Cell Text, Bidirectional Spill & Offscreen Overflow**: Render cell text for all collected items with text, followed by `_paint_offscreen_overflow` for cells outside `[pc_start, pc_end]`.
  4. **Pass 3 — Borders**: Draw cell and merge outer borders on top of fills and text. For merged blocks, use top-left `(r1, c1)` borders for top/left and fall back to `(r2, c1)`/`(r1, c2)` for bottom/right if top-left lacks them.

- **Decision 2 — Bidirectional Spill Bounds & Clipping (`calculate_spill_bounds`):**
  - Keep `calculate_overflow_span(self, r, c, text_width, col_width) -> int` for backward compatibility with existing callers/tests, adding `self.model.is_merged(r, curr_c)` as a stop condition.
  - Add `calculate_spill_bounds(self, r, c, text_width, col_width, eff_h, indent_px=0, min_col=0, max_col=None) -> tuple[int, int]` returning inclusive `(left_col, right_col)`:
    - Eligible for spill iff `not cell.wrap_text`, `not cell.shrink_to_fit`, `(cell.text_rotation or 0) == 0`, not merged, `not fmt_res.is_numeric`, `not fmt_res.has_fill`, and `eff_h in ("left", "right", "center", "centerContinuous")`.
    - `is_cell_empty_for_spill(r, cc)` returns `True` iff `0 <= cc < max_cols`, `not self.model.is_merged(r, cc)`, and `self.model.is_empty(r, cc)` (so styled cells with `value=None` or `""` are empty).
    - `left`: walks right from `c + 1` while accumulated width `< text_width + 6 + indent_px`.
    - `right`: walks left from `c - 1` while accumulated width `< text_width + 6 + indent_px`.
    - `center` / `centerContinuous`: computes `need = max(0.0, (text_width - (col_width - 6)) / 2.0)` and walks left and right independently until each side covers `need + 3` or hits a non-empty/merged cell.
  - **Center-anchored clipping**: For `center` / `centerContinuous`, compute `text_rect` centered on the anchor cell `(col_x + col_w / 2)` with width `max(col_w, text_width + 6)` while clipping strictly to `[clip_left, clip_right]`, ensuring asymmetric blocked neighbors never shift the text's anchor center.

- **Decision 3 — Offscreen Overflow (`_paint_offscreen_overflow`):**
  For each visible row `r` in `[pr_start, pr_end]` (with `row_size(r) > 0`):
  - Scan left from `pc_start - 1` down to `max(min_scan_col, pc_start - 256)` (where `min_scan_col = fz_c` when `pc_start >= fz_c > 0`, else `0`) until hitting a merged cell or first non-empty cell; if that cell can spill right (`eff_h in ("left", "center", "centerContinuous")`), paint its text clipped to `pane_clip` and its spill bounds.
  - Scan right from `pc_end + 1` up to `min(max_scan_col, pc_end + 64)` (where `max_scan_col = fz_c - 1` when `pc_end < fz_c`, else `max_cols - 1`) until hitting a merged cell or first non-empty cell; if that cell can spill left (`eff_h in ("right", "center")`), paint its text clipped to `pane_clip` and its spill bounds.

- **Decision 4 — Line Breaks & Word Wrap:**
  - Normalize `\r\n`, `\r`, `\n` to `" "` when `not cell.wrap_text` before measuring width and painting (both in plain-text painting and `_paint_rich_cell` / `_measure_rich_runs_width`).
  - Add `Qt.TextFlag.TextWordWrap` to `align_flag` when `cell.wrap_text` is `True`.

- **Decision 5 — Default / Inherited Style Resolution in `xlsx_reader._parse_worksheet`:**
  - Collect `<col min max style="..."/>` mappings (`col_styles`) and `<row r="..." s="..." customFormat="1"/>` (`row_style`).
  - For each `<c>` element created in `sheetData`, resolve `s_idx` in order: cell `s` attribute -> `row_style` (when `customFormat` is `"1"`/`"true"`) -> `col_styles.get(c)` -> `0` (`style_deltas[0]`), and apply `style_deltas[s_idx]`.

---

## 3. Files Affected

- `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- `tests/test_ledger_overflow.py` (new)

---

## 4. Verification Plan

1. Unit and GUI rendering tests in `tests/test_ledger_overflow.py`:
   - Left-aligned, right-aligned, and centered text spill across empty and styled-but-empty neighbors.
   - Spill stops at occupied cells and merged regions.
   - Offscreen spill from cells left of `pc_start` and right of `pc_end` renders pixels in the viewport.
   - Merged blocks render fill across the full span, suppress internal gridlines, and wrap text (`poi__45540_form_Header.xlsx` `A3:O3`, `K1:O1`).
   - `libreoffice__totalsRowFunction.xlsx` `B1` (`PRESENT PLANNER`) paints unclipped across `C1`.
   - `libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx` `B2` renders `Hello World` on one line at `Calibri 11`.
2. Full spreadsheet & regression test suite (`pytest`).
3. Visual diff check via `scripts/run_office_diff.py` on the three target fixtures (`poi__45540_form_Header.xlsx`, `libreoffice__totalsRowFunction.xlsx`, `libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx`).
