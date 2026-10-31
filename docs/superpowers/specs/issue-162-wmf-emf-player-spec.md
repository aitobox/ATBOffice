# Specification: Issue #162 - 纯 Python 版 WMF / EMF 二进制矢量图元解析与 QPainter 播放器

## 1. Overview & Problem Statement
在 DOCX、PPTX、RTF 和 XLS 历史文档及剪贴画库中，大量矢量图形、组织结构图、数学公式使用 16 位 Windows Metafile (WMF) 或 32 位 Enhanced Metafile (EMF) 二进制格式存储。现代跨平台桌面与网页环境无法直接渲染这类格式。

在原版项目 `.vibeoffice/public/common/metafile.js` 中，通过纯 JavaScript 解析 GDI 绘图记录流并在 Canvas 上重放，实现了 100% 高保真离线渲染。
在 ATBOffice (Python 3.12+ / PySide6) 中，我们需要实现纯 Python 的 WMF/EMF 矢量图元解析器与 QPainter 播放器 `src/atboffice/vfs/metafile_player.py`，支持将 WMF/EMF 数据高保真回放至任意 `QPainter`（QWidget、QPixmap、QImage、QPrinter 等），并提供便捷的 `render_to_image` 与 `render_to_bytes` (PNG/JPEG) 转换接口。

---

## 2. Requirements & Acceptance Criteria
1. **WMF 格式支持**:
   - 识别 Aldus Placeable Header (`0x9AC6CDD7`) 及标准 18 字节 WMF 头部。
   - 解析窗口/视口映射（`SETWINDOWORG`, `SETWINDOWEXT`, `OFFSETWINDOWORG`, `SCALEWINDOWEXT`）。
   - 解析基本图形记录：`POLYGON` (`0x0324`), `POLYLINE` (`0x0325`), `POLYPOLYGON` (`0x0538`), `RECTANGLE` (`0x041B`), `ROUNDRECT` (`0x061C`), `ELLIPSE` (`0x0418`), `ARC` (`0x0817`), `PIE` (`0x081A`), `CHORD` (`0x0830`), `LINETO` (`0x0213`), `MOVETO` (`0x0214`)。
   - 解析 GDI 对象生命周期：`CREATEPENINDIRECT` (`0x02FA`), `CREATEBRUSHINDIRECT` (`0x02FC`), `CREATEFONTINDIRECT` (`0x02FB`), `SELECTOBJECT` (`0x012D`), `DELETEOBJECT` (`0x01F0`)。
   - 解析文本与文字对齐：`TEXTOUT` (`0x0521`), `EXTTEXTOUT` (`0x0A32`), `SETTEXTALIGN` (`0x012E`), `SETTEXTCOLOR` (`0x0209`), 支持 Windows 多代码页解码。
   - 解析裁剪与状态保存：`SAVEDC` (`0x001E`), `RESTOREDC` (`0x0127`), `INTERSECTCLIPRECT` (`0x0416`)。
   - 解析位图与光栅操作：`STRETCHDIB` (`0x0F43`), `DIBBITBLT` (`0x0940`), `DIBSTRETCHBLT` (`0x0B41`), `PATBLT` (`0x061D`)。

2. **EMF 格式支持**:
   - 识别 32 位 EMF 头部 `EMR_HEADER` (`0x00000001`) 与特征标识 `0x464D4520` (" EMF")。
   - 解析设备边界、尺寸换算（0.01 mm 换算至设备像素与点阵）。
   - 解析仿射变换矩阵（`EMR_SETWORLDTRANSFORM`, `EMR_MODIFYWORLDTRANSFORM`）。
   - 解析 16 位和 32 位坐标的几何记录：`EMR_POLYGON`, `EMR_POLYGON16`, `EMR_POLYLINE`, `EMR_POLYLINE16`, `EMR_POLYBEZIER`, `EMR_POLYBEZIER16`, `EMR_POLYBEZIERTO`, `EMR_POLYBEZIERTO16`, `EMR_POLYPOLYGON`, `EMR_POLYPOLYGON16`。
   - 解析路径系统：`EMR_BEGINPATH`, `EMR_ENDPATH`, `EMR_CLOSEFIGURE`, `EMR_STROKEPATH`, `EMR_FILLPATH`, `EMR_STROKEANDFILLPATH`, `EMR_ABORTPATH`。
   - 解析扩展画笔、画刷与字体：`EMR_EXTCREATEPEN`, `EMR_EXTCREATEFONTINDIRECTW`, `EMR_CREATEDIBPATTERNBRUSHPT`，以及预设系统存量对象 (Stock Objects)。
   - 解析文本与位图扩展记录：`EMR_EXTTEXTOUTW`, `EMR_EXTTEXTOUTA`, `EMR_STRETCHDIBITS`, `EMR_BITBLT`, `EMR_STRETCHBLT`。

