"""GUI and integration tests for Lectern classic three-pane workspace."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.designs import build_design
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import Paragraph, TextBody
from atboffice.modules.presentation.view import PresentationView
from atboffice.modules.presentation.views.workspace import (
    LecternTaskPane,
    LecternWorkspace,
    OutlineEditorWidget,
    SlideDesignPane,
    SlideLayoutPane,
    SlideThumbnailList,
    SpeakerNotesPane,
)


@pytest.fixture
def sample_presentation() -> Presentation:
    """Create a sample presentation with 3 distinct slides."""
    pres = Presentation.create_new(title="Demo Presentation", empty=True)
    d = build_design("default", pres.w, pres.h)
    pres.designs[d.id] = d

    # Slide 1: Title
    s1 = pres.add_slide(layout="title", design_id=d.id)
    title_sh = s1.shapes[0]
    title_sh.text = TextBody.from_plain_text("First Slide Title")
    s1.notes = "Notes for slide 1"

    # Slide 2: Text
    s2 = pres.add_slide(layout="text", design_id=d.id)
    s2.shapes[0].text = TextBody.from_plain_text("Second Slide Title")
    if len(s2.shapes) > 1:
        s2.shapes[1].text = TextBody.from_plain_text("Bullet item A\nBullet item B")
    s2.notes = "Notes for slide 2"

    # Slide 3: Two text
    s3 = pres.add_slide(layout="twoText", design_id=d.id)
    s3.shapes[0].text = TextBody.from_plain_text("Third Slide Title")
    s3.notes = "Notes for slide 3"

    return pres


def test_workspace_initialization(qtbot, sample_presentation: Presentation) -> None:
    workspace = LecternWorkspace(presentation=sample_presentation)
    qtbot.addWidget(workspace)
    workspace.show()

    assert workspace.presentation == sample_presentation
    assert workspace.current_slide_index == 0
    assert workspace.left_pane is not None
    assert workspace.thumbnail_list is not None
    assert workspace.outline_editor is not None
    assert workspace.canvas_view is not None
    assert workspace.notes_pane is not None
    assert workspace.task_pane is not None

    # Check thumbnails count
    assert workspace.thumbnail_list.count() == 3


def test_slide_navigation(qtbot, sample_presentation: Presentation) -> None:
    workspace = LecternWorkspace(presentation=sample_presentation)
    qtbot.addWidget(workspace)
    workspace.show()

    # Switch to slide 1
    workspace.set_current_slide_index(1)
    assert workspace.current_slide_index == 1
    assert workspace.current_slide == sample_presentation.slides[1]
    assert workspace.notes_pane.to_plain_text() == "Notes for slide 2"
    assert workspace.canvas_view.scene().slide == sample_presentation.slides[1]

    # Switch to slide 2
    workspace.set_current_slide_index(2)
    assert workspace.current_slide_index == 2
    assert workspace.notes_pane.to_plain_text() == "Notes for slide 3"


def test_thumbnail_reordering(qtbot, sample_presentation: Presentation) -> None:
    workspace = LecternWorkspace(presentation=sample_presentation)
    qtbot.addWidget(workspace)
    workspace.show()

    slide0 = sample_presentation.slides[0]
    slide1 = sample_presentation.slides[1]
    slide2 = sample_presentation.slides[2]

    # Move slide 0 to index 2
    workspace.move_slide(0, 2)
    assert sample_presentation.slides[0] == slide1
    assert sample_presentation.slides[1] == slide2
    assert sample_presentation.slides[2] == slide0

    assert workspace.thumbnail_list.count() == 3


def test_speaker_notes_binding(qtbot, sample_presentation: Presentation) -> None:
    workspace = LecternWorkspace(presentation=sample_presentation)
    qtbot.addWidget(workspace)
    workspace.show()

    assert workspace.notes_pane.to_plain_text() == "Notes for slide 1"

    # User modifies notes in editor
    workspace.notes_pane.set_plain_text("Updated notes from user typing")
    assert sample_presentation.slides[0].notes == "Updated notes from user typing"

    # Switch to slide 1
    workspace.set_current_slide_index(1)
    assert workspace.notes_pane.to_plain_text() == "Notes for slide 2"

    # Switch back to slide 0
    workspace.set_current_slide_index(0)
    assert workspace.notes_pane.to_plain_text() == "Updated notes from user typing"


def test_outline_synchronization(qtbot, sample_presentation: Presentation) -> None:
    workspace = LecternWorkspace(presentation=sample_presentation)
    qtbot.addWidget(workspace)
    workspace.show()

    # Verify outline contains slide titles
    outline_text = workspace.outline_editor.to_plain_text()
    assert "First Slide Title" in outline_text
    assert "Second Slide Title" in outline_text

    # Update slide title through outline editor API
    workspace.outline_editor.update_slide_title(0, "New Outline Title")
    slide0_title = sample_presentation.slides[0].shapes[0].text.to_plain_text()
    assert "New Outline Title" in slide0_title


def test_task_pane_layout_and_design(qtbot, sample_presentation: Presentation) -> None:
    workspace = LecternWorkspace(presentation=sample_presentation)
    qtbot.addWidget(workspace)
    workspace.show()

    task_pane = workspace.task_pane
    assert task_pane is not None

    # Show layout pane
    task_pane.show_pane("layout")
    assert task_pane.current_pane_id == "layout"

    layout_pane = task_pane.get_pane("layout")
    assert isinstance(layout_pane, SlideLayoutPane)
    assert len(layout_pane.layout_cards) == 21

    # Apply layout 'blank' to current slide
    layout_pane.apply_layout("blank")
    assert workspace.current_slide.layout == "blank"

    # Show design pane
    task_pane.show_pane("design")
    assert task_pane.current_pane_id == "design"

    design_pane = task_pane.get_pane("design")
    assert isinstance(design_pane, SlideDesignPane)
    assert len(design_pane.design_cards) >= 15

    # Navigation history
    task_pane.go_back()
    assert task_pane.current_pane_id == "layout"
    task_pane.go_forward()
    assert task_pane.current_pane_id == "design"

    # Close and open task pane
    task_pane.close_pane()
    assert task_pane.isHidden()
    workspace.toggle_task_pane(True)
    assert not task_pane.isHidden()


def test_presentation_view_integration(qtbot, sample_presentation: Presentation) -> None:
    view = PresentationView(presentation=sample_presentation)
    qtbot.addWidget(view)
    view.show()

    assert view.workspace is not None
    assert view.workspace.presentation == sample_presentation

    # Load new presentation
    new_pres = Presentation.create_new(title="Another Pres")
    view.load_presentation(new_pres)
    assert view.workspace.presentation == new_pres
    assert view.workspace.thumbnail_list.count() == 1


def test_retranslate_ui(qtbot, sample_presentation: Presentation) -> None:
    workspace = LecternWorkspace(presentation=sample_presentation)
    qtbot.addWidget(workspace)
    workspace.show()

    # Retranslate shouldn't crash and should update UI text
    workspace.retranslate_ui()
    assert workspace.left_pane.tabText(0) in ("幻灯片", "Slides")
    assert workspace.left_pane.tabText(1) in ("大纲", "Outline")
