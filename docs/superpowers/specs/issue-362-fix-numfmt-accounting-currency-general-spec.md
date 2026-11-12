# Design Specification: Issue #362 — Accounting Padding, Currency Locale Tokens, General Width Limit

**Issue**: [#362](https://github.com/aitobox/ATBOffice/issues/362) `[TASK-DOC-L03] fix(numfmt): accounting padding, currency locale tokens, General width limit`  
**Branch**: `agent/issue-362-fix-numfmt-accounting-currency-general`  
**Reference**: `.vibeoffice/public/common/numfmt.js`, `.vibeoffice/public/ledger/js/layout.js`, `.vibeoffice/public/ledger/js/render.js`

---

## 1. Problem Statement

`src/atboffice/drawing/numfmt.py` and `src/atboffice/modules/spreadsheet/views/grid_viewport.py` exhibit four rendering fidelity gaps against Excel / VibeOffice:

1. **Accounting padding & fill codes (`_x`, `*x`)**: `_(` / `_)` and `* ` are left as literal characters, producing `'_($* 1.00_)'` in `libreoffice__totalsRowShown.xlsx` B3 instead of left-aligned `$` and right-aligned `1.00` with character-width padding.
2. **Locale-aware currency tokens (`[$text-lcid]`)**: `_parse_tokens` only strips `[$-...]`; tokens with currency text such as `[$£-809]#,##0.00` remain in the pattern and `NUM_TOKEN_RE` treats digits inside `809` as numeric placeholders, producing `'[$£-81259]125.00'` in `libreoffice__totalsRowFunction.xlsx`.
3. **`General` significant character limit & precision**: `format_value(num, "General")` uses `f"{num:.10g}"` without Excel's 11-character limit or 15-significant-digit Decimal rounding, producing `'0.1000000015'` (12 chars) instead of `'0.100000001'` (11 chars) in `openxml-sdk__RelationalPivotA4.xlsx` G27.
4. **Column-width refitting & `####` narrow-column fallback**: `GridViewport` paints `model.get_formatted_text(r, c)` directly without passing column pixel width, so `General` numbers like `5715.046400000001` in `poi__60509.xlsx` E3 (`col_w=64`) are clipped on the left instead of rounded to `5715.046`, and overly narrow numeric cells clip instead of rendering `####`.

---

## 2. Architecture & Data Model

### 2.1 `FormatSegment` & `FormattedResult` (`src/atboffice/drawing/numfmt.py`)

Introduce a lossless segment representation alongside flat `.text` so callers that only need text continue to work seamlessly while `GridViewport` can render exact padding and fill spacing:

```python
@dataclass(frozen=True)
class FormatSegment:
    kind: Literal["text", "pad", "fill"]
    value: str

@dataclass(frozen=True)
class FormattedResult:
    text: str
    color: str | None = None
    is_numeric: bool = False
    is_error: bool = False
    segments: tuple[FormatSegment, ...] = ()
    fill_pos: int | None = None
    has_fill: bool = False
```

- For `FormatSegment("pad", ch)`: in `.text`, contributes `" "` (single space, matching VibeOffice `segText`); in `GridViewport`, advances cursor by `QFontMetricsF.horizontalAdvance(ch)`.
- For `FormatSegment("fill", ch)`: in `.text`, contributes `""`; `has_fill = True`; `fill_pos` records the character offset in `.text` of the first fill segment so callers can split left (`text[:fill_pos]`) and right (`text[fill_pos:]`).
- Adjacent `"text"` segments are coalesced.

### 2.2 Single-Pass Section Tokenizer & Formatter (`numfmt.py`)

Replace regex-only bracket/number parsing with a single-pass section tokenizer modeled on `.vibeoffice/public/common/numfmt.js`:

1. **`_split_sections(code)`**: Splits on `;` outside `"..."` quotes, `[...]` brackets, and `\x` / `_x` / `*x` escapes.
2. **`_tokenize_section(sec)`**: Handles:
   - `"..."` quoted literals
   - `\x` escaped literal
   - `_x` -> `pad` token (`x` defaults to `' '` if at end of string)
   - `*x` -> `fill` token (`x` defaults to `' '` if at end of string)
   - `[...]`:
     - Color names (`COLOR_MAP`) and `[ColorN]` (56-color palette)
     - Conditionals `[<=N]`, `[>=N]`, `[<>N]`, `[<N]`, `[>N]`, `[=N]`
     - Elapsed time `[h]`, `[m]`, `[s]`
     - `[$text-lcid]` / `[$text]` / `[$-lcid]`: splits at first `-` after `$`; emits `text` as a literal token (never re-tokenized as date/digit tokens!) and captures `lcid` for weekday localization (`aaa`/`aaaa`) and system date/time (`F800`/`F400`)
     - `[DBNumN]` / `[NatNumN]` / unknown brackets: ignored
   - `General` (case-insensitive)
   - Date/time tokens (`yyyy`, `yy`, `mmmmm`..`m`, `dddd`..`d`, `aaaa`/`aaa`, `hh`/`h`, `ss`/`s`, `am/pm`, `a/p`, `.0+`)
   - Numeric tokens (`0`, `#`, `?`, `.`, `,`, `%`, `E+`/`E-`/`e+`/`e-`, `/`)
   - `@` text placeholder
3. **Section Selection**: Evaluates conditional sections when present, or selects positive / negative / zero / text section by sign and section count.
4. **Numeric Pattern Formatter (`_format_number_section`)**:
   - Uses `Decimal(f"{abs(val):.15g}")` rounded half-up (`ROUND_HALF_UP`) to avoid binary float artifacts.
   - Places digits across `0`, `#`, `?` placeholders while preserving interleaved literals, `pad`, and `fill` tokens in exact order.
   - Supports `?` rendering as `' '`, grouping `,`, trailing `,` thousands scaling, `%` scaling, scientific notation `E+`/`e+`, and fractions.
5. **`General` Formatter (`_format_general(num, max_chars=11)`)**:
   - `0` -> `"0"`.
   - Normalizes `abs(num)` to 15 significant digits (`Decimal(f"{abs(num):.15g}")`).
   - Fits plain decimal when `-4 <= V` and `V + 1 <= max_chars` (where `V = floor(log10(abs(num)))`), trying descending decimal places up to `max_chars - int_len - 1` and stripping trailing decimal zeros (`0.10000000149011612` at `max_chars=11` -> `'0.100000001'`; `5715.0464` at `max_chars=8` -> `'5715.046'`).
   - Falls back to scientific notation (`E+XX` / `E+XXX`) with descending mantissa digits to fit `max_chars`.
   - If even minimal scientific form exceeds `max_chars`, returns `'#' * max(1, max_chars)` with `is_error=True`.
   - `format_value(..., max_chars: int | None = None)` exposes `max_chars` (default `11` for `General`) while remaining backwards-compatible with all existing callers.

### 2.3 Grid Viewport Integration (`src/atboffice/modules/spreadsheet/views/grid_viewport.py`)

Add a focused helper `_format_cell_for_paint(cell, cell_fm, col_w)` and segment painter `_paint_formatted_segments(...)` in `GridViewport`:

1. Build the cell's `QFont` (`cell.font_family`, `cell.font_size`, `is_bold`, `is_italic`, `cell.underline`) BEFORE measuring text width so measurements use the cell's actual font rather than `self.font()`.
2. Compute `avail = max(1, col_w - 6)` matching `text_rect = QRect(col_x + 3, row_y, span_w - 6, row_h)`.
3. For numeric non-wrapped, non-shrunk, unrotated cells:
   - If `format_code` is `"General"` (case-insensitive):
     - Compute `mdw = max(5, max(int(round(cell_fm.horizontalAdvance(d))) for d in "0123456789"))`.
     - Initial `chars = max(1, min(11, int((avail - 5) // mdw) + 1))`.
     - Format with `format_value(disp_val, "General", max_chars=chars)`.
     - While `cell_fm.horizontalAdvance(res.text) > avail` and `chars > 1` and not `res.text.startswith("#")`: decrement `chars` and re-format.
     - If still `> avail` or `res.text.startswith("#")`: render `"#" * max(1, int(avail // max(1.0, cell_fm.horizontalAdvance("#"))))`.
   - Otherwise (non-`General` numeric format):
     - Format with `format_value(disp_val, cell.format_code)`.
     - Measure `fixed_w = sum(cell_fm.horizontalAdvance(s.value) for s in res.segments if s.kind != "fill")` (or `cell_fm.horizontalAdvance(res.text)` when no segments).
     - If `res.is_error` or (`res.is_numeric` and `fixed_w > avail + 0.5`): render `"#" * max(1, int(avail // max(1.0, cell_fm.horizontalAdvance("#"))))`.
4. **Segment Painting (when `res.has_fill` or any `pad` segment)**:
   - `fill_count = sum(1 for s in res.segments if s.kind == "fill")`.
   - `spare = max(0.0, avail - fixed_w)`.
   - If `fill_count > 0`: anchor `cur_x = float(text_rect.left())` (so `$` sits at the left padding and digits sit at the right padding; `span = 1` so accounting cells never overflow into neighbors).
   - Else (only `pad`, e.g. `#,##0.00_)`): align `cur_x` using `eff_h` (`right` -> `text_rect.right() + 1 - fixed_w`, `center` -> centered, `left` -> `text_rect.left()`).
   - Draw `"text"` segments sequentially; advance `cur_x` by `cell_fm.horizontalAdvance(seg.value)` for `"pad"`; repeat `seg.value` across `spare / fill_count` for non-space `"fill"` and advance by `spare / fill_count`.
5. Respect `res.color` (e.g. `[Red]`) when `cf_res.fg_color` is not set.

---

## 3. Verification Plan

- **Unit tests** (`tests/unit/drawing/test_numfmt.py`):
  - `[$£-809]#,##0.00` -> `'£125.00'`, `[$-409]`, `[$EUR]`, `[$USD]#,##0.00` (not treated as date).
  - `_("$"* #,##0.00_)` for `1.0`, `-1.0`, `0.0`: verifies `.text`, absence of `_`/`*`/`(`, `has_fill=True`, `fill_pos`, and `segments`.
  - `General` 11-char limit: `0.10000000149011612` -> `'0.100000001'`; scientific overflow (`1e12` -> `'1E+12'`, `123456789012` -> `'1.23457E+11'`); narrow `max_chars` rounding (`5715.046400000001` at `max_chars=8` -> `'5715.046'`); too-narrow `####` fallback.
  - All existing `tests/unit/drawing/test_numfmt.py` tests pass.
- **GUI paint tests** (`tests/gui/test_ledger_alignment_rendering.py`):
  - Load `tests/docs/excel/xlsx/libreoffice__totalsRowShown.xlsx`, paint `GridViewport` into a `QImage` (or spy/render), verify B3 paints `$` near left padding and `1.00` near right padding (pixel-level check confirming left-aligned `$` and right-aligned `1.00` separated by blank fill).
  - Load `tests/docs/excel/xlsx/poi__60509.xlsx`, verify E3 formats as `5715.046` at stored column width (`64px`) and fits within cell bounds without clipping leading digits.
  - Verify narrow column numeric cell renders `####`.
- **Full suite**: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/drawing/test_numfmt.py tests/gui/test_ledger_alignment_rendering.py -v` and full `pytest tests/` regression check.
