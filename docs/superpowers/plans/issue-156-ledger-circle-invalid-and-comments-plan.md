# Implementation Plan: Ledger 数据有效性红圈圈释 (circle_invalid) 与单元格批注角标

## Task 1: Sheet Model Extension (Comments & Invalid Circles)
- **Target Files**: `src/atboffice/modules/spreadsheet/models/sheet_model.py`
- **Actions**:
  - Add `CellComment` dataclass (`text`, `author`, `visible`).
  - Add `self.comments: dict[tuple[int, int], CellComment] = {}`.
  - Add `self.invalid_circles: list[tuple[int, int]] = []`.
  - Add `self.show_all_comments: bool = False`.
  - Add helper methods: `set_comment`, `get_comment`, `delete_comment`, `has_comment`.
- **Verification**: Unit tests in `tests/modules/spreadsheet/test_cf_validation.py`.

## Task 2: Comment Dialog Implementation
- **Target Files**:
  - `src/atboffice/modules/spreadsheet/dialogs/comment_dialog.py`
  - `src/atboffice/modules/spreadsheet/dialogs/__init__.py`
- **Actions**:
  - Create `CommentDialog(existing_text, author, parent)`.
  - Add form layout with Author display and QTextEdit for comment text.
  - Add standard OK / Cancel button box.
  - Implement full i18n via `safe_tr()`.
- **Verification**: QtBot dialog test in `tests/modules/spreadsheet/test_cf_validation.py`.

## Task 3: Grid Viewport Rendering & Interaction
- **Target Files**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **Actions**:
  - In `paintEvent()`:
    - Draw invalid circles: red ellipses around cells in `self.model.invalid_circles`.
    - Draw comment corner indicators: small red triangle at the top-right of cells that have comments.
    - Draw visible comments: yellow callout note (`#FFFFE1`) with connector line for visible comments.
  - In `mouseMoveEvent()`:
    - Check if hovered cell has a comment; if so, show `QToolTip`.
    - If moved off comment cell, hide `QToolTip`.
- **Verification**: QtBot render test in `tests/modules/spreadsheet/test_cf_validation.py`.

## Task 4: Ledger Window Actions Integration
- **Target Files**: `src/atboffice/ui/shell/ledger_window.py`
- **Actions**:
  - Implement `data_validation()`: open `DataValidationDialog`, load existing rule if any, save new rule to `sheet.add_data_validation(dv)`.
  - Implement `circle_invalid()`: iterate sheet rules, validate cells using `validate_cell_value()`, populate `sheet.invalid_circles` up to 255 cells, trigger update.
  - Implement `clear_circles()`: empty `sheet.invalid_circles`, trigger update.
  - Implement `insert_comment()`: open `CommentDialog` for active cell, save comment.
  - Implement `show_hide_comment()`: toggle `cm.visible` for active cell comment.
  - Implement `delete_comment()`: delete comment on active cell.
  - Implement `toggle_show_all_comments()`: toggle `sheet.show_all_comments`.
- **Verification**: Integration tests in `tests/modules/spreadsheet/test_cf_validation.py`.

## Task 5: Full Test Suite Verification
- **Actions**:
  - Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_cf_validation.py -v`.
  - Run full test suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/`.
