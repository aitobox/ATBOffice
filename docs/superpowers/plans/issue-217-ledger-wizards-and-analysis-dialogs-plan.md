# Implementation Plan: Issue #217 - 补全 Ledger 图表向导、分列向导与高级分析对话框

## Overview
依据规范 `docs/superpowers/specs/issue-217-ledger-wizards-and-analysis-dialogs-spec.md`，实现 Ledger 模块的 9 个核心向导与对话框，完成数据模型与控制器接通，并建立完整的单元与交互测试覆盖。

---

## Tasks Breakdown

### Task 1: Implement `ChartWizardDialog` (4 步图表向导)
- **File**: `src/atboffice/modules/spreadsheet/dialogs/chart_wizard.py`
- **Details**:
  1. 继承 `QDialog`，使用 `QStackedWidget` 管理 4 个步骤页面：
     - Step 1: 图表类型与子类型选择（柱形图、条形图、折线图、饼图、散点图、面积图、圆环图、雷达图），带类型说明与示例预览。
     - Step 2: 图表源数据（“数据区域”与“系列”两标签页，支持从当前选区自动填充，支持行/列系列切换）。
     - Step 3: 图表选项（标题 Titles、坐标轴 Axes、网格线 Gridlines、图例 Legend、数据标志 Data Labels、数据表 Data Table）。
     - Step 4: 图表位置（作为新工作表插入 / 作为对象插入到指定工作表）。
  2. 向导控制栏（Cancel, < Back, Next >, Finish）。
  3. 点击 Finish 时，在目标工作表的 `SheetDataModel.drawings` 中生成 `FloatingObject(kind="chart", name=title, ...)` 并触发变更。
  4. 完整实现 `retranslate_ui()` 与 100% `safe_tr()` 覆盖。

---

### Task 2: Implement `TextToColumnsWizard` (3 步文本分列向导)
- **File**: `src/atboffice/modules/spreadsheet/dialogs/text_to_columns_wizard.py`
- **Details**:
  1. 继承 `QDialog`，使用 `QStackedWidget` 管理 3 个步骤页面：
     - Step 1: 原始数据类型（分隔符号 Delimited / 固定宽度 Fixed width），起始导入行，选区前 10 行文本预览。
     - Step 2: 分隔符选择（Tab, 分号, 逗号, 空格, 其他自定义字符），连续分隔符视为单个处理，文本限定符选择，实时数据分割预览表格。
     - Step 3: 每列数据格式（常规, 文本, 日期, 不导入此列/跳过），目标区域引用输入框，底部预览表格列头格式指示。
  2. 点击 Finish 时，将选区文本分列结果写入 `SheetDataModel` 对应单元格。
  3. 目标区域存在数据时提示确认替换。
  4. 完整实现 `retranslate_ui()` 与 `safe_tr()`。

---

### Task 3: Implement `SubtotalDialog` (分类汇总对话框)
- **File**: `src/atboffice/modules/spreadsheet/dialogs/subtotal_dialog.py`
- **Details**:
  1. 分类字段下拉框 `combo_group_by`（提取选区表头）。
  2. 汇总函数下拉框 `combo_function`（求和 SUM、计数 COUNT、平均值 AVERAGE、最大值 MAX、最小值 MIN、乘积 PRODUCT、数值计数、标准差、方差）。
  3. 选定汇总项复选框列表 `list_subtotal_columns`。
  4. 替换当前分类汇总、每组数据分页、汇总结果显示在数据下方选项。
  5. 提供“确定”、“取消”、“全部删除 (Remove All)”功能。
  6. 完整实现 `retranslate_ui()` 与 `safe_tr()`。

---

### Task 4: Implement `ConsolidateDialog` (合并计算对话框)
- **File**: `src/atboffice/modules/spreadsheet/dialogs/consolidate_dialog.py`
- **Details**:
  1. 函数选择下拉框（Sum, Count, Average, Max, Min, Product 等）。
  2. 引用位置输入框与选区引用添加/删除列表。
  3. 标签位置复选框（首行 Top row、最左列 Left column）。
  4. 创建指向源数据的链接。
  5. 聚合各引用区域数值写入当前目标位置。
  6. 完整实现 `retranslate_ui()` 与 `safe_tr()`。

