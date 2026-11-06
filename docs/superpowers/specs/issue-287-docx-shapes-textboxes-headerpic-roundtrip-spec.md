# Specification: Issue #287 — 保护 DOCX 图形、文本框与页眉图片的往返保存

## 1. Background & Problem Statement
审计发现 DOCX 往返保存中，`libreoffice__nested-runs.docx`、`libreoffice__tdf113183.docx`、`libreoffice__textframe-borders.docx` 与 `poi__60316.docx` 等样本的绘图、VML 形状或文本框特征发生下降或丢失；同时需核验 `poi__headerPic.docx` 页眉图片及相关媒体部件和关系在往返中的完整性。

原版 `.vibeoffice/public/quire/js/preserve-drawing.js` 与 `preserve.js` 采用未编辑绘图与形状结构无损保留策略（unmodified raw XML preservation），确保 DrawingML、VML 形状、绘图文本框、页眉页脚部件及其媒体关系文件在往返保存中无损保留。

### Acceptance Criteria
1. **DrawingML 与 VML 形状保留**:
   - 完整保留 `wps:wsp`、`wpg:wgp` 等 DrawingML 形状与组合图形，禁止由于 XML 命名空间未注册导致的 `ns4:wsp` 前缀退化与审计特征下降。
   - 完整保留 `<w:pict>` 内的 VML 形状（`shape`, `rect`, `roundrect`, `oval`, `line`, `polyline`, `group`, `image`, `arc`, `curve`）与文本框，并在序列化时确保 `<w:pict>` 正确封装在 `<w:r>` 运行级容器内。
2. **文本框内容与文本模型一致性**:
   - `DrawingObject` 支持 `plain_text()` 动态提取 `raw_xml` 中的 `<w:txbxContent>` 文本，供 `ptext(p)` 及渲染/搜索直接使用。
   - 避免在读取器中向段落 runs 追加独立重复的 `TextItem`，杜绝保存后出现重复文本的问题。
3. **页眉页脚与媒体关系完整性**:
   - 保持 `poi__headerPic.docx` 等文档中页眉页脚图片（`w:drawing` / `pic:pic`）及对应关系部件（`word/_rels/headerX.xml.rels`）与媒体文件（`word/media/imageX.jpeg`）的引用完整性。
   - 在增量保存重写时，优先保留 `source_pkg` 中现存的页眉/页脚关系 ID 及对应目标文件名，防止由于重命名（如 `header2.xml` 变 `header1.xml`）导致已有的关系文件（如 `header2.xml.rels`）脱钩失效。
4. **无损保存安全提示**:
   - 当遇到损坏或无法无损保存的复杂绘图部件时，记入 `doc.losses` 并在保存时向用户展示确认对话框，用户取消时安全中止保存。
5. **回归与往返测试**:
   - 编写针对 `poi__headerPic.docx`、`libreoffice__textframe-borders.docx`、`libreoffice__nested-runs.docx`、`poi__60316.docx` 与 `libreoffice__tdf113183.docx` 的往返保留测试，确保特征无损（0 loss）、关系完好、普通文档不回归。

---

## 2. Technical Architecture & Design

### 2.1 Drawing Model Extensions (`drawing.py`)
1. **`DrawingObject`**:
   - 增加 `plain_text(self) -> str` 方法：当 `raw_xml` 包含 `txbxContent` 时，从 XML 树中动态解析提取所有的 `<w:t>` 文本。
   - 在 `ptext(p)` 时被自动调用，保证文档模型中能够检索并度量文本框文字，同时不需要在 `p.runs` 中注入独立的额外 `TextItem`。
2. **`PictureItem`**:
   - 构造参数及属性保持 `raw_xml: str | None = None`，用于暂存 DrawingML / AlternateContent / VML pict 的完整原始 XML 片段。

