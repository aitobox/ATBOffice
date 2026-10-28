"""Recent files history manager and data model for ATBOffice."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import tempfile
import time
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

DEFAULT_STORAGE_PATH: Path = Path.home() / ".atboffice" / "recent_files.json"


class RecentItem(NamedTuple):
    """Immutable metadata record for a recently opened office document."""

    path: Path
    app: str
    title: str
    size_bytes: int
    last_opened: float

    @property
    def exists(self) -> bool:
        """Check whether the referenced file currently exists on disk."""
        try:
            return self.path.exists()
        except OSError:
            return False

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entry to a JSON-compatible dictionary."""
        return {
            "path": str(self.path),
            "app": self.app,
            "title": self.title,
            "size_bytes": self.size_bytes,
            "last_opened": self.last_opened,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecentItem | None:
        """Construct a RecentItem from a dictionary, returning None if malformed."""
        try:
            raw_path = data.get("path")
            if not raw_path:
                return None
            p = Path(raw_path).resolve()
            app = str(data.get("app", "generic"))
            title = str(data.get("title", p.name))
            size_bytes = int(data.get("size_bytes", 0))
            last_opened = float(data.get("last_opened", 0.0))
            return cls(
                path=p,
                app=app,
                title=title,
                size_bytes=size_bytes,
                last_opened=last_opened,
            )
        except (TypeError, ValueError) as err:
            logger.warning("Failed to parse recent item data %r: %s", data, err)
            return None


class RecentFilesManager:
    """Manages document history serialization and LRU retention for ATBOffice."""

    def __init__(
        self,
        storage_path: Path | str | None = None,
        max_items: int = 20,
    ) -> None:
        """Initialize the recent files manager.

        Args:
            storage_path: JSON file path for persistence. Defaults to ~/.atboffice/recent_files.json.
            max_items: Maximum number of recent files to retain (FIFO eviction).
        """
        if storage_path is not None:
            self.storage_path = Path(storage_path).resolve()
        else:
            self.storage_path = DEFAULT_STORAGE_PATH

        self.max_items = max(1, max_items)
        self._entries: list[RecentItem] = []
        self.load()

    def get_entries(self) -> list[RecentItem]:
        """Return a copy of the list of recent document records (newest first)."""
        return list(self._entries)

    def add_file(self, path: str | Path, app: str) -> RecentItem:
        """Add or promote a file in recent history.

        Args:
            path: Target file path.
            app: Application identifier (e.g., 'quire', 'ledger', 'lectern').

        Returns:
            The created or updated RecentItem.
        """
        resolved_path = Path(path).resolve()
        title = resolved_path.name

        size_bytes = 0
        try:
            if resolved_path.exists():
                size_bytes = resolved_path.stat().st_size
        except OSError:
            size_bytes = 0

        item = RecentItem(
            path=resolved_path,
            app=app,
            title=title,
            size_bytes=size_bytes,
            last_opened=time.time(),
        )

        # Remove existing record with same path if already tracked (LRU / MRU promotion)
        self._entries = [e for e in self._entries if e.path != resolved_path]
        self._entries.insert(0, item)

        # Enforce maximum retention capacity
        if len(self._entries) > self.max_items:
            self._entries = self._entries[: self.max_items]

        self.save()
        return item

    def remove_file(self, path: str | Path) -> bool:
        """Remove a specific file from recent history.

        Args:
            path: Target file path.

        Returns:
            True if an item was found and removed, False otherwise.
        """
        target = Path(path).resolve()
        initial_count = len(self._entries)
        self._entries = [e for e in self._entries if e.path != target]
        if len(self._entries) < initial_count:
            self.save()
            return True
        return False

    def clear_all(self) -> None:
        """Clear all entries from recent history and update storage."""
        self._entries.clear()
        self.save()

    def load(self) -> None:
        """Load history entries from persistent JSON storage."""
        if not self.storage_path.exists():
            self._entries = []
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                logger.warning(
                    "Recent files data in %s is not a list. Resetting.",
                    self.storage_path,
                )
                self._entries = []
                return

            loaded_entries: list[RecentItem] = []
            seen_paths: set[Path] = set()

            for item_dict in data:
                if not isinstance(item_dict, dict):
                    continue
                item = RecentItem.from_dict(item_dict)
                if item is not None and item.path not in seen_paths:
                    seen_paths.add(item.path)
                    loaded_entries.append(item)
                    if len(loaded_entries) >= self.max_items:
                        break

            self._entries = loaded_entries
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as err:
            logger.warning(
                "Error loading recent files from %s: %s. Using empty list.",
                self.storage_path,
                err,
            )
            self._entries = []

    def save(self) -> None:
        """Persist current history entries to JSON storage atomically."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = [item.to_dict() for item in self._entries]

            # Atomic write via temporary file
            temp_file = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.storage_path.parent,
                delete=False,
                prefix="recent_",
                suffix=".tmp",
            )
            try:
                with temp_file as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                Path(temp_file.name).replace(self.storage_path)
            except Exception:
                # Clean up temp file on failure
                try:
                    Path(temp_file.name).unlink(missing_ok=True)
                except OSError:
                    pass
                raise
        except OSError as err:
            logger.error("Failed to save recent files to %s: %s", self.storage_path, err)
