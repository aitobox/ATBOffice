"""Tests for Ledger conditional formatting (CF) and data validation systems."""

from __future__ import annotations

from atboffice.modules.spreadsheet.models.conditional_format import (
    CFVO,
    CFOp,
    CFRule,
    CFRuleType,
    ColorScaleRule,
    ConditionalFormat,
    DataBarRule,
    evaluate_cf_for_cell,
    mix_colors,
)
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel


def test_mix_colors() -> None:
    # Blend red and green
    assert mix_colors("#FF0000", "#00FF00", 0.0).upper() == "#FF0000"
    assert mix_colors("#FF0000", "#00FF00", 1.0).upper() == "#00FF00"
    mid = mix_colors("#000000", "#FFFFFF", 0.5).upper()
    assert mid == "#808080"


def test_cf_cell_is_greater_than() -> None:
    sheet = SheetDataModel(name="TestSheet")
    sheet.set_cell(0, 0, CellData(value=150))
    sheet.set_cell(0, 1, CellData(value=50))

    rule = CFRule(
        type=CFRuleType.CELL_IS.value,
        operator=CFOp.GREATER_THAN.value,
        formula=["100"],
        bg_color="#FFC7CE",
        fg_color="#9C0006",
    )
    cf = ConditionalFormat(
        sqref="A1:B1",
        ranges=[(0, 0, 0, 1)],
        rules=[rule],
    )
    sheet.conditional_formats.append(cf)

    # A1 > 100 should match
    res_a1 = evaluate_cf_for_cell(sheet, 0, 0)
    assert res_a1 is not None
    assert res_a1.bg_color == "#FFC7CE"
    assert res_a1.fg_color == "#9C0006"

    # B1 <= 100 should not match
    res_b1 = evaluate_cf_for_cell(sheet, 0, 1)
    assert res_b1 is None


def test_cf_cell_is_between() -> None:
    sheet = SheetDataModel(name="TestSheet")
    sheet.set_cell(0, 0, CellData(value=75))
    sheet.set_cell(0, 1, CellData(value=150))

    rule = CFRule(
        type=CFRuleType.CELL_IS.value,
        operator=CFOp.BETWEEN.value,
        formula=["50", "100"],
        bg_color="#C6EFCE",
        fg_color="#006100",
    )
    cf = ConditionalFormat(
        sqref="A1:B1",
        ranges=[(0, 0, 0, 1)],
        rules=[rule],
    )
    sheet.conditional_formats.append(cf)

    res_a1 = evaluate_cf_for_cell(sheet, 0, 0)
    assert res_a1 is not None
    assert res_a1.bg_color == "#C6EFCE"

    res_b1 = evaluate_cf_for_cell(sheet, 0, 1)
    assert res_b1 is None


def test_cf_contains_text() -> None:
    sheet = SheetDataModel(name="TestSheet")
    sheet.set_cell(0, 0, CellData(value="Completed Task"))
    sheet.set_cell(0, 1, CellData(value="Pending"))

    rule = CFRule(
        type=CFRuleType.CONTAINS_TEXT.value,
        text="Completed",
        bg_color="#C6EFCE",
    )
    cf = ConditionalFormat(
        sqref="A1:B1",
        ranges=[(0, 0, 0, 1)],
        rules=[rule],
    )
    sheet.conditional_formats.append(cf)

    res_a1 = evaluate_cf_for_cell(sheet, 0, 0)
    assert res_a1 is not None
    assert res_a1.bg_color == "#C6EFCE"

    res_b1 = evaluate_cf_for_cell(sheet, 0, 1)
    assert res_b1 is None


