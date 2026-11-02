# Specification: Issue #217 - 补全 Ledger 图表向导、分列向导与高级分析对话框

## 1. Overview & Objective
本设计规范针对 GitHub Issue #217 (TASK-605)，对照 `.vibeoffice/screenshots/02_ledger/` 中 52 个对话框和 77 张多标签截图基线，完整实现 Ledger 模块中缺失的经典向导体系与高级数据分析对话框集群：
1. **Chart Wizard** (4 步图表向导) - `chart_wizard.py`
2. **Text to Columns Wizard** (3 步文本分列向导) - `text_to_columns_wizard.py`
3. **Subtotal** (分类汇总对话框) - `subtotal_dialog.py`
4. **Consolidate** (合并计算对话框) - `consolidate_dialog.py`
5. **Scenario Manager** (方案管理器对话框) - `scenario_manager_dialog.py`
6. **Data Table** (双变量模拟运算表对话框) - `data_table_dialog.py`
7. **Protect Sheet / Protect Workbook** (工作表/工作簿保护对话框) - `protect_dialog.py`
8. **Advanced Filter** (高级筛选对话框) - `advanced_filter_dialog.py`
9. **Ledger Options** (9 标签全功能选项对话框) - `options_dialog.py`

---

## 2. Visual & Behavioral Parity Reference

对照 `.vibeoffice/screenshots/02_ledger/`：
- `127_dialog_ChartWizard__Chart_Wizard_Step1.png`: Chart Wizard Step 1: 图表类型与子类型选择，包含柱形图、折线图、饼图、条形图、面积图、散点图等标准类型，支持实时预览与详细描述。
- `128_dialog_TextToColumns__Wizard_Step1.png`: Text to Columns Wizard Step 1: 分隔符号或固定宽度分列，底部实时表格预览。
- `097_dialog_Subtotal__Subtotal Calculation by Group.png`: 分类汇总，分类字段、汇总方式（求和/计数/平均值/最大值/最小值/乘积/数值计数/标准差/方差）、选定汇总项、替换当前分类汇总、每组数据分页、汇总结果显示在数据下方。
- `105_dialog_Consolidate__Consolidate Ranges Data.png`: 合并计算，汇总函数、引用位置添加/删除、标签位置（首行/最左列）、创建指向源数据的链接。
- `103_dialog_Scenario_Manager__Scenario Manager.png`: 方案管理器，方案列表、添加/删除/编辑/合并/摘要，应用方案值并支持撤销重做。
- `104_dialog_Data_Table__Two-input Data Table.png`: 模拟运算表，输入引用行单元格、输入引用列单元格，动态计算结果网格。
- `114_dialog_Protect_Sheet__Protect Sheet with Password.png`: 保护工作表，密码输入框、受保护权限多选列表（选定锁定/未锁定单元格、设置格式、插入行列、删除行列、排序、自动筛选、使用数据透视表等）。
- `115_dialog_Protect_Workbook__Protect Workbook Structure.png`: 保护工作簿，保护结构与保护窗口。
- `098_dialog_Advanced_Filter__Advanced Filter Criteria.png`: 高级筛选，在原有区域显示筛选结果/将筛选结果复制到其他位置、列表区域、条件区域、复制到、选择不重复的记录。
- `064_dialog_Options...` 至 `071_dialog_Options...`: 选项对话框 8~9 个经典标签页（视图 View, 计算 Calculation, 编辑 Edit, 常规 General, 自定义序列 Custom Lists, 错误检查 Error Checking, 拼写检查 Spelling, 安全性 Security）。

---

## 3. Component Architecture & Detailed Design

### 3.1. Chart Wizard (4 步图表向导: `chart_wizard.py`)
- **Step 1: Chart Type (图表类型)**
  - 左侧标准图表类型列表：柱形图 (Column)、条形图 (Bar)、折线图 (Line)、饼图 (Pie)、散点图 (XY Scatter)、面积图 (Area)、圆环图 (Doughnut)、雷达图 (Radar)。
  - 右侧子类型网格或卡片：簇状、堆积、百分比堆积、三维效果等。
  - 描述区域说明当前选定图表用途。
