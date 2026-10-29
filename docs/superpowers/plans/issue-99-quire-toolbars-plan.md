# Implementation Plan: Issue #99 - Quire 10 套工具栏声明式构建与命令接入

## Overview
在 `src/atboffice/ui/shell/quire_toolbars.py` 中 1:1 对齐原版声明式实现 Quire 全量 10 套 Office 2003 Luna 工具栏，并在 `src/atboffice/ui/shell/quire_window.py` 中接入 `ActionRegistry` 命令总线与上下文感知显隐控制。

## Tasks

### Task 1: TDD 单元测试编写 (`tests/ui/test_quire_toolbars.py`)
- **Files**:
  - Create: `tests/ui/test_quire_toolbars.py`
- **Details**:
  - `test_quire_10_toolbars_exist`: 验证 `QuireWindow.toolbars` 包含 10 个键 (`standard`, `formatting`, `tables`, `reviewing`, `outlining`, `headerFooter`, `drawing`, `mailMerge`, `picture`, `wordart`)，且均为 `OfficeToolBar` 实例。
  - `test_toolbar_action_registry_binding`: 验证各工具栏按钮与 `ActionRegistry` 绑定，触发按钮时 `ActionRegistry.action_triggered` 正确发出信号。
  - `test_toolbar_special_widgets`: 验证常用工具栏缩放下拉框、格式工具栏字体/字号/样式下拉框、颜色选择器正常存在。
  - `test_contextual_visibility`: 验证 `update_context_toolbars()` 响应上下文状态（表格、图片、艺术字、大纲视图、页眉页脚、审阅）自动显隐。
  - `test_retranslate_ui`: 验证 `retranslate_ui()` 执行无异常并更新工具栏标题。
- **Verification**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_quire_toolbars.py -v
  ```
  *(预计初始阶段由于缺少模块而失败)*

### Task 2: 声明式工具栏集群实现 (`src/atboffice/ui/shell/quire_toolbars.py`)
- **Files**:
  - Create: `src/atboffice/ui/shell/quire_toolbars.py`
- **Details**:
  - 声明式定义所有命令的 `ActionSpec`，涵盖快捷键、提示、图标。
  - 构建 10 套工具栏构建函数：
    1. `_build_standard_toolbar`
    2. `_build_formatting_toolbar`
    3. `_build_tables_toolbar`
    4. `_build_reviewing_toolbar`
    5. `_build_outlining_toolbar`
    6. `_build_header_footer_toolbar`
    7. `_build_drawing_toolbar`
    8. `_build_mail_merge_toolbar`
    9. `_build_picture_toolbar`
    10. `_build_wordart_toolbar`
  - 提供 `build_quire_toolbars(window, action_registry) -> dict[str, OfficeToolBar]`
  - 提供 `retranslate_quire_toolbars(toolbars, tr_func)`
- **Verification**:
  - 模块能够被顺利导入并构建各套工具栏。

### Task 3: 挂载到 QuireWindow 并实现上下文感知控制 (`src/atboffice/ui/shell/quire_window.py`)
- **Files**:
  - Modify: `src/atboffice/ui/shell/quire_window.py`
- **Details**:
  - 引入 `ActionRegistry` 与 `build_quire_toolbars`、`retranslate_quire_toolbars`。
  - 在 `__init__` 中初始化 `self.action_registry = ActionRegistry(self)`。
  - 绑定窗口已有方法（`new_file`, `open_file_dialog`, `save_file`, `cut`, `copy`, `paste`, `undo`, `redo`, `zoom_in`, `zoom_out`, `zoom_reset` 等）到 ActionRegistry 对应的 action ID。
  - 调用 `build_quire_toolbars` 创建 10 套工具栏，将 `drawing` 挂载到 `Qt.ToolBarArea.BottomToolBarArea`，其余挂载到 `Qt.ToolBarArea.TopToolBarArea`。
  - 保存 `self.toolbars` 字典。
  - 实现 `self.toolbar_modes = {"standard": True, "formatting": True, "drawing": True, "tables": "auto", "reviewing": "auto", "picture": "auto", "outlining": "auto", "headerFooter": "auto", "mailMerge": False, "wordart": "auto"}`。
  - 实现 `update_context_toolbars(context=None)`。
  - 完善 `retranslate_ui()`。
- **Verification**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_quire_toolbars.py -v
  ```

### Task 4: 完整验证与全量回归测试
- **Verification**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/
  ```
- 确认全量测试套件（除已知的无关项外）全部通过，零 regression。