def test_cf_duplicate_values() -> None:
    sheet = SheetDataModel(name="TestSheet")
    sheet.set_cell(0, 0, CellData(value=42))
    sheet.set_cell(1, 0, CellData(value=99))
    sheet.set_cell(2, 0, CellData(value=42))

    rule = CFRule(
        type=CFRuleType.DUPLICATE_VALUES.value,
        bg_color="#FFC7CE",
    )
    cf = ConditionalFormat(
        sqref="A1:A3",
        ranges=[(0, 0, 2, 0)],
        rules=[rule],
    )
    sheet.conditional_formats.append(cf)

    # 42 is duplicated
    assert evaluate_cf_for_cell(sheet, 0, 0) is not None
    assert evaluate_cf_for_cell(sheet, 2, 0) is not None
    # 99 is unique
    assert evaluate_cf_for_cell(sheet, 1, 0) is None


def test_cf_color_scale() -> None:
    sheet = SheetDataModel(name="TestSheet")
    sheet.set_cell(0, 0, CellData(value=0))
    sheet.set_cell(1, 0, CellData(value=50))
    sheet.set_cell(2, 0, CellData(value=100))

    scale_rule = ColorScaleRule(
        cfvos=[CFVO(type="min"), CFVO(type="max")],
        colors=["#FF0000", "#00FF00"],
    )
    rule = CFRule(
        type=CFRuleType.COLOR_SCALE.value,
        color_scale=scale_rule,
    )
    cf = ConditionalFormat(
        sqref="A1:A3",
        ranges=[(0, 0, 2, 0)],
        rules=[rule],
    )
    sheet.conditional_formats.append(cf)

    res_min = evaluate_cf_for_cell(sheet, 0, 0)
    assert res_min is not None and res_min.bg_color.upper() == "#FF0000"

    res_max = evaluate_cf_for_cell(sheet, 2, 0)
    assert res_max is not None and res_max.bg_color.upper() == "#00FF00"

    res_mid = evaluate_cf_for_cell(sheet, 1, 0)
    assert res_mid is not None and res_mid.bg_color.upper() == "#808000"


def test_cf_data_bar() -> None:
    sheet = SheetDataModel(name="TestSheet")
    sheet.set_cell(0, 0, CellData(value=20))
    sheet.set_cell(1, 0, CellData(value=100))

    bar_rule = DataBarRule(
        cfvos=[CFVO(type="min"), CFVO(type="max")],
        color="#638EC6",
    )
    rule = CFRule(
        type=CFRuleType.DATA_BAR.value,
        data_bar=bar_rule,
    )
    cf = ConditionalFormat(
        sqref="A1:A2",
        ranges=[(0, 0, 1, 0)],
        rules=[rule],
    )
    sheet.conditional_formats.append(cf)

    res_max = evaluate_cf_for_cell(sheet, 1, 0)
    assert res_max is not None
    assert res_max.data_bar is not None
    assert res_max.data_bar["frac"] == 0.9  # max_len default 0.9


def test_data_validation_whole_number() -> None:
    from atboffice.modules.spreadsheet.models.validation import (
        DataValidation,
        ValidationOp,
        ValidationType,
        validate_cell_value,
    )

    sheet = SheetDataModel(name="TestSheet")
    dv = DataValidation(
        type=ValidationType.WHOLE.value,
        operator=ValidationOp.BETWEEN.value,
        formula1="10",
        formula2="50",
        sqref="A1:A5",
        ranges=[(0, 0, 4, 0)],
        allow_blank=True,
    )
    sheet.add_data_validation(dv)

    # Valid values
    ok, _ = validate_cell_value(sheet, 0, 0, 25)
    assert ok is True
    ok, _ = validate_cell_value(sheet, 0, 0, "30")
    assert ok is True
    ok, _ = validate_cell_value(sheet, 0, 0, None)
    assert ok is True

    # Invalid values
    ok, rule = validate_cell_value(sheet, 0, 0, 5)
    assert ok is False
    assert rule is dv

    ok, _ = validate_cell_value(sheet, 0, 0, 60)
    assert ok is False

    # Fractional not allowed in whole
    ok, _ = validate_cell_value(sheet, 0, 0, 25.5)
    assert ok is False


