# Specification: [phase6] TASK-607: 补全 Lectern 设计模板/配色/动画窗格与放映对话框

## 1. Overview & Problem Statement
对照 `.vibeoffice/screenshots/03_lectern/` 中 12 个任务窗格和 28 个对话框（41 张多标签展开截图）以及 `.vibeoffice/public/lectern/js/panes.js` 与 `dialogs.js`，当前 Lectern 演示文稿模块缺少专门的幻灯片设计模板窗格（Slide Design Templates Gallery）、配色方案窗格（Color Schemes）、动画方案窗格（Animation Schemes），以及动作设置（Action Settings）、设置放映（Set Up Show）、填充效果（Fill Effects 4标签）、艺术字画廊（LettersArt Gallery 30样式）、相册向导（Photo Album）、选项（Options 5标签）等对话框。

本设计旨在补全这 3 个任务窗格和 6 个核心对话框，将其挂载到通用 `TaskPaneDock` 与主窗口菜单/工具栏中，实现高保真度的 PowerPoint 2003 界面体验与 100% 本地化支持。

---

## 2. Reference Screenshots & Baseline Parity
- **任务窗格**:
  - `015_pane_Slide_Design__Task_Pane_Slide_Design.png`: 顶部导航链接 (Design Templates / Color Schemes / Animation Schemes)、Used in This Presentation、Available For Use、Browse...
  - `016_pane_Color_Schemes__Task_Pane_Color_Schemes.png`: 顶部导航链接、Apply a color scheme 8色卡片网格、Edit Color Schemes...
  - `017_pane_Animation_Schemes__Task_Pane_Animation_Schemes.png`: 顶部导航链接、No Animation / Subtle / Moderate / Exciting 预设列表、Apply to All Slides、Play、Slide Show、AutoPreview
- **对话框**:
  - `075_dialog_Action_Settings__Action Settings on Click_Hover.png`: Mouse Click / Mouse Over 标签页、None / Hyperlink to (下一张、上一张、首页、末页、指定幻灯片、URL...)、播放声音
  - `078_dialog_Set_Up_Show__Set Up Slide Show Parameters.png`: 放映类型、放映选项、幻灯片放映范围、推进方式
  - `061~064_dialog_Fill_Effects`: 4 标签页（Gradient, Texture, Pattern, Picture）及实时 Sample 预览
  - `090_dialog_LettersArt_Gallery`: 30 种艺术字样式 5x6 网格预览与选择
  - `091_dialog_Photo_Album`: 相册内容（文件添加、顺序调整、删除、略缩图预览）、相册版式（版面配置、相框形状、标题勾选）
  - `079~083_dialog_Options`: 5 标签页（View, General, Edit, Spelling and Style, Security）

---

## 3. Architecture & Target Files

### 3.1 任务窗格模块 (`src/atboffice/modules/presentation/panes/`)
1. `__init__.py`: 导出 `SlideDesignPane`, `ColorSchemesPane`, `AnimationSchemesPane`。
2. `slide_design_pane.py`:
   - `SlideDesignPane(QWidget)`:
     - 头部链接条：`Design Templates`、`Color Schemes`、`Animation Schemes`，点击切换对应窗格。
     - "当前演示文稿中使用" (`Used in This Presentation`) 列表。
     - "可供使用" (`Available For Use`) 模板网格卡片（预置 Default, Azure, Crimson, Emerald, Midnight, Sunset, Warm, Classic 等经典模板）。
     - 右键菜单 / 下拉箭头："应用至所有幻灯片" (`Apply to All Slides`)、"应用至选定幻灯片" (`Apply to Selected Slides`)。
     - "浏览..." (`Browse...`) 按钮。
3. `color_schemes_pane.py`:
   - `ColorSchemesPane(QWidget)`:
     - 头部链接条切换窗格。
     - 配色方案网格：展示预置的 8 色配色卡片 (lt1, dk1, lt2, dk2, accent1, accent2, hlink, folHlink)。
     - 点击或右键菜单触发应用至所有或选定幻灯片。
     - "编辑配色方案..." (`Edit Color Schemes...`) 按钮。
4. `animation_schemes_pane.py`:
   - `AnimationSchemesPane(QWidget)`:
     - 头部链接条切换窗格。
     - 动画方案分组列表：无动画 (No Animation)、细微型 (Subtle)、中度型 (Moderate)、华丽型 (Exciting)。
     - 操作按钮："应用至所有幻灯片"、"播放"、"幻灯片放映"、"自动预览" 复选框。

### 3.2 对话框模块 (`src/atboffice/modules/presentation/dialogs/`)
1. `action_settings_dialog.py`:
   - `ActionSettingsDialog(QDialog)`: 提供 "单击鼠标" (Mouse Click) 与 "鼠标悬停" (Mouse Over) 两标签页，支持超链接跳转与声音配置。
2. `set_up_show_dialog.py`:
   - `SetUpShowDialog(QDialog)`: 对接并增强现有的放映设置，支持放映类型、连续循环、幻灯片范围、自动/手动换片。
3. `fill_effects_dialog.py`:
   - `FillEffectsDialog(QDialog)`: 4 标签页（渐变 Gradient、纹理 Texture、图案 Pattern、图片 Picture），实时渲染 Sample 样本，输出规范填充字典。
4. `photo_album_dialog.py`:
   - `PhotoAlbumDialog(QDialog)`: 相册向导，支持批量图片导入、上移/下移、删除、相框选择与版式生成。
5. `wordart_gallery_dialog.py`:
   - `WordArtGalleryDialog(QDialog)`: 30 款 WordArt 样式 5x6 网格选择器与 `EditWordArtTextDialog` 文本编辑器。
6. `options_dialog.py`:
   - `LecternOptionsDialog(QDialog)`: 5 标签页（视图、常规、编辑、拼写与样式、安全性）参数配置与持久化。

### 3.3 宿主窗口与组件挂载 (`src/atboffice/ui/shell/lectern_window.py`)
- 在 `LecternWindow.init_task_pane_dock()` 后，自动注册 `slide_design`、`color_schemes`、`animation_schemes` 窗格。
- 联动顶部链接与菜单栏 Action（格式 -> 幻灯片设计、幻灯片放映 -> 动作设置 / 设置放映等）。

---

## 4. Think One Step Ahead: Edge Case & Robustness Analysis
1. **空幻灯片与无选中项处理**:
   - 当没有选中的形状时打开 `ActionSettingsDialog`，对话框应优雅提示或禁用应用按钮，不抛异常崩溃。
   - 当相册向导中未选择任何图片点击 "创建" 时，弹出警告提示并阻止关闭。
2. **多语言与动态文本更新**:
   - 所有对话框及窗格内控件标题、工具提示、分组框、下拉项均使用 `safe_tr()` 包装，实现 `retranslate_ui()`。
3. **取消与关闭无副作用**:
   - 用户在对话框中修改参数后点击 "取消" 或按 ESC，不修改模型，保持原始状态不变。
4. **配色方案与渲染稳定性**:
   - 填充效果渐变计算、图案生成与纹理加载异常时回退到默认浅灰或纯色背景，防止崩溃。

---

## 5. Verification Plan
- 编写专门测试文件 `tests/gui/test_lectern_dialogs_phase6.py`。
- 覆盖各窗格与对话框的实例化、交互流程、取值回填与取消操作。
- 运行测试套件：
  ```bash
  PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_lectern_dialogs_phase6.py -v
  ```
