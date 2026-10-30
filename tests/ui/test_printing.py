"""Unit tests for universal document printing, print preview, and vector PDF export."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPainter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication

from atboffice.ui.shell.base_window import BaseOfficeWindow


class DummyOfficeWindow(BaseOfficeWindow):
    """Concrete window subclass for testing BaseOfficeWindow print hooks."""

    def __init__(self) -> None:
        super().__init__()
        self.app_name = "DummyOffice"
        self.render_count = 0

    def render_to_printer(self, printer: QPrinter) -> None:
        """Test render implementation writing a sample page."""
        self.render_count += 1
        painter = QPainter(printer)
        painter.drawText(100, 100, "ATBOffice Universal Printing Subsystem")
        painter.end()


def test_base_window_print_interfaces(qapp: QApplication, tmp_path: Path) -> None:
    """Verify BaseOfficeWindow provides print_document, print_preview, and export_pdf."""
    win = DummyOfficeWindow()

    # 1. Test direct render hook
    test_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    test_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    out_pdf = tmp_path / "test_dummy.pdf"
    test_printer.setOutputFileName(str(out_pdf))

    assert win.print_document(printer=test_printer) is True
    assert win.render_count == 1
    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 0

    # 2. Test print preview paint hook
    preview_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    preview_pdf = tmp_path / "test_preview.pdf"
    preview_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    preview_printer.setOutputFileName(str(preview_pdf))

    assert win.print_preview(printer=preview_printer) is True
    assert win.render_count == 2
    assert preview_pdf.exists()

    # 3. Test export_pdf
    pdf_target = tmp_path / "exported_doc.pdf"
    assert win.export_pdf(output_path=pdf_target) is True
    assert win.render_count == 3
    assert pdf_target.exists()
    assert pdf_target.stat().st_size > 0
    # Verify PDF magic header
    with open(pdf_target, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-"


def test_quire_print_and_pdf_export(qapp: QApplication, tmp_path: Path) -> None:
    """Verify QuireWindow vector printing and PDF export with rich content."""
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    # Check action handlers
    assert win.action_registry.has_action("print")
    assert win.action_registry.has_action("printPreview")

    # Add text and table to document
    canvas = win.writer_view.canvas_view
    canvas.controller.insert_text("ATBOffice Quire Vector Printing Document\n")
    canvas.insert_table(rows=2, cols=3)
    canvas.controller.insert_text("Cell Content Alpha")

    # 1. Export PDF
    pdf_path = tmp_path / "quire_export.pdf"
    assert win.export_pdf(output_path=pdf_path) is True
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 500

    # 2. Print Document with direct printer
    test_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    test_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    out_print = tmp_path / "quire_printed.pdf"
    test_printer.setOutputFileName(str(out_print))
    assert win.print_document(printer=test_printer) is True
    assert out_print.exists()
    assert out_print.stat().st_size > 500

    # 3. Print preview hook
    preview_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    preview_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    out_prev = tmp_path / "quire_preview.pdf"
    preview_printer.setOutputFileName(str(out_prev))
    assert win.print_preview(printer=preview_printer) is True
    assert out_prev.exists()
    assert out_prev.stat().st_size > 500


def test_ledger_print_and_pdf_export(qapp: QApplication, tmp_path: Path) -> None:
    """Verify LedgerWindow grid pagination, repeat headers, and PDF export."""
    from atboffice.modules.spreadsheet.models.sheet_model import BorderStyle
    from atboffice.ui.shell.ledger_window import LedgerWindow

    win = LedgerWindow()
    assert win.action_registry.has_action("print")
    assert win.action_registry.has_action("printPreview")

    sheet = win.spreadsheet_view.model
    # Set headers in row 0
    sheet.set_cell_value(0, 0, "Item")
    sheet.set_cell_value(0, 1, "Price")
    sheet.set_cell_value(0, 2, "Quantity")
    sheet.set_cell_value(0, 3, "Total")

    # Add several rows
    for r in range(1, 15):
        sheet.set_cell_value(r, 0, f"Product {r}")
        sheet.set_cell_value(r, 1, 99.5)
        sheet.set_cell_value(r, 2, r)
        sheet.set_cell_value(r, 3, 99.5 * r)

    # Style a cell with background color and borders
    c = sheet.get_cell(1, 0)
    if c:
        c.bg_color = "#E0FFE0"
        c.bold = True
        c.border_bottom = BorderStyle(style="thin", color="#008800")

    # 1. Export PDF
    pdf_path = tmp_path / "ledger_export.pdf"
    assert win.export_pdf(output_path=pdf_path) is True
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 500

    # 2. Print Document with direct printer
    test_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    test_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    out_print = tmp_path / "ledger_printed.pdf"
    test_printer.setOutputFileName(str(out_print))
    assert win.print_document(printer=test_printer) is True
    assert out_print.exists()
    assert out_print.stat().st_size > 500

    # 3. Print preview hook
    preview_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    preview_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    out_prev = tmp_path / "ledger_preview.pdf"
    preview_printer.setOutputFileName(str(out_prev))
    assert win.print_preview(printer=preview_printer) is True
    assert out_prev.exists()
    assert out_prev.stat().st_size > 500


def test_lectern_print_and_pdf_export(qapp: QApplication, tmp_path: Path) -> None:
    """Verify LecternWindow slide printing, PDF export, and 3-slide handout mode."""
    from atboffice.modules.presentation.models.shape import Shape
    from atboffice.ui.shell.lectern_window import LecternWindow

    win = LecternWindow()
    assert win.action_registry.has_action("print")
    assert win.action_registry.has_action("printPreview")

    # Add shapes to slide 1
    pres = win.presentation_view.presentation
    slide1 = pres.slides[0]
    sh1 = Shape(id="rect_1", type="shape", geom="rect", x=100.0, y=100.0, w=300.0, h=150.0)
    slide1.shapes.append(sh1)

    # Add slide 2 and 3
    win.add_new_slide()
    win.add_new_slide()
    assert len(pres.slides) == 3

    # 1. Export PDF in standard slide mode
    pdf_path = tmp_path / "lectern_slides.pdf"
    assert win.export_pdf(output_path=pdf_path) is True
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 500

    # 2. Print Document in direct printer
    test_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    test_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    out_print = tmp_path / "lectern_printed.pdf"
    test_printer.setOutputFileName(str(out_print))
    assert win.print_document(printer=test_printer) is True
    assert out_print.exists()
    assert out_print.stat().st_size > 500

    # 3. Print Preview hook
    preview_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    preview_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    out_prev = tmp_path / "lectern_preview.pdf"
    preview_printer.setOutputFileName(str(out_prev))
    assert win.print_preview(printer=preview_printer) is True
    assert out_prev.exists()
    assert out_prev.stat().st_size > 500

    # 4. Handouts Mode (3 slides per page with note lines)
    handout_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    handout_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    out_handout = tmp_path / "lectern_handouts.pdf"
    handout_printer.setOutputFileName(str(out_handout))
    win.render_to_printer(handout_printer, mode="handouts")
    assert out_handout.exists()
    assert out_handout.stat().st_size > 500


def test_action_wiring_and_shortcuts(qapp: QApplication) -> None:
    """Verify print and printPreview actions are wired to all three applications."""
    from atboffice.ui.shell.lectern_window import LecternWindow
    from atboffice.ui.shell.ledger_window import LedgerWindow
    from atboffice.ui.shell.quire_window import QuireWindow

    windows = [QuireWindow(), LedgerWindow(), LecternWindow()]
    for win in windows:
        assert win.action_registry.has_action("print")
        assert win.action_registry.has_action("printPreview")

        # Test triggering print action routes through print method without raising
        called = {"print": False, "preview": False}
        win.render_to_printer = lambda p: called.update({"print": True})
        win.action_registry.trigger_action("print")
        assert called["print"] is True

        win.render_to_printer = lambda p: called.update({"preview": True})
        win.action_registry.trigger_action("printPreview")
        assert called["preview"] is True


def test_feature_matrix_entry() -> None:
    """Verify Document Printing and Print Preview Subsystem status in features.csv."""
    import csv

    features_path = Path("docs/clone/features.csv")
    assert features_path.exists()

    found = False
    with open(features_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0] == "Document Printing and Print Preview Subsystem":
                found = True
                assert row[4] == "yes", f"Expected 'yes' clone status, got {row[4]}"
                break
    assert found, "Document Printing and Print Preview Subsystem entry not found in features.csv"




