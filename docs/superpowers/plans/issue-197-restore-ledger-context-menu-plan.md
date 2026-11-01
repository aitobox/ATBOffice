# Issue #197: 还原 Ledger 右键选择和上下文菜单 实现计划 (Plan)

## 任务目标
按照原版 `grid.js:435`、`app.js:847`、`commands.js` 还原 Ledger 右键交互与完整上下文菜单：
- 选区内右键保持选区，选区外右键正确选择（单元格、行标题、列标题）。
- 右键前自动提交编辑器，提交失败阻止弹出。
- 键盘 `Shift+F10` 触发当前活动单元格上下文菜单。
- 行标题、列标题、单元格、浮动对象四套上下文菜单构建与实际命令执行。
- 工作表保护守卫 `guard_protect`。
- 100% i18n 支持与现有七语言一致性。

---

## 阶段与任务分解 (TDD 模式)

### 任务 1: 创建专项 GUI 测试用例 (Red Phase)
- **目标文件**: `tests/gui/test_ledger_context_menu.py`
- **内容**:
  1. 测试选区内右键：多选区（如 `(1, 1)` 到 `(3, 3)`）内右键 `(2, 2)`，断言选区保持不变。
  2. 测试选区外右键：选区外右键 `(5, 5)`，断言活动单元格与选区更新为 `(5, 5)`。
  3. 测试列标题右键：点击列标题时若已选中则保留，未选中则整列选中。
  4. 测试行标题右键：点击行标题时若已选中则保留，未选中则整行选中。
  5. 测试正在编辑时右键：
     - 输入合法内容右键：提交成功并正常响应。
     - 输入验证失败内容右键：提交失败，编辑状态不丢失，不触发选区改变与菜单弹出。
  6. 测试 `Shift+F10` 键盘触发：断言弹出菜单且定位到活动单元格。
  7. 测试菜单构建与命令执行：
     - 列标题菜单包含剪切、复制、粘贴、插入列、删除列、列宽、隐藏、取消隐藏等。
     - 行标题菜单包含剪切、复制、粘贴、插入行、删除行、行高、隐藏、取消隐藏等。
     - 单元格菜单包含剪切、复制、粘贴、清除内容、批注操作、超链接、设置单元格格式等。
  8. 测试受保护工作表下的防御：保护且锁定状态下拒绝执行剪切、删除、清除内容等修改操作。
- **验证命令**: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_ledger_context_menu.py` (预期失败)

---

### 任务 2: 在 `GridViewport.mousePressEvent` 中实现右键选择与提交逻辑 (Green Phase 1)
- **目标文件**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **实现内容**:
  1. 在 `mousePressEvent` 中捕获 `Qt.MouseButton.RightButton`。
  2. 若 `self.editor_controller.is_active`，调用 `self.editor_controller.commit()`，若返回 `False` 则 `event.accept(); return`。
  3. 执行 `hit_test(int(x), int(y))`：
     - 若 `HitZone.CELL`：若 `self.selection.is_selected(hit.row, hit.col)` 则保持选区，否则 `select_cell(hit.row, hit.col)`。
     - 若 `HitZone.COL_HEADER`：若已是整列且包含 `hit.col` 则保持，否则 `select_cols(hit.col, hit.col)`。
     - 若 `HitZone.ROW_HEADER`：若已是整行且包含 `hit.row` 则保持，否则 `select_rows(hit.row, hit.row)`。
     - 若 `HitZone.CORNER`：`select_all()`。
  4. 调用 `self.viewport().update()`。

---

### 任务 3: 构建四类上下文菜单及命令实现 (Green Phase 2)
- **目标文件**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **实现内容**:
  1. 重构 `contextMenuEvent(self, event: QContextMenuEvent)` 及公共方法 `open_context_menu(self, global_pos: QPoint, hit: HitResult | None = None)`。
  2. 实现四类菜单构建：
     - `_build_col_header_menu(col)`
     - `_build_row_header_menu(row)`
     - `_build_cell_menu(r, c)`
     - `_build_object_menu(obj)`
  3. 实现支撑方法：
     - `cut()` / `copy()` / `paste()` / `paste_special()`
     - `clear_contents()`
     - `insert_rows()` / `delete_rows()` / `insert_cols()` / `delete_cols()`
     - `set_row_height_dialog()` / `set_col_width_dialog()`
     - `hide_selected_rows()` / `unhide_selected_rows()`
     - `hide_selected_cols()` / `unhide_selected_cols()`
     - 批注与超链接交互辅助方法。

---

### 任务 4: 实现 `Shift+F10` 键盘上下文菜单 (Green Phase 3)
- **目标文件**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- **实现内容**:
  1. 在 `keyPressEvent` 中检测 `event.key() == Qt.Key.Key_F10 and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)`。
  2. 计算 `active_cell` 对应的单元格区域中心点并转换成屏幕全局坐标。
  3. 弹出单元格上下文菜单。

---

### 任务 5: 工作表保护守卫 `guard_protect` (Green Phase 4)
- **目标文件**: `src/atboffice/modules/spreadsheet/models/sheet_model.py` 与 `grid_viewport.py`
- **实现内容**:
  1. `SheetDataModel` 支持 `protection` 属性字典。
  2. `guard_protect(allow_key=None, cell_edit=False)` 方法：检查选区锁定状态，提示警告并不允许数据修改。

---

### 任务 6: 全面验证与回归测试 (Refactor Phase)
- **测试命令**:
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_ledger_context_menu.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_grid_viewport.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
- **文档与差异清单记录**:
  - 更新差异说明与回归记录。
