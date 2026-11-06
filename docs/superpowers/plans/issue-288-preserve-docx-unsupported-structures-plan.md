# Implementation Plan: Issue #288 - 保留 DOCX 页面框架、公式和背景等未支持结构

## Overview
扩展 `ParagraphProperties`、`DocxReader`、`DocxWriter` 与 `omml.py`，实现 `framePr` 框架属性、Strict OpenXML 公式/图片命名空间标准化以及文档级 `background` 背景标签的完整无损往返保存。

---

## Tasks

### Task 1: 扩展段落属性模型支持 `frame_pr`
- **Files**: `src/atboffice/modules/writer/models/properties.py`
- **Actions**:
  - 在 `ParagraphProperties` 数据类中添加 `frame_pr: dict[str, str] | None = None`。

### Task 2: 增强 `DocxReader` 解析 `framePr`、`background` 与 Strict 命名空间
- **Files**: `src/atboffice/modules/writer/io/docx_reader.py`
- **Actions**:
  - 在 `_parse_p_pr` 中处理 `tag == "framePr"`，将其属性字典存入 `p_pr.frame_pr`。
  - 在 `_parse_body` 中检查 `root` 是否有 `<w:background>`，若有存入 `self.doc.keep["background"]`。
  - 提供 `normalize_strict_namespaces` 辅助函数，在保存 `raw_xml` 时对 Strict OpenXML 命名空间转换为 Transitional 规范。

### Task 3: 增强 `DocxWriter` 与 `omml.py` 序列化写回
- **Files**: `src/atboffice/modules/writer/io/docx_writer.py`, `src/atboffice/modules/writer/models/omml.py`
- **Actions**:
  - 在 `DocxWriter._populate_p_pr` 中生成 `<w:framePr>` 元素（自动受 `order.py` 的 schema 排序约束）。
  - 在 `DocxWriter._build_document_and_rels` 中，若存在 `doc.keep["background"]`，在 `<w:body>` 前插入 `<w:background>`。
  - 在 `PictureItem` 序列化与 `serialize_omml` 中，确保对 Strict 命名空间进行标准化处理。

### Task 4: 编写 TDD 专项回归测试
- **Files**: `tests/unit/writer/test_docx_unsupported_structures_roundtrip.py`
- **Actions**:
  - 针对 `framePr`（空标签及带丰富属性标签）测试往返保持。
  - 针对 Strict OpenXML（公式与图片）测试往返保持并断言 `m:oMath`、`pic:pic` 前缀。
  - 针对 `w:background` 测试往返保持。
  - 针对真实样本（`fdo55381.docx`, `strict.docx`, `tdf153255.docx`）进行特征无损核验。

### Task 5: 全量验证与 150 文件严格审计
- **Actions**:
  - 运行 `pytest tests/unit/writer/test_docx_unsupported_structures_roundtrip.py`。
  - 运行 `python scripts/run_corpus_audit.py`，确认 150 个文档无一出现新增或未解决 loss。
  - 运行 `pytest tests/` 确保零回归。
