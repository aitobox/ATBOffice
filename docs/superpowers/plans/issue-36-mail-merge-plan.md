# Implementation Plan: Issue #36 [Quire] Mail Merge (邮件合并) 与批量文档生成

## Overview
Implement the complete Office classic Mail Merge subsystem for Quire: CSV/TSV data source ingestion, alias normalization, `MERGEFIELD` dynamic placeholders and evaluation, live in-place preview, batch document generation with section breaks, PDF export, and classic Word 2003 6-step Wizard dialogs with full i18n support.

---

## Tasks

### Task 1: Test Scaffold for Mail Merge Data Ingestion & Models
- **File**: `tests/unit/writer/test_mailmerge.py`
- **Actions**:
  - Write test cases for `parse_delimited` (comma, tab, semicolon delimiters, quoted text with escaped quotes, BOM stripping, blank row filtering).
  - Write test cases for `MailMergeDataSource` (creation, active recipient filtering, column alias matching such as `FirstName` -> `first`, `ZIP Code` -> `zip`).
  - Run `pytest tests/unit/writer/test_mailmerge.py` (verify failure as module not yet created).

### Task 2: Implement Mail Merge Core Models & Data Source Parsing
- **File**: `src/atboffice/modules/writer/models/mailmerge.py`
- **Actions**:
  - Implement `parse_delimited(text)` and `load_data_source_from_csv(path)`.
  - Implement `MailMergeDataSource` with fields, rows, `included` set, sorting, and alias lookup dictionary.
  - Implement `ADDRESS_FIELDS` standard 13 fields.
  - Run `pytest tests/unit/writer/test_mailmerge.py` to verify tests pass.

### Task 3: Field Integration & MERGEFIELD Evaluation
- **Files**:
  - `src/atboffice/modules/writer/models/field.py`
  - `src/atboffice/modules/writer/models/mailmerge.py`
- **Actions**:
  - Add `MERGEFIELD`, `MERGEREC`, `MERGESEQ` support in `field.py` and `mailmerge.py`.
  - In design mode (no data source or preview off), evaluate to placeholder `«FieldName»`.
  - In preview/merge mode, evaluate to data source value with `\b` (prefix) and `\f` (suffix) and general formatting switches (`\* Upper`, `\* Caps`, etc.).
  - Add unit tests for field evaluation in `test_mailmerge.py`.

### Task 4: Implement Batch Merging & Document Generator
- **File**: `src/atboffice/modules/writer/models/mailmerge.py`
- **Actions**:
  - Implement `MailMergeEngine.build_merged_document(src_doc: Document, doc_type: str = "letters") -> Document`.
  - Clone document structure, replace merge field items with concrete text runs.
  - Implement Word blank line suppression for empty address block paragraphs.
  - Insert `nextPage` section breaks between records.
  - Implement `export_merged_pdf(src_doc: Document, output_path: str | Path)` using Qt / layout renderer.
  - Add unit tests verifying multi-record document generation and verify pass.

### Task 5: Implement Classic Word 2003 Mail Merge Wizard & Dialogs
- **File**: `src/atboffice/modules/writer/dialogs/mailmerge_wizard.py`
- **Actions**:
  - Implement `MailMergeWizardDialog` with 6 standard steps:
    1. Select document type (Letters, Envelopes, Labels, Directory)
    2. Select starting document (Current document, Template, Existing)
    3. Select recipients (Browse CSV, Edit recipient list, Type new list)
    4. Write your letter (Insert Merge Field, Address Block, Greeting Line)
    5. Preview your letters (<<, >>, Recipient N of M, Exclude)
    6. Complete the merge (Merge to new document, Print to PDF)
  - Implement `MailMergeRecipientsDialog` (table view with checkboxes and sorting).
  - Implement `AddressListDialog` ("Type a New Address List" modal).
  - Implement `InsertMergeFieldDialog` (list of available fields).
  - 100% i18n support with `safe_tr()` and `retranslate_ui()`.

### Task 6: Integrate with WriterView & GUI Actions
- **Files**:
  - `src/atboffice/modules/writer/view.py`
  - `src/atboffice/modules/writer/dialogs/__init__.py`
- **Actions**:
  - Export dialogs in `dialogs/__init__.py`.
  - Add helper methods on `WriterView` to open Mail Merge Wizard, preview records, and insert merge fields.
  - Add GUI tests in `tests/unit/writer/test_mailmerge.py` to test dialog creation and interactions.

### Task 7: Full Verification Suite Run
- **Command**: `pytest tests/unit/writer/ -v` and `pytest tests/ -v -k "writer or quire"`
- Verify 100% test pass.
