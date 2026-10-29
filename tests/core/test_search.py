"""Tests for cross-module Search & Replace core engine."""

import re

import pytest

from atboffice.core.search import (
    SearchController,
    SearchMatch,
    SearchOptions,
    SpreadsheetSearchAdapter,
    WriterSearchAdapter,
)
from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.writer.layout.pagination import paginate_document
from atboffice.modules.writer.models.document import Document, Paragraph, TextItem
from atboffice.modules.writer.views.caret_controller import CaretController


class TestSearchOptions:
    def test_default_options(self):
        opts = SearchOptions()
        assert opts.text == ""
        assert opts.replace_text == ""
        assert opts.match_case is False
        assert opts.whole_word is False
        assert opts.use_regex is False
        assert opts.direction == "down"

    def test_compile_plain_text(self):
        opts = SearchOptions(text="hello.world", match_case=False)
        pattern = opts.compile_regex()
        assert pattern.search("Hello.World") is not None
        assert pattern.search("helloaworld") is None  # '.' is escaped

    def test_compile_case_sensitive(self):
        opts = SearchOptions(text="Hello", match_case=True)
        pattern = opts.compile_regex()
        assert pattern.search("Hello") is not None
        assert pattern.search("hello") is None

    def test_compile_whole_word(self):
        opts = SearchOptions(text="cat", whole_word=True)
        pattern = opts.compile_regex()
        assert pattern.search("the cat sat") is not None
        assert pattern.search("category") is None
        assert pattern.search("bobcat") is None

    def test_compile_regex(self):
        opts = SearchOptions(text=r"\d{3}-\d{4}", use_regex=True)
        pattern = opts.compile_regex()
        assert pattern.search("Call 123-4567 now") is not None
        assert pattern.search("Call 12-34 now") is None

    def test_compile_invalid_regex_raises(self):
        opts = SearchOptions(text=r"[unclosed", use_regex=True)
        with pytest.raises(re.error):
            opts.compile_regex()


class TestWriterSearchAdapter:
    def _create_doc(self) -> Document:
        doc = Document()
        p1 = Paragraph(id=1, runs=[TextItem("Hello World! Welcome to World of Office.")])
        p2 = Paragraph(id=2, runs=[TextItem("Second paragraph contains world lowercase.")])
        doc.main.blocks = [p1, p2]
        return doc

    def test_writer_find_next_down(self, qapp):
        doc = self._create_doc()
        pag = paginate_document(doc)
        caret = CaretController(doc, pag)
        adapter = WriterSearchAdapter(doc=doc, caret_controller=caret)

        opts = SearchOptions(text="World", match_case=True, direction="down")
        m1 = adapter.find_next(opts)
        assert m1 is not None
        assert m1.target_id == 1
        assert m1.start == 6
        assert m1.end == 11
        assert m1.matched_text == "World"

        # Next match in same paragraph
        m2 = adapter.find_next(opts, start_from=m1)
        assert m2 is not None
        assert m2.target_id == 1
        assert m2.start == 24
        assert m2.end == 29
        assert m2.matched_text == "World"

        # Wraps or finishes
        m3 = adapter.find_next(opts, start_from=m2)
        # In case-sensitive mode, p2 has "world", so p1 was last
        assert m3 is not None
        assert m3.target_id == 1
        assert m3.start == 6  # Wrapped around

    def test_writer_find_previous_up(self, qapp):
        doc = self._create_doc()
        pag = paginate_document(doc)
        caret = CaretController(doc, pag)
        adapter = WriterSearchAdapter(doc=doc, caret_controller=caret)

        opts = SearchOptions(text="World", match_case=True, direction="up")
        start_m = SearchMatch(target_id=1, start=24, end=29, matched_text="World")
        prev_m = adapter.find_next(opts, start_from=start_m)
        assert prev_m is not None
        assert prev_m.target_id == 1
        assert prev_m.start == 6

    def test_writer_replace_one(self, qapp):
        doc = self._create_doc()
        pag = paginate_document(doc)
        caret = CaretController(doc, pag)
        adapter = WriterSearchAdapter(doc=doc, caret_controller=caret)

        opts = SearchOptions(text="World", replace_text="Universe", match_case=True)
        m = adapter.find_next(opts)
        assert m is not None
        replaced = adapter.replace_one(opts, m)
        assert replaced is not None
        p1 = doc.main.blocks[0]
        assert "Hello Universe! Welcome to World of Office." in p1.runs[0].text

    def test_writer_replace_all(self, qapp):
        doc = self._create_doc()
        pag = paginate_document(doc)
        caret = CaretController(doc, pag)
        adapter = WriterSearchAdapter(doc=doc, caret_controller=caret)

        opts = SearchOptions(text="world", replace_text="globe", match_case=False)
        count = adapter.replace_all(opts)
        assert count == 3
        p1_text = doc.main.blocks[0].runs[0].text
        p2_text = doc.main.blocks[1].runs[0].text
        assert "globe" in p1_text
        assert "globe" in p2_text
        assert "World" not in p1_text
        assert "world" not in p2_text


