# Specification: TASK-707 (Issue #241) 修复真实工作簿载入后的显示与同步

## 1. Problem Statement & Background
在 ATBOffice 的电子表格模块（Ledger）中，载入真实的 XLSX 工作簿后，存在以下显示与同步问题：
1. **工作簿替换与对象解绑不彻底**：当 `SpreadsheetView.workbook` 被赋予新的 `WorkbookModel` 时，历史工作簿的信号解绑不完整，`GridViewport` 的内部撤销栈（`_undo_stack`）、重做栈（`_redo_stack`）及剪贴板未清空。如果连续打开两个不同工作簿，撤销或切换可能回溯到上一个工作簿的遗留状态。
2. **多视图与图层引用同步缺失**：工作簿替换或活动表切换时，需要保证 `grid`、`editor_controller`、`sheet_tab_bar`、`object_layer` 及 `geometry_mapper` 严格原子同步指向同一活动工作表 `SheetDataModel`，旧活动表的信号连接彻底切断。
3. **XLSX Reader 解析缺失**：
   - 批注（Comments）：`xl/comments*.xml` 与 `xl/drawings/vmlDrawing*.vml` 未被解析，导致类似 `poi__SimpleWithComments.xlsx` 这样的语料无法显示批注红色三角角标及批注内容。
   - 冻结窗格（Freeze Panes）：工作表 `<sheetViews><sheetView>` 中的 `<pane xSplit="..." ySplit="..." state="frozen">` 未被解析赋值到 `sheet.freeze_cols` 和 `sheet.freeze_rows`。
   - 缩放比例（Zoom）：工作表 `<sheetView zoomScale="...">` 未被解析存储，且 `GridViewport` 缺失 `set_zoom` 及 `zoom` 属性与缩放渲染支持。
4. **公式编辑后缓存值与重算合同**：
   - 载入时保留 Excel 预计算的 `<v>` 缓存值。
   - 用户编辑公式后，必须通过附带当前工作表与工作簿上下文的 `EvalContext` 重新计算。
   - 对于语法错误或未知函数，重算结果必须返回明确的错误值（如 `#NAME?`、`#VALUE!`），严禁伪装为空白或丢失公式。
5. **样本基准对齐**：
   - `libreoffice__cell-value.xlsx`：各类数值与长文本正确载入与格式化。
   - `poi__SimpleWithComments.xlsx`：批注作者与文本正确载入并可在界面呈现。
   - `poi__GroupTest.xlsx`：隐藏行与行高正确解析，视口中正确跳过隐藏行。
   - `libreoffice__conditional_fmt_origin.xlsx`：条件格式规则载入并能在视口计算显示背景色。
   - `libreoffice__Pivot2_Row.xlsx`：透视表呈现数据与底层的 `PivotContainer` 缓存清晰解耦并持久化。

---

## 2. Technical Design & Architecture

### 2.1 XLSX Reader 增强 (`src/atboffice/modules/spreadsheet/io/xlsx_reader.py`)
- **批注解析**：
  - 在 `_parse_worksheet` 中，通过解析 `sheet_path` 对应的 `_rels/*.rels`，定位关系类型为 `.../relationships/comments` 的目标文件（如 `xl/comments1.xml`）。
  - 解析 `<authors><author>` 列表与 `<commentList><comment ref="..." authorId="...">`。
  - 通过 `parse_cell(ref)` 转换为 `(r, c)`。
  - 提取 `<text>` 内的所有 `<t>` 文本并拼接，得到批注正文。
  - 检查关联的 `vmlDrawing`，匹配 `<x:Row>`、`<x:Column>` 与 `<x:Visible>`，标记 `visible=True`。
  - 调用 `sheet.set_comment(r, c, text, author=author, visible=visible)`。
- **冻结窗格与视图参数**：
  - 在 `_parse_worksheet` 中，扫描 `<sheetViews><sheetView>` 下的 `<pane>` 元素。
  - 若 `state` 为 `frozen` 或 `frozenSplit`，提取 `xSplit` 与 `ySplit`，设置 `sheet.freeze_cols = int(float(xs))`，`sheet.freeze_rows = int(float(ys))`。
  - 若有 `zoomScale` 属性，设置 `sheet.extra["zoom"] = int(zoomScale)`。

