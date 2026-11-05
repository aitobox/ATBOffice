# Technical Specification: Issue #266 OLE Compound Document Detection, Encryption Differentiation, and 97-2003 Conversion Guidance

## 1. Overview & Problem Statement
In Microsoft Office file handling, files starting with the OLE Compound File Binary (CFB) header (`0xD0CF11E0A1B11AE1`) can represent either:
1. Encrypted Office Open XML packages (where OOXML `.docx`, `.xlsx`, `.pptx` are wrapped inside an OLE container with `EncryptionInfo` and `EncryptedPackage` streams).
2. Legacy binary Office 97–2003 documents (`.doc`, `.xls`, `.ppt`).
3. Disguised binary documents (e.g. legacy `.doc`, `.xls`, or `.ppt` files mistakenly or intentionally saved with `.docx`, `.xlsx`, or `.pptx` extensions).

Currently, ATBOffice has fragmented checks across `quire_window.py`, `ledger_window.py`, and `lectern_window.py`. These checks duplicate header reads, lack unified stream inspection, do not distinguish disguised extensions from correctly named legacy files, and lack the robust probe mechanism present in `.vibeoffice/public/common/zip.js`.

This specification aligns ATBOffice with `.vibeoffice`:
- Provides a unified OLE / CFB detection and stream inspection module in `atboffice.vfs.crypto` / `atboffice.vfs.ole`.
- Strictly separates encrypted OOXML packages from legacy binary documents.
- Detects disguised extensions with tailored conversion guidance matching `.vibeoffice`.
- Normalizes file dialog filters and preserves document transactional integrity upon warning.

---

## 2. Parity Alignment with .vibeoffice

| Component | .vibeoffice Reference | ATBOffice Target Parity |
|---|---|---|
| **Magic Header Detection** | `zip.js:304-306`: checks `0xe011cfd0` (`D0 CF 11 E0`) | `is_ole_compound_file`: checks `b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"` |
| **Encrypted Differentiation** | `zip.js:307-315`: probes `EncryptedPackage` via UTF-16LE / stream check | `is_encrypted_package`: checks `EncryptionInfo` and `EncryptedPackage` via `CFBReader` + UTF-16LE regex fallback |
| **Legacy Format Identification** | `pptx-read.js:748`, `xlsx-read.js:1151`, `docx-read.js:30` | `detect_ole_format`: classifies into `"word97"`, `"excel97"`, `"powerpoint97"`, `"encrypted_ooxml"`, `"legacy_binary"` |
| **Disguised Extension Warning** | `pptx-read.js:748`: "older binary PowerPoint 97–2003 file (.ppt) with a .pptx name" | `inspect_file_format`: tailored guidance mentioning original format and disguised name |
| **UI Non-Destructive Interception** | `app.js`: throws error, shows toast/dialog, does not destroy open doc | Raises `FileOpenWarningHandled`, state and window title untouched |

---

## 3. Architecture & Interface Design

### 3.1 Public IO Layer Additions (`atboffice.vfs.crypto`)
```python
def is_ole_compound_file(data: bytes | str | Path) -> bool:
    """Return True if data starts with the OLE CFB 8-byte signature."""

def detect_ole_format(data: bytes | str | Path) -> str:
    """Identify the specific format inside an OLE compound document.
    
    Returns:
        - "encrypted_ooxml": Contains EncryptionInfo and EncryptedPackage streams.
        - "word97": Contains WordDocument stream (Word 97-2003 .doc).
        - "excel97": Contains Workbook or Book stream (Excel 97-2003 .xls).
        - "powerpoint97": Contains PowerPoint Document or Current User stream (.ppt).
        - "legacy_binary": Unidentified OLE compound file.
        - "none": Not an OLE compound file.
    """

class FileFormatInspection:
    is_ole: bool
    is_encrypted: bool
    ole_format: str
    ext: str
    is_disguised: bool
    guidance_title: str | None
    guidance_message: str | None

def inspect_file_format(
    path_or_bytes: bytes | str | Path,
    expected_app: str | None = None
) -> FileFormatInspection:
    """Inspect file header, OLE streams, and extension to provide accurate guidance."""
```

