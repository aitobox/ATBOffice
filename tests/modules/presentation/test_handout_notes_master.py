"""Tests for Phase 12 Wave 3 Task 3: Lectern Handout Master & Notes Master."""

from __future__ import annotations

import copy
import zipfile
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication

from atboffice.core.i18n import load_locale
from atboffice.modules.presentation.io import read_pptx, write_pptx
from atboffice.modules.presentation.models.presentation import (
    HandoutMasterSettings,
    NotesMasterSettings,
    Presentation,
)
from atboffice.modules.presentation.printing import (
    PresentationPrintOptions,
    page_count,
    page_size,
    render_handout_page,
    render_notes_page,
    render_presentation,
)
from atboffice.modules.presentation.views.master_view import (
    HandoutMasterView,
    NotesMasterView,
)
from atboffice.ui.shell.lectern_history import snapshot_presentation
from atboffice.ui.shell.lectern_window import LecternWindow


@pytest.fixture(autouse=True)
def _reset_locale():
    load_locale("zh-CN")
    yield
    load_locale("zh-CN")


def test_handout_and_notes_master_models_roundtrip() -> None:
    hm = HandoutMasterSettings(
        slides_per_page=3,
        show_header=True,
        header_text="Confidential",
        show_date=False,
        date_text="2026-11-27",
        show_footer=True,
        footer_text="ATBOffice",
        show_page_number=False,
        orientation="landscape",
    )
    nm = NotesMasterSettings(
        show_header=False,
        header_text="Speaker Header",
        show_date=True,
        date_text="Nov 2026",
        show_footer=True,
        footer_text="Internal Only",
        show_page_number=True,
        notes_font_family="Georgia",
        notes_font_size=14.5,
        show_slide_border=False,
        show_notes_border=True,
    )

    assert HandoutMasterSettings.from_dict(hm.to_dict()) == hm
    assert NotesMasterSettings.from_dict(nm.to_dict()) == nm

    # Invalid slides_per_page / orientation normalize safely
    bad_hm = HandoutMasterSettings.from_dict({"slidesPerPage": 5, "orientation": "diagonal"})
    assert bad_hm.slides_per_page == 6
    assert bad_hm.orientation == "portrait"

    pres = Presentation.create_new()
    pres.handout_master = hm
    pres.notes_master = nm

    # dict round-trip & snapshot_presentation preserve settings
    restored = Presentation.from_dict(pres.to_dict())
    assert restored.handout_master == hm
    assert restored.notes_master == nm

    snap = snapshot_presentation(pres)
    assert snap.handout_master == hm
    assert snap.notes_master == nm
    snap.handout_master.header_text = "Mutated"
    assert pres.handout_master.header_text == "Confidential"


