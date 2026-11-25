"""Tests for the shared undo service."""

from __future__ import annotations

from atboffice.core.undo import UndoService


def _counter_service(qapp, limit: int = 100) -> tuple[UndoService, dict[str, int]]:
    svc = UndoService(limit=limit)
    state = {"v": 0}
    return svc, state


def _set(svc: UndoService, state: dict[str, int], value: int, **kwargs) -> None:
    old = state["v"]
    state["v"] = value
    svc.record(
        f"set {value}",
        lambda: state.__setitem__("v", old),
        lambda: state.__setitem__("v", value),
        **kwargs,
    )


def test_record_does_not_reapply_and_undo_redo_replay(qapp) -> None:
    svc, state = _counter_service(qapp)
    _set(svc, state, 1)
    _set(svc, state, 2)
    assert state["v"] == 2
    assert svc.labels("undo") == ["set 2", "set 1"]
    assert svc.undo() and state["v"] == 1
    assert svc.labels("redo") == ["set 2"]
    assert svc.redo() and state["v"] == 2
    assert svc.undo_steps("undo", 5) == 2
    assert state["v"] == 0
    assert not svc.can_undo()


def test_history_is_bounded(qapp) -> None:
    svc, state = _counter_service(qapp, limit=3)
    for i in range(1, 10):
        _set(svc, state, i)
    assert len(svc) == 3
    assert svc.undo_steps("undo", 10) == 3
    assert state["v"] == 6


def test_nothing_is_recorded_while_replaying_or_paused(qapp) -> None:
    svc = UndoService()
    log: list[str] = []

    def undo() -> None:
        log.append("undo")
        # Restore code that goes through normal editing paths must not record.
        svc.record("nested", lambda: None, lambda: None)

    svc.record("step", undo, lambda: None)
    svc.undo()
    assert log == ["undo"]
    assert len(svc) == 1
    with svc.paused():
        svc.record("ignored", lambda: None, lambda: None)
    assert len(svc) == 1


def test_track_records_only_real_changes(qapp) -> None:
    svc = UndoService()
    box = {"v": 1}
    svc.track("noop", lambda: dict(box), box.update, lambda: None)
    assert len(svc) == 0
    svc.track("set", lambda: dict(box), box.update, lambda: box.update(v=5))
    assert box == {"v": 5} and len(svc) == 1
    svc.undo()
    assert box == {"v": 1}


def test_merge_folds_consecutive_steps(qapp) -> None:
    svc, state = _counter_service(qapp)

    def merge(first, second) -> bool:
        first.redo_fn = second.redo_fn
        return True

    for i in (1, 2, 3):
        _set(svc, state, i, merge_id=42, merge=merge)
    assert len(svc) == 1
    svc.undo()
    assert state["v"] == 0
    svc.redo()
    assert state["v"] == 3


def test_failing_step_is_logged_not_raised(qapp, caplog) -> None:
    svc = UndoService()

    def boom() -> None:
        raise RuntimeError("broken step")

    svc.record("bad", boom, boom)
    assert svc.undo() is True
    assert "broken step" in caplog.text
