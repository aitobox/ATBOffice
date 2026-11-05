# Implementation Plan: Issue #266 OLE Compound Document Detection, Encryption Differentiation, and 97-2003 Conversion Guidance

## Overview
This plan implements a centralized OLE / CFB detection and stream inspection engine, distinguishes encrypted OOXML packages from legacy 97-2003 binary formats, adds disguised extension detection (.doc/.xls/.ppt masked as .docx/.xlsx/.pptx), and integrates robust user guidance dialogs into Quire, Ledger, and Lectern.

---

## Tasks

### Task 1: Unit Tests for OLE Detection & Format Inspection (TDD)
- **Files**: `tests/unit/vfs/test_ole_detection.py`
- **Actions**:
  1. Test `is_ole_compound_file`: returns `True` for CFB signature, `False` for non-CFB / ZIP / empty data.
  2. Test `detect_ole_format`:
     - Returns `"encrypted_ooxml"` for CFB with `EncryptionInfo` + `EncryptedPackage`.
     - Returns `"word97"` for CFB with `WordDocument`.
     - Returns `"excel97"` for CFB with `Workbook` or `Book`.
     - Returns `"powerpoint97"` for CFB with `PowerPoint Document` or `Current User`.
     - Returns `"legacy_binary"` for other OLE files.
     - Fallback detection using UTF-16LE probes when directory structure is damaged.
  3. Test `inspect_file_format`:
     - Detects disguised `.doc` named `.docx`.
     - Detects disguised `.xls` named `.xlsx`.
     - Detects disguised `.ppt` named `.pptx`.
     - Detects cross-module mismatches (e.g. `.ppt` opened in Quire).
     - Returns appropriate localized warning messages.
- **Verification**: Run pytest (expect failures initially before implementation).

### Task 2: Core IO Implementation in `src/atboffice/vfs/crypto.py` and `src/atboffice/vfs/opc.py`
- **Files**:
  - `src/atboffice/vfs/crypto.py`
  - `src/atboffice/vfs/__init__.py`
  - `src/atboffice/vfs/opc.py`
- **Actions**:
  1. In `crypto.py`:
     - Implement `is_ole_compound_file(data)`.
     - Enhance `CFBReader` or add fallback UTF-16LE probe detection.
     - Implement `detect_ole_format(data)`.
     - Define `FileFormatInspection` dataclass.
     - Implement `inspect_file_format(path_or_bytes, expected_app)`.
  2. In `opc.py`:
     - Define `OleCompoundFileError(ValueError)`.
     - In `SourcePackage.from_bytes`, if `is_ole_compound_file(data)`, raise `OleCompoundFileError`.
  3. Re-export new utilities from `atboffice.vfs`.
- **Verification**: Run `tests/unit/vfs/test_ole_detection.py` and `tests/unit/vfs/test_crypto.py`.

### Task 3: Shell Integration & Normalized Filters in Quire, Ledger, and Lectern
- **Files**:
  - `src/atboffice/ui/shell/base_window.py`
  - `src/atboffice/ui/shell/quire_window.py`
  - `src/atboffice/ui/shell/ledger_window.py`
  - `src/atboffice/ui/shell/lectern_window.py`
- **Actions**:
  1. In `base_window.py`:
     - Add `handle_legacy_or_disguised_file(self, path: Path, app_name: str) -> bool` using `inspect_file_format`.
     - Show `QMessageBox.warning` with `inspection.guidance_message`.
     - Raise `FileOpenWarningHandled`.
  2. In `quire_window.py`, `ledger_window.py`, `lectern_window.py`:
     - Replace duplicated binary header read with `self.handle_legacy_or_disguised_file(path, "quire" | "ledger" | "lectern")`.
     - In Ledger, ensure non-CFB files with `.xls` extension (e.g. XMLSS or HTML table) are not falsely blocked by the CFB check.
     - Verify `get_file_filter()` includes standard 97-2003 filter patterns (`*.doc *.dot`, `*.xls *.xlt`, `*.ppt *.pps *.pot`).
- **Verification**: Verify GUI behavior and rollback safety.

### Task 4: GUI Contract & Disguised Extension Tests
- **Files**: `tests/gui/test_phase7_open_contract.py`
- **Actions**:
  1. Add `test_quire_disguised_doc_as_docx_rejected_with_guidance`.
  2. Add `test_ledger_disguised_xls_as_xlsx_rejected_with_guidance`.
  3. Add `test_lectern_disguised_ppt_as_pptx_rejected_with_guidance`.
  4. Add `test_ledger_non_cfb_xmlss_with_xls_ext_not_blocked_by_cfb`.
- **Verification**: Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase7_open_contract.py -v`.

### Task 5: Full Regression Testing & Quality Verification
- **Verification**: Run project-wide tests:
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_phase7_open_contract.py tests/unit/vfs/ -v`
