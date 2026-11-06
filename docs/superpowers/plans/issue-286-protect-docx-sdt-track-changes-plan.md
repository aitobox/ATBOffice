# Implementation Plan: Issue #286 — 保护 DOCX 内容控件与修订记录的往返保存

## Proposed Changes

### 1. Model Definitions
- **`src/atboffice/modules/writer/models/properties.py`**:
  - Add `sdts: list[dict[str, Any]]` and `sdte: list[str]` to `ParagraphProperties`, `CellProperties`, and `TableProperties`.
- **`src/atboffice/modules/writer/models/document.py`**:
  - Add `SdtStartItem(RunItem)` and `SdtEndItem(RunItem)` data classes.
  - Add `losses: list[dict[str, Any]]` and `keep: dict[str, Any]` to `Document`.
  - Add `sdts: list[dict[str, Any]]` and `sdte: list[str]` to `Table` and `Row`.
- **`src/atboffice/modules/writer/models/drawing.py`**:
  - Add `raw_xml: str | None = None` to `DrawingObject` and `PictureItem`.

### 2. DOCX Reader Implementation
- **`src/atboffice/modules/writer/io/docx_reader.py`**:
  - Implement `_parse_sdt_control(sdt_elem)` extracting shell XML, `sdtPr`, `dataBinding`, `alias`, `tag`, etc.
  - In `_collect_blocks`: Parse `<w:sdt>` at block level, tracking start and end block offsets, assigning `sdts` to first block and `sdte` to last block.
  - In `_parse_inline_element`: Parse `<w:sdt>` at inline level, emitting `SdtStartItem` and `SdtEndItem`.
  - In `_collect_table_rows` and cell parsing: Handle `<w:sdt>` wrapping rows or cells.
  - In `_parse_paragraph`: Parse `<w:pPr><w:rPr>`, extracting `<w:ins>` and `<w:del>` into `p.mark_ins` and `p.mark_del`.
  - In `_parse_inline_element`: Handle `<w:ins>` and `<w:del>`, setting `r_pr.ins` and `r_pr.del_rev`.
  - In `_parse_drawing` and `_parse_inline_element` for `AlternateContent`/`drawing`: Retain raw XML string in `pic.raw_xml`.

### 3. DOCX Writer Implementation
- **`src/atboffice/modules/writer/io/docx_writer.py`**:
  - In `_build_document_and_rels` and `_build_hf_xml`: Implement stack-based block SDT wrapping so `<w:sdt>` elements are reconstructed with their original `<w:sdtPr>` and enclosing `<w:sdtContent>`.
  - In `_serialize_paragraph`:
    - Handle `p.mark_ins`, `p.mark_del`, and `p.r_pr` in `_populate_p_pr` creating `<w:rPr>`.
    - Handle inline `SdtStartItem` and `SdtEndItem`, wrapping runs into `<w:sdt>`.
    - Group consecutive runs by `ins` and `del_rev`, wrapping into `<w:ins>` and `<w:del>`.
    - Serialize `PictureItem` with `raw_xml`, appending preserved drawing XML.
  - In `_write_incremental`: Preserve untouched relationships from source package's `document.xml.rels` (`customXml`, `glossaryDocument`, `settings`, etc.).

### 4. UI Compatibility & Loss Prevention
- **`src/atboffice/ui/shell/quire_window.py`**:
  - In `do_save`, inspect `self.writer_view.canvas_view.doc.losses`.
  - If unresolvable loss items exist, prompt the user with a confirmation dialog.
  - If the user cancels, return `False` immediately, aborting the save and preventing destructive file overwrite.

### 5. Regression & Roundtrip Tests
- **`tests/unit/writer/test_docx_sdt_revisions_roundtrip.py`**:
  - Test `poi__60316.docx` roundtrip: exactly 27 SDTs preserved, customXml relationships intact.
  - Test `libreoffice__tdf125881.docx` roundtrip: 2 `ins` and 1 `del` preserved.
  - Test in-memory edit + save + reload of documents with SDT and revisions.
  - Test UI cancel on lossy document save.

---

## Execution Order
1. Write reproduction test file `tests/unit/writer/test_docx_sdt_revisions_roundtrip.py`.
2. Update models in `src/atboffice/modules/writer/models/`.
3. Update reader in `src/atboffice/modules/writer/io/docx_reader.py`.
4. Update writer in `src/atboffice/modules/writer/io/docx_writer.py`.
5. Update `quire_window.py` for save compatibility prompts.
6. Verify tests pass and run full writer test suite.
