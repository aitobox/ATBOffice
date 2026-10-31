# Implementation Plan: Issue #167 — 补全矢量剪贴画库、Scout 桌面助手部件与后台更新检查器

## Task 1: 编写单元测试用例 (`tests/modules/common/test_auxiliary.py`)
- **文件**：`tests/modules/common/test_auxiliary.py`
- **内容**：
  1. `test_clipart_database_and_search`：测试 24 种剪贴画数据项的分类完整性、中英文关键词检索、SVG 内容有效性。
  2. `test_clipart_rendering`：测试 `render_clipart_pixmap` 栅格化生成指定尺寸的 `QPixmap`。
  3. `test_scout_assistant_widget`：测试 Scout 小狗助手部件无边框窗口属性、初始坐标、显隐切换、气泡弹窗触发与拖拽事件。
  4. `test_updater_version_comparison`：测试 SemVer 版本号对比算法（包含/不包含 'v' 前缀、相等、更新、回退等情形）。
  5. `test_updater_worker_mock`：通过 Mock 网络请求测试工作线程的成功检测、有新版本弹窗信号、网络故障降级。
- **验证**：运行 `python -m pytest tests/modules/common/test_auxiliary.py`，确认测试按预期失败（TDD Red 阶段）。

## Task 2: 实现矢量剪贴画选择库 (`src/atboffice/modules/common/clipart_dialog.py`)
- **文件**：`src/atboffice/modules/common/clipart_dialog.py`
- **内容**：
  1. 定义 `ClipartItem` 数据类与 `CLIPART_DATABASE`（收录原版全部 24 项矢量图形定义）。
  2. 实现分类定义 `ClipartCategory`（全部、商务、科技、自然、符号）。
  3. 实现 `ClipartDialog(QDialog)`：
     - 分类过滤栏与搜索框实时检索；
     - `QListWidget` 缩略图网格视图，悬停与选中高亮；
     - 详情与预览区域；
     - “插入(&I)”与“取消(&C)”按钮；
     - `prompt_insert_clipart(parent_window)` 快捷调用与多应用（Quire/Lectern/Ledger）插入适配。
  4. 完整实现 `safe_tr()` 和 `retranslate_ui()`。
- **验证**：单测 `test_clipart_database_and_search` 和 `test_clipart_rendering` 通过。

## Task 3: 实现 Scout 桌面伴侣助手 (`src/atboffice/modules/common/assistant_scout.py`)
- **文件**：`src/atboffice/modules/common/assistant_scout.py`
- **内容**：
  1. 实现 `ScoutBalloon(QWidget)` 漫画对话气泡部件：
     - 白色圆角半透明对话框，底部向下三角形指示尾巴；
     - 问候语 + 快捷菜单选项列表（搜索命令、帮助文档、杂技动画、更新检查、隐藏）。
  2. 实现 `ScoutWidget(QWidget)` 桌面浮动伴侣：
     - `Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint`；
     - `QPainter` 绘制蓝色狗垫、米格鲁猎犬躯体、耳朵、面部特征、红色项圈与金色吊牌；
     - 动画循环：呼吸缩放、眨眼、尾巴摇动；
     - 鼠标左键拖拽交互与屏幕边界防护；
     - 右键上下文菜单与左键点击弹气泡。
  3. 实现 `get_scout_assistant()` 管理器与 `toggle_assistant()`。
- **验证**：单测 `test_scout_assistant_widget` 通过。

## Task 4: 实现后台更新检查器 (`src/atboffice/core/updater.py`)
- **文件**：`src/atboffice/core/updater.py`
- **内容**：
  1. 实现 `compare_versions(v1, v2)` 版本比较工具函数。
  2. 实现 `UpdateCheckWorker(QThread)` 异步获取 GitHub Releases 接口。
  3. 实现 `UpdateDialog(QDialog)` 优雅展示版本更新日志与下载跳转按钮。
  4. 实现 `check_for_updates(parent=None, manual=True, api_url=None)` 统一入口。
- **验证**：单测 `test_updater_version_comparison` 和 `test_updater_worker_mock` 通过。

## Task 5: 菜单与主窗口集成 (`mac_menu.py` 与 `base_window.py`)
- **文件**：
  - `src/atboffice/ui/shell/mac_menu.py`
  - `src/atboffice/ui/shell/base_window.py`
- **内容**：
  1. 在 `mac_menu.py` 的“插入 -> 图片”子菜单增加“剪贴画(&C)...”动作 `insert_clipart`。
  2. 在“帮助”菜单中增加“Office 助手(&O)...”动作 `help_assistant` 与“检查更新(&U)...”动作 `check_updates`。
  3. 在 `mac_menu.py` 的 `_bind_window_slots` 中绑定槽函数。
  4. 在 `base_window.py` 中实现 `open_clipart_dialog`、`toggle_assistant`、`check_for_updates`。
- **验证**：运行菜单与窗口绑定测试。

## Task 6: 全量测试验证与质量审查
- 运行 `pytest tests/modules/common/test_auxiliary.py`。
- 运行全量 `pytest tests/` 确保所有用例 100% 通过无回归。
