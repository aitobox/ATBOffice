# Design Specification: Document Printing, Print Preview, and Vector PDF Export Subsystem

## Context & Objectives
- **Issue**: #134 ([Phase 3] 构建通用打印预览与无损矢量 PDF 导出子系统)
- **Parent Epic**: #129 (ATBOffice Phase 3)
- **Problem Statement**:
  ATBOffice previously only used `QPrinter` in the mail merge wizard to export PDFs. Main application windows (`QuireWindow`, `LedgerWindow`, `LecternWindow`) lack standard `File ▸ Print (Ctrl+P)` and `Print Preview` implementations. Ledger lacks worksheet print pagination and headers/gridline printing, and applications cannot export lossless vector PDFs.
- **Goal**:
  Build a universal, rock-solid printing, print preview, and vector PDF export subsystem in `BaseOfficeWindow` and deep-render pipelines for Quire, Ledger, and Lectern, fully meeting Office 2003 fidelity and PySide6 Qt standards.

---

## Architecture & Interfaces

### 1. Base Class: `BaseOfficeWindow` (`src/atboffice/ui/shell/base_window.py`)
Add universal methods:
- `print_document(printer: QPrinter | None = None) -> bool`:
  - When `printer` is not provided:
    - Instantiates `QPrinter(QPrinter.PrinterMode.HighResolution)`.
    - In non-interactive test mode (e.g. `os.environ.get("PYTEST_CURRENT_TEST")`), skips `QPrintDialog.exec()` and directly renders.
    - Otherwise, opens `QPrintDialog(printer, self)`. If accepted, invokes `self.render_to_printer(printer)`.
  - When `printer` is provided: directly executes `self.render_to_printer(printer)`.
  - Returns boolean indicating success.
- `print_preview(printer: QPrinter | None = None) -> bool`:
  - Instantiates `QPrinter(QPrinter.PrinterMode.HighResolution)`.
  - Creates `QPrintPreviewDialog(printer, self)`.
  - Localizes dialog title (`safe_tr("打印预览 — {app_name}")`).
  - Connects `dialog.paintRequested.connect(self.render_to_printer)`.
  - In non-interactive test mode, invokes `render_to_printer(printer)` directly without blocking modal dialog.
  - Returns `True`.
- `export_pdf(output_path: str | Path | None = None) -> bool`:
  - If `output_path` is None: prompts user via `QFileDialog.getSaveFileName` for target PDF path.
  - Sets up `QPrinter(QPrinter.PrinterMode.HighResolution)` with `OutputFormat.PdfFormat` and `setOutputFileName(str(target))`.
  - Invokes `self.render_to_printer(printer)`.
  - Error handling: catches file I/O or permissions issues, reports via `QMessageBox.critical`, returns boolean status.
- Virtual rendering hook:
  - `def render_to_printer(self, printer: QPrinter) -> None`: Subclasses override this to render document pages onto the printer's `QPainter`.

### 2. Quire (Word Processor) Print Pipeline (`QuireWindow`)
- Wire actions in `QuireWindow.__init__`:
  - `self.action_registry.set_handler("print", self.print_document)`
  - `self.action_registry.set_handler("printPreview", self.print_preview)`
- Override `render_to_printer(self, printer: QPrinter)`:
  - Triggers pagination if document is unpaginated: `self.editor.canvas_view._ensure_paginated()`.
  - Inspects document section page setup: page size (e.g., A4: 595.28 x 841.89 pt), orientation.
  - Sets `printer.setPageOrientation(section.orientation)`.
  - Initializes `painter = QPainter(printer)`.
  - Iterates over each `Page` in `self.editor.canvas_view._pages`:
    - If `idx > 0`: `printer.newPage()`.
    - Renders page headers/footers with dynamic page numbers.
    - Renders paragraph text portions, fonts, baseline alignment, and underline/strikethrough.
    - Renders tables, cell background fills, borders, and cell paragraphs.
    - Renders mathematical formulas / OMML blocks.
    - Renders tab leader lines.
  - Concludes with `painter.end()`.

