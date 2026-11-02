# Implementation Plan: [phase6] TASK-609: 补全 Start Center 启动中心设置、主题卡片与许可声明

## Task Overview
对照 `.vibeoffice/screenshots/00_start_center/` 原版 10 张截图，全面实现与补齐 Start Center 所需的外围设置与独立弹窗：
1. 在 `options_dialog.py` 与 `settings.py` 中补充“系统字体扫描/加载”开关与界面缩放比（100%、125%、150%、200%）持久化。
2. 在 `theme_dialog.py` 中实现独立 `SuiteThemeDialog`（别名 `ThemesDialog`），展示 Classic、Paper、Paper 2016 Ribbon 三张微缩画廊卡片与即时切换。
3. 创建 `src/atboffice/ui/dialogs/update_dialog.py` 软件更新检查对话框。
4. 创建 `src/atboffice/ui/dialogs/license_dialog.py` 开源软件许可证声明阅读器。
5. 在 `start_center.py` 中集成与挂载设置、主题、关于（含许可声明链接）及更新对话框。
6. 在 `tests/test_start_center_ui.py` 中编写并补充全面测试用例，确保全部通过。

---

## Task 1: 核心配置与选项对话框强化
**Files to modify**:
- `src/atboffice/core/settings.py`
- `src/atboffice/ui/dialogs/options_dialog.py`

**Implementation Details**:
- `settings.py`:
  - 在 `DEFAULT_SETTINGS` 中加入 `"fonts/scan_system_fonts": True`。
  - 保证 `"view/ui_scale"` 支持 `"100%"`, `"125%"`, `"150%"`, `"200%"`。
- `options_dialog.py`:
  - 在常规或编辑/字体选项卡中加入：
    - `chk_scan_system_fonts`: "扫描并加载本机系统字体" 复选框。
    - `btn_load_fonts`: "立即重新扫描本机字体" 按钮，绑定扫描系统字体逻辑并更新标签。
    - `lbl_font_info`: 动态显示系统字体数量（如："字体列表已加载本机的 {n} 款字体。"）。
  - 在 `load_from_settings()` 与 `save_to_settings()` 中加入 `fonts/scan_system_fonts` 与 `view/ui_scale` 的存取。
  - 完整接入 `safe_tr()` 与 `retranslate_ui()`。

---

## Task 2: 独立 Themes 主题切换画廊实现
**File to modify**:
- `src/atboffice/ui/dialogs/theme_dialog.py`
- `src/atboffice/ui/dialogs/__init__.py`

**Implementation Details**:
- 定义 `SUITE_THEMES`：
  - `classic`: Classic (经典蓝色工具栏与菜单)
  - `paper`: Paper (暖灰与青色强调色扁平现代卡片)
  - `paper2016`: Paper 2016 Ribbon (功能区选项卡与命令分组)
- 实现 `SuiteThemeCard(QFrame)`：
  - 微缩画廊画布（绘制蓝条、纸质灰、Ribbon 选项卡等）。
  - 标题、副标题说明、选中对勾标志与交互样式。
- 实现 `SuiteThemeDialog(QDialog)`（别名 `ThemesDialog`）：
  - 顶部说明标签："选择 ATBOffice 的外观风格。每个打开的窗口都会随之更改。"
  - 3 张卡片水平排列网格。
  - 单击卡片即时设置选中态，并调用 `apply_theme_globally()` 立即更新全局样式。
  - 底部提供 "确定" (`QDialogButtonBox.Ok`) 按钮。
- `ThemeDialog` 保留默认 Luna 4 键卡片向后兼容，同时支持 `mode="suite"`。
- 导出 `SuiteThemeDialog` 与 `ThemesDialog`。

---

## Task 3: 软件更新对话框实现
**Files to create / modify**:
- `src/atboffice/ui/dialogs/update_dialog.py`
- `src/atboffice/ui/dialogs/__init__.py`

**Implementation Details**:
- 创建 `UpdateDialog(QDialog)`：
  - 标题：`safe_tr("软件更新 — ATBOffice")`。
  - 标题文字："发现新版本 ATBOffice" / "检查更新"。
  - 当前版本与最新版本标签展示。
  - 更新日志 `QPlainTextEdit` 只读文本展示。
  - 动作按钮："前往下载" (`btn_download`，点击打开 release 页面或下载链接) 与 "稍后提醒" (`btn_later`)。
  - 支持手动刷新检查与离线容错处理。
  - 导出至 `atboffice.ui.dialogs`。

---

## Task 4: 开源软件许可证声明对话框实现
**Files to create / modify**:
- `src/atboffice/ui/dialogs/license_dialog.py`
- `src/atboffice/ui/dialogs/__init__.py`

**Implementation Details**:
- 创建 `LicenseDialog(QDialog)`：
  - 标题：`safe_tr("开源许可证与鸣谢 — ATBOffice")`。
  - 顶部简介标签："ATBOffice 所使用的开源软件与字体的许可证声明。"
  - 左侧：搜索筛选框 `txt_search` + 依赖项列表 `list_components`（包含 Python, PySide6, Qt6, openpyxl, python-docx, Pillow, Puff, CommonMark, OpenXML SDK, DejaVu Fonts 等）。
  - 右侧：组件详情卡片与只读许可证条文阅读器 `text_license`。
  - 底部操作栏："复制许可证内容" 按钮与 "关闭" 按钮。
  - 导出至 `atboffice.ui.dialogs`。

---

## Task 5: Start Center 挂载与外围弹窗串联
**File to modify**:
- `src/atboffice/ui/shell/start_center.py`

**Implementation Details**:
- 在左侧侧边栏底部工具栏中布局：
  - `btn_themes`: "主题"，点击触发 `show_theme_dialog()` 打开 `SuiteThemeDialog`。
  - `btn_settings`: "设置"，保持打开 `OptionsDialog`（包含系统字体扫描与缩放比）。
  - `btn_about`: "关于"，展示增强型关于弹窗（包含应用说明、版本号，以及 "开源许可声明" 按钮，点击直接拉起 `LicenseDialog`）。
  - `btn_update`: "检查更新"（根据配置显示或在关于窗口中提供入口）。
- 实现或重构：
  - `show_theme_dialog()`
  - `show_license_dialog()`
  - `show_update_dialog()`
  - `show_about()`
- 在 `retranslate_ui()` 中加入新增按钮与文本标签的多语言刷新。

---

## Task 6: 编写并运行自动化测试套件
**File to modify**:
- `tests/test_start_center_ui.py`

**Implementation Details**:
- 增加测试用例：
  1. `test_options_dialog_system_fonts_and_scale()`: 验证字体扫描开关与界面缩放比的设置存取与持久化。
  2. `test_suite_theme_dialog_cards_and_switching()`: 验证 3 张主题卡片（Classic, Paper, Paper 2016 Ribbon）展示、选中与全局主题调用。
  3. `test_update_dialog_init_and_actions()`: 验证更新弹窗版本显示、日志与按钮行为。
  4. `test_license_dialog_search_and_display()`: 验证开源许可证列表过滤、条文呈现与剪贴板复制。
  5. `test_start_center_bottom_buttons_and_dialog_wiring()`: 验证 StartCenterWindow 底部主题、设置、关于、许可与更新按钮完整串联。
  6. `test_start_center_retranslate_coverage()`: 验证语言切换时所有新按钮与文本的多语言刷新。
- 执行全面 pytest 验证：
  ```bash
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_start_center_ui.py -v
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ui/test_options_dialog.py -v
  ```
