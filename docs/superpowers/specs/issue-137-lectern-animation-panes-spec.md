# Spec: Issue #137 - 实现 Lectern 幻灯片切换与自定义动画交互任务窗格

## 1. Overview & Objective
Lectern 拥有底层的 58 种幻灯片切换算法与进出场动画时序模型（`slideshow/transitions.py` 与 `slideshow/animations.py`），但用户无法通过可视化的交互面板进行配置。
本项目将在右侧任务窗格（`LecternTaskPane`）中实现并集成两大核心任务窗格：
1. **幻灯片切换窗格 (`SlideTransitionPane`)**：用于可视化选择 58 种切换视效、调整速度、音频与自动换片时延，并支持一键应用到全部幻灯片及即时预览。
2. **自定义动画窗格 (`AnimationPane`)**：提供「添加效果」四类级联菜单（进入、强调、退出、动作路径）、选定动画时序列表管理（拖拽与上/下箭头重排）、属性微调（触发方式、方向、速度、延迟），并与幻灯片画布双向联动选择。
3. **幻灯片放映全屏引擎与 PPTX 序列化集成**：将切换与动画状态实时传递至 `SlideShowView`，并在导出为 `.pptx` 时完整写入 `<p:transition>` 与 `<p:timing>`，确保跨软件兼容。

---

## 2. Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      LecternWorkspace                       │
│  ┌──────────────────────┐  ┌─────────────────────────────┐  │
│  │ SlideCanvasView/Scene│  │       LecternTaskPane       │  │
│  │                      │  │ ┌─────────────────────────┐ │  │
│  │  - Shape Selection   │◄─┼─┤ SlideTransitionPane     │ │  │
│  │  - Animation Preview │  │ │  (Transitions Catalogue)│ │  │
│  │                      │  │ ├─────────────────────────┤ │  │
│  │                      │  │ │ AnimationPane           │ │  │
│  │                      │  │ │  (Effects, Timing, List)│ │  │
│  └──────────────────────┘  │ └─────────────────────────┘ │  │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
    ┌────────────────────┐         ┌────────────────────┐
    │    SlideShowView   │         │ PPTX I/O Engine    │
    │ (Transitions &     │         │ (writer_slide.py & │
    │  Step Animations)  │         │  pptx_reader.py)   │
    └────────────────────┘         └────────────────────┘
