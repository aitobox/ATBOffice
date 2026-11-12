# Issue #362 Implementation Plan: Accounting Padding, Currency Locale Tokens, General Width Limit

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Excel number formatting (`_x` padding, `*x` fill + fill position, `[$text-lcid]` currency tokens, 11-char `General` limit) and `GridViewport` column-width fitting / accounting fill rendering / `####` narrow-column handling.

**Architecture:** Port VibeOffice's single-pass section tokenizer, 15-sig-digit decimal rounding, 11-character `General` width formatter, and segment-based output (`FormatSegment`, `fill_pos`, `has_fill`) into `src/atboffice/drawing/numfmt.py`. Integrate width-aware `General` fitting, `####` overflow fallback, and segment painting into `src/atboffice/modules/spreadsheet/views/grid_viewport.py`.

**Tech Stack:** Python 3.12, PySide6 (Qt6), pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/issue-362-fix-numfmt-accounting-currency-general-spec.md`

## Global Constraints

- Preserve `_is_date_format`, `date_to_serial`, `serial_to_parts`, `format_value` compatibility across all callers (`sheet_model.py`, `autofill.py`, `tab_number.py`, `text_fns.py`, `scale.py`).
- All existing tests in `tests/unit/drawing/test_numfmt.py` and `tests/gui/test_ledger_alignment_rendering.py` must continue to pass.
- No placeholder text or unimplemented stubs.

---

### Task 1: Token Parser (`_x`, `*x`, `[$text-lcid]`), Segments, and Number/Date Engine in `numfmt.py`

**Files:**
- Modify: `src/atboffice/drawing/numfmt.py`
- Test: `tests/unit/drawing/test_numfmt.py`

**Interfaces:**
- Produces:
  - `FormatSegment(kind: Literal["text", "pad", "fill"], value: str)`
  - `FormattedResult(text: str, color: str | None = None, is_numeric: bool = False, is_error: bool = False, segments: tuple[FormatSegment, ...] = (), fill_pos: int | None = None, has_fill: bool = False)`
  - `format_value(value: Any, format_str: str = "General", lcid: int | str = 0x04, date1904: bool = False, max_chars: int | None = None) -> FormattedResult`
  - `_is_date_format(code: str) -> bool`

- [ ] **Step 1: Write failing unit tests for `_x`, `*x`, `[$text-lcid]`, and `General` 11-char limit in `tests/unit/drawing/test_numfmt.py`**

Add test classes `TestCurrencyLocaleTokens`, `TestAccountingPaddingAndFill`, and `TestGeneralWidthLimit`:
- `format_value(125.0, "[$£-809]#,##0.00").text == "£125.00"`
- `format_value(125.0, "[$USD]#,##0.00").text == "USD125.00"` (ensures `d`/`s` in `USD` doesn't trigger date mode)
- `format_value(125.0, "[$-409]#,##0.00").text == "125.00"`
- `format_value(1.0, "_($* #,##0.00_)")`: `"$"` and `"1.00"` in `.text`, none of `"_"`, `"*"`, `"("` in `.text`, `has_fill is True`, `fill_pos is not None`, `text[:fill_pos]` has `"$"`, `text[fill_pos:]` has `"1.00"`.
- `format_value(1.0, '_("$"* #,##0.00_);_("$"* \\(#,##0.00\\);_("$"* "-"??_);_(@_)')`: positive, negative, zero, text sections.
- `format_value(0.10000000149011612, "General").text == "0.100000001"`
- `format_value(5715.046400000001, "General", max_chars=8).text == "5715.046"`
- `format_value(123456789012, "General").text == "1.23457E+11"`
- `format_value(12345, "General", max_chars=4)` returns `#` hashes with `is_error=True`.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python -m pytest tests/unit/drawing/test_numfmt.py -v`
Expected: FAIL on the newly added assertions (`[$£-809]`, `_($* ...)`, `General` 11-char limit, `max_chars`).

- [ ] **Step 3: Implement single-pass tokenizer, `FormatSegment`, `General` width formatter, and `FormattedResult` fill metadata in `src/atboffice/drawing/numfmt.py`**

Implement:
- `FormatSegment`, updated `FormattedResult` (`segments`, `fill_pos`, `has_fill`), `PALETTE_56` for `[ColorN]`.
- `_split_sections` respecting `"..."`, `[...]`, `\x`, `_x`, `*x`.
- `_tokenize_section` handling `"..."`, `\x`, `_x`, `*x`, `[color]`, `[ColorN]`, `[cond]`, `[h]`/`[m]`/`[s]`, `[$text-lcid]`, `[DBNumN]`/`[NatNumN]`, `General`, date/time, numeric, `@`.
- `_format_general(num, max_chars=11)` using `Decimal(f"{abs(num):.15g}")` and `ROUND_HALF_UP`, scientific fallback, and `#` error when un-fittable.
- `_format_number_section` placing integer/decimal/exponent/fraction placeholders and preserving `pad`/`fill`/`lit` segments.
- `_format_date_section` preserving `pad`/`fill`/`lit` segments and honoring section `lcid`.
- `_is_date_format(code)` backed by `_tokenize_section` so currency literals like `[$USD]` never false-positive as dates.

