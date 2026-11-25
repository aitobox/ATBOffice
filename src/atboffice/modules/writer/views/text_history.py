"""Undo recording for typing and deleting in Quire.

Copying the whole document for every keystroke would make typing slow in long
documents, so each step stores only the top-level blocks of one story that the
edit touched. Before an edit, the recorder copies the blocks around the caret
and the selection (one block of margin each side, for paragraph merges); after
it, the blocks that differ by identity or lie in that window form the changed
slice. Undo puts the old slice back, redo the new one.

Edits that span two stories fall back to a snapshot of the whole document.
Consecutive typing in one paragraph is merged into one step, ending at a word
boundary, as in Word.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from atboffice.core.i18n import safe_tr
from atboffice.core.undo import AppliedCommand
from atboffice.modules.writer.models.document import Document, Story, info, ptext, reindex
from atboffice.modules.writer.views.caret_controller import DocPos, Selection

#: QUndoCommand id shared by mergeable typing steps.
TYPING_MERGE_ID = 0x5157_0001

#: Labels whose steps merge with the next step of the same kind.
_MERGEABLE = frozenset({"键入"})

StoryRef = tuple[str, Any]


@dataclass(frozen=True)
class Caret:
    """Caret and selection, restored with the document."""

    anchor: DocPos
    focus: DocPos
    pos: DocPos


@dataclass
class SliceEdit:
    """``story.blocks[start:start + len(before)]`` became ``after``."""

    story: StoryRef
    start: int
    before: list[Any]
    after: list[Any]
    caret_before: Caret
    caret_after: Caret
    label: str
    text: str = ""
    parts_before: dict[str, Any] = field(default_factory=dict)
    parts_after: dict[str, Any] = field(default_factory=dict)


@dataclass
class _Pending:
    label: str
    caret: Caret
    parts: dict[str, Any] = field(default_factory=dict)
    story: StoryRef | None = None
    old_blocks: list[Any] = field(default_factory=list)
    saved: dict[int, Any] = field(default_factory=dict)
    snapshot: dict[str, Any] | None = None


def story_ref(doc: Document, story: Any) -> StoryRef | None:
    """A stable name for ``story`` (survives whole-document snapshot restores)."""
    if story is doc.main:
        return ("main", None)
    for attr in ("hf", "fn", "en", "comments"):
        for key, value in getattr(doc, attr).items():
            if value is story:
                return (attr, key)
    return None


def resolve_story(doc: Document, ref: StoryRef) -> Story | None:
    attr, key = ref
    if attr == "main":
        return doc.main
    return getattr(doc, attr, {}).get(key)


class TextEditRecorder:
    """Turns the caret controller's edits into undo steps on ``view.history``."""

    def __init__(self, view: Any) -> None:
        self.view = view
        self._depth = 0
        self._pending: _Pending | None = None

    # -- capture ---------------------------------------------------------------

    @property
    def _doc(self) -> Document:
        return self.view.doc

    def _caret(self) -> Caret:
        ctl = self.view.controller
        return Caret(ctl.selection.anchor, ctl.selection.focus, ctl.pos)

    def begin(self, label: str, parts: tuple[str, ...] = ()) -> None:
        self._depth += 1
        if self._depth > 1:
            return
        if not self.view.history.is_recording:
            self._pending = None
            return
        self._pending = self._capture(label)
        if self._pending.snapshot is None:
            doc = self._doc
            self._pending.parts = {name: copy.deepcopy(getattr(doc, name)) for name in parts}

    def end(self) -> None:
        self._depth -= 1
        if self._depth > 0:
            return
        pending, self._pending = self._pending, None
        if pending is not None:
            self._commit(pending)

    def _capture(self, label: str) -> _Pending:
        doc = self._doc
        caret = self._caret()
        pending = _Pending(label=label, caret=caret)
        stories: set[StoryRef | None] = set()
        tops: list[Any] = []
        for pos in {caret.anchor, caret.focus, caret.pos}:
            inf = info(doc, pos.para_id)
            if not inf:
                continue
            stories.add(story_ref(doc, inf["story"]))
            parents = inf.get("parents") or []
            tops.append(parents[0]["tbl"] if parents else inf["p"])
        ref = stories.pop() if len(stories) == 1 else None
        story = resolve_story(doc, ref) if ref is not None else None
        if story is None:
            pending.snapshot = self.view._snapshot_doc()
            return pending
        blocks = list(story.blocks)
        index = {id(b): i for i, b in enumerate(blocks)}
        found = [index[id(b)] for b in tops if id(b) in index]
        if not found:
            pending.snapshot = self.view._snapshot_doc()
            return pending
        lo = max(0, min(found) - 1)
        hi = min(len(blocks) - 1, max(found) + 1)
        pending.story = ref
        pending.old_blocks = blocks
        pending.saved = {i: copy.deepcopy(blocks[i]) for i in range(lo, hi + 1)}
        return pending

    # -- commit ----------------------------------------------------------------

    def _commit(self, pending: _Pending) -> None:
        label = safe_tr(pending.label)
        caret_after = self._caret()
        if pending.snapshot is not None:
            before = pending.snapshot
            after = self.view._snapshot_doc()
            if after == before:
                return
            self.view.history.record(
                label,
                lambda: self._restore_snapshot(before, pending.caret),
                lambda: self._restore_snapshot(after, caret_after),
            )
            return
        story = resolve_story(self._doc, pending.story) if pending.story else None
        if story is None:
            return
        edit = self._diff(pending, list(story.blocks), caret_after)
        for name, before in pending.parts.items():
            after = getattr(self._doc, name)
            if after != before:
                edit.parts_before[name] = before
                edit.parts_after[name] = copy.deepcopy(after)
        if edit.before == edit.after and not edit.parts_after:
            return
        mergeable = (
            pending.label in _MERGEABLE
            and len(edit.before) == len(edit.after)
            and not edit.parts_after
        )
        self.view.history.record(
            label,
            lambda: self._apply(edit, undo=True),
            lambda: self._apply(edit, undo=False),
            merge_id=TYPING_MERGE_ID if mergeable else -1,
            merge=_merge_typing if mergeable else None,
            data=edit,
        )

    def _diff(self, pending: _Pending, new: list[Any], caret_after: Caret) -> SliceEdit:
        old = pending.old_blocks
        saved = pending.saved
        lo, hi = min(saved), max(saved)
        start = 0
        limit = min(len(old), len(new))
        while start < limit and start < lo and old[start] is new[start]:
            start += 1
        tail = 0
        while (
            tail < limit - start
            and len(old) - 1 - tail > hi
            and old[len(old) - 1 - tail] is new[len(new) - 1 - tail]
        ):
            tail += 1
        before = [
            saved[i] if i in saved else copy.deepcopy(old[i]) for i in range(start, len(old) - tail)
        ]
        after = copy.deepcopy(new[start : len(new) - tail])
        text = ""
        if pending.caret.pos.para_id == caret_after.pos.para_id:
            p = self.view.controller._paragraph_by_id(caret_after.pos.para_id)
            if p is not None:
                full = ptext(p)
                a, b = pending.caret.pos.offset, caret_after.pos.offset
                text = full[a:b] if 0 <= a <= b <= len(full) else ""
        return SliceEdit(
            story=pending.story,  # type: ignore[arg-type]
            start=start,
            before=before,
            after=after,
            caret_before=pending.caret,
            caret_after=caret_after,
            label=pending.label,
            text=text,
        )

    # -- replay ----------------------------------------------------------------

    def _apply(self, edit: SliceEdit, *, undo: bool) -> None:
        story = resolve_story(self._doc, edit.story)
        if story is None:
            return
        current, target = (edit.after, edit.before) if undo else (edit.before, edit.after)
        story.blocks[edit.start : edit.start + len(current)] = copy.deepcopy(target)
        for name, value in (edit.parts_before if undo else edit.parts_after).items():
            setattr(self._doc, name, copy.deepcopy(value))
        self._finish(edit.caret_before if undo else edit.caret_after)

    def _restore_snapshot(self, state: dict[str, Any], caret: Caret) -> None:
        for attr, value in state.items():
            setattr(self._doc, attr, copy.deepcopy(value))
        self._finish(caret)

    def _finish(self, caret: Caret) -> None:
        reindex(self._doc)
        ctl = self.view.controller
        ctl.doc = self._doc
        ctl.pos = caret.pos
        ctl.selection = Selection(caret.anchor, caret.focus)
        ctl._ensure_valid_pos()
        ctl.preferred_x = None
        ctl.repaginate_and_refresh()
        self.view.pagination = ctl.pagination
        self.view._update_scroll_ranges()
        self.view.viewport().update()


def _merge_typing(first: AppliedCommand, second: AppliedCommand) -> bool:
    """Fold ``second`` into ``first`` while typing continues in the same word run."""
    a, b = first.data, second.data
    if not isinstance(a, SliceEdit) or not isinstance(b, SliceEdit):
        return False
    if (a.story, a.start, len(a.after)) != (b.story, b.start, len(b.before)):
        return False
    if len(b.before) != len(b.after) or a.caret_after != b.caret_before:
        return False
    # A new word after a space starts a new step.
    if a.text[-1:].isspace() and b.text[:1] and not b.text[:1].isspace():
        return False
    a.after = b.after
    a.caret_after = b.caret_after
    a.text += b.text
    return True
