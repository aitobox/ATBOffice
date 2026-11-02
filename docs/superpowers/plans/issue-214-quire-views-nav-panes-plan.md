# Implementation Plan: Issue #214 — Quire 视图模式 (大纲/Web/阅读/全屏) 与导航面板

## 1. 任务概述
根据规格说明书，分步实现 Quire 视图模式扩展（Normal、Web Layout、Reading Layout、Outline、Full Screen）以及左侧导航面板（Document Map 与 Thumbnails），并编写全面的自动化 GUI 单元测试。

---

## 2. 详细执行计划

### Task 1: 视图模式枚举与大纲视图核心逻辑
- **目标文件**:
  - `src/atboffice/modules/writer/views/view_modes.py`
  - `src/atboffice/modules/writer/views/outline_view.py`
- **步骤**:
  1. 定义 `ViewMode` 枚举（`PRINT`, `NORMAL`, `WEB`, `READING`, `OUTLINE`, `FULL_SCREEN`）。
  2. 实现 `heading_level(doc, para) -> int`，正确识别 1~9 级标题与正文。
  3. 实现大纲操作逻辑：`promote`, `demote`, `promote_to_h1`, `demote_to_body`, `move_up`, `move_down`, `toggle_collapse`, `show_level`。
  4. 实现大纲工具栏 `OutlineToolbar`，包含各操作按钮与级别下拉菜单。
  5. 实现大纲视图组件 `OutlineViewWidget`，支持分级缩进与折叠展示，或者与编辑画布紧密联动。

### Task 2: 阅读版式工具栏与全屏悬浮工具条
- **目标文件**:
  - `src/atboffice/modules/writer/views/reading_toolbar.py`
  - `src/atboffice/modules/writer/views/fullscreen_bar.py`
- **步骤**:
  1. 实现 `ReadingLayoutToolbar`:
     - 包含文档结构图、缩略图、查找、字体放大/缩小、单页/双页并排切换、关闭按钮。
     - 绑定信号与国际化 `safe_tr()` / `retranslate_ui()`。
  2. 实现 `CloseFullScreenBar`:
     - 浮动工具栏，包含“关闭全屏”按钮，Luna 风格外观与关闭信号。

### Task 3: 左侧导航面板 (Document Map & Thumbnails) 与 Nav Dock
- **目标文件**:
  - `src/atboffice/modules/writer/views/document_map_pane.py`
  - `src/atboffice/modules/writer/views/thumbnails_pane.py`
  - `src/atboffice/modules/writer/views/nav_pane_dock.py`
- **步骤**:
  1. 实现 `DocumentMapPane`:
     - 基于 `QTreeWidget`，解析段落标题建立树形结构，空文档显示 `(无标题)`。
     - 点击标题发送跳转信号，并在光标移动时自动高亮对应标题节点。
  2. 实现 `ThumbnailsPane`:
     - 基于 `QListWidget`，按页渲染页面缩略图并标明页码，点击触发滚动到对应页。
  3. 实现 `QuireNavDock`:
     - 继承自 `QDockWidget`，放置于主窗口左侧，包含 Tab 或模式切换头（文档结构图 / 缩略图）与关闭按钮。

### Task 4: 画布视口与 WriterView 视图扩展
- **目标文件**:
  - `src/atboffice/modules/writer/views/canvas_view.py`
  - `src/atboffice/modules/writer/view.py`
  - `src/atboffice/modules/writer/views/__init__.py`
- **步骤**:
  1. `WriterCanvasView`:
     - 增加 `view_mode` 属性及切换方法。
     - 在 `NORMAL` 模式下：连续页面草稿排版，不显示垂直页边隙和阴影。
     - 在 `WEB` 模式下：按视口宽度自适应流式排版。
     - 在 `READING` 模式下：支持双页并排或单页舒适阅读渲染。
  2. `WriterView`:
     - 集成 `OutlineToolbar`、`ReadingLayoutToolbar`。
     - 提供 `set_view_mode(mode: ViewMode)`，实现无缝视图切换，保存光标焦点与历史记录。
     - 暴露导航信号（跳转至段落/页码）。

### Task 5: QuireWindow 与 MacMenuBar 动作菜单集成
- **目标文件**:
  - `src/atboffice/ui/shell/mac_menu.py`
  - `src/atboffice/ui/shell/quire_window.py`
- **步骤**:
  1. 在 `mac_menu.py` 的 View 菜单中增加：
     - `view_normal`, `view_web`, `view_print`, `view_reading`, `view_outline`, `view_doc_map`, `view_thumbnails`。
     - 对应中英文国际化文本和快捷键。
  2. 在 `QuireWindow` 中：
     - 初始化并附加左侧 `QuireNavDock`。
     - 绑定视图模式动作处理器与单选状态同步。
     - 实现全屏模式切换（隐藏菜单、工具栏、状态栏，浮动 `CloseFullScreenBar`，按 Esc 恢复）。

### Task 6: 编写全面自动化 GUI 单元测试与验证
- **目标文件**:
  - `tests/gui/test_writer_views.py`
- **步骤**:
  1. 编写视图模式切换测试（Normal, Web, Reading, Outline, Print, Full Screen）。
  2. 编写大纲视图等级识别、提升、降级、上移、下移及折叠展开测试。
  3. 编写 Document Map 与 Thumbnails 交互与跳转测试。
  4. 编写全屏模式切换与恢复测试。
  5. 编写 i18n 与 `retranslate_ui()` 验证测试。
  6. 执行全量 pytest 测试套件确认 0 回归。