- [ ] **Step 4: Run tests to verify pass**

Run: `PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python -m pytest tests/unit/drawing/test_numfmt.py -v`
Expected: PASS (all existing + new tests).

- [ ] **Step 5: Commit Task 1**

```bash
git add src/atboffice/drawing/numfmt.py tests/unit/drawing/test_numfmt.py
git commit -m "fix(numfmt): support accounting _x/*x, [$text-lcid], and General width limit (#362)"
```

---

### Task 2: `GridViewport` Width-Aware Fitting, Accounting Segment Painting, and `####` Overflow

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- Test: `tests/gui/test_ledger_alignment_rendering.py`

**Interfaces:**
- Consumes: `format_value`, `FormatSegment`, `FormattedResult` from `atboffice.drawing.numfmt`.
- Adds on `GridViewport`:
  - `_format_cell_for_paint(self, cell: CellData, disp_val: Any, cell_fm: QFontMetricsF, col_w: int) -> FormattedResult`
  - `_paint_formatted_segments(self, painter: QPainter, segments: tuple[FormatSegment, ...], cell_fm: QFontMetricsF, text_rect: QRect, v_flag: Qt.AlignmentFlag, eff_h: str) -> None`

- [ ] **Step 1: Write failing GUI paint tests in `tests/gui/test_ledger_alignment_rendering.py`**

Add tests:
- `test_accounting_fill_alignment_b3_totals_row_shown`: Load `tests/docs/excel/xlsx/libreoffice__totalsRowShown.xlsx`, render `GridViewport` to `QImage`, verify B3 `(2, 1)` paints dark text pixels for `$` near the left edge of B3, blank background across the middle fill zone, and dark text pixels for `1.00` near the right edge of B3. Also test `GridViewport._format_cell_for_paint` produces `$` before fill and `1.00` after fill.
- `test_general_rounding_poi_60509_e3`: Load `tests/docs/excel/xlsx/poi__60509.xlsx`, verify E3 `(2, 4)` formats to `"5715.046"` at its stored column width (`64px`) and fits within `col_w - 6` without clipping.
- `test_narrow_column_renders_hashes`: Set a narrow column (`col_w=24`) with numeric value `12345.67` (`#,##0.00` and `General`) and verify `_format_cell_for_paint` produces `"#"`s fitting within `avail`.

- [ ] **Step 2: Run GUI tests to verify failure**

Run: `PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python -m pytest tests/gui/test_ledger_alignment_rendering.py -v`
Expected: FAIL because `_format_cell_for_paint` does not exist and B3 renders literal `_($* 1.00_)`.

- [ ] **Step 3: Implement `_format_cell_for_paint`, `_paint_formatted_segments`, and update cell text painting in `src/atboffice/modules/spreadsheet/views/grid_viewport.py`**

In `GridViewport._render_paint_event`:
- Construct cell `QFont` and `QFontMetricsF(font)` before measuring/formatting.
- Call `res = self._format_cell_for_paint(cell, disp_val, cell_fm, col_w)`.
- Measure `text_w` accurately from `res.segments` (excluding fill) or `res.text`.
- Set `span = 1` if `res.has_fill` (accounting cells stay within own column).
- Respect `res.color` when `cf_res.fg_color` is unset.
- Paint via `_paint_formatted_segments` when `res.has_fill` or any `pad` segment is present; otherwise `painter.drawText(text_rect, align_flag, res.text)`.

- [ ] **Step 4: Run GUI and unit tests to verify pass**

Run: `PYTHONPATH=src /opt/anaconda3/envs/ATBOffice/bin/python -m pytest tests/unit/drawing/test_numfmt.py tests/gui/test_ledger_alignment_rendering.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/atboffice/modules/spreadsheet/views/grid_viewport.py tests/gui/test_ledger_alignment_rendering.py
git commit -m "fix(ledger): paint accounting segments, General width fitting, and #### overflow (#362)"
```

---

### Task 3: Full Verification & Smoke Tests

- [ ] **Step 1: Run direct `format_value` smoke assertions from issue #362**
- [ ] **Step 2: Run full pytest suite across `tests/`**
- [ ] **Step 3: Check `git diff main...HEAD` for cleanliness and adherence to repo standards**
