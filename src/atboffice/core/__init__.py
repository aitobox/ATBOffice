"""Core application architecture, configuration, and event processing."""

from atboffice.core.app import ATBApplication, create_application
from atboffice.core.recent_files import (
    DEFAULT_STORAGE_PATH,
    RecentFilesManager,
    RecentItem,
)

__all__ = [
    "ATBApplication",
    "create_application",
    "DEFAULT_STORAGE_PATH",
    "RecentFilesManager",
    "RecentItem",
]

