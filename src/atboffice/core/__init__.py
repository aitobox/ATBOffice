"""Core application architecture, configuration, and event processing."""

from atboffice.core.app import ATBApplication, create_application
from atboffice.core.recent_files import (
    DEFAULT_STORAGE_PATH,
    RecentFilesManager,
    RecentItem,
)
from atboffice.core.settings import AppSettings, get_app_settings
from atboffice.core.window_manager import WindowManager

__all__ = [
    "ATBApplication",
    "create_application",
    "DEFAULT_STORAGE_PATH",
    "RecentFilesManager",
    "RecentItem",
    "AppSettings",
    "get_app_settings",
    "WindowManager",
]

