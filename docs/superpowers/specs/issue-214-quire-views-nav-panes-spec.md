# Spec: Issue #214 — Quire 视图模式 (大纲/Web/阅读/全屏) 与导航面板

## 1. 概述与设计背景
Quire 目前默认仅支持 Print Layout（页面视图）。本规格说明书定义对 Word 2003 经典 Quire 视图模式（Normal View、Web Layout View、Reading Layout View、Outline View、Full Screen）以及左侧导航面板（Document Map 和 Thumbnails Pane）的完整移植与实现。

对照 `.vibeoffice/screenshots/01_quire/`（包括 `001` 至 `008` 全景视图与 `019_pane_Document_Map`、`020_pane_Thumbnails`），确保无缝切换视图时文档内容、光标位置、选择范围与撤销/重做栈完整保持，界面控件 100% 覆盖国际化 `safe_tr()` / `tr()`。

---

## 2. 核心架构与模块划分

### 2.1 视图模式枚举 (`ViewMode`)
定义于 `src/atboffice/modules/writer/views/view_modes.py`:
- `PRINT` ("print"): 默认物理页面布局，具备阴影、页边距、垂直间距与双向标尺。
- `NORMAL` ("normal"): 普通连续草稿模式，隐藏垂直标尺与页面间距，连续排版。
- `WEB` ("web"): Web 版式视图，适应窗口宽度流式布局，去除固定页边距限制。
- `READING` ("reading"): 阅读版式视图，显示并排阅读布局，顶部挂载专用阅读工具栏（ReadingLayoutToolbar）。
- `OUTLINE` ("outline"): 大纲视图，根据标题 1~9 级进行树状分级缩进展示，符号展开/折叠，联动大纲操作工具栏。
- `FULL_SCREEN` ("full_screen"): 全屏模式，隐藏菜单栏、工具栏和状态栏，悬浮可拖拽或固定顶部的“关闭全屏”小浮动条。

### 2.2 大纲视图与工具栏 (`OutlineView` & `OutlineToolbar`)
位于 `src/atboffice/modules/writer/views/outline_view.py`:
- **数据与排版**:
  - 计算各顶级块的 Heading Level（1..9，正文为 0）。
  - 根据等级缩进（每级 24~36 pt 缩进）。
  - 展开/折叠状态集合 (`collapsed_ids: set[int]`)，折叠标题时隐藏其下属更高层级内容。
- **大纲交互操作**:
  - `promote()`: 升级标题（如 Heading 2 -> Heading 1，正文 -> 上文同级或 Heading 1）。
  - `demote()`: 降级标题（如 Heading 1 -> Heading 2）。
  - `promote_to_h1()`: 直接升级为 1 级标题。
  - `demote_to_body()`: 降级为正文文本（清除 Heading 样式）。
  - `move_up()` / `move_down()`: 上移/下移当前段落块及其折叠内容。
  - `expand()` / `collapse()`: 展开/折叠当前标题下的内容。
  - `show_level(level: int)`: 展开至指定级别（0 为显示所有级别）。
- **工具栏 (`OutlineToolbar`)**:
  - 包含升级、降级、降级为正文、上移、下移、展开 (+)、折叠 (-)、显示级别组合框 (All Levels, Level 1..9)、关闭大纲视图按钮。

### 2.3 专用阅读版式工具栏 (`ReadingLayoutToolbar`)
位于 `src/atboffice/modules/writer/views/reading_toolbar.py`:
- 按钮集群：
  - 文档结构图切换 (Document Map)
  - 缩略图切换 (Thumbnails)
  - 查找 (Find)
  - 放大文字 (Increase Text Size)
  - 缩小文字 (Decrease Text Size)
  - 单页显示 (Actual Page)
  - 多页并排显示 (Allow Multiple Pages)
  - 关闭阅读版式 (Close Reading Layout)

### 2.4 左侧导航面板 (`DocumentMapPane` 与 `ThumbnailsPane`)
位于 `src/atboffice/modules/writer/views/document_map_pane.py` 和 `src/atboffice/modules/writer/views/thumbnails_pane.py`:
- **DocumentMapPane**:
  - 基于 `QTreeWidget` / `QTreeView`，解析文档正文中的所有 `Heading 1`..`Heading 9` 段落生成树状导航。
  - 支持节点展开/折叠，点击标题快速将光标导航并滚动至目标段落。
  - 监听光标移动事件，自动高亮光标所在或最近的标题节点。
- **ThumbnailsPane**:
  - 基于 `QListWidget` / `QScrollArea`，根据分页结果将每一页渲染为缩略图卡片（带页码标号）。
  - 点击缩略图即时将主画布滚动至对应页。
- **导航停靠窗口 (`QuireNavDock`)**:
  - 停靠于窗口左侧 (`LeftDockWidgetArea`)，支持通过 Tab 或 View 菜单在 Document Map 与 Thumbnails 之间切换或隐藏。

### 2.5 全屏工具栏 (`CloseFullScreenBar`)
位于 `src/atboffice/modules/writer/views/fullscreen_bar.py`:
- 半透明 / Luna 风格浮动工具栏，包含一个醒目的“关闭全屏 (Close Full Screen)”按钮。
- 按 `Esc` 键或点击按钮即可退出全屏模式并还原窗口先前的工具栏及菜单。

---

## 3. 边界条件与健壮性考量 (AI Pre-Implementation Reflection)
1. **无标题文档的 Document Map**: 显示 "(无标题)" 占位提示，不会崩溃或发生空指针异常。
2. **文档修改实时同步**: 在编辑文本时，防抖（Debounce）通知 Document Map 和 Thumbnails 更新，保持流畅性能。
3. **撤销与重做安全**: 大纲提升/降级/移动通过控制器标准文档编辑命令或修改记录，保持撤销重做栈不损坏。
4. **单页与多页切换**: 在普通视图与 Web 视图下，标尺与滚动范围自适应，不发生死循环或除零错误。
5. **全屏状态恢复**: 记录进入全屏前的菜单栏、工具栏、状态栏和主窗口状态，退出全屏时 100% 精确还原。
6. **国际化 100% 覆盖**: 每一个视图名称、按钮工具提示、下拉选项文本均通过 `safe_tr()` 注入。

---

## 4. 测试规划 (`tests/gui/test_writer_views.py`)
- 测试各视图模式无缝切换 (`PRINT`, `NORMAL`, `WEB`, `READING`, `OUTLINE`, `FULL_SCREEN`)。
- 测试大纲视图标题级别判断、升级、降级、上移、下移及折叠展开逻辑。
- 测试文档结构图 (Document Map) 树节点构建、点击跳转与光标跟随高亮。
- 测试缩略图 (Thumbnails) 生成与页码跳转。
- 测试全屏模式进入、浮动条显示以及通过动作或 Esc 退出恢复。
- 测试所有控件的 `retranslate_ui()`。
