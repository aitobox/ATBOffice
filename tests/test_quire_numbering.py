"""Unit and integration tests for Quire list counters, multi-level numbering, and picture bullets.

Issue #364 / TASK-DOC-Q02.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from atboffice.modules.writer.layout.portions import map_symbol_char


def test_map_symbol_char() -> None:
    """Verify Symbol and Wingdings glyph mappings to standard Unicode characters."""
    # Wingdings mappings
    assert map_symbol_char("\uf06c", "Wingdings") == "●"
    assert map_symbol_char("l", "Wingdings") == "●"
    assert map_symbol_char("\uf06e", "Wingdings") == "■"
    assert map_symbol_char("n", "Wingdings") == "■"
    assert map_symbol_char("\uf075", "Wingdings") == "◆"
    assert map_symbol_char("u", "Wingdings") == "◆"
    assert map_symbol_char("\uf0fc", "Wingdings") == "✓"
    assert map_symbol_char("ü", "Wingdings") == "✓"
    assert map_symbol_char("\uf0d8", "Wingdings") == "➢"
    assert map_symbol_char("\uf0a7", "Wingdings") == "▪"
    assert map_symbol_char("§", "Wingdings") == "▪"

    # Symbol mappings
    assert map_symbol_char("\uf0b7", "Symbol") == "•"
    assert map_symbol_char("·", "Symbol") == "•"

    # Private use fallbacks
    assert map_symbol_char("\uf005") == "•"

    # Normal characters without symbol font remain unchanged
    assert map_symbol_char("A", "Arial") == "A"
    assert map_symbol_char("1", "Calibri") == "1"
