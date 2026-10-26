# Implementation Plan: Issue #16 — Office 2003 Luna 经典蓝/银视觉主题与工具栏控件

## Phase 1: 样式系统与助记符处理 (`src/atboffice/ui/styles/luna_2003.py`)
- [ ] 创建 `src/atboffice/ui/styles/__init__.py` 与 `src/atboffice/ui/styles/luna_2003.py`。
- [ ] 定义 Luna Blue 与 Luna Silver 核心配色常数（背景、渐变、把手阴影/高光、按钮悬停/按压/激活边框等）。
- [ ] 实现 `format_mnemonic(text: str, is_macos: bool | None = None) -> str` 跨平台助记符处理函数。
- [ ] 实现 `get_luna_stylesheet(theme: str = "blue") -> str` 生成覆盖 QToolBar、QToolButton、QMenu、QMenuBar、QStatusBar、QDialog 的 QSS 样式表。
- [ ] 实现 `apply_luna_theme(widget: QWidget, theme: str = "blue") -> None`。
- [ ] 编写并执行单元测试 `tests/gui/test_luna_ui.py` 中的样式与助记符测试用例。

## Phase 2: 经典命令栏与把手控件 (`src/atboffice/ui/components/toolbar.py`)
- [ ] 实现 `DottedGrip(QWidget)`：自绘经典 Office 2003 立体凸起圆点点阵（深色点 + 1px 偏移高光点）。
- [ ] 实现 `OfficeToolBarSeparator(QWidget)`：自绘经典深浅双线立体分隔符。
- [ ] 实现 `OfficeToolBar(QToolBar)`：
  - 继承自 `QToolBar`，默认可移动 (`movable=True`)、可浮动 (`floatable=True`)。
  - 自动在工具栏前端挂载自绘点状把手控件（横向/纵向自适应，固定时自动隐藏把手）。
  - 支持辅助方法 `add_office_action(text, icon, tooltip, callback, checkable)`，支持自动格式化助记符。
- [ ] 编写并执行测试 `tests/gui/test_luna_ui.py` 中的工具栏交互与把手绘制测试用例。

## Phase 3: 40 色经典调色板与拾色控件 (`src/atboffice/ui/components/color_picker.py`)
- [ ] 定义 `OFFICE_2003_STANDARD_COLORS`（5 行 × 8 列，共 40 种经典颜色代码）。
- [ ] 定义 `COLOR_NAMES` 字典并使用 `safe_tr` 提供地道中文色名翻译。
- [ ] 实现 `ColorPickerPopup(QFrame)`：
  - 弹出式浮动面板（`Qt.Popup` 窗口标志）。
  - 顶部主操作按钮（“自动”/“无填充”）。
  - 中间 5×8 色块网格，每个色块具备悬停效果与精确中文工具提示。
  - 底部“其他颜色...”按钮，触发 `QColorDialog` 原生/Qt 拾色器。
  - `color_selected = Signal(str)` 发射选中颜色。
- [ ] 实现 `ColorPickerButton(QToolButton)`：
  - 下拉箭头与分体按键（MenuButtonPopup）。
  - 底部绘制当前颜色指示彩条（Color Bar）。
  - 点击左侧应用当前色，点击箭头展开 `ColorPickerPopup`。
- [ ] 编写并执行测试 `tests/gui/test_luna_ui.py` 中的拾色器网格与信号测试用例。

## Phase 4: 主界面集成与主题切换 (`src/atboffice/ui/shell/main_window.py`)
- [ ] 在 `MainWindow` 中集成经典“常用”与“格式”工具栏。
- [ ] 将字体颜色与填充颜色拾色器集成到格式工具栏中，并与选区单元格样式联动。
- [ ] 在系统菜单栏添加“视图 -> 主题”子菜单，支持动态在 Luna Blue 与 Luna Silver 之间无缝切换。
- [ ] 完善国际化 `retranslate_ui` 支持。
- [ ] 编写集成测试 `tests/gui/test_luna_ui.py::test_main_window_luna_integration`。

## Phase 5: 全套回归验证与审查准备
- [ ] 运行 `pytest tests/gui/test_luna_ui.py -v`。
- [ ] 运行全套测试 `pytest tests/ -v` 确保 100% 通过且无回归。
- [ ] 提交代码，过渡至 `reviewing` 状态并移交 `atb-github-code-reviewer`。
