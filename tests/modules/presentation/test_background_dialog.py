"""Unit and GUI tests for Lectern slide background dialog and fill effects."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.dialogs import (
    BackgroundDialog,
    FillEffectsDialog,
)
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Fill
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.slideshow.transitions import render_slide_to_image
from atboffice.modules.presentation.views.background_renderer import (
    GRAD_PRESETS,
    paint_fill_rect,
)
from atboffice.modules.presentation.views.slide_canvas import SlideScene
from atboffice.modules.presentation.views.workspace import render_slide_thumbnail


@pytest.fixture
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def test_slide_background_serialization():
    """Test Slide background model serialization, deserialization, and Fill helpers."""
    # 1. Slide with solid background
    fill_solid = Fill.solid("#FF6600", alpha=0.85)
    slide1 = Slide(id="sl_01", bg=fill_solid, hide_master=True)
    d1 = slide1.to_dict()

    assert "bg" in d1
    assert d1["bg"]["t"] == "solid"
    assert d1["bg"]["c"] == "#FF6600"
    assert abs(d1["bg"]["a"] - 0.85) < 0.01
    assert d1["hide_master"] is True
    assert d1["hideMaster"] is True

    loaded1 = Slide.from_dict(d1)
    assert loaded1.bg is not None
    assert loaded1.bg.type == "solid"
    assert loaded1.bg.color == "#FF6600"
    assert loaded1.hide_master is True

    # 2. Slide without background override (inherits from design)
    slide2 = Slide(id="sl_02", bg=None, hide_master=False)
    d2 = slide2.to_dict()
    assert "bg" not in d2
    assert "hide_master" not in d2

    loaded2 = Slide.from_dict(d2)
    assert loaded2.bg is None
    assert loaded2.hide_master is False

    # 3. Fill image_fill serialization
    img_fill = Fill.image_fill("textures/sample.png", tile=True)
    d_img = img_fill.to_dict()
    assert d_img["t"] == "img"
    assert d_img["image_path"] == "textures/sample.png"
    assert d_img["tile"] is True

    loaded_img = Fill.from_dict(d_img)
    assert loaded_img.type == "img"
    assert loaded_img.image_path == "textures/sample.png"
    assert loaded_img.tile is True


def test_fill_effects_dialog_gradient(app):
    """Test FillEffectsDialog gradient tab options and presets."""
    dialog = FillEffectsDialog(Fill.solid("#003366"))
    assert dialog.windowTitle() != ""
    assert dialog.tab_widget.count() == 4

    # 1. Default to Gradient Tab
    dialog.tab_widget.setCurrentIndex(0)

    # 2. Test Two Color Mode
    dialog.radio_two_col.setChecked(True)
    dialog.color_mode_group.idClicked.emit(2)
    dialog.btn_col1.set_color("#FF0000")
    dialog.btn_col2.set_color("#0000FF")
    dialog.spin_from.setValue(10)
    dialog.spin_to.setValue(20)

    # 3. Test Shading style & variant selection
    dialog.radio_vert.setChecked(True)
    dialog.shading_group.idClicked.emit(1)
    dialog._select_variant(1)

    grad_fill = dialog.get_fill()
    assert grad_fill.type == "grad"
    assert len(grad_fill.stops) >= 2
    assert grad_fill.angle == 0.0  # Vertical

    # 4. Test Preset Mode
    dialog.radio_preset.setChecked(True)
    dialog.color_mode_group.idClicked.emit(3)
    dialog.combo_presets.setCurrentIndex(0)  # 早期黄昏
    preset_fill = dialog.get_fill()
    assert preset_fill.type == "grad"
    assert len(preset_fill.stops) == len(GRAD_PRESETS[0][1])


def test_fill_effects_dialog_texture(app):
    """Test FillEffectsDialog texture tab with procedural textures."""
    dialog = FillEffectsDialog()
    dialog.tab_widget.setCurrentIndex(1)  # Texture tab

    # Select "水滴"
    dialog._on_texture_selected("水滴")
    tex_fill = dialog.get_fill()
    assert tex_fill.type == "img"
    assert tex_fill.tile is True
    assert tex_fill.image_path in ("水滴", "Water droplets")


def test_fill_effects_dialog_pattern(app):
    """Test FillEffectsDialog pattern tab with 54 Office patterns."""
    dialog = FillEffectsDialog()
    dialog.tab_widget.setCurrentIndex(2)  # Pattern tab

    dialog.btn_patt_fg.set_color("#112233")
    dialog.btn_patt_bg.set_color("#EEDDCC")
    dialog._on_pattern_selected("smGrid")

    patt_fill = dialog.get_fill()
    assert patt_fill.type == "patt"
    assert patt_fill.pattern == "smGrid"
    assert patt_fill.fg == "#112233"
    assert patt_fill.bg == "#EEDDCC"


def test_fill_effects_dialog_picture(app, tmp_path):
    """Test FillEffectsDialog picture tab with external image file."""
    # Create temporary image file
    img_path = str(tmp_path / "bg_test.png")
    test_img = QImage(32, 32, QImage.Format.Format_ARGB32)
    test_img.fill(QColor("#5588AA"))
    test_img.save(img_path)

    dialog = FillEffectsDialog()
    dialog.tab_widget.setCurrentIndex(3)  # Picture tab

    dialog.selected_picture_path = img_path
    dialog.chk_tile_pic.setChecked(False)

    pic_fill = dialog.get_fill()
    assert pic_fill.type == "img"
    assert pic_fill.image_path == img_path
    assert pic_fill.tile is False


def test_background_dialog_apply_current_slide(app):
    """Test BackgroundDialog applying custom fill to current slide only."""
    pres = Presentation.create_new(title="BgTest")
    slide = pres.slides[0]
    assert slide.bg is None
    assert slide.hide_master is False

    dialog = BackgroundDialog(slide, pres)
    assert dialog.windowTitle() != ""

    # Choose a solid color
    dialog._set_solid_color("#123456")
    dialog.chk_omit_master.setChecked(True)

    # Apply to current slide
    dialog.apply_to_current_slide()

    assert slide.bg is not None
    assert slide.bg.type == "solid"
    assert slide.bg.color == "#123456"
    assert slide.hide_master is True


def test_background_dialog_apply_to_all(app):
    """Test BackgroundDialog applying fill to all slides and master design."""
    pres = Presentation.create_new(title="BgTestAll")
    # Add second and third slides
    s2 = Slide(id="s2")
    s3 = Slide(id="s3")
    pres.slides.extend([s2, s3])

    dialog = BackgroundDialog(pres.slides[0], pres)
    dialog._set_solid_color("#654321")
    dialog.chk_omit_master.setChecked(True)

    # Apply to all slides
    dialog.apply_to_all_slides()

    # Individual slides reset to None to inherit from design
    for s in pres.slides:
        assert s.bg is None
        assert s.hide_master is True

    # Active design template has the new background
    design = pres.get_design_for_slide(pres.slides[0])
    assert design.bg.type == "solid"
    assert design.bg.color == "#654321"


def test_background_rendering_all_modes(app):
    """Test background rendering engine across solid, gradient, pattern, and procedural textures."""
    img = QImage(160, 90, QImage.Format.Format_ARGB32_Premultiplied)
    r = QRectF(0, 0, 160, 90)

    # 1. Solid
    p1 = QPainter(img)
    paint_fill_rect(p1, r, Fill.solid("#FF8800", alpha=0.9))
    p1.end()
    assert not img.isNull()

    # 2. Linear Gradient
    p2 = QPainter(img)
    grad_fill = Fill.gradient(
        stops=[{"p": 0.0, "c": "#FFFFFF"}, {"p": 1.0, "c": "#003366"}],
        angle=90.0,
    )
    paint_fill_rect(p2, r, grad_fill)
    p2.end()
    assert not img.isNull()

    # 3. Radial Gradient (circle)
    p3 = QPainter(img)
    rad_fill = Fill.gradient(
        stops=[{"p": 0.0, "c": "#FFFF00"}, {"p": 1.0, "c": "#FF0000"}],
        path="circle",
    )
    paint_fill_rect(p3, r, rad_fill)
    p3.end()
    assert not img.isNull()

    # 4. Pattern Fill
    p4 = QPainter(img)
    patt_fill = Fill.pattern_fill("pct50", fg="#000000", bg="#FFFFFF")
    paint_fill_rect(p4, r, patt_fill)
    p4.end()
    assert not img.isNull()

    # 5. Procedural Texture
    p5 = QPainter(img)
    tex_fill = Fill.image_fill("Canvas", tile=True)
    paint_fill_rect(p5, r, tex_fill)
    p5.end()
    assert not img.isNull()


def test_canvas_slideshow_and_thumbnails_integration(app):
    """Test SlideScene, render_slide_to_image, and render_slide_thumbnail with custom background."""
    pres = Presentation.create_new(title="IntegrationDeck")
    slide = pres.slides[0]
    slide.bg = Fill.gradient(
        stops=[{"p": 0.0, "c": "#0B1633"}, {"p": 1.0, "c": "#22427A"}],
        angle=90.0,
    )

    # 1. SlideScene canvas drawBackground
    scene = SlideScene(slide=slide, presentation=pres, slide_width=960.0, slide_height=540.0)
    canvas_img = QImage(960, 540, QImage.Format.Format_ARGB32_Premultiplied)
    cp = QPainter(canvas_img)
    scene.drawBackground(cp, QRectF(0, 0, 960, 540))
    cp.end()
    assert not canvas_img.isNull()

    # 2. Slideshow snapshot render
    slideshow_img = render_slide_to_image(slide, pres, width=960, height=540)
    assert not slideshow_img.isNull()
    assert slideshow_img.width() == 960
    assert slideshow_img.height() == 540

    # 3. Workspace thumbnail render
    thumb_pix = render_slide_thumbnail(slide, pres, width=160)
    assert not thumb_pix.isNull()
    assert thumb_pix.width() == 160
