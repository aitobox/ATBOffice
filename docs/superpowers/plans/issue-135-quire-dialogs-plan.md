# Implementation Plan: Issue #135 - 补齐 Quire 表格属性、边框底纹、分栏与制表位对话框

## Summary
Implement 5 classic Office 2003 / Quire modal dialogs in `src/atboffice/modules/writer/dialogs/` with PySide6, complete i18n (`safe_tr`), edge case handling, and thorough test coverage in `tests/modules/writer/test_writer_dialogs.py`.

---

## Tasks

### Task 1: Comprehensive Test Suite Setup (TDD Red Phase)
- **File**: `tests/modules/writer/test_writer_dialogs.py`
- **Details**:
  - Test `InsertTableDialog`: dimensions, autofit modes, constraints, return values, retranslate_ui.
  - Test `TabsDialog`: add tab, clear tab, clear all, default tab change, alignment and leader options, retranslate_ui.
  - Test `BordersShadingDialog`: setting presets (none, box, all, grid, custom), line styles, colors, shading fills, patterns, retranslate_ui.
  - Test `ColumnsDialog`: presets (1, 2, 3, left, right), equal width toggle, spacing adjustments, line between, retranslate_ui.
  - Test `TablePropertiesDialog`: 4 tabs (Table, Row, Column, Cell), applying to Table instance, options modal dialogs, retranslate_ui.

### Task 2: Implement `InsertTableDialog`
- **File**: `src/atboffice/modules/writer/dialogs/insert_table.py`
- **Details**:
  - Columns & rows spinboxes with limits.
  - AutoFit radio group (fixed, contents, window).
  - Fixed width spinbox.
  - `get_dimensions()` method.
  - `retranslate_ui()`.

### Task 3: Implement `TabsDialog`
- **File**: `src/atboffice/modules/writer/dialogs/tabs_dialog.py`
- **Details**:
  - Position line edit and sorted list widget.
  - Default tab stops spinbox.
  - Alignment radio buttons (Left, Center, Right, Decimal, Bar).
  - Leader radio buttons (None, Dot, Hyphen, Underscore).
  - Set, Clear, Clear All buttons.
  - `get_tabs()` and `get_default_tab()` methods.
  - `retranslate_ui()`.

### Task 4: Implement `BordersShadingDialog`
- **File**: `src/atboffice/modules/writer/dialogs/borders_shading.py`
- **Details**:
  - Borders tab: Presets, style list, color picker, width combo, interactive preview widget.
  - Page Border tab: Section border options.
  - Shading tab: Fill palette, patterns combo, pattern color, preview widget.
  - `get_properties()` method.
  - `retranslate_ui()`.

### Task 5: Implement `ColumnsDialog`
- **File**: `src/atboffice/modules/writer/dialogs/columns_dialog.py`
- **Details**:
  - Presets buttons (One, Two, Three, Left, Right).
  - Columns spinbox, line between checkbox.
  - Dynamic column width/spacing table with equal width sync.
  - `ColumnsPreviewWidget` drawing preview.
  - `get_columns()` and `get_apply_to()` methods.
  - `retranslate_ui()`.

### Task 6: Implement `TablePropertiesDialog`
- **File**: `src/atboffice/modules/writer/dialogs/table_properties.py`
- **Details**:
  - Table tab: Preferred width, alignment, indent, options dialog, borders/shading dialog link.
  - Row tab: Specify height, cantSplit, repeat header.
  - Column tab: Preferred width.
  - Cell tab: Preferred width, vertical alignment (Top, Center, Bottom), cell options dialog.
  - `apply_to_table(table: Table)` and `get_properties()` methods.
  - `retranslate_ui()`.

### Task 7: Update `__init__.py`
- **File**: `src/atboffice/modules/writer/dialogs/__init__.py`
- **Details**:
  - Export `TablePropertiesDialog`, `InsertTableDialog`, `BordersShadingDialog`, `TabsDialog`, `ColumnsDialog`.

### Task 8: Verification & Regression Testing
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/writer/test_writer_dialogs.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_writer_dialogs.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/`
