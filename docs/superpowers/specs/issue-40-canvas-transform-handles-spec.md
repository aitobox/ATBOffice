# Technical Specification - Issue #40: Lectern 基于 QGraphicsView/QGraphicsScene 的自由交互画布与图元变换手柄

## 1. Overview & Context

本规范针对 Issue #40，为 ATBOffice 的演示文稿（Lectern，即 PowerPoint 2003 移植）模块构建基于 PySide6 `QGraphicsView` + `QGraphicsScene` 的高性能自由交互编辑画布。

作为 Lectern 架构演进的关键第二步（Step 2 of 15 under Epic #38，依赖已合并的 #39 核心对象模型），本模块负责将内存中的演示文稿幻灯片模型 (`Slide` / `Shape`) 呈现为富有视觉反馈、操作手感精准的交互编辑画布：
- 8 尺寸缩放手柄（按 Shift 保持等比，按 Alt 绕中心缩放）
- 顶部自由旋转手柄（带连线，按 Shift 按 15° 吸附）
- 黄色菱形几何调节手柄（AutoShape 预设参数动态调节）
- 智能磁性吸附对齐虚线（Smart Guides）
- 图元层叠次序调整（置于顶层、置于底层、上移一层、下移一层）
- 对齐分布（左对齐、居中、右对齐、顶端对齐、垂直居中、底端对齐，横向/纵向均匀分布）
- 多选与编组管理（Group / Ungroup / 撤销重组）

本实现严格对照 `.vibeoffice/public/lectern/js/editor.js` 与 `.vibeoffice/public/lectern/js/app.js`。

---

## 2. Requirements & Acceptance Criteria

### Functional Requirements

1. **Slide Canvas & Viewport (`SlideCanvasView`, `SlideScene`)**:
   - 基于 PySide6 的 `QGraphicsView` 与 `QGraphicsScene`。
   - 具有清晰的幻灯片画幅矩形（默认 960x540 或 720x540，白底纸张，带深色边缘微阴影），背景为中性浅灰/深灰画布。
   - 支持平滑缩放：`zoom_in()`, `zoom_out()`, `set_zoom()`, `zoom_fit()`。
   - 支持框选（Marquee / RubberBand selection）：在空白区域拖拽拉出半透明虚线选框，选中交叠图元；支持按 Shift/Ctrl 增减选择。

2. **Custom Shape Graphics Item (`ShapeGraphicsItem`)**:
   - 继承自 `QGraphicsObject` 或 `QGraphicsItem`，封装 `Shape` 模型数据与实时双向同步。
   - 渲染外观：根据 `Shape` 的 `geom`（矩形、圆角矩形、椭圆、三角形、菱形等）、`fill`（纯色/渐变/无）、`line`（线宽、颜色、虚线样式）、`shadow` 绘制矢量图形。
   - 渲染内嵌文本：支持 `Shape.text`，在几何图形内部居中或按对齐方式排版绘制多行段落文本。
   - 支持图元位置、大小、旋转角度（`rot`）与几何调节参数（`adj`）的双向绑定。

3. **Transformation Handles (`TransformHandleItem`)**:
   - **8 尺寸手柄**：分布于外围包围盒的 `NW`, `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`。拖拽时动态调整图元坐标与尺寸。
     - 保持等比：按住 `Shift` 拖拽角手柄时保持图元原始宽高比。
     - 中心缩放：按住 `Alt`（或 `Ctrl`）拖拽手柄时绕几何中心双向对称缩放。
     - 相应鼠标光标：斜向光标（`SizeFDiagCursor`, `SizeBDiagCursor`）、纵向光标（`SizeVerCursor`）、横向光标（`SizeHorCursor`）。
   - **1 自由旋转手柄**：位于顶部中央手柄上方，由一根连线连接，呈绿色圆点。
     - 拖拽时计算相对几何中心的极坐标角度，动态旋转图元。
     - 按住 `Shift` 时以 15° 为步长吸附（0°, 15°, 30°, ... 345°）。
     - 光标为旋转手势/十字光标。
   - **黄色几何调节手柄**：针对具有 `adj` 调节参数的 AutoShape（如 `roundRect`, `triangle`, `parallelogram`, `trapezoid`, `arrow` 等），呈现黄色菱形调节手柄。拖拽可动态改变调节值，实时刷新几何外形。

