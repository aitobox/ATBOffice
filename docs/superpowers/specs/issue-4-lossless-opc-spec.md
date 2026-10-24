# Specification: Issue #4 Lossless OPC Packaging Engine & Strict Schema Ordering

## 1. Overview & Problem Statement
Office Open XML (OOXML) documents (`.xlsx`, `.xlsm`, `.docx`, `.pptx`) are ZIP-based packages adhering to the Open Packaging Conventions (ECMA-376 Part 2). When opening, modifying, and re-saving spreadsheets in ATBOffice:
1. Unmodified parts (such as VBA macro projects `vbaProject.bin`, ActiveX controls, printer settings, embedded drawings, and custom XML parts) must be carried byte-for-byte from the source package to prevent data corruption or losing macro functionality.
2. Serialized XML structures must strictly adhere to the ECMA-376 element sequences (e.g., `s:CT_Worksheet`, `s:CT_Workbook`, `s:CT_Stylesheet`), as spreadsheet applications like Microsoft Excel and LibreOffice strictly validate schema child order and prompt with file repair warnings when out of sequence.
3. File saving must use atomic writing (`NamedTemporaryFile` + `os.replace`) to protect user data from corruption during sudden process termination or power loss.

---

## 2. Requirements & Acceptance Criteria
- **SourcePackage**:
  - Open from `Path`, filename string, or `bytes`.
  - Provide `has_part(part_name: str) -> bool` and `read_part(part_name: str) -> bytes`.
  - Provide `get_content_type(part_name: str) -> str | None`.
  - Provide `get_relationships(part_name: str = "") -> list[Relationship]`.
  - Normalize part names transparently (handling both `/xl/workbook.xml` and `xl/workbook.xml`).
- **PackageWriter**:
  - Initialize with optional `source_package: SourcePackage | None`.
  - Support `replace_part(part_name: str, content: bytes, content_type: str | None = None)`.
  - Support `add_part(part_name: str, content: bytes, content_type: str)`.
  - Support `delete_part(part_name: str)`.
  - Carry all unmodified parts byte-for-byte from `source_package`.
  - Automatically maintain `[Content_Types].xml` overrides and defaults.
  - Provide `save(target_path: Path | str)` using atomic replace.
  - Provide `to_bytes() -> bytes`.
- **Strict Schema Ordering (`enforce_schema_order`)**:
  - Implement ordering for:
    - `spreadsheetml_worksheet` (`s:CT_Worksheet`)
    - `spreadsheetml_workbook` (`s:CT_Workbook`)
    - `spreadsheetml_styles` (`s:CT_Stylesheet`)
  - Reorder `xml.etree.ElementTree.Element` children in-place according to ECMA-376 Part 4.
  - Support both Clark notation `{http://schemas.openxmlformats.org/spreadsheetml/2006/main}tag` and local tag names `tag`.
- **Robustness**:
  - Clean error handling for corrupted packages, missing files, and invalid formats.
  - 100% type-annotated code.

---

## 3. Architecture & Module Design
- `src/atboffice/vfs/opc.py`: Core `SourcePackage`, `PackageWriter`, `Relationship`, and content-type resolution.
- `src/atboffice/vfs/order.py`: ECMA-376 schema order sequences and `enforce_schema_order(root: Element, schema_family: str)` function.
- `src/atboffice/vfs/xml_tree.py`: XML parsing and serialization helpers preserving encoding and namespaces.