### 3.2 OPC Package Exception Handling (`atboffice.vfs.opc`)
Define `OleCompoundFileError(ValueError)` in `atboffice.vfs.opc`:
- Raised when `SourcePackage.from_bytes` or `open` receives an OLE file instead of a ZIP package.
- Has attributes `is_encrypted`, `ole_format`, `raw_bytes`.

### 3.3 Shell Window Integration (`base_window.py`, `quire_window.py`, `ledger_window.py`, `lectern_window.py`)
- `BaseWindow` provides `handle_legacy_or_disguised_file(path: Path, app_name: str) -> bool`:
  Calls `inspect_file_format`. If it's a legacy or disguised binary file, shows `QMessageBox.warning` and raises `FileOpenWarningHandled`.
- `QuireWindow.do_open`, `LedgerWindow.do_open`, `LecternWindow.do_open` delegate legacy/disguise validation to this unified check.
- Non-CFB files (such as XML Spreadsheet 2003 or HTML table named `.xls`) proceed to their respective textual/XML parsers instead of being falsely rejected.

---

## 4. Internationalization (i18n)
All messages are wrapped in `safe_tr()`:
- Quire legacy:
  `“{name}”是旧版二进制 Word 97–2003 文档 (.doc)。Quire 原生支持 .docx、.html、.rtf、.md 和纯文本文件。请在 Word 或 LibreOffice 中将其另存为 .docx 格式后再打开。`
- Quire disguised:
  `“{name}”是旧版二进制 Word 97–2003 文档 (.doc)，但扩展名为 {ext}。请先在 Word、Pages、Google 文档或 LibreOffice 中将其另存为 .docx 格式。`
- Ledger legacy:
  `“{name}”是旧版二进制 Excel 97–2003 工作簿 (.xls)。Ledger 原生支持 .xlsx、.xlsm、.csv、.tsv 和 XML 电子表格。请在 Excel 或 LibreOffice 中将其另存为 .xlsx 格式后再打开。`
- Ledger disguised:
  `“{name}”是旧版二进制 Excel 97–2003 工作簿 (.xls)，但扩展名为 {ext}。请先在 Excel 或 LibreOffice 中将其另存为 .xlsx 格式。`
- Lectern legacy:
  `“{name}”是旧版二进制 PowerPoint 97–2003 演示文稿 (.ppt)。Lectern 原生支持 .pptx 演示文稿。请在 PowerPoint 或 LibreOffice 中将其另存为 .pptx 格式后再打开。`
- Lectern disguised:
  `“{name}”是旧版二进制 PowerPoint 97–2003 演示文稿 (.ppt)，但扩展名为 {ext}。请先在 PowerPoint、Keynote、Google 幻灯片或 LibreOffice 中将其另存为 .pptx 格式。`
- Mismatch guidance (e.g. PPT in Quire):
  `“{name}”是 PowerPoint 97–2003 演示文稿，而非 Word 文档。Quire 仅支持打开文字处理文档。`

---

## 5. Test Strategy
1. **Unit tests** (`tests/unit/vfs/test_ole_detection.py`):
   - Test `is_ole_compound_file` with tiny bytes, non-CFB zip, valid CFB, empty bytes.
   - Test `detect_ole_format` with simulated WordDocument, Workbook, PowerPoint Document, and EncryptedPackage streams.
   - Test corrupted CFB fallback with UTF-16LE substring probes.
   - Test `inspect_file_format` for genuine `.doc`/`.xls`/`.ppt`, disguised `.docx`/`.xlsx`/`.pptx`, and cross-module mismatches.
2. **GUI Contract tests** (`tests/gui/test_phase7_open_contract.py`):
   - Existing 9 regression tests remain green.
   - New tests for disguised extensions (`test_disguised_doc_as_docx`, `test_disguised_ppt_as_pptx`, `test_disguised_xls_as_xlsx`).
   - New tests for non-CFB XMLSS with `.xls` extension permitted in Ledger.
