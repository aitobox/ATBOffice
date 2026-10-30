# Specification: Issue #136 - 实现 Ledger 条件格式 (CF) 与数据有效性校验系统

## 1. Overview & Context

This specification outlines the architecture, data models, UI components, rendering pipeline integration, and OpenXML XLSX serialization for the conditional formatting (CF) and data validation (DV) subsystems in ATBOffice Ledger (Python 3.12+ / PySide6).

Reference implementation: `.vibeoffice/public/ledger/js/cf.js`.

---

## 2. Core Subsystems & Architecture

```
                            ┌──────────────────────────────┐
                            │        SheetDataModel        │
                            │  .conditional_formats: list  │
                            │  .data_validations: list     │
                            └──────────────┬───────────────┘
                                           │
                 ┌─────────────────────────┴─────────────────────────┐
                 ▼                                                   ▼
   ┌───────────────────────────┐                       ┌───────────────────────────┐
   │    conditional_format     │                       │        validation         │
   │  - CFRule, ColorScale     │                       │  - DataValidation         │
   │  - DataBar, evaluate_cf   │                       │  - validate_cell_value    │
   │  - mix_colors lerp        │                       │  - get_list_items         │
   └─────────────┬─────────────┘                       └─────────────┬─────────────┘
                 │                                                   │
                 ▼                                                   ▼
   ┌───────────────────────────┐                       ┌───────────────────────────┐
   │    GridViewport Render    │                       │     EditorController      │
   │  - bg_color & text style  │                       │  - in-cell validation     │
   │  - data bar overlay       │                       │  - error alert dialog     │
   │  - dropdown trigger icon  │                       │  - list popup dropdown    │
   └───────────────────────────┘                       └───────────────────────────┘
                 │                                                   │
                 └─────────────────────────┬─────────────────────────┘
                                           ▼
                            ┌──────────────────────────────┐
                            │     xlsx_reader / writer     │
                            │  - <conditionalFormatting>   │
                            │  - <dataValidations>         │
                            └──────────────────────────────┘
```

---

## 3. Detailed Data Models

### 3.1 Conditional Formatting (`src/atboffice/modules/spreadsheet/models/conditional_format.py`)

- **`CFRuleType`**:
  `CELL_IS = "cellIs"`, `EXPRESSION = "expression"`, `COLOR_SCALE = "colorScale"`, `DATA_BAR = "dataBar"`, `CONTAINS_TEXT = "containsText"`, `NOT_CONTAINS_TEXT = "notContainsText"`, `BEGINS_WITH = "beginsWith"`, `ENDS_WITH = "endsWith"`, `DUPLICATE_VALUES = "duplicateValues"`, `UNIQUE_VALUES = "uniqueValues"`, `TOP10 = "top10"`, `ABOVE_AVERAGE = "aboveAverage"`

- **`CFOp`**:
  `BETWEEN = "between"`, `NOT_BETWEEN = "notBetween"`, `EQUAL = "equal"`, `NOT_EQUAL = "notEqual"`, `GREATER_THAN = "greaterThan"`, `LESS_THAN = "lessThan"`, `GREATER_THAN_OR_EQUAL = "greaterThanOrEqual"`, `LESS_THAN_OR_EQUAL = "lessThanOrEqual"`

- **`CFVO`**:
  `type: str` ("min", "max", "num", "percent", "percentile", "formula"), `val: Any = None`, `gte: bool = True`

- **`ColorScaleRule`**:
  `cfvos: list[CFVO]` (2 or 3 items), `colors: list[str]` (2 or 3 hex colors e.g. `["#F8696B", "#63BE7B"]` or `["#F8696B", "#FFEB84", "#63BE7B"]`)

- **`DataBarRule`**:
  `cfvos: list[CFVO]`, `color: str = "#638EC6"`, `min_len: float = 0.1`, `max_len: float = 0.9`, `show_value: bool = True`

- **`CFRule`**:
  - `type: str`
  - `operator: str | None = None`
  - `formula: list[str] = field(default_factory=list)`
  - `text: str | None = None`
  - `priority: int = 1`
  - `stop_if_true: bool = False`
  - `bg_color: str | None = None`
  - `fg_color: str | None = None`
  - `bold: bool | None = None`
  - `italic: bool | None = None`
  - `color_scale: ColorScaleRule | None = None`
  - `data_bar: DataBarRule | None = None`

- **`ConditionalFormat`**:
  - `sqref: str` (e.g. `"A1:C10"`)
  - `ranges: list[tuple[int, int, int, int]] = field(default_factory=list)`
  - `rules: list[CFRule] = field(default_factory=list)`

