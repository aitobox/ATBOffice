"""Undo for Lectern: each step is the difference between two copies of the deck.

Lectern edits its model from many places (toolbar commands, task panes,
dialogs, direct manipulation on the canvas, the notes and outline panes). Rather
than teach every one of them to describe its own inverse, the history keeps a
copy of the presentation as it was after the last recorded step. Whenever
something reports an edit, it compares the deck with that copy at the end of
the event-loop turn and records the change as one step. A copy of a typical
deck takes a few milliseconds: images and other binary payloads are shared,
not copied.

Edits are reported by:

* every command run through the action registry,
* ``set_modified(True)``,
* the workspace's ``content_edited`` signal (canvas moves, notes, outline).
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from PySide6.QtCore import QObject, QTimer

from atboffice.core.fault_guard import is_alive, safe_single_shot
from atboffice.core.i18n import safe_tr
from atboffice.core.undo import AppliedCommand, UndoService

logger = logging.getLogger(__name__)

#: Edit kinds whose consecutive steps merge (typing in a pane).
_MERGEABLE_KINDS = {"notes": 0x4C45_0001, "outline": 0x4C45_0002}

_KIND_LABELS = {
    "canvas": "编辑",
    "notes": "键入备注",
    "outline": "编辑大纲",
    "move_slide": "移动幻灯片",
    "handout_master": "编辑讲义母版",
    "notes_master": "编辑备注母版",
}


def snapshot_presentation(pres: Any) -> Any:
    """Deep copy of ``pres`` that shares the read-only source package."""
    memo: dict[int, Any] = {}
    props = getattr(pres, "props", None) or {}
    source = props.get("_source_package")
    if source is not None:
        memo[id(source)] = source
    return copy.deepcopy(pres, memo)


class PresentationHistory(QObject):
    """Checkpoint-based undo history of a Lectern window."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.service = UndoService(self)
        self._source: Any = None
        self._baseline: Any = None
        self._pending = False
        self._label: str | None = None
        self._kind: str | None = None
        self._restoring = False
        self._flush_timer: QTimer | None = None
        self.reset()

    # -- state -----------------------------------------------------------------

    def _presentation(self) -> Any:
        return self.window.presentation_view.presentation

    def cancel_pending(self) -> None:
        """Cancel any scheduled end-of-turn flush safely."""
        self._pending = False
        self._label = self._kind = None
        timer = getattr(self, "_flush_timer", None)
        self._flush_timer = None
        if timer is not None and is_alive(timer):
            try:
                timer.stop()
            except Exception:
                logger.debug("Failed to stop pending flush timer", exc_info=True)

    def reset(self) -> None:
        """Start a new history for the presentation now shown (it was loaded)."""
        self.cancel_pending()
        if self._restoring:
            return
        self._source = self._presentation()
        self._baseline = snapshot_presentation(self._source)
        self._pending = False
        self._label = self._kind = None
        self.service.clear()

    # -- recording -------------------------------------------------------------

    def note_edit(self, kind: str = "edit", label: str | None = None) -> None:
        """Something may have changed the deck: record it at the end of this turn."""
        if (
            self._restoring
            or not self.service.is_recording
            or not is_alive(self)
            or not is_alive(self.window)
        ):
            return
        if label and not self._label:
            self._label = label
        # A plain "edit" (from set_modified) does not hide a more specific kind
        # reported in the same turn; two different specific kinds give "mixed".
        if self._kind in (None, "edit"):
            self._kind = kind
        elif kind not in ("edit", self._kind):
            self._kind = "mixed"
        if not self._pending:
            self._pending = True
            self._flush_timer = safe_single_shot(0, self, self.flush)

    def flush(self) -> None:
        """Record the pending change now (before an undo, or at the end of the turn)."""
        self._flush_timer = None
        if not self._pending or not is_alive(self) or not is_alive(self.window):
            self._pending = False
            return
        self._pending = False
        label, kind = self._label, self._kind
        self._label = self._kind = None
        pres = self._presentation()
        if pres is not self._source:
            self.reset()
            return
        try:
            after = snapshot_presentation(pres)
        except Exception:
            logger.exception("Failed to snapshot presentation during undo recording")
            return
        if after == self._baseline:
            return
        before, self._baseline = self._baseline, after
        text = label or safe_tr(_KIND_LABELS.get(kind or "", "编辑"))
        merge_id = _MERGEABLE_KINDS.get(kind or "", -1)
        self.service.record(
            text,
            lambda: self._restore(before),
            lambda: self._restore(after),
            merge_id=merge_id,
            merge=_merge_steps if merge_id != -1 else None,
            data=kind,
        )

    # -- replay ----------------------------------------------------------------

    def _restore(self, state: Any) -> None:
        view = self.window.presentation_view
        ws = view.workspace
        index = ws.current_slide_index
        pres = snapshot_presentation(state)
        self._restoring = True
        try:
            view.load_presentation(pres)
        finally:
            self._restoring = False
        if pres.slides:
            ws.set_current_slide_index(max(0, min(index, len(pres.slides) - 1)))
        self._source = pres
        self._baseline = state


def _merge_steps(first: AppliedCommand, second: AppliedCommand) -> bool:
    if first.data != second.data:
        return False
    first.redo_fn = second.redo_fn
    return True
