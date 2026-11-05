# Implementation Plan: Issue #270 — TemplateRegistry & WindowManager Template Integration

## Task List

- [ ] **Task 1: Test-Driven Unit Tests for `TemplateRegistry`**
  - File: `tests/test_template_registry.py`
  - Coverage:
    - `TemplateInfo` dataclass instantiation and fields.
    - `TemplateRegistry` singleton access, `reset_instance()`, `clear()`.
    - Custom template registration, lookup by id and app filter.
    - Category listing and template filtering by category/app.
    - Built-in templates verification: 10 Quire, 8 Ledger, 4 Lectern templates exist and have non-empty names.
    - Fallback behavior on non-existent templates.

- [ ] **Task 2: Implement `src/atboffice/core/templates.py`**
  - File: `src/atboffice/core/templates.py`
  - Implementation:
    - `TemplateInfo` dataclass with full typing.
    - `TemplateRegistry` with thread-safe singleton, dict-based index by `(app, id)` and `id`.
    - `register_builtin_templates()` declaring the 22 canonical templates from `.vibeoffice/public/common/templates.json`.
    - `safe_tr` i18n support for category and template names.
  - Verification: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_template_registry.py -v`

- [ ] **Task 3: Integrate `load_template` into Office Shell Windows**
  - Files:
    - `src/atboffice/ui/shell/base_window.py`
    - `src/atboffice/ui/shell/quire_window.py`
    - `src/atboffice/ui/shell/ledger_window.py`
    - `src/atboffice/ui/shell/lectern_window.py`
  - Implementation:
    - Add `self.active_template: TemplateInfo | None = None` to `BaseOfficeWindow`.
    - Implement `load_template(template_id: str) -> bool`:
      - Handles `maybe_save_prompt()`.
      - Resolves template from `TemplateRegistry`.
      - Catches builder errors gracefully.
      - Sets `current_file_path = None`, `set_modified(True)`.
      - Updates window title to `f"{self.default_doc_name} [{safe_tr('基于模板')}: {template.name}] — {self.app_name} [*]"`.
    - In `QuireWindow`: resets document model and synchronizes text/caret.
    - In `LedgerWindow`: resets active sheet and updates grid view.
    - In `LecternWindow`: refreshes slide list and current slide view.
  - Verification: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_window_templates.py -v`

- [ ] **Task 4: Update `WindowManager` Factory Methods**
  - File: `src/atboffice/core/window_manager.py`
  - Implementation:
    - Update signature of `open_quire`, `open_ledger`, `open_lectern` to accept `template_id: str | None = None`.
    - If `template_id` provided, invoke `win.load_template(template_id)` before showing window.
    - Add `open_template(template_id: str, app: str | None = None) -> BaseOfficeWindow` convenience helper.
  - Verification: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_window_manager_templates.py -v`

- [ ] **Task 5: Full Test Suite Verification**
  - Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -k "template" -v`
  - Run full suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/`
  - Ensure all tests pass with 0 regressions.
