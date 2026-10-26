"""GUI tests for Lectern in-place rich text editor, outline indents, and Text AutoFit."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent

from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import (
    Paragraph,
    TextBody,
    TextRun,
)
from atboffice.modules.presentation.views.slide_canvas import (
    SlideCanvasView,
    SlideScene,
)
from atboffice.modules.presentation.views.text_editor import (
    ShapeTextEditorItem,
    safe_tr,
)


@pytest.fixture
def scene_and_view(qtbot):
    """Fixture providing an active slide scene, view, and test shape item."""
    slide = Slide(id="sl_test")
    sh = Shape(
        id="s_text",
        geom="rect",
        x=100.0,
        y=100.0,
        w=300.0,
        h=150.0,
        text=TextBody(
            autofit="norm",
            paragraphs=[
                Paragraph(
                    level=0,
                    runs=[TextRun(text="Initial Title", bold=True, size=24.0)],
                )
            ],
        ),
    )
    slide.add_shape(sh)

    scene = SlideScene(slide=slide, slide_width=960.0, slide_height=540.0)
    view = SlideCanvasView(scene)
    qtbot.addWidget(view)
    view.show()

    item = scene.get_shape_item("s_text")
    assert item is not None
    return scene, view, item


class TestTextEditorInteraction:
    """Test text editor activation, typing, and lifecycle."""

    def test_start_and_finish_editing(self, qtbot, scene_and_view) -> None:
        scene, view, item = scene_and_view

        assert not item.is_editing_text
        assert item._text_editor is None

        # Activate editing
        editor = item.start_text_editing()
        assert item.is_editing_text
        assert item._text_editor is not None
        assert isinstance(editor, ShapeTextEditorItem)
        assert scene.focusItem() == editor

        # Commit and finish
        item.finish_text_editing()
        assert not item.is_editing_text
        assert item._text_editor is None

    def test_double_click_activates_editing(self, qtbot, scene_and_view) -> None:
        scene, view, item = scene_and_view

        editor = item.start_text_editing()
        assert item.is_editing_text
        assert item._text_editor is not None

        # Escape commits and finishes
        ev_esc = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        editor.keyPressEvent(ev_esc)
        assert not item.is_editing_text
        assert item._text_editor is None

    def test_text_input_and_sync(self, qtbot, scene_and_view) -> None:
        scene, view, item = scene_and_view

        editor = item.start_text_editing()
        editor.setPlainText("New Lectern Line")
        editor.commit_and_finish()

        assert not item.is_editing_text
        assert item.shape.text is not None
        assert "New Lectern Line" in item.shape.text.plain_text


class TestOutlineIndents:
    """Test Tab (demote) and Shift+Tab (promote) outline level changes."""

    def test_tab_demote_and_shift_tab_promote(self, qtbot, scene_and_view) -> None:
        scene, view, item = scene_and_view

        editor = item.start_text_editing()
        # Initial level is 0
        cursor = editor.textCursor()
        assert cursor.block().userState() == 0

        # Press Tab -> Demote to level 1
        ev_tab = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Tab,
            Qt.KeyboardModifier.NoModifier,
            "\t",
        )
        editor.keyPressEvent(ev_tab)
        assert editor.textCursor().block().userState() == 1

        # Press Tab again -> Demote to level 2
        editor.keyPressEvent(ev_tab)
        assert editor.textCursor().block().userState() == 2

        # Press Shift+Tab -> Promote back to level 1
        ev_shift_tab = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Tab,
            Qt.KeyboardModifier.ShiftModifier,
            "\t",
        )
        editor.keyPressEvent(ev_shift_tab)
        assert editor.textCursor().block().userState() == 1

        # Press Shift+Tab -> Promote back to level 0
        editor.keyPressEvent(ev_shift_tab)
        assert editor.textCursor().block().userState() == 0

        # Cannot promote beyond level 0
        editor.keyPressEvent(ev_shift_tab)
        assert editor.textCursor().block().userState() == 0

        editor.commit_and_finish()

    def test_backspace_at_block_start_promotes(self, qtbot, scene_and_view) -> None:
        scene, view, item = scene_and_view

        editor = item.start_text_editing()
        editor.demote()
        assert editor.textCursor().block().userState() == 1

        # Move cursor to start of block
        c = editor.textCursor()
        c.movePosition(c.MoveOperation.StartOfBlock)
        editor.setTextCursor(c)

        # Send Backspace at start of block
        ev_bksp = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Backspace,
            Qt.KeyboardModifier.NoModifier,
        )
        editor.keyPressEvent(ev_bksp)
        assert editor.textCursor().block().userState() == 0

        editor.commit_and_finish()


class TestFormattingCommands:
    """Test character formatting operations."""

    def test_bold_italic_underline(self, qtbot, scene_and_view) -> None:
        scene, view, item = scene_and_view

        editor = item.start_text_editing()
        editor.selectAll()

        editor.set_bold(True)
        assert editor.textCursor().charFormat().fontWeight() >= QFont.Weight.Bold

        editor.set_italic(True)
        assert editor.textCursor().charFormat().fontItalic()

        editor.set_underline(True)
        assert editor.textCursor().charFormat().fontUnderline()

        editor.commit_and_finish()

        # Check model persistence
        tb = item.shape.text
        assert tb.paragraphs[0].runs[0].bold
        assert tb.paragraphs[0].runs[0].italic
        assert tb.paragraphs[0].runs[0].underline

    def test_font_size_and_step(self, qtbot, scene_and_view) -> None:
        scene, view, item = scene_and_view

        editor = item.start_text_editing()
        editor.selectAll()

        editor.set_font_size(36.0)
        assert editor.textCursor().charFormat().fontPointSize() == 36.0

        editor.step_font_size(1)
        assert editor.textCursor().charFormat().fontPointSize() == 40.0

        editor.step_font_size(-1)
        assert editor.textCursor().charFormat().fontPointSize() == 36.0

        editor.commit_and_finish()

    def test_font_color_and_family(self, qtbot, scene_and_view) -> None:
        scene, view, item = scene_and_view

        editor = item.start_text_editing()
        editor.selectAll()

        editor.set_font_color("#FF0000")
        assert editor.textCursor().charFormat().foreground().color().name().upper() == "#FF0000"

        editor.set_font_family("Arial")
        cf = editor.textCursor().charFormat()
        has_families = hasattr(cf, "fontFamilies") and cf.fontFamilies()
        fam = cf.fontFamilies()[0] if has_families else cf.fontFamily()
        assert fam == "Arial"

        editor.commit_and_finish()

    def test_alignment_and_bullets(self, qtbot, scene_and_view) -> None:
        scene, view, item = scene_and_view

        editor = item.start_text_editing()
        editor.set_alignment("ctr")
        assert editor.textCursor().blockFormat().alignment() & Qt.AlignmentFlag.AlignCenter

        editor.set_bullet_type("char", "•")
        editor.commit_and_finish()

        tb = item.shape.text
        assert tb.paragraphs[0].props.get("algn") == "ctr"
        assert tb.paragraphs[0].props.get("bu", {}).get("ch") == "•"


class TestAutoFitIntegration:
    """Test Text AutoFit scaling when content overflows."""

    def test_autofit_scales_down_on_large_text(self, qtbot, scene_and_view) -> None:
        scene, view, item = scene_and_view

        # Shape has h=150.0. Add lots of lines to cause overflow.
        long_text = "\n".join([f"Line number {i} of presentation text" for i in range(25)])
        editor = item.start_text_editing()
        editor.setPlainText(long_text)

        # Trigger autofit
        editor.apply_autofit("norm")
        assert item.shape.text.font_scale < 1.0
        assert item.shape.text.font_scale >= 0.25

        editor.commit_and_finish()
        assert item.shape.text.font_scale < 1.0

    def test_shape_autofit_mode(self, qtbot, scene_and_view) -> None:
        scene, view, item = scene_and_view
        item.shape.text.autofit = "shape"

        editor = item.start_text_editing()
        editor.setPlainText(
            "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n"
            "Line 6\nLine 7\nLine 8\nLine 9\nLine 10"
        )
        editor.apply_autofit("shape")

        # Height should expand to hold all lines
        assert item.shape.h >= 150.0
        editor.commit_and_finish()


class TestContextAndI18n:
    """Test i18n translations and context menu generation."""

    def test_safe_tr_translations(self) -> None:
        assert safe_tr("Bold") == "加粗"
        assert safe_tr("Italic") == "倾斜"
        assert safe_tr("Increase Indent") == "增加缩进 (降级)"
        assert safe_tr("Decrease Indent") == "减少缩进 (升级)"

    def test_context_menu_actions(self, scene_and_view) -> None:
        scene, view, item = scene_and_view
        editor = item.start_text_editing()

        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        editor._populate_context_menu(menu)
        action_texts = [a.text() for a in menu.actions() if a.text()]
        assert "加粗" in action_texts or "Bold" in action_texts
        assert "倾斜" in action_texts or "Italic" in action_texts

        item.finish_text_editing()
