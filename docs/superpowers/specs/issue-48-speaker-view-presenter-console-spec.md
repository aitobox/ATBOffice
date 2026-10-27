# Technical Specification: Lectern 双屏演讲者控制台 (Speaker View)

## 1. Overview
实现专业级双屏演讲者控制台（Presenter / Speaker View），完整复刻与超越 PowerPoint 2003 的经典演讲者控制体验。当检测到双显示器时，主屏幕呈现包含当前幻灯片、大字号演讲者备注、下一页幻灯片预览与高精度计时器的全功能控制台；投影屏幕全屏呈现纯净放映内容；支持激光红点提示与荧光笔/画笔墨迹实时标注，并提供无黑场抽屉式跳页导航。

## 2. Requirements & Acceptance Criteria
- [x] 实现模块 `src/atboffice/modules/presentation/slideshow/presenter_view.py`。
- [x] 演讲者控制台显示实时流逝时间与系统当前时间，支持暂停、继续与重置计时。
- [x] 提供下一页幻灯片预览与大字号演讲者备注，支持备注字体放大与缩小。
- [x] 提供幻灯片快捷缩略图抽屉（Drawer/Tray），支持随时无黑场平滑跳转任意幻灯片。
- [x] 演讲过程中支持鼠标临时切换为激光笔（半透明红晕光斑）或画笔/荧光笔（自由墨迹绘制并可选择保留或丢弃）。
- [x] 支持与观众放映视口（`SlideShowView`）双向同步（切页、转场、黑屏/白屏、墨迹与激光笔轨迹）。
- [x] 适配单屏调试模式与多显示器投影模式，提供“交换显示器”功能。
- [x] 100% 国际化适配（`safe_tr` / `retranslate_ui`），中文与英文优雅显示。
- [x] 编写详尽自动化测试 `tests/gui/test_presenter_view.py`，覆盖全部核心状态与边缘条件。

## 3. Architecture & Class Design

### 3.1 Data Structures
```python
@dataclass
class InkPoint:
    x: float
    y: float

@dataclass
class InkStroke:
    points: list[tuple[float, float]]
    color: str = "#FF0000"
    width: float = 2.0
    alpha: float = 1.0
    is_highlighter: bool = False
```

### 3.2 View Classes
1. `SlideCanvasView(QWidget)`:
   - 具备独立绘图缩放逻辑，负责渲染幻灯片图像、激光笔红晕光圈与墨迹笔触。
   - 支持模式：`arrow`（普通箭头/换页）、`laser`（激光红点）、`pen`（圆珠笔）、`highlighter`（荧光笔）、`eraser`（橡皮擦）。
   - 发射信号：`strokeAdded(int, InkStroke)`, `strokeErased(int, int)`, `laserMoved(QPointF)`.

2. `PresenterConsole(QMainWindow)` (别名 `PresenterView`):
   - 核心演讲者控制台窗口。
   - 顶部工具栏：
     - 流逝时间（HH:MM:SS）、当前系统时间、暂停/重置计时按钮、交换显示屏按钮、结束放映按钮。
   - 中部主区域：
     - 左侧：当前幻灯片视口（带激光笔与墨迹交互），下方放置上一页/下一页、画笔菜单、黑屏白屏快捷按钮。
     - 右侧：
       - 上半部：下一页幻灯片预览（带“下一张”标题及提示）。
       - 下半部：演讲者备注显示区，带备注字号放大/缩小控件。
   - 底部抽屉：
     - 幻灯片导航栏（快捷网格/水平缩略图托盘），点击无黑场平滑跳页。
   - 双屏联动：
     - 持有 `audience_view: SlideShowView` 引用，切页与交互实时双向绑定。

## 4. Edge Cases & Robustness
1. **零幻灯片或单张幻灯片**：控制台正确呈现空状态或“放映结束”占位，不发生越界或除以零异常。
2. **无备注幻灯片**：显示温和浅色占位提示文本，备注缩放按钮正常工作。
3. **单屏幕环境**：自动以独立窗口启动演讲者控制台与放映视口，便于开发者调试与演练。
4. **放映结束墨迹保存**：若产生了墨迹，弹窗确认保留或丢弃；若保留，写入幻灯片自定义属性。
5. **快捷键全映射**：支持 PageUp/Down、Space、Ctrl+P、Ctrl+L、Ctrl+E、B、W、Esc 等经典按键。
