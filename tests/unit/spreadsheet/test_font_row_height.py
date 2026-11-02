"""Unit tests for Excel default font row height and East Asian font handling.

Ported from .vibeoffice/tests/fonts.test.mjs.
"""

from __future__ import annotations

from atboffice.modules.spreadsheet.models.color_utils import (
    font_row_pt,
    normalize_font_key,
    pt_to_px,
)


def test_localized_font_name_normalization():
    """Verify localized font names map to standard identifiers."""
    assert normalize_font_key("ＭＳ 明朝") == "ms mincho"
    assert normalize_font_key("맑은 고딕") == "malgun gothic"
    assert normalize_font_key("宋体") == "simsun"
    assert normalize_font_key("Times New Roman") == "times new roman"
    assert normalize_font_key("游ゴシック") == "yu gothic"


def test_default_row_height_for_standard_and_east_asian_fonts():
    """Verify default row heights match Excel localized defaults from tests/fonts.test.mjs."""
    # ＭＳ Ｐゴシック 11pt has rows of 13.5pt in Japanese workbooks
    assert font_row_pt("ＭＳ Ｐゴシック", 11) == 13.5

    # 游ゴシック 11pt has rows of 18.75pt
    assert font_row_pt("游ゴシック", 11) == 18.75

    # 맑은 고딕 11pt has rows of 16.5pt in Korean workbooks
    assert font_row_pt("맑은 고딕", 11) == 16.5

    # Calibri 11pt has rows of 15pt in standard Latin workbooks
    assert font_row_pt("Calibri", 11) == 15.0

    # Arial 11pt has rows of 14.25pt
    assert font_row_pt("Arial", 11) == 14.25

    # SimSun 11pt has rows of 13.5pt in Chinese workbooks
    assert font_row_pt("宋体", 11) == 13.5


def test_pt_to_px_conversion():
    """Verify points to pixels conversion at 96 DPI."""
    assert pt_to_px(15.0) == 20
    assert pt_to_px(13.5) == 18
    assert pt_to_px(18.75) == 25
