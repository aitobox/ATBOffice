# Specification: [Issue #195] 修正 Quire 工具栏控件和上下文状态

## 1. Overview & Problem Statement
在 ATBOffice Quire 模块中，10 个 Luna 工具栏的框架虽然已建立，但在工具栏细节、菜单接通、快捷键和上下文状态上存在以下关键问题：
1. **下拉与分裂按钮未接通业务命令**: `quire_toolbars.py` 的 `_add_drop` 和 `_add_split` 仅以原始文本调用 `menu.addAction(safe_tr(item))`，未在 `ActionRegistry` 中注册对应 Action ID。导致菜单项无法通过 ActionRegistry 统一调度，点击无法触发业务处理，且多语言动态切换时二级菜单无法刷新。
2. **缺乏上下文状态联动与可用性约束**: 表格专属操作（如合并单元格、拆分单元格、平均分布行/列、表格排序、自动求和等）在光标离开表格时未做禁用状态更新；修订审阅相关动作未与文档修订/批注状态建立响应绑定。
3. **绘图与格式预设动作空缺**: 自选图形分类子菜单（线条、基本形状、流程图等）、线条粗细/样式/箭头预设、段落行距预设（1.0/1.5/2.0 等）及边框预设缺乏完整的业务调用链路。
4. **i18n 多语言支持**: 菜单项需全面纳入现有 7 种语言体系，确保 `retranslate_ui` 触发时工具栏标题、按钮文本、提示（Tooltip）及下拉菜单无缝更新。

本设计基于原版 `quire/js/app.js`、`quire/js/commands.js` 规范与 Phase 5 对照矩阵，对 Quire 工具栏体系进行系统级修正与加固。

---

## 2. Requirements & Parity Matrix

### 2.1 Standard Toolbar (常用)
- `undo` (Split):
  - 主命令: `undo` (撤销, Ctrl+Z), 绑定 `win.undo`
  - 下拉项: `undo_empty` ("无操作可撤销"), 禁用 (`enabled=False`)
- `redo` (Split):
  - 主命令: `redo` (重做, Ctrl+Y), 绑定 `win.redo`
  - 下拉项: `redo_empty` ("无操作可重做"), 禁用 (`enabled=False`)
- `tb_table_drop` (Drop: "插入表格"):
  - 主按钮: `tb_table_drop`
  - 下拉项:
    - `insertTable_dialog`: 插入表格(&I)... -> 插入 2x2 表格
    - `insertTable_col_left`: 插入列在左侧 -> `canvas.insert_table_col(left=True)`
    - `insertTable_row_above`: 插入行在上方 -> `canvas.insert_table_row(above=True)`
- `columns_menu` (Drop: "分栏"):
  - 主按钮: `columns_menu`
  - 下拉项:
    - `col_1`: 一栏
    - `col_2`: 两栏
    - `col_3`: 三栏
    - `col_left`: 偏左
    - `col_right`: 偏右

### 2.2 Formatting Toolbar (格式)
- `lineSpacing_menu` (Drop: "行距"):
  - 主按钮: `lineSpacing_menu`
  - 下拉项:
    - `line_spacing_1_0`: 1.0 磅 -> `canvas.set_line_spacing(1.0)`
    - `line_spacing_1_5`: 1.5 磅 -> `canvas.set_line_spacing(1.5)`
    - `line_spacing_2_0`: 2.0 磅 -> `canvas.set_line_spacing(2.0)`
    - `line_spacing_2_5`: 2.5 磅 -> `canvas.set_line_spacing(2.5)`
    - `line_spacing_3_0`: 3.0 磅 -> `canvas.set_line_spacing(3.0)`
    - 分隔线 `-`
    - `line_spacing_more`: 更多(&M)...
- `borderBtn` (Split: "边框"):
  - 主命令: `borderBtn` (应用外侧框线), 绑定 `win.apply_border_preset("outside")`
  - 下拉项:
    - `border_none`: 无边框 -> `win.apply_border_preset("none")`
    - `border_all`: 全框线 -> `win.apply_border_preset("all")`
    - `border_outside`: 外侧框线 -> `win.apply_border_preset("outside")`
    - `border_bottom`: 下框线 -> `win.apply_border_preset("bottom")`
    - `border_top`: 上框线 -> `win.apply_border_preset("top")`
    - `border_left`: 左框线 -> `win.apply_border_preset("left")`
    - `border_right`: 右框线 -> `win.apply_border_preset("right")`

### 2.3 Tables and Borders Toolbar (表格和边框)
- `tbl_insert_menu` (Drop: "插入"):
  - 主按钮: `tbl_insert_menu`
  - 下拉项:
    - `tbl_insert_table`: 插入表格(&I)... -> `canvas.insert_table(2, 2)`
    - `tbl_insert_col_left`: 在左侧插入列 -> `canvas.insert_table_col(left=True)`
    - `tbl_insert_col_right`: 在右侧插入列 -> `canvas.insert_table_col(left=False)`
    - `tbl_insert_row_above`: 在上方插入行 -> `canvas.insert_table_row(above=True)`
    - `tbl_insert_row_below`: 在下方插入行 -> `canvas.insert_table_row(above=False)`
- `tableBorderBtn` (Split: "边框"):
  - 主命令: `tableBorderBtn`, 绑定 `win.apply_table_border("all")`
  - 下拉项: `tbl_border_all` ("所有框线"), `tbl_border_outside` ("外侧框线"), `tbl_border_none` ("无框线")
- `tbl_align_menu` (Drop: "对齐"):
  - `tbl_align_top`: 靠上对齐 -> `win.set_table_cell_valign("top")`
  - `tbl_align_center`: 居中对齐 -> `win.set_table_cell_valign("center")`
  - `tbl_align_bottom`: 靠下对齐 -> `win.set_table_cell_valign("bottom")`
