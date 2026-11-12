# Ledger Text Spill, Merged Cell Blocks, and Non-Wrapped Line Breaks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Ledger spreadsheet rendering so text of any horizontal alignment spills cleanly into empty/styled-empty neighbors (including from offscreen cells), merged cell blocks render across their full bounds with internal gridlines suppressed and text wrapped, and non-wrapped cells render `\n` as a space at the cell's resolved workbook style font.

**Architecture:** Refactor `GridViewport._paint_pane` from single-pass cell drawing into three passes (fills/gridline erasure -> text/spill/offscreen overflow -> borders) with a normalized merge lookup, add `calculate_spill_bounds` for bidirectional spill, normalize line breaks when `wrap_text` is False while adding `TextWordWrap` when True, and resolve omitted cell `s` attributes in `xlsx_reader._parse_worksheet` via row/col/default (`cellXfs[0]`) styles.

**Tech Stack:** Python 3.12+, PySide6 (Qt6), pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/issue-363-ledger-text-spill-merged-cells-spec.md`

## Global Constraints

- Preserve existing `calculate_overflow_span(self, r, c, text_width, col_width) -> int` signature for backward compatibility.
- Support both 4-tuple `(r1, c1, r2, c2)` and `SelectionRange` entries in `model.merges`.
- Do not instantiate empty `CellData` objects for unreferenced `<col style="..."/>` ranges; apply style resolution only to `<c>` cells in `sheetData`.
- Keep all UI text i18n-compliant (no new untranslated UI strings).

---

### Task 1: Resolve Omitted Cell Styles (`cellXfs[0]` / Row / Col Inheritance) in `xlsx_reader.py`

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/io/xlsx_reader.py:820-945`
- Test: `tests/test_ledger_overflow.py`

**Interfaces:**
- Consumes: `style_deltas: list[FormatDelta]` in `_parse_worksheet`
- Produces: Every parsed `CellData` in `sheetData` has `cellXfs[0]` (or row/col style) applied when `<c>` omits `s`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ledger_overflow.py` with a test checking `B2` in `libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx` receives `font_family == "Calibri"` and `font_size == 11`:

```python
"""Tests for Ledger bidirectional text spill, merged cell blocks, and line breaks."""

from __future__ import annotations

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx


def test_tdf169326_b2_inherits_default_workbook_font():
    wb = read_xlsx(
        "tests/docs/excel/xlsx/libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx"
    )
    sh = wb.sheets[0]
    a1 = sh.get_cell(0, 0)
    b2 = sh.get_cell(1, 1)
    assert a1 is not None and b2 is not None
    assert b2.font_family == "Calibri"
    assert b2.font_size == 11
    assert b2.wrap_text is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python -m pytest tests/test_ledger_overflow.py::test_tdf169326_b2_inherits_default_workbook_font -v`
Expected: FAIL (`AssertionError: assert 'Arial' == 'Calibri'`).

- [ ] **Step 3: Implement col/row/default style fallback in `xlsx_reader._parse_worksheet`**

In `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`:
- Record `col_styles: dict[int, int] = {}` while parsing `<col min max style="..."/>` (skipping unbounded tail `c2 - c1 > 1000` unless `c` is in range, or storing `(c1, c2, s_idx)` intervals in a small list `col_style_ranges: list[tuple[int, int, int]]`).
- While parsing `<row>`, read `row_s_str = _attr(row_el, "s")` and `custom_fmt = _attr(row_el, "customFormat") in ("1", "true")`.
- For `<c>`, resolve `s_idx`:
  1. `int(style_idx_str)` if `style_idx_str` is valid
  2. else `row_style` if `custom_fmt` and `row_style` is valid
  3. else matching `col_style_ranges` entry if present
  4. else `0`
- Apply `style_deltas[s_idx]` when `0 <= s_idx < len(style_deltas)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python -m pytest tests/test_ledger_overflow.py::test_tdf169326_b2_inherits_default_workbook_font tests/modules/spreadsheet/test_xlsx_reader.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/modules/spreadsheet/io/xlsx_reader.py tests/test_ledger_overflow.py
git commit -m "fix(xlsx_reader): inherit row/col/default cellXfs[0] style when cell s attribute is omitted (#363)"
```

---

### Task 2: Bidirectional Spill Bounds (`calculate_spill_bounds`) & Non-Wrapped Line Break Normalization

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/views/grid_viewport.py:593-682`
- Test: `tests/test_ledger_overflow.py`

