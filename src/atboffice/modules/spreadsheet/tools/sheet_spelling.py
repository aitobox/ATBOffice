"""Worksheet spell checking on top of the shared offline ``SpellEngine``."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*[A-Za-z]|[A-Za-z]")


@dataclass
class SpellIssue:
    """A misspelled word inside a text cell."""

    r: int
    c: int
    start: int
    end: int
    word: str


def text_cells(sheet: Any, rect: tuple[int, int, int, int] | None = None) -> list[tuple[int, int]]:
    """Constant text cells (no formulas) in row-major order, optionally within ``rect``."""
    out = []
    for (r, c), cell in sheet.cells.items():
        if rect is not None and not (rect[0] <= r <= rect[2] and rect[1] <= c <= rect[3]):
            continue
        if cell.formula or not isinstance(cell.value, str) or not cell.value.strip():
            continue
        out.append((r, c))
    return sorted(out)


class SheetSpellChecker:
    """Walks text cells and yields misspellings, honouring ignore / change-all choices."""

    def __init__(self, sheet: Any, cells: Iterable[tuple[int, int]], engine: Any) -> None:
        self.sheet = sheet
        self.engine = engine
        self.cells = list(cells)
        self.index = 0
        self.offset = 0
        self.ignore_all: set[str] = set()
        self.change_all: dict[str, str] = {}
        self.changed_cells: set[tuple[int, int]] = set()

    def _is_ok(self, word: str) -> bool:
        if word.lower() in self.ignore_all:
            return True
        if len(word) <= 1 or word.isupper():
            return True  # single letters and acronyms, as Excel does by default
        return bool(self.engine.is_valid_word(word))

    def next_issue(self) -> SpellIssue | None:
        """Return the next misspelling, applying pending "Change All" replacements."""
        while self.index < len(self.cells):
            r, c = self.cells[self.index]
            text = self.sheet.get_cell_value(r, c)
            if not isinstance(text, str):
                self.index += 1
                self.offset = 0
                continue
            for m in WORD_RE.finditer(text, self.offset):
                word = m.group(0)
                if word.lower() in self.change_all:
                    self._replace(r, c, m.start(), m.end(), self.change_all[word.lower()])
                    return self.next_issue()
                if not self._is_ok(word):
                    return SpellIssue(r, c, m.start(), m.end(), word)
            self.index += 1
            self.offset = 0
        return None

    def _replace(self, r: int, c: int, start: int, end: int, new: str) -> None:
        text = self.sheet.get_cell_value(r, c)
        self.sheet.ensure_cell(r, c).value = text[:start] + new + text[end:]
        self.sheet.dirty = True
        self.changed_cells.add((r, c))
        self.offset = start + len(new)

    def ignore(self, issue: SpellIssue) -> None:
        self.offset = issue.end

    def ignore_everywhere(self, issue: SpellIssue) -> None:
        self.ignore_all.add(issue.word.lower())
        self.offset = issue.end

    def add_to_dictionary(self, issue: SpellIssue) -> None:
        if hasattr(self.engine, "add_to_custom_dict"):
            self.engine.add_to_custom_dict(issue.word)
        self.ignore_all.add(issue.word.lower())
        self.offset = issue.end

    def change(self, issue: SpellIssue, new: str) -> None:
        self._replace(issue.r, issue.c, issue.start, issue.end, new)

    def change_everywhere(self, issue: SpellIssue, new: str) -> None:
        self.change_all[issue.word.lower()] = new
        self.change(issue, new)
