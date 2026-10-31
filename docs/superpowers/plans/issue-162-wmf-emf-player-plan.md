# Implementation Plan: Issue #162 - 纯 Python 版 WMF / EMF 二进制矢量图元解析与 QPainter 播放器

## Tasks Breakdown

### Task 1: TDD Test Scaffolding
- **Files**: `tests/test_metafile_player.py`
- **Actions**:
  - 编写合成 WMF（带 Aldus Placeable Header 的矩形与多边形）二进制数据构建器。
  - 编写合成 EMF（标准 EMR_HEADER、EMR_RECTANGLE、EMR_POLYGON16、EMR_EOF）二进制数据构建器。
  - 编写单元测试用例：
    - `test_format_detection`: 测试 `is_wmf`, `is_emf` 对不同 magic 签名的识别。
    - `test_wmf_rendering`: 测试 WMF 矩形、椭圆、多边形绘制生成 QImage，检查像素非空。
    - `test_emf_rendering`: 测试 EMF 几何与路径绘制生成 QImage，检查像素非空。
    - `test_dib_decoding`: 测试 24bpp / 32bpp / 8bpp 位图解析。
    - `test_invalid_and_corrupt_data`: 测试空数据、畸形截断数据安全降级返回 None / False。
- **Expected Output**: 运行 `pytest tests/test_metafile_player.py` 初始失败（`ModuleNotFoundError: No module named 'atboffice.vfs.metafile_player'`）。

### Task 2: DIB 解码器与 GDI DC 状态机
- **Files**: `src/atboffice/vfs/metafile_player.py`
- **Actions**:
  - 实现 `_DCState`：管理当前 Pen、Brush、Font、TextColor、BkColor、BkMode、TextAlign、PolyFillMode、Window/Viewport 原点与范围、XForm 变换矩阵、剪裁区域等。
  - 实现状态栈压入/弹出 (`save_dc`, `restore_dc`)。
  - 实现 `_decode_dib_to_image(data, offset, bits_offset, usage, end)`：解析 BITMAPINFOHEADER / BITMAPCOREHEADER，解码行跨度 (stride) 与 1/4/8/16/24/32 bpp 像素至 `QImage`。
  - 实现光栅操作 ROP 处理（AND 掩码 + XOR 异或混合透明度）。

### Task 3: WMF 二进制解析器与 QPainter 回放
- **Files**: `src/atboffice/vfs/metafile_player.py`
- **Actions**:
  - 解析 Aldus Placeable Header (`0x9AC6CDD7`) 及标准 WMF 头。
  - 无 Placeable 头时预扫描 `SETWINDOWEXT`/`SETWINDOWORG` 获取边界。
  - 循环解析标准 16 位 WMF 记录：
    - 图形：`POLYGON`, `POLYLINE`, `POLYPOLYGON`, `RECTANGLE`, `ROUNDRECT`, `ELLIPSE`, `ARC`, `PIE`, `CHORD`, `LINETO`, `MOVETO`。
    - 对象：`CREATEPENINDIRECT`, `CREATEBRUSHINDIRECT`, `CREATEFONTINDIRECT`, `SELECTOBJECT`, `DELETEOBJECT`。
    - 文本：`TEXTOUT`, `EXTTEXTOUT`，支持字符集编码映射 (`shift_jis`, `gbk`, `big5`, `windows-1252` 等)。
    - 位图：`STRETCHDIB`, `DIBBITBLT`, `DIBSTRETCHBLT`, `PATBLT`。
  - 坐标映射至目标画布 / QPainter。

### Task 4: EMF 二进制解析器与 QPainter 回放
- **Files**: `src/atboffice/vfs/metafile_player.py`
- **Actions**:
  - 校验 EMF 签名 `0x464D4520` 与记录类型 1。
  - 解析设备物理尺寸并计算毫米/像素换算因子。
  - 支持 Stock Objects 静态查表 (WHITE_BRUSH, BLACK_PEN, DEFAULT_GUI_FONT 等)。
  - 解析 32 位与 16 位几何记录：`EMR_POLYGON`, `EMR_POLYGON16`, `EMR_POLYLINE`, `EMR_POLYLINE16`, `EMR_POLYBEZIER`, `EMR_POLYBEZIER16`。
  - 解析路径系统：`EMR_BEGINPATH`, `EMR_ENDPATH`, `EMR_STROKEANDFILLPATH`, `EMR_FILLPATH`, `EMR_STROKEPATH`。
  - 解析扩展对象：`EMR_EXTCREATEPEN`, `EMR_EXTCREATEFONTINDIRECTW`, `EMR_CREATEDIBPATTERNBRUSHPT`。
  - 解析文本与位图：`EMR_EXTTEXTOUTW`, `EMR_EXTTEXTOUTA`, `EMR_STRETCHDIBITS`。

### Task 5: 公共接口与导出
- **Files**:
  - `src/atboffice/vfs/metafile_player.py`
  - `src/atboffice/vfs/__init__.py`
- **Actions**:
  - 实现 `MetafilePlayer` 类及 `render_to_image`, `render_to_bytes`, `play`, `get_dimensions`。
  - 实现顶层便捷函数 `render_metafile_to_image`, `render_metafile_to_bytes`, `play_metafile`, `is_wmf`, `is_emf`。
  - 更新 `src/atboffice/vfs/__init__.py`，暴露新模块与符号。

### Task 6: 验证与全量回归测试
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_metafile_player.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/`
- **Actions**:
  - 确保单元测试 100% 通过。
  - 确保全仓已有测试无任何回归。