def test_data_validation_list_comma_separated() -> None:
    from atboffice.modules.spreadsheet.models.validation import (
        DataValidation,
        ValidationType,
        get_list_items,
        validate_cell_value,
    )

    sheet = SheetDataModel(name="TestSheet")
    dv = DataValidation(
        type=ValidationType.LIST.value,
        formula1='"Apples, Oranges, Bananas"',
        sqref="B1:B10",
        ranges=[(0, 1, 9, 1)],
    )
    sheet.add_data_validation(dv)

    items = get_list_items(sheet, dv, 0, 1)
    assert items == ["Apples", "Oranges", "Bananas"]

    ok, _ = validate_cell_value(sheet, 0, 1, "Apples")
    assert ok is True
    ok, _ = validate_cell_value(sheet, 0, 1, "bananas")  # case-insensitive match
    assert ok is True
    ok, _ = validate_cell_value(sheet, 0, 1, "Pineapple")
    assert ok is False


def test_data_validation_list_range_reference() -> None:
    from atboffice.modules.spreadsheet.models.validation import (
        DataValidation,
        ValidationType,
        get_list_items,
        validate_cell_value,
    )

    sheet = SheetDataModel(name="TestSheet")
    sheet.set_cell(0, 0, CellData(value="High"))
    sheet.set_cell(1, 0, CellData(value="Medium"))
    sheet.set_cell(2, 0, CellData(value="Low"))

    dv = DataValidation(
        type=ValidationType.LIST.value,
        formula1="=$A$1:$A$3",
        sqref="C1:C10",
        ranges=[(0, 2, 9, 2)],
    )
    sheet.add_data_validation(dv)

    items = get_list_items(sheet, dv, 0, 2)
    assert items == ["High", "Medium", "Low"]

    ok, _ = validate_cell_value(sheet, 0, 2, "High")
    assert ok is True
    ok, _ = validate_cell_value(sheet, 0, 2, "Critical")
    assert ok is False


def test_data_validation_text_length() -> None:
    from atboffice.modules.spreadsheet.models.validation import (
        DataValidation,
        ValidationOp,
        ValidationType,
        validate_cell_value,
    )

    sheet = SheetDataModel(name="TestSheet")
    dv = DataValidation(
        type=ValidationType.TEXT_LENGTH.value,
        operator=ValidationOp.LESS_THAN_OR_EQUAL.value,
        formula1="5",
        sqref="D1",
        ranges=[(0, 3, 0, 3)],
    )
    sheet.add_data_validation(dv)

    ok, _ = validate_cell_value(sheet, 0, 3, "Hello")
    assert ok is True
    ok, _ = validate_cell_value(sheet, 0, 3, "Hello World")
    assert ok is False


def test_sheet_model_cf_dv_helpers() -> None:
    from atboffice.modules.spreadsheet.models import (
        CFRule,
        ConditionalFormat,
        DataValidation,
        SheetDataModel,
    )

    sheet = SheetDataModel(name="Helpers")
    cf = ConditionalFormat(sqref="A1", ranges=[(0, 0, 0, 0)], rules=[CFRule()])
    dv = DataValidation(sqref="A1", ranges=[(0, 0, 0, 0)])

    sheet.add_conditional_format(cf)
    assert len(sheet.conditional_formats) == 1
    sheet.clear_conditional_formats()
    assert len(sheet.conditional_formats) == 0

    sheet.add_data_validation(dv)
    assert len(sheet.data_validations) == 1
    assert sheet.get_validation_at(0, 0) is dv
    assert sheet.get_validation_at(1, 1) is None
    sheet.clear_data_validations()
    assert len(sheet.data_validations) == 0


