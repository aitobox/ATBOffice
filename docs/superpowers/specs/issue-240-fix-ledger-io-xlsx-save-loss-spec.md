# Specification: Issue #240 (TASK-706) - Fix XLSX/XLSM Default Save Loss

## 1. Context and Problem Statement
When saving a loaded Excel workbook (.xlsx / .xlsm) in ATBOffice Ledger (either through GUI `do_save` or `write_xlsx(wb)` without explicit arguments), significant data loss occurs:
1. `read_xlsx` parses cells and styles into `WorkbookModel` but fails to bind the source `SourcePackage` to the model.
2. `write_xlsx` defaults to generating a brand new OPC package from scratch unless `source_opc` is explicitly passed. In GUI saves (`ledger_window.py:do_save`), `write_xlsx(self.spreadsheet_view.workbook, path)` was invoked without `source_opc`.
3. Even when `source_opc` was provided:
   - `PackageWriter._build_content_types_xml` generated invalid `<Override>` elements for `*.rels` parts and forcibly overrode `/xl/workbook.xml` with standard `CT_WORKBOOK` instead of `application/vnd.ms-excel.sheet.macroEnabled.main+xml`.
   - `_serialize_workbook_rels` recreated `xl/_rels/workbook.xml.rels` from scratch, dropping relationships to `vbaProject.bin`, `calcChain.xml`, and `customXml/item*.xml`.
   - Worksheet serialization discarded `<sheetProtection>`, `<drawing>`, `<legacyDrawing>`, `<controls>`, `<pageSetup>`, and `<sheetPr codeName="...">`, and worksheet rels dropped relationships to `vmlDrawing`, `printerSettings`, and `ctrlProp`.
   - As a result, macro-enabled workbooks (`macro-button-form-control.xlsm`) lost macros and became corrupted/invalid, and curated sample workbooks (`SimpleWithComments`, `60509`, `enhanced-protection`, `tdf113621`) lost comments, charts, protection, and custom XML.

## 2. Goals and Acceptance Criteria
- [x] **macro-button-form-control.xlsm preservation**:
  - Unedited GUI save chain: Opening `macro-button-form-control.xlsm` in `LedgerWindow` and saving without edits retains `vbaProject.bin` byte-for-byte (identical SHA-256), correct content type (`application/vnd.ms-excel.sheet.macroEnabled.main+xml`), workbook/sheet relationships, and produces a valid XLSM.
  - Single-cell edit GUI save chain: Opening in `LedgerWindow`, modifying a cell (e.g. A1 = 42), and saving preserves `vbaProject.bin` SHA, content types, relationships, controls, and produces a valid XLSM with the updated cell data.
- [x] **Feature preservation across curated corpus**:
  - `poi__SimpleWithComments.xlsx`: Preserves comments (`comments1.xml`), `vmlDrawing1.vml`, and worksheet relationships.
  - `poi__60509.xlsx`: Preserves charts (`chart1.xml`), drawings (`drawing1.xml`), `calcChain.xml`, and drawing/worksheet relationships.
  - `libreoffice__enhanced-protection.xlsx`: Preserves workbook and sheet protection tags without corruption.
  - `libreoffice__tdf113621.xlsx`: Preserves custom XML parts (`customXml/item*.xml`), `docProps/custom.xml`, and `workbook.xml.rels` custom XML relationships.
- [x] **Non-destructive failure handling**:
  - Faulty write attempts (simulated I/O failure or permission error) never corrupt or destroy the original file on disk (guaranteed by atomic write to temporary file with `fsync` before `os.replace`).
