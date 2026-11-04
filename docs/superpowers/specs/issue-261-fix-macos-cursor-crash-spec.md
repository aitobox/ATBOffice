# Specification: Issue #261 - fix(platform): 修复 macOS 下鼠标悬停及光标设置导致 Trace/BPT trap: 5 (SIGTRAP/SIGSEGV) 崩溃

## 1. Overview & Problem Statement
On macOS (Apple Silicon / Darwin) running PySide6 6.11.1 and Cocoa (`libqcocoa`), setting specific system cursor shapes—specifically `Qt.CursorShape.SizeAllCursor` and `Qt.CursorShape.WaitCursor`—causes native Cocoa event handling crashes:
- `Trace/BPT trap: 5` (SIGTRAP, exit code -5 / 133)
- `Segmentation fault: 11` (SIGSEGV, exit code 139)

This crash is readily triggered in the Spreadsheet module (Ledger) during normal user interaction:
- Hovering over a cell selection border (`HitZone.BORDER`), which invokes `setCursor(Qt.CursorShape.SizeAllCursor)` in `GridViewport.mouseMoveEvent` (line 2086).
- Grabbing a selection border to initiate range dragging (line 2035).
- Hovering over canvas objects / shapes (`HandleType.BODY`) in `ObjectLayer.mouseMoveEvent` (line 716).

Real-device testing on macOS confirms that while `SizeAllCursor` and `WaitCursor` trigger Cocoa faults, `OpenHandCursor`, `ClosedHandCursor`, `PointingHandCursor`, `SplitHCursor`, `SplitVCursor`, and `BusyCursor` are completely stable and render without faults.

## 2. Requirements & Acceptance Criteria
1. **Platform Cursor Adapter Module (`src/atboffice/platform/cursors.py`)**:
   - Provide `get_safe_cursor(shape: Qt.CursorShape | QCursor, platform_name: str | None = None) -> Qt.CursorShape | QCursor`.
   - On macOS (`platform_name == "darwin"` or `sys.platform == "darwin"`):
     - Maps `Qt.CursorShape.SizeAllCursor` to `Qt.CursorShape.OpenHandCursor`.
     - Maps `Qt.CursorShape.WaitCursor` to `Qt.CursorShape.BusyCursor`.
     - Preserves all other cursor shapes unaltered.
   - On other platforms (Windows, Linux):
     - Returns the requested cursor shape without alterations.
   - Handles both `Qt.CursorShape` enums and `QCursor` instances safely.
   - Provide helper functions:
     - `set_safe_cursor(target: Any, shape: Qt.CursorShape | QCursor) -> None`
     - `safe_set_override_cursor(shape: Qt.CursorShape | QCursor) -> None`
     - `safe_restore_override_cursor() -> None`
2. **Update GridViewport & ObjectLayer**:
   - In `src/atboffice/modules/spreadsheet/views/grid_viewport.py`:
     - Replace direct calls to `Qt.CursorShape.SizeAllCursor` with `get_safe_cursor(Qt.CursorShape.SizeAllCursor)` or `set_safe_cursor`.
   - In `src/atboffice/modules/spreadsheet/views/object_layer.py`:
     - Replace direct calls to `Qt.CursorShape.SizeAllCursor` with `get_safe_cursor(Qt.CursorShape.SizeAllCursor)` or `set_safe_cursor`.
3. **Comprehensive Automated Tests**:
   - Unit tests (`tests/unit/test_platform_cursors.py`):
     - Test cursor mapping logic on darwin vs non-darwin.
     - Test mapping with `Qt.CursorShape` enums, `QCursor` instances, and edge cases.
     - Test helper functions `set_safe_cursor`, `safe_set_override_cursor`.
   - GUI tests (`tests/gui/test_macos_cursor_safety.py`):
     - Simulate mouse hover over `HitZone.BORDER` in `GridViewport` and assert cursor shape is safe (e.g. `OpenHandCursor` on macOS).
     - Simulate mouse hover over `HandleType.BODY` in `ObjectLayer` and assert cursor shape is safe.
     - Verify no exceptions or segmentation faults occur during repeated mouse movements.
4. **Zero Regressions**:
   - All existing test suites pass.

## 3. Architecture & Target Files
| File | Action | Purpose |
|---|---|---|
| `src/atboffice/platform/__init__.py` | Create | Package initialization for platform glue. |
| `src/atboffice/platform/cursors.py` | Create | Platform-safe cursor mapping and helper utilities. |
| `src/atboffice/modules/spreadsheet/views/grid_viewport.py` | Modify | Use `get_safe_cursor` for border hover and drag. |
| `src/atboffice/modules/spreadsheet/views/object_layer.py` | Modify | Use `get_safe_cursor` for body hover. |
| `tests/unit/test_platform_cursors.py` | Create | Unit test coverage for cursor platform adaptation. |
| `tests/gui/test_macos_cursor_safety.py` | Create | GUI tests for safe cursor application in GridViewport and ObjectLayer. |
