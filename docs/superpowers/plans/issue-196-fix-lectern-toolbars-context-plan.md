# Implementation Plan: [Issue #196] 修正 Lectern 工具栏控件和上下文状态

## 1. Goal
系统级修复 Lectern (演示文稿) 模块中 10 个 Luna 工具栏的命令接线、下拉/分裂按钮 Action ID 注册、选中对象上下文联动与可用性约束、多语言切换刷新，以及文本/表格/图片/艺术字/绘图动作的完整业务支持。

---

## 2. Tasks Breakdown (TDD Ordered)

### Task 1: 建立下拉与分裂菜单 Action 映射与注册机制 (`lectern_toolbars.py`)
- 定义 `_LECTERN_DROP_AIDS`: 为 Standard、Formatting、Tables、Picture、WordArt、Diagram、Drawing 等工具栏所有下拉按钮定义明确的 Action ID。
- 定义 `_LECTERN_KNOWN_ITEM_AIDS`: 为撤销/重做、颜色/灰度、表格菜单、自选图形、图片颜色/线型、艺术字形状/对齐等所有子菜单项建立唯一 Action ID、显示文案与默认状态元组。
- 重构 `_add_drop` 和 `_add_split`，引入 `_add_menu_item`：将菜单项以结构化 `ActionSpec` 注册至 `ActionRegistry`，确保可以通过 Action ID 触发，并在菜单对象上保存元数据。
- 完善 `_build_tables_toolbar`、`_build_picture_toolbar`、`_build_wordart_toolbar`、`_build_drawing_toolbar`、`_build_diagram_toolbar`、`_build_standard_toolbar`、`_build_formatting_toolbar` 中的下拉项绑定。

### Task 2: 完善 7 语言深度重翻译 (`lectern_toolbars.py` & `lectern_window.py`)
- 扩展 `retranslate_lectern_toolbars`：
  - 更新全部 10 个工具栏窗口标题。
  - 遍历所有 `OfficeDropDownButton` 调用 `retranslate_ui(translate)`。
  - 遍历所有 `OfficeSplitButton` 刷新菜单内各 Action 文本与提示。
  - 刷新 `Lectern_ZoomCombo`、`Lectern_FontCombo`、`Lectern_SizeCombo` 等 ComboBox 的选项与提示。
- 在 `LecternWindow.retranslate_ui` 中保证调用 `action_registry.retranslate_ui` 与 `retranslate_lectern_toolbars`。

### Task 3: 建立上下文状态联动引擎 (`lectern_window.py`)
- 实现 `_sync_toolbar_states()` 方法：
  - 检查当前活动选区（`selectedItems`）及正在编辑的文本（`ShapeTextEditorItem`）。
  - 同步字体族（`Lectern_FontCombo`）、字号（`Lectern_SizeCombo`）。
  - 同步格式状态按钮的 checked 状态：`bold`, `italic`, `underline`, `shadowText`, `alignLeft`, `alignCenter`, `alignRight`。
  - 实施可用性约束（`setEnabled`）：
    - 形状组合操作：`group` (选中 >= 2), `ungroup` (存在 group), `bringFront`/`sendBack`/`bringForward`/`sendBackward` (选中 >= 1), `align*`/`distribute*` (选中 >= 1)。
    - 表格操作：`tableMergeCells`, `tableSplitCell`, `cellTop`, `cellMiddle`, `cellBottom`, `distRows`, `distCols`, `tableBordersAll` (选区包含 table 时启用，否则禁用)。
    - 图片操作：`picCrop`, `rotateLeft`, `picMoreContrast`, `picLessContrast`, `picMoreBright`, `picLessBright`, `picReset`, `picTransparent` (选区包含 picture 时启用，否则禁用)。
    - 艺术字操作：`wordartEdit`, `wordartGallery`, `wa_format`, `waSameHeight`, `waVertical` (选区包含 wordart 时启用，否则禁用)。
    - 关系图操作：`diagramAddShape`, `diagramPromote`, `diagramDemote`, `diagramMoveUp`, `diagramMoveDown`, `diagramReset`, `diagramToShapes` (选区包含 diagram 时启用，否则禁用)。
- 在 `_on_scene_selection_changed` 中调用 `_sync_toolbar_states()`。

### Task 4: 补全业务动作处理器与视图响应 (`lectern_window.py`)
- 在 `_bind_action_handlers` 中全面接通：
  - 文本格式化：
    - `_toggle_bold`: 对选中文本应用 `set_bold()`，或对选中形状文字批量设置 bold。
    - `_toggle_italic`: 对选中文本应用 `set_italic()`。
    - `_toggle_underline`: 对选中文本应用 `set_underline()`。
    - `shadowText`: 切换文字阴影。
    - `growFont` / `shrinkFont`: 步进字体大小。
    - `alignLeft` / `alignCenter` / `alignRight`: 设置段落对齐。
    - `numbering` / `bullets`: 设置项目符号与编号。
    - `promote` / `demote`: 调整大纲缩进。
  - 常用与表格：
    - `insertTable`: 在当前幻灯片插入 2x2 表格形状并选中。
    - `insertChart`: 插入柱状图/折线图形状。
    - `tb_tables`: 切换表格工具栏显隐。
    - `viewGray` / `view_color` / `view_grayscale` / `view_black_and_white`: 颜色/灰度模式切换。
    - `tableMergeCells` / `tableSplitCell` / `cellTop` / `cellMiddle` / `cellBottom` / `distRows` / `distCols` / `tableBordersAll`。
  - 图片与艺术字：
    - `pic_insert`: 插入图片并放置于幻灯片中央。
    - `rotateLeft`: 逆时针旋转所选对象 90 度。
    - `picReset`: 恢复对象原始缩放与比例。
    - `waSameHeight` / `waVertical`。
  - 幻灯片浏览与母版：
    - `hideSlide`, `rehearse`, `summarySlide`, `speakerNotes`, `transitionPane`, `slideDesign`。
    - `insertSlideMaster`, `insertTitleMaster`, `preserveMaster`, `renameMaster`, `deleteTitleMaster`。

### Task 5: 编写集成验证测试 (`tests/ui/test_lectern_toolbar_wiring.py`)
- 编写测试用例覆盖：
  1. `test_lectern_dropdown_and_split_actions_registered`: 验证所有下拉与分裂按钮的 Action 均已注册且存在 Action ID。
  2. `test_lectern_selection_context_enablement`: 验证无选区、单图形、多图形、表格、图片、艺术字、IntelliArt 时的工具栏按钮 `enabled`/`disabled` 状态。
  3. `test_lectern_text_formatting_actions`: 验证 `bold`, `italic`, `underline`, `growFont`, `shrinkFont`, `alignCenter` 的实际作用与状态反馈。
  4. `test_lectern_table_and_picture_actions`: 验证表格插入与对齐、图片插入与旋转。
  5. `test_lectern_7_language_deep_retranslate`: 验证切换 7 种语言时，所有工具栏、下拉按钮文本、子菜单项文案正确刷新且不出现空白或崩溃。

### Task 6: 运行测试并执行全量验证
- 运行 `pytest tests/ui/test_lectern_toolbars.py tests/ui/test_lectern_toolbar_wiring.py -v`。
- 运行三模块工具栏基准测试与整体回归测试。