**Interfaces:**
- Consumes: `SheetDataModel.is_empty`, `SheetDataModel.is_merged`
- Produces:
  - `_normalize_unwrapped_text(text: str, wrap_text: bool) -> str`
  - `_is_empty_for_spill(self, r: int, c: int) -> bool`
  - `calculate_overflow_span(self, r: int, c: int, text_width: int, col_width: int) -> int` (stops at merged cells)
  - `calculate_spill_bounds(self, r: int, c: int, text_width: float, col_width: int, eff_h: str, indent_px: int = 0, min_col: int = 0, max_col: int | None = None) -> tuple[int, int]`

- [ ] **Step 1: Write failing unit tests for spill bounds & merge blocking**

Add tests to `tests/test_ledger_overflow.py`:
- `test_spill_bounds_right_aligned_c5_into_b5`: C5 right-aligned long text spills into B5 (`left_col <= 1`, `right_col == 2`).
- `test_spill_bounds_center_aligned_both_ways`: C5 centered text spills into both B5 and D5 (`left_col < 2 < right_col`).
- `test_spill_stops_at_styled_empty_vs_merged_and_occupied`: Styled cell with `value=None` allows spill; merged cell `(4, 1, 4, 1)` or occupied cell stops spill.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python -m pytest tests/test_ledger_overflow.py -k "spill_bounds or spill_stops" -v`
Expected: FAIL (`AttributeError: 'GridViewport' object has no attribute 'calculate_spill_bounds'`).

- [ ] **Step 3: Implement `_normalize_unwrapped_text`, `_is_empty_for_spill`, `calculate_spill_bounds`, and update `calculate_overflow_span` & `_measure_rich_runs_width`**

Implement the helpers cleanly in `src/atboffice/modules/spreadsheet/views/grid_viewport.py`:
- `_normalize_unwrapped_text(text: str, wrap_text: bool) -> str`: returns `text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")` when `not wrap_text` else `text`.
- `_is_empty_for_spill(self, r: int, c: int) -> bool`: checks `0 <= c < self.geometry_mapper.max_cols`, `not self.model.is_merged(r, c)`, and `self.model.is_empty(r, c)`.
- `calculate_overflow_span`: calls `_is_empty_for_spill` so merged neighbors block spill.
- `calculate_spill_bounds`: handles `"left"` (rightward), `"right"` (leftward), and `"center"` / `"centerContinuous"` (both ways from anchor), respecting `min_col`, `max_col`, `indent_px`, and 200-column safety cap.
- `_measure_rich_runs_width`: normalizes `\r\n`, `\r`, `\n` to `" "` when `not cell.wrap_text`.

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python -m pytest tests/test_ledger_overflow.py tests/gui/test_grid_viewport.py -k "overflow or spill" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/modules/spreadsheet/views/grid_viewport.py tests/test_ledger_overflow.py
git commit -m "feat(ledger): add bidirectional calculate_spill_bounds and unwrapped newline normalization (#363)"
```

---

### Task 3: Three-Pass Pane Rendering, Merged Cell Blocks, Word Wrap, and Offscreen Overflow

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/views/grid_viewport.py:1003-1312,1829-1985`
- Test: `tests/test_ledger_overflow.py`

**Interfaces:**
- Consumes: `calculate_spill_bounds`, `_normalize_unwrapped_text`, `self.model.merges`
- Produces:
  - `_normalize_merge(m) -> tuple[int, int, int, int]`
  - `_collect_pane_items(...)`
  - `_paint_cell_item_fill(...)`
  - `_paint_cell_item_text(...)`
  - `_paint_cell_item_borders(...)`
  - `_paint_offscreen_overflow(...)`
  - Updated `_paint_rich_cell` accepting optional `clip_rect: QRect | None = None` and normalizing `\n` when `not cell.wrap_text`.

- [ ] **Step 1: Write failing GUI rendering tests covering all acceptance criteria**

