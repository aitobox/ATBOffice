# Implementation Plan: Issue #287 — 保护 DOCX 图形、文本框与页眉图片的往返保存

## 1. Overview
根据 specification 方案，分 4 个任务进行实现与测试：
1. **Task 1: 扩展 Drawing 模型支持 `plain_text()`**
   - 在 `src/atboffice/modules/writer/models/drawing.py` 中为 `DrawingObject` 增加 `plain_text()` 方法，动态解析 `raw_xml` 中的 `<w:txbxContent>` 文本。
2. **Task 2: 注册全局 XML 命名空间并完善 `docx_writer.py` 序列化与页眉/页脚关系映射**
   - 在 `docx_writer.py` 与 `docx_reader.py` 中注册 `wps`, `wpg`, `mc`, `v`, `o`, `w10`, `w14`, `w15` 等命名空间。
   - 在 `_serialize_paragraph` 中对 `AlternateContent`、`drawing`、`pict` 标签元素统一放入 `<w:r>` 运行级容器。
   - 在 `_build_document_and_rels` 中优先复用 `self.source_pkg` 的现有页眉页脚关系 ID 及目标文件名，保证现有 `.rels` 关系文件一致。
3. **Task 3: 完善 `docx_reader.py` 的 VML `<w:pict>` 与 DrawingML 解析**
   - 在 `_parse_vml_pict` 中支持全部标准 VML 形状标签，并将 `<w:pict>` 原始 XML 保存到 `PictureItem.raw_xml`。
   - 若未匹配具体 shape，生成兜底 `PictureItem(raw_xml=raw)` 保留 `<w:pict>`。
   - 移除 `_parse_drawing` 中向 runs 追加额外 `TextItem` 的冗余逻辑，由 `plain_text()` 统一响应文本查询。
4. **Task 4: 编写单元测试与全量回归验证**
   - 新建 `tests/unit/writer/test_docx_shapes_textboxes_roundtrip.py`，覆盖：
     - `libreoffice__textframe-borders.docx`: VML 形状与文本框往返保留（1 -> 1），无损失。
     - `libreoffice__nested-runs.docx`: AlternateContent 与 wps:wsp 往返保留，文本框无重复。
     - `poi__60316.docx`: 5 个 wps:wsp 全部保留，关系文件对应无漂移。
     - `libreoffice__tdf113183.docx`: 2 个 wps:wsp 全部保留。
     - `poi__headerPic.docx`: 页眉图片及关系（`rId1` -> `media/image1.jpeg`）无损保留。
   - 运行全部测试套件确保 0 regression。

---

## 2. Detailed Task Breakdown

### Task 1: `drawing.py`
- Modify `DrawingObject` in `src/atboffice/modules/writer/models/drawing.py`.
- Add `plain_text(self) -> str`.
- Test: Verify `ptext(p)` returns textbox content when a paragraph contains `PictureItem` with `raw_xml`.

### Task 2: `docx_writer.py`
- Register `wps`, `wpg`, `mc`, `v`, `o`, `w10`, `w14`, `w15`.
- Update `_serialize_paragraph` to wrap `<w:pict>` inside `<w:r>`.
- Update `_build_document_and_rels` to preserve existing header/footer IDs and targets from `self.source_pkg`.

### Task 3: `docx_reader.py`
- Register namespaces.
- Update `_parse_vml_pict` to store `raw_xml` on `PictureItem` and handle all VML shape types.
- Clean up redundant `TextItem` append in `_parse_drawing`.

### Task 4: Tests & Regression
- Create `tests/unit/writer/test_docx_shapes_textboxes_roundtrip.py`.
- Run `pytest tests/unit/writer/` and `pytest tests/gui/test_phase7_docx_render.py`.
- Run 25-file audit to confirm zero loss on all target files.
