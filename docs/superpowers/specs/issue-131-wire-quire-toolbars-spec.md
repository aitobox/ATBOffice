# Design Specification: Issue #131 - 全面接线 Quire 工具栏动作至画布排版与 DOM 控制器

## 1. Overview & Objectives

Quire 目前已装配全部 10 套 Word 2003 Luna 风格工具栏（常用、格式、表格和边框、审阅、大纲、页眉和页脚、绘图、邮件合并、图片、艺术字），但绝大多数动作（除 new/open/save/cut/copy/paste 等基础 15 个动作外）未进行真实业务逻辑接线，处于 fallback 占位状态。

本规范将全面补齐 Quire 工具栏与核心画布/DOM 的双向接线：
1. **指令分发（Forward Dispatch）**：将 `ActionRegistry` 中的动作全面分发至排版引擎、表格控制器、审阅引擎及视图控制器。
2. **状态同步（Reverse State Sync）**：光标移动（`caret_moved`）时，根据当前选区与段落属性自动更新工具栏按钮状态（加粗/倾斜/下划线、对齐方式、字号/字体下拉框、列表按钮高亮等）。
3. **上下文感知（Contextual Toolbar Activation）**：光标处于表格内部时自动就绪并弹出「表格和边框」工具栏；离开时恢复上下文。
4. **审阅协同（Review & Revision Sync）**：接受/拒绝修订与新建/删除批注动作与右侧审阅窗格及底质修订模型无缝联动。

---

## 2. Architecture & Modules Design

```
+------------------------------------------------------------------------+
|                              QuireWindow                               |
|  - action_registry: ActionRegistry                                     |
|  - toolbars: dict[str, OfficeToolBar] (10 toolbars cluster)            |
|  - writer_view: WriterView                                             |
|      +-- canvas_view: WriterCanvasView                                 |
|      |     +-- controller: CaretController                             |
|      |     +-- doc: Document                                           |
|      +-- review_pane: ReviewPane                                       |
|      +-- mailmerge_engine: MailMergeEngine                             |
+-----------------------------------+------------------------------------+
                                    | Dispatches actions & syncs states
                                    v
+------------------------------------------------------------------------+
|            WriterEditOps / Canvas Controller Extensions                |
|  1. Paragraph Formatting: align (left/center/right/both), indent, sp   |
|  2. Character Formatting: bold, italic, underline, strike, vert, font  |
|  3. List Formatting: bullets, numbering (numId, lvl)                   |
|  4. Table Operations: insert_row/col, delete_row/col, merge, split     |
|  5. Revision / Comments: accept, reject, insert_comment, toggle_track  |
|  6. Outline Navigation: promote, demote, move_up, move_down            |
|  7. Zoom & View: zoom_in, zoom_out, set_zoom, view reading             |
+------------------------------------------------------------------------+
```

### 2.1 Core Subsystems & Action Mapping

| Subsystem | Actions & Controls | Target Implementation / Controller Method |
|-----------|--------------------|--------------------------------------------|
| **段落排版** | `alignLeft`, `alignCenter`, `alignRight`, `justify` | `canvas_view.set_paragraph_alignment(jc: str)` |
| | `incIndent`, `decIndent` | `canvas_view.change_indent(delta_pt: float)` |
| | 行距下拉菜单 ("1.0", "1.5", "2.0", "2.5", "3.0") | `canvas_view.set_line_spacing(val: float)` |
| **字符格式** | `bold`, `italic`, `underline`, `strike`, `superscript`, `subscript` | `canvas_view.toggle_character_format(attr: str)` |
| | `Quire_FontCombo`, `Quire_SizeCombo` | `canvas_view.set_font_family(name)`, `canvas_view.set_font_size(pt)` |
| | `Quire_HighlightBtn`, `Quire_FontColorBtn` | `canvas_view.set_highlight_color(color)`, `canvas_view.set_font_color(color)` |
| **项目符号与列表** | `bullets`, `numbering` | `canvas_view.toggle_list_style(kind: str)` |
| **表格控制器** | `mergeCells`, `splitCells` | `canvas_view.merge_table_cells()`, `canvas_view.split_table_cells()` |
| | 插入行/列菜单项 ("在上方插入行", "在下方插入行", "在左侧插入列", "在右侧插入列") | `canvas_view.insert_table_row(above: bool)`, `canvas_view.insert_table_col(left: bool)` |
| | `distRows`, `distCols`, `sortAsc`, `sortDesc`, `autoSum` | `canvas_view.distribute_table_rows()`, `distribute_table_cols()`, `sort_table()`, `auto_sum_table()` |
| **审阅与修订** | `acceptChange`, `rejectChange` | `canvas_view.accept_current_revision()`, `reject_current_revision()` |
| | `insertComment`, `trackChanges`, `reviewingPane` | `canvas_view.insert_comment()`, `toggle_track_changes()`, `toggle_review_pane()` |
| | `prevChange`, `nextChange` | `canvas_view.navigate_revision(delta: int)` |
| **大纲级别** | `promote`, `demote`, `promoteH1`, `demoteBody`, `moveUp`, `moveDown` | `canvas_view.change_outline_level(delta: int)`, `move_paragraph(delta: int)` |
| | `Quire_OutlineLevelCombo` | `canvas_view.set_outline_level(level: int | None)` |
| **视图与缩放** | `zoom_in`, `zoom_out`, `zoom_reset`, `Quire_ZoomCombo` | `canvas_view.set_zoom(val: float)` |
| | `viewReading`, `showMarks`, `docMap` | 切换视图与文档辅助显示 |
| **邮件合并** | `mmMainDoc`, `mmOpenSource`, `mmRecipients`, `mmAddress`, `mmGreeting`, `mmInsertField`, `mmViewData`, `mmFirst`, `mmPrev`, `mmNext`, `mmLast`, `mmMergeNew`, `mmMergePrint` | 调用 `writer_view` 现有邮件合并向导与记录步进接口 |
| **工具栏切换** | `tb_tables`, `tb_drawing` | `set_toolbar_mode("tables", ...)`, `set_toolbar_mode("drawing", ...)` |

