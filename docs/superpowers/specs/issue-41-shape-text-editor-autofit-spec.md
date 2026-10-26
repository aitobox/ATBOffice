# Technical Specification - Issue #41: Lectern 形状与文本框原位富文本编辑、列表缩进与自适应字号 (Text AutoFit)

## 1. Overview & Context

本规范针对 Issue #41，为 ATBOffice 的演示文稿（Lectern，即 PowerPoint 2003 移植）模块构建图元与文本框内的原位富文本编辑子系统、大纲多级项目符号列表、大纲升降级缩进（Tab/Shift+Tab）以及 PPT 特色的文本自适应算法（Text AutoFit）。

作为 Lectern 架构演进的第三步（Step 3 of 15 under Epic #38，依赖已合并的 #39 核心模型与 #40 交互画布）：
- 参照原始代码：`.vibeoffice/public/lectern/js/textedit.js`
- 参照相关命令与交互：`.vibeoffice/public/lectern/js/commands.js`, `.vibeoffice/public/lectern/js/app.js` (A.indent, A.moveParas, shrinkToFit, autoSize)

---

## 2. Requirements & Acceptance Criteria

### Functional Requirements

1. **In-Place Rich Text Editor (`ShapeTextEditorItem` in `src/atboffice/modules/presentation/views/text_editor.py`)**:
   - 继承自 `QGraphicsTextItem` 或集成在 `ShapeGraphicsItem` 中的专用图元文本编辑对象。
   - 双击任何具有文字或支持文字的图形（矩形、文本框、占位符等），激活原位富文本编辑。
   - 保持图形的边距内衬（`insets: (top, right, bottom, left)`）与文本区域边界一致。
   - 编辑器内呈现动态光标（Caret），支持键盘方向键导航、鼠标拖拽选择文本范围、Ctrl+A 全选、剪切/复制/粘贴。
   - 当点击画布空白处、选中其他图元、按下 `Escape` 键时，自动同步（Sync）并将富文本内容提交并序列化至底层的 `Shape.text`（`TextBody` 模型），退出编辑状态。

2. **Character Formatting Operations (字符格式化)**:
   - 支持对当前选中文字（或光标所在 run）进行即时字符格式设置：
     - **粗体 (Bold)**: `set_bold(bool)` / `toggle_bold()` (Ctrl+B)
     - **斜体 (Italic)**: `set_italic(bool)` / `toggle_italic()` (Ctrl+I)
     - **下划线 (Underline)**: `set_underline(bool)` / `toggle_underline()` (Ctrl+U)
     - **字号 (Font Size)**: `set_font_size(float)` / `step_font_size(int)` (Ctrl+Shift+>/<)
     - **字体家族 (Font Family)**: `set_font_family(str)` (如 Arial, SimSun, Tahoma 等)
     - **文字颜色 (Font Color)**: `set_font_color(str)` (十六进制如 `#FF0000` 或预设名)
     - **文字阴影 (Shadow)**: `set_text_shadow(bool)` / `toggle_text_shadow()`
     - **清除格式 (Reset Formatting)**: `reset_character_formatting()` (Ctrl+Space)

3. **Multi-level Outline & Bullet Indent (大纲列表多级缩进与项目符号样式)**:
   - 支持 0 到 8 级（9 个大纲层级，涵盖 5 级以上）项目符号与编号列表。
   - 快捷键支持：
     - **Tab**：在段首或选中多行时执行“增加缩进 / 降级 (Demote)”（`level = min(level + 1, 8)`）。
     - **Shift+Tab**：执行“减少缩进 / 升级 (Promote)”（`level = max(level - 1, 0)`）。
     - **Backspace**：在空段落或段首且 `level > 0` 时，自动提升大纲级别。
     - **Enter**：换行时继承当前段落的大纲级别与项目符号属性。
   - 自动关联不同级别的母版字号与项目符号样式（根据 `text.py` 的 `BODY_BULLETS`、`BODY_SIZES`、`BODY_MARL`、`BODY_INDENT`）。
   - 支持设置项目符号类型：`none`（无）、`char`（字符符号如 `•`, `–`, `»` 等）、`num`（编号列表 `1.`, `2.` 等）。

4. **Text AutoFit Algorithm (文本自适应算法)**:
   - 算法参照 PowerPoint 与 `.vibeoffice` 的 `shrinkToFit`：
     - 当形状或占位符启用 `autofit == "norm"` 或内容超出可用高度时：
     - 计算文本所需总排版高度 `need = text_layout_height` 与图元文本框可用高度 `avail = box_height - inset_top - inset_bottom`。
     - 若 `need > avail`，计算最佳缩放因子：
       $$\text{scale} = \max\left(0.25, \text{floor}\left(\frac{\text{avail}}{\text{need}} \times 20\right) / 20\right)$$
       当空间不足时等比平滑压缩字号（缩小至 80%~95% 或自适应阶梯），确保文字无溢出地容纳在形状内部。
     - 若 `autofit == "shape"`（如普通文本框）：当文字行数增加或字号增大时，自适应扩大形状尺寸 `sh.h`。
     - 提供纯函数计算接口 `calculate_autofit_scale(need_height: float, avail_height: float, cur_scale: float = 1.0) -> float`。

