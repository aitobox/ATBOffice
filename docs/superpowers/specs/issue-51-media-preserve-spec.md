# Spec: Issue #51 - [Lectern] 多媒体视频音频占位海报与播放属性无损保留

## 1. 概述与目标 (Overview & Objectives)
在 ATBOffice Lectern (PowerPoint 2003 演示文稿模块) 中实现嵌入多媒体（MP4/WMV/AVI/MOV 视频与 MP3/WAV/WMA 音频）的高保真保留、画布呈现与播放属性管理。
- **高保真无损保留 (Lossless Binary Preservation)**：打开含音视频的 PPTX 文件并保存时，100% 字节级保留原始音视频二进制流文件、链接关系及播放触发时序参数，保证未修改部件哈希一致，Office 打开零报错。
- **海报帧与占位展示 (Poster Frame & Canvas Representation)**：在 PySide6 画布视口上高保真渲染海报缩略图，对于音频呈现经典扬声器图标，并提供交互式半透明播放徽标与播放条占位。
- **播放属性与时序定义 (Playback Properties & Timing)**：定义 `PlaybackSettings`（自动播放、循环播放、音量、停止后隐藏、跨幻灯片播放等），并在 PPTX PresentationML 中正确序列化 `p14:media`、`p:videoFile`/`p:audioFile` 及 `p:timing` / `p:cMediaNode`。

---

## 2. 架构设计与数据模型 (Architecture & Data Models)

### 2.1 `src/atboffice/modules/presentation/models/media_item.py`
创建专用多媒体模型模块：
```python
@dataclass
class PlaybackSettings:
    auto_play: bool = False
    loop: bool = False
    volume: float = 0.8  # 0.0 ~ 1.0 (PresentationML 0 ~ 100000)
    hide_while_not_playing: bool = False
    rewind: bool = True
    play_across_slides: bool = False

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PlaybackSettings: ...

@dataclass
class MediaItem:
    media_type: str  # "video" | "audio"
    media_path: str  # e.g. "ppt/media/media1.mp4"
    content_type: str = "video/mp4"
    media_bytes: bytes | None = None
    poster_path: str | None = None  # e.g. "ppt/media/image1.png"
    poster_bytes: bytes | None = None
    playback: PlaybackSettings = field(default_factory=PlaybackSettings)
    original_element: str = "videoFile"  # "videoFile", "audioFile", "p14:media"

    @property
    def is_video(self) -> bool: return self.media_type == "video"
    @property
    def is_audio(self) -> bool: return self.media_type == "audio"
    @property
    def extension(self) -> str: ...
    @property
    def file_name(self) -> str: ...
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MediaItem | None: ...
```

### 2.2 `Shape` 模型集成 (`src/atboffice/modules/presentation/models/shape.py`)
在 `Shape` 类中增加：
- `media_item: MediaItem | None = None`
- 在 `to_dict()` 与 `from_dict()` 中支持 `media_item` 序列化与反序列化，保持完全向后兼容。

---

## 3. PPTX 读写管道无损保留 (PresentationML IO)

### 3.1 `pptx_reader.py` 解析流
1. 识别多媒体图元：
   - 检查 `<p:pic>` 内 `<p:nvPicPr>` 中的 `<p:nvPr>`（含 `<p:videoFile r:link="...">` 或 `<p:audioFile r:link="...">`）。
   - 检查 `<p:cNvPr>` 下 `<p:extLst>` 中 URI `{DAA4B390-3183-40C9-BE18-7BFA0C31F651}` 的 `<p14:media r:embed="...">`。
2. 提取关系与二进制：
   - 根据 `r:link` 或 `r:embed` 从 `slideX.xml.rels` 解析媒体目标（如 `../media/media1.mp4`），从 OPC 包中读取原始二进制字节流，保存在 `media_map` 与 `MediaItem.media_bytes` 中。
   - 解析 `<p:blipFill>/<a:blip r:embed="...">` 海报帧关系，读取海报图片字节流保存在 `MediaItem.poster_bytes`。
3. 解析播放属性与时序：
   - 从 `<p:timing>` 中检索对应 `spid` 的 `<p:cMediaNode>`，读取音量 `vol`、`showWhenStopped`、循环等属性构建 `PlaybackSettings`。
4. 构造 `Shape(type="image", media_item=media_item, media=poster_path)` 并附加到当前幻灯片。

### 3.2 `pptx_writer.py` 与 `writer_shapes.py` 序列化流
1. 写入媒体 Part：
   - 将原始音视频二进制流原封不动写入 `ppt/media/mediaX.{ext}`，禁止重编码与有损压缩。
   - 在 `[Content_Types].xml` 注册对应的 MIME 类型（`video/mp4`, `audio/mpeg`, `audio/wav`, `video/x-ms-wmv`, `video/quicktime`, etc.）。
2. 构建关系 (`slideX.xml.rels`)：
   - 海报帧关系：`http://schemas.openxmlformats.org/officeDocument/2006/relationships/image` -> `../media/imageY.{ext}`
   - 媒体关联关系：
     - `http://schemas.microsoft.com/office/2007/relationships/media` -> `../media/mediaX.{ext}`
     - 视频关系：`http://schemas.openxmlformats.org/officeDocument/2006/relationships/video` -> `../media/mediaX.{ext}`
     - 音频关系：`http://schemas.openxmlformats.org/officeDocument/2006/relationships/audio` -> `../media/mediaX.{ext}`
3. 生成 PresentationML 图元 XML (`writer_shapes.py`):
   - 生成符合 ECMA-376 严格架构顺序的 `<p:pic>`，包含 `<p14:media>` 扩展与 `<p:videoFile>` / `<p:audioFile>` 标签。
4. 写入 `<p:timing>` 时序节点：
   - 在幻灯片 XML 中追加包含 `<p:cMediaNode>` 的时序结构，与图元 `spid` 关联。

---

## 4. 画布视口呈现与交互 (Canvas UI/UX)

### 4.1 `ShapeGraphicsItem` 画布绘制 (`shape_item.py`)
1. **海报帧绘制**：
   - 如果图元具备 `media_item` 或图片，优先将海报帧以高质量平滑缩放绘制于图元外框内。
   - 若海报帧缺失或为音频，绘制暗色投影背景与扬声器/胶卷几何图形。
2. **播放徽标与控制条占位**：
   - 在图元中央绘制半透明播放圆形徽标（`▶`），鼠标悬停提供高亮微动。
   - 在图元底部绘制经典 PowerPoint 2003 风格播放控制栏：包含播放/暂停按钮、进度条、时间指示（如 `00:00 / 01:23`）与音量图标。
3. **i18n 国际化**：
   - 所有提示文字（如“播放多媒体”、“暂停”、“视频预览”、“音频预览”）使用 `safe_tr()` 包装，支持地道中英文切换。

---

## 5. 边界情况与错误防御 (Edge Cases & Resilience)
1. **缺失媒体文件或损坏包**：若关系引用丢失，提供安全占位图标，不抛出未捕获异常。
2. **无海报的纯音频文件**：自动退化为经典扬声器图标与控制条。
3. **大尺寸视频文件**：流式读取/保存，避免内存溢出。
4. **往返一致性 (Roundtrip)**：读取 PPTX -> 写入 PPTX，确保视频二进制流 SHA256 哈希 100% 保持一致。
