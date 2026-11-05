"""Tests for Quire built-in document templates."""

import pytest

from atboffice.core.templates import TemplateRegistry
from atboffice.modules.writer.models.document import Document, DocumentModel, Paragraph, Table
from atboffice.modules.writer.templates import (
    QUIRE_TEMPLATE_IDS,
    build_quire_template,
)
from atboffice.ui.shell.quire_window import QuireWindow


@pytest.fixture(autouse=True)
def reset_registry():
    """Ensure clean registry state before each test."""
    TemplateRegistry.reset_instance()
    yield
    TemplateRegistry.reset_instance()


def test_quire_template_ids_list():
    """Verify that all 10 canonical templates are declared."""
    expected = [
        "letter",
        "memo",
        "fax",
        "resume",
        "report",
        "agenda",
        "minutes",
        "todo",
        "flyer",
        "recipe",
    ]
    assert QUIRE_TEMPLATE_IDS == expected


def test_build_quire_template_invalid():
    """Verify requesting an invalid template raises KeyError."""
    with pytest.raises(KeyError):
        build_quire_template("non_existent_id")


@pytest.mark.parametrize("tid", QUIRE_TEMPLATE_IDS)
def test_all_ten_templates_build_valid_document(tid):
    """Verify every template builder produces a valid DocumentModel with blocks and metadata."""
    doc = build_quire_template(tid)
    assert isinstance(doc, Document)
    assert isinstance(doc, DocumentModel)
    assert doc.main is not None
    assert len(doc.main.blocks) > 0
    assert doc.props.get("template") is not None
    assert doc.props.get("title") == ""


def test_letter_template():
    """Verify Letter template structure, styles, and section margins."""
    doc = build_quire_template("letter")
    assert doc.sect.mt == 72
    assert doc.sect.ml == 90
    assert doc.sect.mr == 90

    # Custom styles
    assert "CompanyName" in doc.styles
    assert "ReturnAddress" in doc.styles
    assert "InsideAddress" in doc.styles
    assert "BodyTextLetter" in doc.styles

    style_comp = doc.styles["CompanyName"]
    assert style_comp.r_pr.font == "Arial Black"
    assert style_comp.r_pr.sz == 16

    # Blocks check
    blocks = doc.main.blocks
    assert len(blocks) == 10
    assert all(isinstance(b, Paragraph) for b in blocks)
    assert blocks[0].p_pr.style == "ReturnAddress"
    assert blocks[1].p_pr.style == "CompanyName"


def test_memo_template():
    """Verify Memo template structure, custom styles, and message headers."""
    doc = build_quire_template("memo")
    assert "MemoTitle" in doc.styles
    assert "MessageHeader" in doc.styles
    assert "MemoBody" in doc.styles

    title_st = doc.styles["MemoTitle"]
    assert title_st.r_pr.font == "Arial Black"
    assert title_st.r_pr.sz == 36

    blocks = doc.main.blocks
    assert len(blocks) == 10
    assert blocks[1].p_pr.style == "MemoTitle"


def test_fax_template():
    """Verify Fax template table structure, fields, and checkboxes."""
    doc = build_quire_template("fax")
    assert "FaxTitle" in doc.styles
    assert "FaxLabel" in doc.styles

    blocks = doc.main.blocks
    # Blocks: 2 paragraphs, 1 table (4x4), 2 paragraphs
    assert len(blocks) == 5
    assert isinstance(blocks[0], Paragraph)
    assert isinstance(blocks[1], Paragraph)
    assert isinstance(blocks[2], Table)

    table = blocks[2]
    assert len(table.rows) == 4
    assert len(table.rows[0].cells) == 4
    assert table.grid == [60, 156, 60, 156]


def test_resume_template():
    """Verify Resume template section titles and bullet list numbering."""
    doc = build_quire_template("resume")
    assert doc.sect.ml == 90
    assert doc.sect.mr == 90
    assert "Name" in doc.styles
    assert "SectionTitle" in doc.styles
    assert "Achievement" in doc.styles

    # Bullet numbering must be configured
    assert len(doc.numbering["abs"]) > 0
    assert len(doc.numbering["nums"]) > 0

    blocks = doc.main.blocks
    # Check that achievement items have numbering reference
    achieve_paras = [
        b for b in blocks if isinstance(b, Paragraph) and b.p_pr.style == "Achievement"
    ]
    assert len(achieve_paras) >= 3
    for p in achieve_paras[:3]:
        assert p.p_pr.num is not None


