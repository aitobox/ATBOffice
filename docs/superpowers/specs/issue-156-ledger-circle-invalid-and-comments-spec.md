# Technical Specification: Ledger 数据有效性红圈圈释 (circle_invalid) 与单元格批注角标

## 1. Context & Objectives
- **GitHub Issue**: #156
- **Epic**: Phase 4 (#151)
- **Problem Statement**:
  在前期开发中，`DataValidationDialog` 已经具备完善的 UI 及检验能力，但在 `src/atboffice/ui/shell/ledger_window.py` 中，`data_validation()`、`circle_invalid()`、`clear_circles()`、`insert_comment()`、`show_hide_comment()`、`delete_comment()`、`toggle_show_all_comments()` 仍为空桩，且单元格批注未接入数据模型与视图。本规范旨在完成数据有效性视觉圈释与单元格批注的完整交互与渲染体系。

## 2. Architecture & Data Structures

### 2.1 Cell Comments Model
在 `src/atboffice/modules/spreadsheet/models/sheet_model.py` 中增加批注数据模型：
```python
@dataclass
class CellComment:
    """Cell comment/annotation."""
    text: str
    author: str = ""
    visible: bool = False
```
并在 `SheetDataModel` 中增加：
- `self.comments: dict[tuple[int, int], CellComment] = {}`
- `self.invalid_circles: list[tuple[int, int]] = []`
- `self.show_all_comments: bool = False`
- `set_comment(r, c, text, author, visible) -> CellComment`
- `get_comment(r, c) -> CellComment | None`
- `delete_comment(r, c) -> bool`
- `has_comment(r, c) -> bool`

### 2.2 Data Validation Dialog Binding
在 `ledger_window.py:data_validation()` 中：
- 读取当前选区（active cell 与 primary range）。
- 如果当前单元格已有规则，通过 `sheet.get_validation_at(r, c)` 获取并加载入 `DataValidationDialog`。
- 对话框确认后，如果类型为 `any` 则清理该选区规则；否则生成 `DataValidation` 并存入 `sheet.add_data_validation(dv)`。
- 刷新视图。

### 2.3 Circle Invalid Data Engine
在 `ledger_window.py:circle_invalid()` 中：
- 扫描含有有效性规则的所有单元格区域。
- 借助 `validate_cell_value(sheet, r, c, val)` 进行数值检验。
- 收集不符合规则的单元格坐标 `(r, c)`，遵循 Excel / 原版 255 个上限限制（超过时给出提示）。
- 将结果存入 `sheet.invalid_circles`，触发视图重绘。
在 `ledger_window.py:clear_circles()` 中：
- 清空 `sheet.invalid_circles = []` 并刷新视图。

### 2.4 Viewport Rendering & Interaction
在 `src/atboffice/modules/spreadsheet/views/grid_viewport.py` 中：
1. **圈释渲染**：
   - 在 `paintEvent` 中，遍历 `sheet.invalid_circles`。
   - 使用红色画笔 `QPen(QColor(255, 0, 0), 1.5)` 与抗锯齿在对应单元格周围绘制红色椭圆 `drawEllipse`。
2. **批注角标渲染**：
   - 遍历可见区域中含有批注的单元格。
   - 在单元格右上角绘制 6×6 红色实心小三角形指示标。
3. **可见批注浮层**：
   - 若批注处于显示状态（`cm.visible or sheet.show_all_comments`），在单元格右侧绘制经典黄色便利贴样式便利框（`#FFFFE1`）及引线。
4. **悬停 ToolTip**：
   - 在 `mouseMoveEvent` 中进行 `hit_test`，若鼠标悬停在含有批注的单元格上，通过 `QToolTip.showText` 展示作者与批注内容；移出时自动隐藏。

### 2.5 Comment Dialog
新增 `src/atboffice/modules/spreadsheet/dialogs/comment_dialog.py`：
- 提供作者姓名与批注正文编辑。
- 支持快捷键 Esc 取消、Ctrl+Enter / OK 提交。
- 完整的多语言 `safe_tr` 支持。

## 3. Edge Cases & Safeguards
1. **空单元格验证**：若有效性规则勾选 `allow_blank`（默认），空值跳过校验，不产生圈释。
2. **多于 255 个无效数据**：对齐 Excel 与 原版实现，最多圈释 255 个并弹窗警告。
3. **无规则或无无效数据**：状态栏提示友好文本，不报错。
4. **批注不存在时触发操作**：`show_hide_comment` / `delete_comment` 优雅忽略，无异常。
5. **视口滚动与缩放**：圈释与角标精确基于 `geometry_mapper` 计算，滚动时无错位。
