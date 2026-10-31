"""Unit tests for ATBOffice Luna Vector Icons Engine (icons.py)."""

import pytest
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication


# Ensure QApplication instance exists for GUI/pixmap operations
@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_list_office_icons():
    from atboffice.ui.icons import list_office_icons

    icons = list_office_icons()
    assert isinstance(icons, list)
    assert len(icons) >= 120

    core_icons = [
        "new", "open", "save", "print", "preview", "spell", "cut", "copy",
        "paste", "painter", "undo", "redo", "chart", "table", "bold",
        "italic", "underline", "alignLeft", "alignCenter", "alignRight",
        "justify", "numbering", "bullets", "fontColor", "fillColor",
        "fx", "filter", "freeze", "bordersAll", "wordCount", "app"
    ]
    for key in core_icons:
        assert key in icons, f"Missing expected core icon key: {key}"


def test_has_office_icon():
    from atboffice.ui.icons import has_office_icon

    assert has_office_icon("new") is True
    assert has_office_icon("save") is True
    assert has_office_icon("nonexistent_random_key_123") is False


def test_get_office_svg():
    from atboffice.ui.icons import get_office_svg

    svg = get_office_svg("new", size=16)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert 'viewBox="0 0 16 16"' in svg
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg

    empty_svg = get_office_svg("nonexistent_icon_key")
    assert empty_svg == ""


def test_get_office_pixmap():
    from atboffice.ui.icons import get_office_pixmap

    pixmap16 = get_office_pixmap("save", size=16)
    assert isinstance(pixmap16, QPixmap)
    assert not pixmap16.isNull()
    assert pixmap16.width() == 16
    assert pixmap16.height() == 16

    pixmap24 = get_office_pixmap("save", size=24)
    assert not pixmap24.isNull()
    assert pixmap24.width() == 24
    assert pixmap24.height() == 24


def test_get_office_icon_all():
    from atboffice.ui.icons import get_office_icon, list_office_icons

    icons = list_office_icons()
    assert len(icons) >= 120

    for name in icons:
        icon = get_office_icon(name, size=16)
        assert isinstance(icon, QIcon), f"Failed for {name}: not a QIcon"
        assert not icon.isNull(), f"Failed for {name}: QIcon is null"
        pix = icon.pixmap(16, 16)
        assert not pix.isNull(), f"Failed for {name}: pixmap(16, 16) is null"


def test_get_office_icon_swatch():
    from atboffice.ui.icons import get_office_icon, get_office_svg

    svg_default = get_office_svg("fontColor")
    assert "#f00" in svg_default or "red" in svg_default

    svg_custom = get_office_svg("fontColor", swatch_color="#00ff00")
    assert "#00ff00" in svg_custom

    icon_custom = get_office_icon("fontColor", swatch_color="#00ff00")
    assert not icon_custom.isNull()


def test_icon_caching_and_clear():
    from atboffice.ui.icons import clear_icon_cache, get_office_icon

    clear_icon_cache()
    icon1 = get_office_icon("undo", size=16)
    icon2 = get_office_icon("undo", size=16)
    assert icon1 is icon2

    clear_icon_cache()
    icon3 = get_office_icon("undo", size=16)
    # After cache clear, a fresh instance is returned
    assert icon3 is not icon1
    assert not icon3.isNull()


def test_unknown_icon_graceful():
    from atboffice.ui.icons import get_office_icon, get_office_pixmap

    icon = get_office_icon("nonexistent_unknown_xyz")
    assert isinstance(icon, QIcon)
    assert icon.isNull()

    pix = get_office_pixmap("nonexistent_unknown_xyz")
    assert isinstance(pix, QPixmap)
    assert pix.isNull()
