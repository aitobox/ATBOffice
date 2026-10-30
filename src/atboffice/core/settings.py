"""Global application settings and preference persistence for ATBOffice."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS: dict[str, Any] = {
    # General
    "general/default_open_path": str(Path.home()),
    "general/recent_files_limit": 20,
    "general/start_behavior": "start_center",  # "start_center" or "new_doc"
    # View
    "view/ui_scale": "100%",  # "100%", "125%", "150%", "200%"
    "view/status_bar_timeout": 3000,  # milliseconds
    # Edit
    "edit/default_font_family": "Tahoma",
    "edit/default_font_size": 12,  # point size
    "edit/show_gridlines": True,
    # Save
    "save/auto_save_interval": 10,  # minutes
    "save/default_save_format": "docx",  # "docx", "xlsx", "pptx"
    # Language
    "locale/language": "zh-CN",
    # Theme
    "theme/active_theme": "blue",  # "blue", "silver", "olive", "classic"
}


class AppSettings:
    """Singleton wrapper around QSettings providing schema validation and typed access."""

    _instance: AppSettings | None = None

    def __init__(self, organization: str = "ATBOffice", application: str = "ATBOffice") -> None:
        self._qsettings = QSettings(organization, application)

    @classmethod
    def get_instance(cls) -> AppSettings:
        """Return the global AppSettings singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for clean unit testing)."""
        cls._instance = None

    def get_value(self, key: str, default: Any = None) -> Any:
        """Retrieve setting value with automatic type casting based on DEFAULT_SETTINGS schema."""
        expected_default = DEFAULT_SETTINGS.get(key, default)
        val = self._qsettings.value(key, expected_default)
        if val is None:
            return expected_default

        if expected_default is not None:
            # Type coercion
            if isinstance(expected_default, bool):
                if isinstance(val, bool):
                    return val
                return str(val).lower() in ("true", "1", "yes")
            if isinstance(expected_default, int):
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return expected_default
            if isinstance(expected_default, float):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return expected_default
            if isinstance(expected_default, str):
                return str(val)

        return val

    def set_value(self, key: str, value: Any) -> None:
        """Store setting key-value pair and flush to persistent storage."""
        self._qsettings.setValue(key, value)
        self._qsettings.sync()

    def get_all(self) -> dict[str, Any]:
        """Return a copy of all current settings values."""
        result: dict[str, Any] = {}
        for key in DEFAULT_SETTINGS:
            result[key] = self.get_value(key)
        return result

    def reset_defaults(self) -> None:
        """Clear all stored settings and re-apply defaults."""
        for key, default_val in DEFAULT_SETTINGS.items():
            self._qsettings.setValue(key, default_val)
        self._qsettings.sync()

    def sync(self) -> None:
        """Explicitly flush in-memory changes to disk."""
        self._qsettings.sync()

    def apply_startup_settings(self) -> None:
        """Apply stored language, theme, and recent files configurations on startup."""
        try:
            from atboffice.core.i18n import load_locale
            lang = self.get_value("locale/language", "zh-CN")
            load_locale(lang)
        except Exception as exc:
            logger.warning("Error applying startup locale: %s", exc)

        try:
            from atboffice.ui.styles.luna_2003 import apply_theme_globally
            theme = self.get_value("theme/active_theme", "blue")
            apply_theme_globally(theme)
        except Exception as exc:
            logger.warning("Error applying startup theme: %s", exc)

        try:
            from atboffice.core.window_manager import WindowManager
            recents_limit = self.get_value("general/recent_files_limit", 20)
            WindowManager.get_instance().recent_files.set_max_items(recents_limit)
        except Exception as exc:
            logger.warning("Error applying startup recent files limit: %s", exc)


def get_app_settings() -> AppSettings:
    """Convenience accessor for the global AppSettings singleton."""
    return AppSettings.get_instance()
