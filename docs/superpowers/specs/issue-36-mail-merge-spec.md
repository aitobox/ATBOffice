# Specification: Issue #36 [Quire] Mail Merge (邮件合并) 与批量文档生成

## 1. Overview & Problem Statement
Office classic "Mail Merge" (邮件合并) enables users to create personalized form letters, envelopes, mailing labels, and directories by linking a template document with external tabular datasets (such as CSV, TSV, or typed address lists).
In Quire (Word 2003 port), mail merge allows inserting dynamic `MERGEFIELD` placeholders (e.g., `«Name»`, `«Company»`), filtering and sorting recipients, previewing individual records in-place, and executing batch generation to a new consolidated multi-section document or direct PDF export.

This specification defines the architecture, data models, field evaluation rules, document merge engine, and PySide6 UI wizard dialogs in accordance with `.vibeoffice/public/quire/js/mailmerge.js`.

---

## 2. Reference Implementation Analysis (`.vibeoffice/public/quire/js/mailmerge.js`)
The original JavaScript implementation in `.vibeoffice` provides:
1. **Data Source Ingestion**:
   - `parseDelimited(text)`: Auto-detects delimiters (tab `\t`, semicolon `;`, or comma `,`), handles quotes `""`, newlines, strips UTF-8 BOM (`\ufeff`), and generates rows.
   - `setData(name, rows)`: Extracts headers (falling back to `FieldN`), tracks `included` recipient indices in a `Set`, and initializes record cursor `rec = 0`.
   - `typeList()`: Built-in 13 standard address fields editor dialog (Title, First Name, Last Name, Company Name, Address Line 1, Address Line 2, City, State, ZIP Code, Country, Home Phone, Work Phone, E-mail Address).
2. **Field Resolution & Alias Normalization**:
   - `norm(s)`: Sanitizes field names (lowercased alphanumeric).
   - `fieldFor(want)` & `value(name)`: Resolves field names with fuzzy alias fallback (e.g. `firstname` maps to `['first', 'fname', 'givenname']`, `zipcode` maps to `['zip', 'postalcode', 'postcode']`).
   - Supports `MERGEFIELD` with `\b` (prefix text if value not empty) and `\f` (suffix text if value not empty), plus standard `\*` formatting.
   - Supports `MERGEREC` and `MERGESEQ` evaluating to the 1-based record index.
3. **Template Transformation & Merging**:
   - `mergedBlocks(srcBlocks)`: Clones document blocks, replaces `MERGEFIELD` run sequences (`fb`...`fe`) with evaluated text runs, and suppresses empty address lines.
   - `buildMerged()`: Clones styles, numbering, settings, headers/footers, and joins per-record blocks into sections separated by `nextPage` section breaks.
   - `mergeToNew()` & `mergeToPDF()`: Emits a new `Document` or exports to PDF.
4. **Task Pane Wizard**:
   - 6-step workflow: Document Type -> Starting Document -> Recipients -> Write Letter -> Preview -> Complete Merge.

---

## 3. Architecture & Module Design

### 3.1 Module Structure
- `src/atboffice/modules/writer/models/mailmerge.py`:
  - `MailMergeDataSource`: Tabular dataset container with field names, record rows, and recipient inclusion tracking.
  - `MailMergeEngine`: Core evaluation, preview management, field value extraction, and batch document merge engine.
  - `AddressBlockConfig` & `GreetingLineConfig`: Builders for standard Word address blocks and greeting lines.
  - `parse_delimited(text)` / `load_data_source_from_csv(file_path)`: Robust CSV/TSV parser.
- `src/atboffice/modules/writer/dialogs/mailmerge_wizard.py`:
  - `MailMergeWizardDialog`: Word 2003 6-step wizard dialog or task pane.
  - `MailMergeRecipientsDialog`: Table-based recipient selection, sorting, and toggle dialog.
  - `AddressListDialog`: "Type a New Address List" modal for quick data entry.
  - `InsertMergeFieldDialog`: Dialog to choose and insert fields from the loaded data source.
- `src/atboffice/modules/writer/models/field.py`:
  - Enhance `evaluate_field` to resolve `MERGEFIELD`, `MERGEREC`, and `MERGESEQ` when a `mailmerge_engine` or context is provided, and fallback to `«FieldName»` placeholder in design mode.

### 3.2 Data Models (`models/mailmerge.py`)

```python
@dataclass
class MailMergeDataSource:
    name: str
    fields: list[str]
    rows: list[list[str]]
    included: set[int] = field(default_factory=set)
    is_typed: bool = False

    def active_records(self) -> list[int]:
        """Return row indices included in the merge."""
        return [i for i in range(len(self.rows)) if i in self.included]

    def get_value(self, record_index: int, field_name: str) -> str:
        """Resolve value for field_name with alias resolution."""
        ...
```

### 3.3 Merge Engine (`MailMergeEngine`)
- Manages active data source, current record index `current_record`, and preview state `preview_enabled`.
- Methods:
  - `set_data_source(source: MailMergeDataSource)`
  - `value(field_name: str, record_index: int | None = None) -> str`
  - `evaluate_merge_instruction(instr: str, record_index: int | None = None) -> str`
  - `toggle_preview(doc: Document) -> bool`
  - `step_record(doc: Document, delta: int) -> int`
  - `insert_field(doc: Document, p: Paragraph, offset: int, field_name: str)`
  - `insert_address_block(doc: Document, p: Paragraph, offset: int)`
  - `insert_greeting_line(doc: Document, p: Paragraph, offset: int, greeting: str = "Dear", salutation: str = ",")`
  - `build_merged_document(src_doc: Document) -> Document`
  - `export_merged_pdf(src_doc: Document, output_path: str | Path)`

---

## 4. Edge Cases & Robustness Handlers
1. **Missing or Mismatched Columns**:
   - If a `MERGEFIELD` references a non-existent field, return empty string in preview/merge without throwing an exception.
   - In non-preview mode, preserve placeholder `«FieldName»`.
2. **Blank Line Suppression**:
   - Word suppresses address lines where all merged fields are empty so blank lines don't appear in postal addresses.
3. **Delimiter & Encoding Flexibility**:
   - Handles comma, tab, and semicolon-delimited CSVs.
   - Cleans UTF-8 BOM `\ufeff`.
   - Handles multi-line quoted fields properly.
4. **Empty Data Source**:
   - Rejects empty datasets cleanly with informative error message.
5. **Section Break Insertion**:
   - When merging into a single document, inserts `nextPage` section breaks between records to ensure clean page pagination per recipient.

---

## 5. UI & i18n Requirements
- All dialog labels, buttons, tooltips, and prompts must use `safe_tr()` / `QCoreApplication.translate()`.
- Implement full `retranslate_ui()` in `MailMergeWizardDialog` and child dialogs.
- Provide idiomatic Chinese translations (e.g., "邮件合并向导", "插入合并域", "收件人列表", "地址块", "问候行").

---

## 6. Verification Plan
- Unit tests: `tests/unit/writer/test_mailmerge.py` covering:
  - CSV/TSV parsing (commas, tabs, quotes, BOM, delimiter auto-detection).
  - Field alias resolution and value retrieval.
  - `MERGEFIELD` formatting (`\b`, `\f`, `\* Upper`, `\* Caps`).
  - Blank line suppression in address blocks.
  - Multi-record document generation with section breaks.
  - Recipient filtering (included set) and sorting.
  - Dialog and UI components instantiation without error.
