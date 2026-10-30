# Implementation Plan: Issue #132 - 全面接线 Ledger 工具栏动作至单元格格式化、排序与公式计算

全面接线 Ledger 8 套 Excel 2003 Luna 工具栏中的核心动作，连接底层计算模型、选区控制器、网格视口与浮动图形图层，并实现选区双向状态同步与自动化测试验证。

---

## Proposed Tasks

### Task 1: 编写失败测试套件 (TDD Red Phase)
- **Files**: `tests/ui/test_ledger_toolbar_wiring.py`
- **Actions**:
  1. 测试 AutoSum：在连续数值上方或左侧，点击 AutoSum 按钮能正确嗅探并填入 `=SUM(A1:A3)`，计算结果并更新选区单元格；
  2. 测试快速排序：升序/降序能对表格区域基于指定列排序，保持整行关联；
  3. 测试数字格式化：货币样式、百分比样式、千位分隔符样式、增加与减少小数位；
  4. 测试合并及居中：多单元格合并为单个区域并居中，重复点击解除合并；
  5. 测试边框应用：应用所有框线、外侧框线、无边框；
  6. 测试绘图与浮动对象：唤起绘图工具栏，插入自选图形与文本框；
  7. 测试双向状态同步：改变选区时，粗斜体、对齐、字号字体、合并居中按钮状态与活动单元格一致。
- **Verify**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_ledger_toolbar_wiring.py -v` (预期因尚未接线而失败)

---

### Task 2: 在 LedgerWindow 中实现核心业务逻辑方法
- **Files**: `src/atboffice/ui/shell/ledger_window.py`
- **Actions**:
  1. `auto_sum(fn="SUM")`:
     - 检查活动单元格上方连续数字；若无则检查左侧连续数字；
     - 构建公式字符串，调用 `calc` 引擎求值，更新单元格 formula 及 value；
     - 同步更新公式栏与视口；
  2. `quick_sort(desc: bool = False)`:
     - 嗅探选区或周围连续数据区域，调用 `sort_sheet_range` 排序；
  3. 数字格式化与小数增减：
     - `apply_number_format(format_code: str)`
     - `change_decimal_places(delta: int)`
  4. 对齐与缩进：
     - `set_horizontal_alignment(align: str)`
     - `change_cell_indent(delta: int)`
  5. 合并及居中：
     - `toggle_merge_and_center()`
  6. 边框预设：
     - `apply_border_preset(preset_key: str)`
  7. 绘图与图表：
     - `toggle_drawing_toolbar()`
     - `insert_shape(kind: str)`
     - `insert_textbox()`
     - `insert_picture()`
     - `chart_wizard()`
     - `order_selected_object(direction: str)`

---

### Task 3: 全面接线 ActionRegistry 与工具栏菜单
- **Files**: `src/atboffice/ui/shell/ledger_window.py`, `src/atboffice/ui/shell/ledger_toolbars.py`
- **Actions**:
  1. 在 `_bind_action_handlers` 中将全部 action id 挂载至对应方法；
  2. 针对 split 按钮与下拉菜单（如 AutoSum split、边框 split、绘图菜单），连接菜单各 Action；
  3. 连接字体下拉框（`Ledger_FontCombo`）与字号下拉框（`Ledger_SizeCombo`）；
  4. 连接绘图填充颜色选择器（`Ledger_DrawFillColor`）。

---

### Task 4: 实现双向状态同步与上下文工具栏联动
- **Files**: `src/atboffice/ui/shell/ledger_window.py`
- **Actions**:
  1. 实现 `_sync_formatting_toolbar_states()`：
     - 读取活动单元格的字体、字号、加粗、倾斜、下划线、水平对齐、合并状态；
     - 使用 `blockSignals(True)` 动态同步至对应 Action 及 ComboBox；
  2. 监听 `selection_changed` 和 `active_cell_changed` 自动触发状态同步；
  3. 连接 `SpreadsheetObjectLayer.object_selected`，当选中图表对象时自动唤出图表工具栏。

---

### Task 5: 验证与回归测试 (TDD Green Phase)
- **Actions**:
  1. 运行新建的接线测试套件：`pytest tests/ui/test_ledger_toolbar_wiring.py -v`
  2. 运行既有工具栏测试套件：`pytest tests/ui/test_ledger_toolbars.py -v`
  3. 确认所有测试 100% 通过且无 regressions。
