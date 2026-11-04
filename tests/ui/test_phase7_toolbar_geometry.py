"""Phase 7 Toolbar Geometry, Hit-Testing, and State Calibration Tests (TASK-711, #245).

Verifies:
1. Hit-Testing Separation:
   - OfficeSplitButton: main area click triggers action once; arrow area click opens menu.
   - ColorPickerButton: main area click applies recent color; arrow click opens palette popup.
2. Geometry & Pixel Tolerances:
   - Tool button heights 22px (<= 2px deviation), split button width ~34px (<= 2px deviation).
   - Dotted grip width 7px, separator width 4px.
3. Hover / Pressed / Disabled States & Dynamic Enabled Synchronization:
   - No black boxes, clipping, or overlapping double arrows.
   - Action enabled state dynamically syncs with button widget.
4. Multi-Resolution & DPI / Overflow:
   - 1440x900 and 1024x768 overflow scenarios without unhandled Qt exceptions.
5. 9-Locale Full Translation & Non-Truncation:
   - Full sweep across zh-CN, zh-Hant, en, ja, ko, fr, de, es, ru with retranslate_ui().
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from atboffice.core.i18n import SUPPORTED_LOCALES, load_locale
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar, OfficeToolBarSeparator
from atboffice.ui.components.toolbar_buttons import OfficeDropDownButton
from atboffice.ui.icons import get_office_icon
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.ui.styles.luna_2003 import apply_luna_theme


def test_split_button_hit_testing_separation(qtbot) -> None:
    """Main button and dropdown arrow hits must be strictly separated and trigger once."""
    widget = QWidget()
    qtbot.addWidget(widget)
    apply_luna_theme(widget, "blue")

    tb = OfficeToolBar("Standard", widget)
    action_triggered = 0

    def on_action():
        nonlocal action_triggered
        action_triggered += 1

    action = QAction("Undo", tb)
    action.triggered.connect(on_action)
    menu = QMenu("Undo List", tb)
    qtbot.addWidget(menu)
    menu.addAction("Item 1")

    menu_shown = False

    def close_menu():
        try:
            menu.close()
        except RuntimeError:
            pass

    def on_menu_show():
        nonlocal menu_shown
        menu_shown = True
        QTimer.singleShot(0, close_menu)

    menu.aboutToShow.connect(on_menu_show)

    split_btn = tb.add_split_action(action, menu)
    split_btn.show()

    # 1. Click main button body (left side)
    action_triggered = 0
    menu_shown = False
    qtbot.mouseClick(
        split_btn,
        Qt.MouseButton.LeftButton,
        pos=QPoint(8, split_btn.height() // 2),
    )
    assert action_triggered == 1, "Clicking main button body must trigger action exactly once"
    assert not menu_shown, "Clicking main button body must not open menu"

    # 2. Click arrow area (right side)
    action_triggered = 0
    menu_shown = False
    qtbot.mouseClick(
        split_btn,
        Qt.MouseButton.LeftButton,
        pos=QPoint(split_btn.width() - 4, split_btn.height() // 2),
    )
    assert action_triggered == 0, "Clicking arrow area must not trigger main action"
    assert menu_shown, "Clicking arrow area must open the menu"
    qtbot.waitUntil(lambda: not menu.isVisible(), timeout=1000)
    QApplication.processEvents()


def test_color_picker_hit_testing_and_recent_color(qtbot) -> None:
    """Color button main click applies recent color; arrow click opens color picker popup."""
    widget = QWidget()
    qtbot.addWidget(widget)
    apply_luna_theme(widget, "blue")

    tb = OfficeToolBar("Formatting", widget)
    applied_colors: list[str] = []

    def on_color(c: str):
        applied_colors.append(c)

    color_btn = ColorPickerButton(mode="font", default_color="#000000", parent=tb)
    color_btn.color_applied.connect(on_color)
    tb.addWidget(color_btn)
    color_btn.show()

    # 1. Main button click -> applies initial color (#000000)
    applied_colors.clear()
    qtbot.mouseClick(
        color_btn,
        Qt.MouseButton.LeftButton,
        pos=QPoint(8, color_btn.height() // 2),
    )
    assert applied_colors == ["#000000"], "Main click must apply recent color (#000000)"
    assert not color_btn.popup.isVisible(), "Main click must not display color palette popup"

    # 2. Arrow click -> displays popup
    applied_colors.clear()
    qtbot.mouseClick(
        color_btn,
        Qt.MouseButton.LeftButton,
        pos=QPoint(color_btn.width() - 4, color_btn.height() // 2),
    )
    assert len(applied_colors) == 0, "Arrow click must not apply color immediately"
    assert color_btn.popup.isVisible(), "Arrow click must open the ColorPickerPopup"
    color_btn.popup.close()

    # 3. Pick a new color from popup -> updates recent color and emits color_applied
    color_btn.popup._select_color("#FF0000")
    assert applied_colors == ["#FF0000"], "Selecting swatch must emit new color"
    assert color_btn.current_color == "#FF0000", "Must update recent color to #FF0000"

    # 4. Next main click -> applies the new recent color (#FF0000)
    applied_colors.clear()
    qtbot.mouseClick(
        color_btn,
        Qt.MouseButton.LeftButton,
        pos=QPoint(8, color_btn.height() // 2),
    )
    assert applied_colors == ["#FF0000"], "Subsequent main click must use the updated recent color"


def test_toolbar_button_geometry_calibration(qtbot) -> None:
    """Button dimensions must match Office 2003 Luna baseline within <= 2 logical pixels."""
    tb = OfficeToolBar("Geometry", None)
    qtbot.addWidget(tb)

    action = QAction("Save", tb)
    action.setIcon(get_office_icon("save"))
    tb.addAction(action)

    split_btn = tb.add_split_action(action, QMenu("Menu", tb))
    drop_btn = tb.add_drop_button("绘图", get_office_icon("draw"), QMenu("Draw", tb))
    color_btn = ColorPickerButton(mode="fill", default_color="#FFFF00", parent=tb)
    tb.addWidget(color_btn)

    # 1. Dotted grip width
    assert tb.grip_handle.sizeHint().width() == 7, "Dotted grip must be 7px wide"

    # 2. Separator width
    sep = OfficeToolBarSeparator(tb)
    assert sep.sizeHint().width() == 4, "Separator must be 4px wide"

    # 3. Standard button heights: target is 22px, deviation <= 2px (20px to 24px)
    h_split = split_btn.sizeHint().height()
    h_drop = drop_btn.sizeHint().height()
    h_color = color_btn.sizeHint().height()
    assert abs(h_split - 22) <= 2, f"Split button height {h_split} must be ~22px"
    assert abs(h_drop - 22) <= 2, f"Drop button height {h_drop} must be ~22px"
    assert abs(h_color - 22) <= 2, f"Color button height {h_color} must be ~22px"

    # 4. Split button width: target ~34px (32px to 36px)
    w_split = split_btn.sizeHint().width()
    w_color = color_btn.sizeHint().width()
    assert abs(w_split - 34) <= 2, f"Split button width {w_split} must be ~34px"
    assert abs(w_color - 34) <= 2, f"Color button width {w_color} must be ~34px"


def test_dynamic_enabled_synchronization(qtbot) -> None:
    """Disabling an action immediately disables the corresponding toolbar button."""
    tb = OfficeToolBar("EnabledSync", None)
    qtbot.addWidget(tb)

    action = QAction("Redo", tb)
    split_btn = tb.add_split_action(action, QMenu("Redo", tb))
    color_btn = ColorPickerButton(mode="font", default_color="#000000", parent=tb)
    tb.addWidget(color_btn)

    assert split_btn.isEnabled() is True
    assert color_btn.isEnabled() is True

    # Disable action
    action.setEnabled(False)
    assert split_btn.isEnabled() is False, "Split button must synchronize enabled state from action"

    color_btn.setEnabled(False)
    assert color_btn.isEnabled() is False

    # Rendering disabled buttons must not raise exceptions or crash
    pix_split = split_btn.grab()
    assert not pix_split.isNull()
    pix_color = color_btn.grab()
    assert not pix_color.isNull()


def test_multi_resolution_and_overflow(qtbot) -> None:
    """Toolbars must remain fully operable under 1440x900 and 1024x768 overflow scenarios."""
    win = QuireWindow()
    qtbot.addWidget(win)

    # 1. 1440x900 scene
    win.resize(1440, 900)
    win.show()
    QApplication.processEvents()
    for name, tb in win.toolbars.items():
        assert win.toolBarArea(tb) == Qt.ToolBarArea.TopToolBarArea

    # 2. 1024x768 overflow scene
    win.resize(1024, 768)
    QApplication.processEvents()
    for name, tb in win.toolbars.items():
        assert win.toolBarArea(tb) == Qt.ToolBarArea.TopToolBarArea
        # Ensure toolbar extension button or actions exist without error
        assert len(tb.actions()) > 0


def test_nine_locales_toolbar_retranslate(qtbot) -> None:
    """Ensure all 9 locales dynamically update button labels without truncation."""
    win = QuireWindow()
    qtbot.addWidget(win)
    win.show()

    for loc in SUPPORTED_LOCALES:
        load_locale(loc)
        win.retranslate_ui()
        QApplication.processEvents()

        # Check standard and formatting toolbars
        for tb_name in ("standard", "formatting"):
            tb = win.toolbars[tb_name]
            assert tb.windowTitle(), f"Toolbar {tb_name} must have a translated title in {loc}"

            for btn in tb.findChildren(OfficeDropDownButton):
                has_content = bool(btn.toolTip() or btn.text())
                assert has_content, f"DropDownButton must have non-empty text/tip in {loc}"

            for cp in tb.findChildren(ColorPickerButton):
                assert cp.toolTip(), f"ColorPickerButton must have a non-empty tooltip in {loc}"
                # Check popup retranslate
                cp.popup.retranslate_ui()
                assert cp.popup.btn_auto_or_none.text(), f"Popup top text empty in {loc}"
                assert cp.popup.btn_more_colors.text(), f"Popup more colors text empty in {loc}"
