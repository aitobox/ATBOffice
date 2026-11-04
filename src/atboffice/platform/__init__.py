"""Platform-specific glue and compatibility adapters for ATBOffice."""

from atboffice.platform.cursors import (
    get_safe_cursor,
    safe_restore_override_cursor,
    safe_set_override_cursor,
    set_safe_cursor,
)

__all__ = [
    "get_safe_cursor",
    "set_safe_cursor",
    "safe_set_override_cursor",
    "safe_restore_override_cursor",
]
