# Specification: [phase6] TASK-609: 补全 Start Center 启动中心设置、主题卡片与许可声明

## 1. Overview & Problem Statement
对照 `.vibeoffice/screenshots/00_start_center/` 的 10 张高清基线截图以及 `.vibeoffice/public/start.js`、`index.html`、`updater.js` 与 `oss-licenses.html`，当前 PySide6 的 Start Center（`start_center.py`）虽实现了最近文档列表与模板库网格，但在设置项（系统字体扫描加载、界面缩放比例）、Themes 主题切换弹窗（Classic、Paper、Paper 2016 Ribbon 三卡片画廊）、Update 软件更新检查对话框以及 Credits & Open Source Licenses 开源许可声明页面上仍存在缺失。

本任务旨在全面补齐这些设置与外围对话框组件，并在 Start Center 启动中心进行完整串联挂载，达成与原版设计 1:1 的视觉与交互对齐，确保 100% 多语言本地化支持和企业级健壮性。

---

## 2. Reference Screenshots & Baseline Parity
- **Start Center 外围与设置弹窗 (`.vibeoffice/screenshots/00_start_center/`)**:
  - `004_dialog_settings__Settings.png`:
    - Language 设置项（语言下拉选择）
    - UI size 缩放项（Size of menus, toolbars, documents and everything else: 100%, 125%, 150%, 200%）
    - Fonts on this computer（本地系统字体扫描/加载按钮、字体数量状态提示）
    - Recent Files（清空最近文档历史记录按钮）
  - `005_dialog_themes__Themes_classic.png`:
    - Themes 标题与副标题："Choose how VibeOffice.work looks. Every open window changes with it."
    - Classic 主题卡片：经典蓝色工具栏与菜单、状态栏拟物外观预览
  - `006_dialog_themes__Themes_paper.png`:
    - Paper 主题卡片：暖纸色调背景（#F7F5F0）、青色强调色（#008080）、圆角扁平控件风格
  - `007_dialog_themes__Themes_paper2016.png`:
    - Paper 2016 Ribbon 主题卡片：基于功能区 Tab（File、Home、Insert、View）与命令分组卡片预览
  - `008_dialog_about__About_VibeOffice.png`:
    - About 对话框：产品名称与应用组件简介（Quire、Ledger、Lectern）、版本号展示、以及指向 "Open source licenses" 的超链接/按钮
  - `009_dialog_update__Update_VibeOffice.png`:
    - Update 对话框：展示当前版本与最新版本、更新说明、"Download" 与 "Later" 动作按钮
  - `010_page_licenses__Open_Source_Licenses.png`:
    - Credits & Open Source Licenses 鸣谢与开源许可证声明窗口：展示第三方依赖组件清单（Python, PySide6, Qt6, openpyxl, python-docx, Pillow, Puff, CommonMark, OpenXML SDK 等）及其完整 License 文本

---

## 3. Architecture & Target Files

### 3.1 核心配置与选项对话框 (`src/atboffice/core/settings.py` & `src/atboffice/ui/dialogs/options_dialog.py`)
1. `src/atboffice/core/settings.py`:
   - 补充 `fonts/scan_system_fonts`（默认 `True`）。
   - 确保 `view/ui_scale` 默认值支持 `["100%", "125%", "150%", "200%"]`。
2. `src/atboffice/ui/dialogs/options_dialog.py`:
   - 在 `OptionsDialog` 的编辑/字体或常规区域，增加“系统字体扫描/加载”开关 `chk_scan_system_fonts` 与“立即扫描本机字体”按钮 `btn_load_fonts`。
   - 动态显示本机字体数量标签 `lbl_font_info`。
   - 界面缩放比例下拉框 `combo_ui_scale` 映射与保存至 `view/ui_scale`。
   - 保留与现存 5 标签页单元测试的 100% 兼容。

### 3.2 独立 Themes 主题切换画廊 (`src/atboffice/ui/dialogs/theme_dialog.py`)
1. 定义 `SUITE_THEMES` 常量元组：
   - `classic`: Windows 经典 / Classic（经典蓝色工具栏与菜单）
   - `paper`: 纸质现代 / Paper（暖纸色、青色强调色、极简扁平）
   - `paper2016`: 现代功能区 / Paper 2016 Ribbon（Ribbon 功能区选项卡与分组）