### 2.2 视图与图层同步 (`src/atboffice/modules/spreadsheet/view.py`)
- 在 `SpreadsheetView.workbook.setter` 中：
  - 彻底断开旧工作簿的 `active_sheet_changed` 与 `sheet_removed` 信号连接。
  - 调用 `self.grid.clear_undo_stack()`，清空 `_undo_stack` 与 `_redo_stack`，重置 `_internal_clipboard = None`。
  - 清空 `_sheet_selections`。
  - 更新 `sheet_tab_bar.set_workbook(value)`。
  - 绑定新工作簿并触发 `_on_active_sheet_changed(self._workbook.active_sheet_index)`。
- 在 `_on_active_sheet_changed(index)` 中：
  - 取出 `active_sheet = self._workbook.active_sheet` 与 `active_sel`。
  - 同步调用 `self.grid.set_model_and_selection(active_sheet, active_sel)`。
  - 同步调用 `self.editor_controller.set_model_and_selection(active_sheet, active_sel)`。
  - 同步调用 `self.object_layer.set_model(active_sheet)`。
  - 断言验证：`grid.model`、`editor_controller.model`、`object_layer.model`、`sheet_tab_bar.active_sheet` 均恒等引用同一活动工作表实例。

### 2.3 视口与缩放支持 (`src/atboffice/modules/spreadsheet/views/grid_viewport.py`)
- 添加 `clear_undo_stack()` 方法，清空撤销与重做历史。
- 添加 `zoom` 属性与 `set_zoom(zoom: float)` 方法：
  - 缩放范围限制在 `0.1` 至 `4.0`。
  - 缩放变更时，取消当前交互拖拽（`cancel_drag("api")`），更新滚动条配置，触发视口重绘。
  - `set_model_and_selection` 时，检查 `model.extra.get("zoom")`，自适应恢复工作表存储的缩放比例。

### 2.4 公式重算与错误合同 (`src/atboffice/modules/spreadsheet/views/editor_controller.py`)
- 在 `commit()` 中：
  - 当提交以 `=` 开头的公式时，构造附带工作簿与活动表的 `EvalContext(workbook=wb, current_sheet=self.model.name, sheet=self.model)`。
  - 运行 `ast = parse(formula_body)` 并执行 `evaluate_ast(ast, ctx)`。
  - 若求值成功且为数值/字符串，存储到 `cell.value`；若为 `ExcelError`，将其字符串形式（如 `#NAME?`、`#REF!`、`#VALUE!`）赋予 `cell.value`。
  - 若解析失败或发生未捕获异常，`cell.value = "#VALUE!"`，保留 `cell.formula = formula_body`，绝不置空。

---

## 3. Edge Cases & Risk Analysis (Think One Step Ahead)
1. **多工作簿连续打开与内存泄漏**：旧工作簿若未断开 signal，其回调会引用被销毁的 QWidget 或更新错误的工作簿。必须使用 `try...except` 安全断开所有旧信号。
2. **旧工作簿撤销跨越**：用户在 A 文件撤销，若撤销栈未清空，会将 A 的修改误应用到 B。必须在工作簿切换和表切换时清理或隔离撤销栈。
3. **非标准 XML 结构与缺失命名空间**：某些第三方导出的 XLSX 缺少 relationships 或没有作者列表，解析 comments 时必须做好安全降级（default author=""，default visible=False）。
4. **冻结窗格越界**：`xSplit` 或 `ySplit` 超过最大行列数时，做边界截断 `max(0, min(val, max_limit))`。
5. **未支持特性的公式**：如未知函数，Excel 规范显示 `#NAME?`。我们的求值引擎如果抛异常，绝不能让单元格变为空白，必须显式显示 `#VALUE!` 或 `#NAME?`。

---

## 4. Verification Plan
- 运行定向回归测试：
  ```bash
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_xlsx_render.py -ra
  ```
- 验证所有 5 个真实语料加载无报错，内容与批注、隐藏行、条件格式完全匹配。
- 验证连续打开两个工作簿后切表、撤销、缩放无旧数据残留。
- 验证公式重算合同。
- 运行全量测试确认无回归。
