"""VFS HTML Document I/O bridge for Quire."""

from __future__ import annotations

from atboffice.modules.writer.io.html_io import (
    HtmlReader,
    HtmlWriter,
    read_html,
    web_page,
    write_html,
)

__all__ = [
    "HtmlReader",
    "HtmlWriter",
    "read_html",
    "web_page",
    "write_html",
]