def test_xlsx_roundtrip_cf_and_validation(tmp_path) -> None:
    from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
    from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
    from atboffice.modules.spreadsheet.models import (
        CFVO,
        AlertStyle,
        CFOp,
        CFRule,
        CFRuleType,
        ColorScaleRule,
        ConditionalFormat,
        DataValidation,
        SheetDataModel,
        ValidationOp,
        ValidationType,
        WorkbookModel,
    )

    sheet = SheetDataModel(name="TestCFDV")
    sheet.set_cell(0, 0, CellData(value=120))
    sheet.set_cell(1, 0, CellData(value=40))

    # Add CF Rule: cellIs > 100
    rule1 = CFRule(
        type=CFRuleType.CELL_IS.value,
        operator=CFOp.GREATER_THAN.value,
        formula=["100"],
        bg_color="#FFC7CE",
        fg_color="#9C0006",
        bold=True,
    )
    # Add CF Color Scale
    scale_rule = ColorScaleRule(
        cfvos=[CFVO(type="min"), CFVO(type="max")],
        colors=["#FF0000", "#00FF00"],
    )
    rule2 = CFRule(
        type=CFRuleType.COLOR_SCALE.value,
        color_scale=scale_rule,
    )
    cf = ConditionalFormat(
        sqref="A1:A10",
        ranges=[(0, 0, 9, 0)],
        rules=[rule1, rule2],
    )
    sheet.add_conditional_format(cf)

    # Add Data Validation: whole number between 10 and 100
    dv1 = DataValidation(
        type=ValidationType.WHOLE.value,
        operator=ValidationOp.BETWEEN.value,
        formula1="10",
        formula2="100",
        sqref="B1:B10",
        ranges=[(0, 1, 9, 1)],
        allow_blank=True,
        show_error_alert=True,
        error_style=AlertStyle.STOP.value,
        error_title="Invalid Integer",
        error_message="Must be between 10 and 100",
    )
    # Add Data Validation: list
    dv2 = DataValidation(
        type=ValidationType.LIST.value,
        formula1='"Option1,Option2,Option3"',
        sqref="C1:C10",
        ranges=[(0, 2, 9, 2)],
        show_dropdown=True,
    )
    sheet.add_data_validation(dv1)
    sheet.add_data_validation(dv2)

    wb = WorkbookModel(sheets=[sheet])
    out_file = tmp_path / "test_cf_dv.xlsx"

    # Write to XLSX
    write_xlsx(wb, str(out_file))

    # Read back from XLSX
    wb_read = read_xlsx(str(out_file))
    sheet_read = wb_read.sheets[0]

    # Verify CF preserved
    assert len(sheet_read.conditional_formats) == 1
    cf_read = sheet_read.conditional_formats[0]
    assert cf_read.sqref == "A1:A10"
    assert len(cf_read.rules) == 2

    r1_read = cf_read.rules[0]
    assert r1_read.type == CFRuleType.CELL_IS.value
    assert r1_read.operator == CFOp.GREATER_THAN.value
    assert r1_read.formula == ["100"]
    assert r1_read.bg_color == "#FFC7CE"
    assert r1_read.fg_color == "#9C0006"
    assert r1_read.bold is True

    r2_read = cf_read.rules[1]
    assert r2_read.type == CFRuleType.COLOR_SCALE.value
    assert r2_read.color_scale is not None
    assert len(r2_read.color_scale.colors) == 2

    # Verify Data Validations preserved
    assert len(sheet_read.data_validations) == 2
    dv1_read = next(d for d in sheet_read.data_validations if d.type == ValidationType.WHOLE.value)
    assert dv1_read.operator == ValidationOp.BETWEEN.value
    assert dv1_read.formula1 == "10"
    assert dv1_read.formula2 == "100"
    assert dv1_read.error_title == "Invalid Integer"
    assert dv1_read.error_message == "Must be between 10 and 100"

    dv2_read = next(d for d in sheet_read.data_validations if d.type == ValidationType.LIST.value)
    assert "Option1" in (dv2_read.formula1 or "")


