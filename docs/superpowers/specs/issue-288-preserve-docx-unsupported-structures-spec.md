# Specification: Issue #288 - 保留 DOCX 页面框架、公式和背景等未支持结构

## 1. Context & Objectives

在 ATBOffice 对 150 个文档样本（`tests/docs/expectations.json`）及 `tests/docs/word/docx` 的往返审计中，识别出 6 例文档出现 ECMA-376 特征损失：
1. `libreoffice__fdo55381.docx`（4 处）、`libreoffice__tdf105035_framePrB.docx`（2 处）、`libreoffice__tdf113182.docx`（1 处）、`openxml-sdk__bullet-complex.docx`（2 处）：`<w:framePr>` 段落页面框架属性在反序列化保存后丢失（4→0、2→0 等）。
2. `libreoffice__strict.docx`：ISO/IEC 29500 Strict OpenXML 命名空间（`http://purl.oclc.org/ooxml/...`）的公式（`<m:oMath>`）与图片（`<pic:pic>`）在重写为 Transitional 规范时使用了未注册的前缀（`ns10:oMath`, `ns5:pic`），导致特征提取器无法匹配标准前缀，且产生命名空间混淆。
3. `libreoffice__tdf153255.docx`：文档根级背景颜色 `<w:background>` 在解析时被忽略，保存时未重新写回 `<w:document>`。

本任务目标：
- 完善 DOCX 读写器与文档模型，对 `framePr`、Strict OpenXML 公式/图片、以及 `background` 提供无损往返保存能力；
- 保证原有语义、属性与结构在重开后完整保留；
- 编写专项回归测试，并运行 150 文件严格审计验证 0 loss。

---

## 2. Root Cause Analysis & Technical Design

### 2.1 Paragraph Frame Properties (`framePr`)
- **Root Cause**:
  - `ParagraphProperties`（`src/atboffice/modules/writer/models/properties.py`）未包含 `frame_pr` 字段。
  - `DocxReader._parse_p_pr` 遍历 `<w:pPr>` 子元素时忽略了 `tag == "framePr"`。
  - `DocxWriter._populate_p_pr` 在组装 `<w:pPr>` 时未写回 `<w:framePr>`。
- **Design**:
  - 在 `ParagraphProperties` 中添加字段：`frame_pr: dict[str, str] | None = None`。
  - 在 `DocxReader._parse_p_pr` 中，当 `tag == "framePr"` 时，捕获其所有属性字典 `child.attrib` 存入 `p_pr.frame_pr`。
  - 在 `DocxWriter._populate_p_pr` 中，若 `p_pr.frame_pr is not None`，生成 `<w:framePr>` 元素并正确赋属性。
  - 架构位置：`src/atboffice/vfs/order.py` 中的 `wordprocessingml_ppr` 已正确定义 `framePr` 的顺序（在 `pageBreakBefore` 之后、`widowControl` 之前），因此 `enforce_schema_order` 会自动将其排在合规位置。

### 2.2 Strict OpenXML Namespaces Normalization (Equations & Pictures)
- **Root Cause**:
  - ISO/IEC 29500 Strict 文档使用 `http://purl.oclc.org/ooxml/...` 命名空间。
  - ATBOffice 生成的 DOCX 为 ECMA-376 Transitional 文档。
  - 当读取 Strict 格式的图片或公式时，`PictureItem.raw_xml` 或 `OfficeMathItem.raw_xml` 包含了 Strict 命名空间 URI。
  - `DocxWriter` 的命名空间注册器（`ET.register_namespace`）只注册了 Transitional 命名空间 URI。
  - `xml.etree.ElementTree` 遇到未注册前缀的命名空间时，自动为其分配 `ns0`, `ns5`, `ns10` 等临时别名，破坏了 `<m:oMath>` 和 `<pic:pic>` 的前缀语义。
- **Design**:
  - 提供 Strict 到 Transitional 命名空间的标准转换映射 `STRICT_TO_TRANSITIONAL`：
    - `http://purl.oclc.org/ooxml/wordprocessingml/main` -> `http://schemas.openxmlformats.org/wordprocessingml/2006/main`
    - `http://purl.oclc.org/ooxml/officeDocument/relationships` -> `http://schemas.openxmlformats.org/officeDocument/2006/relationships`
    - `http://purl.oclc.org/ooxml/officeDocument/math` -> `http://schemas.openxmlformats.org/officeDocument/2006/math`
    - `http://purl.oclc.org/ooxml/drawingml/wordprocessingDrawing` -> `http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing`
    - `http://purl.oclc.org/ooxml/drawingml/main` -> `http://schemas.openxmlformats.org/drawingml/2006/main`
    - `http://purl.oclc.org/ooxml/drawingml/picture` -> `http://schemas.openxmlformats.org/drawingml/2006/picture`
    - `http://purl.oclc.org/ooxml/drawingml/chart` -> `http://schemas.openxmlformats.org/drawingml/2006/chart`
    - `http://purl.oclc.org/ooxml/drawingml/diagram` -> `http://schemas.openxmlformats.org/drawingml/2006/diagram`
  - 在 `DocxReader` 记录 `raw_xml` 时及在 `DocxWriter` / `serialize_omml` 恢复 `raw_xml` 时，自动进行命名空间标准化替换，确保所有嵌入 XML 与全局 Transitional 命名空间无缝统一。

### 2.3 Document Background (`w:background`)
- **Root Cause**:
  - `DocxReader._parse_body` 只定位 `<w:body>`，未读取其同级的前置元素 `<w:background>`。
  - `DocxWriter._build_document_and_rels` 创建根 `<w:document>` 后直接追加 `<w:body>`，遗漏了背景属性。
- **Design**:
  - 在 `DocxReader._parse_body` 中，检查 `root` 下是否存在 `<w:background>` 元素。若存在，保留在 `doc.keep["background"] = {"attrib": dict(bg_elem.attrib), "raw_xml": ET.tostring(bg_elem, encoding="unicode")}`。
  - 在 `DocxWriter._build_document_and_rels` 中，构建 `root = ET.Element(_w("document"))` 时，若 `self.doc.keep` 中存在 `background`，按 OOXML 顺序先插入 `<w:background>`，再追加 `<w:body>`。

---

## 3. Verification & Quality Gates

1. **Unit & Integration Tests**:
   - `tests/unit/writer/test_docx_unsupported_structures_roundtrip.py`:
     - 验证 `framePr` 单独及批量段落属性的读取与写回；
     - 验证 Strict OpenXML 中的公式与图片往返转换，断言前缀为 `m:` 与 `pic:`；
     - 验证 `background` 颜色、属性及 XML 结构的往返保存；
     - 验证包含各特征的真实样本文件无损往返。
2. **Corpus Audit**:
   - 对 150 个样本执行 `scripts/run_corpus_audit.py`，确认所有 6 个 Word loss 归零。
3. **Full Test Suite**:
   - 运行项目全量单元测试，保证 0 regression。
