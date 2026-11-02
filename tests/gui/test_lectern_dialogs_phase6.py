"""Unit and GUI tests for Lectern Missing Panes and Dialogs (Phase 6, Task 607).

Covers:
1. SlideDesignPane: Design templates gallery, navigation switcher, used/available cards.
2. ColorSchemesPane: 8-color scheme swatches, navigation switcher, apply to all/selected.
3. AnimationSchemesPane: Categorized animation schemes tree, preview and play signals.
4. ActionSettingsDialog: Mouse Click & Mouse Over 2-tab hyperlinks, sound and actions.
5. SetUpShowDialog: Slide show parameters, speaker/window/kiosk, range, pen colors.
6. FillEffectsDialog: 4-tab fill effects (Gradient, Texture, Pattern, Picture), sample preview.
7. PhotoAlbumDialog: Image wizard, reordering, layouts, frames, and create validation.
8. WordArtGalleryDialog & EditWordArtTextDialog: 30-style gallery and text editor.
9. LecternOptionsDialog: 5-tab application and document options configuration.
10. LecternWindow integration and multi-language retranslate_ui across all components.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from atboffice.modules.presentation.dialogs import (
    ActionSettingsDialog,
    EditWordArtTextDialog,
    FillEffectsDialog,
    LecternOptionsDialog,
    PhotoAlbumDialog,
    SetUpShowDialog,
    SetupShowDialog,
    WordArtGalleryDialog,
)
from atboffice.modules.presentation.models.designs import ColorScheme, DESIGNS
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Fill
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.panes import (
    AnimationSchemesPane,
    ColorSchemesPane,
    SlideDesignPane,
)
from atboffice.ui.shell.lectern_window import LecternWindow


@pytest.fixture
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class TestSlideDesignPane:
    def test_slide_design_pane_init_and_signals(self, app):
        pres = Presentation()
        pres.slides.append(Slide(id="s1", layout="blank", design_id="azure"))

        pane = SlideDesignPane(presentation=pres)
        assert len(pane.design_cards) == len(DESIGNS)
        assert "azure" in pane.design_cards

        # Test navigation links
        nav_target = []
        pane.navigate_pane.connect(lambda t: nav_target.append(t))

        pane.btn_nav_colors.click()
        assert nav_target[-1] == "colors"
        pane.btn_nav_anims.click()
        assert nav_target[-1] == "animations"

        # Test design click
        applied = []
        pane.apply_design_requested.connect(lambda k, all_s: applied.append((k, all_s)))

        card_default = pane.design_cards["default"]
        card_default.click()
        assert len(applied) == 1
        assert applied[0] == ("default", True)

        # Retranslate
        pane.retranslate_ui()
        assert pane.lbl_available.text() != ""


class TestColorSchemesPane:
    def test_color_schemes_pane_init_and_apply(self, app):
        pane = ColorSchemesPane()
        assert len(pane.scheme_cards) > 0

        # Test navigation
        nav_target = []
        pane.navigate_pane.connect(lambda t: nav_target.append(t))
        pane.btn_nav_design.click()
        assert nav_target[-1] == "design"

        # Test apply
        applied = []
        pane.apply_color_scheme_requested.connect(lambda s, all_s: applied.append((s, all_s)))

        first_card = pane.scheme_cards[0]
        first_card.click()
        assert len(applied) == 1
        assert isinstance(applied[0][0], ColorScheme)
        assert applied[0][1] is True

        # Test edit button
        edit_clicked = []
        pane.edit_color_scheme_requested.connect(lambda: edit_clicked.append(True))
        pane.btn_edit.click()
        assert len(edit_clicked) == 1

        pane.retranslate_ui()
        assert pane.lbl_apply.text() != ""


class TestAnimationSchemesPane:
    def test_animation_schemes_pane_init_and_selection(self, app):
        pane = AnimationSchemesPane()
        assert pane.tree.topLevelItemCount() == 4

        applied = []
        pane.apply_animation_scheme_requested.connect(lambda k, all_s: applied.append((k, all_s)))

        play_triggered = []
        pane.play_requested.connect(lambda: play_triggered.append(True))

        # Select a subtle scheme item
        subtle_grp = pane.tree.topLevelItem(1)
        fade_item = subtle_grp.child(2)  # fade_all
        pane._on_item_clicked(fade_item, 0)

        assert pane.selected_scheme_key == "fade_all"
        assert len(applied) == 1
        assert applied[0] == ("fade_all", False)
        assert len(play_triggered) == 1

        # Apply to all button
        pane.btn_apply_all.click()
        assert applied[-1] == ("fade_all", True)

        pane.retranslate_ui()
        assert pane.btn_play.text() != ""


class TestActionSettingsDialog:
    def test_action_settings_dialog_tabs_and_data(self, app):
        pres = Presentation()
        pres.slides.append(Slide(id="sl_1", layout="blank"))
        pres.slides.append(Slide(id="sl_2", layout="blank"))

        dlg = ActionSettingsDialog(presentation=pres)
        assert dlg.tabs.count() == 2

        # Configure click tab: Hyperlink to URL
        click_tab = dlg.tab_click
        click_tab.radio_hlink.setChecked(True)
        idx_url = click_tab.action_combo.findData("url")
        click_tab.action_combo.setCurrentIndex(idx_url)
        click_tab.url_edit.setText("https://github.com/aitobox/ATBOffice")
        click_tab.chk_sound.setChecked(True)
        click_tab.chk_highlight.setChecked(True)

        data = dlg.get_action_settings()
        assert data["click"]["none"] is False
        assert data["click"]["action"] == "url"
        assert data["click"]["url"] == "https://github.com/aitobox/ATBOffice"
        assert data["click"]["sound"] is not None
        assert data["click"]["highlight"] is True

        # Configure hover tab: Hyperlink to Next Slide
        hover_tab = dlg.tab_hover
        hover_tab.radio_hlink.setChecked(True)
        idx_next = hover_tab.action_combo.findData("next")
        hover_tab.action_combo.setCurrentIndex(idx_next)

        data2 = dlg.get_action_settings()
        assert data2["hover"]["none"] is False
        assert data2["hover"]["action"] == "next"

        dlg.retranslate_ui()
        assert "动作设置" in dlg.windowTitle()


class TestSetUpShowDialog:
    def test_setup_show_dialog_options(self, app):
        pres = Presentation()
        pres.slides.append(Slide(id="s1", layout="blank"))
        pres.slides.append(Slide(id="s2", layout="blank"))
        pres.slides.append(Slide(id="s3", layout="blank"))

        dlg = SetUpShowDialog(presentation=pres)
        assert dlg.total_slides == 3

        # Select kiosk mode
        dlg.kiosk_radio.setChecked(True)
        assert dlg.loop_chk.isChecked()

        # Set slide range from 2 to 3
        dlg.from_to_radio.setChecked(True)
        dlg.from_spin.setValue(2)
        dlg.to_spin.setValue(3)

        dlg.manual_adv_radio.setChecked(True)

        dlg.apply_changes()
        assert pres.show.kiosk is True
        assert pres.show.from_slide == 2
        assert pres.show.to_slide == 3
        assert pres.show.use_timings is False

        dlg.retranslate_ui()
        assert "Set Up Show" in dlg.windowTitle()


class TestFillEffectsDialog:
    def test_fill_effects_dialog_tabs(self, app):
        dlg = FillEffectsDialog()
        assert dlg.tab_widget.count() == 4

        # 1. Gradient tab
        spec = dlg.get_fill_spec()
        assert spec["type"] in ("grad", "gradient", "solid")

        # Check Fill object
        fill = dlg.get_fill()
        assert fill is not None
        assert fill.type == "grad"

        # 2. Texture tab
        dlg.tab_widget.setCurrentIndex(1)
        fill_tex = dlg.get_fill()
        assert fill_tex.type == "img"
        assert fill_tex.tile is True

        # 3. Pattern tab
        dlg.tab_widget.setCurrentIndex(2)
        fill_patt = dlg.get_fill()
        assert fill_patt.type == "patt"

        # 4. Picture tab
        dlg.tab_widget.setCurrentIndex(3)
        assert dlg.tab_pic is not None


class TestPhotoAlbumDialog:
    def test_photo_album_dialog_flow(self, app, monkeypatch):
        dlg = PhotoAlbumDialog()

        # Empty album validation
        warned = []
        monkeypatch.setattr(QMessageBox, "warning", lambda p, t, m: warned.append(m))
        dlg.btn_create.click()
        assert len(warned) == 1
        assert dlg.result() != QDialog.DialogCode.Accepted

        # Add picture
        dlg.add_picture("/tmp/test_image1.png")
        dlg.add_picture("/tmp/test_image2.png")
        assert len(dlg.picture_paths) == 2
        assert dlg.pic_list.count() == 2

        # Reorder
        dlg.pic_list.setCurrentRow(1)
        dlg.btn_up.click()
        assert dlg.picture_paths[0] == "/tmp/test_image2.png"

        # Remove
        dlg.btn_remove.click()
        assert len(dlg.picture_paths) == 1

        # Configuration options
        dlg.combo_layout.setCurrentIndex(2)  # 2 pictures
        dlg.combo_frame.setCurrentIndex(1)  # rounded rectangle
        dlg.chk_captions.setChecked(True)

        dlg.btn_create.click()
        assert dlg.result() == QDialog.DialogCode.Accepted

        spec = dlg.get_album_spec()
        assert len(spec["pictures"]) == 1
        assert spec["layout"] == "2"
        assert spec["frame"] == "round_rect"
        assert spec["captions"] is True

        dlg.retranslate_ui()
        assert "相册" in dlg.windowTitle()


class TestWordArtGalleryDialog:
    def test_wordart_gallery_dialog(self, app):
        dlg = WordArtGalleryDialog(current_index=5)
        assert len(dlg.style_buttons) == 30
        assert dlg.selected_style_index == 5

        # Select style 12
        dlg._select_style(12)
        assert dlg.selected_style_index == 12
        style = dlg.get_selected_style()
        assert style["name"] == "Style 13"

        dlg.retranslate_ui()
        assert "艺术字库" in dlg.windowTitle()

    def test_edit_wordart_text_dialog(self, app):
        dlg = EditWordArtTextDialog(initial_text="Antigravity", initial_size=48)
        assert dlg.text_edit.toPlainText() == "Antigravity"

        dlg.combo_font.setCurrentText("Impact")
        dlg.btn_italic.setChecked(True)

        data = dlg.get_wordart_data()
        assert data["text"] == "Antigravity"
        assert data["font"] == "Impact"
        assert data["italic"] is True

        dlg.retranslate_ui()
        assert "编辑“艺术字”文字" in dlg.windowTitle()


class TestLecternOptionsDialog:
    def test_lectern_options_dialog_roundtrip(self, app):
        init_opts = {
            "startup_pane": False,
            "user_name": "Test User",
            "max_undos": 50,
            "pw_open": "secret123",
        }
        dlg = LecternOptionsDialog(options=init_opts)
        assert dlg.tabs.count() == 5
        assert dlg.chk_startup_pane.isChecked() is False
        assert dlg.edit_user_name.text() == "Test User"
        assert dlg.spin_max_undos.value() == 50
        assert dlg.edit_pw_open.text() == "secret123"

        # Modify values
        dlg.chk_startup_pane.setChecked(True)
        dlg.edit_user_name.setText("Admin")
        dlg.spin_max_undos.setValue(80)

        out_opts = dlg.get_options()
        assert out_opts["startup_pane"] is True
        assert out_opts["user_name"] == "Admin"
        assert out_opts["max_undos"] == 80

        dlg.retranslate_ui()
        assert "选项" in dlg.windowTitle()


class TestLecternWindowIntegration:
    def test_lectern_window_task_panes_and_actions(self, app):
        win = LecternWindow()
        dock = win.task_pane_dock
        assert dock is not None

        # Verify panes registration
        assert dock.get_pane("slide_design") is not None
        assert dock.get_pane("color_schemes") is not None
        assert dock.get_pane("animation_schemes") is not None

        # Switch to slide_design
        win.open_slide_design_pane()
        assert dock.current_pane_id() == "slide_design"

        # Switch to color_schemes
        win.open_color_schemes_pane()
        assert dock.current_pane_id() == "color_schemes"

        # Switch to animation_schemes
        win.open_animation_schemes_pane()
        assert dock.current_pane_id() == "animation_schemes"

        # Test design template application
        win._on_apply_design_template("azure", apply_to_all=True)
        pres = win.presentation_view.presentation
        assert any("azure" in d.key for d in pres.designs.values())

        # Test animation scheme application
        win._on_apply_animation_scheme("fade_all", apply_to_all=True)
        for s in pres.slides:
            assert getattr(s, "animation_scheme", None) == "fade_all"

        # Retranslate
        win.retranslate_ui()
        win.close()
