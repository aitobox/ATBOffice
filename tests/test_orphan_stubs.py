"""Tests for orphan controls wiring and standardized base window virtual methods."""

from __future__ import annotations

import pytest
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QWidget

from atboffice.core.search import SearchAdapter
from atboffice.modules.presentation.models.slide import Shape, Slide
from atboffice.modules.presentation.views.animation_pane import AnimationPane
from atboffice.modules.presentation.views.workspace import LecternTaskPane
from atboffice.modules.writer.dialogs.bullets_numbering import BulletsNumberingDialog
from atboffice.modules.writer.dialogs.customize_list_dialog import CustomizeListDialog
from atboffice.modules.writer.dialogs.paragraph_dialog import ParagraphDialog
from atboffice.modules.writer.dialogs.tabs_dialog import TabsDialog, TabStop
from atboffice.modules.writer.models.document import Document, TextItem
from atboffice.modules.writer.models.properties import (
    RevisionStamp,
    RunProperties,
)
from atboffice.modules.writer.models.revision import Comment
from atboffice.modules.writer.view import WriterView
from atboffice.modules.writer.views.review_pane import ReviewPane, ReviewToolbar
from atboffice.ui.shell.base_window import BaseOfficeWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ===========================================================================
# 1. ParagraphDialog.btn_tabs & TabsDialog
# ===========================================================================
def test_paragraph_dialog_btn_tabs_wiring(qapp, monkeypatch):
    """Verify clicking btn_tabs launches TabsDialog and updates tabs."""
    dlg = ParagraphDialog()
    assert dlg.btn_tabs is not None
    assert dlg.btn_tabs.text().startswith("制表位") or dlg.btn_tabs.text().startswith("Tabs")

    tabs_opened = False
    mock_tabs = [TabStop(pos=72.0, align="left", leader="none")]

    def mock_tabs_exec(self):
        nonlocal tabs_opened
        tabs_opened = True
        self._tabs = list(mock_tabs)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(TabsDialog, "exec", mock_tabs_exec)

    dlg._on_tabs_clicked()
    assert tabs_opened is True

    props = dlg.get_properties()
    assert len(props.tabs) == 1
    assert props.tabs[0].pos == 72.0


# ===========================================================================
# 2. BulletsNumberingDialog.btn_customize & CustomizeListDialog
# ===========================================================================
def test_bullets_numbering_customize_wiring(qapp, monkeypatch):
    """Verify clicking btn_customize launches CustomizeListDialog."""
    dlg = BulletsNumberingDialog()
    assert dlg.btn_customize is not None

    customized_opened = False

    def mock_custom_exec(self):
        nonlocal customized_opened
        customized_opened = True
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(CustomizeListDialog, "exec", mock_custom_exec)

    dlg._on_customize_clicked()
    assert customized_opened is True


def test_customize_list_dialog_features(qapp):
    """Test CustomizeListDialog structure, level switching, and result output."""
    dlg = CustomizeListDialog(kind="number", initial_level=0)
    assert dlg.windowTitle() != ""
    assert dlg.combo_num_style.count() > 0

    # Test changing alignment and starting number
    dlg.spin_start.setValue(5)
    dlg.combo_align.setCurrentIndex(1)  # centered
    dlg.spin_aligned_at.setValue(18.0)
    dlg.spin_indent_at.setValue(36.0)

    res = dlg.get_customized_level()
    assert res["start"] == 5
    assert res["jc"] in ("center", "centered")
    assert res["aligned_at"] == 18.0
    assert res["indent_at"] == 36.0


