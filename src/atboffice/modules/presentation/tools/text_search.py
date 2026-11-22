"""Find & Replace adapter for Lectern presentations (shared ``FindReplaceDialog``)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from atboffice.core.search import SearchAdapter, SearchMatch, SearchOptions
from atboffice.modules.presentation.tools.text_targets import (
    ParagraphRef,
    iter_paragraphs,
    paragraph_text,
    replace_at,
)


class PresentationSearchAdapter(SearchAdapter):
    """Searches every slide's shapes, group children, table cells and speaker notes.

    ``on_focus(ref, start, end)`` is called to reveal a match (switch slide, select shape).
    ``on_changed()`` is called after any replacement so the view can repaint.
    """

    def __init__(
        self,
        presentation: Any,
        on_focus: Callable[[ParagraphRef, int, int], None] | None = None,
        on_changed: Callable[[], None] | None = None,
        start_slide: int = 0,
    ) -> None:
        self.presentation = presentation
        self.on_focus = on_focus
        self.on_changed = on_changed
        self.start_slide = start_slide

    def find_all(self, options: SearchOptions) -> list[SearchMatch]:
        if not options.text:
            return []
        pattern = options.compile_regex()
        out: list[SearchMatch] = []
        for ref, text in iter_paragraphs(self.presentation):
            for m in pattern.finditer(text):
                if m.end() == m.start():
                    continue
                out.append(
                    SearchMatch(
                        target_id=ref.key,
                        start=m.start(),
                        end=m.end(),
                        matched_text=m.group(0),
                        extra={"ref": ref},
                    )
                )
        return out

    @staticmethod
    def _order(m: SearchMatch) -> tuple[Any, ...]:
        s_idx, owner, p_idx = m.target_id
        return s_idx, repr(owner), p_idx, m.start

    def find_next(
        self, options: SearchOptions, start_from: SearchMatch | None = None
    ) -> SearchMatch | None:
        matches = sorted(self.find_all(options), key=self._order)
        if not matches:
            return None
        if start_from is None:
            later = [m for m in matches if m.target_id[0] >= self.start_slide]
            if options.direction == "down":
                return later[0] if later else matches[0]
            return matches[-1]
        anchor = self._order(start_from)
        if options.direction == "down":
            return next((m for m in matches if self._order(m) > anchor), matches[0])
        return next((m for m in reversed(matches) if self._order(m) < anchor), matches[-1])

    def focus_match(self, match: SearchMatch) -> None:
        if self.on_focus is not None:
            self.on_focus(match.extra["ref"], match.start, match.end)

    def _replacement(self, options: SearchOptions, matched: str) -> str:
        if options.use_regex:
            return options.compile_regex().sub(options.replace_text, matched, count=1)
        return options.replace_text

    def replace_one(self, options: SearchOptions, match: SearchMatch) -> SearchMatch | None:
        ref: ParagraphRef = match.extra["ref"]
        current = paragraph_text(self.presentation, ref)
        if current is None or current[match.start : match.end] != match.matched_text:
            return self.find_next(options, start_from=match)  # stale match: just move on
        new = self._replacement(options, match.matched_text)
        replace_at(self.presentation, ref, match.start, match.end, new)
        if self.on_changed is not None:
            self.on_changed()
        moved = SearchMatch(match.target_id, match.start, match.start + len(new), new, match.extra)
        nxt = self.find_next(options, start_from=moved)
        if nxt is not None:
            self.focus_match(nxt)
        return nxt

    def replace_all(self, options: SearchOptions) -> int:
        matches = sorted(self.find_all(options), key=self._order, reverse=True)
        for m in matches:  # back to front keeps earlier offsets valid
            replace_at(
                self.presentation,
                m.extra["ref"],
                m.start,
                m.end,
                self._replacement(options, m.matched_text),
            )
        if matches and self.on_changed is not None:
            self.on_changed()
        return len(matches)
