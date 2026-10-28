"""Unit tests for RecentFilesManager and RecentItem."""

from __future__ import annotations

import time
from pathlib import Path

from atboffice.core.recent_files import (
    DEFAULT_STORAGE_PATH,
    RecentFilesManager,
)


def test_recent_files_add_and_get(tmp_path: Path):
    store_file = tmp_path / "recent.json"
    doc_file = tmp_path / "test.docx"
    doc_file.write_text("dummy")

    mgr = RecentFilesManager(storage_path=store_file, max_items=5)
    item = mgr.add_file(doc_file, app="quire")
    assert item.title == "test.docx"
    assert item.app == "quire"
    assert item.size_bytes == 5
    assert isinstance(item.last_opened, float)
    assert item.last_opened > 0

    entries = mgr.get_entries()
    assert len(entries) == 1
    assert entries[0].path == doc_file.resolve()


def test_recent_files_max_limit_fifo(tmp_path: Path):
    store_file = tmp_path / "recent.json"
    mgr = RecentFilesManager(storage_path=store_file, max_items=2)
    f1 = tmp_path / "1.docx"
    f2 = tmp_path / "2.xlsx"
    f3 = tmp_path / "3.pptx"
    for f in (f1, f2, f3):
        f.touch()
        mgr.add_file(f, app="generic")

    entries = mgr.get_entries()
    assert len(entries) == 2
    assert entries[0].path == f3.resolve()
    assert entries[1].path == f2.resolve()


def test_recent_files_remove_and_clear(tmp_path: Path):
    store_file = tmp_path / "recent.json"
    mgr = RecentFilesManager(storage_path=store_file)
    f1 = tmp_path / "1.docx"
    f1.touch()
    mgr.add_file(f1, app="quire")
    assert len(mgr.get_entries()) == 1

    # Remove non-existent file returns False
    assert mgr.remove_file(tmp_path / "nonexistent.docx") is False
    assert len(mgr.get_entries()) == 1

    # Remove existing file returns True
    assert mgr.remove_file(f1) is True
    assert len(mgr.get_entries()) == 0

    # Test clear_all
    f2 = tmp_path / "2.xlsx"
    f2.touch()
    mgr.add_file(f2, app="ledger")
    assert len(mgr.get_entries()) == 1
    mgr.clear_all()
    assert len(mgr.get_entries()) == 0


def test_recent_files_re_add_promotes_to_top(tmp_path: Path):
    store_file = tmp_path / "recent.json"
    mgr = RecentFilesManager(storage_path=store_file, max_items=5)
    f1 = tmp_path / "1.docx"
    f2 = tmp_path / "2.xlsx"
    f1.write_text("short")
    f2.write_text("medium")

    mgr.add_file(f1, app="quire")
    time.sleep(0.01)
    mgr.add_file(f2, app="ledger")

    entries = mgr.get_entries()
    assert len(entries) == 2
    assert entries[0].path == f2.resolve()
    assert entries[1].path == f1.resolve()

    # Re-adding f1 should move f1 to the top and update app/size
    f1.write_text("much longer content")
    time.sleep(0.01)
    updated_item = mgr.add_file(str(f1), app="quire")

    entries = mgr.get_entries()
    assert len(entries) == 2
    assert entries[0].path == f1.resolve()
    assert entries[0].size_bytes == len("much longer content")
    assert entries[1].path == f2.resolve()
    assert updated_item.path == f1.resolve()


def test_recent_files_persistence_roundtrip(tmp_path: Path):
    store_file = tmp_path / "recent.json"
    mgr1 = RecentFilesManager(storage_path=store_file, max_items=5)

    f1 = tmp_path / "doc.docx"
    f1.write_text("hello")
    mgr1.add_file(f1, app="quire")

    # Second instance pointing to same file
    mgr2 = RecentFilesManager(storage_path=store_file, max_items=5)
    entries = mgr2.get_entries()
    assert len(entries) == 1
    assert entries[0].path == f1.resolve()
    assert entries[0].app == "quire"
    assert entries[0].title == "doc.docx"
    assert entries[0].size_bytes == 5


def test_recent_files_missing_or_corrupt_json(tmp_path: Path):
    store_file = tmp_path / "sub_dir" / "corrupted.json"
    store_file.parent.mkdir(parents=True, exist_ok=True)
    store_file.write_text("{ this is invalid json !!!", encoding="utf-8")

    # Corrupted JSON should not crash, should start with empty list
    mgr = RecentFilesManager(storage_path=store_file)
    assert len(mgr.get_entries()) == 0

    # Saving should overwrite the corrupted file properly
    f1 = tmp_path / "doc.docx"
    f1.touch()
    mgr.add_file(f1, app="quire")
    assert len(mgr.get_entries()) == 1

    # Reload and verify valid JSON
    mgr_reloaded = RecentFilesManager(storage_path=store_file)
    assert len(mgr_reloaded.get_entries()) == 1


def test_recent_files_nonexistent_target_file(tmp_path: Path):
    store_file = tmp_path / "recent.json"
    mgr = RecentFilesManager(storage_path=store_file)
    ghost_file = tmp_path / "ghost.docx"

    # Does not crash when file doesn't exist on disk
    item = mgr.add_file(ghost_file, app="quire")
    assert item.title == "ghost.docx"
    assert item.size_bytes == 0
    assert item.exists is False


def test_recent_files_default_storage_path():
    mgr = RecentFilesManager()
    assert mgr.storage_path == DEFAULT_STORAGE_PATH
