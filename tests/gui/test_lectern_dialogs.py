"""Tests for Lectern classic presentation property dialogs."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.dialogs import (
    FormatShapeDialog,
    HeaderFooterDialog,
    SetupShowDialog,
    SlideLayoutDialog,
)
from atboffice.modules.presentation.models.presentation import (
    HeaderFooterSettings,
    Presentation,
    SlideShowSettings,
)
from atboffice.modules.presentation.models.shape import Fill, Line, Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun


@pytest.fixture
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def test_format_shape_dialog_init_and_apply(app):
    """Test FormatShapeDialog initialization and applying changes to a shape."""
    shape = Shape(
        id="shape1",
        type="shape",
        name="AutoShape 1",
        geom="rect",
        x=50.0,
        y=60.0,
        w=200.0,
        h=150.0,
        rot=0.0,
        fill=Fill.solid("#336699", alpha=0.9),
        line=Line(color="#003366", width=2.0, dash="dash"),
        text=TextBody(
            insets=(10.0, 5.0, 10.0, 5.0),
            paragraphs=[Paragraph(level=0, runs=[TextRun(text="Sample text")])],
        ),
    )

    dialog = FormatShapeDialog([shape])
    assert dialog.windowTitle() != ""
    assert dialog.tab_widget.count() >= 5  # Colors, Size, Position, TextBox, Web

    # Test updating values via dialog controls
    dialog.color_lines_tab.fill_color_btn.set_color("#FF5500")
    dialog.color_lines_tab.transparency_spin.setValue(20)
    dialog.color_lines_tab.line_weight_spin.setValue(3.5)
    dialog.color_lines_tab.line_dash_combo.setCurrentText("dot")

    dialog.size_tab.width_spin.setValue(250.0)
    dialog.size_tab.height_spin.setValue(180.0)
    dialog.size_tab.rot_spin.setValue(45.0)

    dialog.pos_tab.x_spin.setValue(80.0)
    dialog.pos_tab.y_spin.setValue(90.0)

    dialog.text_tab.margin_left_spin.setValue(15.0)
    dialog.text_tab.margin_top_spin.setValue(8.0)
    dialog.text_tab.word_wrap_chk.setChecked(True)

    dialog.web_tab.alt_text_edit.setPlainText("Accessible description")

    # Apply changes
    dialog.apply_changes()

    assert shape.fill.color == "#FF5500"
    assert abs(shape.fill.alpha - 0.8) < 0.01  # 20% transparency = 0.8 alpha
    assert shape.line.width == 3.5
    assert shape.line.dash == "dot"
    assert shape.w == 250.0
    assert shape.h == 180.0
    assert shape.rot == 45.0
    assert shape.x == 80.0
    assert shape.y == 90.0
    assert shape.text.insets[0] == 15.0
    assert shape.text.insets[1] == 8.0
    assert shape.text.wrap is True
    assert getattr(shape, "alt", "") == "Accessible description"


def test_format_shape_dialog_picture_tab(app):
    """Test FormatShapeDialog with an image shape."""
    pic_shape = Shape(
        id="pic1",
        type="image",
        name="Picture 1",
        x=10.0,
        y=10.0,
        w=300.0,
        h=200.0,
        crop={"l": 0.0, "t": 0.0, "r": 0.0, "b": 0.0},
    )

    dialog = FormatShapeDialog([pic_shape])
    # Should include Picture tab
    assert dialog.pic_tab is not None
    dialog.pic_tab.crop_left_spin.setValue(10.0)
    dialog.pic_tab.crop_top_spin.setValue(5.0)
    dialog.pic_tab.brightness_spin.setValue(15)
    dialog.pic_tab.contrast_spin.setValue(-10)

    dialog.apply_changes()

    assert pic_shape.crop["l"] == 0.1  # 10%
    assert pic_shape.crop["t"] == 0.05  # 5%
    assert getattr(pic_shape, "img", {}).get("bright") == 15
    assert getattr(pic_shape, "img", {}).get("contrast") == -10


def test_setup_show_dialog(app):
    """Test SetupShowDialog show modes and options."""
    settings = SlideShowSettings(
        loop=False,
        no_anim=False,
        use_timings=True,
        from_slide=0,
        to_slide=0,
        pen_color="#FF0000",
        kiosk=False,
    )
    pres = Presentation(
        slides=[Slide(id="s1"), Slide(id="s2"), Slide(id="s3")],
        show=settings,
    )

    dialog = SetupShowDialog(pres)
    assert dialog.windowTitle() != ""

    # Switch to kiosk mode
    dialog.kiosk_radio.setChecked(True)
    # Kiosk should force loop to True
    assert dialog.loop_chk.isChecked() is True

    # Switch to slide range From 2 To 3
    dialog.from_to_radio.setChecked(True)
    dialog.from_spin.setValue(2)
    dialog.to_spin.setValue(3)

    # Change pen color
    dialog.pen_color_btn.set_color("#0000FF")

    # Change advance slides to manual
    dialog.manual_adv_radio.setChecked(True)

    # Change show options
    dialog.no_anim_chk.setChecked(True)

    dialog.apply_changes()

    assert settings.kiosk is True
    assert settings.loop is True
    assert settings.from_slide == 2
    assert settings.to_slide == 3
    assert settings.pen_color == "#0000FF"
    assert settings.use_timings is False
    assert settings.no_anim is True


def test_header_footer_dialog(app):
    """Test HeaderFooterDialog slide header & footer settings."""
    hf = HeaderFooterSettings(
        dt=False,
        dt_auto=True,
        dt_fmt="datetime1",
        dt_text="",
        num=False,
        ftr=False,
        ftr_text="",
        not_on_title=False,
    )
    pres = Presentation(
        slides=[Slide(id="s1"), Slide(id="s2")],
        hf=hf,
    )

    dialog = HeaderFooterDialog(pres, slide_idx=0)
    dialog.dt_chk.setChecked(True)
    dialog.dt_fixed_radio.setChecked(True)
    dialog.dt_fixed_edit.setText("2026-10-27")
    dialog.num_chk.setChecked(True)
    dialog.ftr_chk.setChecked(True)
    dialog.ftr_edit.setText("Confidential")
    dialog.not_on_title_chk.setChecked(True)

    dialog.apply_to_all()

    assert pres.hf.dt is True
    assert pres.hf.dt_auto is False
    assert pres.hf.dt_text == "2026-10-27"
    assert pres.hf.num is True
    assert pres.hf.ftr is True
    assert pres.hf.ftr_text == "Confidential"
    assert pres.hf.not_on_title is True


def test_slide_layout_dialog(app):
    """Test SlideLayoutDialog selection and callback."""
    selected_layout = []

    def on_apply(layout_key: str):
        selected_layout.append(layout_key)

    dialog = SlideLayoutDialog(current_layout="title_content", on_select=on_apply)
    assert dialog.layout_list.count() > 0

    # Select another layout
    dialog.select_layout("blank")
    dialog.apply_layout()

    assert selected_layout == ["blank"]


def test_dialogs_retranslate_ui(app):
    """Verify that retranslate_ui works without crashing for all dialogs."""
    pres = Presentation(slides=[Slide(id="s1")])
    shape = Shape(id="s1")

    d1 = FormatShapeDialog([shape])
    d1.retranslate_ui()

    d2 = SetupShowDialog(pres)
    d2.retranslate_ui()

    d3 = HeaderFooterDialog(pres)
    d3.retranslate_ui()

    d4 = SlideLayoutDialog()
    d4.retranslate_ui()


def test_format_shape_dialog_edge_cases(app):
    """Test empty shapes, multiple shapes, and aspect ratio locking."""
    # 1. Empty shape list
    d_empty = FormatShapeDialog([])
    assert d_empty.shapes is not None
    assert len(d_empty.shapes) == 1

    # 2. Aspect ratio locking
    s = Shape(id="s_aspect", w=100.0, h=50.0)
    d = FormatShapeDialog([s])
    d.size_tab.lock_aspect_chk.setChecked(True)
    d.size_tab.width_spin.setValue(200.0)
    assert d.size_tab.height_spin.value() == 100.0
    d.size_tab.height_spin.setValue(50.0)
    assert d.size_tab.width_spin.value() == 100.0

    # 3. Line shape
    line_shape = Shape(id="line1", type="line")
    d_line = FormatShapeDialog([line_shape])
    assert "Line" in d_line.windowTitle()


def test_setup_show_range_swapping(app):
    """Test that inverted slide range (from > to) is automatically corrected."""
    pres = Presentation(
        slides=[Slide(id="s1"), Slide(id="s2"), Slide(id="s3"), Slide(id="s4")],
        show=SlideShowSettings(),
    )
    dialog = SetupShowDialog(pres)
    dialog.from_to_radio.setChecked(True)
    dialog.from_spin.setValue(4)
    dialog.to_spin.setValue(2)
    dialog.apply_changes()

    assert pres.show.from_slide == 2
    assert pres.show.to_slide == 4

