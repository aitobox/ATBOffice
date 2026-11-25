"""Recovery drafts of different windows never overwrite each other."""

from __future__ import annotations

import os
from pathlib import Path

from atboffice.core.recovery_service import RecoveryService, list_orphan_drafts


def test_two_windows_with_the_same_name_keep_separate_drafts(qapp, tmp_path: Path) -> None:
    first = RecoveryService(recovery_dir=tmp_path)
    second = RecoveryService(recovery_dir=tmp_path)
    assert first.save_draft(b"one") and second.save_draft(b"two")
    drafts = sorted(p.read_bytes() for p in tmp_path.iterdir())
    assert drafts == [b"one", b"two"]
    first.cleanup()
    second.cleanup()


def test_tokened_draft_names_are_listed(tmp_path: Path) -> None:
    dead_pid = 2**22 + 12345
    (tmp_path / f"Report_recovery_{dead_pid}_0123abcd.docx").write_bytes(b"x")
    (tmp_path / f"Live_recovery_{os.getpid()}_89abcdef.docx").write_bytes(b"y")
    drafts = list_orphan_drafts(tmp_path)
    assert [(d.name, d.ext, d.pid) for d in drafts] == [("Report", ".docx", dead_pid)]
