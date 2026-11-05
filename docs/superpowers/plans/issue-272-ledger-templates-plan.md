# Implementation Plan: Issue #272 - Align .vibeoffice to Implement 8 Ledger Spreadsheet Templates

- **Issue**: [#272](https://github.com/aitobox/ATBOffice/issues/272)
- **Branch**: `agent/issue-272-ledger-templates`
- **Spec**: `docs/superpowers/specs/issue-272-ledger-templates-spec.md`

---

## Task Breakdown & Steps

### Task 1: Create `src/atboffice/modules/spreadsheet/templates/base.py`
- Define styling constants matching `.vibeoffice`:
  - `B`: Bold text
  - `HDR`: Header row (white bold text `#FFFFFF`, blue fill `#336699`, centered, wrap)
  - `TITLE`: Main title (sz 16, bold, `#1F3F7F`)
  - `MONEY`: Currency format `"$#,##0.00"`
  - `BOX`: Thin gray `#808080` border on all 4 sides
  - `INPUT`: Soft yellow fill `#FFFFCC`, unlocked (`locked=False`)
- Define helper function `build_sheet_from_spec(spec: dict, workbook: WorkbookModel) -> SheetDataModel`:
  - Parses cell coordinates (`parse_cell`), sets formulas and values.
  - Applies styling deltas / attributes (`CellData`).
  - Sets custom column widths (`sheet.geometry.set_col_width(c, int(w * 8))`).
  - Sets freeze panes (`sheet.freeze_rows`, `sheet.freeze_cols`).
  - Sets cell merges (`sheet.add_merge`).
  - Sets data validations (`sheet.add_data_validation`).
  - Records initial selection and grid visibility in `sheet.extra`.

### Task 2: Create `src/atboffice/modules/spreadsheet/templates/builders.py`
- Implement 8 template specs corresponding to `.vibeoffice/public/ledger/js/panes.js`:
  1. `build_loan_spec()` -> `loan`
  2. `build_expense_spec()` -> `expense`
  3. `build_invoice_spec()` -> `invoice`
  4. `build_timecard_spec()` -> `timecard`
  5. `build_budget_spec()` -> `budget`
  6. `build_tasks_spec()` -> `tasks`
  7. `build_shopping_spec()` -> `shopping`
  8. `build_schedule_spec()` -> `schedule`

### Task 3: Create `src/atboffice/modules/spreadsheet/templates/__init__.py`
- Expose `LEDGER_TEMPLATE_IDS`, `LEDGER_TEMPLATE_NAMES`.
- Implement `build_ledger_template(template_id: str) -> WorkbookModel`:
  - Creates `WorkbookModel()`.
  - Replaces default blank sheet with template sheet.
  - Runs `wb.recalculate()` to pre-calculate all initial formula values.
  - Sets `wb.dirty = False`.
- Implement `register_ledger_templates(registry: TemplateRegistry | None = None) -> None`:
  - Attaches `builder` lambda to registered ledger templates.

### Task 4: Connect `TemplateRegistry` & `LedgerWindow`
- In `src/atboffice/core/templates.py`:
  - In `TemplateRegistry.register_builtin_templates()`, import `build_ledger_template` and set `builder=lambda win=None, target_id=tid: build_ledger_template(target_id)`.
- In `src/atboffice/ui/shell/ledger_window.py`:
  - Implement `_apply_template_result(self, result: Any) -> None` to set `self.spreadsheet_view.workbook = result`.
  - Override `new_file(self) -> bool` to reset with a new `WorkbookModel`.

### Task 5: Write Automated Tests in `tests/test_ledger_templates.py`
- Verify `LEDGER_TEMPLATE_IDS` contains all 8 items.
- Verify `build_ledger_template(invalid)` raises `KeyError`.
- Verify all 8 templates build valid `WorkbookModel` instances with sheets, columns, and cells.
- Verify formula evaluations:
  - `loan`: Scheduled payment in `G3`, formula `=IF(C3*C4*C5*C6>0,-PMT(C4/C6,C5*C6,C3),"")` evaluated to around `489.15`.
  - `timecard`: regular / overtime calculation and total hours.
  - `budget`: sums in income/expenses rows.
  - `tasks`: countifs formulas.
- Verify `LedgerWindow.load_template(template_id)` loads template into the window and sets window title `[基于模板: ...]`.

### Task 6: Run Full Test Suite & Verification
```bash
PYTHONPATH=src conda run -n ATBOffice pytest tests/test_ledger_templates.py -v
```
