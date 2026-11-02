# Specification: [Issue #196] 修正 Lectern 工具栏控件和上下文状态

## 1. Overview & Problem Statement
在 ATBOffice Lectern (幻灯片演示) 模块中，10 个 Office 2003 Luna 工具栏虽然已在 Phase 4 中搭设基础架构并在 `docs/clone/TOOLBAR_BASELINE_MATRIX.md` 中登记了 117 个控件对照项，但深入审计后发现存在以下关键缺失与缺陷：
1. **下拉与分裂按钮未接通业务命令**: `lectern_toolbars.py` 的 `_add_drop` 和 `_add_split` 仅以原始文本调用 `menu.addAction(safe_tr(item))`，未在 `ActionRegistry` 中注册对应 Action ID。导致二级菜单项无法通过 ActionRegistry 统一调度，点击无法触发业务处理，且多语言动态切换时二级菜单无法刷新。
2. **缺乏选中对象上下文联动与可用性约束**: 当选中不同类型的对象（文字、自选图形、表格、图片、艺术字、IntelliArt 关系图）或未选任何对象时，工具栏按钮未正确更新 `enabled`/`disabled` 状态。例如：无选区时组合/对齐未禁用；表格操作在非表格选区未禁用；图片处理动作在非图片选区未禁用。
3. **格式与图形操作存在未接线或空桩方法**: `_toggle_bold`、`_toggle_italic`、`_toggle_underline` 仅标记 dirty 而未真正修改选中文本或形状文字属性；字号增大/减小 (`growFont`/`shrinkFont`)、文字阴影 (`shadowText`)、段落对齐 (`alignLeft`/`alignCenter`/`alignRight`)、编号/符号 (`numbering`/`bullets`)、大纲级别提升/降低 (`promote`/`demote`)、表格行列与对齐操作、图片旋转/裁剪/重设等未接线至视图与模型层。
4. **多语言与 i18n 刷新完整性**: `retranslate_lectern_toolbars` 仅更新了工具栏窗口标题，未对 `OfficeDropDownButton`、`OfficeSplitButton`、下拉菜单项、ComboBox 项及工具提示进行深度刷新，无法满足 7 语言动态无缝切换的要求。

本设计基于原版 `lectern` 规范与 Phase 5 对照矩阵，对 Lectern 工具栏体系与上下文联动进行系统级修正与加固。

---

## 2. Requirements & Parity Matrix

### 2.1 Standard Toolbar (常用 - 27 项)
- `new` / `open` / `save` / `print` / `printPreview` / `spelling`: 核心文档操作接通。
- `cut` / `copy` / `paste` / `formatPainter`: 剪贴板与格式刷操作。
- `undo` (Split):
  - 主命令: `undo` (撤销, Ctrl+Z), 绑定 `win.undo`
  - 下拉项: `undo_empty` ("无操作可撤销"), 禁用 (`enabled=False`)
- `redo` (Split):
  - 主命令: `redo` (重做, Ctrl+Y), 绑定 `win.redo`
  - 下拉项: `redo_empty` ("无操作可重做"), 禁用 (`enabled=False`)
- `insertChart`: 插入统计图表 (在当前幻灯片插入图表形状)。
- `insertTable`: 插入表格 (在当前幻灯片插入 2x2/3x3 表格形状)。
- `tb_tables`: 切换表格和边框工具栏显隐。
- `hyperlink`: 插入超链接 (Ctrl+K)。
- `expandAll` / `showFormatting` / `showGrid`: 视图与网格参考线切换。
- `viewGray` (Split: "颜色/灰度"):
  - 主命令: `viewGray` -> 切换灰度显示模式
  - 下拉项: `view_color` ("彩色"), `view_grayscale` ("灰度"), `view_black_and_white` ("纯黑白")
- `zoom (combo)`: 缩放下拉框 (`Lectern_ZoomCombo`) 联动视口缩放。
- `help`: 帮助信息。

### 2.2 Formatting Toolbar (格式 - 24 项)
- `font (combo)` / `size (combo)`: 字体族与字号下拉框，联动活动文本编辑框或所选形状文字。
- `bold` / `italic` / `underline` / `shadowText`: 字符样式切换，与当前选中文本状态双向绑定。
- `alignLeft` / `alignCenter` / `alignRight`: 段落对齐切换，排他互斥并反映当前对齐方式。
- `numbering` / `bullets`: 项目编号与项目符号切换。
- `growFont` / `shrinkFont`: 增大/减小字号 (按字号阶梯步进)。
- `promote` / `demote`: 提升/降低缩进与大纲级别 (Alt+Shift+Left / Alt+Shift+Right)。
- `fontColor (ColorPickerButton)`: 文字颜色选择器。
- `slideDesign`: 打开/激活幻灯片设计任务窗格。
- `newSlide`: 插入新幻灯片 (Ctrl+M)。