```

### 2.1 State & Model Synchronizations
- `Slide.transition`: 存储幻灯片切换配置（`type`, `speed`, `click`, `after`, `dir`, `orient`, `spokes`, `thruBlk`）。
- `Slide.animations`: 存储形状动画列表（`Animation(id, sid, cls, eff, dir, start, dur, delay, by)`）。
- `LecternTaskPane`:
  - 注册 `transition`（幻灯片切换）与 `customAnim`（自定义动画）两个窗格；
  - 顶部下拉菜单展示所有注册面板名称；
  - 支持前后历史导航与标题联动；
  - 幻灯片切换时通知各面板刷新绑定的 `Slide` 实例。

---

## 3. Detailed Component Specifications

### 3.1 SlideTransitionPane (`src/atboffice/modules/presentation/views/transition_pane.py`)
- **布局层次**：
  1. 效果列表（`QListWidget`）：从 `slideshow/transitions.py` 的 `TRANSITION_CATALOGUE` 加载 58 种效果，第一项为「无切换」；当前选中的效果高亮显示并自动滚动定位。
  2. 修改切换效果群组（`QGroupBox`）：
     - 速度下拉框（`QComboBox`）：慢速 (Slow, 1000ms)、中速 (Medium, 750ms)、快速 (Fast, 500ms)。
     - 声音下拉框（`QComboBox`）：[无声音] (支持预留)。
  3. 换片方式群组（`QGroupBox`）：
     - 复选框「单击鼠标时」(On mouse click，默认 True)。
     - 复选框「自动换片时间」(Automatically after) + 浮点/整数秒数调节器（`QDoubleSpinBox`，0.0~3600.0 秒）。
  4. 操作按钮栏：
     - 「应用于所有幻灯片」(Apply to All Slides)。
     - 「▶ 播放」(Play)：触发当前幻灯片切换预览。
     - 「幻灯片放映」(Slide Show)：唤起全屏播放。
     - 「自动预览」(AutoPreview) 复选框。
- **公共 API 与信号**：
  - `set_slide(slide: Slide | None)`
  - `set_presentation(presentation: Presentation | None)`
  - `transitionChanged = Signal(object)`
  - `applyToAllRequested = Signal(object)`
  - `previewRequested = Signal()`
  - `slideshowRequested = Signal()`
  - `retranslate_ui()`

### 3.2 AnimationPane Enhancements (`src/atboffice/modules/presentation/views/animation_pane.py`)
- **现有功能保持并增强**：
  1. 拖拽重排：配置 `list_anims.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)` 并监听行重排事件，保证与 `slide.animations` 实时一致。
  2. 计时属性扩展：在 `grp_modify` 中增加「延迟 (Delay)」微调框（`QDoubleSpinBox`，单位秒，默认 0.0s）。
  3. 双向高亮联动：
     - 画布选中形状时，`set_selected_shapes([shape_id])` 自动高亮并定位列表中该形状绑定的第一条动画。
     - 动画列表选中条目时，发射 `shapeSelectionRequested(str)` 信号联动画布聚焦对应形状。
  4. 支持右键上下文菜单与双击播放。
  5. 国际化：全面支持 `safe_tr()` 与 `retranslate_ui()`。

### 3.3 Workspace & TaskPane Integration (`src/atboffice/modules/presentation/views/workspace.py`)
- 在 `LecternTaskPane` 中维护动态标题字典 `self.pane_titles: dict[str, str]`。
- 在 `LecternWorkspace._init_ui()` 中实例化并注册：
  - `self.transition_pane = SlideTransitionPane(self.task_pane)`
  - `self.task_pane.register_pane("transition", safe_tr("幻灯片切换"), self.transition_pane)`
  - `self.animation_pane = AnimationPane(self.task_pane)`
  - `self.task_pane.register_pane("customAnim", safe_tr("自定义动画"), self.animation_pane)`
- 在 `_refresh_active_slide()` 中同步更新 `transition_pane.set_slide(cur)` 与 `animation_pane.set_slide(cur, selected_ids)`。
- 绑定 `applyToAllRequested`：将当前切换效果拷贝至所有幻灯片并刷新缩略图。

### 3.4 PPTX I/O Persistence (`writer_slide.py` & `pptx_reader.py`)
- 在 `writer_slide.py` 中增强 `timing_to_xml`：
  - 除了媒体节点外，将 `slide.animations` 中的动画按顺序序列化为 `<p:cTn presetClass="..." presetID="..." presetSubtype="..." dur="..." delay="...">` 等节点，使 Office 2003 / 现代 PowerPoint 能完整识别形状动画。
  - 增强 `transition_to_xml` 保证属性（方向、细分类型）正确映射。

---

## 4. Edge Cases & Resilience
1. **空幻灯片与无形状状态**：
   - 切换窗格与动画窗格应具备空状态保护，禁用或显示友好说明，严禁抛出 `IndexError` 或 `AttributeError`。
2. **多选与无选区**：
   - 画布无选区时，点击「添加效果」不崩溃，自动提示或回退至首个可用形状。
3. **应用于全部幻灯片**：
   - 使用深拷贝 `copy.deepcopy(cur.transition)` 避免所有幻灯片共享同一个实例导致对象修改冲突。
4. **语言即时热切换**：
   - 调用 `retranslate_ui()` 时必须重置所有控件文字、下拉框选项、列表项工具提示以及菜单标题。
