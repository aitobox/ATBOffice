# Technical Specification - Issue #159: Ledger 自定义自动筛选双条件对话框 (Custom AutoFilter)

## 1. Overview & Problem Statement

在 ATBOffice 的电子表格（Ledger）模块中，AutoFilter（自动筛选）功能允许用户在数据表格的首行（表头）通过下拉菜单进行快速排序和值筛选。目前已支持升降序排序、全选/反选值列表筛选以及 Top 10 筛选，但缺少 Excel 2003 经典的 **“(自定义...)” (Custom AutoFilter)** 复杂条件过滤向导。

本任务旨在：
1. 创建独立的 `src/atboffice/modules/spreadsheet/dialogs/custom_filter.py` 对话框组件。
2. 完整复刻 Excel 2003 经典双行条件过滤，涵盖全部 12 种比较操作符（等于、不等于、大于、大于或等于、小于、小于或等于、开头是、开头不是、结尾是、结尾不是、包含、不包含）。
3. 支持双条件间的“与（AND）”和“或（OR）”逻辑关系。
4. 提供目标值可编辑下拉框（自动装填当前列的唯一值列表），并支持 `*`（任意字符串）与 `?`（单个字符）通配符匹配。
5. 联动表头下拉菜单 `FilterDropdown` 中的“(自定义...)”选项，支持读取和回显已有筛选条件，并在确认后更新 `FilterModel`，触发 `apply_auto_filter` 更新视图。
6. 满足全面 i18n 要求（中英文地道翻译与 `retranslate_ui`）。

---

## 2. Reference & Parity with Original (.vibeoffice)

在原版 `.vibeoffice/public/ledger/js/filter.js` 中：
- `OPS`:
  - `equal` ("equals" / "等于")
  - `notEqual` ("does not equal" / "不等于")
  - `greaterThan` ("is greater than" / "大于")
  - `greaterThanOrEqual` ("is greater than or equal to" / "大于或等于")
  - `lessThan` ("is less than" / "小于")
  - `lessThanOrEqual` ("is less than or equal to" / "小于或等于")
  - `begins` ("begins with" / "开头是")
  - `notBegins` ("does not begin with" / "开头不是")
  - `ends` ("ends with" / "结尾是")
  - `notEnds` ("does not end with" / "结尾不是")
  - `contains` ("contains" / "包含")
  - `notContains` ("does not contain" / "不包含")
- 对话框结构：
  - 显示提示文本：“显示行:”(Show rows where:)
  - 当前列名加粗显示（如“<b>销售额</b>”或“<b>列 A</b>”）
  - 第一条件行：[操作符下拉框] [值输入/下拉框]
  - 中间逻辑组合：单选框 [与(And)] [或(Or)]
  - 第二条件行：[操作符下拉框(带空选)] [值输入/下拉框]
  - 底部提示：“用 ? 代表单个字符\n用 * 代表任意多个字符”
  - 确定 / 取消 按钮
- 回调与模型：
  - `fromDialog(op, val)`: 解析通配符与数值类型。
  - `customTest(cond, v, text)`: 数字按数值比对，字符串按文本及通配符比对。
  - `fc.custom = { and: bool, list: [...] }`。

---

## 3. Edge Case & Pre-Implementation Reflection (Think One Step Ahead)

1. **已存在筛选条件的回显 (Re-entrant Editing)**:
   - 若用户再次打开已自定义筛选的列，对话框必须精准回显此前的操作符、目标值以及 And/Or 单选状态，而不是丢失上次输入。
2. **第二条件为空 (Optional Second Condition)**:
   - 用户往往只需要单个条件。第二行操作符必须包含空选项（`""`）；当第二条件未选操作符或值为空时，只应用第一条件，不生成冗余条件。
3. **两个条件均为空 (Empty Input Handling)**:
   - 若用户清空了所有条件并点击确定，应视为清除该列的自定义筛选（相当于全选），不产生无效的过滤规则。
4. **通配符转义与数字/文本混合列**:
   - `test_custom_condition` 需正确区分纯数字比较与带通配符的模糊文本比较。如输入 `100`，数值单元格 `100.0` 应匹配；如输入 `10*`，则按通配符模式匹配字符串 `"100"`、`"105"` 等。
5. **大小写敏感度与空白单元格**:
   - 筛选比对遵循 Excel 默认规则（文本比较不区分大小写，`is_blank` 正确处理 None/空字符串）。
6. **UI 焦点与键盘导航**:
   - 默认焦点停留在第一条件的值输入框，支持 Enter 键直接确认，Esc 键取消。
7. **完整 i18n 支持**:
   - 所有文本使用 `safe_tr()` / `QCoreApplication.translate("CustomFilterDialog", ...)`，实现中英双语地道翻译，并提供 `retranslate_ui()`。

---

## 4. Architecture & Interface Contracts

### 4.1 `src/atboffice/modules/spreadsheet/dialogs/custom_filter.py`

```python
class CustomFilterDialog(QDialog):
    OPERATORS = [
        ("equal", "等于"),
        ("notEqual", "不等于"),
        ("greaterThan", "大于"),
        ("greaterThanOrEqual", "大于或等于"),
        ("lessThan", "小于"),
        ("lessThanOrEqual", "小于或等于"),
        ("begins", "开头是"),
        ("notBegins", "开头不是"),
        ("ends", "结尾是"),
        ("notEnds", "结尾不是"),
        ("contains", "包含"),
        ("notContains", "不包含"),
    ]

    def __init__(
        self,
        column_header: str,
        unique_values: list[str],
        initial_conditions: list[tuple[str, str]] | None = None,
        initial_and: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        ...

    def get_custom_criteria(self) -> tuple[list[tuple[str, str]], bool]:
        """Return (criteria_list, is_and). Criteria list format: [(operator, value_pattern), ...]."""
        ...

    def retranslate_ui(self) -> None:
        ...
```

### 4.2 Integration with `FilterDropdown`

在 `src/atboffice/modules/spreadsheet/views/filter_dropdown.py` 中：
- 从 `atboffice.modules.spreadsheet.dialogs.custom_filter` 导入 `CustomFilterDialog`。
- 在 `_on_custom(self)` 中：
  - 获取当前列的已有筛选条件 `current_crit = self.af.cols.get(self.col_offset)`。
  - 提取 `initial_conditions = current_crit.custom_list if current_crit else None`。
  - 提取 `initial_and = current_crit.custom_and if current_crit else True`。
  - 实例化 `CustomFilterDialog` 并执行。
  - 若用户确认且 `conds` 非空，构建 `ColumnFilter(custom_list=conds, custom_and=is_and)` 并发射 `filter_applied` 信号；若清空则发射 `filter_cleared`。

---

## 5. Verification Plan

1. **单元测试 (`tests/modules/spreadsheet/test_filter_and_sort.py`)**:
   - 测试 12 种操作符在数值、文本、通配符下的求值准确性。
   - 测试 AND 和 OR 双条件的逻辑组合。
   - 测试 `CustomFilterDialog` 的创建、数据填充、初值回显、条件提取及 `retranslate_ui`。
   - 测试通过 `FilterDropdown` 触发自定义筛选并更新 `AutoFilter` 隐藏行。
2. **全量回归测试**:
   - `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/ -v`。
