# Design Specification: Issue #132 - 全面接线 Ledger 工具栏动作至单元格格式化、排序与公式计算

## 1. Overview & Objectives

Ledger 目前已装配全部 8 套 Excel 2003 Luna 风格工具栏（常用 Standard、格式 Formatting、边框 Borders、公式审核 Auditing、审阅 Reviewing、列表 List、图表 Chart、绘图 Drawing），但除基础剪切板（cut/copy/paste）和字体粗斜体（bold/italic/underline）外，超过 85% 的常用动作未做真实业务逻辑接线。

本规范将全面补齐 Ledger 工具栏与电子表格视图（`SpreadsheetView`）、网格视口（`GridViewport`）、单元格模型（`SheetDataModel`）、计算核心（`calc/`）以及浮动对象层（`SpreadsheetObjectLayer`）的双向接线：
1. **自动求和与公式填充（AutoSum & Formula Calculation）**：智能嗅探上方与左侧连续数值单元格，自动填入 `=SUM(...)` / `=AVERAGE(...)` 等公式并更新单元格。
2. **快速排序（Quick Sort）**：按选区首列执行快速升序/降序重排，自动保持整行数据与样式关联。
3. **数字格式化快捷动作（Number Formatting）**：实现货币（`$`）、百分比（`%`）、千位分隔符（`,`）与增减小数位数。
4. **对齐与合并居中（Alignment & Merge & Center）**：实现左对齐、居中、右对齐，以及多单元格合并及居中的状态切换与反向同步。
5. **边框预设与管理（Borders Presets）**：接入无边框、外侧框线、粗外框、全框线、双下框线等边框样式。
6. **绘图与浮动对象（DrawingML & Floating Objects）**：连接绘图工具栏开关、图形/文本框/图片插入与层叠排序。
7. **双向状态同步（Two-way State Synchronization）**：选区改变时，双向刷新格式工具栏字体、字号、对齐、加粗倾斜、合并居中按钮状态，以及根据活动对象动态激活图表工具栏。

---

## 2. Architecture & Modules Design

```
+------------------------------------------------------------------------+
|                              LedgerWindow                              |
|  - action_registry: ActionRegistry                                     |
|  - toolbars: dict[str, OfficeToolBar] (8 toolbars cluster)             |
|  - spreadsheet_view: SpreadsheetView                                   |
|      +-- grid: GridViewport                                            |
|      +-- model: SheetDataModel                                         |
|      +-- selection: SelectionModel                                     |
|      +-- editor_controller: EditorController                           |
|      +-- formula_bar: FormulaBar                                       |
|      +-- object_layer: SpreadsheetObjectLayer                          |
+-----------------------------------+------------------------------------+
                                    | Dispatches actions & syncs states
                                    v
+------------------------------------------------------------------------+
|                      Ledger Operations & Handlers                      |
|  1. AutoSum Engine: sniff_contiguous_numbers -> build formula -> eval  |
|  2. Sort Engine: sort_sheet_range with header detection                |
|  3. Number Formatting: currency, percent, comma, inc/dec decimals      |
|  4. Alignment & Merge: align (left/center/right), toggle_merge_center  |
|  5. Border Presets: thin, thick, double, outline, all, none            |
|  6. Drawing & Objects: add_object (shape/textbox/image/chart), z-order |
|  7. Reverse State Sync: selection_changed -> refresh controls          |
+------------------------------------------------------------------------+
```

### 2.1 Action ID Mapping & Handlers Table

| Toolbar | Action ID / Control | Handler Method / Target Component |
|---------|---------------------|-----------------------------------|
| **常用 Standard** | `autoSum` | `auto_sum(fn="SUM")`: 智能识别上方或左侧连续数值区域生成公式 |
| | `sortAsc`, `sortDesc` | `quick_sort(desc: bool)`: 扩展选区或基于单列执行全行排序 |
| | `tb_drawing` | `toggle_drawing_toolbar()`: 切换底部绘图工具栏可见性 |
| | `hyperlink` | `insert_hyperlink_dialog()`: 插入超链接 |
| | `chartWizard` | `create_or_insert_chart()`: 插入浮动统计图表并激活图表上下文 |
| | `formatPainter` | `toggle_format_painter()`: 启用格式刷复制源单元格样式 |
| | `print`, `printPreview` | `open_print_dialog()`, `open_print_preview()` |
| | `spelling` | `open_spelling_dialog()`: 拼写检查 |
| | `Ledger_ZoomCombo` | `set_zoom(val)`: 调整网格缩放比率 |
| **格式 Formatting** | `Ledger_FontCombo`, `Ledger_SizeCombo` | `set_font_family(name)`, `set_font_size(pt)` |
| | `alignLeft`, `alignCenter`, `alignRight` | `set_horizontal_alignment(align: str)` |
| | `mergeCenter` | `toggle_merge_and_center()`: 切换选区合并与解除合并 |
| | `currencyStyle` | `apply_number_format("$#,##0.00")` |
| | `percentStyle` | `apply_number_format("0%")` |
| | `commaStyle` | `apply_number_format("#,##0.00")` |
| | `incDecimal`, `decDecimal` | `change_decimal_places(delta: int)` |
| | `incIndent`, `decIndent` | `change_cell_indent(delta: int)` |
| | `bordersApply` | `apply_border_preset(preset_key)` |
| | `Ledger_FillColorBtn`, `Ledger_FontColorBtn` | `apply_fill_color(c)`, `apply_font_color(c)` |
| **边框 Borders** | `borderNone`, `borderOutline`, `borderThickOutline`, `bordersPalette` | `apply_border_preset(...)` |
| **公式审核 Auditing** | `tracePrecedents`, `traceDependents`, `removeArrows` | 追踪单元格引用关系并绘制/清除箭头 |
| | `evaluateFormula` | `evaluate_active_cell_formula()`: 计算求值 |
| | `insertComment`, `validation`, `circleInvalid`, `clearCircles` | 批注与数据有效性动作 |
| **审阅 Reviewing** | `rev_insertComment`, `showHideComment`, `deleteComment`, `showComments` | 审阅批注管理 |
| **列表 List** | `totalRow` | 切换列表底部汇总计算行 |
| **图表 Chart** | `formatObject` | 设置浮动图表对象属性 |
| **绘图 Drawing** | `insertShape`, `insertTextBox`, `insertPicture` | 在 `SpreadsheetObjectLayer` 创建对应浮动图形 |
| | `Ledger_DrawFillColor` | 更改当前选中浮动图形填充颜色 |
| | "置于顶层", "置于底层" | `bring_to_front()`, `send_to_back()` |

