# Design Specification - Issue #107: Lossless OPC Container Hardening & Byte-for-Byte Preservation

## 1. Overview & Objectives
Issue #107 reinforces the Open Packaging Conventions (OPC) engine (`src/atboffice/vfs/opc.py`) in ATBOffice. The implementation ensures 1:1 behavioral alignment with the original reference (`.vibeoffice/public/common/opc.js` and `.vibeoffice/tools/ooxml/package.py`), supporting:
1. Deep nested Part relationship tree traversal and cycle-safe graph resolution (`subtree`, `resolve_part_uri`, `relative_part_uri`).
2. Exact `[Content_Types].xml` reconstruction with case-insensitive `Default` extensions and `/PartName` `Override` mapping.
3. Byte-for-byte stream preservation (`preserve_unmodified_parts`) ensuring that unedited parts (such as VBA macros `vbaProject.bin`, ActiveX controls, themes, drawings, media, unknown custom XML) retain 100% identical byte contents (MD5/SHA256 alignment).
4. Uniform part name normalization and path sanitization (handling leading slashes, Windows separators, URL encodings, and case sensitivity).

---

## 2. Architecture & Data Structures

### 2.1 Relationship Representation & Normalization
```python
@dataclass(frozen=True)
class Relationship:
    id: str
    type: str
    target: str
    target_mode: str = "Internal"
    fragment: str = ""
```
- `target_mode`: `"Internal"` | `"External"`
- `fragment`: anchor fragment (e.g., `#Sheet1!A1`) if present
- `target_part`: property computing the internal normalized target part name (resolving `target` relative to the owner part).

### 2.2 URI & Path Utilities
- `normalize_part_name(name: str) -> str`: Normalizes separators (`\` to `/`), decodes percent-encoded components safely, removes redundant `./` and leading `/`.
- `resolve_part_uri(owner_part: str, target_uri: str) -> str`: Resolves a relative or absolute target URI from the owner part within package bounds. Rejects paths escaping the package (`..` beyond root).
- `relative_part_uri(owner_part: str, target_part: str) -> str`: Computes the relative path from owner directory to target part.
- `get_rels_path(owner_part: str) -> str`:
  - `""` -> `_rels/.rels`
  - `"xl/workbook.xml"` -> `"xl/_rels/workbook.xml.rels"`
- `get_owner_from_rels_path(rels_path: str) -> str`:
  - `"_rels/.rels"` -> `""`
  - `"xl/_rels/workbook.xml.rels"` -> `"xl/workbook.xml"`

### 2.3 SourcePackage Extensions
- `subtree(start_part: str = "") -> list[str]`: Traverses the relationship DAG starting from `start_part` (empty string for package root), returning all reachable internal parts in breadth-first or depth-first order with cycle detection.
- `find_referrers(part_name: str) -> list[tuple[str, Relationship]]`: Reverse lookup finding all owner parts and relationships that reference `part_name`.
- `has_part(part_name: str) -> bool`: Normalization-aware presence check.
- `read_part(part_name: str) -> bytes`: Returns exact raw bytes.
- `get_content_type(part_name: str) -> str | None`: Resolves Override first, then Default extension (case-insensitive).

### 2.4 Lossless Preservation & PackageWriter
- `preserve_unmodified_parts(source: SourcePackage | zipfile.ZipFile | bytes | Path, target_zip: zipfile.ZipFile, modified_parts: set[str] | dict[str, bytes], deleted_parts: set[str] | None = None) -> list[str]`:
  Copies every part from `source` that is neither in `modified_parts` nor in `deleted_parts` directly as raw binary bytes into `target_zip`. Returns the list of preserved part names.
- `PackageWriter`:
  - Maintains source package reference.
  - Allows `replace_part`, `add_part`, `delete_part`.
  - In `to_bytes()` and `save()`, unedited parts are copied byte-for-byte with exact SHA-256 preservation.
  - Automatically regenerates or updates `[Content_Types].xml` and modified `.rels` while keeping unedited `.rels` files intact.

---

## 3. Edge Cases & Error Handling

1. **Path Traversal Attacks**: Targets like `../../../../etc/passwd` or `../outside.xml` escaping root raise `ValueError("Part URI escapes package")`.
2. **External Relationships**: Hyperlinks, email targets, and external resources (`TargetMode="External"`) are preserved with their raw target strings without local path resolution.
3. **Circular Dependencies**: Graph traversal in `subtree` tracks `visited` set to prevent infinite loops.
4. **Case Sensitivity**: Windows zip implementations or casing variations (`.XML`, `.png`) are mapped cleanly without duplicating entries in `[Content_Types].xml`.
5. **Binary Integrity**: Media files and binary streams (e.g. `vbaProject.bin`, `printerSettings.bin`) must not undergo string decoding/encoding or CRLF translations.
6. **Atomic Disk Write**: Saving uses `tempfile.NamedTemporaryFile` + `fsync` + `os.replace` to prevent corrupted files on crash.

---

## 4. Acceptance Criteria & Test Plan

1. **Test Suite**: `tests/vfs/test_opc_preserve.py`
2. **Coverage**:
   - Relationship resolution (`resolve_part_uri`, `relative_part_uri`, boundary protection).
   - Relationship tree traversal (`subtree` with multi-level nesting and cycle detection).
   - Content types resolution (Override vs Default, case insensitivity, dynamic generation).
   - Byte-for-byte carry test: modifying `sheet1.xml` in a multi-part XLSX package with `vbaProject.bin` and images, verifying that SHA256 of `vbaProject.bin` and images matches source exactly.
   - `preserve_unmodified_parts` function interface validation.
   - Preserving `.rels` byte streams when relationships for an owner are unchanged.
   - Full regression pass of `tests/unit/vfs/test_opc.py` and project-wide test suite.