- [x] **Verification command**:
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_xlsx_preserve.py tests/unit/corpus/test_excel_corpus.py -ra` must exit with code 0.
- [x] **Feature matrix update**:
  - Update `docs/clone/phase7_features.csv` entry for XLSX roundtrip preservation with test evidence and status.

## 3. Architecture and Technical Design

### A. OPC Container Engine (`src/atboffice/vfs/opc.py`)
1. **ECMA-376 Content Types Conformance**:
   - In `_build_content_types_xml`: ensure parts ending in `.rels` are NEVER added to `<Override>`. The `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>` rule governs all relationship parts.
2. **Deterministic Part Sorting**:
   - Maintain `[Content_Types].xml` first, `_rels/.rels` second, followed by lexicographically sorted parts.

### B. Workbook and Sheet Models (`src/atboffice/modules/spreadsheet/models/`)
1. **Source Package Binding**:
   - `WorkbookModel`: Bind `_source_package: SourcePackage | None` and `extra["source_package"]`.
   - `SheetDataModel`: Add `self.dirty: bool = False`, `self.extra: dict[str, Any] = {}`, and `self.code_name: str | None = None`.
   - Mark `self.dirty = True` on mutations (`set_cell`, `set_cell_value`, `set_cell_formula`, `clear_cell`, `add_merge`).

### C. XLSX Reader (`src/atboffice/modules/spreadsheet/io/xlsx_reader.py`)
1. **Capture SourcePackage**:
   - In `read_xlsx`, instantiate `SourcePackage` from input stream/bytes/path and assign `wb.extra["source_package"] = source_pkg` and `wb._source_package = source_pkg`.
2. **Metadata Extraction**:
   - Extract `<workbookPr codeName="...">` into `wb.extra["code_name"]`.
   - Detect macro enablement: if `source_pkg.has_part("xl/vbaProject.bin")` or content type is `application/vnd.ms-excel.sheet.macroEnabled.main+xml`, set `wb.extra["is_macro_enabled"] = True`.
   - Extract `<workbookProtection ...>` into `wb.extra["protection"]`.
   - Extract `<definedNames>` into `wb.extra["defined_names"]`.
   - For each sheet: assign `sheet.extra["ooxml_part"] = s_part` and extract `<sheetProtection ...>`, `<sheetPr codeName="...">`, and `<autoFilter ...>`.

### D. XLSX Writer (`src/atboffice/modules/spreadsheet/io/xlsx_writer.py`)
1. **Source Package Resolution**:
   - `source_pkg` resolves from `source_opc or getattr(workbook, "_source_package", None) or workbook.extra.get("source_package")`.
2. **Macro & Content Type Handling**:
   - If `is_macro_enabled` (determined by `.xlsm` output path, `vbaProject.bin` present, or `wb.extra["is_macro_enabled"]`), use `CT_WORKBOOK_MACRO` (`application/vnd.ms-excel.sheet.macroEnabled.main+xml`).
3. **Workbook & Workbook Relationships Preservation**:
   - In `_serialize_workbook`: emit `codeName` in `<workbookPr>`, emit `<workbookProtection>`, and emit `<definedNames>`.
   - In `_serialize_workbook_rels`: preserve all non-replaced relationships from `source_pkg.get_relationships("xl/workbook.xml")` (e.g. `vbaProject`, `calcChain`, `customXml`, `externalLink`).
4. **Worksheet & Worksheet Relationships Preservation**:
   - For sheets with `ooxml_part` in `source_pkg`:
     - If not modified (`not sheet.dirty` and `not workbook.dirty`): reuse original XML bytes.
     - If modified: patch `<sheetData>` and `<dimension>` in the original worksheet XML, preserving all surrounding tags (`sheetPr`, `pageSetup`, `drawing`, `legacyDrawing`, `controls`, `sheetProtection`, etc.).
   - For sheet rels: preserve auxiliary relationships from `source_pkg` (`comments`, `vmlDrawing`, `printerSettings`, `ctrlProp`, `drawing`).

### E. GUI Shell (`src/atboffice/ui/shell/ledger_window.py`)
1. In `do_save`, ensure `write_xlsx` is called with the workbook. Because the workbook holds its `_source_package`, `write_xlsx` seamlessly executes lossless roundtrip carry.
2. In `do_open`, ensure `candidate_wb` attaches its `_source_package`.

## 4. Edge Cases & Error Handling
- **Overwrite Protection / Atomic Save**: `PackageWriter.save` writes to `.tmp_opc_*` in the destination directory, runs `os.fsync`, then performs atomic `os.replace`. If any exception occurs during packing or writing, the temporary file is unlinked and the original file is left intact.
- **Conversion on Save As (.xlsx vs .xlsm)**: If a user opens `.xlsm` and explicitly saves as `.xlsx`, macros may be stripped per user request, while saving to `.xlsm` preserves macros byte-for-byte.
- **Missing or Corrupt Parts in Source**: If a source part cannot be parsed or decoded, fall back gracefully to clean generated XML with non-blocking error capture.