- **Step 2: Chart Source Data (图表源数据)**
  - “数据区域”标签页：数据区域引用框（带折叠选区按钮）；系列产生在：行 (Rows) 或 列 (Columns)。
  - “系列”标签页：系列列表（添加/删除）、名称引用框、值引用框、分类(X)轴标志引用框。
- **Step 3: Chart Options (图表选项)**
  - 标签页 1: 标题 (Titles: 图表标题、分类(X)轴标题、数值(Y)轴标题)。
  - 标签页 2: 坐标轴 (Axes: 显示分类轴、显示数值轴)。
  - 标签页 3: 网格线 (Gridlines: 主要网格线、次要网格线)。
  - 标签页 4: 图例 (Legend: 显示图例，位置：底部/右上角/顶部/右侧/左侧)。
  - 标签页 5: 数据标志 (Data Labels: 无/值/百分比/系列名称/类别名称)。
  - 标签页 6: 数据表 (Data Table: 显示数据表、显示图例项标示)。
- **Step 4: Chart Location (图表位置)**
  - 单选钮 1: 作为新工作表插入 (As new sheet: 默认名称 `Chart1`)。
  - 单选钮 2: 作为其中的对象插入 (As object in: 当前工作表下拉列表)。
- **向导按钮控制**: `< 上一步(&B)`, `下一步(&N) >`, `完成(&F)`, `取消(&C)`。
- **确定提交**:
  - 在当前工作表 `SheetDataModel.drawings` 中创建 `FloatingObject(kind="chart", name=title, ...)`，设定合理的行列锚点与尺寸，并通知视图重绘。

### 3.2. Text to Columns Wizard (3 步文本分列向导: `text_to_columns_wizard.py`)
- **Step 1: 原始数据类型**
  - 单选钮 1: 分隔符号 (Delimited: 逗号或制表符等字符分割每个字段)。
  - 单选钮 2: 固定宽度 (Fixed width: 每列字段对齐，并在列间包含空格)。
  - 导入起始行号 `start_row` (QSpinBox)。
  - 底部选区前 10 行文本预览。
- **Step 2: 分隔符 / 分割线设置**
  - Delimited 模式: 复选框 Tab、分号、逗号、空格、其他（输入框），连续分隔符号视为单个处理，文本识别符号（双引号/单引号/无）。
  - Fixed width 模式: 拖动/点击标尺添加分割线。
  - 底部数据分割预览表格（实时更新列分割线）。
- **Step 3: 列数据格式与目标区域**
  - 列数据格式单选钮: 常规 (General)、文本 (Text)、日期 (Date)、不导入此列/跳过 (Do not import column/Skip)。
  - 目标区域引用框 (Destination: 默认起始单元格)。
  - 底部表格选中列时高亮并更新该列的格式设置。
- **确定提交**:
  - 执行分列算法，将当前选定区域的文本行依次拆分，写回到 `SheetDataModel` 中对应的行列单元格，并触发模型变更信号。

### 3.3. Subtotal Dialog (分类汇总: `subtotal_dialog.py`)
- 字段:
  - 分类字段下拉框 `combo_group_by`: 自动提取数据区域第 1 行的列标题。
  - 汇总方式下拉框 `combo_function`: 求和 (SUM), 计数 (COUNT), 平均值 (AVERAGE), 最大值 (MAX), 最小值 (MIN), 乘积 (PRODUCT), 数值计数 (COUNT NUMS), 标准偏差 (STDEV), 方差 (VAR)。
  - 选定汇总项复选列表 `list_subtotal_columns`: 数据区数值列复选。
  - 替换当前分类汇总 `check_replace` (默认勾选)。
  - 每组数据分页 `check_page_break`。
  - 汇总结果显示在数据下方 `check_summary_below` (默认勾选)。