4. **Smart Guides & Magnetic Snapping (智能对齐与磁性吸附)**:
   - 拖拽移动或缩放图元时，自动检测与其他图元及幻灯片基准线的对齐关系：
     - 水平对齐线：左边缘（Left）、水平中心（Center）、右边缘（Right）。
     - 垂直对齐线：顶边缘（Top）、垂直居中（Middle）、底边缘（Bottom）。
     - 幻灯片基准线：幻灯片左边缘 (0)、水平中线 (W/2)、右边缘 (W)、顶边缘 (0)、垂直中线 (H/2)、底边缘 (H)。
   - 磁性吸附门限：距离在吸附阈值（如 6 pt / 像素）内时自动吸附对齐。
   - 视觉反馈：在匹配对齐轴上绘制醒目的红色虚线引导线（`Smart Guide Lines`），拖拽松开后自动消除。

5. **Z-Order Layer Stacking (图元层叠次序)**:
   - `bring_to_front()`：置于顶层。
   - `send_to_back()`：置于底层。
   - `bring_forward()`：上移一层。
   - `send_backward()`：下移一层。
   - 同步更新底层 `slide.shapes` 列表顺序与 scene item 的 `zValue`。

6. **Alignment & Distribution (图元对齐与均匀分布)**:
   - 对齐操作：
     - `align_left()`, `align_center()`, `align_right()`
     - `align_top()`, `align_middle()`, `align_bottom()`
     - 单选或开启“对齐到幻灯片”时，以幻灯片边缘为基准；多选时，以所有选中图元的联合外接包围盒为基准。
   - 分布操作：
     - `distribute_horizontally()`：水平均匀分布（间距相等）。
     - `distribute_vertically()`：垂直均匀分布（间距相等）。

7. **Grouping & Ungrouping (多选编组与解散编组)**:
   - `group_selected()`：将选中的 2 个及以上顶层图元打包为一个 `type='group'` 的复合 `Shape`，包围盒紧贴子元素联合边界。
   - `ungroup_selected()`：解散选中的编组，将子元素还原至幻灯片主列表中，保留旋转与位移。

8. **i18n & Context Menu**:
   - 右键快捷菜单：置于顶层、置于底层、上移一层、下移一层、对齐、组合、取消组合、剪切、复制、删除等。
   - 100% 文本国际化（`safe_tr()` / `tr()`），提供地道生动的中文与英文。
   - 实现 `retranslate_ui()`。

---

## 3. Architecture & Module Structure

```
src/atboffice/modules/presentation/
├── __init__.py
├── view.py                       # Updated PresentationView embedding SlideCanvasView
├── models/                       # Models from Issue #39 (Presentation, Slide, Shape, etc.)
└── views/
    ├── __init__.py               # Re-exports views
    ├── shape_item.py             # ShapeGraphicsItem & TransformHandleItem
    └── slide_canvas.py           # SlideCanvasView, SlideScene, SmartGuideController
```

### Detailed Component Roles

- `TransformHandleItem`:
  - 继承自 `QGraphicsItem`。
  - 负责绘制单一手柄（8 方位尺寸方块、顶部旋转圆球、黄色调节菱形）。
  - 根据手柄类型和角度设置对应光标。

- `ShapeGraphicsItem`:
  - 继承自 `QGraphicsObject`，拥有 signals（如 `geometryChanged`, `selectionChanged`）。
  - 管理手柄显示/隐藏（仅在选中时显示手柄）。
  - 负责 Shape 渲染（矢量路径、填充、描边、阴影、文本）。
  - 处理缩放、旋转、调节事件并同步回 `Shape` 模型。

- `SmartGuideController`:
  - 负责检测待吸附元素与目标元素/画布中线的边缘与中心距离。
  - 计算磁性吸附偏移量（`dx, dy`）。
  - 负责在 Scene 上临时绘制/清理红色的辅助虚线。

- `SlideScene`:
  - 管理当前 `Slide` 的所有图元。
  - 处理框选多选（Rubberband）。
  - 提供 Z-Order、对齐、分布、组合、解散接口。

- `SlideCanvasView`:
  - 提供缩放、视口居中、滚轮操作、快捷键与右键上下文菜单。

---

## 4. Verification Plan

- 编写全面的 pytest 单元与 GUI 测试：`tests/gui/test_slide_canvas.py`
  - 测试画布初始化、尺寸自适应与画幅渲染
  - 测试图元选择与变换手柄生成（8 尺寸手柄、1 旋转手柄、黄色调节手柄）
  - 测试尺寸缩放（Shift 等比约束、Alt 中心缩放）
  - 测试自由旋转与 Shift 15° 吸附
  - 测试几何调节手柄（roundRect, triangle 等调节值变化）
  - 测试智能吸附线（Smart Guides 磁性吸附与坐标对齐计算）
  - 测试层叠次序（置于顶层/底层、上移/下移一层）
  - 测试对齐分布（六向对齐与横纵均匀分布）
  - 测试多选编组与解散编组（Group / Ungroup）
  - 测试 i18n 与 `retranslate_ui()`
