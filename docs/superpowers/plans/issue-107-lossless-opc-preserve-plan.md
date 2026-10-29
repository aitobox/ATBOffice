# Implementation Plan - Issue #107: Lossless OPC Container Hardening & Byte-for-Byte Preservation

## Overview
This plan implements the complete specification for Issue #107: reinforcing `src/atboffice/vfs/opc.py` with deep relationship resolution, cycle-safe subtree traversal, exact content type overrides/defaults, and byte-for-byte stream preservation (`preserve_unmodified_parts`).

---

## Tasks

### Task 1: Write Comprehensive Test Suite (`tests/vfs/test_opc_preserve.py`)
- **Action**: Create `tests/vfs/test_opc_preserve.py`.
- **Test Scenarios**:
  1. `test_part_name_normalization_and_uri_resolution`: Leading slashes, backslashes, percent-decoding, `..` resolution, and package escape validation.
  2. `test_relative_part_uri`: Relative path computation between directories and files.
  3. `test_relationship_resolution_and_subtree`: Multi-tiered relationship tree (`_rels/.rels` -> `xl/workbook.xml` -> `xl/worksheets/sheet1.xml` -> `xl/drawings/drawing1.xml` -> `xl/media/image1.png`), plus cycle handling.
  4. `test_content_type_resolution`: Default extension case-insensitivity (`.PNG`, `.xml`), overrides, unknown extensions.
  5. `test_preserve_unmodified_parts_function`: Standalone function copying unedited parts to a new zipfile.
  6. `test_package_writer_byte_for_byte_sha256`: Opening a package with VBA macros and images, modifying one XML part, verifying preserved parts maintain 100% SHA256 integrity.
  7. `test_unmodified_rels_preservation`: Verifying that `.rels` byte streams remain identical when relationships are not touched.
- **Verification Command**:
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/vfs/test_opc_preserve.py -v` (Initially fails on missing methods/signatures).

### Task 2: Implement Core OPC Enhancements (`src/atboffice/vfs/opc.py`)
- **Action**: Edit `src/atboffice/vfs/opc.py`.
- **Implementations**:
  1. URI utilities: `normalize_part_name`, `resolve_part_uri`, `relative_part_uri`.
  2. `Relationship` dataclass with `fragment` and `target_part(owner: str)` support.
  3. `SourcePackage` additions:
     - `subtree(start_part: str = "") -> list[str]`
     - `find_referrers(part_name: str) -> list[tuple[str, Relationship]]`
     - Robust content type resolution with case-insensitive extensions.
  4. `preserve_unmodified_parts(source, target_zip, modified_parts, deleted_parts=None) -> list[str]` standalone API.
  5. `PackageWriter` byte-for-byte preservation and deterministic ZIP packing.

### Task 3: Execute Unit Tests & Verify Behavior
- **Action**: Run targeted test suite:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/vfs/test_opc_preserve.py tests/unit/vfs/test_opc.py -v
  ```
- **Expected Outcome**: All tests pass.

### Task 4: Run Repository-Wide Test Suite
- **Action**: Verify no regressions across the entire project:
  ```bash
  PYTHONPATH=src conda run -n ATBOffice pytest tests/
  ```
- **Expected Outcome**: All passing tests remain passing (with only pre-existing known exceptions if any).

### Task 5: Transition to Code Review
- **Action**: Update `.github-agent-state.yml` to `reviewing` and trigger `atb-github-code-reviewer`.