- 按钮: 确定 (OK), 取消 (Cancel), 全部删除 (Remove All)。
- 执行逻辑: 对选中数据区域按分类列分组，在组别变更处插入汇总行，填入对应分类汇总公式 `=SUBTOTAL(function_code, range)`，并在末尾插入总计行。

### 3.4. Consolidate Dialog (合并计算: `consolidate_dialog.py`)
- 字段:
  - 函数下拉框 `combo_function`: 求和、计数、平均值、最大值、最小值、乘积等。
  - 引用位置输入框 `edit_reference`: 支持手动输入或单元格选区拾取。
  - 所有引用位置列表 `list_all_references`: 显示已添加的引用，带“添加(&A)”、“删除(&D)”按钮。
  - 标签位置复选框: 首行 (Top row)、最左列 (Left column)。
  - 创建指向源数据的链接 (Create links to source data)。
- 按钮: 确定、关闭/取消、浏览。
- 执行逻辑: 读取所有引用区域中的数据，按行列标签或位置进行聚合计算，将汇总结果填入当前目标区域。

### 3.5. Scenario Manager (方案管理器: `scenario_manager_dialog.py`)
- 方案列表 `list_scenarios`，显示当前工作表已定义的所有方案。
- 信息展示: 可变单元格 (Changing cells)、批注 (Comment)。
- 按钮:
  - 显示 (Show): 将所选方案的可变单元格值填入工作表。
  - 关闭 (Close)。
  - 添加 (Add...): 弹出“添加方案”子对话框（方案名称、可变单元格、批注、防修改与隐藏保护），随后弹出“方案值”输入框输入每个单元格的值。
  - 删除 (Delete): 删除所选方案。
  - 编辑 (Edit...): 修改所选方案名称、范围与值。
  - 摘要 (Summary...): 生成方案摘要工作表。

### 3.6. Data Table (模拟运算表: `data_table_dialog.py`)
- 字段:
  - 输入引用行的单元格 (Row input cell) - 对应表格上方行表头变量。
  - 输入引用列的单元格 (Column input cell) - 对应表格左侧列表头变量。
- 按钮: 确定、取消。
- 执行逻辑:
  - 读取选区左上角公式，遍历行输入变量列表与列输入变量列表，将变量代入公式单元格重新求值，并将矩阵结果填充至模拟运算表内部单元格。

### 3.7. Protect Sheet / Protect Workbook (保护对话框: `protect_dialog.py`)
- `ProtectSheetDialog`:
  - 密码输入框 `edit_password` (密码掩码)。
  - 复选框 `check_protect`: 保护工作表及锁定的单元格内容。
  - 允许此工作表的所有用户进行复选列表:
    - 选定锁定单元格 (Select locked cells - 默认勾选)
    - 选定未锁定单元格 (Select unlocked cells - 默认勾选)
    - 设置单元格格式 (Format cells)
    - 设置列格式 (Format columns)
    - 设置行格式 (Format rows)
    - 插入列 (Insert columns)
    - 插入行 (Insert rows)
    - 插入超链接 (Insert hyperlinks)
    - 删除列 (Delete columns)
    - 删除行 (Delete rows)
    - 排序 (Sort)
    - 使用自动筛选 (Use AutoFilter)
    - 使用数据透视表 (Use PivotTable reports)
    - 编辑对象 (Edit objects)
    - 编辑方案 (Edit scenarios)
  - 确定时弹出“确认密码”验证对话框。
  - 将保护状态持久化在 `sheet.protection = {"password_hash": ..., "locked": True, "permissions": {...}}`。
- `UnprotectSheetDialog`:
  - 若已设密码，提示输入密码解除保护；密码校验通过后解除保护。
- `ProtectWorkbookDialog`:
  - 密码输入框。
  - 保护工作簿选项: 结构 (Structure - 默认勾选)、窗口 (Windows)。
  - 确定后持久化在 `workbook.protection = {"password_hash": ..., "structure": True, "windows": False}`。

### 3.8. Advanced Filter (高级筛选: `advanced_filter_dialog.py`)
- 方式单选钮:
  - 在原有区域显示筛选结果 (Filter the list, in-place)
  - 将筛选结果复制到其他位置 (Copy to another location)
