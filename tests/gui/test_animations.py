"""Comprehensive tests for custom animations engine, timing task pane, and slideshow stepping."""

import pytest
from PySide6.QtCore import QRectF

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Animation, Slide
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun
from atboffice.modules.presentation.slideshow.animations import (
    DIR4,
    DIR8,
    E_EMPH,
    E_ENTR,
    E_EXIT,
    E_PATH,
    HV,
    INOUT,
    SPEEDS,
    AnimationItem,
    AnimationStep,
    AnimationStepPlayer,
    apply_initial_state,
    apply_step_state,
    clamp,
    compile_steps,
    compute_frame,
    default_dir,
    ease_in_out,
    ease_out,
    effect_display_name,
    find_effect,
    list_effects,
    path_points,
    safe_tr,
)
from atboffice.modules.presentation.slideshow.slideshow_view import SlideShowView
from atboffice.modules.presentation.views.animation_pane import AnimationPane

# ==============================================================================
# 1. Catalogue & Metadata Tests
# ==============================================================================


def test_catalogue_counts():
    """Verify that there are 50+ total effect definitions across all 4 categories."""
    assert len(E_ENTR) >= 22
    assert len(E_EMPH) >= 5
    assert len(E_EXIT) >= 17
    assert len(E_PATH) >= 8

    total_effects = len(E_ENTR) + len(E_EMPH) + len(E_EXIT) + len(E_PATH)
    assert total_effects >= 50

    # Ensure list_effects maps correctly
    assert list_effects("entr") == E_ENTR
    assert list_effects("emph") == E_EMPH
    assert list_effects("exit") == E_EXIT
    assert list_effects("path") == E_PATH


def test_catalogue_directions_and_speeds():
    """Verify direction lists and speed presets."""
    assert len(DIR8) == 8
    assert len(DIR4) == 4
    assert len(HV) == 2
    assert len(INOUT) == 2
    assert len(SPEEDS) == 5

    # Check flyIn has 8 directions
    fly_in = find_effect("entr", "flyIn")
    assert fly_in is not None
    assert fly_in.dirs == DIR8
    assert default_dir("entr", "flyIn") == "b"

    # Check wipe has 4 directions
    wipe = find_effect("entr", "wipe")
    assert wipe is not None
    assert wipe.dirs == DIR4

    # Check speeds values
    speed_map = dict(SPEEDS)
    assert speed_map["Very Slow"] == 5000
    assert speed_map["Slow"] == 3000
    assert speed_map["Medium"] == 2000
    assert speed_map["Fast"] == 1000
    assert speed_map["Very Fast"] == 500


def test_safe_tr_and_display_name():
    """Verify localization translation lookup."""
    assert safe_tr("Entrance") == "进入"
    assert safe_tr("Fly In") == "飞入"
    assert safe_tr("On Click") == "单击时"
    assert safe_tr("Re-Order") == "重新排序"

    name_entr = effect_display_name("entr", "flyIn")
    assert "飞入" in name_entr or "Fly In" in name_entr


# ==============================================================================
# 2. Math & Easing Functions
# ==============================================================================


def test_easing_curves():
    """Test boundary and midpoint behaviors of easing algorithms."""
    assert ease_out(0.0) == pytest.approx(0.0)
    assert ease_out(1.0) == pytest.approx(1.0)
    assert ease_out(0.5) > 0.5  # Ease-out decelerates

    assert ease_in_out(0.0) == pytest.approx(0.0)
    assert ease_in_out(0.5) == pytest.approx(0.5)
    assert ease_in_out(1.0) == pytest.approx(1.0)
    assert ease_in_out(0.25) < 0.25  # Ease-in part

    assert clamp(-5.0, 0.0, 1.0) == 0.0
    assert clamp(1.5, 0.0, 1.0) == 1.0
    assert clamp(0.7, 0.0, 1.0) == 0.7


def test_motion_path_points():
    """Test 2D trajectory generation for motion paths."""
    anim_right = Animation(id="a1", sid="s1", cls="path", eff="right")
    pts_r = path_points(anim_right)
    assert len(pts_r) == 2
    assert pts_r[0] == [0.0, 0.0]
    assert pts_r[1] == [0.25, 0.0]

    anim_circle = Animation(id="a2", sid="s1", cls="path", eff="circle")
    pts_c = path_points(anim_circle)
    assert len(pts_c) == 25

    anim_bounce = Animation(id="a3", sid="s1", cls="path", eff="bounce")
    pts_b = path_points(anim_bounce)
    assert len(pts_b) == 21


# ==============================================================================
# 3. Frame Computation Tests
# ==============================================================================


