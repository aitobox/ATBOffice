"""Tests for HoneycombColorDialog, DocumentPropertiesDialog, and InAppSaveAsDialog."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog
import pytest

from atboffice.ui.components.color_picker import ColorPickerPopup
from atboffice.ui.components.honeycomb_color_dialog import (
    GrayscaleStrip,
    HoneycombColorDialog,
    HoneycombWidget,
)
from atboffice.ui.dialogs.document_properties_dialog import (
    DocumentMetadata,
    DocumentPropertiesDialog,
)
from atboffice.ui.dialogs.in_app_save_as_dialog import (
    ConfirmPasswordDialog,
    InAppSaveAsDialog,
    SecurityOptionsDialog,
)


def test_honeycomb_color_dialog_geometry_and_cells(qtbot):
    """Verify HoneycombWidget generates exactly 127 hexagonal cells and grayscale strip."""
    dlg = HoneycombColorDialog(initial_color="#FF0000")
    qtbot.addWidget(dlg)

    honey = dlg.honeycomb
    assert len(honey._cells) == 127

    # Center cell (row 6, col 6) is white
    center_cell = [c for c in honey._cells if c.row == 6 and c.col == 6][0]
    assert center_cell.color.name().upper() == "#FFFFFF"

    # Grayscale strip has 16 steps
    grays = dlg.grays
    assert isinstance(grays, GrayscaleStrip)


def test_honeycomb_color_dialog_custom_tab_sync(qtbot):
    """Verify RGB and Hex input syncing in HoneycombColorDialog."""
    dlg = HoneycombColorDialog(initial_color="#3366FF")
    qtbot.addWidget(dlg)

    assert dlg.spin_r.value() == 0x33
    assert dlg.spin_g.value() == 0x66
    assert dlg.spin_b.value() == 0xFF
    assert dlg.edit_hex.text().upper() == "#3366FF"

    # Modify RGB in Custom tab
    dlg.spin_r.setValue(255)
    dlg.spin_g.setValue(0)
    dlg.spin_b.setValue(128)

    assert dlg.selected_color().name().upper() == "#FF0080"
    assert dlg.edit_hex.text().upper() == "#FF0080"


def test_color_picker_popup_opens_honeycomb(qtbot):
    """Verify ColorPickerPopup._open_more_colors_dialog integrates HoneycombColorDialog."""
    popup = ColorPickerPopup()
    qtbot.addWidget(popup)

    chosen_colors = []
    popup.color_selected.connect(chosen_colors.append)

    with patch.object(HoneycombColorDialog, "getColor", return_value=QColor("#00FF88")):
        popup._open_more_colors_dialog()

    assert chosen_colors == ["#00FF88"]


def test_document_properties_dialog_tabs_and_custom_props(qtbot):
    """Verify DocumentPropertiesDialog 5 tabs and custom properties CRUD."""
    meta = DocumentMetadata(
        title="Test Title",
        author="Test Author",
        words=1250,
        pages=5,
        headings=["Introduction", "Methods", "Results"],
        custom_properties={"Project": {"type": "text", "value": "ATBOffice"}},
    )
    dlg = DocumentPropertiesDialog(meta)
    qtbot.addWidget(dlg)

    # 5 tabs check
    assert dlg.tab_widget.count() == 5
    assert "常规" in dlg.tab_widget.tabText(0)
    assert "摘要" in dlg.tab_widget.tabText(1)
    assert "统计" in dlg.tab_widget.tabText(2)
    assert "内容" in dlg.tab_widget.tabText(3)
    assert "自定义" in dlg.tab_widget.tabText(4)

    # Summary check
    assert dlg.edit_title.text() == "Test Title"
    assert dlg.edit_author.text() == "Test Author"

    # Contents check
    assert dlg.list_contents.count() == 3

    # Custom properties check
    assert dlg.table_custom.rowCount() == 1
    assert dlg.table_custom.item(0, 0).text() == "Project"

    # Add new custom property
    dlg.combo_prop_name.setEditText("Department")
    dlg.combo_prop_type.setCurrentIndex(0)
    dlg.edit_prop_val.setText("Engineering")
    dlg.btn_add_prop.click()

    assert dlg.table_custom.rowCount() == 2
    assert "Department" in dlg.metadata.custom_properties
    assert dlg.metadata.custom_properties["Department"]["value"] == "Engineering"

    # Edit fields and accept
    dlg.edit_title.setText("Updated Title")
    dlg._on_accept()
    assert dlg.metadata.title == "Updated Title"


def test_security_options_and_password_confirmation(qtbot):
    """Verify SecurityOptionsDialog encryption options and password confirmation."""
    sec_dlg = SecurityOptionsDialog({"password": "", "read_only_recommended": False})
    qtbot.addWidget(sec_dlg)

    sec_dlg.edit_open_pwd.setText("Secret123")
    sec_dlg.chk_read_only.setChecked(True)

    with patch.object(ConfirmPasswordDialog, "exec", return_value=QDialog.DialogCode.Accepted), \
         patch.object(ConfirmPasswordDialog, "confirmed_password", return_value="Secret123"):
        sec_dlg._on_accept()

    opts = sec_dlg.get_security_options()
    assert opts["password"] == "Secret123"
    assert opts["read_only_recommended"] is True


def test_in_app_save_as_dialog(tmp_path: Path, qtbot):
    """Verify InAppSaveAsDialog path selection, extension appending, and tools menu."""
    dlg = InAppSaveAsDialog(
        initial_path=tmp_path / "MyDoc.docx",
        filter_str="Word 文档 (*.docx);;所有文件 (*.*)",
    )
    qtbot.addWidget(dlg)

    assert dlg.edit_filename.text() == "MyDoc"
    assert dlg.btn_tools is not None

    dlg.edit_filename.setText("FinalReport")
    dlg._on_save_clicked()

    path, filter_type, sec_opts = dlg.get_save_info()
    assert path is not None
    assert path.name == "FinalReport.docx"
    assert "Word 文档" in filter_type
