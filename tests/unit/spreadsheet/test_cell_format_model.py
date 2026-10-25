"""Unit tests for cell format attributes, BorderStyle, FormatDelta, and SheetDataModel formatting."""

import pytest
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    FormatDelta,
    SheetDataModel,
)


def test_cell_data_format_defaults():
    cell = CellData(value=100)
    assert cell.value == 100
    assert cell.format_code == "General"
    assert cell.bold is False
    assert cell.italic is False
    assert cell.underline is False
    assert cell.underline_style == "none"
    assert cell.strike is False
    assert cell.vert_align is None
    assert cell.align_h == "general"
    assert cell.align_v == "bottom"
    assert cell.indent == 0
    assert cell.wrap_text is False
    assert cell.shrink_to_fit is False
    assert cell.text_rotation == 0
    assert cell.text_direction == "context"
    assert cell.border_top is None
    assert cell.border_bottom is None
    assert cell.border_left is None
    assert cell.border_right is None
    assert cell.border_diag_up is None
    assert cell.border_diag_down is None
    assert cell.bg_color is None
    assert cell.pattern is None
    assert cell.pattern_color is None
    assert cell.locked is True
    assert cell.hidden is False


def test_border_style_representation():
    bs = BorderStyle(style="thin", color="#FF0000")
    assert bs.style == "thin"
    assert bs.color == "#FF0000"


def test_format_delta_application():
    model = SheetDataModel()
    delta = FormatDelta(
        format_code="#,##0.00",
        bold=True,
        font_size=14,
        fg_color="#0000FF",
        bg_color="#FFFF00",
        align_h="center",
        align_v="center",
        wrap_text=True,
        border_top=BorderStyle(style="thick", color="#000000"),
        border_bottom=BorderStyle(style="double", color="#000000"),
        pattern="pct25",
        pattern_color="#888888",
        locked=False,
        hidden=True,
    )

    # Apply to empty cell
    model.apply_format_delta(0, 0, delta)
    cell = model.get_cell(0, 0)
    assert cell is not None
    assert cell.format_code == "#,##0.00"
    assert cell.bold is True
    assert cell.font_size == 14
    assert cell.fg_color == "#0000FF"
    assert cell.bg_color == "#FFFF00"
    assert cell.align_h == "center"
    assert cell.align_v == "center"
    assert cell.wrap_text is True
    assert cell.border_top == BorderStyle(style="thick", color="#000000")
    assert cell.border_bottom == BorderStyle(style="double", color="#000000")
    assert cell.pattern == "pct25"
    assert cell.pattern_color == "#888888"
    assert cell.locked is False
    assert cell.hidden is True


def test_format_delta_partial_update():
    model = SheetDataModel()
    cell = CellData(value="Text", format_code="0%", bold=True, font_size=12)
    model.set_cell(1, 1, cell)

    # Partial delta changing only italic and font_size
    delta = FormatDelta(italic=True, font_size=16)
    model.apply_format_delta(1, 1, delta)

    updated = model.get_cell(1, 1)
    assert updated.value == "Text"
    assert updated.format_code == "0%"  # Untouched
    assert updated.bold is True  # Untouched
    assert updated.italic is True  # Updated
    assert updated.font_size == 16  # Updated


def test_sheet_data_model_merges():
    model = SheetDataModel()
    assert len(model.merges) == 0

    model.add_merge(1, 1, 3, 3)
    assert len(model.merges) == 1
    assert model.is_merged(2, 2) is True
    assert model.is_merged(0, 0) is False
    assert model.get_merge_range(2, 2) == (1, 1, 3, 3)

    model.remove_merge(1, 1)
    assert len(model.merges) == 0
    assert model.is_merged(2, 2) is False
