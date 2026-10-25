# Specification: Issue #13 [Ledger] 原位单元格编辑、公式栏双向绑定与自动计算状态栏

## 1. Overview & Objectives

完整实现 Excel 2003 / ATBOffice Ledger 电子表格的原位编辑交互闭环：
1. **原位浮层编辑器 (In-Cell Editor) 与控制器 (`EditorController`)**：双击单元格、按 F2 或直接键入字符在网格激活原位编辑浮层输入框，支持自适应内容扩张排版。
2. **公式编辑栏 (`FormulaBar`) 与双向数据绑定**：包含名称框 (NameBox)、取消 (X)、确认 (✓) 与插入函数 (fx) 按钮及公式输入框；与原位浮层编辑器进行严格的毫秒级双向无缝绑定。
3. **公式录入点选模式 (Point Mode) 与多色引用高亮外框**：在录入以 `=` 开头的公式时，点击或拖拽网格单元格自动插入对应的引用地址（如 `A1`、`B2:C5`），并在网格画布同步绘制多色高亮外边框 (`#0000FF`, `#008000`, `#9900CC` 等)。
4. **AutoCalculate 自动计算状态栏 (`StatusBar`)**：实时响应选区变动，异步/即时聚合选区内数值的求和 (Sum)、平均值 (Average)、计数 (Count)、数值计数 (Count Nums)、最大值 (Max)、最小值 (Min)，并提供右键功能切换菜单及编辑模式状态指示（就绪/输入/编辑/点选）。

---

## 2. Architecture & Components

```
┌────────────────────────────────────────────────────────┐
│ MainWindow / Shell                                     │
│  ├─ SpreadsheetView                                    │
│  │   ├─ FormulaBar (NameBox, Cancel, Commit, Fx, Edit) │
│  │   ├─ GridViewport (Virtualized Canvas)              │
│  │   │   └─ InCellEditor (Floating QLineEdit Overlay)  │
│  │   └─ EditorController (Mode, Pointing, Highlights)  │
│  └─ StatusBar (Mode, AutoCalculate, Lock Indicators)   │
└────────────────────────────────────────────────────────┘
```

### 2.1 FormulaBar (`src/atboffice/modules/spreadsheet/views/formula_bar.py`)
- **NameBox** (`QLineEdit`):
  - 显示当前选区名称/地址（如 `A1` 或拖拽选区时的 `2R x 3C`）。
  - 用户可手动键入地址（如 `C10` 或 `B2:D6`）并回车直接跳转并选中该区域。
- **Action Buttons**:
  - `btn_cancel`: 红色 "✕" 按钮，取消当前编辑（同 Esc 快捷键），编辑未激活时处于禁用/半透明状态。
  - `btn_commit`: 绿色 "✓" 按钮，提交当前编辑（同 Enter 快捷键），编辑未激活时处于禁用/半透明状态。
  - `btn_fx`: 经典蓝斜体 "fx" 按钮，点击进入公式向导或自动补齐 `=` 开始录入公式。
- **Formula Input** (`QLineEdit`):
  - 呈现并编辑单元格公式 (`=SUM(...)`) 或文本/数值。
  - 与网格原位编辑浮层保持 100% 实时双向同步。

### 2.2 EditorController (`src/atboffice/modules/spreadsheet/views/editor_controller.py`)
- **状态机模式 (`EditorMode`)**:
  - `READY`: 空闲就绪状态。
  - `ENTER`: 字符键入启动覆盖编辑模式。
  - `EDIT`: F2 或双击启动的光标原位追加/修改模式。
  - `POINT`: 公式录入状态且光标位于操作符/逗号/左括号之后，允许点击网格点选单元格插入引用。
- **原位浮层 (`InCellEditor`)**:
  - 继承自 `QLineEdit`，绝对定位在 `GridViewport.viewport()` 之上。
  - 根据单元格字体族、字号、加粗、倾斜、背景色与对齐方式动态渲染样式。
  - 随着输入内容宽度自适应增加宽度（向右扩展），避免文本被截断。
