# Specification: Full Excel Paste Special Dialog Semantics & Engine (Issue #339)

## 1. Overview & Objective
Align ATBOffice Ledger's Paste Special feature (`Edit ▸ Paste Special...` / `Ctrl+Alt+V`) with Excel 2003 and VibeOffice (`.vibeoffice/public/ledger/js/clipboard.js`). 
This includes:
1. Complete Paste Special dialog (`PasteSpecialDialog`) with all classic radio options, operation radios, skip blanks & transpose checkboxes, Paste Link, and full i18n.
2. Complete semantic paste engine in `GridViewport.paste_special` supporting:
   - Tiling across target selections when selection dimensions are multiples of source block dimensions.
   - Arithmetic operations (`add`, `subtract`/`sub`, `multiply`/`mul`, `divide`/`div`) with division-by-zero protection (`#DIV/0!`), handling numbers, strings, and formulas.
   - Dimension transposition (`transpose`) swapping rows and columns for cells, formatting, merges, comments, and data validations.
   - Formula relative coordinate shifting and vector transposition.
   - Preservation of target borders under `noBorders` / `allExceptBorders`.
   - Selective paste modes (`all`, `formulas`, `values`, `formats`, `comments`, `validation`, `colWidths`, `formulasNF`, `valuesNF`).
   - Protected sheet validation via `guard_protect(cell_edit=True)`.
   - Undo/Redo integration.

## 2. Architecture & Design

### 2.1 Dialog Architecture (`paste_special_dialog.py`)
- Window title: `选择性粘贴` / `Paste Special`
- Radio Groups:
  - **Paste Group**:
    - `all`: 全部(&A) / All
    - `formulas`: 公式(&F) / Formulas
    - `values`: 数值(&V) / Values
    - `formats`: 格式(&T) / Formats
    - `comments`: 批注(&C) / Comments
    - `validation`: 有效性验证(&N) / Validation
    - `noBorders`: 无边框(&X) / All except borders
    - `colWidths`: 列宽(&W) / Column widths
    - `formulasNF`: 公式和数字格式(&R) / Formulas and number formats
    - `valuesNF`: 值和数字格式(&U) / Values and number formats
  - **Operation Group**:
    - `none`: 无(&O) / None
    - `add`: 加(&D) / Add
    - `sub`: 减(&S) / Subtract
    - `mul`: 乘(&M) / Multiply
    - `div`: 除(&I) / Divide
  - **Modifiers**:
    - `skip_blanks`: 跳过空单元(&B) / Skip blanks
    - `transpose`: 转置(&E) / Transpose
  - **Buttons**:
    - `btn_paste_link`: 粘贴链接(&L) / Paste Link
    - `btn_ok`: 确定 / OK
    - `btn_cancel`: 取消 / Cancel
- Full `retranslate_ui` support for dynamic locale switching.

### 2.2 Semantic Engine Architecture (`grid_viewport.py`)
- **Clipboard Snapshot**: Ensure `copy()` captures cells, dimensions (`h`, `w`), column widths, internal range `pr`, merges, and comments.
- **Destination Tiling**:
  - Determine `dest_h` and `dest_w` based on `transpose`.
  - If current selection `sel_h > 1 or sel_w > 1`, and `sel_h % dest_h == 0` and `sel_w % dest_w == 0`, destination tiles across the entire target selection (`tile_h = sel_h`, `tile_w = sel_w`).
  - Otherwise destination is single block `tile_h = dest_h, tile_w = dest_w`.
- **Math Execution**:
  - Convert values safely from strings/numbers.
  - Compute target value cell-by-cell.
  - If dividing by zero, return `#DIV/0!`.
- **Transpose Execution**:
  - Swap rows and cols: `dest_h = src_w`, `dest_w = src_h`.
  - Map cell `(r, c)` using `src_i = sj, src_j = si`.
  - Transpose merges `(r1, c1, r2, c2) -> (c1, r1, c2, r2)`.
  - Transpose comments and validations.
  - Relative formula coordinate transformation.
- **Shortcuts**:
  - Bind `Ctrl+Alt+V` in `GridViewport.keyPressEvent` to invoke `paste_special()`.

### 2.3 Verification & Testing Strategy
- Unit and GUI test file: `tests/gui/test_phase9_paste_special_semantics.py`.
- Test cases:
  1. Dialog initialization, option extraction, and `retranslate_ui`.
  2. Multi-cell tiling across destination selection for math operations and paste.
  3. Arithmetic operations (Add, Sub, Mul, Div, Div by zero `#DIV/0!`).
  4. Transpose dimensions (e.g. 2x3 block becomes 3x2 block) with data, merges, and comments.
  5. Transpose formula coordinate translation.
  6. Skip blanks behavior with empty cells vs existing values.
  7. Formats, No Borders, Column Widths, Formulas & NF, Values & NF.
  8. Sheet protection enforcement.
  9. Undo / Redo fidelity.
