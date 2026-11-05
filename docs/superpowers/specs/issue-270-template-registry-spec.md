# Design Specification: Issue #270 — TemplateRegistry & WindowManager Template Integration

## 1. Overview & Objectives
This specification designs the centralized template management subsystem (`TemplateRegistry`) for ATBOffice and connects it end-to-end with `WindowManager` and the three editor shell windows (`QuireWindow`, `LedgerWindow`, `LecternWindow`).

This is **Step 1 of 4** in the Template System Parity Epic (#269). It establishes the foundational registry, metadata data structures, window instantiation pathways, and lifecycle interfaces upon which Steps 2 (Quire 10 templates), 3 (Ledger 8 templates), and 4 (Lectern 4 templates & UI dialogs) will build.

---

## 2. Architecture & Data Structures

### 2.1 `TemplateInfo` (`src/atboffice/core/templates.py`)
A lightweight, typed dataclass representing a registered document template:
```python
from dataclasses import dataclass
from typing import Callable, Any

@dataclass
class TemplateInfo:
    id: str                                    # Unique ID: e.g. "letter", "loan", "status"
    name: str                                  # Display name: e.g. "Contemporary Letter"
    app: str                                   # Target app: "quire", "ledger", "lectern"
    category: str                              # Category: "Letters & Faxes", "Reports", etc.
    icon: str = "📄"                           # Emoji or icon identifier
    builder: Callable[[Any], Any] | None = None# Generator callback taking window or model
    description: str = ""                      # Human-readable summary
    sample_path: str | None = None             # Optional preview image / asset path
```

### 2.2 `TemplateRegistry` (`src/atboffice/core/templates.py`)
Central thread-safe singleton managing template definitions:
- **Singleton Pattern**: `get_instance()` and `reset_instance()`.
- **Registration**:
  - `register(template: TemplateInfo) -> None`
  - `unregister(template_id: str, app: str | None = None) -> bool`
  - `get(template_id: str, app: str | None = None) -> TemplateInfo | None`
  - `list_templates(app: str | None = None, category: str | None = None) -> list[TemplateInfo]`
  - `list_categories(app: str | None = None) -> list[str]`
  - `clear() -> None`
  - `register_builtin_templates() -> None`: Initializes default metadata aligning with `.vibeoffice/public/common/templates.json`:
    - **Quire (10)**: `letter`, `memo`, `fax`, `resume`, `report`, `agenda`, `minutes`, `todo`, `flyer`, `recipe`
    - **Ledger (8)**: `loan`, `expense`, `invoice`, `timecard`, `budget`, `tasks`, `shopping`, `schedule`
    - **Lectern (4)**: `status`, `meeting`, `lesson`, `event`

### 2.3 `WindowManager` Integration (`src/atboffice/core/window_manager.py`)
Enhance the three window factory methods with an optional `template_id` parameter:
```python
def open_quire(self, path: str | Path | None = None, template_id: str | None = None) -> BaseOfficeWindow: ...
def open_ledger(self, path: str | Path | None = None, template_id: str | None = None) -> BaseOfficeWindow: ...
def open_lectern(self, path: str | Path | None = None, template_id: str | None = None) -> BaseOfficeWindow: ...
```
When `template_id` is supplied:
1. Window is instantiated (with `file_path=None`).
2. Calls `win.load_template(template_id)`.
3. Registers and shows the window.

### 2.4 Document Window Lifecycle (`load_template`)
In `BaseOfficeWindow` (and specialized in `QuireWindow`, `LedgerWindow`, `LecternWindow`):
```python
def load_template(self, template_id: str) -> bool:
```
1. Checks `maybe_save_prompt()`. If the user cancels unsaved edits, aborts and returns `False`.
2. Resolves `TemplateInfo` via `TemplateRegistry.get_instance().get(template_id, app=self.app_name.lower())`.
3. If not found: logs warning, returns `False` (safe fallback to empty document without crash).
4. Sets `self.current_file_path = None` (ensures document is treated as an untitled new document).
5. Stores `self.active_template = template`.
6. Executes `template.builder(self)` if callable.
7. Sets `self.set_modified(True)` (flagged as modified/needs save).
8. Updates window title to reflect template:
   `f"{self.default_doc_name} [{safe_tr('基于模板')}: {template.name}] — {self.app_name} [*]"`
9. Returns `True`.

---

## 3. Edge Cases & Robustness Considerations
1. **Invalid / Missing Template ID**:
   - `load_template("invalid")` returns `False`, logs warning, leaves the document in a valid empty state without raising unhandled exceptions.
2. **Template Builder Exceptions**:
   - If a template builder throws, `load_template` catches `Exception`, logs the traceback via `logger.exception`, and returns `False` gracefully.
3. **Save vs Save-As Semantics**:
   - Because `current_file_path` is explicitly `None`, calling `save_file()` in the UI triggers `save_file_as()` (file dialog), preventing inadvertent overwriting of templates.
4. **App Mismatch**:
   - Requesting `open_quire(template_id="loan")` checks `template.app == "quire"` and rejects the mismatch cleanly.
5. **i18n & Internationalization**:
   - All text messages, category names, and title annotations use `safe_tr()`.
   - `retranslate_ui()` is supported.

---

## 4. Verification Plan
1. Unit tests for `TemplateRegistry`:
   - Singleton creation and reset.
   - Registering, retrieving, unregistering, filtering by app and category.
   - Built-in template initialization and coverage.
2. Integration tests for `WindowManager`:
   - `open_quire(template_id="letter")`, `open_ledger(template_id="loan")`, `open_lectern(template_id="status")`.
   - Title verification containing template reference.
   - Unsaved state (`is_modified == True`, `current_file_path is None`).
   - Invalid `template_id` fallback behavior.
3. Full test suite execution:
   ```bash
   PYTHONPATH=src conda run -n ATBOffice pytest tests/ -k "template" -v
   ```
