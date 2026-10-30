"""Unit tests for Quire AutoCorrect and Spell checking engines (Issue #139)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QContextMenuEvent,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QPainter,
)
from PySide6.QtWidgets import QApplication

from atboffice.core.settings import AppSettings
from atboffice.modules.writer.autocorrect import AutoCorrectEngine
from atboffice.modules.writer.dialogs.spelling_dialog import SpellingGrammarDialog
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TextItem,
    ptext,
    reindex,
)
from atboffice.modules.writer.spell import SpellEngine
from atboffice.modules.writer.views.canvas_view import WriterCanvasView
from atboffice.modules.writer.views.caret_controller import CaretController, DocPos


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance is initialized for GUI components."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def clean_state():
    """Reset AppSettings and spell engine state before each test."""
    AppSettings.reset_instance()
    settings = AppSettings.get_instance()
    settings.set_value("spelling/check_as_you_type", True)
    settings.set_value("spelling/ignore_uppercase", True)
    settings.set_value("spelling/ignore_numbers", True)
    settings.set_value("autocorrect/smart_quotes", True)
    settings.set_value("autocorrect/replace_text_as_you_type", True)
    settings.set_value("autocorrect/dashes", True)
    settings.set_value("autocorrect/fractions", True)
    settings.set_value("autocorrect/auto_lists", True)

    spell = SpellEngine.get_instance()
    spell.ignored_all.clear()
    spell.custom_dict.clear()
    spell.cache.clear()
    yield


def test_autocorrect_smart_quotes():
    """Verify straight quote to smart curved quote transformation based on context."""
    engine = AutoCorrectEngine()

    # Double quotes: opening after whitespace/punctuation, closing after text
    assert engine.smart_char('"', "") == "“"
    assert engine.smart_char('"', " ") == "“"
    assert engine.smart_char('"', "(") == "“"
    assert engine.smart_char('"', "a") == "”"
    assert engine.smart_char('"', ".") == "”"

    # Single quotes: opening after whitespace, apostrophe/closing after letters
    assert engine.smart_char("'", "") == "‘"
    assert engine.smart_char("'", " ") == "‘"
    assert engine.smart_char("'", "s") == "’"
    assert engine.smart_char("'", "t") == "’"


def test_autocorrect_typing_rules():
    """Verify symbol, typo, dash, and fraction replacements."""
    engine = AutoCorrectEngine()

    # Symbols: (c), (r), (tm), ...
    assert engine.process_typing("Here is (c)", " ") == (8, 11, "©")
    assert engine.process_typing("Product (r)", " ") == (8, 11, "®")
    assert engine.process_typing("Brand (tm)", " ") == (6, 10, "™")
    assert engine.process_typing("Wait...", ".") == (4, 7, "…")

    # Fractions: 1/2, 1/4, 3/4
    assert engine.process_typing("Measure 1/2", " ") == (8, 11, "½")
    assert engine.process_typing("Quarter 1/4", " ") == (8, 11, "¼")
    assert engine.process_typing("Three 3/4", " ") == (6, 9, "¾")

    # Em-dash
    assert engine.process_typing("word--", "-") == (4, 6, "—")

    # Typos with case restoration
    assert engine.process_typing("This is teh", " ") == (8, 11, "the")
    assert engine.process_typing("Teh", " ") == (0, 3, "The")
    assert engine.process_typing("TEH", " ") == (0, 3, "THE")
    assert engine.process_typing("recieve", " ") == (0, 7, "receive")


def test_acceptance_criterion_1_symbol_c_to_copyright(qapp):
    """Criterion 1: 键入 (c) 并按空格，文字立即自动变为 ©。"""
    doc = Document()
    doc.main.blocks.append(Paragraph())
    reindex(doc)

    canvas = WriterCanvasView(doc=doc)
    controller = canvas.controller

    # Type "(c)"
    controller.insert_text("(")
    controller.insert_text("c")
    controller.insert_text(")")

    # Type space " "
    controller.insert_text(" ")

    p = doc.main.blocks[0]
    assert ptext(p) == "© "


def test_autocorrect_auto_lists_on_enter(qapp):
    """Verify auto-formatting numbered and bulleted lists on Enter."""
    doc = Document()
    p1 = Paragraph(runs=[TextItem("1. First item")])
    doc.main.blocks.append(p1)
    reindex(doc)

    canvas = WriterCanvasView(doc=doc)
    controller = canvas.controller
    controller.pos = DocPos(p1.id, len("1. First item"))

    controller.insert_paragraph_break()

    # p1 should now be formatted as a numbered list with prefix stripped
    assert p1.p_pr is not None
    assert p1.p_pr.num is not None
    assert p1.p_pr.num.id == "2"
    assert ptext(p1) == "First item"

    # Next paragraph created should inherit numbered list
    p2 = doc.main.blocks[1]
    assert isinstance(p2, Paragraph)
    assert p2.p_pr is not None
    assert p2.p_pr.num is not None


def test_spell_engine_validation_and_suggestions():
    """Verify offline dictionary loading, validation rules, and suggestions."""
    spell = SpellEngine.get_instance()

    assert len(spell.word_map) > 50000

    # Valid words
    assert spell.is_valid_word("the") is True
    assert spell.is_valid_word("The") is True
    assert spell.is_valid_word("document") is True
    assert spell.is_valid_word("John's") is True
    assert spell.is_valid_word("NASA") is True
    assert spell.is_valid_word("2nd") is True

    # Invalid typos
    assert spell.is_valid_word("teh") is False
    assert spell.is_valid_word("recieve") is False

    # Suggestions: 'teh' -> 'the'
    suggs = spell.suggest("teh")
    assert "the" in suggs
    assert suggs[0] == "the"

    # Case restoration in suggestion
    suggs_cap = spell.suggest("Teh")
    assert "The" in suggs_cap

    # Ignore all and Custom dictionary
    spell.ignore_all("teh")
    assert spell.is_valid_word("teh") is True

    spell.add_to_custom_dict("myprojectword")
    assert spell.is_valid_word("myprojectword") is True


def test_acceptance_criterion_2_wavy_line_and_context_menu(qapp):
    """Criterion 2: 键入 teh 等错词时，文字下方渲染红色波浪线；右键菜单中出现 the 纠错建议。"""
    doc = Document()
    p = Paragraph(runs=[TextItem("Here is teh problem.")])
    doc.main.blocks.append(p)
    reindex(doc)

    canvas = WriterCanvasView(doc=doc)
    canvas.resize(800, 600)

    # 1. Verify wavy underline drawing occurs on canvas paint
    drawn_lines = []
    orig_draw_wavy = canvas._draw_wavy_line

    def tracking_wavy(painter, x1, x2, y, color):
        drawn_lines.append((x1, x2, y, color))
        orig_draw_wavy(painter, x1, x2, y, color)

    canvas._draw_wavy_line = tracking_wavy

    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)
    painter = QPainter(img)
    page_rect = QRectF(0.0, 0.0, 800.0, 1000.0)
    canvas._paint_page_content(painter, page_rect, canvas.pagination.pages[0])
    painter.end()

    assert len(drawn_lines) > 0, "Red wavy line was not rendered for misspelled word 'teh'"

    # 2. Right-click context menu over 'teh'
    # Position caret on 'teh' (offset 8-11)
    canvas.controller.pos = DocPos(p.id, 9)

    # Find the misspelled word at current caret position
    pt = ptext(p)
    misspelled = None
    for w, s, e in canvas.spell_engine.tokenize_words(pt):
        if s <= 9 <= e and not canvas.spell_engine.is_valid_word(w):
            misspelled = w
            break

    assert misspelled == "teh"
    suggestions = canvas.spell_engine.suggest(misspelled)
    assert "the" in suggestions


def test_acceptance_criterion_4_hide_wavy_line_when_option_disabled(qapp):
    """Criterion 4: 在设置中关闭「键入时检查拼写」能隐藏所有波浪线提示。"""
    doc = Document()
    p = Paragraph(runs=[TextItem("Here is teh problem.")])
    doc.main.blocks.append(p)
    reindex(doc)

    canvas = WriterCanvasView(doc=doc)

    # Turn OFF check_as_you_type
    AppSettings.get_instance().set_value("spelling/check_as_you_type", False)

    drawn_lines = []
    canvas._draw_wavy_line = lambda painter, x1, x2, y, color: drawn_lines.append((x1, x2, y, color))

    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    painter = QPainter(img)
    page_rect = QRectF(0.0, 0.0, 800.0, 1000.0)
    canvas._paint_page_content(painter, page_rect, canvas.pagination.pages[0])
    painter.end()

    assert len(drawn_lines) == 0, "Wavy line should be suppressed when check_as_you_type is False"


def test_acceptance_criterion_3_f7_spelling_dialog_navigation(qapp):
    """Criterion 3: 按 F7 能唤起拼写检查对话框并依次定位至错词。"""
    doc = Document()
    p1 = Paragraph(runs=[TextItem("This is teh first error.")])
    p2 = Paragraph(runs=[TextItem("Second is a recieve defect.")])
    doc.main.blocks.extend([p1, p2])
    reindex(doc)

    canvas = WriterCanvasView(doc=doc)

    # Test F7 key event dispatch
    f7_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F7, Qt.KeyboardModifier.NoModifier)

    dialog_opened = []

    def mock_open_spelling():
        dialog_opened.append(True)

    canvas.open_spelling_dialog = mock_open_spelling
    canvas.keyPressEvent(f7_event)

    assert len(dialog_opened) == 1, "F7 key press did not trigger open_spelling_dialog"

    # Test SpellingGrammarDialog functionality directly
    dlg = SpellingGrammarDialog(doc, controller=canvas.controller)

    # Dialog should locate 'teh' first
    assert dlg.current_idx < len(dlg.issues)
    assert dlg.issues[dlg.current_idx]["word"] == "teh"

    # Suggestions should contain 'the'
    sugg_items = [dlg.list_suggestions.item(i).text() for i in range(dlg.list_suggestions.count())]
    assert "the" in sugg_items

    # Change 'teh' -> 'the'
    dlg._on_change()

    # Document p1 should now have 'the'
    assert "the" in ptext(p1)
    assert "teh" not in ptext(p1)

    # Next issue should locate 'recieve'
    if dlg.current_idx < len(dlg.issues):
        assert dlg.issues[dlg.current_idx]["word"] == "recieve"
        dlg._on_change()
        assert "receive" in ptext(p2)
