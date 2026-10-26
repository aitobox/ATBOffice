# Specification: Issue #16 — Office 2003 Luna 经典蓝/银视觉主题与工具栏控件

## 1. 概述与设计背景 (Overview)
本项目旨在将经典 Microsoft Office 2003 标志性的 Luna Blue（经典蓝）与 Luna Silver（典雅银）视觉主题及经典工具栏与拾色器移植到 ATBOffice Python / PySide6 (Qt6) 架构中。

根据 Issue #16 与本地原始代码 `.vibeoffice`：
- `.vibeoffice/public/common/looks.css` (Luna Blue 经典配色表、阴影与渐变参数)
- `.vibeoffice/public/common/ui.css` (工具栏手柄、带下划线助记键按钮、下凹状态样式)
- `.vibeoffice/public/common/icons.js` (16x16 经典命令图标及配色)
- `.vibeoffice/public/common/core.js` (40 色经典调色板 `C.STANDARD`)

## 2. 架构设计与模块划分 (Architecture & Modules)

### 2.1 样式系统: `src/atboffice/ui/styles/luna_2003.py`
- **调色板定义 (Color Tokens)**:
  - **Luna Blue (经典蓝)**:
    - 渐变起始/结束: `--dock-a: #9EBEF5`, `--dock-b: #C4DAFA`, 工具栏 `--tb-a: #E3EFFF`, `--tb-b: #CBE1FC`, `--tb-c: #7BA4E0`, 边框 `--tb-border: #3B619C`
    - 把手点阵: 阴影 `--grip: #274176`, 高光 `--grip-hi: #FFFFFF`
    - 按钮悬停: 背景 `--hot-a: #FFF4CC`, 边框 `--hot-border: #000080`
    - 按钮按下: 背景 `--press-a: #FE803E`, 边框 `--hot-border: #800000`
    - 按钮选中(Checked): 背景 `--chk-a: #FFDF9A`, `--chk-b: #FFA64C`
    - 状态栏: `--status-bg: #D8E2F3`, 边框 `--sb-sep: #8EAADB`
  - **Luna Silver (典雅银)**:
    - 工具栏与底色: `#EAEAF0` 到 `#D5D5DF`
    - 边框与把手: `#8B8B9B`, `#5A5A6E`
    - 按钮悬停与激活: 银灰色调微黄高光
- **API 接口**:
  - `get_luna_stylesheet(theme: str = "blue") -> str`: 生成 QSS 样式表，作用于主窗口、工具栏、菜单、按钮及状态栏。
  - `apply_luna_theme(widget: QWidget, theme: str = "blue") -> None`: 动态应用指定主题样式与调色板。
  - `format_mnemonic(text: str, is_macos: bool | None = None) -> str`: 跨平台助记符处理，macOS 下剔除 `&`，Windows/Linux 下保留 `&`。

### 2.2 经典命令工具栏: `src/atboffice/ui/components/toolbar.py`
- **`OfficeToolBar(QToolBar)`**:
  - 继承自 `QToolBar`，支持停靠、拖拽浮动 (`isFloating`)、显示/隐藏。
  - 自绘 Office 2003 经典点状把手 (`GripHandle` / `paintEvent`)：
    - 水平工具栏在左侧绘制 2 列立体凸起圆点（阴影点 + 1px 偏移高光点），高度 18px，宽度 7px。
    - 垂直工具栏在顶部绘制 2 行立体圆点。
  - 经典立体分隔符 (`QFrame` / `paintEvent`)：左侧深色线 `#6A8CCB` + 右侧浅色线 `#F1F9FF`。
  - 按钮样式：扁平无边框，悬停与按压时呈现 Office 2003 经典圆角高光矩形。
  - 支持折叠与可配置动作（如新建、打开、保存、打印、剪切、复制、粘贴、撤销、重做、加粗、倾斜、下划线、对齐等）。

### 2.3 经典 40 色拾色网格: `src/atboffice/ui/components/color_picker.py`
- **调色板定义**: 严格对接 `C.STANDARD` 40 种经典颜色（5 行 × 8 列）：
  - Row 1: `#000000`, `#993300`, `#333300`, `#003300`, `#003366`, `#000080`, `#333399`, `#333333`
  - Row 2: `#800000`, `#FF6600`, `#808000`, `#008000`, `#008080`, `#0000FF`, `#666699`, `#808080`
  - Row 3: `#FF0000`, `#FF9900`, `#99CC00`, `#339966`, `#33CCCC`, `#3366FF`, `#800080`, `#969696`
  - Row 4: `#FF00FF`, `#FFCC00`, `#FFFF00`, `#00FF00`, `#00FFFF`, `#00CCFF`, `#993366`, `#C0C0C0`
  - Row 5: `#FF99CC`, `#FFCC99`, `#FFFF99`, `#CCFFCC`, `#CCFFFF`, `#99CCFF`, `#CC99FF`, `#FFFFFF`
- **`ColorPickerPopup(QFrame)`**:
  - 弹出式网格面板（`Qt.Popup`）。
  - 顶部按钮：“自动 / 无填充”(`Automatic / No Fill`)。
  - 中间区：40 个色块按钮（尺寸 18x18px，带悬停与选中高光）。每个色块拥有完整中文翻译 tooltip（如“黑色”、“橄榄绿”、“海绿色”、“天蓝”等）。
  - 底部按钮：“其他颜色...”(`More Colors...`)，点击弹出 `QColorDialog`。
  - 信号：`color_selected(str)`，返回 `#RRGGBB`、`"auto"` 或 `"none"`。
- **`ColorPickerButton(QToolButton)`**:
  - 带有向下小箭头的分割按钮或菜单按钮，下方带当前选中颜色指示条（Color Bar）。
  - 点击左侧直接应用当前颜色；点击下拉箭头弹出 `ColorPickerPopup`。

### 2.4 主界面集成与菜单项 (`src/atboffice/ui/shell/main_window.py`)
- 添加标准工具栏与格式工具栏到 `MainWindow`。
- 在“视图 (View)”菜单中添加“主题 (Themes)”子菜单（包含 Luna Blue 与 Luna Silver 切换项）。
- 在格式工具栏上添加字体颜色与填充颜色拾色器。
- 支持快捷键与多语言动态切换 (`retranslate_ui`)。

## 3. 验收标准与测试策略 (Verification Plan)
- **单元与 GUI 测试**: `tests/gui/test_luna_ui.py`
  1. `test_luna_styles`: 测试 QSS 生成、Luna Blue / Silver 样式切换、调色板颜色属性。
  2. `test_mnemonic_formatting`: 测试 macOS 与 Windows/Linux 下的 `&` 助记符过滤逻辑。
  3. `test_office_toolbar`: 测试 `OfficeToolBar` 实例化、浮动/停靠属性、点状把手自绘无异常。
  4. `test_color_picker_popup`: 测试 40 色色块生成数量、点击色块发射信号、自动/无填充按钮行为、其他颜色对话框响应。
  5. `test_color_picker_button`: 测试 `ColorPickerButton` 下拉弹出、当前颜色条绘制与更新。
  6. `test_main_window_luna_integration`: 测试主窗口工具栏存在性、主题动态切换。
