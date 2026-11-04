# Implementation Plan: Issue #240 (TASK-706) - Fix XLSX/XLSM Default Save Loss

## Overview
Implement lossless roundtrip carry and preservation for Excel (.xlsx and .xlsm) workbooks in ATBOffice Ledger, ensuring macros (vbaProject.bin), comments, charts, protection, custom XML, and relationships survive default saves.

---

### Task 1: Fix OPC Content Types Conformance in `src/atboffice/vfs/opc.py`
- Modify `_build_content_types_xml`:
  - Ensure parts ending in `.rels` are excluded from `<Override>` elements.
- Verify that `[Content_Types].xml` produces strictly valid ECMA-376 XML.

---

### Task 2: Enhance Workbook and Sheet Models
- File: `src/atboffice/modules/spreadsheet/models/sheet_model.py`:
  - Add `dirty: bool = False`, `extra: dict[str, Any] = {}`, and `code_name: str | None = None` to `SheetDataModel`.
  - Set `self.dirty = True` in `set_cell`, `set_cell_value`, `set_cell_formula`, `clear_cell`, `add_merge`.
- File: `src/atboffice/modules/spreadsheet/models/workbook_model.py`:
  - Add `_source_package: Any = None` attribute and property to `WorkbookModel`.

---

### Task 3: Enhance XLSX Reader in `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- Capture `SourcePackage` from incoming bytes/stream/path.
- Attach `wb._source_package = source_pkg` and `wb.extra["source_package"] = source_pkg`.
- Extract `<workbookPr codeName="...">` into `wb.extra["code_name"]`.
- Extract `<fileVersion codeName="...">` into `wb.extra["file_version_code_name"]`.
- Detect macro enablement (`wb.extra["is_macro_enabled"] = True`).
- Extract `<workbookProtection ...>` and `<definedNames>`.
- For each sheet: assign `sheet.extra["ooxml_part"] = s_part` and extract `<sheetProtection>`, `<sheetPr codeName="...">`, `<autoFilter>`.

---

### Task 4: Implement Lossless XLSX/XLSM Writer in `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`
- Resolve `source_pkg` from `source_opc or getattr(workbook, "_source_package", None) or workbook.extra.get("source_package")`.
- Detect macro enablement: use `CT_WORKBOOK_MACRO` (`application/vnd.ms-excel.sheet.macroEnabled.main+xml`) if `.xlsm` or `vbaProject.bin` present.
- In `_serialize_workbook`:
  - Emit `codeName` in `<workbookPr>`.
  - Emit `<workbookProtection>` if present.
  - Emit `<definedNames>` if present.
- In `_serialize_workbook_rels`:
  - Preserve non-regenerated relationships from `source_pkg.get_relationships("xl/workbook.xml")` (`vbaProject`, `calcChain`, `customXml`, `externalLink`).
- In worksheet serialization:
  - If sheet has `ooxml_part` in `source_pkg`:
    - If unmodified: keep original XML bytes directly.
    - If modified: patch `<sheetData>` and `<dimension>` into original XML, preserving `<sheetPr>`, `<pageSetup>`, `<drawing>`, `<legacyDrawing>`, `<controls>`, `<sheetProtection>`, `<autoFilter>`.
  - In worksheet relationships (`xl/worksheets/_rels/sheet{i}.xml.rels`):
    - Preserve auxiliary relationships (`comments`, `vmlDrawing`, `printerSettings`, `ctrlProp`, `drawing`).

---

### Task 5: Verify GUI Shell in `src/atboffice/ui/shell/ledger_window.py`
- Ensure `do_open` binds `candidate_wb` with its `_source_package`.
- Ensure `do_save` seamlessly executes lossless roundtrip.

---

### Task 6: Add Targeted Test Suite in `tests/gui/test_phase7_xlsx_preserve.py`
- Create comprehensive tests:
  - `test_macro_xlsm_gui_save_unedited`: Test unedited GUI save chain on `macro-button-form-control.xlsm`.
  - `test_macro_xlsm_gui_save_edited_cell`: Test single-cell edit GUI save chain on `macro-button-form-control.xlsm`.
  - `test_corpus_comments_preservation`: Test comments in `poi__SimpleWithComments.xlsx`.
  - `test_corpus_charts_drawings_preservation`: Test charts and drawings in `poi__60509.xlsx`.
  - `test_corpus_protection_preservation`: Test protection in `libreoffice__enhanced-protection.xlsx`.
  - `test_corpus_custom_xml_preservation`: Test custom XML in `libreoffice__tdf113621.xlsx`.
  - `test_faulty_write_does_not_corrupt_original`: Test atomic save error handling.

---

### Task 7: Update Feature Matrix in `docs/clone/phase7_features.csv`
- Update the entry for XLSX Writer Engine with OPC Roundtrip with evidence.

---

### Task 8: Run Full Verification Suite
- Run:
  `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_xlsx_preserve.py tests/unit/corpus/test_excel_corpus.py -ra`
