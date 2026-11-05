"""Unit and integration tests for Lectern's 4 presentation templates."""

import tempfile
from pathlib import Path

import pytest

from atboffice.core.templates import TemplateRegistry
from atboffice.modules.presentation.io.pptx_reader import read_pptx
from atboffice.modules.presentation.io.pptx_writer import write_pptx
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.templates import (
    LECTERN_TEMPLATE_IDS,
    LECTERN_TEMPLATE_NAMES,
    build_lectern_template,
)
from atboffice.ui.shell.lectern_window import LecternWindow


def test_lectern_template_ids_and_names():
    """Verify LECTERN_TEMPLATE_IDS contains the canonical 4 templates."""
    assert len(LECTERN_TEMPLATE_IDS) == 4
    assert set(LECTERN_TEMPLATE_IDS) == {"status", "meeting", "lesson", "event"}
    for tid in LECTERN_TEMPLATE_IDS:
        assert tid in LECTERN_TEMPLATE_NAMES
        assert len(LECTERN_TEMPLATE_NAMES[tid]) > 0


def test_invalid_template_id_raises_key_error():
    """Verify build_lectern_template raises KeyError for unknown template ID."""
    with pytest.raises(KeyError, match="Unknown Lectern template identifier"):
        build_lectern_template("invalid_id")


def test_status_template():
    """Verify Project Status Report template: 7 slides, blueprint design,
    chevron SmartArt, and milestones table.
    """
    pres = build_lectern_template("status")
    assert isinstance(pres, Presentation)
    assert len(pres.slides) == 7

    # Design
    design = pres.get_design_for_slide(None)
    assert design.key == "blueprint"

    # Slide 1: Title
    s1 = pres.slides[0]
    t1 = next(
        sh for sh in s1.shapes if sh.placeholder and sh.placeholder.type in ("ctrTitle", "title")
    )
    assert t1.text.plain_text == "Project Name"

    # Slide 3: Chevron SmartArt
    s3 = pres.slides[2]
    sa_shape = next((sh for sh in s3.shapes if sh.sa is not None), None)
    assert sa_shape is not None
    assert sa_shape.sa["layout"] == "chevron"
    assert len(sa_shape.kids) == 4
    texts = [k.text.plain_text for k in sa_shape.kids if k.text]
    assert "Discover" in texts
    assert "Launch" in texts

    # Slide 4: Milestones Table
    s4 = pres.slides[3]
    tbl_shape = next((sh for sh in s4.shapes if sh.type == "table" or bool(sh.tbl)), None)
    assert tbl_shape is not None
    tbl_data = tbl_shape.tbl
    assert len(tbl_data["rows"]) == 5
    assert len(tbl_data["cols"]) == 4
    assert tbl_data["rows"][0]["cells"][0]["text"] == "Milestone"
    assert tbl_data["rows"][4]["cells"][0]["text"] == "Launch"

    # Transition
    for s in pres.slides:
        assert s.transition.type == "fade"


def test_meeting_template():
    """Verify Team Meeting template: 6 slides, meadow design, vProcess SmartArt."""
    pres = build_lectern_template("meeting")
    assert isinstance(pres, Presentation)
    assert len(pres.slides) == 6

    # Design
    design = pres.get_design_for_slide(None)
    assert design.key == "meadow"

    # Slide 2: vProcess SmartArt
    s2 = pres.slides[1]
    sa_shape = next((sh for sh in s2.shapes if sh.sa is not None), None)
    assert sa_shape is not None
    assert sa_shape.sa["layout"] == "vProcess"
    assert len(sa_shape.kids) > 0


def test_lesson_template():
    """Verify Lesson template: 6 slides, parchment design, radial SmartArt."""
    pres = build_lectern_template("lesson")
    assert isinstance(pres, Presentation)
    assert len(pres.slides) == 6

    # Design
    design = pres.get_design_for_slide(None)
    assert design.key == "parchment"

    # Slide 3: Radial SmartArt
    s3 = pres.slides[2]
    sa_shape = next((sh for sh in s3.shapes if sh.sa is not None), None)
    assert sa_shape is not None
    assert sa_shape.sa["layout"] == "radial"
    assert len(sa_shape.kids) > 0


def test_event_template():
    """Verify Event Announcement template: 5 slides, night design, timeline SmartArt."""
    pres = build_lectern_template("event")
    assert isinstance(pres, Presentation)
    assert len(pres.slides) == 5

    # Design
    design = pres.get_design_for_slide(None)
    assert design.key == "night"

    # Slide 3: Timeline SmartArt
    s3 = pres.slides[2]
    sa_shape = next((sh for sh in s3.shapes if sh.sa is not None), None)
    assert sa_shape is not None
    assert sa_shape.sa["layout"] == "timeline"
    assert len(sa_shape.kids) > 0


def test_pptx_serialization_roundtrip():
    """Verify all 4 templates serialize to PPTX and deserialize without error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for tid in LECTERN_TEMPLATE_IDS:
            pres = build_lectern_template(tid)
            pptx_path = Path(tmpdir) / f"{tid}.pptx"
            write_pptx(pres, pptx_path)
            assert pptx_path.exists()
            assert pptx_path.stat().st_size > 5000

            loaded = read_pptx(pptx_path)
            assert isinstance(loaded, Presentation)
            assert len(loaded.slides) == len(pres.slides)


def test_template_registry_integration():
    """Verify TemplateRegistry has registered callable builders for all 4 Lectern templates."""
    reg = TemplateRegistry.get_instance()
    for tid in LECTERN_TEMPLATE_IDS:
        tpl = reg.get(tid, app="lectern")
        assert tpl is not None
        assert tpl.app == "lectern"
        assert callable(tpl.builder)
        built = tpl.builder()
        assert isinstance(built, Presentation)
        assert len(built.slides) >= 5


def test_lectern_window_load_template(qtbot):
    """Verify LecternWindow loads template, sets presentation model, and updates title."""
    win = LecternWindow()
    qtbot.addWidget(win)

    loaded = win.load_template("status")
    assert loaded is True
    assert win.active_template is not None
    assert win.active_template.id == "status"
    assert len(win.presentation.slides) == 7
    assert "项目状态汇报" in win.windowTitle() or "Project Status Report" in win.windowTitle()

    # Reset with new_file
    win.new_file()
    assert win.active_template is None
    assert len(win.presentation.slides) == 1
