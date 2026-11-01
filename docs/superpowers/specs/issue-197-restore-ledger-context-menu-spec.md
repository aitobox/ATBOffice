# Issue #197: 还原 Ledger 右键选择和上下文菜单 设计规范 (Spec)

## 1. 概述与目标

在原版 `.vibeoffice/public/ledger/` 中：
- `grid.js:435`: 在选区内右键保留原有选区，在选区外右键移动活动单元格并重新框选；右键首先尝试提交单元格当前输入，若验证失败或阻止提交则保持当前编辑状态。
- `app.js:847`: 根据命中目标（列标题 `colhdr`、行标题 `rowhdr`、单元格 `cell`、浮动图形/图表对象 `object`）动态构建具备完整操作能力的Luna风格右键上下文菜单。
- 键盘快捷键 `Shift+F10`: 触发在当前活动单元格矩形中心的快捷菜单。

在移植版 `ATBOffice` 中，`src/atboffice/modules/spreadsheet/views/grid_viewport.py` 的右键处理严重缺失：
1. `mousePressEvent` 忽略了 `RightButton`，未执行选区保留或右键重选逻辑，也未在右键前提交活动编辑。
2. `contextMenuEvent` 仅包含一个“设置单元格格式”动作，缺失剪切、复制、粘贴、选择性粘贴、插入、删除、清除内容、列宽/行高、隐藏/取消隐藏、批注管理、超链接管理等菜单项。
3. 缺失对工作表保护状态（`guard_protect`）的检查和防御，可能在受保护状态下误改数据。
4. 缺失 `Shift+F10` 键盘上下文菜单支持及对象右键菜单联动。

本设计规范依据原版提交 `32ff53a5da0e75ebac11acdb0251cd3d8c7bf408` 与移植版基线 `38664cabd0dcb88dabec91855eb0357dc30f0cdd`，在 `grid_viewport.py` 与 `ledger_window.py` 中 1:1 还原原版右键选择与上下文菜单系统。

---

## 2. 详细技术方案

### 2.1 右键事件与选区保护机制 (Right Click Selection & Commit)

在 `GridViewport.mousePressEvent` 中针对 `Qt.MouseButton.RightButton` 实现：
1. **活动编辑器提交检查**:
   - 若 `self.editor_controller` 处于活动编辑状态 (`is_active`):
     - 调用 `self.editor_controller.commit()`。
     - 若 `commit()` 返回 `False`（例如数据验证 Stop 警告、公式语法错误未放行）：
       - 立即终止事件处理，不切换选区、不弹出右键菜单，保留编辑焦点。
2. **命中测试与选区判定 (Hit Test & Selection Logic)**:
   - 计算命中区域 `hit = self.hit_test(x, y)`：
     - **`HitZone.CELL` (单元格)**:
       - 检查右键位置 `(hit.row, hit.col)` 是否已落在当前任意选区内 (`self.selection.is_selected(hit.row, hit.col)`)。
       - 若在选区内：**保留既有选区**，不重设选区。
       - 若在选区外：更新选区为单单元格 `self.selection.select_cell(hit.row, hit.col)`。
     - **`HitZone.COL_HEADER` (列标题)**:
       - 检查当前选区是否为整列选区，且 `hit.col` 是否已落在选中列范围内。
       - 若已选中该列：**保留既有选区**。
       - 若未选中：将选区切换为整列 `self.selection.select_cols(hit.col, hit.col)`。
     - **`HitZone.ROW_HEADER` (行标题)**:
       - 检查当前选区是否为整行选区，且 `hit.row` 是否已落在选中行范围内。
       - 若已选中该行：**保留既有选区**。
       - 若未选中：将选区切换为整行 `self.selection.select_rows(hit.row, hit.row)`。
     - **`HitZone.CORNER` (全选角标)**:
       - 执行全选 `self.selection.select_all()`。
3. **视口刷新**:
   - 触发 `self.viewport().update()`。

---

### 2.2 上下文菜单构建与分发 (Context Menu Architecture)

在 `GridViewport.contextMenuEvent` 和 `show_context_menu(pos, reason)` 中根据目标上下文分流：

#### A. 浮动对象菜单 (Floating Object Context Menu)
- 若 `self.object_layer` 存在且其上有被选中的对象 (`selected_object`):
  - 显示对象上下文菜单：
    - 剪切 (`Cut`)、复制 (`Copy`)、粘贴 (`Paste`)、删除 (`Delete`)
    - 分隔符
    - 叠放次序 (`Order`): 置于顶层 (`Bring to Front`)、置于底层 (`Send to Back`)、上移一层 (`Bring Forward`)、下移一层 (`Send Backward`)
    - 分隔符
    - 设置对象格式 (`Format Object...`)