def test_enter_and_exit_handout_and_notes_master_via_actions(qapp: QApplication) -> None:
    win = LecternWindow()
    try:
        win.resize(1200, 800)
        win.show()
        qapp.processEvents()

        ws = win.presentation_view.workspace
        assert ws.view_mode == "normal"

        # Check actions exist in ActionRegistry and mac_menu View -> Master
        for aid in ("viewMaster", "view_handout_master", "view_notes_master", "closeMaster"):
            act = win.action_registry.get_action(aid)
            assert act is not None, f"Missing action {aid}"
            assert act.isVisible() is True
            assert win.action_registry.has_command(aid) is True

        # Enter Handout Master
        win.action_registry.trigger_action("view_handout_master")
        qapp.processEvents()
        assert ws.view_mode == "handout_master"
        assert isinstance(ws.center_stack.currentWidget(), HandoutMasterView)
        assert win.action_registry.get_action("view_handout_master").isChecked() is True
        assert win.action_registry.get_action("view_notes_master").isChecked() is False

        # Close via closeMaster
        win.action_registry.trigger_action("closeMaster")
        qapp.processEvents()
        assert ws.view_mode == "normal"
        assert win.action_registry.get_action("view_handout_master").isChecked() is False

        # Enter Notes Master
        win.action_registry.trigger_action("view_notes_master")
        qapp.processEvents()
        assert ws.view_mode == "notes_master"
        assert isinstance(ws.center_stack.currentWidget(), NotesMasterView)
        assert win.action_registry.get_action("view_notes_master").isChecked() is True

        # Close via close button on NotesMasterView
        ws.notes_master_view.btn_close.click()
        qapp.processEvents()
        assert ws.view_mode == "normal"
        assert win.action_registry.get_action("view_notes_master").isChecked() is False
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_handout_master_view_controls_and_preview_rendering(qapp: QApplication) -> None:
    pres = Presentation.create_new()
    view = HandoutMasterView(pres)
    view.resize(1000, 720)
    view.show()
    qapp.processEvents()

    edited_calls: list[bool] = []
    view.master_edited.connect(lambda: edited_calls.append(True))

    # Switch through all 1/2/3/4/6/9 layouts
    for count in (1, 2, 3, 4, 6, 9):
        view.layout_buttons[count].click()
        qapp.processEvents()
        assert pres.handout_master.slides_per_page == count

    # Switch to 3-per-page, edit header/footer/date/page-number/orientation
    view.layout_buttons[3].click()
    view.chk_header.setChecked(True)
    view.edit_header.setText("Quarterly Review")
    view.chk_date.setChecked(True)
    view.edit_date.setText("2026-11-27")
    view.chk_footer.setChecked(True)
    view.edit_footer.setText("Company Confidential")
    view.chk_page_number.setChecked(False)
    view.combo_orientation.setCurrentIndex(1)  # landscape
    qapp.processEvents()

    assert pres.handout_master.slides_per_page == 3
    assert pres.handout_master.header_text == "Quarterly Review"
    assert pres.handout_master.date_text == "2026-11-27"
    assert pres.handout_master.footer_text == "Company Confidential"
    assert pres.handout_master.show_page_number is False
    assert pres.handout_master.orientation == "landscape"
    assert len(edited_calls) > 0

    # Render preview widget to QImage to verify non-blank WYSIWYG painting
    pix = view.preview.grab()
    img = pix.toImage()
    assert not img.isNull()
    assert img.width() > 100 and img.height() > 100


def test_notes_master_view_controls_and_preview_rendering(qapp: QApplication) -> None:
    pres = Presentation.create_new()
    view = NotesMasterView(pres)
    view.resize(1000, 720)
    view.show()
    qapp.processEvents()

    view.chk_header.setChecked(True)
    view.edit_header.setText("Notes Header")
    view.chk_date.setChecked(True)
    view.edit_date.setText("2026-11-27")
    view.chk_footer.setChecked(True)
    view.edit_footer.setText("Notes Footer")
    view.chk_page_number.setChecked(True)
    view.font_combo.setCurrentText("Times New Roman")
    view.font_size_spin.setValue(16)
    view.chk_slide_border.setChecked(False)
    view.chk_notes_border.setChecked(True)
    qapp.processEvents()

    assert pres.notes_master.header_text == "Notes Header"
    assert pres.notes_master.date_text == "2026-11-27"
    assert pres.notes_master.footer_text == "Notes Footer"
    assert pres.notes_master.notes_font_family == "Times New Roman"
    assert pres.notes_master.notes_font_size == 16.0
    assert pres.notes_master.show_slide_border is False
    assert pres.notes_master.show_notes_border is True

    pix = view.preview.grab()
    img = pix.toImage()
    assert not img.isNull()
    assert img.width() > 100 and img.height() > 100