def test_conditional_format_dialog(qtbot) -> None:
    from atboffice.modules.spreadsheet.dialogs import ConditionalFormatDialog
    from atboffice.modules.spreadsheet.models import (
        CFOp,
        CFRule,
        CFRuleType,
        ConditionalFormat,
    )

    rule = CFRule(
        type=CFRuleType.CELL_IS.value,
        operator=CFOp.GREATER_THAN.value,
        formula=["100"],
        bg_color="#FFC7CE",
    )
    cf = ConditionalFormat(sqref="A1:B5", ranges=[(0, 0, 4, 1)], rules=[rule])

    dlg = ConditionalFormatDialog(existing_cf=cf, sqref="A1:B5", ranges=[(0, 0, 4, 1)])
    qtbot.addWidget(dlg)

    cf_out = dlg.get_conditional_format()
    assert cf_out.sqref == "A1:B5"
    assert len(cf_out.rules) >= 1
    assert cf_out.rules[0].operator == CFOp.GREATER_THAN.value
    assert cf_out.rules[0].formula == ["100"]


def test_data_validation_dialog(qtbot) -> None:
    from atboffice.modules.spreadsheet.dialogs import DataValidationDialog
    from atboffice.modules.spreadsheet.models import (
        AlertStyle,
        DataValidation,
        ValidationOp,
        ValidationType,
    )

    dv = DataValidation(
        type=ValidationType.WHOLE.value,
        operator=ValidationOp.BETWEEN.value,
        formula1="5",
        formula2="25",
        sqref="A1:A10",
        ranges=[(0, 0, 9, 0)],
        error_style=AlertStyle.STOP.value,
        error_title="Out of Bounds",
        error_message="Value must be between 5 and 25",
    )

    dlg = DataValidationDialog(existing_dv=dv, sqref="A1:A10", ranges=[(0, 0, 9, 0)])
    qtbot.addWidget(dlg)

    dv_out = dlg.get_data_validation()
    assert dv_out.type == ValidationType.WHOLE.value
    assert dv_out.operator == ValidationOp.BETWEEN.value
    assert dv_out.formula1 == "5"
    assert dv_out.formula2 == "25"
    assert dv_out.error_title == "Out of Bounds"


def test_grid_viewport_rendering_with_cf(qtbot) -> None:
    from atboffice.modules.spreadsheet.models import (
        CFOp,
        CFRule,
        CFRuleType,
        ConditionalFormat,
        DataBarRule,
        DataValidation,
        SheetDataModel,
        ValidationType,
    )
    from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport

    sheet = SheetDataModel(name="RenderSheet")
    sheet.set_cell(0, 0, CellData(value=150))
    sheet.set_cell(0, 1, CellData(value=75))

    # CF > 100
    rule1 = CFRule(
        type=CFRuleType.CELL_IS.value,
        operator=CFOp.GREATER_THAN.value,
        formula=["100"],
        bg_color="#FFC7CE",
        fg_color="#9C0006",
        bold=True,
    )
    # CF Data Bar
    rule2 = CFRule(
        type=CFRuleType.DATA_BAR.value,
        data_bar=DataBarRule(color="#638EC6"),
    )
    cf = ConditionalFormat(sqref="A1:B1", ranges=[(0, 0, 0, 1)], rules=[rule1, rule2])
    sheet.add_conditional_format(cf)

    # List Data Validation with dropdown
    dv = DataValidation(
        type=ValidationType.LIST.value,
        formula1='"One, Two, Three"',
        sqref="A1",
        ranges=[(0, 0, 0, 0)],
        show_dropdown=True,
    )
    sheet.add_data_validation(dv)

    grid = GridViewport(model=sheet)
    qtbot.addWidget(grid)
    grid.resize(400, 300)
    grid.show()
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()

    # Verify dropdown indicator rect created for active cell A1
    assert grid._dv_dropdown_rect is not None


def test_sheet_model_comments() -> None:
    sheet = SheetDataModel(name="CommentSheet")
    assert not sheet.has_comment(0, 0)
    assert sheet.get_comment(0, 0) is None

    # Set comment
    cm = sheet.set_comment(0, 0, "Initial comment", "Author1", visible=False)
    assert sheet.has_comment(0, 0)
    assert cm.text == "Initial comment"
    assert cm.author == "Author1"
    assert not cm.visible

    # Get comment
    retrieved = sheet.get_comment(0, 0)
    assert retrieved is not None
    assert retrieved.text == "Initial comment"

    # Delete comment
    assert sheet.delete_comment(0, 0) is True
    assert not sheet.has_comment(0, 0)
    assert sheet.delete_comment(0, 0) is False


