# Implementation Plan: Paste Special Dialog Semantics & Engine (Issue #339)

## Task Breakdown

### Task 1: Refine `PasteSpecialDialog` in `src/atboffice/modules/spreadsheet/dialogs/paste_special_dialog.py`
- Verify and refine radio button labels and accelerators matching classic Excel 2003 / VibeOffice.
- Ensure all option aliases (`what`, `type`, `op`, `operation`, `skip_blanks`, `transpose`, `link`) are fully supported.
- Ensure 100% i18n coverage in `retranslate_ui`.

### Task 2: Implement Formula Transposition Helper in `src/atboffice/modules/spreadsheet/calc/references.py`
- Add `transpose_formula(text: str, src_r: int, src_c: int, target_r: int, target_c: int) -> str`
- Translate relative cell and area references during transpose operations.

### Task 3: Enhance Semantic Paste Engine in `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- Ensure `copy()` captures merges and comments into `_internal_clipboard`.
- In `paste_special`:
  - Enforce `guard_protect(cell_edit=True)`.
  - Calculate tiled destination when target selection is multiple of source block dimensions.
  - Apply math operations cell-by-cell over full destination.
  - Implement Transpose swapping for cells, formulas, formatting, merges, and comments.
  - Implement `noBorders` keeping existing target borders.
  - Add `Ctrl+Alt+V` key handler in `keyPressEvent`.

### Task 4: Comprehensive Tests in `tests/gui/test_phase9_paste_special_semantics.py`
- TDD tests exercising all acceptance criteria:
  - Dialog options and retranslation.
  - Math operations (`add`, `sub`, `mul`, `div`, zero division `#DIV/0!`).
  - Destination selection tiling (1x1 factor multiplied over NxM range).
  - Transpose dimensions, formulas, merges, comments.
  - Skip blanks.
  - Sheet protection guard.
  - Undo / Redo.

### Task 5: Verification & Quality Gate
- Run `pytest tests/gui/test_phase9_paste_special_semantics.py -v`.
- Run full phase7/phase9 tests to verify zero regressions.
