# Specification: Issue #135 - 补齐 Quire 表格属性、边框底纹、分栏与制表位对话框

## 1. Overview & Context
This specification details the Python 3.12+ / PySide6 implementation of classic Word 2003 / Quire modal dialogs:
1. `TablePropertiesDialog` (`table_properties.py`)
2. `InsertTableDialog` (`insert_table.py`)
3. `BordersShadingDialog` (`borders_shading.py`)
4. `TabsDialog` (`tabs_dialog.py`)
5. `ColumnsDialog` (`columns_dialog.py`)

All dialogs will reside in `src/atboffice/modules/writer/dialogs/`, be exported in `__init__.py`, conform strictly to idiomatic Qt6 patterns, use `safe_tr()` for complete i18n support, and implement `retranslate_ui()`.

---

## 2. Architecture & Detailed Module Design

### 2.1 `TablePropertiesDialog` (`table_properties.py`)
- **Tabs**:
  1. **Table («表格»)**:
     - Preferred width: `QCheckBox` + `QDoubleSpinBox` + `QComboBox` ("dxa" / "Inches/cm", "pct" / "Percent").
     - Alignment: `QRadioButton` group (Left / 居中 / Right).
     - Indent from left: `QDoubleSpinBox` (active only when Left aligned).
     - Text wrapping: `QRadioButton` group (None / Around).
     - Borders & Shading button: opens `BordersShadingDialog`.
     - Options button: modal dialog for default cell margins (top, bottom, left, right), cell spacing, auto resize checkbox.
  2. **Row («行»)**:
     - Row selector / label (`Row 1:` or `Rows 1-2:`).
     - Specify height: `QCheckBox` + `QDoubleSpinBox` + `QComboBox` (At least / Exactly).
     - Options: Allow row to break across pages (`cant_split`), Repeat as header row at the top of each page (`tbl_header`).
  3. **Column («列»)**:
     - Column selector / label (`Column 1:`).
     - Preferred width: `QCheckBox` + `QDoubleSpinBox`.
  4. **Cell («单元格»)**:
     - Preferred width: `QCheckBox` + `QDoubleSpinBox`.
     - Vertical alignment: `QRadioButton` group (Top / Center / Bottom).
     - Cell Options button: cell margins (same as table / custom t,b,l,r), wrap text, fit text.
- **Data Model Integration**:
  - Accepts `table: Table | None`, `table_props: TableProperties | None`, `row_idx: int = 0`, `col_idx: int = 0`, `cell_props: CellProperties | None`, `active_tab: int = 0`.
  - Provides `apply_to_table(table: Table) -> None` and `get_properties() -> dict`.

### 2.2 `InsertTableDialog` (`insert_table.py`)
- **Layout & Controls**:
  - Table size:
    - Number of columns: `QSpinBox` (min: 1, max: 63, default: 5).
    - Number of rows: `QSpinBox` (min: 1, max: 32767, default: 2).
  - AutoFit behavior:
    - Fixed column width: `QRadioButton` + `QDoubleSpinBox` (with auto or points).
    - AutoFit to contents: `QRadioButton`.
    - AutoFit to window: `QRadioButton`.
  - Remember dimensions checkbox: `QCheckBox`.
- **Data Model Integration**:
  - `get_dimensions() -> tuple[int, int, str, float | None]` returning `(cols, rows, autofit_mode, col_width)`.

### 2.3 `BordersShadingDialog` (`borders_shading.py`)
- **Tabs**:
  1. **Borders («边框»)**:
     - Settings: Radio buttons or list (None, Box, All, Grid, Custom).
     - Line Style: `QListWidget` with visual / text style names (`single`, `dotted`, `dashed`, `double`, `triple`, `wave`, etc.).
     - Color: `QComboBox` or color picker button with standard palette.
     - Width: `QComboBox` (0.25, 0.5, 0.75, 1.0, 1.5, 2.25, 3.0, 4.5, 6.0 pt).
     - Preview Widget (`BorderPreviewWidget`): Shows top, bottom, left, right, insideH, insideV with interactive toggle buttons.
     - Apply to: `QComboBox` ("Table", "Cell", "Paragraph", "Text").
  2. **Page Border («页面边框»)**:
     - Same settings applied to whole page / section margin boundary.
     - Apply to: `QComboBox` ("Whole document", "This section", "First page only", "All except first page").
  3. **Shading («底纹»)**:
     - Fill Color: Color swatch grid + "No Fill" button + custom color dialog.
     - Patterns: Style combo (`clear`, `solid`, `5%`, `10%`, `20%`, `25%`, `50%`, `75%`, `horzStripe`, `vertStripe`, etc.) + Color combo.
     - Preview: Live shading box.
     - Apply to: `QComboBox` ("Table", "Cell", "Paragraph", "Text").
- **Data Model Integration**:
  - Accepts `borders: dict[str, BorderProperties] | None`, `shading: ShadingProperties | None`, `target_type: str = "cell"`.
  - `get_properties() -> dict` returning clean borders and shading dictionaries.

### 2.4 `TabsDialog` (`tabs_dialog.py`)
- **Controls**:
  - Tab stop position: `QLineEdit` + `QListWidget` showing sorted tab stop positions.
  - Default tab stops: `QDoubleSpinBox` (min: 1.0, default: 36.0 pt).
  - Alignment: `QRadioButton` group (Left, Center, Right, Decimal, Bar).
  - Leader: `QRadioButton` group (1 None, 2 ......., 3 -------, 4 ______ ).
  - Buttons: `Set` (adds or updates tab stop), `Clear` (removes highlighted position), `Clear All` (clears all).
  - Clear list info label.
- **Data Model Integration**:
  - Accepts `tabs: list[TabStop] | None`, `default_tab: float = 36.0`.
  - `get_tabs() -> list[TabStop]`, `get_default_tab() -> float`.

### 2.5 `ColumnsDialog` (`columns_dialog.py`)
- **Controls**:
  - Presets: Buttons for "One" (1), "Two" (2), "Three" (3), "Left" (2, uneven), "Right" (2, uneven).
  - Number of columns: `QSpinBox` (min: 1, max: 13, default: 1).
  - Line between: `QCheckBox` (`sep`).
  - Width and spacing:
    - Dynamic rows/columns showing Col #, Width, Spacing.
    - Equal column width: `QCheckBox` (`equal_width`).
  - Apply to: `QComboBox` ("This section", "Whole document", "This point forward").
  - Start new column: `QCheckBox`.
  - Live Preview Widget (`ColumnsPreviewWidget`): Renders columns simulation with vertical line separator.
- **Data Model Integration**:
  - Accepts `cols: ColumnsProperties | None`, `page_width: float = 612.0`, `margins: tuple[float, float] = (90.0, 90.0)`.
  - `get_columns() -> ColumnsProperties`, `get_apply_to() -> str`.

---

## 3. Edge Cases & Robustness Handling
1. **Input validation**: Non-numeric or out-of-range dimensions safely clamped; empty lists handled gracefully without crashing.
2. **Dynamic UI state sync**: Disabling width/spacing fields when "Equal column width" is checked; updating live preview widgets synchronously.
3. **i18n & Retranslate**: 100% translatable text with `safe_tr()`; `retranslate_ui()` tested and working.
4. **Clean integration**: Exported in `__init__.py` without circular dependencies.