- `tbl_dash_style` (Drop: "线型"): "实线", "虚线", "点线", "双线"
- `tbl_line_weight` (Drop: "粗细"): "0.5 pt", "0.75 pt", "1.0 pt", "1.5 pt", "2.25 pt", "3.0 pt"
- `tbl_line_color` (Drop: "边框颜色"): "自动", "黑色", "蓝色", "红色"
- `tbl_shading_color` (Drop: "底纹颜色"): "无填充颜色", "浅灰色", "黄色", "浅蓝色"

### 2.4 Reviewing Toolbar (审阅)
- `acceptChange` (Split: "接受所选修订(&A)"):
  - 主命令: `acceptChange` -> `canvas.accept_current_revision(all_revisions=False)`
  - 下拉项: `rev_accept_selected` ("接受所选修订"), `rev_accept_all` ("接受对文档所做的所有修订", -> `canvas.accept_current_revision(all_revisions=True)`)
- `rejectChange` (Split: "拒绝所选修订(&R)"):
  - 主命令: `rejectChange` -> `canvas.reject_current_revision(all_revisions=False)`
  - 下拉项: `rev_reject_selected` ("拒绝所选修订"), `rev_reject_all` ("拒绝对文档所做的所有修订", -> `canvas.reject_current_revision(all_revisions=True)`), `-`, `rev_delete_all_comments` ("删除文档中的所有批注")
- `rev_display_mode` (Drop: "显示以供审阅"): "显示标记的最终状态", "最终状态", "显示标记的原始状态", "原始状态"
- `rev_show_menu` (Drop: "显示"): "批注", "墨迹", "插入和删除", "格式"

### 2.5 Drawing Toolbar (绘图)
- `draw_menu` (Drop: "绘图(&R)"):
  - `draw_group`: 组合(&G) (disabled=True)
  - `draw_ungroup`: 取消组合(&U) (disabled=True)
  - `draw_order_front`: 置于顶层(&F) -> `win.reorder_selected_object("front")`
  - `draw_order_back`: 置于底层(&B) -> `win.reorder_selected_object("back")`
  - `draw_nudge_up`: 微移向上 -> `win.nudge_selected_object(0, -1)`
  - `draw_nudge_down`: 微移向下 -> `win.nudge_selected_object(0, 1)`
  - `draw_align_left`: 左对齐 -> `win.align_selected_objects("left")`
  - `draw_rotate_right`: 向右旋转 90° -> `win.rotate_selected_object(90)`
- `autoshapes_menu` (Drop: "自选图形(&U)"):
  - `as_lines`: 线条 -> `win.insert_shape("line")`
  - `as_connectors`: 连接符 -> `win.insert_shape("connector")`
  - `as_basic`: 基本形状 -> `win.insert_shape("basic")`
  - `as_arrows`: 箭头总汇 -> `win.insert_shape("arrow")`
  - `as_flowchart`: 流程图 -> `win.insert_shape("flowchart")`
  - `as_stars`: 星与旗帜 -> `win.insert_shape("star")`
  - `as_callouts`: 标注 -> `win.insert_shape("callout")`
- 线型预设: `draw_line_style`, `draw_dash_style`, `draw_arrow_style`, `draw_shadow_style`

### 2.6 Picture, WordArt & HeaderFooter Toolbars
- Picture: `pic_color_mode` ("颜色"), `pic_line_style` ("线条样式"), `pic_wrap_mode` ("文字环绕")
- WordArt: `wa_shape_menu` ("艺术字形状"), `wa_wrap_mode` ("文字环绕")
- HeaderFooter: `hf_autotext_menu` ("插入自动图文集")

---

## 3. Architecture & Context States

### 3.1 Contextual State Engine
在 `QuireWindow` 中，由 `_sync_toolbar_states()` 和 `update_context_toolbars()` 统一处理：
1. **表格上下文 (In-Table)**:
   - 处于表格内时，自动显示 `tables` 工具栏（若处于 auto 模式）。
   - 启用表格专属 Action: `mergeCells`, `splitCells`, `distRows`, `distCols`, `sortAsc`, `sortDesc`, `autoSum` 以及表格插入/对齐菜单项。
   - 处于普通段落时，禁用上述表格专属 Action，防止非法调用。
2. **修订与审阅上下文**:
   - 当文档开启修订跟踪或包含修订/批注时，自动显示 `reviewing` 工具栏。
   - `acceptChange` 与 `rejectChange` 按钮及子菜单根据修订状态动态更新可用性。
3. **选区格式同步**:
   - `bold`, `italic`, `underline`, 段落对齐 (`alignLeft`, `alignCenter`, `alignRight`, `justify`), 列表样式 (`bullets`, `numbering`), 字体/字号 ComboBox 严格随光标和选区实时同步 checked 状态与当前值。

### 3.2 动态多语言支持 (retranslate_ui)
- 扩展 `retranslate_quire_toolbars`，遍历所有 10 个工具栏内的 `OfficeDropDownButton` 调用其 `retranslate_ui()`。
- `ActionRegistry` 统一刷新注册动作的 Label 和 Tooltip。

---

## 4. Verification Plan
- **单元与集成测试**:
  - `tests/ui/test_quire_toolbar_wiring.py`: 验证所有下拉与分裂按钮的实例类型、Action 注册、点击业务响应。
  - 测试表格进入/离开时专属操作的启用/禁用状态切换。
  - 测试 7 种语言动态切换下标题与按钮文本的完整性。
- **基线对照回归**:
  - `tests/ui/test_toolbar_baseline_parity.py` 全部通过。
