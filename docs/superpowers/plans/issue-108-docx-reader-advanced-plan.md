# Implementation Plan: Issue #108 - [Phase 2] DOCX 读取器全量扩充 (编号列表、复杂表格跨行跨列与图形环绕)

## Overview
全面升级 `src/atboffice/modules/writer/io/docx_reader.py`，实现对齐原版 quire/js/docx-read.js (1,876 行) 的高级 DOCX 特性：多级编号列表、复杂表格跨行跨列与边距边框、DrawingML 矢量内联与浮动图片（带环绕模式与 Z-Order）、VML 兼容图片、脚注/尾注与书签索引。

---

## Proposed Tasks

### Task 1: 扩展模型定义 (Model Extensions)
- **Files**:
  - `src/atboffice/modules/writer/models/document.py`
  - `src/atboffice/modules/writer/models/properties.py`
- **Actions**:
  - 在 `document.py` 中添加 `NoteRefItem(RunItem)`，支持 `kind: str = "fn"` (或 `"en"`), `note_id: str = "0"`, `custom_mark: str = ""`.
  - 在 `properties.py` 中的 `CellProperties` 添加 `tc_mar: dict[str, float] = field(default_factory=dict)`。
  - 确认 `TableProperties.borders` 与 `TableProperties.cell_mar` 完整可用。

### Task 2: 编写独立测试套件 (TDD Red Phase)
- **Files**:
  - `tests/modules/writer/test_docx_reader_advanced.py`
- **Actions**:
  - 构建辅助函数 `create_test_docx(parts: dict[str, str | bytes]) -> bytes` 动态打包符合 OPC 规范的内存 DOCX。
  - 编写 5 组针对性测试用例：
    1. `test_numbering_advanced`: 测试抽象编号、多级 lvl、numFmt (decimal, bullet)、lvlText、startOverride 与段落 num 映射。
    2. `test_table_complex_spans_and_margins`: 测试 `gridSpan` 跨列、`vMerge` (restart/continue) 跨行、`tcMar` 单元格边距、`trHeight` 行高规则。
    3. `test_drawingml_inline_and_anchor`: 测试 `wp:inline` 与 `wp:anchor` 浮动图片，验证尺寸 EMU 转换、WrapMode (square, tight, behind)、浮动位置与旋转/裁剪。
    4. `test_vml_pict_backward_compat`: 测试 `w:pict` VML 图片解析。
    5. `test_footnotes_endnotes_bookmarks`: 测试脚注故事 `doc.fn`、尾注故事 `doc.en` 与书签字典 `doc.props["bookmarks"]`。
  - 运行测试并确认失败（红灯阶段）。

### Task 3: 扩充 DocxReader 核心解析引擎 (TDD Green Phase)
- **Files**:
  - `src/atboffice/modules/writer/io/docx_reader.py`
- **Actions**:
  - 实现 `_parse_numbering(self)`：
    - 读取 `word/numbering.xml`
    - 解析 `abstractNum`（所有 9 个 level，包括 `numFmt`, `lvlText`, `start`, `lvlJc`, `suff`, `pPr.ind`）
    - 解析 `num` 及其 `lvlOverride`
    - 保存至 `self.doc.numbering`
  - 增强 `_parse_table(self, tbl_elem)`：
    - 准确读取 `gridSpan`, `vMerge` (空 val 默认 "continue")
    - 读取 `tcMar` (top, bottom, left, right in twips -> pt)
    - 读取 `tblCellMar` (top, bottom, left, right in twips -> pt)
    - 读取 `trHeight` 与 `hRule`
    - 读取单元格及表格边框
  - 实现 `_parse_drawing(self, elem)` 与 `_parse_vml_pict(self, elem)`：
    - 在 `_parse_inline_element` 中支持 `w:drawing` 与 `w:pict`
    - 在 `_parse_paragraph` 中支持直接作为段落子节点的 `w:drawing` 与 `w:pict`
    - 转换 EMUs 至 points (`emu / 12700.0`)
    - 解析 `blip` 的 `embed`/`link` 关系 ID，转换为实际图片路径
    - 解析 `srcRect` 裁剪与 `xfrm` 旋转
    - 解析 `wp:anchor` 的 `PositionH`, `PositionV`, `WrapMode`, `WrapDist`, `z_index`, `behind`
    - 生成 `PictureItem` 附加至 runs
  - 实现 `_parse_footnotes(self)` 与 `_parse_endnotes(self)`：
    - 读取 `word/footnotes.xml` 与 `word/endnotes.xml`
    - 解析 footnote/endnote 块并挂载至 `self.doc.fn` 和 `self.doc.en`
    - 在 inline 元素中解析 `footnoteReference` 与 `endnoteReference` 并生成 `NoteRefItem`
  - 完善书签收集至 `self.doc.props["bookmarks"]`
  - 在 `DocxReader.read()` 中按序调用上述所有解析方法。

### Task 4: 运行独立测试并验证全部通过 (Green Phase)
- **Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/writer/test_docx_reader_advanced.py -v
  ```

### Task 5: 全量回归测试与代码质量验证
- **Command**:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/ -v
  PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/ -v
  ```
