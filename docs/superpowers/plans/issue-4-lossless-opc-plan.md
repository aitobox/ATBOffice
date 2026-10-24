# Implementation Plan: Issue #4 Lossless OPC Packaging Engine & Strict Schema Ordering

## User Review Required
None. High confidence (>=90%) autonomous execution.

---

## Tasks Breakdown

### Task 1: TDD Unit Tests for Schema Ordering and OPC Packaging
- Create `tests/unit/vfs/test_order.py`
  - Test worksheet schema ordering (out-of-order tags like `mergeCells` before `sheetData`).
  - Test workbook schema ordering (e.g. `sheets` before `workbookPr`).
  - Test styles schema ordering (e.g. `cellXfs` before `fonts`).
  - Test namespace handling (`{http://schemas.openxmlformats.org/spreadsheetml/2006/main}`).
  - Test unmatched/extension tags are preserved cleanly at end.
- Create `tests/unit/vfs/test_opc.py`
  - Test `SourcePackage.from_bytes` and `SourcePackage.open`.
  - Test `has_part`, `read_part`, `get_content_type`, `get_relationships`.
  - Test `PackageWriter` byte-for-byte carry on unmodified parts (e.g. `vbaProject.bin`, drawings).
  - Test `PackageWriter.replace_part`, `add_part`, `delete_part`.
  - Test atomic save (`save(path)`) using temporary file and `os.replace`.
  - Test error handling on corrupted/invalid packages.

### Task 2: Implement Schema Ordering (`src/atboffice/vfs/order.py`)
- Port schema order sequences from `.vibeoffice/public/common/opc-order.js` for:
  - `spreadsheetml_worksheet` (`s:CT_Worksheet`)
  - `spreadsheetml_workbook` (`s:CT_Workbook`)
  - `spreadsheetml_styles` (`s:CT_Stylesheet`)
- Implement `enforce_schema_order(root_element: Element, schema_family: str) -> None`.

### Task 3: Implement XML Helpers (`src/atboffice/vfs/xml_tree.py`)
- Implement lightweight XML parse, serialize, and namespace stripping/matching utilities.

### Task 4: Implement Lossless OPC Packaging (`src/atboffice/vfs/opc.py`)
- Implement `Relationship` dataclass.
- Implement `SourcePackage` wrapping `zipfile.ZipFile`:
  - Parses `[Content_Types].xml` (Default extensions and Override part names).
  - Parses package-level and part-level `.rels`.
  - Normalizes part names (strips leading `/`).
- Implement `PackageWriter`:
  - Carries all untouched parts from `source_package` byte-for-byte.
  - Generates updated `[Content_Types].xml`.
  - Atomically saves to disk with `tempfile.NamedTemporaryFile` + `os.replace`.

### Task 5: Full Test Suite Verification
- Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/vfs/ -v`
- Run full test suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/`
- Verify 100% pass with zero regressions.
