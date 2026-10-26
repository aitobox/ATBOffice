# Specification: Issue #29 - Quire 交互式双向标尺 (水平/垂直标尺、页边距、缩进游标与制表位)

## 1. Overview & Objective
实现 Word 2003 经典的水平与垂直双向标尺控件 (`HorizontalRuler`, `VerticalRuler`, `TabSelectorWidget`)。
实时根据当前光标所在段落与节设置展示刻度；支持通过鼠标拖拽首行缩进小三角、悬挂缩进小三角与左/右边距滑块动态微调段落；在标尺上单选点选创建左对齐、居中、右对齐与小数点制表位；在页面画布上实时投射对齐虚线参考；松开鼠标后更新段落缩进并触发文档重排。

## 2. Reference Implementation
严格遵循本地原始代码实现规范：
- `.vibeoffice/public/quire/js/rulers.js`

## 3. Architecture & Components

### 3.1 `src/atboffice/modules/writer/views/ruler.py`
包含以下核心模块与组件：
1. **`RulerUnit` & 刻度换算**:
   - 支持 `"cm"`, `"inch"` / `"in"`, `"pt"`。
   - 换算系数：
     - cm: 28.3465 pt/cm
     - in: 72.0 pt/in
     - pt: 1.0 pt
   - 标尺单位主刻度与副刻度划分算法。
2. **`TabSelectorWidget` (标尺角落制表位类型切换钮)**:
   - 循环切换 7 种类型：
     - `left`: 左对齐制表位
     - `center`: 居中制表位
     - `right`: 右对齐制表位
     - `decimal`: 小数点制表位
     - `bar`: 竖线制表位
     - `firstLine`: 首行缩进
     - `hanging`: 悬挂缩进
   - 矢量图标绘制与当前选定类型信号通知。
3. **`HorizontalRuler` (水平标尺控件)**:
   - 继承 `QWidget`。
   - 包含背景区域区分：纸张外区域（灰色/深色）、页边距区域（边距底色）、正文文本区域（纯白底色）。
   - 刻度线与数字绘制（以正文文本左边缘为 0 原点）。
   - 交互式游标与标记物 (Markers)：
     - `first`: 首行缩进 (First Line Indent) 倒三角标记。
     - `hang`: 悬挂缩进 (Hanging Indent) 正三角标记。
     - `left`: 左侧矩形底座，拖拽时同时联动 `left` 与 `first_line` 绝对位移。
     - `right`: 右侧缩进正三角标记。
     - `tab`: 自定义制表位标记（根据对齐方式绘制对应形状）。
     - `margin_left` / `margin_right`: 页边距拖拽热区。
   - 交互操作与事件：
     - 单击正文区域添加制表位（或直接设置缩进）。
     - 拖拽游标动态更新位置并在画布上投射垂直参考虚线。
     - 拖拽制表位超出标尺上下边框（> 18px）时标记为删除，松开鼠标后清除该制表位。
     - 松开鼠标时提交段落修改：更新 `p.indent_first` / `p.indent_left` / `p.indent_right` / `p.p_pr.tabs`，触发重排。
     - 双击标尺触发制表位或页面设置事件。
4. **`VerticalRuler` (垂直标尺控件)**:
   - 继承 `QWidget`。
   - 显示当前页的上边距、正文高度、下边距。
   - 绘制垂直刻度线与旋转数字。
   - 支持拖拽上边距与下边距分界线，拖拽时在画布上投射水平对齐虚线。
   - 松开鼠标时更新对应节的上边距 `mt` / 下边距 `mb`。
5. **`WriterView` 整体布局集成**:
   - 采用 `QGridLayout` 将 `TabSelectorWidget`, `HorizontalRuler`, `VerticalRuler`, `WriterCanvasView` 完美贴合布局。
   - 标尺与画布的视口滚动 (`scroll_x`, `scroll_y`)、缩放比例 (`zoom`) 及光标位置事件实时双向绑定。

### 3.2 `WriterCanvasView` 扩展
- 支持投射对齐虚线参考：
  - `set_ruler_guide(x: float | None = None, y: float | None = None)`
  - `clear_ruler_guide()`
- 并在 `paintEvent` 中绘制半透明蓝色/黑色对齐虚线。

### 3.3 `Paragraph` 属性兼容层
- 在 `Paragraph` 模型中增加便捷属性：
  - `indent_left`: getter/setter 代理到 `self.p_pr.ind.left`
  - `indent_right`: getter/setter 代理到 `self.p_pr.ind.right`
  - `indent_first`: getter/setter 代理到 `self.p_pr.ind.first_line`

## 4. Edge Cases & Robustness
1. **空文档或无光标状态**:
   - 标尺安全 fallback 到默认页面宽度 (Letter: 612x792 pt, 边距 72/90 pt)。
2. **多列 (Multi-column) 或表格内标尺显示**:
   - 当光标位于表格单元格或多列栏内时，白色文本区根据单元格/列宽动态自适应。
3. **Alt 键无级微调**:
   - 按住 Alt 键拖拽时禁用步进吸附 (Snap)，支持精细到 0.1 pt 的连续微调。
4. **缩进防越界**:
   - 限制左缩进与悬挂缩进不得超过可用页宽，防止文字排版溢出崩溃。
5. **i18n 多语言**:
   - 100% 界面文字与 Tooltip 均包装于 `safe_tr()`，并实现 `retranslate_ui()`。

## 5. Verification Plan
- 编写 `tests/gui/test_ruler.py`，覆盖：
  - 标尺刻度与单位计算 (cm, inch, pt)
  - 缩进滑块几何位置计算与绘制
  - 拖拽首行缩进、左缩进、右缩进的段落属性更新
  - 添加与删除自定义制表位交互
  - 画布对齐虚线投射与清除
  - 标尺单位切换与缩放同步
  - 多语言动态切换 (`retranslate_ui`)
- 运行全量测试套件确认 0 退化。
