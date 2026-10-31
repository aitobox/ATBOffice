# Implementation Plan: Issue #164 - Word 2003 字数与版面统计对话框 (Word Count)

## Task Breakdown

### Task 1: Create Unit Test Suite for Word Count & Dialog
- **File**: `tests/modules/writer/test_word_count.py`
- **Details**:
  - Test pure statistics calculator with various texts:
    - English text (words, chars with/without spaces).
    - CJK Chinese text.
    - Mixed CJK, Western, and numeric text.
    - Blank / empty text and multi-line paragraphs.
  - Test document-level statistics:
    - Document with footnotes and endnotes (toggle `include_notes=True/False`).
    - Document with multiple pages.
  - Test selection vs document statistics:
    - Sliced selection stats compared against full document stats.
  - Test `WordCountDialog`:
    - Dialog instantiation, UI controls existence (table, checkbox, close button).
    - Dynamic re-computation when checkbox toggled.
    - Initializing with/without active selection.
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/writer/test_word_count.py -v` (Fails initially because implementation is missing).

### Task 2: Implement Word Count Engine and Dialog
- **File**: `src/atboffice/modules/writer/dialogs/word_count_dlg.py`
- **Details**:
  - Define `WordCountStats` dataclass.
  - Implement `count_text_statistics(text: str) -> WordCountStats`.
  - Implement `calculate_document_statistics(doc: Document, include_notes: bool = False, pagination: PaginationResult | None = None) -> WordCountStats`.
  - Implement `calculate_selection_statistics(canvas_view: WriterCanvasView) -> WordCountStats | None`.
  - Implement `WordCountDialog(QDialog)`:
    - Classic Word 2003 layout: statistics caption, table, include notes checkbox, Close button.
    - Multi-column comparison display when selection is non-empty.
    - Interactive checkbox event wiring to `recalculate()`.
    - Complete i18n support with `safe_tr()` and `retranslate_ui()`.
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/writer/test_word_count.py -v` passes.

### Task 3: Integrate Dialog into WriterView, QuireWindow, and Mac Menu
- **Files**:
  - `src/atboffice/modules/writer/dialogs/__init__.py`
  - `src/atboffice/modules/writer/view.py`
  - `src/atboffice/ui/shell/quire_window.py`
  - `src/atboffice/ui/shell/mac_menu.py`
- **Details**:
  - Export `WordCountDialog`, `WordCountStats`, `calculate_document_statistics` from `dialogs`.
  - Add `open_word_count_dialog(self) -> WordCountDialog` method to `WriterView`.
  - In `QuireWindow._bind_actions()`: connect `tools_word_count` and `wordCount` to `self.writer_view.open_word_count_dialog`.
  - In `mac_menu.py`: ensure `tools_word_count` / `wordCount` is registered and properly mapped.
- **Verification**: Ensure integration works smoothly and menu action triggers the dialog.

### Task 4: Full Verification and Regression Check
- Run all writer module tests:
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/writer/`
- Verify zero regressions.
