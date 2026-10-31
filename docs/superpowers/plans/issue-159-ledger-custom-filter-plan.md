# Implementation Plan - Issue #159: Ledger 自定义自动筛选双条件对话框

## Objective
实现 Excel 2003 风格的 Ledger 自定义自动筛选双条件对话框 (`CustomFilterDialog`)，提供 12 种比较操作符、可编辑目标值下拉框、与/或单选组合逻辑、回显已有条件以及完整 i18n 支持，并与 `FilterDropdown` 联动更新 `FilterModel`。

---

## Tasks

### Task 1: Write Comprehensive Test Suite (TDD)
- **Files**: `tests/modules/spreadsheet/test_filter_and_sort.py`
- **Actions**:
  1. 单元测试 `test_custom_condition`:
     - 验证 `equal`, `notEqual`, `greaterThan`, `greaterThanOrEqual`, `lessThan`, `lessThanOrEqual`。
     - 验证 `begins`, `notBegins`, `ends`, `notEnds`, `contains`, `notContains`。
     - 验证通配符 `*` 和 `?`。
     - 验证数值、文本混合比较。
  2. 单元测试 `apply_auto_filter` 与 `ColumnFilter(custom_list=..., custom_and=...)`:
     - 验证双条件 AND 逻辑。
     - 验证双条件 OR 逻辑。
     - 验证与 values/blank 的联合过滤。
  3. 单元测试 `CustomFilterDialog`:
     - 验证对话框初始化（列名、候选列表、操作符列表）。
     - 验证初始条件回显（initial_conditions, initial_and）。
     - 验证条件提取 `get_custom_criteria()`。
     - 验证 `retranslate_ui()`。
  4. 验证 `FilterDropdown._on_custom` 打开对话框并应用筛选。
- **Verification Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_filter_and_sort.py -v
  ```

### Task 2: Implement `CustomFilterDialog`
- **Files**: `src/atboffice/modules/spreadsheet/dialogs/custom_filter.py`
- **Actions**:
  1. 定义 12 种操作符映射表 `OPERATORS`。
  2. 实现 `CustomFilterDialog` 类：
     - 双行条件设置：第一行（必须或首选条件），第二行（可选条件，首项带空选项）。
     - 目标值可编辑下拉框 `QComboBox(setEditable=True)`，填充唯一值。
     - 逻辑组合单选按钮组：`QRadioButton("&And")` 与 `QRadioButton("&Or")`，默认 And。
     - 通配符使用提示 QLabel（支持中英文地道翻译）。
     - 接收 `initial_conditions` 和 `initial_and` 参数以恢复已有条件。
     - 确定/取消 `QDialogButtonBox`。
     - `get_custom_criteria() -> tuple[list[tuple[str, str]], bool]`。
     - `retranslate_ui()` 规范多语言更新。

### Task 3: Package Export
- **Files**: `src/atboffice/modules/spreadsheet/dialogs/__init__.py`
- **Actions**:
  1. 导入并导出 `CustomFilterDialog`。

### Task 4: Connect with `FilterDropdown`
- **Files**: `src/atboffice/modules/spreadsheet/views/filter_dropdown.py`
- **Actions**:
  1. 从 `atboffice.modules.spreadsheet.dialogs.custom_filter` 导入 `CustomFilterDialog`。
  2. 移除旧的冗余内嵌 `CustomFilterDialog`，避免重复定义。
  3. 在 `_on_custom` 中传入当前列的已有筛选条件（如果有）进行回显。
  4. 用户确认后更新 `ColumnFilter`，发射 `filter_applied` 或 `filter_cleared` 信号。

### Task 5: End-to-End Verification & Regression Suite
- **Verification Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_filter_and_sort.py -v
  PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/ -v
  ```