### 2.3 Sorter Toolbar (幻灯片浏览 - 9 项)
- `hideSlide`: 隐藏/显示选定幻灯片。
- `rehearse`: 启动排练计时。
- `summarySlide`: 根据选定幻灯片生成摘要幻灯片。
- `speakerNotes`: 编辑演讲者备注。
- `transitionPane`: 打开幻灯片切换窗格。
- `sorter_slideDesign` / `sorter_newSlide`: 浏览视图下的设计与新建。

### 2.4 Master Toolbar (母版视图 - 4 项)
- `insertSlideMaster` / `insertTitleMaster`: 插入幻灯片/标题母版。
- `preserveMaster` / `renameMaster` / `deleteTitleMaster`: 母版保留、重命名与删除。
- `closeMaster`: 关闭母版视图并返回普通视图。

### 2.5 Outlining Toolbar (大纲 - 7 项)
- `outline_promote` / `outline_demote`: 大纲级别升降。
- `moveParaUp` / `moveParaDown`: 段落上下移动。
- `outline_summarySlide` / `outline_showFormatting`: 摘要幻灯片与格式显示。

### 2.6 Diagram Toolbar (关系图 - 13 项)
- `diagramAddShape` (Split): 添加形状及下拉子命令 (`diagramAddAfter`, `diagramAddBefore`, `diagramAddAbove`, `diagramAddBelow`)。
- `diagramPromote` / `diagramDemote` / `diagramMoveUp` / `diagramMoveDown`: 关系图节点层级与顺序调整。
- `layoutMenu` (Drop): 版式选择 ("组织结构图", "层次结构", "循环图", "射线图", "金字塔图", "维恩图", "目标图")。
- `colorsMenu` (Drop): 颜色主题 ("主色调", "多彩", "深色", "轻快")。
- `styleMenu` (Drop): 样式方案 ("平面样式", "3D 凸起", "金属质感", "渐变填充")。
- `diagramTextPane` / `diagramReset` / `diagramToShapes`: 文本窗格切换、重设图形、转换为独立自选图形。

### 2.7 Tables and Borders Toolbar (表格和边框 - 16 项)
- `tbl_dash_style` (Drop): 线型选择 ("实线", "虚线", "点线", "双线")。
- `tbl_line_weight` (Drop): 粗细选择 ("0.5 磅" ~ "6.0 磅")。
- `tbl_line_color` (Drop): 线条颜色 ("自动", "黑色", "红色", "蓝色", "灰色")。
- `tableBordersAll` (Split): 边框应用 ("所有框线", "外侧框线", "内侧框线", "无框线", "顶端框线", "底端框线", "左侧框线", "右侧框线")。
- `tbl_fill_color` (Drop): 底纹颜色 ("无填充", "浅灰色", "黄色", "浅蓝色", "浅绿色")。
- `tableMenu` (Drop): 表格菜单 ("插入表格", "在左侧插入列", "在右侧插入列", "在上方插入行", "在下方插入行", "删除列", "删除行", "合并单元格", "拆分单元格", "选择表格", "边框和底纹")。
- `tableMergeCells` / `tableSplitCell`: 合并与拆分单元格。
- `cellTop` / `cellMiddle` / `cellBottom`: 单元格垂直对齐。
- `distRows` / `distCols`: 平均分布各行/各列。

### 2.8 Picture Toolbar (图片 - 14 项)
- `pic_insert`: 插入图片。
- `pic_color_mode` (Drop): 颜色模式 ("自动", "灰度", "黑白", "冲蚀")。
- `picMoreContrast` / `picLessContrast`: 对比度增减。
- `picMoreBright` / `picLessBright`: 亮度增减。
- `picCrop`: 激活图片裁剪控制柄。
- `rotateLeft`: 向左旋转 90 度。
- `pic_line_style` (Drop): 线型粗细。
- `formatObject`: 设置图片格式对话框。
- `picTransparent`: 设置透明色。
- `picReset`: 重设图片大小与色彩。

### 2.9 WordArt Toolbar (艺术字 - 9 项)
- `wa_insert`: 插入新艺术字。
- `wordartEdit`: 编辑艺术字文字。
- `wordartGallery`: 打开艺术字库预设对话框。
- `wa_format`: 设置艺术字格式。
- `wa_shape_menu` (Drop): 艺术字形状 ("纯文本", "波浪", "上凸", "下凹", "环形", "倒三角形")。
- `waSameHeight`: 艺术字字母同样高度。
- `waVertical`: 艺术字垂直排版。
- `wa_align_menu` (Drop): 艺术字对齐 ("左对齐", "居中", "右对齐", "两端对齐")。
- `wa_char_spacing_menu` (Drop): 字符间距 ("很紧", "紧密", "常规", "稀疏", "很松")。

