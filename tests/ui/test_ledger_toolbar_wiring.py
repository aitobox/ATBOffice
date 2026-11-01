"""Comprehensive integration tests for Ledger toolbar action wiring and state synchronization."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from atboffice.core.i18n import load_locale
from atboffice.modules.spreadsheet.models.selection_model import SelectionRange
from atboffice.modules.spreadsheet.models.sheet_model import CellData
from atboffice.modules.spreadsheet.views.object_layer import FloatingObject
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


def test_format_painter_workflow_and_undo_redo(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    # Set source cell (0, 0) with bold, red text, yellow background, and specific border
    src = CellData(
        value="Header",
        bold=True,
        italic=True,
        fg_color="#FF0000",
        bg_color="#FFFF00",
    )
    model.set_cell(0, 0, src)

    # Set target cell (1, 1) with existing value and formula
    target = CellData(value=100, formula="=50*2", bold=False, italic=False)
    model.set_cell(1, 1, target)

    # Select source cell and trigger format painter
    win.spreadsheet_view.selection.select_cell(0, 0)
    assert win.action_registry.has_action("formatPainter")
    act_fp = win.action_registry.get_action("formatPainter")
    assert not act_fp.isChecked()

    win.action_registry.trigger_action("formatPainter")
    assert act_fp.isChecked()
    assert getattr(win, "_format_painter_active", False)

    # Apply to target cell (1, 1)
    win.apply_format_painter_to_range(1, 1, 1, 1)

    # Verify target cell received styles while preserving value and formula
    c_target = model.get_cell(1, 1)
    assert c_target.value == 100
    assert c_target.formula == "=50*2"
    assert c_target.bold is True
    assert c_target.italic is True
    assert c_target.fg_color == "#FF0000"
    assert c_target.bg_color == "#FFFF00"

    # Single-click format painter should auto-deactivate after application
    assert not act_fp.isChecked()
    assert not getattr(win, "_format_painter_active", False)

    # Test undo
    win.undo()
    c_target_undone = model.get_cell(1, 1)
    assert c_target_undone.value == 100
    assert c_target_undone.formula == "=50*2"
    assert c_target_undone.bold is False
    assert c_target_undone.italic is False
    assert c_target_undone.fg_color is None

    # Test redo
    win.redo()
    c_target_redone = model.get_cell(1, 1)
    assert c_target_redone.value == 100
    assert c_target_redone.bold is True
    assert c_target_redone.fg_color == "#FF0000"


def test_format_painter_sticky_and_cancel(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    model.set_cell(0, 0, CellData(value="Source", bold=True, fg_color="#008000"))
    model.set_cell(1, 0, CellData(value="Target1"))
    model.set_cell(2, 0, CellData(value="Target2"))

    win.spreadsheet_view.selection.select_cell(0, 0)
    # Double-click sticky mode
    win.toggle_format_painter(double_click=True)
    act_fp = win.action_registry.get_action("formatPainter")
    assert act_fp.isChecked()
    assert getattr(win, "_format_painter_sticky", False)

    # First application
    win.apply_format_painter_to_range(1, 0, 1, 0)
    assert model.get_cell(1, 0).bold is True
    assert model.get_cell(1, 0).fg_color == "#008000"
    # Still active because sticky!
    assert act_fp.isChecked()
    assert getattr(win, "_format_painter_active", False)

    # Second application
    win.apply_format_painter_to_range(2, 0, 2, 0)
    assert model.get_cell(2, 0).bold is True
    assert model.get_cell(2, 0).fg_color == "#008000"
    assert act_fp.isChecked()

    # Cancel format painter (e.g. Esc or re-click)
    win.action_registry.trigger_action("formatPainter")
    assert not act_fp.isChecked()
    assert not getattr(win, "_format_painter_active", False)


def test_hyperlink_dialog_direct(qtbot) -> None:
    from atboffice.modules.spreadsheet.dialogs.hyperlink_dialog import HyperlinkDialog

    # Test web URL tab
    dlg = HyperlinkDialog(
        existing_text="Google",
        existing_target="www.google.com",
        sheets=["Sheet1", "Sheet2"],
        is_existing=False,
    )
    qtbot.addWidget(dlg)
    data = dlg.get_data()
    assert not data["is_removed"]
    assert data["display"] == "Google"
    assert data["target"] == "http://www.google.com"

    # Test place in document tab
    dlg_doc = HyperlinkDialog(
        existing_text="",
        existing_location="'Sheet2'!B10",
        sheets=["Sheet1", "Sheet2"],
        is_existing=True,
    )
    qtbot.addWidget(dlg_doc)
    data_doc = dlg_doc.get_data()
    assert not data_doc["is_removed"]
    assert data_doc["location"] == "'Sheet2'!B10"
    assert data_doc["display"] == "'Sheet2'!B10"

    # Test mail tab
    dlg_mail = HyperlinkDialog(
        existing_text="Contact Support",
        existing_target="mailto:help@example.com?subject=Inquiry",
        sheets=["Sheet1"],
        is_existing=True,
    )
    qtbot.addWidget(dlg_mail)
    data_mail = dlg_mail.get_data()
    assert "mailto:help@example.com" in data_mail["target"]
    assert "Inquiry" in data_mail["target"]

    # Test remove link
    dlg_mail._on_remove_clicked()
    assert dlg_mail.is_removed is True
    assert dlg_mail.get_data()["is_removed"] is True

    # Test retranslate_ui
    dlg.retranslate_ui()
    assert dlg.windowTitle() != ""


def test_hyperlink_insert_edit_and_remove(qtbot, monkeypatch) -> None:
    from atboffice.modules.spreadsheet.dialogs.hyperlink_dialog import HyperlinkDialog

    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    # Cell (0, 0) initially empty
    win.spreadsheet_view.selection.select_cell(0, 0)

    # Mock dialog execution to return OK with web link
    def mock_exec_insert(self):
        self.edit_text.setText("Visit Site")
        self.edit_addr.setText("https://aitobox.com")
        self.is_removed = False
        return 1

    monkeypatch.setattr(HyperlinkDialog, "exec", mock_exec_insert)

    assert win.action_registry.has_action("hyperlink")
    win.action_registry.trigger_action("hyperlink")

    # Verify cell text, style, and model links
    c = model.get_cell(0, 0)
    assert c.value == "Visit Site"
    assert c.underline is True
    assert c.fg_color == "#0000FF"
    assert len(model.links) == 1
    assert model.links[0]["target"] == "https://aitobox.com"

    # Test edit and remove link
    def mock_exec_remove(self):
        self.is_removed = True
        return 1

    monkeypatch.setattr(HyperlinkDialog, "exec", mock_exec_remove)
    win.action_registry.trigger_action("hyperlink")

    # Verify link removed and style reverted
    c = model.get_cell(0, 0)
    assert len(model.links) == 0
    assert c.underline is False
    assert c.fg_color is None

    # Test undo restores link and styling
    win.undo()
    assert len(model.links) == 1
    c_undone = model.get_cell(0, 0)
    assert c_undone.underline is True
    assert c_undone.fg_color == "#0000FF"

    # Test redo
    win.redo()
    assert len(model.links) == 0


def test_hyperlink_cancel_operation(qtbot, monkeypatch) -> None:
    from atboffice.modules.spreadsheet.dialogs.hyperlink_dialog import HyperlinkDialog

    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    model.set_cell(0, 0, CellData(value="Original", bold=False, underline=False))
    win.spreadsheet_view.selection.select_cell(0, 0)

    # Mock dialog execution to simulate Cancel (returns 0)
    def mock_exec_cancel(self):
        self.edit_text.setText("Changed Text")
        self.edit_addr.setText("https://cancel.com")
        return 0

    monkeypatch.setattr(HyperlinkDialog, "exec", mock_exec_cancel)
    win.action_registry.trigger_action("hyperlink")

    # Verify nothing was altered
    c = model.get_cell(0, 0)
    assert c.value == "Original"
    assert c.underline is False
    assert len(getattr(model, "links", [])) == 0


def test_total_row_toggle_and_undo_redo(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    model = win.spreadsheet_view.model
    # Set data in A1:B3
    # A: Labels, B: Numbers
    model.set_cell(0, 0, CellData(value="Item1"))
    model.set_cell(0, 1, CellData(value=10.0))
    model.set_cell(1, 0, CellData(value="Item2"))
    model.set_cell(1, 1, CellData(value=20.0))
    model.set_cell(2, 0, CellData(value="Item3"))
    model.set_cell(2, 1, CellData(value=30.0))

    win.spreadsheet_view.selection.select_cell(0, 0)
    act_total = win.action_registry.get_action("totalRow")
    assert act_total is not None
    assert not act_total.isChecked()

    # 1. Toggle ON total row
    win.action_registry.trigger_action("totalRow")
    assert act_total.isChecked()
    assert getattr(win, "_total_row_active", False) is True

    # Total row should be at row 3 (index 3)
    lbl_c = model.get_cell(3, 0)
    assert lbl_c is not None
    assert lbl_c.value in ("汇总", "Total", "合计")
    assert lbl_c.bold is True
    assert lbl_c.border_top is not None and lbl_c.border_top.style == "thin"
    assert lbl_c.border_bottom is not None and lbl_c.border_bottom.style == "double"

    tot_c = model.get_cell(3, 1)
    assert tot_c is not None
    assert tot_c.value == 60.0
    assert "SUBTOTAL(109,B1:B3)" in tot_c.formula
    assert tot_c.bold is True
    assert tot_c.border_bottom.style == "double"

    # 2. Toggle OFF total row
    win.action_registry.trigger_action("totalRow")
    assert not act_total.isChecked()
    assert getattr(win, "_total_row_active", False) is False
    assert (3, 0) not in model.cells
    assert (3, 1) not in model.cells

    # 3. Test Undo restores total row
    win.undo()
    assert act_total.isChecked()
    assert getattr(win, "_total_row_active", False) is True
    assert model.get_cell(3, 1).value == 60.0

    # 4. Test Redo removes total row again
    win.redo()
    assert not act_total.isChecked()
    assert getattr(win, "_total_row_active", False) is False


def test_total_row_empty_sheet_and_convert_to_range(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    # Empty sheet: toggle total row should safely return without adding cells
    win.action_registry.trigger_action("totalRow")
    act_total = win.action_registry.get_action("totalRow")
    assert not act_total.isChecked()
    assert getattr(win, "_total_row_active", False) is False

    # Populate data, turn on total row, then convert to range
    model = win.spreadsheet_view.model
    model.set_cell(0, 0, CellData(value="A"))
    model.set_cell(0, 1, CellData(value=5))
    win.spreadsheet_view.selection.select_cell(0, 0)

    win.action_registry.trigger_action("totalRow")
    assert act_total.isChecked()
    assert getattr(win, "_total_row_active", False) is True

    # convertToRange should clear total row and uncheck action
    win.action_registry.trigger_action("convertToRange")
    assert not act_total.isChecked()
    assert getattr(win, "_total_row_active", False) is False
    assert (1, 0) not in model.cells


def test_format_object_context_enablement_and_dialog(qtbot, monkeypatch) -> None:
    from atboffice.modules.spreadsheet.dialogs.format_object_dialog import (
        FormatObjectDialog,
    )

    win = LedgerWindow()
    qtbot.addWidget(win)

    act_fo = win.action_registry.get_action("formatObject")
    assert act_fo is not None
    # Initially no object selected -> must be disabled!
    assert not act_fo.isEnabled()

    # Add a floating object
    layer = win.spreadsheet_view.object_layer
    obj = FloatingObject(
        name="TestRect",
        kind="rect",
        fill_color="#FF0000",
        line_color="#000000",
        line_width=1.0,
        abs_rect=(10, 10, 100, 50),
    )
    layer.add_object(obj)

    # Select object -> formatObject should become enabled
    layer.select_object(obj)
    assert act_fo.isEnabled()

    # Mock dialog execution to change fill color and width
    def mock_exec_format(self):
        self._current_fill_color = "#00FF00"
        self.spin_width.setValue(150)
        self._apply_and_accept()
        return 1

    monkeypatch.setattr(FormatObjectDialog, "exec", mock_exec_format)
    win.action_registry.trigger_action("formatObject")

    # Verify object updated
    assert obj.fill_color == "#00FF00"
    assert obj.abs_rect[2] == 150

    # Deselect object -> formatObject becomes disabled again
    layer.select_object(None)
    assert not act_fo.isEnabled()


def test_format_object_dialog_direct_and_cancel(qtbot) -> None:
    from atboffice.modules.spreadsheet.dialogs.format_object_dialog import (
        FormatObjectDialog,
    )

    obj = FloatingObject(
        name="ChartArea",
        kind="chart",
        fill_color="#123456",
        line_color="#654321",
        line_width=2.5,
        abs_rect=(0, 0, 200, 100),
    )
    dlg = FormatObjectDialog(obj)
    qtbot.addWidget(dlg)

    assert dlg.windowTitle() in ("设置图表区格式", "Format Chart Area")
    dlg.retranslate_ui()
    assert dlg.windowTitle() != ""

    # User modifies values in UI but cancels
    dlg.spin_width.setValue(300)
    dlg._current_fill_color = "#ABCDEF"
    dlg.reject()

    # Verify object remains untouched on cancel
    assert obj.fill_color == "#123456"
    assert obj.abs_rect[2] == 200


def test_hyperlink_and_format_object_dialog_seven_languages(qtbot) -> None:
    from atboffice.modules.spreadsheet.dialogs.format_object_dialog import (
        FormatObjectDialog,
    )
    from atboffice.modules.spreadsheet.dialogs.hyperlink_dialog import HyperlinkDialog

    obj = FloatingObject(name="Shape", kind="shape")
    dlg_fo = FormatObjectDialog(obj)
    qtbot.addWidget(dlg_fo)

    dlg_hl = HyperlinkDialog(sheets=["Sheet1"], is_existing=True)
    qtbot.addWidget(dlg_hl)

    for loc in ["zh-CN", "zh-Hant", "en", "ja", "ko", "fr", "de"]:
        load_locale(loc)
        dlg_fo.retranslate_ui()
        dlg_hl.retranslate_ui()
        assert dlg_fo.windowTitle() != ""
        assert dlg_hl.windowTitle() != ""
        assert dlg_hl.tab_widget.tabText(0) != ""
        assert dlg_fo.tab_widget.tabText(0) != ""

    load_locale("zh-CN")



