"""Unit tests for the 54 ECMA-376 / Office 2003 pattern definitions and pixmap generation."""

import pytest
from PySide6.QtGui import QBrush, QColor, QPixmap
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.dialogs.pattern_defs import (
    PATTERNS,
    PATTERN_NAMES,
    create_pattern_brush,
    create_pattern_pixmap,
)


def test_54_patterns_count_and_format():
    assert len(PATTERNS) == 54
    for name, rows in PATTERNS.items():
        assert len(rows) == 8, f"Pattern {name} must have 8 rows"
        for val in rows:
            assert 0 <= val <= 0xFF, f"Pattern {name} row value {val} out of range"
        assert name in PATTERN_NAMES, f"Pattern {name} missing from PATTERN_NAMES"


def test_create_pattern_pixmap(qapp: QApplication):
    pixmap = create_pattern_pixmap("pct25", fg_color="#000000", bg_color="#FFFFFF", size=(16, 16))
    assert isinstance(pixmap, QPixmap)
    assert not pixmap.isNull()
    assert pixmap.width() == 16
    assert pixmap.height() == 16


def test_create_pattern_brush(qapp: QApplication):
    brush = create_pattern_brush("trellis", fg_color="#FF0000", bg_color="#00FF00")
    assert isinstance(brush, QBrush)
    assert not brush.texture().isNull()
