# Specification: Issue #286 — 保护 DOCX 内容控件与修订记录的往返保存

## 1. Background & Problem Statement
往返审计发现 `poi__60316.docx` 的内容控件 `<w:sdt>` 在通过 ATBOffice 保存后由 27 个降低到 0 个，`tdf125881.docx` 的插入修订记录 `<w:ins>` 由 2 个降低到 0 个（伴随 `<w:del>` 由 1 个降为 0 个）。
原版 `.vibeoffice/public/quire/js/preserve.js` 采用未编辑内容保留策略（unmodified/opaque preservation strategy），确保正文、页眉页脚、文本框中的结构化内容控件（SDT）、嵌套控件、数据绑定（dataBinding）、修订记录（Track Changes revisions）以及相关关系（customXml/glossaryDocument 等）在往返保存中无损保留。

### Acceptance Criteria
1. **内容控件保留**: 核实并保留正文、页眉页脚、绘图文本框中的内容控件（block-level SDT、inline SDT、table-row/cell SDT）、嵌套内容控件与数据绑定（dataBinding）。
2. **修订记录保留**: 核实并保留段落标记上的修订记录（`<w:pPr><w:rPr><w:ins>` / `<w:del>`）以及运行级的修订记录（`<w:ins>` / `<w:del>`），包括 author、date、id 等元数据。
3. **关系保留**: 保持 `word/_rels/document.xml.rels` 中涉及 `customXml`、`glossaryDocument`、`settings`、`fontTable`、`theme` 等相关部件的关联关系，不被破坏或意外移除。
4. **无损保存安全提示**: 当文档存在无法无损保存的内容时，在保存时向用户展示兼容性/损耗确认对话框，用户取消时安全终止保存，不静默破坏原有文档或覆盖丢失。
5. **回归与往返测试**: 增加包含 `poi__60316.docx` 与 `libreoffice__tdf125881.docx` 的往返、编辑及重开测试，验证语义、关系及关键节点完整性。

---

## 2. Technical Architecture & Design

### 2.1 Model Extensions
1. **`ParagraphProperties` / `TableProperties` / `Row` / `Cell`**:
   - `sdts: list[dict[str, Any]] = field(default_factory=list)`
   - `sdte: list[str] = field(default_factory=list)`
2. **`document.py`**:
   - `SdtStartItem(RunItem)`: inline SDT start item with `control` dictionary (`key`, `shell_xml`, metadata).
   - `SdtEndItem(RunItem)`: inline SDT end item with `key`.
   - `Document`: add `losses: list[dict[str, Any]] = field(default_factory=list)` and `keep: dict[str, Any] = field(default_factory=dict)`.
3. **`drawing.py` (`DrawingObject` / `PictureItem`)**:
   - `raw_xml: str | None = None` (retains raw XML of `<w:drawing>` or `<mc:AlternateContent>` when present).

### 2.2 Reader (`docx_reader.py`)
1. **Block SDTs (`_collect_blocks`)**:
   - When encountering `<w:sdt>` in body/header/footer:
     - Capture `control = self._parse_sdt_control(child)`.
     - Track starting block offset `n0 = len(blocks)`.
     - Recursively parse child blocks in `<w:sdtContent>`.
     - If no blocks were produced, append an empty `Paragraph()`.
     - Attach `control` to `blocks[n0].p_pr.sdts.insert(0, control)`.
     - Attach `control["key"]` to `blocks[-1].p_pr.sdte.append(control["key"])`.
2. **Inline SDTs (`_parse_inline_element`)**:
   - When encountering `<w:sdt>`:
     - Capture `control = self._parse_sdt_control(elem)`.
     - Append `SdtStartItem(control=control)`.
     - Parse inline children of `<w:sdtContent>`.
     - Append `SdtEndItem(key=control["key"])`.
3. **Table Row / Cell SDTs**:
   - In `_collect_table_rows` and cell parsing, support `<w:sdt>` wrapping rows or cells using `sdts`/`sdte` markers.
4. **Revisions (`ins` / `del`)**:
   - In `_parse_paragraph`: check `<w:pPr><w:rPr>` for `<w:ins>` and `<w:del>`, populating `p.mark_ins` and `p.mark_del` with `RevisionStamp`.
   - In `_parse_inline_element`: when parsing `<w:ins>` / `<w:del>`, extract `RevisionStamp` and propagate `r_pr.ins` / `r_pr.del_rev` to all child runs.
5. **Drawings with AlternateContent / Textboxes**:
   - When reading `<w:drawing>` or `<mc:AlternateContent>`, preserve the full original XML in `pic.raw_xml`.

### 2.3 Writer (`docx_writer.py`)
1. **Block SDT Serialization**:
   - When serializing story blocks (in body, headers, footers), use a stack-based algorithm:
     - For each control in `block.p_pr.sdts`, push a new `<w:sdt>` wrapper parsed from `control["shell_xml"]`.
     - Serialize the block into the current container's `<w:sdtContent>`.
     - For each key in `block.p_pr.sdte`, pop and append the completed `<w:sdt>` element to the parent container.
2. **Inline SDT & Revision Serialization**:
   - In `_serialize_paragraph`, handle `SdtStartItem` and `SdtEndItem`:
     - Wrap inline runs between `sdts` and `sdte` into `<w:sdt>` element's `<w:sdtContent>`.
   - Group consecutive runs by `(link, ins, del_rev)`:
     - Wrap runs with `ins` into `<w:ins w:id="..." w:author="..." w:date="..."><w:r>...<w:t>...</w:t></w:r></w:ins>`.
     - Wrap runs with `del_rev` into `<w:del w:id="..." w:author="..." w:date="..."><w:r>...<w:delText>...</w:delText></w:r></w:del>`.
   - In `_populate_p_pr`:
     - If `p.mark_ins` or `p.mark_del` or `p.r_pr` is present, create `<w:rPr>` with `<w:ins>` / `<w:del>` and formatting.
3. **Drawing Serialization**:
   - When serializing `PictureItem` with `raw_xml`:
     - Re-emit the preserved XML directly into `p_elem`.
4. **Relationship Preservation**:
   - In `_write_incremental`, carry over all untouched relationships from the source package's `word/_rels/document.xml.rels` (e.g. `customXml`, `glossaryDocument`, `settings`, etc.).

### 2.4 UI Compatibility Check (`quire_window.py`)
1. Before performing `do_save`, if `doc.losses` contains unresolvable losses, prompt the user with a warning dialog (`safe_tr("文件中有部分内容无法无损保存...\n是否继续保存？")`).
2. If the user clicks Cancel, return `False` immediately, aborting the save operation.

---

## 3. Test & Verification Plan
1. **Unit Test Suite**:
   - Create `tests/unit/writer/test_docx_sdt_revisions_roundtrip.py`.
   - Test roundtrip of `tests/docs/word/docx/poi__60316.docx`:
     - Verify SDT count in `word/document.xml` stays at 27.
     - Verify customXml relationships (rId1, rId2) remain in `word/_rels/document.xml.rels`.
   - Test roundtrip of `tests/docs/word/docx/libreoffice__tdf125881.docx`:
     - Verify `w:ins` and `w:del` elements in `word/document.xml` are preserved (2 ins, 1 del).
   - Test compatibility dialog on lossy conditions.
2. **Regression Testing**:
   - Run full `pytest tests/unit/writer/` to ensure 0 regressions.