- 区域输入框:
  - 列表区域 (List range): 待筛选的数据区域。
  - 条件区域 (Criteria range): 包含列标题与筛选条件的区域。
  - 复制到 (Copy to): 目标单元格引用（仅在“复制到其他位置”时可用）。
- 复选框:
  - 选择不重复的记录 (Unique records only)。
- 确定后执行多条件筛选，隐藏不符合条件的行或复制符合条件的唯一记录至目标位置。

### 3.9. Ledger Options (全功能选项: `options_dialog.py`)
- 多标签设计 (QTabWidget)，包含 8 个经典选项卡：
  1. 视图 (View): 显示编辑栏、状态栏；窗口选项：分页符、公式、网格线、行号列标、零值、工作表标签。
  2. 计算 (Calculation): 自动计算、手动计算、保存前重新计算、迭代计算 (最大迭代次数、最大变化值)。
  3. 编辑 (Edit): 单元格拖放功能、按 Enter 键后移动所选单元格（方向：下/右/上/左）、自动设置小数点。
  4. 常规 (General): 新工作簿工作表数、标准字体与字号、默认文件位置。
  5. 自定义序列 (Custom Lists): 经典内置星期与月份序列，支持自定义添加与从单元格导入。
  6. 错误检查 (Error Checking): 启用后台错误检查、规则指示指示灯颜色。
  7. 拼写检查 (Spelling): 忽略大写单词、忽略包含数字的单词。
  8. 安全性 (Security): 打开权限密码、修改权限密码。
- 提供 `get_settings()` 与 `apply_settings()`，并支持 `retranslate_ui()`。

---

## 4. Internationalization (i18n) & Edge Cases

### 4.1. 100% i18n
所有对话框文字、控件标签、按钮、下拉选项均必须经过 `safe_tr(text)` / `tr(text)`，支持中文、英文等地道互译，并包含标准的 `retranslate_ui()` 方法。

### 4.2. Edge Cases (思考领先一步)
1. **空数据区域处理**:
   - 若用户在空工作表或单单元格打开分列向导或图表向导，不得崩溃；默认自动推断当前选区，若无有效数据则给出优雅提示或使用默认范围 `$A$1`。
2. **非法单元格引用与公式语法**:
   - 单元格引用解析使用 `parse_cell_reference` / 正则校验，用户输入非法引用时阻止确定并提示，严禁抛出未捕获异常。
3. **分列越界覆盖**:
   - 文本分列扩展到右侧已有内容的单元格时，弹出标准提示：“是否替换目标单元格内容？” (Do you want to replace the contents of the destination cells?)。
4. **工作表受保护时的操作门禁**:
   - 当 `sheet.protection` 启用时，针对未授权项（例如编辑锁定单元格、删除行、插入列等）进行拦截阻断，并提示工作表受保护。
5. **撤销重做与数据完整性**:
   - 分类汇总、合并计算与分列操作修改网格时，保证原子性操作，不产生悬空状态。

---

## 5. Verification & Testing Plan
- 编写 `tests/gui/test_ledger_dialogs_phase6.py`：
  - 测试所有 9 个对话框/向导的实例化与初值加载。
  - 测试 Chart Wizard 4 步翻页、参数流转与生成 `FloatingObject`。
  - 测试 Text to Columns 3 步向导及分隔符切分算法与填充。
  - 测试 Subtotal 对话框与分组计算。
  - 测试 Consolidate 对话框与多区域引用管理。
  - 测试 Scenario Manager 方案添加、查看与应用。
  - 测试 Data Table 对话框参数校验。
  - 测试 Protect Sheet / Protect Workbook 密码设置、校验与解除保护。
  - 测试 Advanced Filter 条件筛选。
  - 测试 Ledger Options 选项读取与设置保存。
  - 测试所有组件的 `retranslate_ui` 完整性。
- 运行验证命令：
  ```bash
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_ledger_dialogs_phase6.py -v
  ```