Add rendering pixel tests in `tests/test_ledger_overflow.py`:
1. `test_render_right_aligned_spill_c5_into_b5`: C5 right-aligned long text over styled-empty B5 paints dark text pixels inside B5 (`rect(4, 1)`).
2. `test_render_center_aligned_spill_both_sides`: C5 centered long text spills dark pixels into both B5 and D5, and stops cleanly when D5 is occupied or merged without overlapping D5.
3. `test_render_offscreen_spill_left_and_right`: Scrolling horizontally hides anchor column A (left-aligned) or column E (right-aligned); dark text pixels still appear in visible neighbor columns.
4. `test_render_merged_block_fill_suppresses_gridlines_and_wraps`: Unfilled merge `(0, 0, 1, 2)` erases internal gridlines while keeping outer gridlines; filled merge `(0, 10, 0, 14)` in `poi__45540_form_Header.xlsx` paints gray `#808080` fill and white wrapped text on 2 lines; `A3:O3` in `poi__45540_form_Header.xlsx` paints the full sentence across neighbor columns without clipping.
5. `test_render_totals_row_function_b1_unclipped`: `libreoffice__totalsRowFunction.xlsx` `B1` (`PRESENT PLANNER`) paints white text pixels across `C1` (`rect(0, 2)`) over `#1594A0` background.
6. `test_render_tdf169326_b2_single_line_calibri_11`: `libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx` `B2` renders `Hello World` on one single line (no pixels in upper/lower split rows, ink spans wider than a single word).

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python -m pytest tests/test_ledger_overflow.py -v`
Expected: FAIL on the new rendering tests.

- [ ] **Step 3: Refactor `GridViewport._paint_pane` step 4 into 3-pass rendering + merges + offscreen overflow + word wrap**

Implement in `src/atboffice/modules/spreadsheet/views/grid_viewport.py`:
- `_normalize_merge`: handles 4-tuples and `SelectionRange`.
- `_collect_pane_items`:
  - Indexes merges (`merge_by_cell`, skipping cells > 200k area from dict explosion if ever huge).
  - Collects merges intersecting `[pr_start, pr_end] x [pc_start, pc_end]` (even if `r1 < pr_start` or `c1 < pc_start`).
  - Collects non-merged visible cells in `[pr_start, pr_end] x [pc_start, pc_end]`.
- Pass 1 (`_paint_cell_item_fill`):
  - Paints `bg_col`, `pattern`, and `data_bar` over `item_rect`.
  - If `merge is not None` and no `bg_col`/`pattern`, draws 1px `Qt.GlobalColor.white` lines over internal vertical (`c1+1..c2`) and horizontal (`r1+1..r2`) gridlines strictly inside `item_rect` (clamped to `[pr_start..pr_end]`, `[pc_start..pc_end]`).
- Pass 2 (`_paint_cell_item_text` + `_paint_offscreen_overflow`):
  - Computes `eff_h`, `eff_v`, `fmt_res` (normalizing `\n` -> `" "` when `not cell.wrap_text`).
  - Computes `clip_rect` and `draw_rect` using `calculate_spill_bounds` when eligible (`not cell.wrap_text and not cell.shrink_to_fit and (cell.text_rotation or 0) == 0 and merge is None and not fmt_res.is_numeric and not fmt_res.has_fill and not fmt_res.is_error and eff_h in ("left", "right", "center", "centerContinuous")`).
  - For `center` / `centerContinuous` spill, anchors `draw_rect` symmetrically around `col_x + col_w / 2` while clipping to `[clip_left, clip_right]` so blocked neighbors on one side never shift the center point.
  - When `cell.wrap_text` is True, adds `Qt.TextFlag.TextWordWrap` to `align_flag`.
  - `_paint_rich_cell`: accepts `clip_rect: QRect | None = None` and normalizes `\n` to `" "` when `not cell.wrap_text`.
  - `_paint_offscreen_overflow`: scans left from `pc_start - 1` down to `min_scan_col` and right from `pc_end + 1` up to `max_scan_col` per visible row, painting spilling text from the nearest non-empty unmerged cell into `pane_clip`.
- Pass 3 (`_paint_cell_item_borders`):
  - Draws `top`, `bottom`, `left`, `right` borders on `item_rect` (for merges, top/left from `(r1, c1)` and bottom/right from `(r1, c1)` falling back to `(r2, c1)` / `(r1, c2)`).

- [ ] **Step 4: Run all tests and visual diff spot-checks**

Run:
```bash
PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python -m pytest tests/test_ledger_overflow.py tests/gui/test_ledger_alignment_rendering.py tests/gui/test_grid_viewport.py tests/unit/spreadsheet/ -v
```
And run visual diff spot-checks into `/tmp/diff_after`:
```bash
for f in poi__45540_form_Header.xlsx libreoffice__totalsRowFunction.xlsx libreoffice__tdf169326_ignore_line_breaks_in_referenced_cells.xlsx; do
  PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python scripts/run_office_diff.py \
    --file "tests/docs/excel/xlsx/$f" --capture \
    --candidate-dir /tmp/diff_after/cand --diff-dir /tmp/diff_after/diff \
    --out "/tmp/diff_after/$f.md" --json "/tmp/diff_after/$f.json"
done
```
Inspect rendered PNGs in `/tmp/diff_after/cand/excel/` to confirm visual fidelity!

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/modules/spreadsheet/views/grid_viewport.py tests/test_ledger_overflow.py
git commit -m "fix(ledger): 3-pass pane rendering, bidirectional spill, merged blocks, and word wrap (#363)"
```
