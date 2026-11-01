"""Comprehensive integration tests for Ledger toolbar action wiring and state synchronization."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from atboffice.core.i18n import load_locale
from atboffice.modules.spreadsheet.models.selection_model import SelectionRange
from atboffice.modules.spreadsheet.models.sheet_model import CellData
from atboffice.ui.shell.ledger_window import LedgerWindow


def test_autosum_above_single_cell(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    # Set numeric values in A1:A3 (0,0), (1,0), (2,0)
    model.set_cell(0, 0, CellData(value=10))
    model.set_cell(1, 0, CellData(value=20))
    model.set_cell(2, 0, CellData(value=30))

    # Select A4 (3, 0)
    win.spreadsheet_view.selection.select_cell(3, 0)

    # Trigger autoSum action
    assert win.action_registry.has_action("autoSum")
    win.action_registry.trigger_action("autoSum")

    cell_a4 = model.get_cell(3, 0)
    assert cell_a4 is not None
    assert cell_a4.formula == "SUM(A1:A3)"
    assert cell_a4.value == 60.0


def test_autosum_left_single_cell(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    # Set numeric values in A1:B1 (0,0), (0,1)
    model.set_cell(0, 0, CellData(value=15))
    model.set_cell(0, 1, CellData(value=25))

    # Select C1 (0, 2)
    win.spreadsheet_view.selection.select_cell(0, 2)

    # Trigger autoSum action
    win.action_registry.trigger_action("autoSum")

    cell_c1 = model.get_cell(0, 2)
    assert cell_c1 is not None
    assert cell_c1.formula == "SUM(A1:B1)"
    assert cell_c1.value == 40.0


def test_quick_sort_asc_and_desc(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    model.set_cell(0, 0, CellData(value=30))
    model.set_cell(1, 0, CellData(value=10))
    model.set_cell(2, 0, CellData(value=20))

    sel = win.spreadsheet_view.selection
    sel.clear()
    sel.add_range(SelectionRange(0, 0, 2, 0))
    sel.set_active_cell(0, 0)

    # Sort ascending
    assert win.action_registry.has_action("sortAsc")
    win.action_registry.trigger_action("sortAsc")

    assert model.get_cell_value(0, 0) == 10
    assert model.get_cell_value(1, 0) == 20
    assert model.get_cell_value(2, 0) == 30

    # Sort descending
    assert win.action_registry.has_action("sortDesc")
    win.action_registry.trigger_action("sortDesc")

    assert model.get_cell_value(0, 0) == 30
    assert model.get_cell_value(1, 0) == 20
    assert model.get_cell_value(2, 0) == 10


def test_number_formatting_and_decimals(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    model.set_cell(0, 0, CellData(value=1234.5))
    win.spreadsheet_view.selection.select_cell(0, 0)

    # Currency format
    assert win.action_registry.has_action("currencyStyle")
    win.action_registry.trigger_action("currencyStyle")
    text = model.get_formatted_text(0, 0)
    assert "1,234.50" in text

    # Percent format
    model.set_cell(0, 0, CellData(value=0.25))
    assert win.action_registry.has_action("percentStyle")
    win.action_registry.trigger_action("percentStyle")
    text = model.get_formatted_text(0, 0)
    assert "25%" in text

    # Comma format
    model.set_cell(0, 0, CellData(value=1234567))
    assert win.action_registry.has_action("commaStyle")
    win.action_registry.trigger_action("commaStyle")
    text = model.get_formatted_text(0, 0)
    assert "1,234,567.00" in text

    # Increase decimal
    assert win.action_registry.has_action("incDecimal")
    win.action_registry.trigger_action("incDecimal")
    text = model.get_formatted_text(0, 0)
    assert "1,234,567.000" in text

    # Decrease decimal
    assert win.action_registry.has_action("decDecimal")
    win.action_registry.trigger_action("decDecimal")
    text = model.get_formatted_text(0, 0)
    assert "1,234,567.00" in text


def test_alignment_actions(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    model.set_cell(0, 0, CellData(value="Test"))
    win.spreadsheet_view.selection.select_cell(0, 0)

    win.action_registry.trigger_action("alignCenter")
    assert model.get_cell(0, 0).align_h == "center"

    win.action_registry.trigger_action("alignRight")
    assert model.get_cell(0, 0).align_h == "right"

    win.action_registry.trigger_action("alignLeft")
    assert model.get_cell(0, 0).align_h == "left"


def test_merge_and_center_toggle(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    model.set_cell(0, 0, CellData(value="Header"))

    sel = win.spreadsheet_view.selection
    sel.clear()
    sel.add_range(SelectionRange(0, 0, 1, 2))
    sel.set_active_cell(0, 0)

    # Initial: not merged
    assert not model.is_merged(0, 0)

    # 1. Trigger mergeCenter -> merge and center
    win.action_registry.trigger_action("mergeCenter")
    assert model.is_merged(0, 0)
    assert model.get_cell(0, 0).align_h == "center"
    act_merge = win.action_registry.get_action("mergeCenter")
    assert act_merge.isChecked()

    # 2. Trigger mergeCenter again -> unmerge
    win.action_registry.trigger_action("mergeCenter")
    assert not model.is_merged(0, 0)
    assert not act_merge.isChecked()


def test_border_presets_application(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    model.set_cell(0, 0, CellData(value="A1"))
    model.set_cell(0, 1, CellData(value="B1"))
    model.set_cell(1, 0, CellData(value="A2"))
    model.set_cell(1, 1, CellData(value="B2"))

    sel = win.spreadsheet_view.selection
    sel.clear()
    sel.add_range(SelectionRange(0, 0, 1, 1))
    sel.set_active_cell(0, 0)

    # Apply outline border
    win.action_registry.trigger_action("borderOutline")
    c00 = model.get_cell(0, 0)
    assert c00.border_top is not None
    assert c00.border_left is not None

    # Apply no border
    win.action_registry.trigger_action("borderNone")
    c00_cleared = model.get_cell(0, 0)
    assert c00_cleared.border_top is None
    assert c00_cleared.border_left is None


def test_drawing_toolbar_and_floating_objects(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.show()

    # Toggle drawing toolbar
    assert not win.toolbars["drawing"].isVisible()
    win.action_registry.trigger_action("tb_drawing")
    assert win.toolbars["drawing"].isVisible()

    # Insert textbox
    win.action_registry.trigger_action("insertTextBox")
    objs = win.spreadsheet_view.object_layer.objects
    assert any(o.kind == "textbox" for o in objs)

    # Insert shape
    win.action_registry.trigger_action("insertShape")
    objs = win.spreadsheet_view.object_layer.objects
    assert any(o.kind == "rect" for o in objs)

    # Chart wizard creates chart and triggers chart context
    win.action_registry.trigger_action("chartWizard")
    assert win.toolbars["chart"].isVisible()


def test_two_way_formatting_state_sync(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    # Set cell (0, 0) with distinct formatting
    model.set_cell(
        0,
        0,
        CellData(
            value="Formatted",
            bold=True,
            italic=True,
            underline=True,
            align_h="center",
            font_family="宋体",
            font_size=16,
        ),
    )
    # Set cell (1, 1) with normal formatting
    model.set_cell(
        1,
        1,
        CellData(
            value="Normal",
            bold=False,
            italic=False,
            underline=False,
            align_h="left",
            font_family="Arial",
            font_size=10,
        ),
    )

    # 1. Select (0, 0) -> actions should become checked
    win.spreadsheet_view.selection.select_cell(0, 0)
    assert win.action_registry.get_action("bold").isChecked()
    assert win.action_registry.get_action("italic").isChecked()
    assert win.action_registry.get_action("underline").isChecked()
    assert win.action_registry.get_action("alignCenter").isChecked()

    fmt_tb = win.toolbars["formatting"]
    font_combo = fmt_tb.findChild(QComboBox, "Ledger_FontCombo")
    size_combo = fmt_tb.findChild(QComboBox, "Ledger_SizeCombo")
    if font_combo:
        assert font_combo.currentText() == "宋体"
    if size_combo:
        assert size_combo.currentText() == "16"

    # 2. Select (1, 1) -> actions should become unchecked
    win.spreadsheet_view.selection.select_cell(1, 1)
    assert not win.action_registry.get_action("bold").isChecked()
    assert not win.action_registry.get_action("italic").isChecked()
    assert not win.action_registry.get_action("underline").isChecked()
    assert win.action_registry.get_action("alignLeft").isChecked()
    if font_combo:
        assert font_combo.currentText() == "Arial"
    if size_combo:
        assert size_combo.currentText() == "10"


def test_all_dropdown_and_split_actions_registered(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    expected_actions = [
        # Undo / Redo split menus
        "undo",
        "undo_empty",
        "redo",
        "redo_empty",
        # AutoSum split menu
        "autoSum",
        "autoSum_sum",
        "autoSum_average",
        "autoSum_count",
        "autoSum_max",
        "autoSum_min",
        "autoSum_more",
        # Borders formatting split menu
        "bordersApply",
        "border_bottom",
        "border_top",
        "border_left",
        "border_right",
        "border_none",
        "border_all",
        "border_thick_box",
        "border_bottom_double",
        # Borders toolbar split menu & color
        "bordersPalette",
        "border_pal_none",
        "border_pal_bottom",
        "border_pal_top",
        "border_pal_all",
        "border_pal_outside",
        "border_pal_thick",
        "border_line_color",
        "border_color_auto",
        "border_color_black",
        "border_color_red",
        "border_color_blue",
        "border_color_gray",
        # Validation auditing split menu
        "validation",
        "validation_dlg",
        "circleInvalid",
        "clearCircles",
        # List toolbar drop menu
        "list_menu",
        "insertRows",
        "insertCols",
        "sortDlg",
        "autoFilter",
        "totalRow",
        "convertToRange",
        # Chart toolbar drop menu
        "chart_type_menu",
        "chart_type_column",
        "chart_type_line",
        "chart_type_pie",
        "chart_type_bar",
        "chart_type_area",
        "chart_type_scatter",
        "chart_type_radar",
        # Drawing toolbar drop menu
        "draw_menu",
        "bringToFront",
        "sendToBack",
        "draw_group",
        "draw_ungroup",
    ]

    for aid in expected_actions:
        assert win.action_registry.has_action(
            aid
        ), f"Action '{aid}' must be registered in action_registry"


def test_autosum_dropdown_functions(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    # Set numeric values in A1:A3
    model.set_cell(0, 0, CellData(value=10))
    model.set_cell(1, 0, CellData(value=20))
    model.set_cell(2, 0, CellData(value=30))

    # 1. Average
    win.spreadsheet_view.selection.select_cell(3, 0)
    win.action_registry.trigger_action("autoSum_average")
    c = model.get_cell(3, 0)
    assert c is not None
    assert c.formula == "AVERAGE(A1:A3)"
    assert c.value == 20.0

    # 2. Count
    win.spreadsheet_view.selection.select_cell(3, 0)
    win.action_registry.trigger_action("autoSum_count")
    c = model.get_cell(3, 0)
    assert c is not None
    assert c.formula == "COUNT(A1:A3)"
    assert c.value == 3.0

    # 3. Max
    win.spreadsheet_view.selection.select_cell(3, 0)
    win.action_registry.trigger_action("autoSum_max")
    c = model.get_cell(3, 0)
    assert c is not None
    assert c.formula == "MAX(A1:A3)"
    assert c.value == 30.0

    # 4. Min
    win.spreadsheet_view.selection.select_cell(3, 0)
    win.action_registry.trigger_action("autoSum_min")
    c = model.get_cell(3, 0)
    assert c is not None
    assert c.formula == "MIN(A1:A3)"
    assert c.value == 10.0


def test_borders_dropdown_wiring(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    model.set_cell(0, 0, CellData(value="BordersTest"))
    win.spreadsheet_view.selection.select_cell(0, 0)

    # Top border
    win.action_registry.trigger_action("border_top")
    c = model.get_cell(0, 0)
    assert c.border_top is not None

    # Bottom border
    win.action_registry.trigger_action("border_bottom")
    c = model.get_cell(0, 0)
    assert c.border_bottom is not None

    # Double bottom border
    win.action_registry.trigger_action("border_bottom_double")
    c = model.get_cell(0, 0)
    assert c.border_bottom is not None
    assert c.border_bottom.style == "double"

    # Thick outline
    win.action_registry.trigger_action("border_thick_box")
    c = model.get_cell(0, 0)
    assert c.border_top.style == "medium"
    assert c.border_bottom.style == "medium"


def test_border_line_color_actions(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    model.set_cell(0, 0, CellData(value="ColorBorder"))
    win.spreadsheet_view.selection.select_cell(0, 0)

    # Apply all borders then change color to Red
    win.action_registry.trigger_action("bordersApply")
    win.action_registry.trigger_action("border_color_red")
    c = model.get_cell(0, 0)
    assert c.border_top is not None
    assert c.border_top.color == "#FF0000"

    # Change to Blue
    win.action_registry.trigger_action("border_color_blue")
    c = model.get_cell(0, 0)
    assert c.border_top.color == "#0000FF"


def test_list_toolbar_actions(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    model.set_cell(0, 0, CellData(value="Row0"))
    model.set_cell(1, 0, CellData(value="Row1"))
    model.set_cell(0, 1, CellData(value="Col1"))

    # 1. Insert row at row 1 -> Row1 moves to row 2
    win.spreadsheet_view.selection.select_cell(1, 0)
    win.action_registry.trigger_action("insertRows")
    assert model.get_cell_value(0, 0) == "Row0"
    assert model.get_cell_value(2, 0) == "Row1"

    # 2. Insert col at col 1 -> Col1 moves to col 2
    win.spreadsheet_view.selection.select_cell(0, 1)
    win.action_registry.trigger_action("insertCols")
    assert model.get_cell_value(0, 2) == "Col1"

    # 3. Toggle autoFilter
    assert not win.action_registry.get_action("autoFilter").isChecked()
    win.action_registry.trigger_action("autoFilter")
    assert win.action_registry.get_action("autoFilter").isChecked()
    assert getattr(model, "auto_filter", None) is not None

    # 4. Convert to range clears autoFilter
    win.action_registry.trigger_action("convertToRange")
    assert not win.action_registry.get_action("autoFilter").isChecked()
    assert getattr(model, "auto_filter", None) is None


def test_chart_toolbar_type_dropdown(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    # Trigger chart_type_line
    win.action_registry.trigger_action("chart_type_line")
    objs = win.spreadsheet_view.object_layer.objects
    assert any(getattr(o, "chart_type", "") == "line" for o in objs)

    # Select chart and change to pie
    win.action_registry.trigger_action("chart_type_pie")
    assert any(getattr(o, "chart_type", "") == "pie" for o in objs)


def test_drawing_z_order_actions(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    # Insert two shapes
    win.action_registry.trigger_action("insertTextBox")
    win.action_registry.trigger_action("insertShape")
    objs = win.spreadsheet_view.object_layer.objects
    assert len(objs) >= 2

    # Select the first object and bring to front
    first_obj = objs[0]
    win.spreadsheet_view.object_layer.select_object(first_obj)
    win.action_registry.trigger_action("bringToFront")
    assert win.spreadsheet_view.object_layer.objects[-1] == first_obj

    # Send to back
    win.action_registry.trigger_action("sendToBack")
    assert win.spreadsheet_view.object_layer.objects[0] == first_obj


def test_inapplicable_actions_disabled(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    # Inapplicable items must be disabled
    act_undo_empty = win.action_registry.get_action("undo_empty")
    act_redo_empty = win.action_registry.get_action("redo_empty")
    act_draw_group = win.action_registry.get_action("draw_group")
    act_draw_ungroup = win.action_registry.get_action("draw_ungroup")

    assert act_undo_empty is not None and not act_undo_empty.isEnabled()
    assert act_redo_empty is not None and not act_redo_empty.isEnabled()
    assert act_draw_group is not None and not act_draw_group.isEnabled()
    assert act_draw_ungroup is not None and not act_draw_ungroup.isEnabled()


def test_toolbar_dropdown_retranslate_ui(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    # Switch to zh-CN
    load_locale("zh-CN")
    win.retranslate_ui()
    act_sum = win.action_registry.get_action("autoSum_sum")
    assert act_sum is not None
    assert "求和" in act_sum.text()

    # Switch to en
    load_locale("en")
    win.retranslate_ui()
    assert "Sum" in act_sum.text()

    # Switch to ja
    load_locale("ja")
    win.retranslate_ui()
    assert "合計" in act_sum.text()

    # Restore zh-CN
    load_locale("zh-CN")
    win.retranslate_ui()

