# Implementation Plan: [phase6] TASK-607: 补全 Lectern 设计模板/配色/动画窗格与放映对话框

## Task Overview
实现 Lectern 模块缺失的 3 个任务窗格（设计模板、配色方案、动画方案）与 6 个对话框（动作设置、设置放映、填充效果、相册向导、艺术字画廊、选项），并接入 `LecternWindow` 与 `TaskPaneDock`，编写全套自动化测试并执行验证。

---

## Task 1: 任务窗格包与三大窗格实现
**Files to create**:
- `src/atboffice/modules/presentation/panes/__init__.py`
- `src/atboffice/modules/presentation/panes/slide_design_pane.py`
- `src/atboffice/modules/presentation/panes/color_schemes_pane.py`
- `src/atboffice/modules/presentation/panes/animation_schemes_pane.py`

**Details**:
- `slide_design_pane.py`:
  - 顶部快捷链接切换（设计模板 / 配色方案 / 动画方案）。
  - "Used in This Presentation" 当前使用设计模板列表。
  - "Available For Use" 预设设计模板网格（默认、海洋蓝、火焰红、森林绿、夜幕黑、日落暖、古典雅等），支持缩略图卡片展示。
  - 点击卡片应用、右键上下文菜单（"应用至所有幻灯片"、"应用至选定幻灯片"）。
  - "Browse..." 外部导入模板支持。
- `color_schemes_pane.py`:
  - 顶部链接切换。
  - 8色色板卡片网格（lt1, dk1, lt2, dk2, accent1, accent2, hlink, folHlink）。
  - 点击应用、右键应用至所有/选中幻灯片。
  - "Edit Color Schemes..." 回调。
- `animation_schemes_pane.py`:
  - 顶部链接切换。
  - 分组列表：No Animation, Subtle, Moderate, Exciting 各经典动画方案。
  - 底部操作栏：应用至所有幻灯片、播放、幻灯片放映、AutoPreview 复选框。

---

## Task 2: 核心对话框实现与导出
**Files to create**:
- `src/atboffice/modules/presentation/dialogs/action_settings_dialog.py`
- `src/atboffice/modules/presentation/dialogs/set_up_show_dialog.py`
- `src/atboffice/modules/presentation/dialogs/fill_effects_dialog.py`
- `src/atboffice/modules/presentation/dialogs/photo_album_dialog.py`
- `src/atboffice/modules/presentation/dialogs/wordart_gallery_dialog.py`
- `src/atboffice/modules/presentation/dialogs/options_dialog.py`
- 更新 `src/atboffice/modules/presentation/dialogs/__init__.py`

**Details**:
- `action_settings_dialog.py`: 2 标签（Mouse Click, Mouse Over），无/超链接单选，动作下拉（下一张、上一张、首页、末页、指定幻灯片、URL），播放音频，`get_action_settings()`。
- `set_up_show_dialog.py`: 包装和增强放映设置，支持演讲者全屏、窗口浏览、展台自动放映，循环放映，笔颜色，幻灯片范围等。
- `fill_effects_dialog.py`: 4 标签（渐变、纹理、图案、图片），单色/双色/预设渐变，透明度，4 种底纹样式变体，Sample 样本实时渲染，`get_fill_spec()`。
- `photo_album_dialog.py`: 相册向导，图片添加、上移、下移、删除、预览，版式选择（1/2/4 张图片），相框形状，标题勾选，`get_album_spec()`。
- `wordart_gallery_dialog.py`: 30 种艺术字预设网格，`WordArtGalleryDialog` 与 `EditWordArtTextDialog`。
- `options_dialog.py`: 5 标签（视图、常规、编辑、拼写与样式、安全性），`get_options()` / `set_options()`。

---

## Task 3: 宿主窗口与菜单整合 (`LecternWindow`)
**File to modify**:
- `src/atboffice/ui/shell/lectern_window.py`

**Details**:
- 在 `init_task_pane_dock()` 处注册 `slide_design`、`color_schemes`、`animation_schemes` 三大窗格。
- 绑定窗格间导航与菜单触发槽函数。

---

## Task 4: 编写全面自动化测试套件
**File to create**:
- `tests/gui/test_lectern_dialogs_phase6.py`

**Details**:
- 测试各任务窗格加载、卡片点击、右键菜单、信号发射。
- 测试各对话框打开、参数修改、取值验证、取消/关闭逻辑。
- 测试 i18n 多语言翻译文本覆盖与 `retranslate_ui()`。

---

## Task 5: 验证与验收
- 执行 pytest 测试：
  ```bash
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_lectern_dialogs_phase6.py -v
  ```
- 执行全量回归测试确认无任何现有功能破坏。
