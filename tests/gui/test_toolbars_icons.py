"""GUI tests for toolbar 16x16 vector icon bindings and ToolButtonIconOnly styling."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QMainWindow

from atboffice.core.action_registry import ActionRegistry
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.lectern_toolbars import build_lectern_toolbars
from atboffice.ui.shell.ledger_toolbars import build_ledger_toolbars
from atboffice.ui.shell.quire_toolbars import build_quire_toolbars


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_office_toolbar_compact_defaults():
    _ensure_app()
    win = QMainWindow()
    tb = OfficeToolBar("Test", win)
    assert tb.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert tb.iconSize() == QSize(16, 16)


def test_color_picker_button_has_icon():
    _ensure_app()
    win = QMainWindow()
    tb = OfficeToolBar("Test", win)
    btn_font = ColorPickerButton(mode="font", parent=tb)
    assert not btn_font.icon().isNull()
    btn_fill = ColorPickerButton(mode="fill", parent=tb)
    assert not btn_fill.icon().isNull()


def test_quire_toolbars_have_icons():
    _ensure_app()
    win = QMainWindow()
    reg = ActionRegistry(win)
    toolbars = build_quire_toolbars(win, reg)

    assert "standard" in toolbars
    assert "formatting" in toolbars
    assert "drawing" in toolbars

    core_action_ids = [
        "new", "open", "save", "permission", "sendMail", "print", "printPreview",
        "spelling", "research", "cut", "copy", "paste", "painter", "undo", "redo",
        "hyperlink", "bold", "italic", "underline", "alignLeft", "alignCenter",
        "alignRight", "justify", "numbering", "bullets", "decIndent", "incIndent",
    ]

    for aid in core_action_ids:
        act = reg.get_action(aid)
        assert act is not None, f"Quire action {aid} not registered"
        assert not act.icon().isNull(), f"Quire action {aid} has null icon"
        assert bool(act.toolTip()), f"Quire action {aid} has empty tooltip"


def test_ledger_toolbars_have_icons():
    _ensure_app()
    win = QMainWindow()
    reg = ActionRegistry(win)
    toolbars = build_ledger_toolbars(win, reg)

    assert "standard" in toolbars
    assert "formatting" in toolbars
    assert "auditing" in toolbars

    core_action_ids = [
        "new", "open", "save", "print", "printPreview", "spelling",
        "cut", "copy", "paste", "formatPainter", "undo", "redo", "hyperlink",
        "sortAsc", "sortDesc", "chartWizard", "bold", "italic", "underline",
        "alignLeft", "alignCenter", "alignRight", "mergeCenter", "currencyStyle",
        "percentStyle", "commaStyle", "traceError", "tracePrecedents", "traceDependents",
    ]

    for aid in core_action_ids:
        act = reg.get_action(aid)
        assert act is not None, f"Ledger action {aid} not registered"
        assert not act.icon().isNull(), f"Ledger action {aid} has null icon"
        assert bool(act.toolTip()), f"Ledger action {aid} has empty tooltip"


def test_lectern_toolbars_have_icons():
    _ensure_app()
    win = QMainWindow()
    reg = ActionRegistry(win)
    toolbars = build_lectern_toolbars(win, reg)

    assert "standard" in toolbars
    assert "formatting" in toolbars
    assert "drawing" in toolbars

    core_action_ids = [
        "new", "open", "save", "print", "printPreview", "spelling",
        "cut", "copy", "paste", "formatPainter", "undo", "redo", "insertChart",
        "insertTable", "hyperlink", "bold", "italic", "underline", "shadowText",
        "alignLeft", "alignCenter", "alignRight", "numbering", "bullets",
        "growFont", "shrinkFont", "promote", "demote", "newSlide",
    ]

    for aid in core_action_ids:
        act = reg.get_action(aid)
        assert act is not None, f"Lectern action {aid} not registered"
        assert not act.icon().isNull(), f"Lectern action {aid} has null icon"
        assert bool(act.toolTip()), f"Lectern action {aid} has empty tooltip"
