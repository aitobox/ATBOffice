# Implementation Plan: Universal Printing, Print Preview, and Vector PDF Export

- **Issue**: #134 ([Phase 3] 构建通用打印预览与无损矢量 PDF 导出子系统)
- **Target Branch**: `agent/issue-134-print-preview-pdf-export`
- **Spec**: `docs/superpowers/specs/issue-134-print-preview-pdf-export-spec.md`

---

## Tasks

### Task 1: BaseOfficeWindow Core Printing & PDF Export Interfaces
- **Files**:
  - `src/atboffice/ui/shell/base_window.py`
  - `tests/ui/test_printing.py`
- **Actions**:
  - Add imports from `PySide6.QtPrintSupport` (`QPrinter`, `QPrintDialog`, `QPrintPreviewDialog`).
  - Implement `print_document(printer: QPrinter | None = None) -> bool`.
  - Implement `print_preview(printer: QPrinter | None = None) -> bool`.
  - Implement `export_pdf(output_path: str | Path | None = None) -> bool`.
  - Define `render_to_printer(self, printer: QPrinter) -> None`.
  - Add safe dialogs and error alerts with `safe_tr`.
- **Verification**:
  - Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_printing.py -k test_base_window -v`

### Task 2: Quire Document Page Rendering Pipeline
- **Files**:
  - `src/atboffice/ui/shell/quire_window.py`
  - `tests/ui/test_printing.py`
- **Actions**:
  - Register `print` and `printPreview` action handlers in `QuireWindow`.
  - Implement `render_to_printer(self, printer: QPrinter)`.
  - Page iteration: page breaks, margins, header/footer text, paragraph portions, text fonts, math formulas, tab leaders, table grid cells, borders, and fills.
- **Verification**:
  - Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_printing.py -k test_quire -v`

### Task 3: Ledger Worksheet Pagination, Gridlines & Repeat Headers
- **Files**:
  - `src/atboffice/ui/shell/ledger_window.py`
  - `tests/ui/test_printing.py`
- **Actions**:
  - Wire `print_workbook` and `print_preview` in `LedgerWindow`.
  - Implement `render_to_printer(self, printer: QPrinter)`.
  - Calculate row/column pagination breaks.
  - Implement repeating header rows at the top of pages.
  - Render gridlines, cell values, font formats, patterns, cell borders, and drawings.
- **Verification**:
  - Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_printing.py -k test_ledger -v`

### Task 4: Lectern Slide Rendering & 3-Slide Handout Mode
- **Files**:
  - `src/atboffice/ui/shell/lectern_window.py`
  - `tests/ui/test_printing.py`
- **Actions**:
  - Wire `print` and `printPreview` in `LecternWindow`.
  - Implement `render_to_printer(self, printer: QPrinter, mode: str = "slides", handouts_per_page: int = 3)`.
  - In slides mode: render each slide vector graphics to one printer page.
  - In handouts mode (3 per page): render 3 thumbnail slides on the left and note lines on the right.
- **Verification**:
  - Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_printing.py -k test_lectern -v`

### Task 5: Feature Matrix Update & Full Test Suite Pass
- **Files**:
  - `docs/clone/features.csv`
  - `tests/ui/test_printing.py`
- **Actions**:
  - Update `features.csv` entry `Document Printing and Print Preview Subsystem` status to `yes`.
  - Run full test suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/ui/test_printing.py -v`.