#### B. 列标题上下文菜单 (Column Header Context Menu)
- 触发条件：命中 `HitZone.COL_HEADER` 或当前选区为整列。
- 菜单项：
  1. 剪切 (`Cu&t`, Ctrl+X)
  2. 复制 (`&Copy`, Ctrl+C)
  3. 粘贴 (`&Paste`, Ctrl+V)
  4. 选择性粘贴 (`Paste &Special...`)
  5. 分隔符
  6. 插入 (`&Insert`): 在选定列左侧插入等量列
  7. 删除 (`&Delete`): 删除选定的整列
  8. 清除内容 (`Clear Co&ntents`, Del): 清除选定列的所有单元格数据
  9. 分隔符
  10. 设置单元格格式 (`Format C&ells...`, Ctrl+1)
  11. 列宽 (`Column &Width...`): 弹窗设置列宽（像素或标准字符宽度）
  12. 隐藏 (`&Hide`, Ctrl+0): 隐藏选定列
  13. 取消隐藏 (`&Unhide`, Ctrl+Shift+)): 取消选定范围及相邻列的隐藏状态

#### C. 行标题上下文菜单 (Row Header Context Menu)
- 触发条件：命中 `HitZone.ROW_HEADER` 或当前选区为整行。
- 菜单项：
  1. 剪切 (`Cu&t`, Ctrl+X)
  2. 复制 (`&Copy`, Ctrl+C)
  3. 粘贴 (`&Paste`, Ctrl+V)
  4. 选择性粘贴 (`Paste &Special...`)
  5. 分隔符
  6. 插入 (`&Insert`): 在选定行上方插入等量行
  7. 删除 (`&Delete`): 删除选定的整行
  8. 清除内容 (`Clear Co&ntents`, Del): 清除选定行的所有单元格数据
  9. 分隔符
  10. 设置单元格格式 (`Format C&ells...`, Ctrl+1)
  11. 行高 (`Row &Height...`): 弹窗设置行高
  12. 隐藏 (`&Hide`, Ctrl+9): 隐藏选定行
  13. 取消隐藏 (`&Unhide`, Ctrl+Shift+(): 取消选定范围及相邻行的隐藏状态

#### D. 普通单元格上下文菜单 (Cell Context Menu)
- 触发条件：命中 `HitZone.CELL`。
- 菜单项：
  1. 剪切 (`Cu&t`, Ctrl+X)
  2. 复制 (`&Copy`, Ctrl+C)
  3. 粘贴 (`&Paste`, Ctrl+V)
  4. 选择性粘贴 (`Paste &Special...`)
  5. 分隔符
  6. 插入... (`&Insert...`, Ctrl+Shift++): 单元格插入对话框（活动单元格下移/右移、整行/整列）
  7. 删除... (`&Delete...`, Ctrl+-): 单元格删除对话框（活动单元格上移/左移、整行/整列）
  8. 清除内容 (`Clear Co&ntents`, Del)
  9. 分隔符
  10. 批注动作:
      - 若活动单元格存在批注：
        - 编辑批注 (`&Edit Comment`, Shift+F2)
        - 删除批注 (`&Delete Comment`)
        - 显示/隐藏批注 (`&Show/Hide Comment`)
      - 若无批注：
        - 插入批注 (`&Insert Comment`, Shift+F2)
  11. 分隔符
  12. 设置单元格格式 (`Format C&ells...`, Ctrl+1)
  13. 从下拉列表中选择 (`Pick From Drop-down &List...`, Alt+Down)
  14. 添加监视 (`Add &Watch`)
  15. 分隔符
  16. 超链接动作:
      - 若活动单元格存在超链接：
        - 编辑超链接 (`&Edit Hyperlink...`)
        - 打开超链接 (`&Open Hyperlink`)
        - 删除超链接 (`&Remove Hyperlink`)
      - 若无超链接：
        - 插入超链接 (`Hyperl&ink...`, Ctrl+K)

---

### 2.3 快捷键 Shift+F10 支持

- 在 `GridViewport.keyPressEvent` 中捕获 `Qt.Key.Key_F10` 且包含 `Qt.KeyboardModifier.ShiftModifier`。
- 计算当前活动单元格的视口中心坐标：
  `rect = self.geometry_mapper.cell_rect(r, c)`
  映射至屏幕全局坐标并以键盘触发原因弹出上下文菜单。

---

### 2.4 数据保护守卫 (Guard Protection)

实现 `guard_protect(allow_key: str | None = None, cell_edit: bool = False) -> bool`:
- 检查 `self.model.protection`: 若未开启保护则放行 (`return False`)。
- 若开启保护：
  - 检查选区内所有单元格是否包含 `locked == True` 的单元格。
  - 若受保护且锁定：弹出只读警告消息框，并返回 `True` 阻止修改操作。

---

### 2.5 国际化与翻译 (i18n & Retranslate)

- 严格使用 `safe_tr()` 包装所有菜单文字。
- 对齐 Excel 2003 中文地道翻译与现有多语言资源文件。
