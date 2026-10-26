"""Tests for Office 2003 Luna Blue/Silver styling, toolbar, and color picker."""

import sys

from PySide6.QtWidgets import QMainWindow, QWidget

from atboffice.ui.components.color_picker import (
    OFFICE_2003_STANDARD_COLORS,
    ColorPickerButton,
    ColorPickerPopup,
)
from atboffice.ui.components.toolbar import DottedGrip, OfficeToolBar
from atboffice.ui.shell.main_window import MainWindow
from atboffice.ui.styles.luna_2003 import (
    apply_luna_theme,
    format_mnemonic,
    get_luna_stylesheet,
)


def test_format_mnemonic():
    """Verify platform-specific mnemonic accelerator formatting."""
    # macOS: strip mnemonic parentheses and ampersands
    assert format_mnemonic("文件(&F)", is_macos=True) == "文件"
    assert format_mnemonic("&File", is_macos=True) == "File"
    assert format_mnemonic("普通文本", is_macos=True) == "普通文本"

    # Non-macOS (Windows/Linux): preserve mnemonics
    assert format_mnemonic("文件(&F)", is_macos=False) == "文件(&F)"
    assert format_mnemonic("&File", is_macos=False) == "&File"
    assert format_mnemonic("Normal Text", is_macos=False) == "Normal Text"


def test_luna_stylesheets(qtbot):
    """Verify Luna Blue and Luna Silver QSS stylesheet generation and application."""
    widget = QWidget()
    qtbot.addWidget(widget)

    qss_blue = get_luna_stylesheet("blue")
    assert "QToolBar" in qss_blue
    assert "#E3EFFF" in qss_blue or "#3B619C" in qss_blue
    assert "QToolButton" in qss_blue

    qss_silver = get_luna_stylesheet("silver")
    assert "QToolBar" in qss_silver
    assert qss_silver != qss_blue

    # Verify theme application
    apply_luna_theme(widget, "blue")
    assert widget.styleSheet() == qss_blue

    apply_luna_theme(widget, "silver")
    assert widget.styleSheet() == qss_silver


def test_office_toolbar(qtbot):
    """Verify OfficeToolBar properties, grip handle, and actions."""
    win = QMainWindow()
    qtbot.addWidget(win)
    tb = OfficeToolBar("Standard", win)
    win.addToolBar(tb)
    win.show()

    assert tb.isMovable() is True
    assert tb.isFloatable() is True

    # Grip widget check
    grip = tb.grip_handle
    assert isinstance(grip, DottedGrip)
    assert not grip.isHidden()

    # When toolbar is fixed, grip should hide
    tb.setMovable(False)
    assert grip.isHidden() is True
    tb.setMovable(True)
    assert not grip.isHidden()

    # Test adding actions with mnemonic
    act = tb.add_office_action("新建(&N)", tooltip="新建文件 (Ctrl+N)")
    assert act is not None
    if sys.platform == "darwin":
        assert act.text() == "新建"
    else:
        assert act.text() == "新建(&N)"

    # Add separator
    sep = tb.add_office_separator()
    assert sep is not None


def test_color_picker_popup(qtbot):
    """Verify 40-color standard palette popup and selection signals."""
    popup = ColorPickerPopup(mode="fill")
    qtbot.addWidget(popup)

    # Must contain exactly 40 standard color buttons
    assert len(popup.swatch_buttons) == 40
    assert len(OFFICE_2003_STANDARD_COLORS) == 40

    # First color is black, last is white
    assert OFFICE_2003_STANDARD_COLORS[0].upper() == "#000000"
    assert OFFICE_2003_STANDARD_COLORS[-1].upper() == "#FFFFFF"

    # Tooltip check (localized)
    first_btn = popup.swatch_buttons[0]
    assert first_btn.toolTip() != ""

    # Test clicking a swatch emits color_selected
    with qtbot.waitSignal(popup.color_selected, timeout=1000) as blocker:
        first_btn.click()
    assert blocker.args == ["#000000"]

    # Test clicking automatic / no fill button
    with qtbot.waitSignal(popup.color_selected, timeout=1000) as blocker:
        popup.btn_auto_or_none.click()
    assert blocker.args == ["none"]

    # Test mode="font" automatic button
    popup_font = ColorPickerPopup(mode="font")
    qtbot.addWidget(popup_font)
    with qtbot.waitSignal(popup_font.color_selected, timeout=1000) as blocker:
        popup_font.btn_auto_or_none.click()
    assert blocker.args == ["auto"]


def test_color_picker_button(qtbot):
    """Verify ColorPickerButton drop-down, current color display, and trigger."""
    btn = ColorPickerButton(mode="font", default_color="#000000")
    qtbot.addWidget(btn)

    assert btn.current_color == "#000000"

    # Set color and verify property update
    btn.set_color("#FF0000")
    assert btn.current_color == "#FF0000"

    # Triggering action applies current color
    with qtbot.waitSignal(btn.color_applied, timeout=1000) as blocker:
        btn.click()
    assert blocker.args == ["#FF0000"]


def test_main_window_luna_integration(qtbot):
    """Verify MainWindow integrates OfficeToolBar and Luna theme switching."""
    win = MainWindow()
    qtbot.addWidget(win)

    # Standard and Formatting toolbars should be present
    assert hasattr(win, "toolbar_standard")
    assert hasattr(win, "toolbar_formatting")
    assert isinstance(win.toolbar_standard, OfficeToolBar)
    assert isinstance(win.toolbar_formatting, OfficeToolBar)

    # Verify color picker buttons on formatting toolbar
    assert hasattr(win, "btn_font_color")
    assert hasattr(win, "btn_fill_color")
    assert isinstance(win.btn_font_color, ColorPickerButton)
    assert isinstance(win.btn_fill_color, ColorPickerButton)

    # Verify theme switching
    win.set_theme("silver")
    assert win.current_theme == "silver"
    win.set_theme("blue")
    assert win.current_theme == "blue"