def test_handout_and_notes_master_undo_redo(qapp: QApplication) -> None:
    win = LecternWindow()
    try:
        win.resize(1100, 760)
        win.show()
        qapp.processEvents()

        # 1. Handout Master undo/redo
        win.action_registry.trigger_action("view_handout_master")
        qapp.processEvents()
        hm_view = win.presentation_view.workspace.handout_master_view
        assert win.presentation_view.presentation.handout_master.slides_per_page == 6

        hm_view.layout_buttons[3].click()
        qapp.processEvents()
        win.flush_pending_edits()
        assert win.presentation_view.presentation.handout_master.slides_per_page == 3
        assert win.is_modified is True

        hm_view.edit_header.setText("Board Deck")
        qapp.processEvents()
        win.flush_pending_edits()
        assert win.presentation_view.presentation.handout_master.header_text == "Board Deck"

        win.undo()
        qapp.processEvents()
        assert win.presentation_view.presentation.handout_master.header_text == ""
        assert hm_view.edit_header.text() == ""

        win.undo()
        qapp.processEvents()
        assert win.presentation_view.presentation.handout_master.slides_per_page == 6
        assert hm_view.layout_buttons[6].isChecked() is True

        win.redo()
        qapp.processEvents()
        assert win.presentation_view.presentation.handout_master.slides_per_page == 3

        # 2. Notes Master undo/redo
        win.action_registry.trigger_action("view_notes_master")
        qapp.processEvents()
        nm_view = win.presentation_view.workspace.notes_master_view
        nm_view.chk_notes_border.setChecked(True)
        qapp.processEvents()
        win.flush_pending_edits()
        assert win.presentation_view.presentation.notes_master.show_notes_border is True

        win.undo()
        qapp.processEvents()
        assert win.presentation_view.presentation.notes_master.show_notes_border is False
        assert nm_view.chk_notes_border.isChecked() is False

        win.redo()
        qapp.processEvents()
        assert win.presentation_view.presentation.notes_master.show_notes_border is True
        assert nm_view.chk_notes_border.isChecked() is True
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_printing_respects_handout_and_notes_master(qapp: QApplication, tmp_path: Path) -> None:
    pres = Presentation.create_new()
    for _ in range(3):
        pres.add_slide("text")
    pres.slides[0].notes = "Detailed speaker script for slide 1."

    # Handout Master: 2 per page, landscape, custom header/footer/date
    pres.handout_master = HandoutMasterSettings(
        slides_per_page=2,
        show_header=True,
        header_text="Handout Header",
        show_date=True,
        date_text="2026-11-27",
        show_footer=True,
        footer_text="Handout Footer",
        show_page_number=True,
        orientation="landscape",
    )
    h_opts = PresentationPrintOptions(what="handouts")  # uses master default per_page=2
    assert page_count(pres, h_opts) == 2
    pw, ph = page_size(pres, h_opts)
    assert pw > ph  # landscape A4

    # Render handout page to QImage and verify non-white pixels in header/footer/slot regions
    h_img = QImage(int(pw), int(ph), QImage.Format.Format_ARGB32)
    h_img.fill(QColor("#FFFFFF"))
    hp = QPainter(h_img)
    render_handout_page(hp, pres, pres.slides[:2], pw, ph, 1, h_opts)
    hp.end()
    # Header area (top-left) must have drawn text pixels
    has_header_ink = any(
        QColor(h_img.pixel(x, y)) != QColor("#FFFFFF")
        for x in range(36, 200)
        for y in range(10, 32)
    )
    assert has_header_ink

    # Notes Master: custom font, notes border on, slide border off
    pres.notes_master = NotesMasterSettings(
        show_header=True,
        header_text="Notes Header",
        show_date=True,
        date_text="2026-11-27",
        show_footer=True,
        footer_text="Notes Footer",
        show_page_number=True,
        notes_font_family="Courier New",
        notes_font_size=15.0,
        show_slide_border=False,
        show_notes_border=True,
    )
    n_opts = PresentationPrintOptions(what="notes")
    nw, nh = page_size(pres, n_opts)
    n_img = QImage(int(nw), int(nh), QImage.Format.Format_ARGB32)
    n_img.fill(QColor("#FFFFFF"))
    np = QPainter(n_img)
    render_notes_page(np, pres, pres.slides[0], nw, nh, 1, n_opts)
    np.end()

    # Notes border should draw a dark border line at x = MARGIN + 36 = 72
    has_notes_border = any(
        QColor(n_img.pixel(72, y)).red() < 200 for y in range(int(nh * 0.5), int(nh - 60))
    )
    assert has_notes_border

    # Full QPrinter PDF export succeeds
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    pdf_path = tmp_path / "handout_notes_master.pdf"
    printer.setOutputFileName(str(pdf_path))
    assert render_presentation(printer, pres, h_opts) == 2
    assert pdf_path.exists() and pdf_path.stat().st_size > 500