- **Evaluation Engine (`evaluate_cf_for_cell`)**:
  - Iterates rules by priority.
  - Matches rule condition for cell `(r, c)`.
  - Calculates color gradient interpolation (`mix_colors(c1, c2, t)`) for color scales.
  - Computes fraction `frac` for data bars.
  - Returns `CFResult` containing `bg_color`, `fg_color`, `bold`, `italic`, `data_bar`.

### 3.2 Data Validation (`src/atboffice/modules/spreadsheet/models/validation.py`)

- **`ValidationType`**:
  `ANY = "any"`, `WHOLE = "whole"`, `DECIMAL = "decimal"`, `LIST = "list"`, `DATE = "date"`, `TIME = "time"`, `TEXT_LENGTH = "textLength"`, `CUSTOM = "custom"`

- **`ValidationOp`**:
  `BETWEEN = "between"`, `NOT_BETWEEN = "notBetween"`, `EQUAL = "equal"`, `NOT_EQUAL = "notEqual"`, `GREATER_THAN = "greaterThan"`, `LESS_THAN = "lessThan"`, `GREATER_THAN_OR_EQUAL = "greaterThanOrEqual"`, `LESS_THAN_OR_EQUAL = "lessThanOrEqual"`

- **`AlertStyle`**:
  `STOP = "stop"`, `WARNING = "warning"`, `INFORMATION = "information"`

- **`DataValidation`**:
  - `type: str = "any"`
  - `operator: str = "between"`
  - `allow_blank: bool = True`
  - `show_dropdown: bool = True`
  - `show_input_message: bool = False`
  - `input_title: str = ""`
  - `input_message: str = ""`
  - `show_error_alert: bool = True`
  - `error_style: str = "stop"`
  - `error_title: str = ""`
  - `error_message: str = ""`
  - `formula1: str | None = None`
  - `formula2: str | None = None`
  - `sqref: str = ""`
  - `ranges: list[tuple[int, int, int, int]] = field(default_factory=list)`

- **Validation Engine**:
  - `get_validation_for_cell(sheet, r, c) -> DataValidation | None`
  - `get_list_items(sheet, dv, r, c) -> list[str]`
  - `validate_cell_value(sheet, r, c, val) -> tuple[bool, DataValidation | None]`

---

## 4. UI & Dialogs

1. **`ConditionalFormatDialog`** (`src/atboffice/modules/spreadsheet/dialogs/conditional_format_dialog.py`):
   - Supports adding, editing, removing rules.
   - Condition type selection (Cell Value Is, Formula Is).
   - Operator dropdown (between, equal, greaterThan, lessThan, etc.).
   - Value 1 & 2 inputs.
   - Color pickers for preview background and text color.
   - Complete `safe_tr()`, `retranslate_ui()`.

2. **`DataValidationDialog`** (`src/atboffice/modules/spreadsheet/dialogs/data_validation_dialog.py`):
   - 3 Classic tabs: Settings, Input Message, Error Alert.
   - Validation type selector with dynamic field enabling.
   - Complete `safe_tr()`, `retranslate_ui()`.

3. **`ValidationAlertDialog`**:
   - Modal alert showing Stop / Warning / Information icon.
   - Title, message, and Retry / Cancel / Yes / No buttons.

---

## 5. Rendering Pipeline & Editor Integration

1. **`GridViewport`**:
   - During cell painting in `paintEvent`, calls `evaluate_cf_for_cell()`.
   - Overlays CF background color, font color, bold/italic, and data bar rectangle.
   - If active cell has list validation with in-cell dropdown, displays dropdown arrow button at the right edge of the cell.

2. **`EditorController`**:
   - On commit, validates input with `validate_cell_value()`.
   - On failure, displays `ValidationAlertDialog`.
   - Supports dropdown selection menu when clicking dropdown arrow or pressing Alt+Down.

---

## 6. XLSX File I/O Serialization

- **`xlsx_writer.py`**:
  - Writes `<conditionalFormatting sqref="...">` elements with `<cfRule>` children.
  - Writes `<dataValidations count="...">` elements with `<dataValidation>` children.
  - Conforms strictly to ECMA-376 Part 1 schema ordering.

- **`xlsx_reader.py`**:
  - Reads `<conditionalFormatting>` and attaches `ConditionalFormat` objects to `SheetDataModel`.
  - Reads `<dataValidations>` and attaches `DataValidation` objects to `SheetDataModel`.
