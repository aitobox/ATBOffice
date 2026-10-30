"""Unit and integration tests for SlideTransitionPane, AnimationPane, workspace integration and PPTX roundtrip."""

import copy
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Animation, Slide, Transition
from atboffice.modules.presentation.slideshow.transitions import (
    TRANSITION_CATALOGUE,
    list_transitions,
)
from atboffice.modules.presentation.views.animation_pane import AnimationPane
from atboffice.modules.presentation.views.transition_pane import SlideTransitionPane
from atboffice.modules.presentation.views.workspace import LecternWorkspace
from atboffice.modules.presentation.io.writer_slide import slide_to_xml
from atboffice.modules.presentation.io.pptx_reader import PptxReader
import xml.etree.ElementTree as ET


# ==============================================================================
# 1. SlideTransitionPane Unit Tests
# ==============================================================================


def test_transition_pane_catalogue_population(qtbot):
    """Verify that all 58 transition effects from catalogue are loaded."""
    pane = SlideTransitionPane()
    qtbot.addWidget(pane)

    assert pane.list_transitions.count() == len(TRANSITION_CATALOGUE)
    first_item = pane.list_transitions.item(0)
    assert first_item is not None
    # First item should be "none" / "无切换"
    eff_0 = first_item.data(Qt.ItemDataRole.UserRole)
    assert eff_0.key == "none"


def test_transition_pane_selection_and_modification(qtbot):
    """Verify selecting a transition updates the slide model and emits transitionChanged."""
    pane = SlideTransitionPane()
    qtbot.addWidget(pane)

    slide = Slide(id="s1")
    slide.transition = Transition(type="none")
    pane.set_slide(slide)

    signals_received = []
    pane.transitionChanged.connect(lambda t: signals_received.append(t))

    # Find and select blinds_horz
    blinds_row = -1
    for row in range(pane.list_transitions.count()):
        it = pane.list_transitions.item(row)
        eff = it.data(Qt.ItemDataRole.UserRole)
        if eff.key == "blinds_horz":
            blinds_row = row
            break
    assert blinds_row >= 0

    pane.list_transitions.setCurrentRow(blinds_row)
    assert slide.transition.type == "blinds"
    assert slide.transition.dir == "horz"
    assert len(signals_received) >= 1
    assert signals_received[-1].type == "blinds"


def test_transition_pane_speed_and_timing(qtbot):
    """Verify speed dropdown, advance on click, and advance automatically timing."""
    pane = SlideTransitionPane()
    qtbot.addWidget(pane)

    slide = Slide(id="s1")
    slide.transition = Transition(type="fade", speed="fast", click=True, after=None)
    pane.set_slide(slide)

    # 1. Change speed to "Slow" (慢速)
    slow_idx = pane.combo_speed.findData("slow")
    assert slow_idx >= 0
    pane.combo_speed.setCurrentIndex(slow_idx)
    assert slide.transition.speed == "slow"

    # 2. Advance timing
    pane.chk_on_click.setChecked(False)
    assert slide.transition.click is False

    pane.chk_auto_after.setChecked(True)
    pane.spin_after_secs.setValue(3.5)
    assert slide.transition.after == pytest.approx(3.5)

    # Unchecking auto after clears the timer
    pane.chk_auto_after.setChecked(False)
    assert slide.transition.after is None


def test_transition_pane_apply_to_all(qtbot):
    """Verify 'Apply to All' propagates the current transition to all presentation slides."""
    pane = SlideTransitionPane()
    qtbot.addWidget(pane)

    pres = Presentation()
    s1 = Slide(id="s1", transition=Transition(type="dissolve", speed="med"))
    s2 = Slide(id="s2", transition=Transition(type="none"))
    s3 = Slide(id="s3", transition=Transition(type="cut"))
    pres.slides.extend([s1, s2, s3])

    pane.set_presentation(pres)
    pane.set_slide(s1)

    apply_signals = []
    pane.applyToAllRequested.connect(lambda t: apply_signals.append(t))

    pane.btn_apply_to_all.click()

    assert len(apply_signals) == 1
    assert s2.transition.type == "dissolve"
    assert s2.transition.speed == "med"
    assert s3.transition.type == "dissolve"
    assert s3.transition.speed == "med"