### 2.10 Drawing Toolbar (绘图 - 22 项)
- `draw_menu` (Drop): 绘图菜单 (叠放次序置顶/置底/上移/下移、组合/取消组合/重新组合、对齐或分布)。
- `selectObjects`: 框选模式。
- `autoshapes_menu` (Drop): 自选图形分类 ("线条", "连接符", "基本形状", "箭头总汇", "流程图", "星与旗帜", "标注")。
- `drawLine` / `drawArrow` / `drawRect` / `drawOval` / `textBox`: 常用形状绘制工具。
- `draw_insertWordArt` / `draw_insertDiagram` / `insertClipArt` / `draw_insertPicture`: 插入对象动作。
- `draw_fill_btn` / `draw_line_btn` / `draw_font_btn`: 填充/线条/字体颜色拾取器。
- `draw_line_style` (Drop) / `draw_dash_style` (Drop) / `draw_arrow_style` (Drop) / `draw_shadow_style` (Drop): 形状线型、虚线、箭头、阴影预设。

---

## 3. Architecture & Context State Synchronization

### 3.1 Selection Context Sync Engine
在 `LecternWindow` 中扩展 `_sync_toolbar_states()`，在下列触发点自动执行：
1. 场景选区变化 (`_on_scene_selection_changed`)
2. 活动幻灯片切换 (`load_slide`)
3. 文本光标或编辑状态改变 (`_on_text_editor_focus` / `_on_text_selection_changed`)
4. 视图模式切换 (`set_view_mode`)

### 3.2 Contextual Enablement Rules (可用性约束)
- **选区对象数量约束**:
  - `group`: 仅当选中文本框或形状数量 >= 2 时启用 (`enabled = len(selected) >= 2`)。
  - `ungroup`: 仅当选中对象中至少包含一个组 (`type == "group"`) 时启用。
  - `bringFront` / `sendBack` / `bringForward` / `sendBackward`: 选中对象数 >= 1 时启用。
  - `alignLeft` / `alignCenter` / `alignRight` / `alignTop` / `alignMiddle` / `alignBottom` / `distributeH` / `distributeV`: 选中对象数 >= 1 时启用。
- **表格上下文约束**:
  - `tableMergeCells` / `tableSplitCell` / `cellTop` / `cellMiddle` / `cellBottom` / `distRows` / `distCols` / `tableBordersAll`: 仅当所选对象包含表格 (`is_table == True`) 时启用。
- **图片上下文约束**:
  - `picCrop` / `rotateLeft` / `picMoreContrast` / `picLessContrast` / `picMoreBright` / `picLessBright` / `picReset` / `picTransparent`: 仅当所选对象包含图片 (`is_picture == True`) 时启用。
- **艺术字上下文约束**:
  - `wordartEdit` / `wordartGallery` / `wa_format` / `waSameHeight` / `waVertical`: 仅当所选对象包含艺术字 (`is_wordart == True`) 时启用。
- **关系图上下文约束**:
  - `diagramAddShape` / `diagramPromote` / `diagramDemote` / `diagramMoveUp` / `diagramMoveDown` / `diagramReset` / `diagramToShapes`: 仅当所选对象包含 IntelliArt (`is_diagram == True`) 时启用。

---

## 4. i18n & Multi-Language Architecture
1. `_LECTERN_DROP_AIDS` 与 `_LECTERN_KNOWN_ITEM_AIDS` 集中维护所有下拉与菜单项的唯一标识、显示文案与默认状态。
2. `retranslate_lectern_toolbars` 递归遍历所有 10 个工具栏：
   - 刷新工具栏 `windowTitle`。
   - 遍历 `OfficeDropDownButton` 调用 `retranslate_ui(translate)`。
   - 遍历 `OfficeSplitButton` 刷新菜单内各 Action 文本与提示。
   - 刷新 `Lectern_ZoomCombo`、`Lectern_FontCombo`、`Lectern_SizeCombo` 提示与固定文本。
3. `LecternWindow.retranslate_ui` 同步调用 `action_registry.retranslate_ui(safe_tr)` 和 `retranslate_lectern_toolbars`，确保 7 语言无死角刷新。

---

## 5. Verification Plan
- 编写全面的自动化集成测试 `tests/ui/test_lectern_toolbar_wiring.py`：
  1. 测试所有下拉与分裂按钮的 Action 注册和 ID 唯一性。
  2. 测试选区变化时工具栏按钮的 `enabled` / `disabled` 状态切换。
  3. 测试文本格式化 (`bold`, `italic`, `underline`, `growFont`, `shrinkFont`, `alignLeft`) 的实际模型与视图响应。
  4. 测试表格、图片、艺术字、绘图对象的创建与交互操作。
  5. 测试 7 种语言动态切换下所有工具栏、按钮、下拉项文案正确性。
- 运行全部现有测试以保证零回归。
