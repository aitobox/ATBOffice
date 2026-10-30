# Specification: Issue #138 - 多标签首选项设置 (Options) 与主题实时预览切换

## 1. Overview & Objective
在 ATBOffice 中，原有的启动中心设置按钮仅为一个静态提示弹窗（`_on_settings_clicked`），并且缺乏全局配置持久化管理和主题切换对话框。
本功能实现：
1. **全局配置管理层 (`AppSettings`)**：基于 `PySide6.QtCore.QSettings` 实现结构化、类型安全、带默认回退的配置存取，涵盖常规、视图、编辑、保存、语言和主题各个维度。
2. **通用的多标签「首选项 / 选项 (Options)」对话框 (`OptionsDialog`)**：
   - 包含 5 个核心设置选项卡：
     - **常规 (General)**：默认打开/保存位置、最近文档历史保留上限 (5–50)、启动行为（显示启动中心 vs 自动新建空白文档）；
     - **视图 (View)**：UI 界面缩放比例 (100%、125%、150%、200%)、状态栏提示显示时间 (ms)；
     - **编辑与排版 (Edit)**：默认字体名称、默认字号 (pt)、表格单元格网格线显示偏好；
     - **保存 (Save)**：自动恢复/自动保存时间间隔 (1–60 分钟)、默认文件保存格式 (DOCX / XLSX / PPTX)；
     - **语言 (Language)**：界面显示语言切换（zh-CN, zh-Hant, en, ja, ko, fr, de），支持动态触发全窗口 `retranslate_ui()`。
   - 提供「确定 (OK)」、「取消 (Cancel)」、「应用 (Apply)」及「恢复默认值 (Restore Defaults)」按钮。
3. **经典外观主题选择器 (`ThemeDialog`)**：
   - 支持 4 大经典外观主题：
     - **Luna 2003 Blue**（经典蓝色，默认）
     - **Luna 2003 Silver**（经典银色）
     - **Luna 2003 Olive Green**（经典橄榄绿）
     - **Windows Classic**（经典灰 / 2000 风格）
   - 每张主题卡片提供缩略图或视觉色彩预览卡片、名称、描述及单选/点击即选机制。
   - 支持实时热切换全应用 QSS 样式表与窗口调色板，无需重启。
4. **与主程序全面集成**：
   - 启动中心（Start Center）底部「设置」按钮点击弹出 `OptionsDialog`；
   - 菜单栏 `工具 ▸ 选项...` (`tools_options`) 弹出 `OptionsDialog`；
   - 菜单栏 `视图 ▸ 主题` 增加主题选择器选项及 4 个主题快捷切换项。
   - 应用启动时从 `AppSettings` 自动恢复主题、语言和最近文件配置。

## 2. Architecture & Data Model

### 2.1 Settings Storage (`atboffice.core.settings`)
使用 `QSettings("ATBOffice", "ATBOffice")` 存储键值：
- `general/default_open_path`: str (default: 用户文档或主目录)
- `general/recent_files_limit`: int (default: 20, min: 5, max: 100)
- `general/start_behavior`: str (default: "start_center", choices: "start_center", "new_doc")
- `view/ui_scale`: str (default: "100%", choices: "100%", "125%", "150%", "200%")
- `view/status_bar_timeout`: int (default: 3000, ms)
- `edit/default_font_family`: str (default: "Tahoma")
- `edit/default_font_size`: int (default: 12)
- `edit/show_gridlines`: bool (default: True)
- `save/auto_save_interval`: int (default: 10, minutes)
- `save/default_save_format`: str (default: "docx")
- `locale/language`: str (default: "zh-CN")
- `theme/active_theme`: str (default: "blue", choices: "blue", "silver", "olive", "classic")

提供单例 / 工具类 `AppSettings`:
- `get(key, default)` / `set(key, value)`
- `reset_to_defaults()`
- `apply_to_app()`：启动时将已保存的语言、主题与配置应用到系统中。

