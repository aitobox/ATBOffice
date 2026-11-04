# Implementation Plan: Issue #261 - fix(platform): 修复 macOS 下鼠标悬停及光标设置导致 Trace/BPT trap: 5 (SIGTRAP/SIGSEGV) 崩溃

## User Review Required
No human review required. Confident >= 90% autonomous decision.

---

### Task 1: Create Unit Tests for Platform Cursors (TDD)
- **Files**: `tests/unit/test_platform_cursors.py`
- **Actions**:
  - Test cursor mapping for macOS:
    - `SizeAllCursor` -> `OpenHandCursor`
    - `WaitCursor` -> `BusyCursor`
    - Other cursors remain untouched.
  - Test cursor mapping for non-macOS (Linux/Windows):
    - `SizeAllCursor` remains `SizeAllCursor`
    - `WaitCursor` remains `WaitCursor`
  - Test input types: `Qt.CursorShape`, `QCursor`, `int`.
  - Test helper functions: `set_safe_cursor`, `safe_set_override_cursor`, `safe_restore_override_cursor`.
- **Verification Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/test_platform_cursors.py
  ```
  *(Expected to fail initially due to missing module)*

---

### Task 2: Implement Platform Cursor Adapter
- **Files**:
  - `src/atboffice/platform/__init__.py`
  - `src/atboffice/platform/cursors.py`
- **Actions**:
  - Implement `get_safe_cursor(shape, platform_name=None)`:
    - Inspect platform (`sys.platform == "darwin"` if `platform_name is None`).
    - Map `SizeAllCursor` to `OpenHandCursor`.
    - Map `WaitCursor` to `BusyCursor`.
    - Support both `Qt.CursorShape` and `QCursor`.
  - Implement `set_safe_cursor(widget, shape)`:
    - Calls `widget.setCursor(get_safe_cursor(shape))`.
  - Implement `safe_set_override_cursor(shape)` and `safe_restore_override_cursor()`.
- **Verification Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/test_platform_cursors.py
  ```
  *(Must pass 100%)*

---

### Task 3: Create GUI Regression Tests for GridViewport and ObjectLayer
- **Files**: `tests/gui/test_macos_cursor_safety.py`
- **Actions**:
  - Create test fixture for `GridViewport` and simulate mouse move over `HitZone.BORDER`.
  - Verify that the viewport's cursor shape matches `get_safe_cursor(Qt.CursorShape.SizeAllCursor)`.
  - Create test fixture for `ObjectLayer` and simulate mouse hover over `HandleType.BODY`.
  - Verify that the object layer's cursor shape matches `get_safe_cursor(Qt.CursorShape.SizeAllCursor)`.
  - Test that calling `set_safe_cursor` does not throw exceptions or segfaults.
- **Verification Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_macos_cursor_safety.py
  ```

---

### Task 4: Integrate Safe Cursors in GridViewport and ObjectLayer
- **Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `src/atboffice/modules/spreadsheet/views/object_layer.py`
- **Actions**:
  - In `grid_viewport.py`, import `get_safe_cursor` from `atboffice.platform.cursors`.
  - At line 2035 (`_drag_snapshot` for `HitZone.BORDER`), use `get_safe_cursor(Qt.CursorShape.SizeAllCursor)`.
  - At line 2086 (`HitZone.BORDER` hover), use `get_safe_cursor(Qt.CursorShape.SizeAllCursor)`.
  - In `object_layer.py`, import `get_safe_cursor` from `atboffice.platform.cursors`.
  - At line 716 (`HandleType.BODY` hover), use `get_safe_cursor(Qt.CursorShape.SizeAllCursor)`.
- **Verification Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_macos_cursor_safety.py tests/gui/test_grid_viewport.py
  ```

---

### Task 5: Full Test Suite Verification & Git Commit
- **Actions**:
  - Run full test suite:
    ```bash
    PYTHONPATH=src conda run -n ATBOffice pytest tests/
    ```
  - Verify zero regressions.
  - Commit changes to branch `agent/issue-261-fix-macos-cursor-crash`.
  - Advance state to `reviewing`.
