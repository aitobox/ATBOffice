"""Tests for Slide Sorter View and Master View switching in Lectern."""

from __future__ import annotations

import pytest

from atboffice.modules.presentation.models.designs import build_design
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Fill, Shape
from atboffice.modules.presentation.models.slide import Transition
from atboffice.modules.presentation.models.text import TextBody
from atboffice.modules.presentation.view import PresentationView
from atboffice.modules.presentation.views.sorter_view import (
    SlideSorterCard,
    SlideSorterView,
)
from atboffice.modules.presentation.views.workspace import (
    LecternWorkspace,
    build_master_slide,
    sync_master_slide,
)


@pytest.fixture
def sample_presentation() -> Presentation:
    """Create a sample presentation with 4 slides having different properties."""
    pres = Presentation.create_new(title="Sorter Test Pres", empty=True)
    d = build_design("default", pres.w, pres.h)
    pres.designs[d.id] = d

    # Slide 1: Normal title
    s1 = pres.add_slide(layout="title", design_id=d.id)
    s1.shapes[0].text = TextBody.from_plain_text("Slide One")

    # Slide 2: Has transition and timing
    s2 = pres.add_slide(layout="text", design_id=d.id)
    s2.shapes[0].text = TextBody.from_plain_text("Slide Two")
    s2.transition = Transition(type="wipe", speed="med", after=5.0)

    # Slide 3: Hidden slide
    s3 = pres.add_slide(layout="text", design_id=d.id)
    s3.shapes[0].text = TextBody.from_plain_text("Slide Three Hidden")
    s3.hidden = True

    # Slide 4: Regular slide
    s4 = pres.add_slide(layout="text", design_id=d.id)
    s4.shapes[0].text = TextBody.from_plain_text("Slide Four")

    return pres


def test_slide_sorter_card_rendering(qtbot, sample_presentation: Presentation) -> None:
    """Test SlideSorterCard thumbnail, sequence number, and transition badges."""
    s1 = sample_presentation.slides[0]
    card1 = SlideSorterCard(slide=s1, index=0, presentation=sample_presentation)
    qtbot.addWidget(card1)
    card1.show()

    assert card1.number_label.text() == "1"
    assert card1.star_label is None or not card1.star_label.isVisible()
    assert card1.time_label is None or not card1.time_label.isVisible()
    assert not card1.is_hidden_slide

    # Slide 2 has transition and timing
    s2 = sample_presentation.slides[1]
    card2 = SlideSorterCard(slide=s2, index=1, presentation=sample_presentation)
    qtbot.addWidget(card2)
    card2.show()

    assert card2.number_label.text() == "2"
    assert card2.star_label is not None and card2.star_label.isVisible()
    assert "wipe" in card2.star_label.toolTip().lower()
    assert card2.time_label is not None and card2.time_label.isVisible()
    assert "00:05" in card2.time_label.text()

    # Slide 3 is hidden
    s3 = sample_presentation.slides[2]
    card3 = SlideSorterCard(slide=s3, index=2, presentation=sample_presentation)
    qtbot.addWidget(card3)
    card3.show()

    assert card3.is_hidden_slide
    assert card3.hidden_badge is not None and card3.hidden_badge.isVisible()


def test_slide_sorter_card_selection(qtbot, sample_presentation: Presentation) -> None:
    """Test selection toggling on SlideSorterCard."""
    s1 = sample_presentation.slides[0]
    card = SlideSorterCard(slide=s1, index=0, presentation=sample_presentation)
    qtbot.addWidget(card)
    card.show()

    assert not card.is_selected
    card.set_selected(True)
    assert card.is_selected
    card.set_selected(False)
    assert not card.is_selected


def test_slide_sorter_view_population(qtbot, sample_presentation: Presentation) -> None:
    """Test populating SlideSorterView with slides and selection handling."""
    view = SlideSorterView(presentation=sample_presentation)
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()

    assert len(view.cards) == 4
    assert view.get_selected_indices() == {0}

    # Select single
    view.select_slide(2)
    assert view.get_selected_indices() == {2}

    # Range selection (Shift)
    view.select_range(1, 3)
    assert view.get_selected_indices() == {1, 2, 3}

    # Toggle selection (Ctrl)
    view.toggle_slide_selection(0)
    assert view.get_selected_indices() == {0, 1, 2, 3}
    view.toggle_slide_selection(2)
    assert view.get_selected_indices() == {0, 1, 3}


