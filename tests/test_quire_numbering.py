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


def test_document_blocks_traversal() -> None:
    """Verify Document.blocks and all_paras traversal in reading order including tables."""
    from atboffice.modules.writer.models.document import Cell, Document, Paragraph, Row, Story, Table

    p1 = Paragraph()
    p1.label = "1."
    p2 = Paragraph()
    p2.label = "2."
    p3 = Paragraph()
    p3.label = "5."
    p4 = Paragraph()
    p4.label = "3."
    p5 = Paragraph()
    p5.label = "4."

    tbl = Table(rows=[Row(cells=[Cell(blocks=[p4, p5])])])
    doc = Document(main=Story(kind="main", blocks=[p1, p2, tbl, p3]))

    # Verify Paragraph.label exists and defaults to empty string on new paragraph
    p_new = Paragraph()
    assert p_new.label == ""

    # Verify doc.blocks traverses in reading order
    blocks = doc.blocks
    assert blocks == [p1, p2, tbl, p4, p5, p3]

    # Verify list comprehension pattern from acceptance criteria
    labels = [b.label for b in doc.blocks if hasattr(b, "label") and b.label]
    assert labels == ["1.", "2.", "3.", "4.", "5."]

    # Verify doc.all_paras returns only paragraphs
    assert doc.all_paras() == [p1, p2, p4, p5, p3]