- **点选与引用计算 (`Formula Pointing`)**:
  - 侦测公式前缀 (`=`) 及操作数插入位置 (`operand_at()`)。
  - 当在网格上单击/拖选时，自动在公式当前插入点追加或替换引用（如 `A1` 或 `A1:B3`）。
  - 使用 `src/atboffice/modules/spreadsheet/calc/parser.py` 中的 `tokenize()` 解析公式中的所有 `ref` 标记，生成引用高亮列表 (`ReferenceHighlight`)。
- **高亮外边框联动**:
  - 将高亮列表输出至 `GridViewport`，在 `paintEvent` 中以 2px 彩色边框（按色盘 `['#0000FF', '#008000', '#9900CC', '#800000', '#00CC33', '#CC6600', '#CC0099']` 循环赋色）精确包裹对应的网格单元格。

### 2.3 StatusBar (`src/atboffice/ui/components/status_bar.py`)
- **Mode Indicator**:
  - 左侧展示当前工作模式：“就绪” (Ready)、“输入” (Enter)、“编辑” (Edit)、“点选” (Point)。
- **Status / Info Message**:
  - 中间弹性区域，展示上下文提示与操作提示。
- **AutoCalculate Indicator**:
  - 监听选区变化与模型单元格更新。
  - 支持函数切换：
    - `NONE`: 不显示
    - `AVERAGE`: `平均值={value}`
    - `COUNT`: `计数={count_nums}` (仅统计数值单元格)
    - `COUNTA`: `计数={count_all}` (统计非空单元格)
    - `MAX`: `最大值={max}`
    - `MIN`: `最小值={min}`
    - `SUM`: `求和={sum}` (默认)
  - 仅当选区单元格数量 > 1 时显示聚合结果，单单元格时隐藏。
  - 支持右键呼出快捷菜单切换聚合计算函数。
- **Lock Indicators**:
  - 右侧提供大写锁定 (CAPS)、数字锁定 (NUM)、滚动锁定 (SCRL) 经典状态槽。

---

## 3. Edge Cases & Robustness Analysis

1. **编辑同步时死循环问题 (Echo Loop Prevention)**:
   - 原位输入框与公式栏输入框双向监听 `textChanged`。必须通过内部 `_syncing` 互斥保护标志，防止因双向赋值引发信号递归循环。
2. **公式中的字符串字面量误判**:
   - 如果公式文本为 `="A1 + B1"`，双引号内部的 `A1` 是字符串而非单元格引用，不能误触发高亮或被点选替换。利用已有的 Pratt 词法分析器 `tokenize()` 准确区分 `ref` 与 `str`。
3. **滚动与缩放自适应 (Viewport Scroll / Reveal)**:
   - 当在浮层编辑时滚动滚动条，浮层位置必须随之同步更新（计算 `col_pos - scroll_x`, `row_pos - scroll_y`）；若滑出可视区域需合理裁剪或隐藏。
4. **单元格跨越与空值处理**:
   - 多选区包含空单元格、文本单元格、错误值 (`#DIV/0!`, `#VALUE!`) 时，AutoCalculate 计算 SUM/AVERAGE 应跳过文本与空单元格；若包含显式错误，展示为空或遵循 Excel 规范处理。
5. **名称框非法地址容错**:
   - 用户在名称框输入非法字符串（如 `ZZZ99999999` 或非法字符）时，优雅恢复为原先的有效单元格地址，不发生崩溃或程序异常。
6. **国际化与多语言 (i18n)**:
   - 全部控件文案、右键菜单项、状态栏指示器均采用 `safe_tr()` 包装并提供地道的中英文对照。

---

## 4. Verification Plan

- 编写完整的自动化测试 `tests/gui/test_editor_and_status_bar.py`，基于 `pytest-qt` 测试：
  1. `FormulaBar` 初始化、名称框地址显示与手动跳转定位。
  2. 原位编辑浮层唤出（双击与 F2）、文本双向同步与回车提交。
  3. 公式录入点选引用自动插入（如点选 `C2` 插入 `C2`，拖拽选区插入 `C2:D4`）。
  4. 引用高亮色框数据生成与绘制验证。
  5. `StatusBar` 模式切换指示与 AutoCalculate 选区求和/平均值/计数聚合及菜单切换。