3. **DIB 位图解码器**:
   - 支持 `BITMAPINFOHEADER` (40+ bytes) 与 `BITMAPCOREHEADER` (12 bytes)。
   - 支持 1bpp、4bpp、8bpp（带调色板）、16bpp (5-5-5)、24bpp (BGR)、32bpp (BGRA/BGRX)。
   - 支持光栅混合操作：AND 掩码 + XOR 异或位图透明合成。

4. **PySide6 / QPainter 映射**:
   - 使用 `QPen`, `QBrush`, `QPainterPath`, `QFont`, `QTransform`, `QColor` 实现 1:1 精确映射。
   - 保护 Painter 状态：进入与退出均使用 `painter.save()` / `painter.restore()`。
   - 支持回放到指定的目标矩形 `target_rect` 或自动按原生比例渲染到 `QImage`。

---

## 3. Pre-Implementation Reflection (Edge Case Analysis)
| 异常/边界场景 | 潜在风险 | 解决方案 |
|---|---|---|
| 空数据或截断二进制流 | 越界索引引发 `IndexError` 或 `struct.error` | 使用结构化检查，所有解包统一保护并捕获异常，安全跳出或返回 `None` |
| 边界宽高为 0 或倒置 | 除零异常 `ZeroDivisionError`，尺寸无效 | 计算比例时除数 fallback 为 1；坐标翻转通过 `fx, fy` 仿射镜像安全处理 |
| 恶意或超大图元坐标 (>20,000 px) | 内存爆表 / OOM | 限制单图最大尺寸 `max_px`（默认 1200），限制循环记录最多 400,000 条防死循环 |
| 奇数对齐字节 / 结构体内填充字节 | 偏移量未对齐导致后续记录错位 | 严格按照 record 的 `size` 字段步进，字符串与点集遵循 2/4 字节对齐补零规则 |
| 缺乏字体或指定字体不存在 | Qt 降级导致文字溢出 | 映射 Windows 经典字体名至系统常见字体（如 Arial, SimSun, Tahoma），安全 fallback |
| DIB 掩码光栅合成 (AND + XOR) | 图标透明通道变黑底 | 保留前序 AND 掩码并在后续 XOR 时合成具有 Alpha 通道的 ARGB32 QImage |

---

## 4. Architecture & Interface Design
模块路径：`src/atboffice/vfs/metafile_player.py`

### 4.1 核心类与方法
- `MetafilePlayer`:
  ```python
  class MetafilePlayer:
      def __init__(self, painter: Optional[QPainter] = None, target_rect: Optional[QRectF] = None):
          ...
      def play(self, data: bytes, painter: QPainter, target_rect: Optional[QRectF] = None, kind: str = "auto") -> bool:
          ...
      def render_to_image(self, data: bytes, kind: str = "auto", max_px: int = 1200) -> Optional[QImage]:
          ...
      def render_to_bytes(self, data: bytes, kind: str = "auto", format: str = "PNG", max_px: int = 1200) -> Optional[bytes]:
          ...
      def get_dimensions(self, data: bytes, kind: str = "auto") -> Optional[Tuple[int, int]]:
          ...
  ```

### 4.2 模块级便捷接口
```python
def is_wmf(data: bytes) -> bool: ...
def is_emf(data: bytes) -> bool: ...
def render_metafile_to_image(data: bytes, kind: str = "auto", max_px: int = 1200) -> Optional[QImage]: ...
def render_metafile_to_bytes(data: bytes, kind: str = "auto", format: str = "PNG", max_px: int = 1200) -> Optional[bytes]: ...
def play_metafile(data: bytes, painter: QPainter, target_rect: Optional[QRectF] = None, kind: str = "auto") -> bool: ...
```

---

## 5. Verification Plan
- 单元测试：`tests/test_metafile_player.py`
  - 测试 WMF 头部（Placeable 与非 Placeable）解析。
  - 测试 EMF 头部解析与 Stock Objects 查找。
  - 测试 WMF 矩形、椭圆、多边形、文本记录回放。
  - 测试 EMF 路径、多边形 (EMR_POLYGON16 / EMR_POLYLINE16)、贝塞尔曲线回放。
  - 测试 DIB 内存位图解码 (1bpp, 8bpp, 24bpp, 32bpp)。
  - 测试边界异常数据（空字节、畸形数据、除零防崩）。
  - 执行命令：
    `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_metafile_player.py -v`