def test_compute_frame_entrance():
    """Test frame states for Entrance animations."""
    bounds = QRectF(100, 100, 200, 100)

    # Appear: hidden until progress reaches 1.0
    anim_appear = Animation(id="a1", sid="s1", cls="entr", eff="appear")
    f0 = compute_frame(anim_appear, 0.0, bounds)
    assert f0.visible is False
    f1 = compute_frame(anim_appear, 1.0, bounds)
    assert f1.visible is True

    # Fade: opacity scales with progress
    anim_fade = Animation(id="a2", sid="s1", cls="entr", eff="fade")
    f_fade0 = compute_frame(anim_fade, 0.0, bounds)
    f_fade5 = compute_frame(anim_fade, 0.5, bounds)
    f_fade1 = compute_frame(anim_fade, 1.0, bounds)
    assert f_fade0.opacity == pytest.approx(0.0)
    assert 0.0 < f_fade5.opacity < 1.0
    assert f_fade1.opacity == pytest.approx(1.0)

    # Fly In from bottom ('b')
    anim_fly = Animation(id="a3", sid="s1", cls="entr", eff="flyIn", dir="b")
    f_fly0 = compute_frame(anim_fly, 0.0, bounds, slide_w=960, slide_h=540)
    f_fly1 = compute_frame(anim_fly, 1.0, bounds, slide_w=960, slide_h=540)
    assert f_fly0.translate_y > 0  # Starts offscreen below
    assert f_fly1.translate_y == pytest.approx(0.0)

    # Zoom
    anim_zoom = Animation(id="a4", sid="s1", cls="entr", eff="zoom")
    f_zoom0 = compute_frame(anim_zoom, 0.0, bounds)
    f_zoom1 = compute_frame(anim_zoom, 1.0, bounds)
    assert f_zoom0.scale_x < 0.01
    assert f_zoom1.scale_x == pytest.approx(1.0)


def test_compute_frame_emphasis():
    """Test frame states for Emphasis animations."""
    bounds = QRectF(100, 100, 200, 100)

    # Spin 360 degrees
    anim_spin = Animation(id="a1", sid="s1", cls="emph", eff="spin", amount=360.0)
    f_spin0 = compute_frame(anim_spin, 0.0, bounds)
    f_spin5 = compute_frame(anim_spin, 0.5, bounds)
    f_spin1 = compute_frame(anim_spin, 1.0, bounds)
    assert f_spin0.rotation == pytest.approx(0.0)
    assert f_spin5.rotation == pytest.approx(180.0)
    assert f_spin1.rotation == pytest.approx(360.0)

    # Grow/Shrink 150%
    anim_grow = Animation(id="a2", sid="s1", cls="emph", eff="growShrink", amount=150.0)
    f_grow1 = compute_frame(anim_grow, 1.0, bounds)
    assert f_grow1.scale_x == pytest.approx(1.5)
    assert f_grow1.scale_y == pytest.approx(1.5)


def test_compute_frame_motion_path():
    """Test frame states for Motion Paths."""
    bounds = QRectF(100, 100, 200, 100)
    anim_path = Animation(id="a1", sid="s1", cls="path", eff="right")
    f0 = compute_frame(anim_path, 0.0, bounds, slide_w=1000, slide_h=500)
    f1 = compute_frame(anim_path, 1.0, bounds, slide_w=1000, slide_h=500)
    assert f0.translate_x == pytest.approx(0.0)
    assert f1.translate_x == pytest.approx(250.0)  # 0.25 * 1000


# ==============================================================================
# 4. Step Compilation & Sequencing
# ==============================================================================


def test_compile_steps_grouping():
    """Test grouping animations by click, with, and after triggers."""
    slide = Slide(id="s1")
    sh1 = Shape(id="sh1", type="rect")
    sh2 = Shape(id="sh2", type="rect")
    sh3 = Shape(id="sh3", type="rect")
    slide.shapes.extend([sh1, sh2, sh3])

    # a1: on click
    a1 = Animation(id="a1", sid="sh1", cls="entr", eff="flyIn", start="click", dur=500)
    # a2: with previous
    a2 = Animation(id="a2", sid="sh2", cls="entr", eff="fade", start="with", dur=500)
    # a3: on click
    a3 = Animation(id="a3", sid="sh3", cls="exit", eff="flyOut", start="click", dur=500)
    slide.animations.extend([a1, a2, a3])

    steps = compile_steps(slide)
    assert len(steps) == 2
    # Step 0 contains a1 and a2
    assert len(steps[0].items) == 2
    assert steps[0].items[0].anim.id == "a1"
    assert steps[0].items[1].anim.id == "a2"
    assert steps[0].is_auto is False

    # Step 1 contains a3
    assert len(steps[1].items) == 1
    assert steps[1].items[0].anim.id == "a3"


def test_compile_steps_paragraph_expansion():
    """Test 'by=para' expands multi-paragraph text shapes into sub-items."""
    slide = Slide(id="s1")
    sh = Shape(id="sh_txt", type="text")
    sh.text = TextBody(
        paragraphs=[
            Paragraph(level=0, runs=[TextRun(text="First bullet")]),
            Paragraph(level=0, runs=[TextRun(text="Second bullet")]),
            Paragraph(level=1, runs=[TextRun(text="Third bullet")]),
        ]
    )
    slide.shapes.append(sh)

    a = Animation(id="a_para", sid="sh_txt", cls="entr", eff="fade", start="click", by="para")
    slide.animations.append(a)

    steps = compile_steps(slide)
    assert len(steps) >= 2  # Paragraph 1 starts step 0, Paragraph 2 starts step 1