def test_transition_pane_signals_and_retranslate(qtbot):
    """Verify Play, SlideShow signals, and UI retranslation."""
    pane = SlideTransitionPane()
    qtbot.addWidget(pane)

    slide = Slide(id="s1", transition=Transition(type="push", dir="d"))
    pane.set_slide(slide)

    preview_events = []
    slideshow_events = []
    pane.previewRequested.connect(lambda: preview_events.append(True))
    pane.slideshowRequested.connect(lambda: slideshow_events.append(True))

    pane.btn_play.click()
    assert len(preview_events) == 1

    pane.btn_slideshow.click()
    assert len(slideshow_events) == 1

    # Retranslate
    pane.retranslate_ui()
    assert "切换" in pane.lbl_title.text() or "Transition" in pane.lbl_title.text()
    assert pane.btn_apply_to_all.text() != ""


# ==============================================================================
# 2. AnimationPane Enhanced Unit Tests
# ==============================================================================


def test_animation_pane_effects_and_timing(qtbot):
    """Verify adding effects, delay setting, reordering, and retranslation in AnimationPane."""
    pane = AnimationPane()
    qtbot.addWidget(pane)

    slide = Slide(id="s1")
    sh1 = Shape(id="sh1", name="Title Box")
    sh2 = Shape(id="sh2", name="Subtitle")
    slide.shapes.extend([sh1, sh2])
    pane.set_slide(slide, selected_shape_ids=["sh1"])

    # 1. Add entrance effect
    pane._on_add_effect_chosen("entr", "flyIn")
    assert len(slide.animations) == 1
    anim1 = slide.animations[0]
    assert anim1.sid == "sh1"
    assert anim1.eff == "flyIn"

    # 2. Add exit effect to sh2
    pane.selected_shape_ids = ["sh2"]
    pane._on_add_effect_chosen("exit", "flyOut")
    assert len(slide.animations) == 2
    anim2 = slide.animations[1]
    assert anim2.sid == "sh2"
    assert anim2.eff == "flyOut"

    # 3. Test delay adjustment
    pane.list_anims.setCurrentRow(0)
    assert hasattr(pane, "spin_delay")
    pane.spin_delay.setValue(1.5)
    assert slide.animations[0].delay == pytest.approx(1500)

    # 4. Reorder effects (move anim2 up)
    pane.list_anims.setCurrentRow(1)
    pane._move_animation(-1)
    assert slide.animations[0].id == anim2.id
    assert slide.animations[1].id == anim1.id

    # 5. Retranslate UI
    pane.retranslate_ui()
    assert pane.lbl_title.text() != ""


def test_animation_pane_shape_bidirectional_sync(qtbot):
    """Verify selecting a shape highlights its animation, and selecting an animation signals shape selection."""
    pane = AnimationPane()
    qtbot.addWidget(pane)

    slide = Slide(id="s1")
    sh1 = Shape(id="sh1", name="Card 1")
    sh2 = Shape(id="sh2", name="Card 2")
    slide.shapes.extend([sh1, sh2])

    a1 = Animation(id="a1", sid="sh1", cls="entr", eff="appear")
    a2 = Animation(id="a2", sid="sh2", cls="entr", eff="zoom")
    slide.animations.extend([a1, a2])

    shape_selected_signals = []
    pane.shapeSelectionRequested.connect(lambda sid: shape_selected_signals.append(sid))

    pane.set_slide(slide)

    # Select shape sh2 -> should highlight item for a2 in list
    pane.set_selected_shapes(["sh2"])
    assert pane.list_anims.currentRow() == 1

    # Select row 0 (a1) -> emits shapeSelectionRequested("sh1")
    pane.list_anims.setCurrentRow(0)
    assert "sh1" in shape_selected_signals