### 2.2 Theme Engine Extension (`atboffice.ui.styles.luna_2003`)
扩展 `get_luna_stylesheet(theme: str) -> str` 与 `apply_luna_theme(widget: QWidget, theme: str)`：
- 增加 `olive` 与 `classic` 专属色板 tokens：
  - `olive`: 橄榄绿渐变背景、柔和绿命令栏、经典深绿按压/高亮边框；
  - `classic`: Windows 经典灰背景 (`#ECE9D8`)、3D 边框浮凸效果、经典蓝高亮选中；
- 提供应用级切换函数 `apply_theme_globally(theme: str)`：
  - 更新 `QApplication.instance().setStyleSheet(qss)`
  - 更新所有活动的 `BaseOfficeWindow` 和 `WindowManager.get_instance().active_windows` 的 palette 和菜单勾选项；
  - 保存主题至 `AppSettings`。

### 2.3 OptionsDialog (`atboffice.ui.dialogs.options_dialog`)
- 继承 `QDialog`，模态对话框。
- 顶部/左侧为 `QTabWidget`，包含 5 个子页：
  - `GeneralTab`: Default Path (QLineEdit + Browse QPushButton), Recent Limit (QSpinBox), Start Behavior (QRadioButton: Start Center vs New Document).
  - `ViewTab`: UI Scale (QComboBox: 100%, 125%, 150%, 200%), Status Bar Tip Duration (QSpinBox).
  - `EditTab`: Default Font (QFontComboBox or QComboBox), Default Size (QSpinBox), Show Gridlines (QCheckBox).
  - `SaveTab`: Auto-save interval (QSpinBox: 1-60 mins), Default Save Format (QComboBox: DOCX, XLSX, PPTX).
  - `LanguageTab`: Language (QComboBox with `LOCALE_DISPLAY_NAMES`).
- 底部操作栏：`QDialogButtonBox`（确定、取消、应用）加「恢复默认」按钮。
- 支持 `retranslate_ui()`。

### 2.4 ThemeDialog (`atboffice.ui.dialogs.theme_dialog`)
- 继承 `QDialog`。
- 展示 4 个主题预览卡片（`ThemeCard`）：
  - 卡片顶部为渐变缩略色块示意图（模拟标题栏、工具栏及按键色泽）；
  - 卡片中间为主题名称（如 `Luna 2003 蓝色`、`Luna 2003 银色`、`Luna 2003 橄榄绿`、`Windows 经典`）；
  - 卡片底部为描述；
  - 卡片支持点击选中并带有蓝色高亮边框。
- 底部提供「即时预览」开关或切换卡片即时刷新背景窗口主题。
- 点击「确定」保存并生效，点击「取消」若已预览则恢复原主题。

## 3. Edge Cases & Resilience
1. **配置值校验与异常防护**：读取损坏或非预期的配置项时，自动回退到安全的默认值，绝不允许异常崩溃。
2. **多语言即时生效**：更改语言后，调用 `load_locale()`，通过 `get_i18n_manager().locale_changed` 信号联动通知当前所有打开窗口更新文字，对话框自身同样调用 `retranslate_ui()`。
3. **最近文件上限变更联动**：用户调整最近文件上限后，立即调用 `WindowManager.get_instance().recent_files.set_max_items(limit)` 并保存，启动中心的最近文档视图随之刷新。
4. **全平台环境兼顾**：在 macOS/Linux/Windows 上路径处理使用 `Path`，文件浏览对话框在 pytest 测试时支持环境模拟或无头测试保护。
5. **完整国际化覆盖**：所有控件标签、按钮、下拉列表项及提示语 100% 经过 `safe_tr()` / `tr()` 包装，实现中英双语及多语种地道翻译。

## 4. Acceptance Verification
- `pytest tests/ui/test_options_dialog.py -v` 覆盖：
  1. `AppSettings` 读写、默认值与重置；
  2. `OptionsDialog` 的各标签页控件初始化与保存；
  3. 修改最近文档上限、自动保存时间间隔并确认成功持久化；
  4. 切换语言动态触发 `retranslate_ui()`；
  5. `ThemeDialog` 4 大主题卡片构建与选择切换；
  6. `apply_theme_globally` 即时热重载所有窗口样式表。
