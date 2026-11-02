# Implementation Plan: [phase6] TASK-603 补全 Quire 缺失对话框集群

## Objective
Implement all missing dialog clusters for Quire Writer in `src/atboffice/modules/writer/dialogs/`, wire them into `quire_window.py`, and test them in `tests/gui/test_writer_dialogs_phase6.py`.

## Tasks

### Task 1: Break & Page Formatting Dialogs
- Create `src/atboffice/modules/writer/dialogs/break_dialog.py`:
  - `BreakDialog`
- Create `src/atboffice/modules/writer/dialogs/page_formatting_dialogs.py`:
  - `DropCapDialog`
  - `TextDirectionDialog`
  - `WatermarkDialog`
  - `PageNumbersDialog`
  - `ChangeCaseDialog`
  - `DocumentThemeDialog`

### Task 2: Reference & Annotation Dialogs
- Create `src/atboffice/modules/writer/dialogs/reference_dialogs.py`:
  - `FootnoteDialog`
  - `CaptionDialog`
  - `CrossRefDialog`
  - `IndexTablesDialog`
  - `BookmarkDialog`
  - `HyperlinkDialog`
  - `DateTimeDialog`
  - `FieldDialog`
  - `SymbolDialog`

### Task 3: Tools & Options Dialogs
- Create `src/atboffice/modules/writer/dialogs/tools_dialogs.py`:
  - `AutoCorrectDialog`
  - `QuireOptionsDialog`
  - `CustomizeDialog`
  - `EnvelopesLabelsDialog`
  - `LetterWizardDialog`
  - `AutoSummarizeDialog`
  - `HyphenationDialog`

### Task 4: Advanced Table Dialogs
- Create `src/atboffice/modules/writer/dialogs/table_dialogs.py`:
  - `InsertCellsDialog`
  - `DeleteCellsDialog`
  - `SplitCellsDialog`
  - `TableAutoFormatDialog`
  - `TableSortDialog`
  - `TableFormulaDialog`

### Task 5: Export in `__init__.py` & Wire into `quire_window.py`
- Update `src/atboffice/modules/writer/dialogs/__init__.py` to export all new dialogs.
- Update `src/atboffice/ui/shell/quire_window.py` to add handler methods and register action handlers in `_bind_action_handlers`.

### Task 6: Test Suite & Verification
- Create `tests/gui/test_writer_dialogs_phase6.py` covering all new dialogs.
- Run tests:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_writer_dialogs_phase6.py -v
  ```
- Run full test suite to guarantee zero regressions:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/
  ```
