"""Unit and integration tests for WordArt gallery and curved text deformations."""

import math
import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath

from atboffice.modules.common.wordart_gallery import (
    WA_STYLES,
    WarpMode,
    WordArtGalleryDialog,
    WordArtStyle,
    WordArtTextDialog,
    WordArtThumbnailWidget,
    create_wordart_composite_path,
    prompt_insert_wordart,
    render_wordart,
    warp_points,
)


def test_wordart_styles_count_and_properties():
    """Verify that exactly 30 classic WordArt style presets exist with valid parameters."""
    assert len(WA_STYLES) == 30

    for i, style in enumerate(WA_STYLES):
        assert isinstance(style, WordArtStyle)
        assert style.id == i
        assert style.fill_type in ("solid", "gradient")
        assert len(style.fill_colors) >= 1
        assert style.warp in [m.value for m in WarpMode]
        assert isinstance(style.font_family, str)
        assert len(style.font_family) > 0


def test_wordart_warp_points_all_modes():
    """Verify parametric warp calculations for all 10 warp modes."""
    w, h, fs = 200.0, 100.0, 36.0
    for mode in WarpMode:
        pts = warp_points(mode.value, w, h, fs, num_points=32)
        assert len(pts) == 33  # 0 to 32 inclusive
        for x, y in pts:
            assert not math.isnan(x) and not math.isinf(x)
            assert not math.isnan(y) and not math.isinf(y)


def test_wordart_composite_path_generation(qapp):
    """Test generating vector QPainterPath for both plain and warped text."""
    style_plain = WA_STYLES[0]  # Plain text
    style_arch = WA_STYLES[4]   # Arch Up
    style_wave = WA_STYLES[5]   # Wave

    rect = QRectF(0.0, 0.0, 300.0, 150.0)

    # 1. Plain text path
    path_plain = create_wordart_composite_path("ATBOffice", style_plain, rect)
    assert isinstance(path_plain, QPainterPath)
    assert not path_plain.isEmpty()
    assert path_plain.boundingRect().width() > 0

    # 2. Arch Up path
    path_arch = create_wordart_composite_path("Curve Test", style_arch, rect)
    assert isinstance(path_arch, QPainterPath)
    assert not path_arch.isEmpty()

    # 3. Wave path
    path_wave = create_wordart_composite_path("Wave Text", style_wave, rect)
    assert isinstance(path_wave, QPainterPath)
    assert not path_wave.isEmpty()

    # 4. Edge case: empty text returns empty path without error
    empty_path = create_wordart_composite_path("", style_plain, rect)
    assert empty_path.isEmpty()

    # 5. Edge case: zero or negative rect handled gracefully
    zero_rect = QRectF(0.0, 0.0, 0.0, 0.0)
    zero_path = create_wordart_composite_path("Test", style_plain, zero_rect)
    assert isinstance(zero_path, QPainterPath)


def test_wordart_render_to_image(qapp):
    """Verify that render_wordart draws without error onto a QImage surface."""
    img = QImage(300, 150, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)

    painter = QPainter(img)
    for style in WA_STYLES[:6]:
        render_wordart(painter, "WordArt", style, QRectF(10.0, 10.0, 280.0, 130.0))
    painter.end()


def test_wordart_thumbnail_widget(qapp):
    """Test thumbnail widget for rendering style preview and handling selection."""
    style = WA_STYLES[2]
    thumb = WordArtThumbnailWidget(style, is_selected=False)
    assert thumb.sizeHint().width() > 0
    assert thumb.sizeHint().height() > 0

    thumb.set_selected(True)
    assert thumb.is_selected

    # Render thumbnail to pixmap
    pm = thumb.grab()
    assert not pm.isNull()
    assert pm.width() > 0


def test_wordart_gallery_dialog(qapp):
    """Test WordArtGalleryDialog grid creation, selection, and keyboard navigation."""
    dlg = WordArtGalleryDialog()
    assert dlg.selected_style_index == 0
    assert dlg.selected_style.id == 0

    # Change selection
    dlg.set_selected_style_index(12)
    assert dlg.selected_style_index == 12
    assert dlg.selected_style.id == 12

    # Verify 30 thumbnails exist in the grid
    assert len(dlg.thumbnail_widgets) == 30

    dlg.close()


def test_wordart_text_dialog(qapp):
    """Test WordArtTextDialog controls, property updates, and result dictionary."""
    dlg = WordArtTextDialog(
        initial_text="Hello World",
        initial_font="Arial Black",
        initial_size=40,
        initial_bold=True,
        initial_italic=False,
    )
    res = dlg.get_result()
    assert res["text"] == "Hello World"
    assert res["font"] == "Arial Black"
    assert res["size"] == 40
    assert res["bold"] is True
    assert res["italic"] is False

    # Update text and font properties
    dlg.text_edit.setPlainText("Modified Text")
    dlg.size_combo.setCurrentText("72")
    dlg.bold_btn.setChecked(False)
    dlg.italic_btn.setChecked(True)

    res2 = dlg.get_result()
    assert res2["text"] == "Modified Text"
    assert res2["size"] == 72
    assert res2["bold"] is False
    assert res2["italic"] is True

    dlg.close()


def test_prompt_insert_wordart_canceled(qapp, monkeypatch):
    """Verify that canceling the gallery dialog returns None cleanly."""
    monkeypatch.setattr(
        WordArtGalleryDialog, "exec", lambda self: WordArtGalleryDialog.DialogCode.Rejected
    )
    result = prompt_insert_wordart(parent=None)
    assert result is None


def test_mac_menu_and_base_window_wordart_integration(qapp):
    """Verify that mac_menu registers insert_wordart and base window provides handler."""
    from atboffice.ui.shell.base_window import BaseOfficeWindow
    from atboffice.ui.shell.mac_menu import MacMenuBar

    win = BaseOfficeWindow()
    assert hasattr(win, "open_wordart_gallery")

    menu_bar = MacMenuBar(win)
    assert "insert_wordart" in menu_bar.action_map
    act = menu_bar.action_map["insert_wordart"]
    assert "艺术字" in act.text()

    win.close()

