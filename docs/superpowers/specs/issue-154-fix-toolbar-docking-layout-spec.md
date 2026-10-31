# Specification: Issue #154 - Fix Application Window Toolbar Docking Layout

## Overview & Background
In `QuireWindow`, `LedgerWindow`, and `LecternWindow`, the drawing toolbar (`win.toolbars["drawing"]`) was previously hard-coded into `Qt.ToolBarArea.BottomToolBarArea`. Because the drawing toolbar features numerous text and dropdown actions without compact icons, docking it at the bottom created a bloated footer area that encroached upon the document viewport, sheet tab bar, and status bar.

This specification details the structural correction of the toolbar layout across all three core applications to ensure all command bars dock strictly in `Qt.ToolBarArea.TopToolBarArea` in structured rows, freeing the bottom area entirely for the status bar and native application widgets (such as Ledger's worksheet tab bar).

---

## Requirements & Scope

1. **Eliminate Bottom Toolbar Docking**:
   - Completely remove all calls to `self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, ...)` in `quire_window.py`, `ledger_window.py`, and `lectern_window.py`.
   - Ensure that zero toolbars are docked in `BottomToolBarArea`, `LeftToolBarArea`, or `RightToolBarArea` by default.

2. **Standardized Top Toolbar Row Ordering**:
   - **Row 1**: Standard Command Bar (`standard`).
   - **Row 2**: Formatting Command Bar (`formatting`).
   - **Row 3**: Drawing Command Bar (`drawing`) along with domain contextual/optional toolbars:
     - *Quire*: `tables`, `reviewing`, `outlining`, `headerFooter`, `picture`, `mailMerge`, `wordart`.
     - *Ledger*: `borders`, `auditing`, `reviewing`, `list`, `chart`.
     - *Lectern*: `outlining`, `sorter`, `master`, `diagram`, `tables`, `picture`, `wordart`.
   - Row breaks are established using `self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)` to prevent horizontal overflow and awkward stacking.

3. **Bottom Cleanliness & Preserved Subsystems**:
   - In `LedgerWindow`: Bottom area contains exclusively the worksheet tab bar (`sheet_tab_bar`) and the status bar (`statusBar()`).
   - In `QuireWindow` and `LecternWindow`: Bottom area contains exclusively the status bar.
   - No text toolbar footer exists at the bottom.

4. **Tool Button Sizing & Compact Presentation**:
   - Verify tool buttons conform to the Office 2003 Luna compact metrics (20px minimum height + padding + border converging to 26px).
   - Ensure drawing toolbar actions and dropdown menus function properly when docked on the top row.

5. **Test Assertions and Regression Suite**:
   - Update existing unit tests in `tests/ui/test_quire_toolbars.py`, `tests/ui/test_ledger_toolbars.py`, and `tests/ui/test_lectern_toolbars.py` to assert `Qt.ToolBarArea.TopToolBarArea`.
   - Implement comprehensive GUI regression test suite: `tests/gui/test_window_toolbar_docking.py` verifying docking area and bottom area cleanliness across all three windows.

---

## Edge Cases & Error Handling

- **Dynamic Visibility & Toggling**: When `tb_drawing` or other toolbar visibility is toggled on and off via menus or shortcuts, the toolbar must stay attached to `TopToolBarArea` without migrating to the bottom.
- **Contextual Show/Hide**: When contextual toolbars appear (e.g. Table, Chart, WordArt), they must remain in `TopToolBarArea`.
- **Fullscreen & Viewport Resize**: When windows are resized to minimum or maximum dimensions, top toolbars wrap cleanly or provide standard Qt overflow chevrons without disrupting the document canvas.
- **i18n Integrity**: All toolbar titles and status tips remain wrapped in `safe_tr()` / `core_safe_tr()`.

---

## Verification Plan

```bash
PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_window_toolbar_docking.py -v
PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_quire_toolbars.py tests/ui/test_ledger_toolbars.py tests/ui/test_lectern_toolbars.py -v
```