---

## 3. Detailed Technical Implementation

### 3.1 AutoSum Sniffing & Evaluation
- **单单元格选中时（`r1 == r2 and c1 == c2`）**：
  1. 首先向上探索：从 `r - 1` 向上检查连续数值单元格（`is_number(r_check, c)`），直到遇到非数值或表头。若探测到长度 $\ge 1$ 的连续数字，取该区间 `(top_r, c) .. (r - 1, c)` 生成公式 `f"=SUM({col_name(c)}{top_r+1}:{col_name(c)}{r})"`;
  2. 若上方无连续数值，则向左探索：从 `c - 1` 向左检查连续数值单元格，取 `(r, left_c) .. (r, c - 1)` 生成公式 `f"=SUM({col_name(left_c)}{r+1}:{col_name(c-1)}{r+1})"`;
  3. 若均无数值，则默认填入 `f"={fn}()"`;
  4. 计算当前公式数值，写入目标单元格并刷新网格视口与公式栏。
- **多单元格选区时（`r1 != r2 or c1 != c2`）**：
  - 若选区下方存在空行或最后一行为空，在底部各列写入各列对应垂直求和公式。

### 3.2 Quick Sort Algorithm
- 若当前仅选中单个单元格：利用 `open_sort_dialog` 的扩散算法嗅探周围连续数据块，确定数据范围 `(r1, c1, r2, c2)`。
- 判断第一行是否为表头（`has_header`，若第一行含字符串而后续为数值）。
- 调用 `sort_sheet_range(model, r1, c1, r2, c2, [(target_col, desc)], has_header=has_header)`。
- 刷新视口并标记文档为 dirty。

### 3.3 Number Formatting & Decimals
- 货币：`"$#,##0.00"`（或带负数括号的 Excel 规范格式）
- 百分比：`"0%"` 或 `"0.00%"`
- 千位符：`"#,##0.00"`
- 增减小数位：
  - 解析当前单元格 `format_code` 中的小数位数；
  - 若当前为 `General`，增加一位变为 `"0.0"`；
  - 若已有小数部分（如 `"#,##0.00"`），增加一位变为 `"#,##0.000"`，减少一位变为 `"#,##0.0"`，归零时为 `"#,##0"`。

### 3.4 Alignment & Merge and Center
- `mergeCenter`:
  - 检查选区 `(r1, c1, r2, c2)` 中是否有单元格已处于合并区域：
    - 若已合并，则调用 `model.remove_merge(r, c)` 解除合并；
    - 若未合并且 `r1 != r2 or c1 != c2`，调用 `model.add_merge(r1, c1, r2, c2)`，并将所有单元格水平对齐设为 `"center"`；
  - 保持选区及网格视口同步刷新。

### 3.5 Border Presets
通过 `BorderStyle(style=..., color=...)` 作用于单元格边框：
- `none`: 清空四边框线；
- `outline` / `thickBox`: 外侧框线（仅对选区最上行设置 top，最下行设置 bottom，最左列设置 left，最右列设置 right）；
- `all`: 对选区内全部单元格填充四边 thin 框线；
- `bottom` / `thickBottom` / `bottomDouble`: 对选区最下行设置对应底框线。

### 3.6 Two-way Formatting Status Synchronization
- 连接 `spreadsheet_view.selection.selection_changed` 和 `active_cell_changed` 至 `_sync_formatting_toolbar_states()`：
  - 读取当前活动单元格 `CellData`：
    - `act_bold.setChecked(cell.bold)`
    - `act_italic.setChecked(cell.italic)`
    - `act_underline.setChecked(cell.underline)`
    - `alignLeft.setChecked(cell.align_h == "left")`
    - `alignCenter.setChecked(cell.align_h == "center")`
    - `alignRight.setChecked(cell.align_h == "right")`
    - `mergeCenter.setChecked(model.is_merged(r, c))`
    - 下拉框安全同步（使用 `blockSignals(True)` 避免循环触发）：`font_combo.setCurrentText(cell.font_family)`, `size_combo.setCurrentText(str(cell.font_size))`。
- 浮动对象选中信号 `object_layer.object_selected` 连接至 `update_context_toolbars`：
  - 选中 `chart` 类型时唤出图表工具栏。

---

## 4. Verification Plan

1. 执行已有回归测试：
```bash
PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_ledger_toolbars.py -v
```
2. 构建全新完备接线测试套件 `tests/ui/test_ledger_toolbar_wiring.py`，覆盖：
   - AutoSum 自动嗅探计算与单元格公式更新；
   - 快速升序/降序重排数据行；
   - 货币、百分比、千分位、增减小数位渲染；
   - 多单元格合并居中及反向解除合并；
   - 边框预设应用与清除；
   - 浮动图形与图表插入联动；
   - 光标移动时工具栏双向状态同步。
