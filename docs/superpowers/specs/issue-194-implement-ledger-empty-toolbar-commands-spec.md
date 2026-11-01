# Specification: [Phase 5] 实现 Ledger 已注册的空工具栏命令

## 1. Overview & Context

- **Issue**: [#194](https://github.com/aitobox/ATBOffice/issues/194) - `[Phase 5] 实现 Ledger 已注册的空工具栏命令`
- **Parent Epic**: #188 (Phase 5 parity, interaction and stability)
- **Reference**:
  - `.vibeoffice/public/ledger/js/commands.js` (lines 68, 122–123, 144, 172, 228)
  - `.vibeoffice/public/ledger/js/app.js` (lines 1050–1065, 1114–1134)
  - `.vibeoffice/public/ledger/js/ops.js` (lines 388–420 `paintFormats`)
  - `.vibeoffice/public/ledger/js/dialogs.js` (lines 938–980 `D.hyperlink`)
  - `.vibeoffice/public/ledger/js/drawing.js` (lines 423–460 `DR.format`)
  - `.vibeoffice/public/common/ui.js` (lines 784–825 `ui.brush`)
- **Target Files**:
  - `src/atboffice/ui/shell/ledger_window.py`
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `src/atboffice/modules/spreadsheet/dialogs/hyperlink_dialog.py` (new)
  - `src/atboffice/modules/spreadsheet/dialogs/format_object_dialog.py` (new)
  - `tests/ui/test_ledger_toolbar_wiring.py`
  - `docs/clone/CLONE_DIFF.md`
  - `src/atboffice/resources/locale/*.json` (7 languages)

---

## 2. Requirements & Parity Analysis

| Toolbar Command | Original (`.vibeoffice`) Behavior | Current Python Port Status | Target Parity Implementation |
|---|---|---|---|
| **`formatPainter`** (格式刷) | `commands.js:172`, `app.js:1050`, `ops.js:388`: Picks source format on click; single-click applies once then deactivates; double-click stays sticky across multiple selections; copies font, borders, fill, align, format code, and relative merges; cancel/Esc drops painter without altering cells; supports undo/redo. | Method in `ledger_window.py` contains only a docstring. No active brush state, cursor feedback, or paste logic. | Implement `FormatPainter` state machine in `LedgerWindow` and `GridViewport`. Copy formatting attributes without changing values/formulas. Support single-click and double-click sticky mode, cancel on Esc/re-click, and record in `_undo_stack`. |
| **`hyperlink`** (插入超链接) | `commands.js:122`, `dialogs.js:938`: Opens dialog with 3 modes (Web/File, Place in Document, Email), text to display, screen tip. If editing existing link, provides "Remove Link". Applies blue underline hyperlink style and records link in `model.links`. Cancel preserves cell data; supports undo/redo. | `insert_hyperlink` in `ledger_window.py` is a docstring only. `grid_viewport.py` has a minimal `QInputDialog` fallback. | Implement comprehensive `HyperlinkDialog` with Web, Place in Document, and Mail tabs. Add/update/remove links in `model.links`, apply/revert hyperlink style, support undo/redo, and ensure Cancel makes zero modifications. |
| **`totalRow`** (汇总行) | `commands.js:228`, `app.js:1115`: Context-enabled when table/data list exists; checked if total row is active. Toggling appends summary row with "Total" label and `SUBTOTAL`/`SUM` formulas with top/double-bottom borders; unchecking removes summary row and clears cells. Cancel/undo restores state. | Method in `ledger_window.py` is a docstring only; `convert_table_to_range` has an inactive stub. | Detect active table or auto-filter data region; toggle summary row with `Total` label and `SUM`/`SUBTOTAL` formulas and accounting borders; update checked state; integrate with `convert_table_to_range`; record in `_undo_stack`; disable if no data region exists. |
| **`formatObject`** (设置对象格式) | `commands.js:144`, `drawing.js:423`: Context-enabled ONLY when a floating object (shape, image, chart, textbox) is selected. Opens tabbed dialog for Colors/Lines (fill, line color/weight), Size (width, height, aspect ratio), Properties (move/size with cells, alt text). Cancel makes no changes; OK updates object attributes and records undo. | Method in `ledger_window.py` is a docstring only. Action is not dynamically disabled when no object is selected. | Connect `object_layer.object_selected` signal to dynamically enable/disable `formatObject` action. Implement `FormatObjectDialog` with Fill, Line, Size, and Properties tabs. Cancel leaves object unchanged; OK commits properties and triggers repaint. |

---

## 3. Detailed Technical Architecture & Edge Cases

### 3.1. Format Painter (`formatPainter`)
1. **State Management**:
   - `_format_painter_active: bool = False`
   - `_format_painter_sticky: bool = False`
   - `_format_painter_source: dict[str, Any] | None = None` (stores source cell style snapshot and bounding dimensions)
2. **Action Triggering**:
   - When user clicks `formatPainter` action:
     - If already active: deactivate and reset cursor and action checked state.
     - If not active:
       - Sample primary range active cell from `selection`.
       - Copy style properties: `font_family`, `font_size`, `bold`, `italic`, `underline`, `underline_style`, `strike`, `fg_color`, `bg_color`, `align_h`, `align_v`, `indent`, `wrap_text`, `format_code`, `borders`, `pattern`, `pattern_color`.
       - Set `_format_painter_active = True`.
       - Set `_format_painter_sticky = is_double_click`.
       - Set `action_registry.set_checked("formatPainter", True)`.
       - Set grid cursor to `Qt.PointingHandCursor` and show status message.
3. **Application & Cancellation**:
   - When user selects or drags over target cells in `GridViewport`:
     - If `_format_painter_active`:
       - Record `before_cells` in undo stack.
       - Apply copied style attributes to target cells (leaving `value` and `formula` untouched).
       - Record `after_cells` in undo stack.
       - If not `_format_painter_sticky`: deactivate painter immediately.
   - On pressing Escape or toggling button off: cancel painter immediately without modifying any cell.
   - Undo/Redo: Undoing restores target cells' prior styling cleanly.

### 3.2. Hyperlink (`hyperlink`)
1. **Dialog (`HyperlinkDialog`)**:
   - Model inspection: Check if active cell `(r, c)` contains an existing link in `model.links`.
   - Fields:
     - `text_edit`: Display text (defaults to cell's text/value or link display).
     - `tab_widget`:
       - Tab 1: Web / File URL (address line edit, placeholder `https://`, auto-prepends `http://` if `www.` typed).
       - Tab 2: Place in This Document (combo box of sheets in workbook + cell reference edit e.g. `A1`).
       - Tab 3: Email (email address + subject line edit).
     - `tooltip_edit`: ScreenTip.
     - Buttons: `OK`, `Cancel`, `Remove Link` (shown only if existing link).
2. **Execution**:
   - If `Cancel`: dialog closes with `QDialog.Rejected`, no cell or links modified.
   - If `Remove Link`:
     - Removes link entry for `(r, c)` from `model.links`.
     - Reverts cell font style (clears underline and default blue color).
     - Records undo command.
   - If `OK`:
     - Formats target URL / location string.
     - Updates cell value to display text if cell was empty or value changed.
     - Adds or replaces link entry in `model.links`.
     - Applies hyperlink styling (underline, blue text `#0000FF`).
     - Records undo command.

### 3.3. Total Row (`totalRow`)
1. **Context & Enablement**:
   - Enabled when active worksheet has an active table, auto-filter, or non-empty rectangular data region around active cell.
   - Disabled when active sheet is empty or no valid data region can be resolved.
2. **Toggle Behavior**:
   - When toggled ON:
     - Determines data bounds `(r1, c1, r2, c2)` from active table or auto-filter or data cluster.
     - Row `r_total = r2 + 1`.
     - Column `c1`: sets label `safe_tr("汇总")` (or "Total").
     - Column `c2` (and numeric columns): sets formula `=SUBTOTAL(109, ...)` or `=SUM(...)`.
     - Sets cell styling: bold font, top border thin, bottom border double.
     - Sets `_total_row_active = True`, `_total_row_range = (r1, c1, r_total, c2)`.
     - Sets action checked state to `True`.
     - Records undo command.
   - When toggled OFF:
     - Removes summary row cells at `r_total`.
     - Sets `_total_row_active = False`.
     - Sets action checked state to `False`.
     - Records undo command.
   - In `convert_table_to_range`: if `_total_row_active`, removes summary row and resets action checked state to `False`.

### 3.4. Format Object (`formatObject`)
1. **Context & Enablement**:
   - Connects to `SpreadsheetObjectLayer.object_selected` signal.
   - When `selected_object is None`: `action_registry.get_action("formatObject").setEnabled(False)`.
   - When `selected_object is not None`: `action_registry.get_action("formatObject").setEnabled(True)`.
2. **Dialog (`FormatObjectDialog`)**:
   - Opens for the selected `FloatingObject`.
   - Tabs:
     - **Colors and Lines**: Fill color, fill transparency, Line color, Line width.
     - **Size**: Width, Height, Lock aspect ratio.
     - **Properties**: Positioning mode (`twoCell`, `oneCell`, `absolute`), Alt text / description.
   - If `Cancel`: object remains completely untouched.
   - If `OK`: updates object attributes, requests layer repaint, sets window modified flag, records undo command.

---

## 4. Verification & Testing Strategy

1. **Unit & Integration Tests in `tests/ui/test_ledger_toolbar_wiring.py`**:
   - `test_format_painter_single_and_sticky_application`:
     - Set source cell A1 with bold, red fill, border. Set target cell B1 with value "Target".
     - Trigger `formatPainter`. Apply to B1. Verify B1 receives style without changing value "Target".
     - Verify painter deactivates after single application.
     - Verify double-click / sticky mode applies across multiple targets.
     - Verify undo/redo reverts formatting without altering value.
     - Verify cancel/Escape leaves cells untouched.
   - `test_hyperlink_insert_edit_and_remove`:
     - Test inserting hyperlink into empty cell and cell with existing text.
     - Verify `model.links` contains link record and cell text is updated and styled blue/underline.
     - Test cancel leaves model untouched.
     - Test editing existing link and clicking "Remove Link" removes link and resets style.
     - Test undo/redo.
   - `test_total_row_toggle_and_context`:
     - Test in empty sheet: `totalRow` action is disabled or gracefully handled.
     - Populate data rows A1:B3. Trigger `totalRow`.
     - Verify row 4 has "Total" in col 0 and SUM/SUBTOTAL in col 1, with double bottom border.
     - Verify toggle off removes row 4.
     - Verify `convertToRange` resets `totalRow`.
     - Verify undo/redo.
   - `test_format_object_context_enablement_and_dialog`:
     - Verify `formatObject` is disabled when no object is selected.
     - Add floating shape and select it: verify `formatObject` becomes enabled.
     - Trigger `formatObject`, apply property changes (fill color, width). Verify object updated.
     - Test cancel leaves object untouched.
     - Deselect object: verify `formatObject` becomes disabled again.
2. **Full Regression Suite**:
   - Run full test suite with `pytest`.
   - Verify all 7 language strings exist and load without warnings.