def test_apply_initial_and_step_state():
    """Test initial and finished states calculation."""
    slide = Slide(id="s1")
    sh = Shape(id="sh1", type="rect")
    slide.shapes.append(sh)
    a = Animation(id="a1", sid="sh1", cls="entr", eff="fade", start="click")
    slide.animations.append(a)

    steps = compile_steps(slide)
    init_state = apply_initial_state(steps)
    assert init_state["sh1"].visible is False

    finished_state = apply_step_state(steps, 1)
    assert finished_state["sh1"].visible is True
    assert finished_state["sh1"].opacity == 1.0


# ==============================================================================
# 5. AnimationStepPlayer
# ==============================================================================


def test_animation_step_player(qtbot):
    """Test QTimer-driven step player execution and finish_now."""
    player = AnimationStepPlayer(slide_w=960, slide_h=540)
    step = AnimationStep(
        items=[
            AnimationItem(
                anim=Animation(id="a1", sid="sh1", cls="entr", eff="fade", dur=200),
                start=0,
                end=200,
                dur=200,
                shape_id="sh1",
            )
        ],
        total_duration=200,
    )

    frames_received = []
    player.frameChanged.connect(lambda f: frames_received.append(f))
    finished = []
    player.stepFinished.connect(lambda idx: finished.append(idx))

    player.play(step, 0, {}, {"sh1": QRectF(0, 0, 100, 100)})
    assert player.is_playing is True

    # Test finish_now immediately completes the step
    player.finish_now()
    assert player.is_playing is False
    assert len(finished) == 1
    assert finished[0] == 0


# ==============================================================================
# 6. AnimationPane GUI Tests
# ==============================================================================


def test_animation_pane_ui(qtbot):
    """Test AnimationPane interactions: adding, modifying, reordering, deleting."""
    pane = AnimationPane()
    qtbot.addWidget(pane)

    slide = Slide(id="s1")
    sh1 = Shape(id="sh1", name="Title Box")
    sh2 = Shape(id="sh2", name="Subtitle")
    slide.shapes.extend([sh1, sh2])

    pane.set_slide(slide, selected_shape_ids=["sh1"])

    # 1. Add Effect
    pane._on_add_effect_chosen("entr", "flyIn")
    assert len(slide.animations) == 1
    assert pane.list_anims.count() == 1
    assert slide.animations[0].eff == "flyIn"
    assert slide.animations[0].dir == "b"

    # Add second effect on sh2
    pane.selected_shape_ids = ["sh2"]
    pane._on_add_effect_chosen("emph", "spin")
    assert len(slide.animations) == 2
    assert pane.list_anims.count() == 2

    # 2. Reorder: move second effect up
    pane.list_anims.setCurrentRow(1)
    pane._move_animation(-1)
    assert slide.animations[0].eff == "spin"
    assert slide.animations[1].eff == "flyIn"

    # 3. Modify trigger and speed
    pane.list_anims.setCurrentRow(0)
    pane.combo_start.setCurrentIndex(1)  # With Previous
    assert slide.animations[0].start == "with"

    pane.combo_speed.setCurrentIndex(3)  # Fast (1000)
    assert slide.animations[0].dur == 1000

    # 4. Remove selected effect
    pane._on_remove_clicked()
    assert len(slide.animations) == 1
    assert pane.list_anims.count() == 1

    # 5. Retranslate UI
    pane.retranslate_ui()
    assert "添加效果" in pane.btn_add_effect.text() or "Add Effect" in pane.btn_add_effect.text()


# ==============================================================================
# 7. SlideShowView Animation Stepping Tests
# ==============================================================================


def test_slideshow_animation_stepping(qtbot):
    """Test SlideShowView stepping through animations before advancing slide."""
    pres = Presentation()
    slide1 = Slide(id="s1")
    sh = Shape(id="sh1", name="Title", x=100, y=100, w=400, h=100)
    slide1.shapes.append(sh)
    a1 = Animation(id="a1", sid="sh1", cls="entr", eff="flyIn", start="click", dur=300)
    slide1.animations.append(a1)

    slide2 = Slide(id="s2")
    pres.slides.extend([slide1, slide2])

    view = SlideShowView(pres, start_slide_index=0, fullscreen=False)
    qtbot.addWidget(view)

    # Initial state: slide1 has animations, step_idx is 0, entrance shape is hidden
    assert view.current_slide_index == 0
    assert len(view._anim_steps) == 1
    assert view._anim_step_idx == 0
    assert view._frame_states["sh1"].visible is False

    # Press space/next: triggers animation step 0 instead of switching to slide 2
    view.next_slide()
    assert view.current_slide_index == 0
    assert view._anim_player.is_playing is True

    # Finish animation now (rapid click)
    view.next_slide()
    assert view._anim_player.is_playing is False
    assert view._anim_step_idx == 1
    assert view._frame_states["sh1"].visible is True

    # Next click now advances to slide 2 because all animations on slide 1 are done
    view.next_slide()
    assert view.current_slide_index == 1

    # Prev slide goes back to slide 1
    view.prev_slide()
    assert view.current_slide_index == 0

    view.end_show()