---

## 3. Detailed Technical Design

### 3.1 Range Formatting Engine (`format_range` / `format_paragraphs`)
实现规范的范围排版辅助逻辑：
- 当光标折叠（`selection.is_collapsed`）时：
  - 段落属性直接作用于当前段落 `controller.pos.para_id`；
  - 字符属性作用于当前光标所在 Run 及段落默认 `p.r_pr`；
- 当存在多字/多段选区时：
  - 通过 `doc.order(a, b)` 排序选区端点；
  - 段落属性遍历作用于 `paras_between(doc, start_p, end_p)`；
  - 字符属性在起止段落执行 `split_at` 拆分 Run 边界，遍历区间内所有 Run 变更属性，最后执行 `normalize(p)` 合并连续同格式 Run；
- 排版变更后自动调用 `reindex(doc)` 并触发 `caret_controller.repaginate_and_refresh()`，保证画面即时重绘与标尺刷新。

### 3.2 Table Context & In-Table Detection
利用 `info(doc, pos.para_id)` 获取段落容器层级：
```python
def get_current_table_context(self) -> dict[str, Any] | None:
    inf = info(self.doc, self.controller.pos.para_id)
    if not inf or not inf.get("parents"):
        return None
    for p in inf["parents"]:
        if isinstance(p, dict) and "tbl" in p:
            return {
                "tbl": p["tbl"],
                "row": p.get("row"),
                "cell": p.get("cell"),
            }
    return None
```
在 `_on_caret_moved` 时判断 `get_current_table_context() is not None`：
- 若为 True，自动调用 `self.update_context_toolbars({"in_table": True})`，唤出表格和边框工具栏；
- 若为 False，自动调用 `self.update_context_toolbars({"in_table": False})`。

### 3.3 Two-Way State Synchronization
当 `caret_moved` 触发时，`QuireWindow` 读取当前光标处属性并阻断信号更新工具栏控件状态：
1. **加粗/倾斜/下划线**：
   - 提取光标所在 Run 的 `r_pr.b`, `r_pr.i`, `r_pr.u != "none"`；
   - 更新对应 QAction 的 `setChecked(bool)`。
2. **对齐方式**：
   - 提取段落 `p_pr.jc`（"left", "center", "right", "both"）；
   - 更新 `alignLeft`, `alignCenter`, `alignRight`, `justify` 动作的 `setChecked`。
3. **字号与字体下拉框**：
   - 阻塞下拉框信号，设置 `font_combo.setCurrentText(font_name)` 与 `size_combo.setCurrentText(str(sz))`。
4. **修订与审阅状态**：
   - 检查 `is_tracking(doc)`，更新 `trackChanges` 动作勾选态；
   - 更新审阅窗格可见性联动。

---

## 4. Edge Cases & Error Handling

1. **空文档或单空段落**：
   - 光标在首个空段落时执行排版，不应抛出 IndexError 或 NoneType 异常；
2. **跨表格与非表格选区**：
   - 选区同时包含普通段落与表格单元格时，段落排版仅作用于可排版段落，表格操作仅在明确单表上下文激活；
3. **表格合并与拆分边界**：
   - 单单元格执行拆分至少分为 1 行 2 列；非连续或跨非矩形区域合并进行安全防御；
4. **递归信号防范（Signal Loops）**：
   - 在光标移动更新 Font/Size/Style/Zoom 下拉框文本时，通过 `blockSignals(True)` 防止反向触发格式修改。

---

## 5. Verification Plan

1. **单元与集成测试**：
   - 执行已有的 `tests/ui/test_quire_toolbars.py`，保证不发生功能退化；
   - 新建 `tests/ui/test_quire_toolbar_wiring.py`：
     - 测试加粗、倾斜、下划线点击触发及 DOM 属性变更；
     - 测试居中、左对齐、居右、两端对齐及缩进；
     - 测试字号、字体变更及下拉框防回环联动；
     - 测试光标进入表格时表格工具栏自动弹出；
     - 测试表格插入行/列、删除行/列、合并单元格；
     - 测试审阅与修订切换及批注插入；
     - 测试大纲提升与降级。
2. **命令验证**：
   ```bash
   PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_quire_toolbars.py tests/ui/test_quire_toolbar_wiring.py -v
   ```
