"""Cross-module search and replace architecture for ATBOffice.

Provides unified SearchOptions, SearchMatch data structures, abstract
SearchAdapter interface, and SearchController coordination logic with concrete
implementations for Quire (Writer) and Ledger (Spreadsheet).
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, Signal

from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    all_paragraphs,
    ptext,
    reindex,
)
from atboffice.modules.writer.views.caret_controller import (
    CaretController,
    DocPos,
    delete_range_in_paragraph,
    insert_text_in_paragraph,
)

logger = logging.getLogger(__name__)


def safe_tr(text: str) -> str:
    """Translate UI text safely for search system."""
    return QCoreApplication.translate("Search", text)


@dataclass
class SearchOptions:
    """Configuration options for search and replace operations."""

    text: str = ""
    replace_text: str = ""
    match_case: bool = False
    whole_word: bool = False
    use_regex: bool = False
    direction: str = "down"  # "down" (forward) or "up" (backward)
    scope: str = "all"  # "all" or "selection"

    def compile_regex(self) -> re.Pattern:
        """Compile options into a compiled regular expression pattern."""
        if not self.text:
            raise ValueError("Search text cannot be empty")

        flags = re.MULTILINE
        if not self.match_case:
            flags |= re.IGNORECASE

        if self.use_regex:
            return re.compile(self.text, flags)

        # Non-regex standard search: support Office specials
        src = self.text
        # Replace caret escape patterns
        specials = {
            "^p": "\n",
            "^t": "\t",
            "^^": "^",
        }
        for code, char in specials.items():
            src = src.replace(code, char)

        pattern = re.escape(src)
        if self.whole_word:
            pattern = rf"(?<!\w){pattern}(?!\w)"

        return re.compile(pattern, flags)


@dataclass
class SearchMatch:
    """Represents a single match within a document or sheet."""

    target_id: Any  # Paragraph ID or (row, col) tuple
    start: int  # Starting character offset in text
    end: int  # Ending character offset in text
    matched_text: str  # The matched text
    extra: dict[str, Any] = field(default_factory=dict)


class SearchAdapter(ABC):
    """Abstract interface for module-specific search and replace operations."""

    @abstractmethod
    def find_all(self, options: SearchOptions) -> list[SearchMatch]:
        """Find all occurrences matching the search options."""

    @abstractmethod
    def find_next(
        self, options: SearchOptions, start_from: SearchMatch | None = None
    ) -> SearchMatch | None:
        """Find the next occurrence after or before start_from."""

    @abstractmethod
    def replace_one(
        self, options: SearchOptions, match: SearchMatch
    ) -> SearchMatch | None:
        """Replace the specified match and return the next match if any."""

    @abstractmethod
    def replace_all(self, options: SearchOptions) -> int:
        """Replace all occurrences matching options and return the count."""

    @abstractmethod
    def focus_match(self, match: SearchMatch) -> None:
        """Position viewport and cursor/selection on the given match."""


class WriterSearchAdapter(SearchAdapter):
    """Search and replace adapter for Quire word-processing documents."""

    def __init__(
        self,
        doc: Document,
        caret_controller: CaretController | None = None,
        writer_view: Any = None,
    ) -> None:
        self.doc = doc
        self.caret_controller = caret_controller
        self.writer_view = writer_view

    def _get_paragraphs(self) -> list[Paragraph]:
        reindex(self.doc)
        return all_paragraphs(self.doc)

    def find_all(self, options: SearchOptions) -> list[SearchMatch]:
        if not options.text:
            return []
        pattern = options.compile_regex()
        matches: list[SearchMatch] = []
        for p in self._get_paragraphs():
            txt = ptext(p)
            for m in pattern.finditer(txt):
                matches.append(
                    SearchMatch(
                        target_id=p.id,
                        start=m.start(),
                        end=m.end(),
                        matched_text=m.group(0),
                    )
                )
        return matches

    def find_next(
        self, options: SearchOptions, start_from: SearchMatch | None = None
    ) -> SearchMatch | None:
        matches = self.find_all(options)
        if not matches:
            return None

        if start_from is None:
            return matches[0] if options.direction == "down" else matches[-1]

        # Order matches based on paragraph reading order
        paras = self._get_paragraphs()
        para_order = {p.id: i for i, p in enumerate(paras)}

        def key(m: SearchMatch) -> tuple[int, int]:
            return (para_order.get(m.target_id, 0), m.start)

        sorted_matches = sorted(matches, key=key)
        start_key = (para_order.get(start_from.target_id, 0), start_from.start)

        if options.direction == "down":
            for m in sorted_matches:
                if key(m) > start_key:
                    return m
            # Wrap around to start
            return sorted_matches[0]
        else:
            for m in reversed(sorted_matches):
                if key(m) < start_key:
                    return m
            # Wrap around to end
            return sorted_matches[-1]

    def focus_match(self, match: SearchMatch) -> None:
        if self.caret_controller is not None:
            pos_start = DocPos(match.target_id, match.start)
            pos_end = DocPos(match.target_id, match.end)
            self.caret_controller.set_pos(pos_start, extend_selection=False)
            self.caret_controller.set_pos(pos_end, extend_selection=True)

        if self.writer_view is not None:
            if hasattr(self.writer_view, "canvas_view"):
                self.writer_view.canvas_view.update()
            elif hasattr(self.writer_view, "update"):
                self.writer_view.update()

    def replace_one(
        self, options: SearchOptions, match: SearchMatch
    ) -> SearchMatch | None:
        paras = {p.id: p for p in self._get_paragraphs()}
        p = paras.get(match.target_id)
        if p is None:
            return None

        delete_range_in_paragraph(p, match.start, match.end)
        insert_text_in_paragraph(p, match.start, options.replace_text)
        reindex(self.doc)

        if self.caret_controller is not None:
            self.caret_controller.document_modified.emit()
            if hasattr(self.caret_controller, "repaginate_and_refresh"):
                self.caret_controller.repaginate_and_refresh()

        # Find next match after the replaced location
        new_match = SearchMatch(
            target_id=match.target_id,
            start=match.start + len(options.replace_text) - 1,
            end=match.start + len(options.replace_text),
            matched_text=options.replace_text,
        )
        nxt = self.find_next(options, start_from=new_match)
        if nxt:
            self.focus_match(nxt)
        return nxt

    def replace_all(self, options: SearchOptions) -> int:
        pattern = options.compile_regex()
        total_count = 0
        paras = self._get_paragraphs()

        for p in paras:
            txt = ptext(p)
            matches = list(pattern.finditer(txt))
            if not matches:
                continue

            total_count += len(matches)
            # Replace backwards so earlier character indices remain valid
            for m in reversed(matches):
                delete_range_in_paragraph(p, m.start(), m.end())
                # Handle regex groups if use_regex
                rep_text = (
                    m.expand(options.replace_text)
                    if options.use_regex
                    else options.replace_text
                )
                insert_text_in_paragraph(p, m.start(), rep_text)

        reindex(self.doc)
        if self.caret_controller is not None:
            self.caret_controller.document_modified.emit()
            if hasattr(self.caret_controller, "repaginate_and_refresh"):
                self.caret_controller.repaginate_and_refresh()

        if self.writer_view is not None and hasattr(self.writer_view, "update"):
            self.writer_view.update()

        return total_count


class SpreadsheetSearchAdapter(SearchAdapter):
    """Search and replace adapter for Ledger spreadsheet worksheets."""

    def __init__(
        self,
        model: SheetDataModel,
        selection: SelectionModel | None = None,
        spreadsheet_view: Any = None,
    ) -> None:
        self.model = model
        self.selection = selection
        self.spreadsheet_view = spreadsheet_view

    def find_all(self, options: SearchOptions) -> list[SearchMatch]:
        if not options.text:
            return []
        pattern = options.compile_regex()
        matches: list[SearchMatch] = []

        # Sort coordinates in row-major order: (row, col)
        coords = sorted(self.model.cells.keys())
        for r, c in coords:
            val = self.model.get_cell_value(r, c)
            if val is None or val == "":
                continue
            text_val = str(val)
            for m in pattern.finditer(text_val):
                matches.append(
                    SearchMatch(
                        target_id=(r, c),
                        start=m.start(),
                        end=m.end(),
                        matched_text=m.group(0),
                    )
                )
        return matches

    def find_next(
        self, options: SearchOptions, start_from: SearchMatch | None = None
    ) -> SearchMatch | None:
        matches = self.find_all(options)
        if not matches:
            return None

        if start_from is None:
            return matches[0] if options.direction == "down" else matches[-1]

        start_coord = start_from.target_id
        if options.direction == "down":
            for m in matches:
                if (m.target_id, m.start) > (start_coord, start_from.start):
                    return m
            return matches[0]
        else:
            for m in reversed(matches):
                if (m.target_id, m.start) < (start_coord, start_from.start):
                    return m
            return matches[-1]

    def focus_match(self, match: SearchMatch) -> None:
        r, c = match.target_id
        if self.selection is not None:
            self.selection.select_cell(r, c)

        if self.spreadsheet_view is not None:
            if hasattr(self.spreadsheet_view, "grid"):
                self.spreadsheet_view.grid.reveal(r, c)
                self.spreadsheet_view.grid.viewport().update()

    def replace_one(
        self, options: SearchOptions, match: SearchMatch
    ) -> SearchMatch | None:
        r, c = match.target_id
        val = self.model.get_cell_value(r, c)
        if val is None:
            return None

        text_val = str(val)
        pattern = options.compile_regex()
        # Replace first match at or after start
        new_val, count = pattern.subn(options.replace_text, text_val, count=1)
        if count > 0:
            self.model.set_cell_value(r, c, new_val)

        nxt = self.find_next(options, start_from=match)
        if nxt:
            self.focus_match(nxt)
        return nxt

    def replace_all(self, options: SearchOptions) -> int:
        pattern = options.compile_regex()
        total_count = 0
        coords = sorted(self.model.cells.keys())

        for r, c in coords:
            val = self.model.get_cell_value(r, c)
            if val is None or val == "":
                continue
            text_val = str(val)
            new_val, n = pattern.subn(options.replace_text, text_val)
            if n > 0:
                self.model.set_cell_value(r, c, new_val)
                total_count += n

        if self.spreadsheet_view is not None:
            if hasattr(self.spreadsheet_view, "grid"):
                self.spreadsheet_view.grid.viewport().update()

        return total_count


class SearchController(QObject):
    """Central search and replace coordinator connecting UI dialogs with view adapters."""

    match_found = Signal(object)
    no_match_found = Signal()
    replace_completed = Signal(int)
    status_message = Signal(str)
    wrapped_around = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._adapter: SearchAdapter | None = None
        self._current_match: SearchMatch | None = None

    def set_adapter(self, adapter: SearchAdapter | None) -> None:
        """Bind or switch the active search adapter."""
        self._adapter = adapter
        self._current_match = None

    @property
    def current_match(self) -> SearchMatch | None:
        return self._current_match

    def find_next(self, options: SearchOptions) -> SearchMatch | None:
        """Find the next occurrence and emit signals."""
        if self._adapter is None or not options.text:
            self.no_match_found.emit()
            return None

        try:
            match = self._adapter.find_next(options, start_from=self._current_match)
        except Exception as e:
            logger.warning("Search failed: %s", e)
            self.status_message.emit(safe_tr("查找发生错误: ") + str(e))
            self.no_match_found.emit()
            return None

        if match is not None:
            self._current_match = match
            self._adapter.focus_match(match)
            self.match_found.emit(match)
            return match
        else:
            self._current_match = None
            self.no_match_found.emit()
            return None

    def replace_one(self, options: SearchOptions) -> SearchMatch | None:
        """Replace the current match and advance to the next."""
        if self._adapter is None:
            self.no_match_found.emit()
            return None

        if self._current_match is None:
            # If nothing currently selected, find first
            return self.find_next(options)

        try:
            nxt = self._adapter.replace_one(options, self._current_match)
            self._current_match = nxt
            if nxt is not None:
                self.match_found.emit(nxt)
            else:
                self.no_match_found.emit()
            return nxt
        except Exception as e:
            logger.warning("Replace failed: %s", e)
            self.status_message.emit(safe_tr("替换发生错误: ") + str(e))
            return None

    def replace_all(self, options: SearchOptions) -> int:
        """Replace all occurrences across the active document or sheet."""
        if self._adapter is None or not options.text:
            self.replace_completed.emit(0)
            return 0

        try:
            count = self._adapter.replace_all(options)
            self._current_match = None
            self.replace_completed.emit(count)
            return count
        except Exception as e:
            logger.warning("Replace all failed: %s", e)
            self.status_message.emit(safe_tr("全部替换发生错误: ") + str(e))
            self.replace_completed.emit(0)
            return 0
