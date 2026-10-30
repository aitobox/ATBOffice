# Implementation Plan: Issue #138 - 多标签首选项设置 (Options) 与主题实时预览切换

## Task Breakdown & DAG

### Task 1: Global Settings Management Layer (`AppSettings`)
- **Files**:
  - `src/atboffice/core/settings.py` (new)
  - `src/atboffice/core/__init__.py` (export `AppSettings`)
- **Details**:
  - Encapsulate `QSettings("ATBOffice", "ATBOffice")`.
  - Provide defaults dict:
    - `general/default_open_path`: `str(Path.home())`
    - `general/recent_files_limit`: 20
    - `general/start_behavior`: "start_center"
    - `view/ui_scale`: "100%"
    - `view/status_bar_timeout`: 3000
    - `edit/default_font_family`: "Tahoma"
    - `edit/default_font_size`: 12
    - `edit/show_gridlines`: True
    - `save/auto_save_interval`: 10
    - `save/default_save_format`: "docx"
    - `locale/language`: "zh-CN"
    - `theme/active_theme`: "blue"
  - Methods: `get_value(key)`, `set_value(key, value)`, `get_all()`, `reset_defaults()`, `apply_startup_settings()`.
  - Add `set_max_items(count: int)` in `RecentFilesManager` (`src/atboffice/core/recent_files.py`) and sync when `recent_files_limit` changes.

### Task 2: Office 2003 Theme Engine Extension (`luna_2003.py`)
- **Files**:
  - `src/atboffice/ui/styles/luna_2003.py`
- **Details**:
  - Define color tokens for `olive` (Luna Olive Green) and `classic` (Windows Classic).
  - Update `get_luna_stylesheet(theme: str) -> str` to support `"blue"`, `"silver"`, `"olive"`, and `"classic"`.
  - Implement `apply_theme_globally(theme: str)`:
    - Apply QSS to `QApplication.instance()`
    - Iterate `WindowManager.get_instance().active_windows` and `start_center` and topLevelWidgets to call `set_theme(theme)` and update palettes
    - Save to `AppSettings`.
  - Provide helper `THEMES` list: `[("blue", safe_tr("Luna 2003 蓝色")), ("silver", safe_tr("Luna 2003 银色")), ("olive", safe_tr("Luna 2003 橄榄绿")), ("classic", safe_tr("Windows 经典"))]`.

### Task 3: Theme Selector Dialog (`ThemeDialog`)
- **Files**:
  - `src/atboffice/ui/dialogs/theme_dialog.py` (new)
  - `src/atboffice/ui/dialogs/__init__.py` (export `ThemeDialog`)
- **Details**:
  - Create `ThemeCard(QFrame)` showing thumbnail gradient swatches, title, description, and selected state.
  - Create `ThemeDialog(QDialog)` with 4 cards arranged in a 2x2 grid or horizontal layout.
  - Real-time preview: when clicking a theme card, instantly preview using `apply_theme_globally(theme)`.
  - On "OK", persist selection; on "Cancel", revert to previous theme if changed.
  - Implement `retranslate_ui()`.

### Task 4: Multi-Tab Options Dialog (`OptionsDialog`)
- **Files**:
  - `src/atboffice/ui/dialogs/options_dialog.py` (new)
  - `src/atboffice/ui/dialogs/__init__.py` (export `OptionsDialog`)
- **Details**:
  - Create `OptionsDialog(QDialog)` with `QTabWidget` (General, View, Edit, Save, Language).
  - Populate controls from `AppSettings`.
  - "Apply" & "OK": Save all modified fields to `AppSettings`, sync language via `load_locale()`, sync recent files limit, and sync theme if changed.
  - "Restore Defaults": Reset UI controls to default values.
  - Implement `retranslate_ui()`.

### Task 5: Application & Menu Integration
- **Files**:
  - `src/atboffice/ui/shell/start_center.py`: Wire `self.btn_settings.clicked` to open `OptionsDialog`.
  - `src/atboffice/ui/shell/base_window.py`: Add `show_options_dialog()` and `show_theme_dialog()`. Update `set_theme` to support olive and classic.
  - `src/atboffice/ui/shell/mac_menu.py`: Wire `tools_options` to `show_options_dialog`. Add `theme_luna_olive`, `theme_classic`, and `theme_dialog` action items and wire them up.
  - `src/atboffice/main.py` / `src/atboffice/core/app.py`: Call `AppSettings.apply_startup_settings()` on startup.

### Task 6: Comprehensive Unit & Integration Tests
- **Files**:
  - `tests/ui/test_options_dialog.py` (new)
- **Details**:
  - Test `AppSettings` defaults, persistence, types, and reset.
  - Test `OptionsDialog` tabs creation, loading, saving, and "Restore Defaults".
  - Test modifying recent files limit and auto-save interval.
  - Test changing language dynamically and triggering `retranslate_ui()`.
  - Test `ThemeDialog` card selection, theme switching, and cancel reverting.
  - Test Start Center settings button and MenuBar `tools_options` wiring.
  - Run full test suite to guarantee 0 regressions.