def test_report_template():
    """Verify Report template headings, TOC construct, and footer with PAGE field."""
    doc = build_quire_template("report")
    assert "Title" in doc.styles
    assert "Subtitle" in doc.styles
    assert "Heading1" in doc.styles
    assert "Heading2" in doc.styles

    # Footer story
    assert "rf" in doc.hf
    assert doc.sect.refs.get("ftr", {}).get("default") == "rf"

    footer_story = doc.hf["rf"]
    assert len(footer_story.blocks) >= 1

    # Main blocks: 15 paragraphs including TOC and sections
    blocks = doc.main.blocks
    assert len(blocks) == 15


def test_agenda_template():
    """Verify Agenda template structure and 6x3 table."""
    doc = build_quire_template("agenda")
    assert "AgendaTitle" in doc.styles
    assert "AgendaItem" in doc.styles

    blocks = doc.main.blocks
    # 2 paragraphs, 1 table, 2 paragraphs
    assert len(blocks) == 5
    table = blocks[2]
    assert isinstance(table, Table)
    assert len(table.rows) == 6
    assert len(table.rows[0].cells) == 3
    assert table.grid == [72, 252, 108]


def test_minutes_template():
    """Verify Minutes template structure, action items table, and discussion topics."""
    doc = build_quire_template("minutes")
    assert "MinutesTitle" in doc.styles
    assert "MinutesHeading" in doc.styles
    assert "MinutesText" in doc.styles

    tables = [b for b in doc.main.blocks if isinstance(b, Table)]
    assert len(tables) == 1
    table = tables[0]
    assert len(table.rows) == 5
    assert len(table.rows[0].cells) == 3
    assert table.grid == [276, 96, 72]


def test_todo_template():
    """Verify Todo template checklist styles and checkboxes."""
    doc = build_quire_template("todo")
    assert "ListTitle" in doc.styles
    assert "ListHeading" in doc.styles
    assert "Checklist" in doc.styles

    checklist_paras = [
        b for b in doc.main.blocks if isinstance(b, Paragraph) and b.p_pr.style == "Checklist"
    ]
    assert len(checklist_paras) >= 8


def test_flyer_template():
    """Verify Flyer template margins and kicker/title/tagline styles."""
    doc = build_quire_template("flyer")
    assert doc.sect.mt == 54
    assert doc.sect.mb == 54
    assert "FlyerKicker" in doc.styles
    assert "FlyerTitle" in doc.styles
    assert "FlyerTagline" in doc.styles
    assert "FlyerWhen" in doc.styles
    assert "FlyerText" in doc.styles


def test_recipe_template():
    """Verify Recipe template 2x4 table and ingredient / method numbering."""
    doc = build_quire_template("recipe")
    assert "RecipeTitle" in doc.styles
    assert "RecipeHeading" in doc.styles
    assert "RecipeText" in doc.styles

    tables = [b for b in doc.main.blocks if isinstance(b, Table)]
    assert len(tables) == 1
    table = tables[0]
    assert len(table.rows) == 2
    assert len(table.rows[0].cells) == 4
    assert table.grid == [108, 108, 108, 108]

    # Verify both bullet and decimal numbering instances exist
    assert len(doc.numbering["nums"]) >= 2


def test_template_registry_integration():
    """Verify that TemplateRegistry has callable builders for all 10 Quire templates."""
    reg = TemplateRegistry.get_instance()
    for tid in QUIRE_TEMPLATE_IDS:
        tpl = reg.get(tid, app="quire")
        assert tpl is not None, f"Template {tid} missing in registry"
        assert callable(tpl.builder), f"Template {tid} has no builder"
        doc = tpl.builder()
        assert isinstance(doc, Document)
        assert len(doc.main.blocks) > 0


def test_quire_window_load_template(qtbot):
    """Verify QuireWindow properly loads template and displays it on canvas."""
    win = QuireWindow()
    qtbot.addWidget(win)

    assert win.load_template("letter") is True
    assert win.active_template is not None
    assert win.active_template.id == "letter"
    assert win.is_modified is True
    assert "当代信函" in win.windowTitle()

    # Check canvas document
    canvas_doc = win.writer_view.canvas_view.doc
    assert canvas_doc is not None
    assert len(canvas_doc.main.blocks) == 10


def test_quire_window_new_file_clears_template(qtbot):
    """Verify new_file resets active template and sets clean blank document."""
    win = QuireWindow()
    qtbot.addWidget(win)

    win.load_template("letter")
    assert win.active_template is not None

    win.new_file()
    assert win.active_template is None
    assert not win.is_modified
    assert len(win.writer_view.canvas_view.doc.main.blocks) == 1
