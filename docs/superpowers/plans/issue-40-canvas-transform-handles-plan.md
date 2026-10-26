# Implementation Plan - Issue #40: Lectern 基于 QGraphicsView/QGraphicsScene 的自由交互画布与图元变换手柄

## Tasks Overview

- [ ] **Task 1**: Geometry Path Helpers & Views Package Setup (`src/atboffice/modules/presentation/views/`)
- [ ] **Task 2**: `TransformHandleItem` & `ShapeGraphicsItem` (8 尺寸缩放手柄、1 旋转手柄与黄色调节手柄)
- [ ] **Task 3**: `SmartGuideController` (智能对齐辅助线与磁性吸附)
- [ ] **Task 4**: `SlideScene` (幻灯片画幅底板、Z-Order 层叠次序、对齐分布与编组解散)
- [ ] **Task 5**: `SlideCanvasView` & `PresentationView` 整合 (平滑缩放、右键菜单、快捷键、国际化与全量 GUI 测试验证)

---

### Task 1: Geometry Path Helpers & Views Package Setup
- **Files**:
  - `src/atboffice/modules/presentation/views/__init__.py`
  - `src/atboffice/modules/presentation/views/geometry_helper.py`
  - `tests/gui/test_slide_canvas.py`
- **Details**:
  - 创建 `geometry_helper.py`，提供常用 AutoShape 几何轮廓路径生成函数 (`create_shape_path(geom, w, h, adj=None)`)，支持 `rect`, `roundRect`, `ellipse`, `triangle`, `diamond`, `parallelogram`, `trapezoid`, `hexagon`, `octagon`, `rightArrow`, `line` 及调节参数。
  - 创建基础测试骨架。

---

### Task 2: `TransformHandleItem` & `ShapeGraphicsItem`
- **Files**:
  - `src/atboffice/modules/presentation/views/shape_item.py`
  - `tests/gui/test_slide_canvas.py`
- **Details**:
  - `TransformHandleItem`:
    - 8 尺寸缩放手柄 (`NW, N, NE, E, SE, S, SW, W`)。
    - 1 顶部自由旋转手柄 (`ROTATE`)，绘制绿色旋转小球及垂直连线。
    - 1 黄色菱形几何调节手柄 (`ADJUST`)，针对支持调节的形状动态定位。
    - 光标设置（`SizeFDiagCursor`, `SizeBDiagCursor`, `SizeVerCursor`, `SizeHorCursor`, `PointingHandCursor` 等）。
  - `ShapeGraphicsItem`:
    - 继承 `QGraphicsObject`，关联 `Shape` 模型。
    - 绘制填充（纯色/渐变/无）、描边（宽度、颜色、虚线）、阴影与内部文本。
    - 处理手柄拖拽：
      - Shift 约束：保持原始宽高比等比缩放。
      - Alt 约束：绕几何中心双向缩放。
      - 旋转拖拽：计算角度，按 Shift 按 15° 吸附。
      - 黄色手柄拖拽：更新 `shape.adj` 并重算路径。
  - TDD 验证手柄生成与拖拽变换。

---

### Task 3: `SmartGuideController` (智能对齐与磁性吸附)
- **Files**:
  - `src/atboffice/modules/presentation/views/smart_guides.py`
  - `tests/gui/test_slide_canvas.py`
- **Details**:
  - 实现 `SmartGuideController`：
    - 输入当前正在拖动的目标 item 和场景中所有其他 item 及幻灯片画布基准线（0, W/2, W, 0, H/2, H）。
    - 比较边缘（Left, Center, Right, Top, Middle, Bottom），当距离小于吸附阈值（6 pt）时计算吸附修正量 `(snap_dx, snap_dy)`。
    - 生成匹配的对齐辅助线定义（红色虚线）。
    - 提供绘制和清除辅助线机制。
  - 编写吸附和辅助线定位测试。

---

### Task 4: `SlideScene` (Z-Order、对齐分布与编组管理)
- **Files**:
  - `src/atboffice/modules/presentation/views/slide_canvas.py`
  - `tests/gui/test_slide_canvas.py`
- **Details**:
  - `SlideScene`:
    - 设置幻灯片画幅大小（默认 960x540 或 720x540），绘制白色幻灯片底纸、投影边框与灰色工作区背景。
    - 框选（Rubberband）多选支持。
    - Z-Order 调整：
      - `bring_to_front()`
      - `send_to_back()`
      - `bring_forward()`
      - `send_backward()`
      - 同步更新 `slide.shapes` 顺序和 item 的 `zValue`。
    - 对齐与分布：
      - `align_shapes('L' | 'C' | 'R' | 'T' | 'M' | 'B')`
      - `distribute_shapes('h' | 'v')`
    - 多选编组：
      - `group_selected()`：打包成 `Shape(type='group', kids=...)`
      - `ungroup_selected()`：解散编组恢复子图元。

---

### Task 5: `SlideCanvasView` & `PresentationView` 整合与完整验证
- **Files**:
  - `src/atboffice/modules/presentation/views/slide_canvas.py`
  - `src/atboffice/modules/presentation/view.py`
  - `tests/gui/test_slide_canvas.py`
- **Details**:
  - `SlideCanvasView`:
    - 视口管理：抗锯齿、居中、平滑缩放（`zoom_in`, `zoom_out`, `zoom_fit`, `set_zoom`）。
    - 右键上下文菜单与国际化：置于顶层、置于底层、上移一层、下移一层、对齐、组合、取消组合、剪切、复制、删除。
    - 键盘快捷键处理（Delete/Backspace, Ctrl+G, Ctrl+Shift+G, 方向键微移）。
    - `retranslate_ui()` 确保 100% 国际化。
  - 更新 `PresentationView`，嵌入 `SlideCanvasView` 并支持加载 `Slide`。
  - 执行 `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_slide_canvas.py -v` 并确保全量测试通过。