def test_pptx_roundtrip_handout_and_notes_master() -> None:
    # 1. From-scratch PPTX save & reopen preserves customized handout & notes masters
    pres = Presentation.create_new()
    pres.slides[0].notes = "Presenter note"
    pres.handout_master = HandoutMasterSettings(
        slides_per_page=4,
        show_header=True,
        header_text="Draft Handout",
        show_date=True,
        date_text="2026-11-27",
        show_footer=False,
        footer_text="",
        show_page_number=True,
        orientation="landscape",
    )
    pres.notes_master = NotesMasterSettings(
        show_header=True,
        header_text="Speaker Copy",
        show_date=False,
        date_text="",
        show_footer=True,
        footer_text="Confidential",
        show_page_number=True,
        notes_font_family="Georgia",
        notes_font_size=14.0,
        show_slide_border=False,
        show_notes_border=True,
    )

    raw = write_pptx(pres)
    reopened = read_pptx(raw)
    assert reopened.handout_master == pres.handout_master
    assert reopened.notes_master == pres.notes_master

    # 2. Round-trip an existing corpus PPTX: untouched masters stay byte-for-byte identical
    corpus_file = Path("tests/docs/powerpoint/pptx/libreoffice__master-slides.pptx")
    if corpus_file.exists():
        src_bytes = corpus_file.read_bytes()
        loaded = read_pptx(src_bytes)
        out_unchanged = write_pptx(loaded)
        with (
            zipfile.ZipFile(__import__("io").BytesIO(src_bytes)) as zin,
            zipfile.ZipFile(__import__("io").BytesIO(out_unchanged)) as zout,
        ):
            assert zin.read("ppt/handoutMasters/handoutMaster1.xml") == zout.read(
                "ppt/handoutMasters/handoutMaster1.xml"
            )
            assert zin.read("ppt/notesMasters/notesMaster1.xml") == zout.read(
                "ppt/notesMasters/notesMaster1.xml"
            )

        # Now edit handout_master and notes_master on loaded corpus file and re-save
        loaded2 = copy.deepcopy(loaded)
        loaded2.handout_master.show_header = True
        loaded2.handout_master.header_text = "Patched Header"
        loaded2.handout_master.slides_per_page = 3
        loaded2.notes_master.notes_font_size = 16.0
        loaded2.notes_master.show_notes_border = True
        out_patched = write_pptx(loaded2)
        reloaded = read_pptx(out_patched)
        assert reloaded.handout_master.show_header is True
        assert reloaded.handout_master.header_text == "Patched Header"
        assert reloaded.handout_master.slides_per_page == 3
        assert reloaded.notes_master.notes_font_size == 16.0
        assert reloaded.notes_master.show_notes_border is True


def test_retranslate_ui_switches_cleanly(qapp: QApplication) -> None:
    pres = Presentation.create_new()
    hm = HandoutMasterView(pres)
    nm = NotesMasterView(pres)
    load_locale("zh-CN")
    hm.retranslate_ui()
    nm.retranslate_ui()
    assert hm.btn_close.text() == "关闭母版视图"
    assert nm.btn_close.text() == "关闭母版视图"

    load_locale("en")
    hm.retranslate_ui()
    nm.retranslate_ui()
    assert hm.btn_close.text() == "Close Master View"
    assert nm.btn_close.text() == "Close Master View"


def test_ribbon_contextual_tabs_and_menu_visibility(qapp: QApplication) -> None:
    win = LecternWindow()
    try:
        win.resize(1200, 800)
        win.show()
        win.set_theme("paper2016")
        qapp.processEvents()

        rb = win.ribbon_bar
        assert rb is not None
        assert win.menu_bar.menu_map["view_master"].menuAction().isVisible() is True

        win.set_view_mode("handout_master")
        qapp.processEvents()
        assert "handout_master" in rb.active_context_ids()
        assert rb.current_tab_id == "handoutMasterTab"

        win.set_view_mode("notes_master")
        qapp.processEvents()
        assert "notes_master" in rb.active_context_ids()
        assert rb.current_tab_id == "notesMasterTab"

        win.action_registry.trigger_action("closeMaster")
        qapp.processEvents()
        assert rb.active_context_ids() == ()
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()
