"""Issue #442: printer geometry, in-window Print Preview and print fidelity (3 modules)."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest
from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QImage, QPageLayout, QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QDialog

from atboffice.modules.presentation.models.text import TextBody
from atboffice.modules.presentation.printing import (
    PresentationPrintOptions,
    page_count,
    paint_slide,
)
from atboffice.modules.spreadsheet.printing import header_footer
from atboffice.modules.spreadsheet.printing.layout import paginate
from atboffice.modules.spreadsheet.printing.setup import (
    SheetPrintSetup,
    get_print_setup,
    set_print_setup,
)
from atboffice.ui.printing.printer_setup import configure_page
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.mac_menu import MacMenuBar
from atboffice.ui.shell.quire_window import QuireWindow

DOCX = Path(__file__).resolve().parents[1] / "docs" / "word" / "docx"


def _pdf_printer(path: Path) -> QPrinter:
    pr = QPrinter(QPrinter.PrinterMode.HighResolution)
    pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    pr.setOutputFileName(str(path))
    return pr


def _pdf_pages(path: Path) -> list[tuple[float, float]]:
    doc = QPdfDocument()
    doc.load(str(path))
    return [
        (doc.pagePointSize(i).width(), doc.pagePointSize(i).height())
        for i in range(doc.pageCount())
    ]


def _raster(path: Path, page: int = 0, zoom: float = 1.0) -> QImage:
    doc = QPdfDocument()
    doc.load(str(path))
    size = doc.pagePointSize(page)
    return doc.render(page, QSize(int(size.width() * zoom), int(size.height() * zoom)))


def _count(img: QImage, pred, step: int = 2) -> int:
    n = 0
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            if pred(QColor(img.pixel(x, y))):
                n += 1
    return n


# ---------------------------------------------------------------- shared geometry
def test_configure_page_is_full_page_with_orientation(qtbot, tmp_path) -> None:
    pr = _pdf_printer(tmp_path / "geo.pdf")
    configure_page(pr, 960.0, 540.0)
    layout = pr.pageLayout()
    assert pr.fullPage()
    assert pr.resolution() == 72
    assert layout.orientation() == QPageLayout.Orientation.Landscape
    full = layout.fullRect(QPageLayout.Unit.Point)
    assert (round(full.width()), round(full.height())) == (960, 540)
    assert layout.margins(QPageLayout.Unit.Point).left() == 0
    configure_page(pr, 595.276, 841.89)
    assert pr.pageLayout().orientation() == QPageLayout.Orientation.Portrait


def test_in_window_preview_panel(qtbot) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()
    for _ in range(3):
        win.presentation_view.presentation.add_slide("text")
    panel = win.open_print_preview_panel()
    assert panel.isVisible() and panel.parent() is win
    assert panel.geometry() == win.centralWidget().geometry()
    qtbot.waitUntil(lambda: panel.page_count() == 4, timeout=3000)
    panel.toggle_magnifier()
    assert panel.btn_magnifier.isChecked()
    panel.set_view("all")
    closed: list[bool] = []
    panel.closed.connect(lambda: closed.append(True))
    panel.close_preview()
    assert closed and win._print_preview_panel is None


# ---------------------------------------------------------------- Lectern
def _deck(win: LecternWindow, n: int = 5) -> object:
    pres = win.presentation_view.presentation
    while len(pres.slides) < n:
        pres.add_slide("text")
    for i, slide in enumerate(pres.slides):
        for sh in slide.shapes:
            if sh.placeholder and sh.placeholder.type in ("title", "ctrTitle"):
                sh.text = TextBody.from_plain_text(f"Slide {i + 1}")
    return pres


@pytest.mark.parametrize(
    ("what", "per", "expected"),
    [
        ("slides", 0, 4),
        ("handouts", 1, 4),
        ("handouts", 2, 2),
        ("handouts", 3, 2),
        ("handouts", 4, 1),
        ("handouts", 6, 1),
        ("handouts", 9, 1),
        ("notes", 0, 4),
        ("outline", 0, 1),
    ],
)
def test_lectern_print_layouts(qtbot, tmp_path, what, per, expected) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    pres = _deck(win, 5)
    pres.slides[1].hidden = True
    win.print_options.what = what
    win.print_options.per_page = per or 6
    out = tmp_path / "deck.pdf"
    win.render_to_printer(_pdf_printer(out))
    pages = _pdf_pages(out)
    assert len(pages) == expected == page_count(pres, win.print_options)
    w, h = pages[0]
    if what == "slides":
        assert (round(w), round(h)) == (round(pres.w), round(pres.h))  # aspect + landscape
    else:
        assert h > w  # portrait A4
    win.print_options.print_hidden = True
    assert page_count(pres, win.print_options) >= expected


def test_lectern_prints_design_background_and_grayscale(qtbot) -> None:
    from atboffice.modules.presentation.models.designs import build_design
    from atboffice.modules.presentation.models.shape import Fill

    win = LecternWindow()
    qtbot.addWidget(win)
    pres = _deck(win, 1)
    design = build_design("default", pres.w, pres.h)
    design.bg = Fill.solid("#C00000")
    pres.designs = {design.id: design}
    pres.slides[0].design_id = design.id
    for mode, check in (
        ("color", lambda c: c.red() > 150 and c.green() < 60),
        ("grayscale", lambda c: c.red() == c.green() == c.blue()),
    ):
        img = QImage(320, 180, QImage.Format.Format_ARGB32)
        img.fill(QColor("#FFFFFF"))
        p = QPainter(img)
        paint_slide(p, pres.slides[0], pres, QRectF(0, 0, 320, 180), mode)
        p.end()
        assert check(QColor(img.pixel(10, 10))), mode


def test_lectern_preview_controls_change_options(qtbot) -> None:
    from PySide6.QtWidgets import QCheckBox, QComboBox

    win = LecternWindow()
    qtbot.addWidget(win)
    win.show()
    panel = win.open_print_preview_panel()
    what = panel.findChild(QComboBox, "printWhatCombo")
    color = panel.findChild(QComboBox, "printColorCombo")
    frame = panel.findChild(QCheckBox, "printFrameCheck")
    what.setCurrentIndex(what.findData("handouts:4"))
    color.setCurrentIndex(color.findData("bw"))
    frame.setChecked(True)
    opts = win.print_options
    assert (opts.what, opts.per_page, opts.color, opts.frame_slides) == ("handouts", 4, "bw", True)
    panel.close_preview()


def test_old_lectern_mode_keyword_still_works(qtbot, tmp_path) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    _deck(win, 4)
    out = tmp_path / "h.pdf"
    win.render_to_printer(_pdf_printer(out), mode="handouts")
    assert len(_pdf_pages(out)) == 1
    assert isinstance(win.print_options, PresentationPrintOptions)
    assert win.print_options.what == "slides"  # keyword does not leak into the options


# ---------------------------------------------------------------- Ledger
def _ledger(qtbot, rows: int = 80, cols: int = 12) -> LedgerWindow:
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.resize(1200, 800)
    win.show()
    sheet = win.spreadsheet_view.grid.model
    for r in range(rows):
        for c in range(cols):
            sheet.set_cell_value(r, c, f"R{r + 1}C{c + 1}")
    return win


def test_header_footer_codes(qtbot) -> None:
    assert header_footer.split_sections("&LLeft&CMid&RRight") == ("Left", "Mid", "Right")
    assert header_footer.split_sections("Plain") == ("", "Plain", "")
    text = header_footer.expand('&"Arial,Bold"&12Page &P of &N — &A &&', 2, 5, "Data")
    assert text == "Page 2 of 5 — Data &"


def test_ledger_pagination_titles_fit_area_breaks(qtbot) -> None:
    win = _ledger(qtbot)
    sheet = win.spreadsheet_view.grid.model
    st = SheetPrintSetup()
    base = paginate(sheet, st)
    assert len(base.pages) > 1
    st.title_rows = (0, 0)
    titled = paginate(sheet, st)
    assert titled.pages[0].repeat_rows is None
    assert all(p.repeat_rows == (0, 0) for p in titled.pages if p.rows[0] > 0)
    st.fit_to, st.fit_width, st.fit_height = True, 1, 1
    fit = paginate(sheet, st)
    assert len(fit.pages) == 1 and fit.scale < base.scale
    st = SheetPrintSetup(print_area=(0, 0, 9, 2))
    assert [(p.rows, p.cols) for p in paginate(sheet, st).pages] == [((0, 9), (0, 2))]
    sheet.view_state.row_breaks = [5]
    pages = paginate(sheet, st).pages
    assert [p.rows for p in pages] == [(0, 4), (5, 9)]
    st.print_area = (0, 0, 2_000_000, 1)  # whole columns clip to the used range
    assert paginate(sheet, st).area[2] == 79


def test_ledger_orientation_and_page_order(qtbot, tmp_path) -> None:
    win = _ledger(qtbot, 120, 20)
    sheet = win.spreadsheet_view.grid.model
    st = SheetPrintSetup(orientation="landscape")
    set_print_setup(sheet, st)
    out = tmp_path / "land.pdf"
    win.render_to_printer(_pdf_printer(out))
    w, h = _pdf_pages(out)[0]
    assert w > h
    down = paginate(sheet, st).pages
    st.page_order = "over_then_down"
    over = paginate(sheet, st).pages
    assert down[1].cols == down[0].cols and over[1].rows == over[0].rows


def test_ledger_print_renders_merges_fills_and_drawings(qtbot, tmp_path) -> None:
    from atboffice.modules.spreadsheet.views.object_layer import (
        AnchorType,
        CellAnchorPoint,
        FloatingObject,
    )

    win = _ledger(qtbot, 10, 4)
    sheet = win.spreadsheet_view.grid.model
    cell = sheet.ensure_cell(0, 0)
    cell.bg_color = "#00B050"
    sheet.merges.append((2, 0, 3, 2))
    obj = FloatingObject(
        id=1,
        kind="rect",
        anchor_type=AnchorType.TWO_CELL,
        from_point=CellAnchorPoint(row=5, col=1),
        to_point=CellAnchorPoint(row=8, col=3),
    )
    obj.fill_color = "#FF0000"
    sheet.drawings.append(obj)
    out = tmp_path / "cells.pdf"
    win.render_to_printer(_pdf_printer(out))
    img = _raster(out)
    assert _count(img, lambda c: c.green() > 150 and c.red() < 60 and c.blue() < 120) > 20
    assert _count(img, lambda c: c.red() > 200 and c.green() < 60 and c.blue() < 60) > 20
    assert len(_pdf_pages(out)) == 1


def test_ledger_black_and_white_has_no_color(qtbot, tmp_path) -> None:
    win = _ledger(qtbot, 10, 4)
    sheet = win.spreadsheet_view.grid.model
    sheet.ensure_cell(0, 0).bg_color = "#FF0000"
    set_print_setup(sheet, SheetPrintSetup(black_white=True))
    out = tmp_path / "bw.pdf"
    win.render_to_printer(_pdf_printer(out))
    img = _raster(out)
    assert _count(img, lambda c: abs(c.red() - c.green()) > 40) == 0


def test_ledger_page_setup_dialog_and_menu(qtbot, monkeypatch) -> None:
    from atboffice.modules.spreadsheet.dialogs.page_setup_dialog import LedgerPageSetupDialog

    win = _ledger(qtbot, 5, 3)
    dlg = LedgerPageSetupDialog(SheetPrintSetup())
    qtbot.addWidget(dlg)
    dlg.rb_landscape.setChecked(True)
    dlg.rb_fit.setChecked(True)
    dlg.edit_area.setText("$A$1:$C$4")
    dlg.edit_title_rows.setText("$1:$1")
    dlg.combo_footer.setCurrentIndex(2)
    dlg._apply_preset("footer", 2)
    st = dlg.result_setup()
    assert (st.orientation, st.fit_to, st.print_area, st.title_rows) == (
        "landscape",
        True,
        (0, 0, 3, 2),
        (0, 0),
    )
    assert "&P" in st.footer
    dlg.edit_area.setText("A0:??")
    with pytest.raises(ValueError):
        dlg.result_setup()

    monkeypatch.setattr(LedgerPageSetupDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        LedgerPageSetupDialog, "result_setup", lambda self: SheetPrintSetup(gridlines=True)
    )

    def fake_accept(self) -> None:
        self.setup = self.result_setup()

    monkeypatch.setattr(LedgerPageSetupDialog, "accept", fake_accept)
    original_exec = LedgerPageSetupDialog.exec

    def exec_and_accept(self):
        self.accept()
        return original_exec(self)

    monkeypatch.setattr(LedgerPageSetupDialog, "exec", exec_and_accept)
    assert win.action_registry.trigger_action("pageSetup")
    assert get_print_setup(win.spreadsheet_view.grid.model).gridlines
    mb = win.findChild(MacMenuBar)
    assert mb.action_map["pageSetup"].isVisible()


def test_page_setup_menu_hidden_in_lectern(qtbot) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    assert not win.findChild(MacMenuBar).action_map["pageSetup"].isVisible()


def test_ledger_page_setup_xlsx_round_trip(qtbot, tmp_path) -> None:
    from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
    from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

    wb = WorkbookModel()
    sheet = wb.sheets[0]
    sheet.set_cell_value(0, 0, "x")
    st = SheetPrintSetup(
        orientation="landscape",
        paper="Letter",
        fit_to=True,
        fit_height=0,
        gridlines=True,
        headings=True,
        header="&L&A",
        footer="&C&P",
        first_page_number=3,
        page_order="over_then_down",
        black_white=True,
    )
    st.margins["left"] = 36.0
    set_print_setup(sheet, st)
    out = tmp_path / "ps.xlsx"
    write_xlsx(wb, out)
    xml = zipfile.ZipFile(out).read("xl/worksheets/sheet1.xml").decode()
    assert '<pageSetUpPr fitToPage="1"/>' in xml
    assert xml.index("<printOptions") < xml.index("<pageMargins") < xml.index("<pageSetup ")
    loaded = get_print_setup(read_xlsx(out).sheets[0])
    assert loaded.to_dict() == st.to_dict()


def test_ledger_preview_extras(qtbot) -> None:
    from PySide6.QtWidgets import QToolButton

    win = _ledger(qtbot, 5, 3)
    panel = win.open_print_preview_panel()
    margins = panel.findChild(QToolButton, "previewMarginsButton")
    margins.setChecked(True)
    assert win._preview_show_margins
    panel.findChild(QToolButton, "previewPageBreakButton").click()
    assert win.spreadsheet_view.grid._view_mode == "page_break"


# ---------------------------------------------------------------- Quire
def test_quire_prints_with_screen_painter(qtbot, tmp_path) -> None:
    src = DOCX / "openxml-sdk__bullet-complex.docx"
    if not src.exists():
        pytest.skip("fixture missing")
    win = QuireWindow(str(src))
    qtbot.addWidget(win)
    win.resize(1200, 900)
    win.show()
    out = tmp_path / "q.pdf"
    win.render_to_printer(_pdf_printer(out))
    pages = _pdf_pages(out)
    canvas = win.writer_view.canvas_view
    assert len(pages) == len(canvas.pagination.pages)
    first = canvas.pagination.pages[0]
    assert (round(pages[0][0]), round(pages[0][1])) == (round(first.width), round(first.height))
    # print mode is undone afterwards
    assert canvas.pt_to_px_ratio == pytest.approx(96.0 / 72.0)
    assert not canvas._printing


def test_quire_text_metrics_match_device(qtbot) -> None:
    """Words never overlap at printer resolutions (metrics follow the device)."""
    src = DOCX / "openxml-sdk__bullet-complex.docx"
    if not src.exists():
        pytest.skip("fixture missing")
    win = QuireWindow(str(src))
    qtbot.addWidget(win)
    win.show()
    canvas = win.writer_view.canvas_view
    page = canvas.pagination.pages[0]
    ink = []
    for dpi in (72, 200):
        img = QImage(
            int(page.width * dpi / 72), int(page.height * dpi / 72), QImage.Format.Format_ARGB32
        )
        img.fill(QColor("#FFFFFF"))
        dpm = int(round(dpi / 0.0254))
        img.setDotsPerMeterX(dpm)
        img.setDotsPerMeterY(dpm)
        p = QPainter(img)
        p.scale(dpi / 72, dpi / 72)
        canvas.render_page_to_painter(p, page)
        p.end()
        # right-most ink on the page, in points: overlapping/oversized text would push it
        xs = [
            x
            for x in range(0, img.width(), 2)
            if any(QColor(img.pixel(x, y)).black() > 100 for y in range(0, img.height(), 4))
        ]
        ink.append(max(xs) * 72 / dpi if xs else 0)
    assert ink[0] > 100
    assert ink[1] == pytest.approx(ink[0], abs=6.0)


def test_quire_landscape_section_page_size(qtbot, tmp_path) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)
    canvas = win.writer_view.canvas_view
    sect = canvas.doc.sect
    sect.pg_w, sect.pg_h, sect.orient = sect.pg_h, sect.pg_w, "landscape"
    canvas.set_document(canvas.doc)
    out = tmp_path / "land.pdf"
    win.render_to_printer(_pdf_printer(out))
    w, h = _pdf_pages(out)[0]
    assert w > h


def test_pdf_export_uses_same_renderer(qtbot, tmp_path) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    _deck(win, 2)
    out = tmp_path / "e.pdf"
    assert win.export_pdf(out)
    data = out.read_bytes()
    assert re.search(rb"/MediaBox \[0 0 960", data)
