# Specification: Issue #216 - 补全 Ledger 视图 (分页符预览/全屏) 与完整右键菜单

## 1. Overview & Objective
本设计规范针对 GitHub Issue #216 (TASK-604)，补全 ATBOffice Ledger 模块中缺失的视图模式（Page Break Preview 分页符预览、Full Screen 全屏视图）以及完整的右键上下文菜单（行标右键、列标右键、工作表标签右键、状态栏自动计算区右键切换）。

## 2. Visual & Behavioral Parity Reference
对齐 `.vibeoffice/screenshots/02_ledger/` 中的原版截图与交互：
1. `02_ledger/001_overview__Default_Grid_Normal.png`: 默认网格视图。
2. `02_ledger/002_overview__Page_Break_Preview.png`: 分页符预览视图。外框带有实线/虚线蓝色分页边界线，页面外部为灰色底色，页面中央渲染“Page 1”半透明水印；首次进入弹出“Welcome to Page Break Preview”提示对话框。
3. `02_ledger/003_overview__Full_Screen.png`: 全屏模式。隐藏主窗口菜单栏、工具栏、编辑栏、状态栏，浮动“关闭全屏”控制浮条，支持快捷键 `Esc` 一键退出。
4. `02_ledger/050_context_Row_Header__Context_Row.png`: 行标右键菜单（剪切/复制/粘贴/选择性粘贴/插入行/删除行/清除内容/单元格格式/行高/最适合的行高/隐藏/取消隐藏）。
5. `02_ledger/051_context_Col_Header__Context_Column.png`: 列标右键菜单（剪切/复制/粘贴/选择性粘贴/插入列/删除列/清除内容/单元格格式/列宽/最适合的列宽/标准列宽/隐藏/取消隐藏）。
6. `02_ledger/052_context_Sheet_Tab__Context_SheetTab.png`: 工作表标签右键菜单（插入工作表/删除/重命名/移动或复制/工作表标签颜色/隐藏/取消隐藏）。
7. `02_ledger/053_context_StatusBar_Calc__AutoCalculate_Menu.png`: 状态栏自动计算区右键菜单（None/Average/Count/Count Nums/Max/Min/Sum），支持勾选切换并实时重算。

---

## 3. Architecture & Module Design

### 3.1. GridViewport: Page Break Preview (分页符预览)
- **状态维护**:
  - `_view_mode: str = "normal"` ("normal" | "page_break")
  - `view_mode` 属性与 `set_view_mode(mode: str)` 方法。
  - 视图切换信号: `view_mode_changed = Signal(str)`。
- **分页与渲染逻辑**:
  - 在 `GridViewport.paintEvent` 中，根据当前 `_view_mode`:
    - 若为 `"page_break"`:
      1. 计算当前数据占用范围 (Used Range: `min_r..max_r`, `min_c..max_c`)，若为空表则默认至少覆盖 `0..30` 行与 `0..7` 列（对应标准打印页宽）。
      2. 计算打印分页网格（如每页约 50 行 x 10 列，或由打印几何设置决定）。
      3. 计算每页的屏幕物理矩形 `page_rect`。
      4. 绘制页面外部灰色阴影区域（覆盖视口内不在任何打印页范围的背景）。
      5. 绘制页面边界蓝色边框（实线/虚线粗边框 `QPen(QColor(0, 0, 255), 2)`）。
      6. 绘制页面中央巨大半透明水印文字 `"Page {n}"`（或地道多语言“第 {n} 页”）：`QFont("Arial", 40, QFont.Weight.Bold)`，颜色 `QColor(180, 180, 180, 120)`。
  - **初次进入提示框**:
    - 提供 `show_page_break_welcome_dialog()`，展示原版提示文本并支持“不再提示”逻辑。

### 3.2. LedgerWindow: Full Screen (全屏视图)
- **全屏进入与退出**:
  - 绑定 `view_fullscreen` 动作。
  - `toggle_full_screen(enable: bool | None = None)`。
  - 进入全屏:
    - 记录当前菜单栏、工具栏、编辑栏、状态栏的显隐状态。
    - 隐藏主菜单栏、所有工具栏、编辑栏、状态栏。
    - 调用 `self.showFullScreen()`。
    - 弹出无边框置顶浮动工具条 `FullScreenToolBar`，内含“关闭全屏(&C)”按钮。
  - 退出全屏:
    - 隐藏并销毁浮动工具条。
    - 恢复之前保存的菜单栏、工具栏、编辑栏、状态栏显隐状态。
    - 调用 `self.showNormal()`。
  - 键盘事件:
    - 捕获 `Qt.Key.Key_Escape`，若处于全屏模式则平滑退出全屏。