class TestSpreadsheetSearchAdapter:
    def _create_sheet(self) -> SheetDataModel:
        sheet = SheetDataModel(name="TestSheet")
        sheet.set_cell(0, 0, CellData(value="Revenue 2024"))
        sheet.set_cell(0, 1, CellData(value=1000))
        sheet.set_cell(1, 0, CellData(value="Cost 2024"))
        sheet.set_cell(1, 1, CellData(value=500))
        sheet.set_cell(2, 0, CellData(value="Net Revenue"))
        sheet.set_cell(2, 1, CellData(value=500))
        return sheet

    def test_spreadsheet_find_next(self, qapp):
        sheet = self._create_sheet()
        sel = SelectionModel()
        adapter = SpreadsheetSearchAdapter(model=sheet, selection=sel)

        opts = SearchOptions(text="Revenue", match_case=True, direction="down")
        m1 = adapter.find_next(opts)
        assert m1 is not None
        assert m1.target_id == (0, 0)
        assert m1.matched_text == "Revenue"

        m2 = adapter.find_next(opts, start_from=m1)
        assert m2 is not None
        assert m2.target_id == (2, 0)

    def test_spreadsheet_replace_all(self, qapp):
        sheet = self._create_sheet()
        sel = SelectionModel()
        adapter = SpreadsheetSearchAdapter(model=sheet, selection=sel)

        opts = SearchOptions(text="2024", replace_text="2025")
        count = adapter.replace_all(opts)
        assert count == 2
        assert sheet.get_cell_value(0, 0) == "Revenue 2025"
        assert sheet.get_cell_value(1, 0) == "Cost 2025"


class TestSearchController:
    def test_controller_signals_and_orchestration(self, qapp):
        sheet = SheetDataModel(name="TestSheet")
        sheet.set_cell(0, 0, CellData(value="Alpha Beta"))
        sheet.set_cell(1, 0, CellData(value="Gamma Delta"))
        sel = SelectionModel()
        adapter = SpreadsheetSearchAdapter(model=sheet, selection=sel)

        controller = SearchController()
        controller.set_adapter(adapter)

        found_matches = []
        controller.match_found.connect(found_matches.append)

        no_match_count = [0]
        controller.no_match_found.connect(
            lambda: no_match_count.__setitem__(0, no_match_count[0] + 1)
        )

        # Search for Beta
        m = controller.find_next(SearchOptions(text="Beta"))
        assert m is not None
        assert len(found_matches) == 1
        assert found_matches[0].target_id == (0, 0)

        # Search for NonExistent
        m2 = controller.find_next(SearchOptions(text="Omega"))
        assert m2 is None
        assert no_match_count[0] == 1

        # Replace All
        rep_counts = []
        controller.replace_completed.connect(rep_counts.append)
        n = controller.replace_all(SearchOptions(text="Alpha", replace_text="Zeta"))
        assert n == 1
        assert rep_counts == [1]
        assert sheet.get_cell_value(0, 0) == "Zeta Beta"
