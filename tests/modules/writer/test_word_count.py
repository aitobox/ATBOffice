"""Unit & GUI tests for Quire Writer Word Count dialog and statistics engine:
- WordCountStats data model
- count_text_statistics / calculate_document_statistics calculation logic
- Footnotes and endnotes inclusion toggle
- Selection vs full document comparison
- WordCountDialog modal UI and interactions
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.dialogs.word_count_dlg import (
    WordCountDialog,
    WordCountStats,
    calculate_document_statistics,
    count_text_statistics,
)
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    Story,
    TextItem,
)
from atboffice.modules.writer.view import WriterView


def create_doc_with_paragraphs(texts: list[str]) -> Document:
    """Helper to build a Document with given paragraph texts."""
    doc = Document()
    doc.main.blocks = []
    for t in texts:
        p = Paragraph()
        p.runs = [TextItem(text=t)]
        doc.main.blocks.append(p)
    return doc


class TestWordCountStatistics:
    def test_english_text_statistics(self) -> None:
        text = "The quick brown fox jumps over the lazy dog."
        stats = count_text_statistics(text)
        assert stats.words == 9
        assert stats.chars_no_spaces == 36
        assert stats.chars_with_spaces == 44
        assert stats.paragraphs == 1
        assert stats.lines == 1

    def test_cjk_text_statistics(self) -> None:
        text = "天地玄黄，宇宙洪荒。"
        stats = count_text_statistics(text)
        # 8 CJK characters
        assert stats.words == 8
        assert stats.chars_no_spaces == 10
        assert stats.chars_with_spaces == 10
        assert stats.paragraphs == 1
        assert stats.lines == 1

    def test_mixed_cjk_english_statistics(self) -> None:
        text = "ATBOffice 是一款优秀的 Office 办公套件。"
        # "ATBOffice" (1) + "Office" (1) + 10 CJK characters ("是一款优秀的办公套件") = 12 words
        stats = count_text_statistics(text)
        assert stats.words == 12
        assert stats.chars_no_spaces > 0
        assert stats.chars_with_spaces > stats.chars_no_spaces

    def test_empty_and_whitespace_text(self) -> None:
        empty_stats = count_text_statistics("")
        assert empty_stats.words == 0
        assert empty_stats.chars_no_spaces == 0
        assert empty_stats.chars_with_spaces == 0
        assert empty_stats.paragraphs == 1

        ws_stats = count_text_statistics("   \n\t  ")
        assert ws_stats.words == 0
        assert ws_stats.chars_no_spaces == 0
        assert ws_stats.paragraphs == 1

    def test_multi_paragraph_text(self) -> None:
        text = "First paragraph line.\n\nSecond paragraph text."
        stats = count_text_statistics(text)
        assert stats.words == 6
        assert stats.paragraphs == 2


class TestDocumentStatistics:
    def test_document_paragraphs(self) -> None:
        doc = create_doc_with_paragraphs(
            ["Hello world from Quire.", "Second paragraph with more words."]
        )
        stats = calculate_document_statistics(doc, include_notes=False)
        assert stats.pages == 1
        assert stats.words == 9  # 4 + 5
        assert stats.paragraphs == 2
        assert stats.lines >= 2

    def test_document_with_footnotes_and_endnotes(self) -> None:
        doc = create_doc_with_paragraphs(["Main body text here."])

        fn_p = Paragraph()
        fn_p.runs = [TextItem(text="Footnote reference explanation.")]
        doc.fn["fn1"] = Story(kind="fn", blocks=[fn_p])

        en_p = Paragraph()
        en_p.runs = [TextItem(text="Endnote citation source.")]
        doc.en["en1"] = Story(kind="en", blocks=[en_p])

        stats_without_notes = calculate_document_statistics(doc, include_notes=False)
        stats_with_notes = calculate_document_statistics(doc, include_notes=True)

        assert stats_without_notes.words == 4
        assert stats_with_notes.words == 4 + 3 + 3
        assert stats_with_notes.paragraphs == 3
        assert stats_with_notes.chars_no_spaces > stats_without_notes.chars_no_spaces


class TestWordCountDialogUI:
    def test_dialog_initialization_without_selection(self, qapp: QApplication) -> None:
        doc = create_doc_with_paragraphs(["Word 2003 dialog testing paragraph."])
        dlg = WordCountDialog(doc=doc, selection_text=None)

        assert dlg.windowTitle() == "字数统计"
        assert dlg.btn_close is not None
        assert dlg.table is not None
        assert dlg.check_include_notes is not None
        assert dlg.table.rowCount() == 6
        # Without selection, table has 2 columns: [项目, 统计值]
        assert dlg.table.columnCount() == 2

        # Check values in table
        stat_names = [dlg.table.item(r, 0).text() for r in range(6)]
        assert "页数" in stat_names
        assert "字数" in stat_names
        assert "字符数(不计空格)" in stat_names
        assert "字符数(计空格)" in stat_names
        assert "段落数" in stat_names
        assert "行数" in stat_names

        # Close button closes dialog
        dlg.btn_close.click()

    def test_dialog_with_selection_comparison(self, qapp: QApplication) -> None:
        doc = create_doc_with_paragraphs(
            ["This is a longer document for comparison.", "Additional paragraph here."]
        )
        selection_text = "longer document"
        dlg = WordCountDialog(doc=doc, selection_text=selection_text)

        # When selection exists, 3 columns: [项目, 选定内容, 整篇文档]
        assert dlg.table.columnCount() == 3
        assert dlg.selection_stats is not None
        assert dlg.doc_stats is not None
        assert dlg.selection_stats.words == 2
        assert dlg.doc_stats.words == 10

    def test_toggle_include_notes(self, qapp: QApplication) -> None:
        doc = create_doc_with_paragraphs(["Document body."])
        fn_p = Paragraph()
        fn_p.runs = [TextItem(text="Extra footnote note words.")]
        doc.fn["fn1"] = Story(kind="fn", blocks=[fn_p])

        dlg = WordCountDialog(doc=doc)
        initial_words = dlg.doc_stats.words
        assert initial_words == 2

        # Toggle include notes
        dlg.check_include_notes.setChecked(True)
        assert dlg.doc_stats.words == 2 + 4

        dlg.check_include_notes.setChecked(False)
        assert dlg.doc_stats.words == 2

    def test_retranslate_ui(self, qapp: QApplication) -> None:
        doc = create_doc_with_paragraphs(["Test string"])
        dlg = WordCountDialog(doc=doc)
        dlg.retranslate_ui()
        assert dlg.windowTitle() == "字数统计"
        assert "包括文本框、脚注和尾注(&I)" in dlg.check_include_notes.text()
        assert "关闭(&C)" in dlg.btn_close.text()


class TestWriterViewWordCountIntegration:
    def test_writer_view_open_word_count(self, qapp: QApplication) -> None:
        doc = create_doc_with_paragraphs(["WriterView integration test."])
        view = WriterView(doc=doc)
        dlg = view.create_word_count_dialog()
        assert isinstance(dlg, WordCountDialog)
        assert dlg.doc_stats.words == 3