# ==============================================================================
# 3. LecternTaskPane & Workspace Integration Tests
# ==============================================================================


def test_workspace_task_pane_transitions_and_animations(qtbot):
    """Verify LecternWorkspace integrates SlideTransitionPane and AnimationPane seamlessly."""
    pres = Presentation.create_new()
    ws = LecternWorkspace(presentation=pres)
    qtbot.addWidget(ws)

    # Check task pane registration
    tp = ws.task_pane
    assert "transition" in tp.panes
    assert "customAnim" in tp.panes
    assert isinstance(tp.panes["transition"], SlideTransitionPane)
    assert isinstance(tp.panes["customAnim"], AnimationPane)

    # Switch to transition pane
    tp.show_pane("transition")
    assert tp.current_pane_id == "transition"
    assert tp.stack.currentWidget() == tp.panes["transition"]

    # Switch to custom animation pane
    tp.show_pane("customAnim")
    assert tp.current_pane_id == "customAnim"
    assert tp.stack.currentWidget() == tp.panes["customAnim"]

    # Switch active slide updates panes
    s2 = Slide(id="s2")
    s2.transition = Transition(type="wipe", dir="l")
    s2.shapes.append(Shape(id="sh_s2", name="Body"))
    s2.animations.append(Animation(id="a_s2", sid="sh_s2", cls="entr", eff="fade"))
    pres.slides.append(s2)

    ws.set_current_slide_index(1)
    trans_pane: SlideTransitionPane = tp.panes["transition"]
    anim_pane: AnimationPane = tp.panes["customAnim"]

    assert trans_pane.slide == s2
    assert anim_pane.slide == s2
    assert anim_pane.list_anims.count() == 1


# ==============================================================================
# 4. PPTX I/O Persistence & Roundtrip Tests
# ==============================================================================


def test_pptx_transition_and_animation_xml_roundtrip():
    """Verify transitions and shape animations serialize to PresentationML XML and deserialize cleanly."""
    slide = Slide(id="s1")
    sh = Shape(id="sh1", name="Diagram")
    slide.shapes.append(sh)

    # Set transition
    slide.transition = Transition(
        type="comb",
        speed="med",
        click=True,
        after=2.5,
        dir="vert",
    )

    # Set animations
    a1 = Animation(
        id="a1",
        sid="sh1",
        cls="entr",
        eff="flyIn",
        dir="b",
        start="click",
        dur=1000,
        delay=500,
    )
    slide.animations.append(a1)

    xml_str = slide_to_xml(slide)
    assert "<p:transition" in xml_str
    assert 'spd="med"' in xml_str
    assert 'advTm="2500"' in xml_str
    assert "<p:comb" in xml_str
    assert 'dir="vert"' in xml_str

    assert "<p:timing>" in xml_str
    assert 'presetClass="entr"' in xml_str

    # Parse back using PptxReader helpers
    root = ET.fromstring(xml_str)
    reader = PptxReader.__new__(PptxReader)
    parsed_trans = reader._parse_transition(root.find("{http://schemas.openxmlformats.org/presentationml/2006/main}transition"))
    assert parsed_trans.type == "comb"
    assert parsed_trans.dir == "vert"
    assert parsed_trans.speed == "med"
    assert parsed_trans.after == pytest.approx(2.5)

    timing_elem = root.find("{http://schemas.openxmlformats.org/presentationml/2006/main}timing")
    # In PPTX, shapes are parsed from <p:sp> whose id becomes the numeric spid
    sp_elem = root.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}sp")
    parsed_shape = reader._parse_sp_element(sp_elem)
    parsed_anims = reader._parse_slide_animations(timing_elem, [parsed_shape])
    assert len(parsed_anims) >= 1
    assert parsed_anims[0].cls == "entr"
    assert parsed_anims[0].sid == parsed_shape.id