2. 实现 `SuiteThemeDialog(QDialog)`（别名 `ThemesDialog`）：
   - 顶部说明文本："选择 ATBOffice 的整体外观风格。所有打开的窗口将同步即时生效。"
   - 3 张高保真主题画廊交互卡片（`SuiteThemeCard`），内部渲染对应外观的精美微缩图（Classic 经典蓝条、Paper 暖灰扁平、Paper 2016 Ribbon 功能区）。
   - 单击卡片即时设置选中态，并触发 `apply_theme_globally` 全局外观切换。
   - 底端提供 "确定" 按钮。
3. `ThemeDialog` 保持向后兼容：默认模式保留 Luna 4 色卡片，同时支持通过 `mode="suite"` 打开套件 3 主题卡片。

### 3.3 软件更新对话框 (`src/atboffice/ui/dialogs/update_dialog.py`)
1. 实现 `UpdateDialog(QDialog)`：
   - 标题：`safe_tr("软件更新 — ATBOffice")`
   - 展示版本信息：当前版本与最新可用版本。
   - 展示更新日志/发行说明（`QPlainTextEdit` 格式化呈现）。
   - 按钮组："前往下载" (`btn_download`) 与 "稍后提醒" (`btn_later`)。
   - 提供便捷静态调用 `UpdateDialog.prompt_update(parent, info, current_ver)`。

### 3.4 开源许可证声明窗口 (`src/atboffice/ui/dialogs/license_dialog.py`)
1. 实现 `LicenseDialog(QDialog)`：
   - 标题：`safe_tr("开源许可证与鸣谢 — ATBOffice")`
   - 左侧为依赖库清单（支持搜索筛选框 `txt_search`，列表包含 PySide6, Qt6, openpyxl, python-docx, Pillow, Puff, CommonMark, OpenXML SDK, DejaVu Fonts 等）。
   - 右侧为详细 License 条文阅读器（只读 `QPlainTextEdit`）。
   - 底部提供 "复制许可证内容" 与 "关闭" 按钮。

### 3.5 启动中心主窗口集成 (`src/atboffice/ui/shell/start_center.py`)
1. 左侧边栏底端工具栏布局：
   - `btn_themes`（主题）：打开 `SuiteThemeDialog`。
   - `btn_settings`（设置）：打开 `OptionsDialog`（包含系统字体扫描与缩放比）。
   - `btn_about`（关于）：打开关于窗口，内含 "开源许可声明" 按钮直接链接到 `LicenseDialog`。
   - `btn_update`（更新检查）：触发版本检查并按需打开 `UpdateDialog`。
2. 完整实现 `retranslate_ui()`：保证语言切换时所有按钮、工具提示和弹窗内容 100% 动态刷新。

---

## 4. Think One Step Ahead: Edge Case & Robustness Analysis
1. **系统字体扫描耗时与界面卡顿**:
   - `QFontDatabase.families()` 在拥有大量字体的系统上可能耗时几十至上百毫秒。应在首次扫描后内存缓存字体列表，避免频繁重复调用阻塞 Qt 事件循环。
2. **多窗口主题同步切换**:
   - 当用户在 Start Center 中切换主题（如从 Classic 切换至 Paper），若后台有其他打开的窗口（如 Quire 或 Ledger），必须通过 `WindowManager.get_instance().windows` 广播 `set_theme()`，并容错处理未挂载主题接口的第三方窗口。
3. **断网或 GitHub API 速率受限时的更新检查**:
   - `UpdateDialog` 和更新检查应具备离线与异常捕获机制，优雅显示离线提示，绝不抛出未捕获异常导致应用崩溃。
4. **许可证文本编码与空列表**:
   - 搜索筛选开源许可证时，若输入无匹配关键字，提供空状态提示标签，避免崩溃。
5. **多语言与国际化覆盖率**:
   - 严禁任何硬编码英文字符串无 `safe_tr()` 包裹，确保 zh-CN、en 等语言下文本地道通顺。

---

## 5. Verification Plan
- 运行针对启动中心及其外围弹窗的单元测试套件：
  ```bash
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_start_center_ui.py -v
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ui/test_options_dialog.py -v
  ```
- 确认全部测试 100% 通过无回归。