### 3.3. 行标与列标右键菜单补全
- **行标右键菜单 (`_build_row_header_menu`)**:
  - 剪切(&T)、复制(&C)、粘贴(&P)、选择性粘贴(&S)…
  - 分隔线
  - 插入(&I)、删除(&D)、清除内容(&N)
  - 分隔线
  - 设置单元格格式(&F)…
  - 行高(&R)…
  - 最适合的行高(&A)
  - 隐藏(&H)、取消隐藏(&U)
  - 实现 `autofit_selected_rows()`: 遍历选中行中各单元格内容，利用 QFontMetrics 估算所需行高并设置。
- **列标右键菜单 (`_build_col_header_menu`)**:
  - 剪切(&T)、复制(&C)、粘贴(&P)、选择性粘贴(&S)…
  - 分隔线
  - 插入(&I)、删除(&D)、清除内容(&N)
  - 分隔线
  - 设置单元格格式(&F)…
  - 列宽(&C)…
  - 最适合的列宽(&A)
  - 标准列宽(&S)…
  - 隐藏(&H)、取消隐藏(&U)
  - 实现 `autofit_selected_cols()`: 遍历选中列中各单元格文本内容，使用 QFontMetrics 估算所需列宽并设置。
  - 实现 `set_standard_col_width_dialog()`: 弹出标准列宽输入框（默认 72/8.43），确认后应用到选中列。

### 3.4. SheetTabBar: 工作表标签右键与移动/复制对话框
- **标签右键菜单项补全**:
  - 插入(&I)... (插入新工作表)
  - 删除(&D) (删除当前工作表，最后一页禁用)
  - 重命名(&R) (激活行内编辑)
  - 移动或复制(&M)... (弹出 `MoveCopySheetDialog`)
  - 分隔线
  - 工作表标签颜色(&T)... (弹出 `QColorDialog`)
  - 隐藏(&H) (若支持隐藏则隐藏当前工作表)
  - 取消隐藏(&U)...
- **`MoveCopySheetDialog` 实现**:
  - 下拉框/列表框展示全部工作表名称，外加 `(移至最后)`。
  - 复选框 `建立副本(&C)` (Create a copy)。
  - 点击“确定”:
    - 若勾选“建立副本”，调用 `workbook.add_sheet(...)` 生成带序号的副本工作表并插入至目标位置。
    - 若未勾选，调用 `workbook.move_sheet(...)` 将当前工作表移动至目标索引位置。
    - 保持激活态并刷新标签栏显示。

### 3.5. StatusBar: 自动计算区右键与即时重算
- 完整包含 7 种统计计算模式:
  - `NONE` ("无")
  - `AVERAGE` ("平均值")
  - `COUNTA` ("计数")
  - `COUNT` ("数值计数")
  - `MAX` ("最大值")
  - `MIN` ("最小值")
  - `SUM` ("求和")
- 右键点击 `lbl_calc` 弹出 QMenu 单选组。用户切换时立即保存设置，并针对当前选区重新调用 `update_calculation` 刷新显示。
- 文本格式采用地道的多语言模板，如 `safe_tr("求和={0}").format(...)`。

---

## 4. Internationalization (i18n)
所有新增菜单项、对话框控件、提示文字一律经由 `safe_tr()` 包装，禁止硬编码中文或生硬机器直译：
- 普通视图 (Normal)
- 分页预览 (Page Break Preview)
- 全屏 (Full Screen)
- 关闭全屏 (Close Full Screen)
- 最适合的行高 (AutoFit Row Height)
- 最适合的列宽 (AutoFit Column Width)
- 标准列宽 (Standard Width)
- 移动或复制工作表 (Move or Copy Sheet)
- 建立副本 (Create a copy)
- (移至最后) ((move to end))

---

## 5. Verification & Test Plan
编写针对性单元测试与集成测试，覆盖：
1. `GridViewport`:
   - `view_mode` 切换 ("normal" <-> "page_break") 与信号触发。
   - 分页计算、边界与“Page N”水印绘制逻辑测试。
   - `_build_row_header_menu` / `_build_col_header_menu` 包含“最适合的行高”、“最适合的列宽”、“标准列宽”。
   - `autofit_selected_rows` 与 `autofit_selected_cols` 执行测试。
2. `LedgerWindow`:
   - 全屏切换进入/退出，浮动工具条显示与隐藏，`Esc` 键退出全屏。
3. `SheetTabBar`:
   - 右键菜单弹出项验证。
   - `MoveCopySheetDialog` 模拟移动与创建副本。
4. `StatusBar`:
   - 右键切换各计算函数，验证不同选区数据下的实时显示输出。
