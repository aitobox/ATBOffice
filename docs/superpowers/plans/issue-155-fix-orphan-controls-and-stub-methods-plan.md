# Implementation Plan: Issue #155 (TASK-401)
## 修复孤儿无信号控件并规范基类窗口虚方法接口

### Task 1: TDD Reproduction and Regression Test Suite
- **File**: `tests/test_orphan_stubs.py`
- **Actions**:
  - Write test `test_paragraph_dialog_tabs_button_click()` to verify `btn_tabs` launches `TabsDialog` and synchronizes tabs.
  - Write test `test_bullets_numbering_customize_dialog()` to verify `btn_customize` launches `CustomizeListDialog` and preserves level customizations.
  - Write test `test_review_toolbar_wiring_and_i18n()` to verify `ReviewToolbar` button text translations, `markup_filter_changed` signal, and `WriterView` review actions.
  - Write test `test_animation_pane_add_effect_menu()` to verify `btn_add_effect` menu popup and category action triggers.
  - Write test `test_lectern_task_pane_title_button()` to verify `title_button` interaction.
  - Write test `test_base_office_window_methods()` to verify standardized dispatching of `undo`, `redo`, `cut`, `copy`, `paste`, `zoom` and printer rendering.
  - Write test `test_search_adapter_interface()` to verify `SearchAdapter` compliance.

### Task 2: Fix ParagraphDialog Tab Stops Wiring
- **File**: `src/atboffice/modules/writer/dialogs/paragraph_dialog.py`
- **Actions**:
  - Connect `self.btn_tabs.clicked.connect(self._on_tabs_clicked)`.
  - Implement `_on_tabs_clicked(self) -> None`:
    - Open `TabsDialog(parent=self, tabs=self.props.tabs)`.
    - Upon accept, update `self.props.tabs` with `dlg.get_tabs()`.
    - Trigger preview `self._trigger_preview()`.
  - Ensure `get_properties()` returns `res.tabs = list(self.props.tabs)`.

### Task 3: Implement CustomizeListDialog and Wire BulletsNumberingDialog
- **Files**:
  - `src/atboffice/modules/writer/dialogs/customize_list_dialog.py` (New file)
  - `src/atboffice/modules/writer/dialogs/bullets_numbering.py`
  - `src/atboffice/modules/writer/dialogs/__init__.py`
- **Actions**:
  - Create `CustomizeListDialog` replicating Word 2003 list customization (level selection 1-9, number format, start at, alignment, indents, live preview, `retranslate_ui`).
  - In `BulletsNumberingDialog`, connect `self.btn_customize.clicked.connect(self._on_customize_clicked)`.
  - Implement `_on_customize_clicked(self) -> None` to launch `CustomizeListDialog` and store custom configuration.
  - Export `CustomizeListDialog` in `src/atboffice/modules/writer/dialogs/__init__.py`.

### Task 4: Enhance ReviewToolbar Localization and Wire Document Review Actions
- **Files**:
  - `src/atboffice/modules/writer/views/review_pane.py`
  - `src/atboffice/modules/writer/view.py`
- **Actions**:
  - In `ReviewToolbar`:
    - Translate all strings (menu items, tooltips, action text) using `safe_tr()`.
    - Add signal `markup_filter_changed = Signal(bool, bool, bool)`.
    - Connect `act_show_comments`, `act_show_ins_del`, `act_show_formatting` toggled signals.
  - In `ReviewPane`:
    - Implement `set_markup_filter(self, show_comments: bool, show_ins_del: bool, show_formatting: bool) -> None`.
    - Filter items in `refresh_items()` according to the active filter state.
  - In `WriterView`:
    - Wire `review_toolbar.markup_filter_changed` to `review_pane.set_markup_filter`.
    - Wire accept/reject revision actions to `doc` revision functions.
    - Wire delete/new comment actions.

### Task 5: Wire AnimationPane and LecternTaskPane Controls
- **Files**:
  - `src/atboffice/modules/presentation/views/animation_pane.py`
  - `src/atboffice/modules/presentation/views/workspace.py`
- **Actions**:
  - In `AnimationPane`:
    - Connect `self.btn_add_effect.clicked.connect(self.btn_add_effect.showMenu)`.
    - Verify submenus for Entrance, Emphasis, Exit, Motion Paths.
  - In `LecternTaskPane`:
    - Connect `self.title_button.clicked.connect(self.title_button.showMenu)`.

### Task 6: Standardize Virtual Methods in BaseOfficeWindow and SearchAdapter
- **Files**:
  - `src/atboffice/ui/shell/base_window.py`
  - `src/atboffice/core/search.py`
- **Actions**:
  - In `BaseOfficeWindow`:
    - Replace raw `pass` stubs with smart event/widget dispatching:
      - `undo`/`redo`: invoke on `self.focusWidget()` if available.
      - `cut`/`copy`/`paste`: dispatch to `self.focusWidget()` or standard clipboard.
      - `zoom_in`/`zoom_out`/`zoom_reset`: dispatch to central widget's zoom methods if supported.
      - `render_to_printer`: document subclass contract clearly.
  - In `SearchAdapter`:
    - Ensure `@abstractmethod` definitions have clean signatures and docstrings.

### Task 7: Verification & Regression Gate
- Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_orphan_stubs.py -v`.
- Run related dialog and GUI tests:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_writer_dialogs.py tests/modules/writer/test_writer_dialogs.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_animations.py tests/modules/presentation/test_animation_panes.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_review.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_base_office_window.py -v`
- Confirm all tests pass with zero regressions.