### 2.2 Reader Enhancements (`docx_reader.py`)
1. **Namespaces Registration**:
   - 注册 `wps` (`http://schemas.microsoft.com/office/word/2010/wordprocessingShape`)、`wpg` (`http://schemas.microsoft.com/office/word/2010/wordprocessingGroup`)、`mc` (`http://schemas.openxmlformats.org/markup-compatibility/2006`)、`v` (`urn:schemas-microsoft-com:vml`)、`o` (`urn:schemas-microsoft-com:office:office`)、`w10` (`urn:schemas-microsoft-com:office:word`)、`w14` (`http://schemas.microsoft.com/office/word/2010/wordml`)、`w15` (`http://schemas.microsoft.com/office/word/2012/wordml`) 等标准命名空间。
2. **`_parse_vml_pict`**:
   - 支持全量 VML 形状标签：`("shape", "rect", "roundrect", "oval", "line", "polyline", "group", "image", "arc", "curve")`。
   - 保存整个 `<w:pict>` 的原始 XML 到 `PictureItem.raw_xml`。
   - 若 `elem` 中未匹配到具体子 shape（例如仅有 shapetype 或自定义 VML），仍然创建兜底 `PictureItem(width=0, height=0, raw_xml=raw)`，确保 `<w:pict>` 结构不丢失。
3. **`_parse_drawing`**:
   - 移除向 `runs` 追加冗余 `TextItem` 的逻辑，统一由 `PictureItem.plain_text()` 提供文本接口，避免在保存时生成重复文本。

### 2.3 Writer Enhancements (`docx_writer.py`)
1. **Namespaces Registration**:
   - 在模块顶层全局注册 `wps`, `wpg`, `mc`, `v`, `o`, `w10`, `w14`, `w15` 等命名空间前缀，杜绝 ElementTree 序列化生成 `ns4:wsp`、`ns1:AlternateContent` 等非标准前缀。
2. **`_serialize_paragraph`**:
   - 当 `item` 为带有 `raw_xml` 的 `PictureItem` 时：
     - 若 `elem.tag` 为 `AlternateContent`、`drawing` 或 `pict`，确保使用 `<w:r>` 容器包裹后追加到 `p_elem`，符合 ECMA-376 规范。
3. **Header / Footer 关系映射与文件名保持**:
   - 在 `_build_document_and_rels` 中，检查 `self.source_pkg` 是否存在与 `old_id` 对应的现有关系。
   - 若存在现有关系，则直接复用其 `target`（如 `header2.xml`）与 `id`（如 `rId10`），避免顺序重命名打乱 `word/_rels/` 中已有关系文件的绑定。
   - 新增的页眉页脚使用独立的 `hdr_idx` 与 `ftr_idx` 计数器分配目标名称。

---

## 3. Test & Verification Plan
1. **往返特征审计测试 (`test_docx_shapes_textboxes_roundtrip.py`)**:
   - 对 `tests/docs/word/docx/poi__headerPic.docx`：验证页眉图片、DrawingML、图片关系（`rId1` -> `media/image1.jpeg`）无损保留。
   - 对 `tests/docs/word/docx/libreoffice__textframe-borders.docx`：验证 VML `<w:pict>` 与 `<v:rect><v:textbox>` 往返 1 -> 1 保留，且无损失。
   - 对 `tests/docs/word/docx/libreoffice__nested-runs.docx`：验证 `AlternateContent` 与 `wps:wsp` 往返 1 -> 1 保留，文本框无重复文本。
   - 对 `tests/docs/word/docx/poi__60316.docx`：验证 5 个 `wps:wsp` 全部保留，关系文件对应无漂移。
   - 对 `tests/docs/word/docx/libreoffice__tdf113183.docx`：验证 2 个 `wps:wsp` 全部保留。
2. **全量回归核验**:
   - 运行 `pytest tests/unit/writer/` 确保全部 167+ 项测试通过。
   - 运行 `pytest tests/gui/test_phase7_docx_render.py` 确保渲染与文本提取通过。
