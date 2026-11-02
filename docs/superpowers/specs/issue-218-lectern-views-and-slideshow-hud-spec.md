# Specification: TASK-606 补全 Lectern 视图矩阵 (浏览/备注/母版) 与放映浮动控制条

## 1. Overview & Objective
本设计规范针对 GitHub Issue #218（TASK-606），为 Lectern 演示文稿模块实现完整的视图矩阵与全屏放映 HUD 交互体系：
1. **Slide Sorter View（幻灯片浏览视图）**: 完善多列自适应网格、转场星标、持续时间、拖拽重排与右键菜单。
2. **Notes Page View（备注页视图）**: 全新实现 `NotesPageView`，模拟 A4/Letter 打印版式，上半部分预览幻灯片，下半部分富文本/纯文本编辑演讲备注，双向同步。
3. **Slide Master View（母版视图）**: 全新独立实现 `SlideMasterView`，支持幻灯片母版与标题母版层级切换、占位符编辑与一键关闭返回。
4. **Slide Show HUD（放映浮动控制条）**: 全新实现 `SlideShowHud`，在全屏放映模式下鼠标移至左下角时半透明淡入，提供上一张、下一张、画笔工具菜单、定位跳转菜单、结束放映。
5. **Lectern Window 集成**: 在 `LecternWindow` 与 `LecternWorkspace` 深度集成视图切换菜单、状态栏视图切换快捷按钮、母版专用工具条及 100% `safe_tr()` 国际化支持。

---

## 2. Architecture & File Structure

### 2.1 File Map
- `src/atboffice/modules/presentation/views/sorter_view.py`: 幻灯片浏览视图组件（增强与优化）
- `src/atboffice/modules/presentation/views/notes_view.py`: **新增** 备注页视图组件（A4 打印版式、幻灯片缩略图预览与大幅演讲者备注编辑）
- `src/atboffice/modules/presentation/views/master_view.py`: **新增** 母版视图组件（独立母版编辑画板、占位符层级、左侧母版树、关闭工具条）
- `src/atboffice/modules/presentation/slideshow/slide_hud.py`: **新增** 放映浮动控制条（半透明浮动工具栏、画笔子菜单、定位菜单、下一页/上一页）
- `src/atboffice/modules/presentation/slideshow/slideshow_view.py`: 嵌入 `SlideShowHud`，整合画笔墨迹绘制模式与 HUD 事件响应
- `src/atboffice/modules/presentation/views/workspace.py`: 支持 `normal` / `sorter` / `notes` / `master` 四大视图模式切换与状态同步
- `src/atboffice/ui/shell/lectern_window.py`: 视图菜单与动作绑定（`viewNormal`, `viewSorter`, `viewNotesPage`, `viewMaster`），状态栏模式按钮
- `tests/gui/test_lectern_views_phase6.py`: **新增** 综合单元与集成测试套件

---

## 3. Detailed Component Designs

### 3.1 Notes Page View (`notes_view.py`)
- **Page Layout**:
  - 继承自 `QScrollArea`，内部居中展示一个模拟纸张白色画板（`NotesPagePaper`）。
  - 纸张尺寸按标准比例（如 4:3 页面下 794x1123，A4 纵向版式），带有灰色阴影（`QGraphicsDropShadowEffect` 或 QSS 边框模拟）。
- **Sub-components**:
  - **Header / Footer Info**: 显示页眉、日期、页脚、幻灯片编号。
  - **Slide Thumbnail Preview**: 上半部分区域展示当前幻灯片的高清渲染略缩图，带有黑色细边框。
  - **Speaker Notes Editor**: 下半部分区域放置富文本/多行文本编辑框（`QTextEdit`），预设占位提示文本（"单击此处添加备注" / "Click to add notes"）。
  - **Navigation Bar**: 底部或顶部提供翻页工具条（`[ ◄ 上一页 ]` `[ 幻灯片 1/4 ]` `[ 下一页 ► ]`）。
- **Synchronization**:
  - 实时编辑同步：`notes_changed` 信号触发 `slide.notes` 更新，并向父级工作区发射同步信号。
  - 切换幻灯片：外部调用 `set_current_slide_index(idx)` 即时刷新预览图和文本内容。

### 3.2 Slide Master View (`master_view.py`)
- **Master Tree / Thumbnails**:
  - 左侧展示母版列表：
    - `1. 幻灯片母版` (Slide Master)
    - `2. 标题母版` (Title Master)
  - 选中对应项切换主画布编辑目标（`slide` vs `title`）。
- **Placeholders**:
  - 标题占位符（"单击此处编辑母版标题样式"）。
  - 正文占位符（5 级项目符号文本）。
  - 页眉/页脚/日期/数字占位符。
- **Close Toolbar**:
  - 顶部显眼展示 `MasterViewCloseBar`，包含 "关闭母版视图"（Close Master View）按钮与增删标题母版按钮。
  - 点击关闭将母版占位符样式与背景饰品同步回 `design` 并切回 `normal` 视图。

### 3.3 Slide Show HUD (`slide_hud.py`)
- **Widget**:
  - `SlideShowHud(QFrame)`，无边框、半透明暗黑背景（`rgba(30, 30, 30, 200)`），圆角半径 6px。
  - 尺寸约 180x36px，悬浮于全屏窗口的左下角（如 `x=24, y=height-60`）。
- **Buttons & Menus**:
  1. `btn_prev`: 上一张（`◄`），发送 `prev_clicked`。
  2. `btn_pen`: 画笔工具（`✎`），点击弹出 `QMenu`：
     - 箭头指针 (Arrow)
     - 圆珠笔 (Ballpoint Pen - 红色细线)
     - 荧光笔 (Highlighter - 黄色半透明宽线)
     - 墨迹颜色 (Ink Color: 黑色, 红色, 蓝色, 绿色, 黄色)
     - 橡皮擦 (Eraser - 单击笔画擦除)
     - 清除屏幕上所有墨迹 (Clear All Ink)
  3. `btn_menu`: 快捷菜单（`☰`），弹出定位跳转（Go to Slide）列表与黑屏/白屏控制。
  4. `btn_next`: 下一张（`►`），发送 `next_clicked`。
  5. `btn_end`: 结束放映（`✕` / `End`），发送 `end_clicked`。
- **Auto-hide & Fade**:
  - 鼠标移入屏幕左下区域（如 `y > height - 100 and x < 300`）时淡入；离开后延时 3 秒淡出。

### 3.4 Integration in `LecternWorkspace` & `LecternWindow`
- `LecternWorkspace.set_view_mode(mode: str)`:
  - 支持 `mode in ("normal", "sorter", "notes", "master")`。
  - `center_stack` 统一管理四大视图，切换平滑无闪烁。
- `LecternWindow`:
  - 注册 `viewNotesPage` 动作，快捷键切换。
  - 底部状态栏增设三联/四联视图快捷切换按钮（Normal, Sorter, Notes, Show）。
  - Retranslate UI 统一覆盖所有视图与控件。

---

## 4. Verification & Testing Strategy
- 覆盖全部 4 个视图模式互相切换无异常。
- 覆盖备注页视图加载、文本编辑与模型持久化。
- 覆盖母版视图加载、母版类型切换、关闭同步。
- 覆盖幻灯片浏览视图排序、复制、删除。
- 覆盖放映 HUD 创建、悬浮检测、按钮点击、画笔模式切换与安全退出。
- 验证所有文本 100% 支持 `safe_tr()`。
