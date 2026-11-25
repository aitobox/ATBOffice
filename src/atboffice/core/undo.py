"""Shared undo service: one bounded ``QUndoStack`` per document.

Quire, Ledger and Lectern all record their edits here. Every edit is recorded
*after* it has been applied, as a pair of callables (undo and redo), so callers
keep their existing "mutate the model, then refresh" code and only describe how
to go back and forth.

Two helpers cover the common cases:

* :meth:`UndoService.record` takes explicit undo / redo callables.
* :meth:`UndoService.track` captures a state before and after ``mutate()`` and
  records a step only when the state changed; ``restore(state)`` moves the model
  to either side.

While an undo or redo is being replayed, recording is suppressed, so restore
code that reuses normal editing paths can't push new steps onto the stack.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Steps kept per document. Older steps are dropped first.
DEFAULT_UNDO_LIMIT = 100


def _run(fn: Callable[[], Any], kind: str, label: str) -> None:
    # Qt calls undo()/redo() from C++, where a Python exception would only be
    # printed; log it with the step's name instead.
    try:
        fn()
    except Exception:
        logger.exception("Failed to %s %r", kind, label)


class AppliedCommand(QUndoCommand):
    """A change that has already been made to the model.

    The first ``redo()`` call, which ``QUndoStack.push`` makes immediately, is
    skipped because the change is already in place. Later calls replay it.

    ``merge_id`` (when not -1) and ``merge`` allow consecutive commands to be
    coalesced, as typing is: ``merge(self, other)`` returns True after folding
    ``other`` into ``self``.
    """

    def __init__(
        self,
        label: str,
        undo: Callable[[], Any],
        redo: Callable[[], Any],
        *,
        merge_id: int = -1,
        merge: Callable[[AppliedCommand, AppliedCommand], bool] | None = None,
        data: Any = None,
    ) -> None:
        super().__init__(label)
        self.undo_fn = undo
        self.redo_fn = redo
        self.data = data
        self._merge_id = merge_id
        self._merge = merge
        self._applied = True

    def redo(self) -> None:
        if self._applied:
            self._applied = False
            return
        _run(self.redo_fn, "redo", self.text())

    def undo(self) -> None:
        _run(self.undo_fn, "undo", self.text())

    def id(self) -> int:
        return self._merge_id

    def mergeWith(self, other: QUndoCommand) -> bool:
        if self._merge is None or not isinstance(other, AppliedCommand):
            return False
        return bool(self._merge(self, other))


class UndoService(QObject):
    """Undo history of one document.

    ``changed`` fires whenever the history moves (push, undo, redo, clear), so
    toolbars can refresh their Undo / Redo state and drop-down lists.
    """

    changed = Signal()

    def __init__(self, parent: QObject | None = None, limit: int = DEFAULT_UNDO_LIMIT) -> None:
        super().__init__(parent)
        self.stack = QUndoStack(self)
        self.stack.setUndoLimit(max(0, int(limit)))
        self.stack.indexChanged.connect(self.changed)
        self._replaying = 0
        self._paused = 0

    # -- recording -------------------------------------------------------------

    @property
    def is_replaying(self) -> bool:
        """True while an undo or redo is being applied."""
        return self._replaying > 0

    @property
    def is_recording(self) -> bool:
        """False while replaying or paused: new steps would be dropped."""
        return not self._replaying and not self._paused

    @contextmanager
    def paused(self) -> Iterator[None]:
        """Run a block whose edits must not be recorded (loading, resetting)."""
        self._paused += 1
        try:
            yield
        finally:
            self._paused -= 1

    def push(self, command: QUndoCommand) -> bool:
        """Push an already-applied command; returns False while not recording."""
        if not self.is_recording:
            return False
        self.stack.push(command)
        return True

    def record(
        self,
        label: str,
        undo: Callable[[], Any],
        redo: Callable[[], Any],
        *,
        merge_id: int = -1,
        merge: Callable[[AppliedCommand, AppliedCommand], bool] | None = None,
        data: Any = None,
    ) -> bool:
        """Record a change that has already been applied."""
        return self.push(
            AppliedCommand(label, undo, redo, merge_id=merge_id, merge=merge, data=data)
        )

    def record_states(
        self, label: str, before: T, after: T, restore: Callable[[T], Any]
    ) -> bool:
        """Record a change between two captured states of the model."""
        return self.record(label, lambda: restore(before), lambda: restore(after))

    def track(
        self,
        label: str,
        capture: Callable[[], T],
        restore: Callable[[T], Any],
        mutate: Callable[[], Any],
    ) -> Any:
        """Run ``mutate()`` and record one step if the captured state changed.

        Nothing is recorded when ``mutate`` returns ``False``.
        """
        if not self.is_recording:
            return mutate()
        before = capture()
        result = mutate()
        if result is False:
            return result
        after = capture()
        if after != before:
            self.record_states(label, before, after, restore)
        return result

    @contextmanager
    def macro(self, label: str) -> Iterator[None]:
        """Group every step recorded inside the block into one undo step."""
        if not self.is_recording:
            yield
            return
        self.stack.beginMacro(label)
        try:
            yield
        finally:
            self.stack.endMacro()

    # -- navigation ------------------------------------------------------------

    def can_undo(self) -> bool:
        return self.stack.canUndo()

    def can_redo(self) -> bool:
        return self.stack.canRedo()

    def undo(self) -> bool:
        """Undo one step; returns False when there is nothing to undo."""
        if not self.stack.canUndo():
            return False
        self._replay(self.stack.undo)
        return True

    def redo(self) -> bool:
        """Redo one step; returns False when there is nothing to redo."""
        if not self.stack.canRedo():
            return False
        self._replay(self.stack.redo)
        return True

    def undo_steps(self, kind: str, steps: int) -> int:
        """Undo (``kind == "undo"``) or redo several steps; returns how many ran."""
        step = self.undo if kind == "undo" else self.redo
        done = 0
        for _ in range(max(0, steps)):
            if not step():
                break
            done += 1
        return done

    def _replay(self, action: Callable[[], None]) -> None:
        self._replaying += 1
        try:
            action()
        finally:
            self._replaying -= 1

    # -- inspection ------------------------------------------------------------

    def labels(self, kind: str) -> list[str]:
        """Undo (or redo) step labels, the next one to run first."""
        stack = self.stack
        index = stack.index()
        if kind == "undo":
            return [stack.text(i) for i in range(index - 1, -1, -1)]
        return [stack.text(i) for i in range(index, stack.count())]

    def __len__(self) -> int:
        return self.stack.count()

    def clear(self) -> None:
        """Forget the whole history (a new document was loaded)."""
        self.stack.clear()
        self.changed.emit()

    def set_clean(self) -> None:
        """Mark the current position as the saved state."""
        self.stack.setClean()

    def is_clean(self) -> bool:
        return self.stack.isClean()
