"""Spell checking across a presentation, protocol-compatible with ``SheetSpellChecker``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QCoreApplication

from atboffice.modules.presentation.tools.text_targets import (
    ParagraphRef,
    iter_paragraphs,
    paragraph_text,
    replace_at,
)
from atboffice.modules.spreadsheet.tools.sheet_spelling import WORD_RE


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("PresentationSpelling", text)


@dataclass
class SlideSpellIssue:
    ref: ParagraphRef
    start: int
    end: int
    word: str


class PresentationSpellChecker:
    """Walks slides in order from ``start_slide`` (wrapping), like PowerPoint."""

    def __init__(self, presentation: Any, engine: Any, start_slide: int = 0) -> None:
        self.presentation = presentation
        self.engine = engine
        refs = [ref for ref, _ in iter_paragraphs(presentation)]
        n = len(getattr(presentation, "slides", []))
        start = max(0, min(start_slide, n - 1)) if n else 0
        self.refs = [r for r in refs if r.slide_idx >= start] + [
            r for r in refs if r.slide_idx < start
        ]
        self.index = 0
        self.offset = 0
        self.ignore_all: set[str] = set()
        self.change_all: dict[str, str] = {}
        self.changed = False

    def _is_ok(self, word: str) -> bool:
        if word.lower() in self.ignore_all or len(word) <= 1 or word.isupper():
            return True
        return bool(self.engine.is_valid_word(word))

    def next_issue(self) -> SlideSpellIssue | None:
        while self.index < len(self.refs):
            ref = self.refs[self.index]
            text = paragraph_text(self.presentation, ref)
            if text is not None:
                for m in WORD_RE.finditer(text, self.offset):
                    word = m.group(0)
                    if word.lower() in self.change_all:
                        self._replace(ref, m.start(), m.end(), self.change_all[word.lower()])
                        return self.next_issue()
                    if not self._is_ok(word):
                        return SlideSpellIssue(ref, m.start(), m.end(), word)
            self.index += 1
            self.offset = 0
        return None

    def _replace(self, ref: ParagraphRef, start: int, end: int, new: str) -> None:
        replace_at(self.presentation, ref, start, end, new)
        self.changed = True
        self.offset = start + len(new)

    def describe_issue(self, issue: SlideSpellIssue) -> str:
        where = safe_tr("备注") if issue.ref.owner[0] == "notes" else safe_tr("幻灯片")
        return safe_tr("{0} {1}").format(where, issue.ref.slide_idx + 1)

    def ignore(self, issue: SlideSpellIssue) -> None:
        self.offset = issue.end

    def ignore_everywhere(self, issue: SlideSpellIssue) -> None:
        self.ignore_all.add(issue.word.lower())
        self.offset = issue.end

    def add_to_dictionary(self, issue: SlideSpellIssue) -> None:
        if hasattr(self.engine, "add_to_custom_dict"):
            self.engine.add_to_custom_dict(issue.word)
        self.ignore_all.add(issue.word.lower())
        self.offset = issue.end

    def change(self, issue: SlideSpellIssue, new: str) -> None:
        self._replace(issue.ref, issue.start, issue.end, new)

    def change_everywhere(self, issue: SlideSpellIssue, new: str) -> None:
        self.change_all[issue.word.lower()] = new
        self.change(issue, new)