---

### Task 5: Implement `ScenarioManagerDialog` (方案管理器对话框)
- **File**: `src/atboffice/modules/spreadsheet/dialogs/scenario_manager_dialog.py`
- **Details**:
  1. 方案列表、可变单元格与批注只读显示。
  2. 添加方案子对话框 `AddScenarioDialog`、方案值子对话框 `ScenarioValuesDialog`。
  3. “显示”按钮将方案值更新入工作表对应单元格。
  4. “摘要”按钮生成方案汇总报告。
  5. 完整实现 `retranslate_ui()` 与 `safe_tr()`。

---

### Task 6: Implement `DataTableDialog` (双变量/单变量模拟运算表对话框)
- **File**: `src/atboffice/modules/spreadsheet/dialogs/data_table_dialog.py`
- **Details**:
  1. 输入引用行单元格 (Row input cell)。
  2. 输入引用列单元格 (Column input cell)。
  3. 模拟运算表运算逻辑，填充计算结果矩阵。
  4. 完整实现 `retranslate_ui()` 与 `safe_tr()`。

---

### Task 7: Implement `ProtectSheetDialog`, `UnprotectSheetDialog` & `ProtectWorkbookDialog`
- **File**: `src/atboffice/modules/spreadsheet/dialogs/protect_dialog.py`
- **Details**:
  1. `ProtectSheetDialog`:
     - 密码输入框、保护工作表及锁定单元格内容复选框。
     - 允许用户操作清单多选列表（选定锁定/未锁定单元格、格式设置、插入/删除行列、排序、自动筛选、数据透视表、对象编辑等）。
     - 再次确认密码校验。
     - 更新 `sheet.protection` 字典。
  2. `UnprotectSheetDialog`:
     - 密码校验输入框，核对 hash 后移除 `sheet.protection`。
  3. `ProtectWorkbookDialog`:
     - 密码输入框、结构与窗口复选框。
     - 更新 `workbook.protection`。
  4. 完整实现 `retranslate_ui()` 与 `safe_tr()`。

---

### Task 8: Implement `AdvancedFilterDialog` (高级筛选对话框)
- **File**: `src/atboffice/modules/spreadsheet/dialogs/advanced_filter_dialog.py`
- **Details**:
  1. 筛选方式单选：在原有区域显示筛选结果 / 将筛选结果复制到其他位置。
  2. 列表区域、条件区域、复制到目标区域输入框。
  3. 选择不重复的记录复选框。
  4. 执行多条件与唯一记录过滤计算。
  5. 完整实现 `retranslate_ui()` 与 `safe_tr()`。

---

### Task 9: Implement `LedgerOptionsDialog` (9 标签全功能选项对话框)
- **File**: `src/atboffice/modules/spreadsheet/dialogs/options_dialog.py`
- **Details**:
  1. 8~9 个选项标签页：View, Calculation, Edit, General, Custom Lists, Error Checking, Spelling, Security。
  2. 读取与设置持久化字典 `get_settings()` / `apply_settings()`。
  3. 完整实现 `retranslate_ui()` 与 `safe_tr()`。

---

### Task 10: Export Dialogs & Wire into Dialogs Package & Controller
- **Files**:
  - `src/atboffice/modules/spreadsheet/dialogs/__init__.py`
  - `src/atboffice/modules/spreadsheet/views/editor_controller.py`
- **Details**:
  - 在 `__init__.py` 中导出所有新增的 Dialog/Wizard 类。
  - 在 `editor_controller.py` 或 command 体系中挂载相应操作入口，确保点击或调用时能正常拉起对话框。

---

### Task 11: Comprehensive Test Suite & Full Verification
- **File**: `tests/gui/test_ledger_dialogs_phase6.py`
- **Details**:
  - 编写覆盖全部 9 个对话框/向导的全面测试用例。
  - 验证初始加载、各步骤翻页、参数校验、执行完成、取消退出、国际化 `retranslate_ui`。
  - 运行 pytest 测试套件并确保 100% 通过。
