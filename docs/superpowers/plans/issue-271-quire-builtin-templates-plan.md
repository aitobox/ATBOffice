# Implementation Plan: Quire Built-in Document Templates (Issue #271)

## Overview
Implement 10 built-in document templates for Quire matching `.vibeoffice/public/quire/js/templates.js`, integrate with `TemplateRegistry` and `QuireWindow`, and verify thoroughly with comprehensive test coverage.

---

### Task 1: Models & Properties Foundation
- **Target Files**:
  - `src/atboffice/modules/writer/models/properties.py`
  - `src/atboffice/modules/writer/models/document.py`
- **Actions**:
  - Add `borders: dict[str, Any] = field(default_factory=dict)` to `ParagraphProperties` for paragraph-level border lines.
  - Export `DocumentModel = Document` in `document.py`.
- **Verification**:
  - Import `ParagraphProperties` and verify `borders` field defaults to `{}`.

---

### Task 2: TDD Test Suite Creation
- **Target File**:
  - `tests/test_quire_templates.py`
- **Actions**:
  - Test `build_quire_template(tid)` for all 10 template IDs (`letter`, `memo`, `fax`, `resume`, `report`, `agenda`, `minutes`, `todo`, `flyer`, `recipe`).
  - Assert document metadata (`props["template"]`).
  - Assert presence of custom styles and properties (e.g. `MemoTitle`, `FaxLabel`, `AgendaTitle`, etc.).
  - Assert table structure for templates with tables (`fax`, `agenda`, `minutes`, `recipe`).
  - Assert list numbering definitions for `resume`, `minutes`, and `recipe`.
  - Assert date fields and macrobutton placeholders.
  - Test unknown template ID handling.
  - Test `TemplateRegistry` integration: templates have active builders returning `Document`.
  - Test `QuireWindow.load_template(tid)` updates canvas view document and window title.
- **Verification**:
  - Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_quire_templates.py` (confirm fails initially before implementation).

---

### Task 3: Core Quire Templates Implementation
- **Target File**:
  - `src/atboffice/modules/writer/templates.py`
- **Actions**:
  - Implement helper functions:
    - `placeholder(label, r_pr)` -> list of RunItems (fb, fs, text, fe)
    - `date_field(fmt, r_pr)` -> list of RunItems with current formatted date
    - `simple_table(rows, widths, header_fill, p_style)` -> Table with formatted cells
    - `make_bullet_abs(...)`, `make_number_abs(...)`, and `add_num(...)`
  - Implement all 10 template builders:
    - `build_letter_template(doc)`
    - `build_memo_template(doc)`
    - `build_fax_template(doc)`
    - `build_resume_template(doc)`
    - `build_report_template(doc)`
    - `build_agenda_template(doc)`
    - `build_minutes_template(doc)`
    - `build_todo_template(doc)`
    - `build_flyer_template(doc)`
    - `build_recipe_template(doc)`
  - Implement `build_quire_template(template_id: str) -> Document`.
  - Implement `register_quire_templates(registry: TemplateRegistry | None = None)`.

---

### Task 4: TemplateRegistry & QuireWindow Integration
- **Target Files**:
  - `src/atboffice/core/templates.py`
  - `src/atboffice/ui/shell/quire_window.py`
- **Actions**:
  - In `TemplateRegistry.register_builtin_templates()`, bind the builder callbacks for the 10 Quire templates to `build_quire_template`.
  - In `QuireWindow`, implement `_apply_template_result(self, result: Any) -> None` to update canvas view document.
  - In `QuireWindow`, implement `new_file(self) -> bool` to reset canvas with a fresh blank `Document`.

---

### Task 5: Comprehensive Verification & Regression Testing
- **Actions**:
  - Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_quire_templates.py -v`
  - Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_template_registry.py tests/test_window_templates.py -v`
  - Run full test suite to guarantee 0 regressions.
