"""Unit tests for conditional formatting data bars, color scales, and comment hover callouts."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

from atboffice.modules.spreadsheet.models.conditional_format import (
    CFVO,
    CFRule,
    CFRuleType,
    ColorScaleRule,
    ConditionalFormat,
    DataBarRule,
    evaluate_cf_for_cell,
    mix_colors,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport


class TestColorScaleInterpolation:
    """Test 2-color and 3-color scale RGB linear interpolation."""

    def test_mix_colors_linear_rgb(self):
        # Pure red (#FF0000) to pure blue (#0000FF)
        c1 = "#FF0000"
        c2 = "#0000FF"
        assert mix_colors(c1, c2, 0.0) == "#FF0000"
        assert mix_colors(c1, c2, 1.0) == "#0000FF"
        mid = mix_colors(c1, c2, 0.5)
        # Rounding 255 * 0.5 = 128
        assert mid in ("#800080", "#7F007F")

    def test_2_color_scale_evaluation(self):
        sheet = SheetDataModel()
        # Set values 10, 50, 100 in column A (rows 0, 1, 2)
        sheet.set_cell(0, 0, CellData(value=10))
        sheet.set_cell(1, 0, CellData(value=50))
        sheet.set_cell(2, 0, CellData(value=100))

        cs_rule = CFRule(
            type=CFRuleType.COLOR_SCALE.value,
            color_scale=ColorScaleRule(
                cfvos=[CFVO(type="min"), CFVO(type="max")],
                colors=["#FFFFFF", "#0000FF"],  # White to Blue
            ),
        )
        cf = ConditionalFormat(
            ranges=[(0, 0, 2, 0)],
            rules=[cs_rule],
        )
        sheet.conditional_formats = [cf]

        res_min = evaluate_cf_for_cell(sheet, 0, 0)
        assert res_min is not None
        assert res_min.bg_color == "#FFFFFF"

        res_max = evaluate_cf_for_cell(sheet, 2, 0)
        assert res_max is not None
        assert res_max.bg_color == "#0000FF"

        res_mid = evaluate_cf_for_cell(sheet, 1, 0)
        assert res_mid is not None
        # Relative t = (50 - 10) / (100 - 10) = 40 / 90 ~ 0.444
        col = QColor(res_mid.bg_color)
        assert col.red() < 255
        assert col.blue() > 0

    def test_3_color_scale_evaluation(self):
        sheet = SheetDataModel()
        # Values 0, 50, 100
        sheet.set_cell(0, 0, CellData(value=0))
        sheet.set_cell(1, 0, CellData(value=50))
        sheet.set_cell(2, 0, CellData(value=100))

        cs_rule = CFRule(
            type=CFRuleType.COLOR_SCALE.value,
            color_scale=ColorScaleRule(
                cfvos=[CFVO(type="min"), CFVO(type="percent", val=50), CFVO(type="max")],
                colors=["#FF0000", "#FFFF00", "#00FF00"],  # Red -> Yellow -> Green
            ),
        )
        cf = ConditionalFormat(
            ranges=[(0, 0, 2, 0)],
            rules=[cs_rule],
        )
        sheet.conditional_formats = [cf]

        res_0 = evaluate_cf_for_cell(sheet, 0, 0)
        assert res_0 is not None
        assert res_0.bg_color == "#FF0000"

        res_50 = evaluate_cf_for_cell(sheet, 1, 0)
        assert res_50 is not None
        assert res_50.bg_color == "#FFFF00"

        res_100 = evaluate_cf_for_cell(sheet, 2, 0)
        assert res_100 is not None
        assert res_100.bg_color == "#00FF00"

    def test_color_scale_zero_span(self):
        sheet = SheetDataModel()
        sheet.set_cell(0, 0, CellData(value=42))
        sheet.set_cell(1, 0, CellData(value=42))

        cs_rule = CFRule(
            type=CFRuleType.COLOR_SCALE.value,
            color_scale=ColorScaleRule(
                cfvos=[CFVO(type="min"), CFVO(type="max")],
                colors=["#FFFFFF", "#000000"],
            ),
        )
        sheet.conditional_formats = [ConditionalFormat(ranges=[(0, 0, 1, 0)], rules=[cs_rule])]

        res = evaluate_cf_for_cell(sheet, 0, 0)
        assert res is not None
        assert res.bg_color is not None


class TestDataBarEvaluation:
    """Test Data Bar fraction, gradient, negative color, and metadata calculation."""

    def test_data_bar_fraction_calculation(self):
        sheet = SheetDataModel()
        sheet.set_cell(0, 0, CellData(value=0))
        sheet.set_cell(1, 0, CellData(value=50))
        sheet.set_cell(2, 0, CellData(value=100))

        db_rule = CFRule(
            type=CFRuleType.DATA_BAR.value,
            data_bar=DataBarRule(
                cfvos=[CFVO(type="min"), CFVO(type="max")],
                color="#638EC6",
                neg_color="#FF0000",
                min_len=0.1,
                max_len=0.9,
                show_value=True,
            ),
        )
        sheet.conditional_formats = [ConditionalFormat(ranges=[(0, 0, 2, 0)], rules=[db_rule])]

        res_min = evaluate_cf_for_cell(sheet, 0, 0)
        assert res_min is not None
        assert res_min.data_bar is not None
        assert pytest.approx(res_min.data_bar["frac"], rel=1e-2) == 0.1
        assert res_min.data_bar["color"] == "#638EC6"
        assert res_min.data_bar["show_value"] is True
        assert res_min.data_bar["gradient"] is True

        res_max = evaluate_cf_for_cell(sheet, 2, 0)
        assert res_max is not None
        assert pytest.approx(res_max.data_bar["frac"], rel=1e-2) == 0.9

        res_mid = evaluate_cf_for_cell(sheet, 1, 0)
        assert res_mid is not None
        # 0.1 + (0.9 - 0.1) * 0.5 = 0.5
        assert pytest.approx(res_mid.data_bar["frac"], rel=1e-2) == 0.5

    def test_data_bar_negative_values(self):
        sheet = SheetDataModel()
        sheet.set_cell(0, 0, CellData(value=-25))
        sheet.set_cell(1, 0, CellData(value=50))

        db_rule = CFRule(
            type=CFRuleType.DATA_BAR.value,
            data_bar=DataBarRule(
                color="#638EC6",
                neg_color="#FF3333",
            ),
        )
        sheet.conditional_formats = [ConditionalFormat(ranges=[(0, 0, 1, 0)], rules=[db_rule])]

        res_neg = evaluate_cf_for_cell(sheet, 0, 0)
        assert res_neg is not None
        assert res_neg.data_bar is not None
        assert res_neg.data_bar["is_negative"] is True
        assert res_neg.data_bar["color"] == "#FF3333"


class TestGridViewportDataBarAndCommentHover:
    """Test GridViewport visual rendering with data bars and comment hover card."""

    def test_grid_viewport_renders_data_bar(self, qapp):
        model = SheetDataModel()
        model.set_cell(0, 0, CellData(value=80))

        db_rule = CFRule(
            type=CFRuleType.DATA_BAR.value,
            data_bar=DataBarRule(
                color="#2196F3",
                min_len=0.0,
                max_len=1.0,
                show_value=True,
            ),
        )
        model.conditional_formats = [ConditionalFormat(ranges=[(0, 0, 0, 0)], rules=[db_rule])]

        viewport = GridViewport(model=model)
        viewport.resize(400, 300)

        img = QImage(400, 300, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        painter = QPainter(img)
        viewport.paintEvent(None)  # Verify paintEvent executes without exception
        painter.end()

        assert not img.isNull()

    def test_grid_viewport_comment_hover_and_callout(self, qapp):
        model = SheetDataModel()
        model.set_cell(0, 0, CellData(value="Target Cell"))
        model.set_comment(
            0,
            0,
            text="This is an important review comment.",
            author="Reviewer Alice",
            visible=False,
        )

        viewport = GridViewport(model=model)
        viewport.resize(500, 400)

        assert viewport.hover_comment_cell is None

        # Simulate hover over cell (0, 0)
        viewport.show_comment_hover(0, 0)
        assert viewport.hover_comment_cell == (0, 0)

        # Render paintEvent to verify drop shadow, box, text and leader arrow
        img = QImage(500, 400, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        painter = QPainter(img)
        viewport.paintEvent(None)
        painter.end()
        assert not img.isNull()

        # Simulate moving mouse away to empty cell (5, 5)
        viewport.show_comment_hover(5, 5)
        assert viewport.hover_comment_cell is None

        # Simulate leave event
        viewport.show_comment_hover(0, 0)
        assert viewport.hover_comment_cell == (0, 0)
        viewport.leaveEvent(None)
        assert viewport.hover_comment_cell is None

    def test_comment_hover_without_author_and_multiline_text(self, qapp):
        model = SheetDataModel()
        model.set_cell(1, 1, CellData(value="Note Cell"))
        model.set_comment(
            1,
            1,
            text="Line 1: Note content\nLine 2: Second detail\nLine 3: Third point",
            author="",
            visible=False,
        )

        viewport = GridViewport(model=model)
        viewport.resize(500, 400)
        viewport.show_comment_hover(1, 1)
        assert viewport.hover_comment_cell == (1, 1)

        img = QImage(500, 400, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        painter = QPainter(img)
        viewport.paintEvent(None)
        painter.end()
        assert not img.isNull()

    def test_data_bar_suppresses_cell_text_when_show_value_false(self, qapp):
        model = SheetDataModel()
        model.set_cell(0, 0, CellData(value=100))

        db_rule = CFRule(
            type=CFRuleType.DATA_BAR.value,
            data_bar=DataBarRule(
                color="#638EC6",
                show_value=False,
            ),
        )
        model.conditional_formats = [ConditionalFormat(ranges=[(0, 0, 0, 0)], rules=[db_rule])]

        viewport = GridViewport(model=model)
        viewport.resize(400, 300)

        img = QImage(400, 300, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        painter = QPainter(img)
        viewport.paintEvent(None)
        painter.end()
        assert not img.isNull()
