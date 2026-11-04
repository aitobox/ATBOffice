"""GUI verification tests for Phase 7 TASK-712: Visible Commands and Dynamic i18n."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.models.document import Document, Paragraph, TextItem
from atboffice.modules.writer.views.outline_view import (
    OutlineToolbar,
    OutlineViewWidget,
    heading_level,
)


def test_outline_toolbar_level_change(qapp: QApplication) -> None:
    """Verify OutlineToolbar level combo emits signal and updates paragraph level."""
    tb = OutlineToolbar()
    emitted_levels: list[int] = []
    tb.outline_level_changed.connect(emitted_levels.append)

    # Change level combo to Heading 2 (index 2)
    tb._combo_outline_level.setCurrentIndex(2)
    assert 2 in emitted_levels

    doc = Document()
    p = Paragraph(id=1, runs=[TextItem("Chapter 1")])
    doc.main.blocks.append(p)

    view = OutlineViewWidget(doc=doc)
    view.selected_para = p

    # Set outline level to 1 (Heading 1)
    view.set_selected_outline_level(1)
    assert heading_level(doc, p) == 1
    assert p.p_pr.style == "Heading1"
    assert p.p_pr.outline_level == 0

    # Demote to body text (level 0)
    view.set_selected_outline_level(0)
    assert heading_level(doc, p) == 0
    assert p.p_pr.style == "Normal"
    assert p.p_pr.outline_level is None


def test_chart_wizard_series_crud_and_sheet_isolation(qapp: QApplication) -> None:
    """Verify ChartWizardDialog series add/delete, data sync, and cancel safety."""
    from atboffice.modules.spreadsheet.dialogs.chart_wizard import ChartWizardDialog
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

    wb = WorkbookModel()
    sheet1 = wb.sheets[0]
    sheet1.drawings = []

    dlg = ChartWizardDialog(sheet_model=sheet1, workbook_model=wb)

    # Move to Step 2 (Source Data)
    dlg.btn_next.click()
    assert dlg.current_step == 1
    # Switch to Series tab (tab index 1)
    dlg.tabs_source.setCurrentIndex(1)

    initial_count = dlg.list_series.count()
    assert initial_count >= 1

    # Add series
    dlg.btn_add_series.click()
    assert dlg.list_series.count() == initial_count + 1

    # Edit series name and values for current series
    cur_row = dlg.list_series.currentRow()
    assert cur_row == initial_count
    dlg.edit_series_name.setText("Quarterly Profit")
    dlg.edit_series_values.setText("=Sheet1!$C$2:$C$10")
    dlg.edit_series_x.setText("=Sheet1!$A$2:$A$10")

    # Verify series in list item display reflects name
    assert "Quarterly Profit" in dlg.list_series.currentItem().text()

    # Verify spec export includes series
    spec = dlg.get_chart_spec()
    assert "series" in spec
    assert len(spec["series"]) == initial_count + 1
    assert spec["series"][-1]["name"] == "Quarterly Profit"
    assert spec["series"][-1]["values"] == "=Sheet1!$C$2:$C$10"

    # Delete series
    dlg.btn_del_series.click()
    assert dlg.list_series.count() == initial_count

    # Test Cancel does not modify sheet drawings
    dlg.reject()
    assert len(sheet1.drawings) == 0

    # Test set_sheet_model switching
    sheet2 = SheetDataModel(name="Sheet2")
    sheet2.drawings = []
    dlg2 = ChartWizardDialog(sheet_model=sheet1, workbook_model=wb)
    dlg2.set_sheet_model(sheet2)
    dlg2.btn_finish.click()
    # sheet1 should NOT have drawings, sheet2 should have 1 drawing
    assert len(sheet1.drawings) == 0
    assert len(sheet2.drawings) == 1


def test_scenario_manager_merge_and_document_safety(qapp: QApplication) -> None:
    """Verify ScenarioManagerDialog merge scenarios, button wiring, and document isolation."""
    from atboffice.modules.spreadsheet.dialogs.scenario_manager_dialog import (
        MergeScenariosDialog,
        ScenarioManagerDialog,
    )
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel

    sheet1 = SheetDataModel(name="Sheet1")
    sheet1.set_cell_value(1, 1, 100)  # B2 = 100

    scenarios1 = [
        {
            "name": "Base",
            "changing_cells": "$B$2",
            "comment": "Baseline",
            "values": {"$B$2": "100"},
        }
    ]

    dlg = ScenarioManagerDialog(sheet_model=sheet1, initial_scenarios=scenarios1)
    assert dlg.btn_merge is not None

    # Merge scenarios from another source
    source_scenarios = [
        {
            "name": "Optimistic",
            "changing_cells": "$B$2",
            "comment": "High growth",
            "values": {"$B$2": "200"},
        }
    ]

    # Test merge dialog class exists
    merge_dlg = MergeScenariosDialog(sheets=["Sheet1", "Sheet2"], parent=dlg)
    assert merge_dlg is not None

    # Merge directly through method
    dlg.merge_scenarios(source_scenarios)
    names = [s["name"] for s in dlg.get_scenarios()]
    assert "Optimistic" in names
    assert len(dlg.get_scenarios()) == 2

    # Verify document safety: applying a scenario mutates sheet1
    dlg.list_scenarios.setCurrentRow(1)
    dlg._on_show()
    assert sheet1.get_cell_value(1, 1) == 200

    # Switching sheet_model updates reference
    sheet2 = SheetDataModel(name="Sheet2")
    sheet2.set_cell_value(1, 1, 50)
    dlg.set_sheet_model(sheet2)
    dlg.list_scenarios.setCurrentRow(0)
    dlg._on_show()
    # sheet2 updated to 100, sheet1 unchanged
    assert sheet2.get_cell_value(1, 1) == 100
    assert sheet1.get_cell_value(1, 1) == 200


def test_ledger_options_custom_lists_and_screentips(qapp: QApplication) -> None:
    """Verify LedgerOptionsDialog custom lists CRUD and ScreenTips setting."""
    from atboffice.modules.spreadsheet.dialogs.options_dialog import (
        BUILTIN_CUSTOM_LISTS,
        LedgerOptionsDialog,
    )

    dlg = LedgerOptionsDialog()
    assert hasattr(dlg, "chk_show_screentips")
    assert dlg.chk_show_screentips.isChecked()

    # Check ScreenTips option exported
    opts = dlg.get_options()
    assert "show_screentips" in opts
    assert opts["show_screentips"] is True

    # Switch to Custom Lists tab (index 4)
    dlg.tabs.setCurrentIndex(4)

    # Initial state: "新序列" is selected
    assert dlg.list_custom_lists.currentRow() == 0
    assert dlg.btn_del_list.isEnabled() is False

    # Select built-in list (index 1)
    dlg.list_custom_lists.setCurrentRow(1)
    assert dlg.btn_del_list.isEnabled() is False
    assert len(dlg.edit_list_entries.toPlainText()) > 0

    # Go back to "新序列", enter new list and add
    dlg.list_custom_lists.setCurrentRow(0)
    dlg.edit_list_entries.setPlainText("North\nSouth\nEast\nWest")
    dlg.btn_add_list.click()

    # User list added and selected
    new_idx = dlg.list_custom_lists.currentRow()
    assert new_idx > len(BUILTIN_CUSTOM_LISTS)
    assert dlg.btn_del_list.isEnabled() is True
    assert "North" in dlg.list_custom_lists.currentItem().text()

    opts = dlg.get_options()
    assert "custom_lists" in opts
    assert any("North" in item for cl in opts["custom_lists"] for item in cl)

    # Delete the newly added custom list
    dlg.btn_del_list.click()
    assert dlg.list_custom_lists.currentRow() == 0
    assert dlg.btn_del_list.isEnabled() is False


def test_hyperlink_screentip_dialog(qapp: QApplication) -> None:
    """Verify HyperlinkDialog ScreenTip sub-dialog and screentip in returned data."""
    from atboffice.modules.writer.dialogs.reference_dialogs import (
        HyperlinkDialog,
        HyperlinkScreenTipDialog,
    )

    tip_dlg = HyperlinkScreenTipDialog(initial_tip="Click to open", parent=None)
    assert tip_dlg is not None
    assert tip_dlg.get_screentip() == "Click to open"

    dlg = HyperlinkDialog(initial_text="Link Text", initial_address="https://example.com")
    dlg.screentip = "Official Portal"

    data = dlg.get_hyperlink_data()
    assert "screentip" in data
    assert data["screentip"] == "Official Portal"
    assert data["text"] == "Link Text"
    assert data["target"] == "https://example.com"


def test_action_registry_fallback_and_whitelist(qapp: QApplication) -> None:
    """Verify ActionRegistry capability explanations, whitelist, and no duplicate triggers."""
    from atboffice.core.action_registry import ActionRegistry, ActionSpec

    reg = ActionRegistry()
    spec = ActionSpec(
        id="act_draw_canvas",
        label="绘图画布",
        tip="插入绘图画布",
        disabled_reason="依赖底层对象层引擎",
    )
    action = reg.register_action(spec)
    assert action is not None

    # Register whitelist info for abstract or setMenu containers
    reg.register_whitelist_action(
        "act_menu_file_container",
        kind="setMenu",
        reason="文件顶层下拉菜单容器",
    )
    assert reg.is_whitelisted_action("act_menu_file_container")
    info = reg.get_whitelist_info("act_menu_file_container")
    assert info is not None and info["kind"] == "setMenu"

    # Verify triggering fires single trigger event without duplicate handler calls
    trigger_count = 0

    def handler() -> None:
        nonlocal trigger_count
        trigger_count += 1

    reg.set_handler("act_draw_canvas", handler)

    # Retranslate UI roundtrip
    reg.retranslate_ui()
    reg.retranslate_ui()
    reg.retranslate_ui()

    action.trigger()
    assert trigger_count == 1  # Verify no duplicate connections after retranslating


def test_multi_locale_retranslate_across_all_dialogs(qapp: QApplication) -> None:
    """Verify all 9 locales can switch dynamically and retranslate_ui executes cleanly."""
    from atboffice.core.action_registry import ActionRegistry, ActionSpec
    from atboffice.core.i18n import SUPPORTED_LOCALES, get_i18n_manager
    from atboffice.modules.spreadsheet.dialogs.chart_wizard import ChartWizardDialog
    from atboffice.modules.spreadsheet.dialogs.options_dialog import LedgerOptionsDialog
    from atboffice.modules.spreadsheet.dialogs.scenario_manager_dialog import (
        ScenarioManagerDialog,
    )
    from atboffice.modules.writer.dialogs.reference_dialogs import HyperlinkDialog
    from atboffice.modules.writer.views.outline_view import OutlineToolbar

    mgr = get_i18n_manager()

    reg = ActionRegistry()
    reg.register_action(ActionSpec(id="cmd_save", label="Save", tip="Save Document"))

    tb_outline = OutlineToolbar()
    dlg_chart = ChartWizardDialog()
    dlg_scenario = ScenarioManagerDialog()
    dlg_options = LedgerOptionsDialog()
    dlg_hyperlink = HyperlinkDialog()

    for loc in SUPPORTED_LOCALES:
        mgr.set_locale(loc)
        # Execute retranslate_ui on each component
        reg.retranslate_ui()
        tb_outline.retranslate_ui()
        dlg_chart.retranslate_ui()
        dlg_scenario.retranslate_ui()
        dlg_options.retranslate_ui()
        dlg_hyperlink.retranslate_ui()

    # Reset back to zh-CN
    mgr.set_locale("zh-CN")
    reg.retranslate_ui()
    dlg_chart.retranslate_ui()
    assert dlg_chart.btn_finish.text() == "完成(&F)"





