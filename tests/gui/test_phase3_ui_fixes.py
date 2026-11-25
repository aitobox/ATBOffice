"""Visible UI fixes of the language-and-UI review phase."""

from __future__ import annotations

import collections
import copy

import pytest
from PySide6.QtGui import QAction, QPalette

from atboffice.ui.components.office_status_bar import OfficeStatusBar
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.ui.styles.luna_2003 import THEME_KEYS, luna_palette, theme_tokens

WINDOWS = (QuireWindow, LedgerWindow, LecternWindow)


@pytest.fixture
def make_window(qtbot, qapp):
    created = []

    def make(cls):
        win = cls()
        qtbot.addWidget(win)
        win.show()
        qapp.processEvents()
        created.append(win)
        return win

    yield make
    for win in created:
        win.set_modified(False)


@pytest.mark.parametrize("theme", THEME_KEYS)
def test_palette_is_light_in_every_theme(theme) -> None:
    pal = luna_palette(theme)
    assert pal.color(QPalette.ColorRole.Base).lightness() == 255
    assert pal.color(QPalette.ColorRole.Text).lightness() == 0
    assert pal.color(QPalette.ColorRole.WindowText).lightness() == 0
    assert pal.color(QPalette.ColorRole.Window).lightness() > 200
    assert theme_tokens(theme).key == theme


@pytest.mark.parametrize("cls", WINDOWS)
def test_every_editor_has_the_shared_status_bar(make_window, cls) -> None:
    win = make_window(cls)
    assert isinstance(win.statusBar(), OfficeStatusBar)
    assert win.statusBar().isVisible()


def test_quire_status_bar_shows_page_and_column(make_window) -> None:
    win = make_window(QuireWindow)
    win.update_status_fields()
    sb = win.status_bar
    assert sb.field("page_of").text() == "1/1"
    assert sb.field("col").text().endswith("1")


@pytest.mark.parametrize("cls", WINDOWS)
def test_document_has_the_keyboard_when_a_window_opens(make_window, cls) -> None:
    win = make_window(cls)
    win.focus_document()
    target = win.document_widget()
    focus = win.focusWidget()
    assert focus is target or target.isAncestorOf(focus)


@pytest.mark.parametrize("cls", WINDOWS)
def test_no_two_actions_share_a_shortcut(make_window, cls) -> None:
    win = make_window(cls)
    owners: dict[str, set[int]] = collections.defaultdict(set)
    for action in win.findChildren(QAction):
        for seq in action.shortcuts():
            if not seq.isEmpty():
                owners[seq.toString()].add(id(action))
    clashes = {key: len(ids) for key, ids in owners.items() if len(ids) > 1}
    assert clashes == {}


def test_lectern_slide_counter_counts_every_slide(make_window, qapp) -> None:
    from atboffice.modules.presentation.models.presentation import Presentation

    win = make_window(LecternWindow)
    pres = Presentation.create_new()
    extra = copy.deepcopy(pres.slides[0])
    extra.id = f"{extra.id}-2"
    pres.slides.append(extra)
    win.presentation_view.load_presentation(pres)
    qapp.processEvents()
    assert "2" in win.lbl_status_slide.text().split()[-1]


def test_lectern_drawing_tools_have_icons(make_window) -> None:
    win = make_window(LecternWindow)
    for aid in ("drawLine", "drawArrow", "drawRect", "drawOval", "textBox"):
        action = win.action_registry.get_action(aid)
        assert action is not None and not action.icon().isNull(), aid


def test_sheet_tabs_are_not_clipped(make_window) -> None:
    win = make_window(LedgerWindow)
    view = win.spreadsheet_view
    row = view.grid.horizontalScrollBar()
    assert row.height() >= view.sheet_tab_bar.height()


def test_lectern_thumbnails_fit_the_pane(make_window, qapp) -> None:
    win = make_window(LecternWindow)
    thumbs = win.presentation_view.workspace.thumbnail_list
    thumbs.resize(190, 400)
    qapp.processEvents()
    assert thumbs.iconSize().width() <= thumbs.width() - 30
