# Implementation Plan: Issue #213 - 统一任务窗格宿主 TaskPaneDock 与公共对话框

## Tasks Breakdown

### Task 1: HoneycombColorDialog 蜂窝调色板
- **File**: `src/atboffice/ui/components/honeycomb_color_dialog.py`
- **Features**:
  - `HoneycombWidget`: 六角形绘制算法（13 行，7->13->7 共 127 个蜂窝单元格），鼠标移动与悬浮高亮、点击拾色。
  - `GrayscaleStrip`: 底部 16 阶灰度色块条。
  - `CustomTab`: RGB 旋钮/滑块、Hex 文本输入框。
  - `PreviewBox`: New vs Current 实时色彩比对。
  - `getColor(initial, parent, title)` 静态便捷方法。
- **Integration**:
  - 在 `src/atboffice/ui/components/color_picker.py` 中更新 `_open_more_colors_dialog`，调起 `HoneycombColorDialog`。

### Task 2: DocumentPropertiesDialog 文档属性 5 标签对话框
- **File**: `src/atboffice/ui/dialogs/document_properties_dialog.py`
- **Features**:
  - `DocumentMetadata`: 数据模型，管理标准元数据与自定义属性字典。
  - 5 个标签页：`General`（常规）、`Summary`（摘要）、`Statistics`（统计）、`Contents`（内容大纲）、`Custom`（自定义属性）。
  - 支持自定义属性的添加、修改和删除。
  - 提供 `safe_tr()` 及 `retranslate_ui()`。

### Task 3: InAppSaveAsDialog & SecurityOptionsDialog 内置另存为与加密
- **File**: `src/atboffice/ui/dialogs/in_app_save_as_dialog.py`
- **Features**:
  - `SecurityOptionsDialog`: 打开权限密码、修改权限密码、建议只读复选框，并在设置密码时弹出二次密码确认对话框。
  - `InAppSaveAsDialog`: 文件名输入、格式过滤器下拉、目录选择、以及“工具(Tools)”菜单弹出安全选项对话框。
  - 提供 `get_save_info()` 返回目标路径及安全加密配置。

### Task 4: TaskPaneDock 统一任务窗格宿主容器
- **File**: `src/atboffice/ui/components/task_pane.py`
- **Features**:
  - `TaskPaneHeader`: 包含后退、前进、主页、标题下拉菜单按钮、关闭按钮。
  - `TaskPaneDock(QDockWidget)`: 支持窗格按 ID 注册、切换、后退、前进、回到主页，维护浏览历史栈。
  - 内置 `GettingStartedPane` 和 `NewDocumentPane` 通用窗格。
  - 100% `safe_tr()` 与 `retranslate_ui()` 支持。

### Task 5: 模块主窗口挂载与集成
- **Files**:
  - `src/atboffice/ui/shell/base_window.py`: 添加 `show_document_properties_dialog()` 与 `task_pane_dock` 钩子。
  - `src/atboffice/ui/shell/quire_window.py`: 初始化挂载 `TaskPaneDock` 并绑定 `Ctrl+F1` 快捷键与视图菜单。
  - `src/atboffice/ui/shell/ledger_window.py`: 初始化挂载 `TaskPaneDock` 并绑定 `Ctrl+F1` 快捷键与视图菜单。
  - `src/atboffice/ui/shell/lectern_window.py`: 初始化挂载 `TaskPaneDock` 并绑定 `Ctrl+F1` 快捷键与视图菜单。

### Task 6: 编写单元测试
- **Files**:
  - `tests/ui/test_task_pane.py`: 测试 `TaskPaneDock` 注册、历史前进/后退/主页切换、下拉菜单项、关闭/重译。
  - `tests/ui/test_common_dialogs.py`: 测试 `HoneycombColorDialog`（127 单元格蜂窝渲染与拾色、Hex输入、灰度条）、`DocumentPropertiesDialog`（5 标签页读写与自定义属性）、`InAppSaveAsDialog` 与 `SecurityOptionsDialog`（密码确认）。

### Task 7: 运行全量验证与代码评审
- 执行 pytest 测试验证。
- 检查零回归。
- 推进状态机进入 `reviewing` 并启动代码评审。