5. **Model Synchronization (模型与富文本双向同步)**:
   - 从 `TextBody` 到 `QTextDocument`：
     - 依次将 `Paragraph` 解析为 `QTextBlock`，根据 `level` 配置 `QTextBlockFormat`（`leftMargin`、`textIndent`），根据 `TextRun` 设置 `QTextCharFormat`（字体、字号、加粗、倾斜、下划线、颜色）。
   - 从 `QTextDocument` 到 `TextBody`：
     - 遍历所有 `QTextBlock` 与其内部的 `QTextFragment`，重构 `Paragraph`、`TextRun` 列表。
     - 保持原有未修改字段（`props`, `end_props`）不丢失。

6. **Full i18n & Event Hooks**:
   - 右键文字上下文菜单（粗体、斜体、下划线、项目符号、增大字号、减小字号、增加缩进、减少缩进）。
   - 所有 UI 文本均使用 `safe_tr()` / `tr()` 包装，实现地道中文与英文双语支持。
   - 实现 `retranslate_ui()`。

---

## 3. Architecture & Class Design

### Class Breakdown: `src/atboffice/modules/presentation/views/text_editor.py`

1. **`ShapeTextEditorItem(QGraphicsTextItem)`**:
   - 挂载在 `ShapeGraphicsItem` 之上的富文本原位编辑组件。
   - 属性与方法：
     - `shape_item: ShapeGraphicsItem`
     - `text_body: TextBody`
     - `start_editing()`: 初始化文档、设置交互标志 `Qt.TextEditorInteraction`、聚焦、显示光标。
     - `commit_and_finish()`: 将文档状态写回 `shape.text`，计算 AutoFit，隐藏或移除编辑图元，触发更新。
     - `calculate_content_height() -> float`: 获取当前排版渲染高度。
     - `apply_autofit(mode: str = "norm")`: 自动调整字号或形状尺寸。
     - `keyPressEvent(event: QKeyEvent)`: 拦截 Tab、Shift+Tab、Escape、Enter、Backspace 进行层级与格式处理。
     - `focusOutEvent(event: QFocusEvent)`: 失焦时自动提交。

2. **Formatting Helper APIs**:
   - `set_bold(enabled: bool | None = None)`
   - `set_italic(enabled: bool | None = None)`
   - `set_underline(enabled: bool | None = None)`
   - `set_font_size(size: float)`
   - `set_font_family(family: str)`
   - `set_font_color(color_hex: str)`
   - `set_text_shadow(enabled: bool)`
   - `promote()`: 提升大纲级别（`indent(-1)`）
   - `demote()`: 降低大纲级别（`indent(1)`）
   - `set_bullet_type(b_type: str, char: str = "•")`

3. **`calculate_autofit_scale(need_height: float, avail_height: float, cur_scale: float = 1.0) -> float`**:
   - 独立的数学算法工具函数，便于纯单元测试与高效重用。

4. **Integration with `ShapeGraphicsItem` & `SlideScene`**:
   - 在 `ShapeGraphicsItem` 中重写 `mouseDoubleClickEvent(event)`:
     - 实例化或激活 `ShapeTextEditorItem`。
   - 在 `ShapeGraphicsItem` 绘制逻辑中：
     - 当正在编辑时，隐藏原静态文字绘制，避免重影。
     - 编辑结束时，重新绘制带格式的富文本。

---

## 4. Edge Cases & Resilience

| 边界情况 | 处理策略 |
|---|---|
| 图元没有任何文字 (`text` 为 None 或空) | 双击时自动创建空 `TextBody` 和初始 `Paragraph(level=0)`，光标置于 (0,0) 并等待输入。 |
| 输入大量文本导致严重超出图形 | 动态计算 AutoFit 比例，最小字号保护限制为 `0.25 * base_size` 或 8pt，防止字号坍缩为 0。 |
| 按 Tab 键时如果在形状或文本框编辑模式 | 拦截 Tab 默认的控件焦点切换行为，转换为大纲降级 (Demote) 或插入制表符。 |
| 按 Shift+Tab 键时 | 拦截 Shift+Tab，转换为大纲升级 (Promote)；当 level 已经为 0 时保持为 0，不越界。 |
| 带有旋转角度的图元原位编辑 | 随父级 `ShapeGraphicsItem` 自动继承坐标系变换与旋转，光标与选框保持与图元一致的倾斜角。 |
| 用户连续双击或快速点击画布外部 | 幂等检测当前编辑状态，防抖并安全触发 `commit_and_finish()`，防止重复创建编辑器。 |

---

## 5. Verification Plan

1. **Unit Tests (`tests/unit/presentation/test_text_autofit.py`)**:
   - 测试 `calculate_autofit_scale`: 空间充足时为 1.0，空间不足时平滑缩减至 0.8~0.95 及以下。
   - 测试 `TextBody` 与富文本文档模型的互转：多段落、不同 level、加粗/斜体/颜色提取无损。
   - 测试大纲层级边界检查：升降级不小于 0 且不大于 8。

2. **GUI Tests (`tests/gui/test_textedit.py`)**:
   - `pytest-qt` 驱动 `SlideCanvasView` 和 `SlideScene`。
   - 双击测试：双击矩形图元，验证文本编辑器成功激活并获取焦点。
   - 按键测试：发送字符输入，验证输入内容。
   - 列表缩进测试：发送 Tab 键验证大纲降级 (`level == 1`)，发送 Shift+Tab 验证大纲升级 (`level == 0`)。
   - 格式设置测试：调用加粗、斜体、字号设置，验证文本格式属性。
   - 失焦与提交测试：点击空白区域，验证富文本成功写回 `Shape.text`，图形文字更新。