def test_slide_sorter_view_reordering(qtbot, sample_presentation: Presentation) -> None:
    """Test moving slides within SlideSorterView."""
    view = SlideSorterView(presentation=sample_presentation)
    qtbot.addWidget(view)
    view.show()

    # Initial order of slide IDs
    initial_ids = [s.id for s in sample_presentation.slides]

    # Move slide at index 0 to index 3
    view.move_slides([0], 3)
    new_ids = [s.id for s in sample_presentation.slides]
    assert new_ids == [initial_ids[1], initial_ids[2], initial_ids[0], initial_ids[3]]

    # Multi-slide move
    # Move indices 0 and 1 to index 4 (end)
    view.move_slides([0, 1], 4)
    expected_ids = [new_ids[2], new_ids[3], new_ids[0], new_ids[1]]
    assert [s.id for s in sample_presentation.slides] == expected_ids


def test_slide_sorter_view_empty_presentation(qtbot) -> None:
    """Test SlideSorterView handles empty presentations gracefully."""
    empty_pres = Presentation.create_new(title="Empty", empty=True)
    view = SlideSorterView(presentation=empty_pres)
    qtbot.addWidget(view)
    view.show()

    assert len(view.cards) == 0
    assert view.get_selected_indices() == set()


def test_slide_sorter_context_actions(qtbot, sample_presentation: Presentation) -> None:
    """Test duplicate, delete, and hide actions in sorter view."""
    view = SlideSorterView(presentation=sample_presentation)
    qtbot.addWidget(view)
    view.show()

    orig_count = len(sample_presentation.slides)
    view.select_slide(0)
    view.duplicate_selected_slides()
    assert len(sample_presentation.slides) == orig_count + 1

    # Toggle hide
    s0 = sample_presentation.slides[0]
    initial_hidden = s0.hidden
    view.select_slide(0)
    view.toggle_hide_selected_slides()
    assert s0.hidden != initial_hidden

    # Delete
    del_count = len(sample_presentation.slides)
    view.select_slide(del_count - 1)
    view.delete_selected_slides()
    assert len(sample_presentation.slides) == del_count - 1


def test_master_slide_build_and_sync(sample_presentation: Presentation) -> None:
    """Test building synthetic master slide and syncing edits back to design."""
    design = sample_presentation.get_design_for_slide(None)

    # Build slide master
    ms = build_master_slide(sample_presentation, design, master_kind="slide")
    assert ms.layout == "text"
    assert any(sh.placeholder and sh.placeholder.type == "title" for sh in ms.shapes)
    assert any(sh.placeholder and sh.placeholder.type == "body" for sh in ms.shapes)

    # Add a custom decoration shape to master slide
    custom_deco = Shape(
        id="custom_master_logo",
        type="shape",
        name="MasterLogo",
        x=20.0,
        y=20.0,
        w=100.0,
        h=40.0,
        fill=Fill.solid("#FF5500"),
    )
    ms.shapes.append(custom_deco)

    # Sync back to design
    sync_master_slide(sample_presentation, ms)

    # Verify design decorations contains custom_deco
    assert any(sh.id == "custom_master_logo" for sh in design.decorations)

    # Build title master
    tm = build_master_slide(sample_presentation, design, master_kind="title")
    assert tm.layout == "title"
    assert any(sh.placeholder and sh.placeholder.type == "ctrTitle" for sh in tm.shapes)
    assert any(sh.placeholder and sh.placeholder.type == "subTitle" for sh in tm.shapes)


def test_workspace_view_mode_switching(qtbot, sample_presentation: Presentation) -> None:
    """Test switching between normal, sorter, and master views in LecternWorkspace."""
    workspace = LecternWorkspace(presentation=sample_presentation)
    qtbot.addWidget(workspace)
    workspace.show()

    # Default is normal view
    assert workspace.view_mode == "normal"
    assert workspace.sorter_view is not None
    assert not workspace.sorter_view.isVisible()

    # Switch to sorter view
    workspace.set_view_mode("sorter")
    assert workspace.view_mode == "sorter"
    assert workspace.sorter_view.isVisible()

    # Double click in sorter view switches back to normal view
    workspace.sorter_view.slide_double_clicked.emit(2)
    assert workspace.view_mode == "normal"
    assert workspace.current_slide_index == 2

    # Switch to master view
    workspace.set_view_mode("master")
    assert workspace.view_mode == "master"
    assert workspace.master_close_bar.isVisible()

    # Exit master view
    workspace.exit_master_view()
    assert workspace.view_mode == "normal"
    assert not workspace.master_close_bar.isVisible()


def test_presentation_view_mode_api(qtbot, sample_presentation: Presentation) -> None:
    """Test PresentationView exposes view mode methods cleanly."""
    pv = PresentationView(presentation=sample_presentation)
    qtbot.addWidget(pv)
    pv.show()

    assert pv.view_mode == "normal"
    pv.set_view_mode("sorter")
    assert pv.view_mode == "sorter"
    pv.set_view_mode("normal")
    assert pv.view_mode == "normal"
