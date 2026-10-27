# Plan: Issue #51 - [Lectern] 多媒体视频音频占位海报与播放属性无损保留

## Task 1: 实现多媒体数据模型 `media_item.py`
- **目标**: 实现 `PlaybackSettings` 和 `MediaItem` 数据类，支持音视频属性、海报路径与字节流管理、MIME 类型推导以及完整的字典序列化。
- **文件**: `src/atboffice/modules/presentation/models/media_item.py`
- **验证**: 编写单测验证模型序列化与反序列化。

## Task 2: 扩展 `Shape` 模型集成 `MediaItem`
- **目标**: 在 `Shape` 模型中增加 `media_item: MediaItem | None = None`，并在 `to_dict` / `from_dict` 中妥善序列化与还原，确保与现有图形模型兼容。
- **文件**: `src/atboffice/modules/presentation/models/shape.py`
- **验证**: 运行已有的 shape 与 model 单元测试。

## Task 3: 实现 PresentationML 多媒体读取解析器 (`pptx_reader.py`)
- **目标**:
  - 解析 `<p:pic>` / `<p:sp>` 内的 `<p:videoFile>`, `<p:audioFile>`, `<p:quickTimeFile>` 及 `<p14:media>`。
  - 提取多媒体关系目标及海报帧关系目标。
  - 读取 OPC Package 中的媒体二进制流与海报图片，存入 `MediaItem` 与 `pres.props["_media_map"]`。
  - 解析 `<p:timing>` 中 `<p:cMediaNode>` 的播放时序参数（音量、停止后隐藏、循环）。
- **文件**: `src/atboffice/modules/presentation/io/pptx_reader.py`
- **验证**: 单元测试验证读取包含音视频的 PPTX 结构并解析出 `MediaItem`。

## Task 4: 实现 PresentationML 多媒体无损序列化 (`pptx_writer.py` 与 `writer_shapes.py`)
- **目标**:
  - 将音视频原始二进制流 100% 字节级保存到 `ppt/media/` 部件中，并在 `[Content_Types].xml` 注册正确 MIME 类型。
  - 在 `slideX.xml.rels` 中写入 `REL_IMAGE` 海报关系及 `video`/`audio`/`media` 关系。
  - 在 `writer_shapes.py` 中生成符合 ECMA-376 的 `<p:pic>` 结构，包含 `<p14:media>` 扩展与 `<p:videoFile>`/`<p:audioFile>` 标签。
  - 在幻灯片 XML 中追加 `<p:timing>` / `<p:cMediaNode>` 播放属性节点。
- **文件**:
  - `src/atboffice/modules/presentation/io/pptx_writer.py`
  - `src/atboffice/modules/presentation/io/writer_shapes.py`
  - `src/atboffice/modules/presentation/io/writer_slide.py`
- **验证**: 单元测试验证导出的 PPTX 包含完整的媒体 part、rels 和 PresentationML pic 节点。

## Task 5: 画布海报与播放控件预览渲染 (`shape_item.py`)
- **目标**:
  - 在 `ShapeGraphicsItem` 中绘制图片/海报帧内容。
  - 对于多媒体对象，居中绘制半透明播放圆形按钮（`▶`），在底部绘制经典播放控制条（播放/暂停按钮、时间轴、音量图标、时间文本）。
  - 对无海报音频对象绘制经典扬声器图标占位。
  - 封装完整的国际化文本与安全工具提示。
- **文件**: `src/atboffice/modules/presentation/views/shape_item.py`
- **验证**: GUI 渲染测试与无图形降级单测。

## Task 6: 编写多媒体无损往返回归测试套件 (`test_media_preserve.py`)
- **目标**:
  - 覆盖模型序列化测试。
  - 覆盖 PPTX 写入与读取往返测试，验证音视频二进制流哈希 100% 保持一致（无损保留）。
  - 覆盖播放参数保留测试（音量、自动播放、循环）。
  - 覆盖画布图元绘制与缺失媒体防御测试。
- **文件**: `tests/unit/presentation/test_media_preserve.py`
- **验证**: 运行 `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/presentation/test_media_preserve.py -v`。

## Task 7: 运行全量测试套件并保证 100% 通过
- **目标**: 运行 `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`，确认无任何回归。
