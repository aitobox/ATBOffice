# Implementation Plan: Issue #136 - 实现 Ledger 条件格式 (CF) 与数据有效性校验系统

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement full conditional formatting (rules, color scales, data bars) and data validation (whole, decimal, list, custom, alert dialogs, dropdowns) with full OpenXML XLSX roundtrip preservation and PySide6 UI integration.

**Architecture:** Sparse sheet data model extension in `SheetDataModel`, dedicated calculation and evaluation engines in `conditional_format.py` and `validation.py`, custom paint rendering in `GridViewport`, validation checks in `EditorController`, and OOXML read/write in `xlsx_reader.py` and `xlsx_writer.py`.

**Tech Stack:** Python 3.12+, PySide6 (Qt6), XML ElementTree, pytest.

**Spec:** `docs/superpowers/specs/issue-136-ledger-cf-validation-spec.md`

## Global Constraints
- Pure Python 3.12+ with complete type hints everywhere.
- 100% i18n support via `safe_tr()` / `tr()` and `retranslate_ui()`.
- Zero regressions across existing test suite.
- Maintain compatibility with ECMA-376 Part 1 OOXML XLSX schema.

---

### Task 1: Conditional Formatting Data Model and Evaluation Engine

**Files:**
- Create: `src/atboffice/modules/spreadsheet/models/conditional_format.py`
- Test: `tests/modules/spreadsheet/test_cf_validation.py`

- [ ] **Step 1: Write failing unit test for CF data structures and evaluation**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement `conditional_format.py` with CFRule, ColorScale, DataBar, and evaluate_cf_for_cell**
- [ ] **Step 4: Run pytest to verify pass**

---

### Task 2: Data Validation Data Model and Engine

**Files:**
- Create: `src/atboffice/modules/spreadsheet/models/validation.py`
- Test: `tests/modules/spreadsheet/test_cf_validation.py`

- [ ] **Step 1: Write failing unit test for DataValidation, get_list_items, and validate_cell_value**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement `validation.py` with validation logic for whole, decimal, list, textLength, date, custom**
- [ ] **Step 4: Run pytest to verify pass**

---

### Task 3: Integrate CF & Validation into SheetDataModel and Module Exports

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/models/sheet_model.py`
- Modify: `src/atboffice/modules/spreadsheet/models/__init__.py`
- Test: `tests/modules/spreadsheet/test_cf_validation.py`

- [ ] **Step 1: Write failing test verifying SheetDataModel has conditional_formats and data_validations**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement fields and helper methods in `sheet_model.py` and export in `models/__init__.py`**
- [ ] **Step 4: Run pytest to verify pass**

---

### Task 4: XLSX Reader and Writer Serialization for CF and Data Validation

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`
- Modify: `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- Test: `tests/modules/spreadsheet/test_cf_validation.py`

- [ ] **Step 1: Write failing test for XLSX roundtrip of conditional formatting and data validation**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement `<conditionalFormatting>` and `<dataValidations>` XML serialization in `xlsx_writer.py`**
- [ ] **Step 4: Implement XML deserialization in `xlsx_reader.py`**
- [ ] **Step 5: Run pytest to verify roundtrip test passes**

---

### Task 5: GridViewport Rendering and Dropdown Indicator Integration

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- Test: `tests/modules/spreadsheet/test_cf_validation.py`

- [ ] **Step 1: Write test for viewport cell rendering with CF background, text color, and dropdown arrow**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Integrate `evaluate_cf_for_cell` in `GridViewport.paintEvent` and draw list validation dropdown button**
- [ ] **Step 4: Run pytest to verify pass**

---

### Task 6: EditorController In-Cell Validation, Alert Dialog, and Dropdown Selection

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/views/editor_controller.py`
- Test: `tests/modules/spreadsheet/test_cf_validation.py`

- [ ] **Step 1: Write test for cell editing validation check and error rejection**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement validation check and error alert in `EditorController.finish_editing` / `commit_edit`**
- [ ] **Step 4: Run pytest to verify pass**

---

### Task 7: Classic Dialogs: ConditionalFormatDialog, DataValidationDialog, and ValidationAlertDialog

**Files:**
- Create: `src/atboffice/modules/spreadsheet/dialogs/conditional_format_dialog.py`
- Create: `src/atboffice/modules/spreadsheet/dialogs/data_validation_dialog.py`
- Modify: `src/atboffice/modules/spreadsheet/dialogs/__init__.py`
- Test: `tests/modules/spreadsheet/test_cf_validation.py`

- [ ] **Step 1: Write tests for dialog instantiation, tab setup, and property extraction**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement `ConditionalFormatDialog`, `DataValidationDialog`, and `ValidationAlertDialog` with full i18n**
- [ ] **Step 4: Run full test suite to verify 100% pass**