def test_comment_dialog(qtbot) -> None:
    from atboffice.modules.spreadsheet.dialogs import CommentDialog

    dlg = CommentDialog(
        existing_text="Existing note",
        author="Alice",
        cell_ref="B2",
    )
    qtbot.addWidget(dlg)

    assert dlg.get_text() == "Existing note"
    assert dlg.get_author() == "Alice"

    dlg.edit_text.setPlainText("Modified note text")
    assert dlg.get_text() == "Modified note text"

    dlg.retranslate_ui()
    assert "B2" in dlg.windowTitle()


def test_circle_invalid_and_clear_circles(qtbot) -> None:
    from atboffice.modules.spreadsheet.models import (
        DataValidation,
        ValidationOp,
        ValidationType,
    )
    from atboffice.ui.shell.ledger_window import LedgerWindow

    win = LedgerWindow()
    qtbot.addWidget(win)

    sheet = win.spreadsheet_view.model

    # Validation: Whole number between 10 and 20 on A1:A3
    dv = DataValidation(
        type=ValidationType.WHOLE.value,
        operator=ValidationOp.BETWEEN.value,
        formula1="10",
        formula2="20",
        sqref="A1:A3",
        ranges=[(0, 0, 2, 0)],
    )
    sheet.add_data_validation(dv)

    sheet.set_cell(0, 0, CellData(value=15))  # Valid
    sheet.set_cell(1, 0, CellData(value=5))   # Invalid (< 10)
    sheet.set_cell(2, 0, CellData(value=25))  # Invalid (> 20)

    # Trigger circle invalid
    win.circle_invalid()
    assert (1, 0) in sheet.invalid_circles
    assert (2, 0) in sheet.invalid_circles
    assert (0, 0) not in sheet.invalid_circles

    # Clear circles
    win.clear_circles()
    assert len(sheet.invalid_circles) == 0


def test_comment_actions_in_ledger_window(qtbot) -> None:
    from atboffice.ui.shell.ledger_window import LedgerWindow

    win = LedgerWindow()
    qtbot.addWidget(win)

    sheet = win.spreadsheet_view.model
    sel = win.spreadsheet_view.selection
    sel.select_cell(1, 1)  # B2

    # Add comment programmatically to test toggles
    sheet.set_comment(1, 1, "Test comment on B2", "Tester", visible=False)

    # Show / hide comment
    win.show_hide_comment()
    assert sheet.get_comment(1, 1).visible is True

    win.show_hide_comment()
    assert sheet.get_comment(1, 1).visible is False

    # Toggle show all comments
    assert sheet.show_all_comments is False
    win.toggle_show_all_comments()
    assert sheet.show_all_comments is True

    # Delete comment
    win.delete_comment()
    assert sheet.get_comment(1, 1) is None


def test_grid_viewport_rendering_with_circles_and_comments(qtbot) -> None:
    from atboffice.modules.spreadsheet.models import SheetDataModel
    from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport

    sheet = SheetDataModel(name="RenderCommentsSheet")
    sheet.set_cell(0, 0, CellData(value="Cell A1"))
    sheet.set_cell(1, 1, CellData(value="Cell B2"))

    # Add comment with visible callout
    sheet.set_comment(0, 0, "A1 Comment", "Author", visible=True)
    # Add comment with hidden callout (corner triangle only)
    sheet.set_comment(1, 1, "B2 Comment", "Author", visible=False)

    # Add invalid circle
    sheet.invalid_circles = [(0, 0), (1, 1)]

    grid = GridViewport(model=sheet)
    qtbot.addWidget(grid)
    grid.resize(500, 400)
    grid.show()

    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()

    # Verify viewport renders without errors
    grid.viewport().update()
    QCoreApplication.processEvents()