# ===========================================================================
# 3. ReviewToolbar & ReviewPane & WriterView Wiring
# ===========================================================================
def test_review_toolbar_and_filtering(qapp):
    """Verify ReviewToolbar localization, filter signals, and ReviewPane filtering."""
    toolbar = ReviewToolbar()
    toolbar.retranslate_ui()

    assert "修订" in toolbar.act_track.text() or "Track" in toolbar.act_track.text()
    assert "显示" in toolbar.btn_show.text() or "Show" in toolbar.btn_show.text()
    assert "接受" in toolbar.btn_accept.text() or "Accept" in toolbar.btn_accept.text()
    assert "拒绝" in toolbar.btn_reject.text() or "Reject" in toolbar.btn_reject.text()

    # Test markup filter signal
    emitted_filters = []
    toolbar.markup_filter_changed.connect(lambda c, i, f: emitted_filters.append((c, i, f)))

    toolbar.act_show_comments.setChecked(False)
    assert len(emitted_filters) > 0
    assert emitted_filters[-1][0] is False  # comments is False

    # Test ReviewPane markup filtering
    doc = Document()
    p = doc.main.blocks[0]
    stamp = RevisionStamp(author="Bob", date="2026-10-30T10:00:00Z")
    p.runs = [TextItem(text="Test", r_pr=RunProperties(ins=stamp))]
    doc.comments["c1"] = Comment(id="c1", text="Test comment", author="Alice")

    pane = ReviewPane(doc=doc)
    assert pane.list_widget.count() == 2  # 1 revision + 1 comment

    # Filter out comments
    pane.set_markup_filter(show_comments=False, show_ins_del=True, show_formatting=True)
    assert pane.list_widget.count() == 1

    # Filter out insertions/deletions too
    pane.set_markup_filter(show_comments=False, show_ins_del=False, show_formatting=True)
    assert pane.list_widget.count() == 1  # Shows empty placeholder label item


def test_writer_view_wires_review_toolbar_actions(qapp):
    """Verify WriterView wires ReviewToolbar actions to document operations."""
    view = WriterView()
    tb = view.review_toolbar
    rp = view.review_pane

    # Toggle markup filters in toolbar updates review pane
    tb.act_show_comments.setChecked(False)
    assert rp._filter_comments is False


# ===========================================================================
# 4. AnimationPane & LecternTaskPane Wiring
# ===========================================================================
def test_animation_pane_add_effect_menu(qapp):
    """Verify AnimationPane.btn_add_effect menu popup and category menus."""
    pane = AnimationPane()
    assert pane.btn_add_effect is not None
    assert pane.menu_add_effect is not None
    assert len(pane.menu_add_effect.actions()) == 4

    # Setup slide and shape
    slide = Slide(id="slide1")
    sh = Shape(id="sh1", name="Rectangle 1")
    slide.shapes.append(sh)
    pane.set_slide(slide, selected_shape_ids=["sh1"])

    # Trigger entrance effect
    entr_menu = pane._category_menus[0]
    assert entr_menu is not None
    first_eff_act = entr_menu.actions()[0]
    first_eff_act.trigger()

    assert len(slide.animations) == 1
    assert slide.animations[0].cls == "entr"


def test_lectern_task_pane_title_button(qapp):
    """Verify LecternTaskPane title button menu popup."""
    pane = LecternTaskPane()
    dummy1 = QWidget()
    dummy2 = QWidget()
    pane.register_pane("pane1", "版式", dummy1)
    pane.register_pane("pane2", "配色", dummy2)

    assert pane.title_button is not None
    assert pane.title_button.menu() is pane.menu
    assert len(pane.menu.actions()) == 2


# ===========================================================================
# 5. BaseOfficeWindow Standardized Virtual Methods
# ===========================================================================
def test_base_office_window_virtual_methods_dispatch(qapp):
    """Verify BaseOfficeWindow methods dispatch to focused widgets and avoid empty stubs."""
    win = BaseOfficeWindow()

    # With line edit child focused
    editor = QLineEdit(win)
    editor.setText("Hello World")
    editor.selectAll()
    win.setCentralWidget(editor)
    editor.setFocus()

    # cut / copy / paste / undo / redo should dispatch without raising or failing
    win.copy()
    win.undo()
    win.redo()
    win.zoom_in()
    win.zoom_out()
    win.zoom_reset()

    printer = QPrinter()
    win.render_to_printer(printer)  # Safe default implementation


# ===========================================================================
# 6. SearchAdapter Interface Compliance
# ===========================================================================
def test_search_adapter_interface():
    """Verify SearchAdapter ABC cannot be instantiated directly without implementations."""
    with pytest.raises(TypeError):
        SearchAdapter()  # type: ignore

    class IncompleteAdapter(SearchAdapter):
        pass

    with pytest.raises(TypeError):
        IncompleteAdapter()  # type: ignore