### 3. Ledger (Spreadsheet) Print Pipeline (`LedgerWindow`)
- Wire actions in `LedgerWindow.__init__`:
  - `self.action_registry.set_handler("print", self.print_workbook)`
  - `self.action_registry.set_handler("printPreview", self.print_preview)`
  - Implement `print_workbook()` to delegate to `self.print_document()`.
- Override `render_to_printer(self, printer: QPrinter)`:
  - Computes active sheet used range (`min_r`, `min_c`, `max_r`, `max_c`) from cell data and drawings.
  - Computes printable rectangle in points from printer: `rect = printer.pageRect(QPrinter.Unit.Point)`.
  - Calculates horizontal and vertical page cuts (column spans and row spans), honoring paper margins.
  - Supports repeating header rows (`rows_to_repeat_at_top`, default row 0 if multiple pages down).
  - Supports gridlines printing toggle (`show_gridlines = True`).
  - Initializes `painter = QPainter(printer)`.
  - Iterates through page tiles `(col_span, row_span)`:
    - If page index > 0: `printer.newPage()`.
    - Renders repeating header rows at the top of the page.
    - Renders cell backgrounds, borders, numbers, and text with clipping and alignment.
    - Renders gridlines across active columns/rows.
    - Renders header/footer text (Sheet name, Page X of Y, Date/Time).
    - Renders drawings and charts located within page boundaries.
  - Concludes with `painter.end()`.

### 4. Lectern (Presentation) Print Pipeline (`LecternWindow`)
- Wire actions in `LecternWindow.__init__`:
  - `self.action_registry.set_handler("print", self.print_document)`
  - `self.action_registry.set_handler("printPreview", self.print_preview)`
- Override `render_to_printer(self, printer: QPrinter)`:
  - Supports print modes:
    1. **Slides Mode** (default): Each slide maps to one page, vector rendered via `QPainter` or `SlideScene.render()`.
    2. **Handouts Mode (3 slides per page)**: 3 slide thumbnails stacked on the left, with ruled horizontal note lines on the right for audience annotations.
    3. **Grayscale / Color** support.
  - Iterates over `self.presentation_view.presentation.slides`:
    - Handles pagination with `printer.newPage()`.
    - Preserves aspect ratio and centers slide on printable page area.
    - Renders shapes, texts, lines, fills, charts in vector precision.

---

## Edge Case Analysis & Robustness
1. **Empty Document**: Handled gracefully by emitting a blank page or single empty sheet without division-by-zero or indexing exceptions.
2. **Printer Invalidation / Headless Environments**: Automated unit tests execute with mock or PDF printers without requiring GUI system dialogs.
3. **File System Failures**: PDF export handles missing parent directories, read-only locations, and invalid paths with user-friendly error alerts.
4. **Vector Fidelity**: Uses native `QPainter.drawText`, `drawLine`, `drawRect`, and Qt font metrics directly to target device, guaranteeing searchable, crisp vector PDF output.
5. **i18n Localization**: 100% of UI titles, menu actions, tooltips, dialog prompts, and header/footer strings use `safe_tr`.

---

## Verification Plan
1. Unit tests: `tests/ui/test_printing.py` covering:
   - `test_base_window_print_interface`: verifies `print_document`, `print_preview`, and `export_pdf` methods.
   - `test_quire_print_and_pdf_export`: tests Quire document pagination, page rendering to PDF, and vector text output.
   - `test_ledger_print_and_pdf_export`: tests Ledger sheet pagination, repeat headers, gridlines, and cell rendering to PDF.
   - `test_lectern_print_and_pdf_export`: tests Lectern slide rendering to PDF, handouts mode (3 slides with note lines).
   - `test_action_wiring`: verifies toolbar and menu action triggering for all 3 apps.
2. Feature matrix check:
   - Update `docs/clone/features.csv` entry for `Document Printing and Print Preview Subsystem` to `yes`.
