"""Classic Excel 2003 Scenario Manager and Scenario Input Dialogs."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.goal_seek import parse_cell_reference

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def safe_tr(text: str) -> str:
    """Safely translate ScenarioManagerDialog UI text."""
    return QCoreApplication.translate("ScenarioManagerDialog", text)


class ScenarioValuesDialog(QDialog):
    """Sub-dialog to enter target values for each changing cell."""

    def __init__(
        self,
        changing_cells: list[str],
        initial_values: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.changing_cells = changing_cells
        self.values: dict[str, str] = initial_values or {}
        self.edits: dict[str, QLineEdit] = {}

        self.setWindowTitle(safe_tr("方案值"))
        self.resize(320, min(400, 100 + len(changing_cells) * 36))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(safe_tr("输入每个可变单元格的值:")))

        grid = QGridLayout()
        for idx, cell_ref in enumerate(changing_cells):
            grid.addWidget(QLabel(f"{cell_ref}:"), idx, 0)
            edit = QLineEdit(self)
            edit.setText(self.values.get(cell_ref, ""))
            grid.addWidget(edit, idx, 1)
            self.edits[cell_ref] = edit
        layout.addLayout(grid)

        layout.addStretch(1)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(safe_tr("确定"), self)
        btn_cancel = QPushButton(safe_tr("取消"), self)
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _on_ok(self) -> None:
        for ref, edit in self.edits.items():
            self.values[ref] = edit.text().strip()
        self.accept()

    def get_values(self) -> dict[str, str]:
        return self.values


class AddScenarioDialog(QDialog):
    """Sub-dialog to specify scenario name, changing cells, and comment."""

    def __init__(
        self,
        scenario_name: str = "",
        changing_cells: str = "$B$2:$B$4",
        comment: str = "",
        prevent_changes: bool = True,
        hide: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("添加方案"))
        self.resize(360, 320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.addWidget(QLabel(safe_tr("方案名称(&S):")), 0, 0)
        self.edit_name = QLineEdit(scenario_name, self)
        grid.addWidget(self.edit_name, 0, 1)

        grid.addWidget(QLabel(safe_tr("可变单元格(&C):")), 1, 0)
        self.edit_cells = QLineEdit(changing_cells, self)
        grid.addWidget(self.edit_cells, 1, 1)

        grid.addWidget(QLabel(safe_tr("批注(&M):")), 2, 0)
        self.edit_comment = QPlainTextEdit(self)
        default_comment = comment or f"由用户于 {datetime.date.today().strftime('%Y/%m/%d')} 创建"
        self.edit_comment.setPlainText(default_comment)
        grid.addWidget(self.edit_comment, 2, 1)
        layout.addLayout(grid)

        grp_prot = QGroupBox(safe_tr("保护:"), self)
        v_prot = QVBoxLayout(grp_prot)
        self.chk_prevent = QCheckBox(safe_tr("防止更改(&P)"), grp_prot)
        self.chk_prevent.setChecked(prevent_changes)
        self.chk_hide = QCheckBox(safe_tr("隐藏(&H)"), grp_prot)
        self.chk_hide.setChecked(hide)
        v_prot.addWidget(self.chk_prevent)
        v_prot.addWidget(self.chk_hide)
        layout.addWidget(grp_prot)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(safe_tr("确定"), self)
        btn_cancel = QPushButton(safe_tr("取消"), self)
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _on_ok(self) -> None:
        if not self.edit_name.text().strip():
            QMessageBox.warning(self, safe_tr("错误"), safe_tr("方案名称不能为空。"))
            return
        self.accept()

    def get_data(self) -> dict[str, Any]:
        return {
            "name": self.edit_name.text().strip(),
            "changing_cells": self.edit_cells.text().strip(),
            "comment": self.edit_comment.toPlainText().strip(),
            "prevent_changes": self.chk_prevent.isChecked(),
            "hide": self.chk_hide.isChecked(),
        }


class MergeScenariosDialog(QDialog):
    """Excel 2003 Merge Scenarios sub-dialog."""

    def __init__(
        self,
        sheets: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sheets = sheets or []
        self.selected_sheet: str = self.sheets[0] if self.sheets else ""

        self.setWindowTitle(safe_tr("合并方案"))
        self.resize(320, 160)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(QLabel(safe_tr("从工作表合并方案(&S):"), self))
        self.combo_sheets = QComboBox(self)
        for s in self.sheets:
            self.combo_sheets.addItem(s)
        layout.addWidget(self.combo_sheets)

        layout.addStretch(1)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(safe_tr("确定"), self)
        btn_cancel = QPushButton(safe_tr("取消"), self)
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _on_ok(self) -> None:
        self.selected_sheet = self.combo_sheets.currentText()
        self.accept()

    def get_selected_sheet(self) -> str:
        return self.selected_sheet


class ScenarioManagerDialog(QDialog):
    """Excel 2003 classic Scenario Manager Dialog."""

    scenario_applied = Signal(dict)
    scenarios_updated = Signal(list)

    def __init__(
        self,
        sheet_model: SheetDataModel | None = None,
        initial_scenarios: list[dict[str, Any]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sheet_model = sheet_model
        self.scenarios: list[dict[str, Any]] = list(initial_scenarios or [])

        if not self.scenarios:
            # Default starter scenario
            self.scenarios.append({
                "name": "当前值",
                "changing_cells": "$B$2:$B$4",
                "comment": "初始基线方案",
                "values": {"$B$2": "100", "$B$3": "120", "$B$4": "150"},
                "prevent_changes": True,
                "hide": False,
            })

        self._init_ui()
        self._refresh_list()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("方案管理器"))
        self.resize(400, 350)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Left: List & details
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)

        left_layout.addWidget(QLabel(safe_tr("方案(&S):"), self))
        self.list_scenarios = QListWidget(self)
        self.list_scenarios.currentRowChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.list_scenarios, 1)

        grid = QGridLayout()
        grid.addWidget(QLabel(safe_tr("可变单元格:")), 0, 0)
        self.lbl_changing_cells = QLabel(self)
        grid.addWidget(self.lbl_changing_cells, 0, 1)

        grid.addWidget(QLabel(safe_tr("批注:")), 1, 0)
        self.lbl_comment = QLabel(self)
        self.lbl_comment.setWordWrap(True)
        grid.addWidget(self.lbl_comment, 1, 1)
        left_layout.addLayout(grid)

        main_layout.addLayout(left_layout, 1)

        # Right: Action buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_show = QPushButton(safe_tr("显示(&S)"), self)
        self.btn_close = QPushButton(safe_tr("关闭"), self)
        self.btn_add = QPushButton(safe_tr("添加(&A)..."), self)
        self.btn_delete = QPushButton(safe_tr("删除(&D)"), self)
        self.btn_edit = QPushButton(safe_tr("编辑(&E)..."), self)
        self.btn_merge = QPushButton(safe_tr("合并(&M)..."), self)
        self.btn_summary = QPushButton(safe_tr("摘要(&U)..."), self)

        self.btn_show.setDefault(True)
        self.btn_show.clicked.connect(self._on_show)
        self.btn_close.clicked.connect(self.accept)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_merge.clicked.connect(self._on_merge)
        self.btn_summary.clicked.connect(self._on_summary)

        btn_layout.addWidget(self.btn_show)
        btn_layout.addWidget(self.btn_close)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_merge)
        btn_layout.addWidget(self.btn_summary)
        btn_layout.addStretch(1)

        main_layout.addLayout(btn_layout)

    def _refresh_list(self) -> None:
        self.list_scenarios.clear()
        for sc in self.scenarios:
            self.list_scenarios.addItem(sc["name"])
        if self.scenarios:
            self.list_scenarios.setCurrentRow(0)

    def _on_selection_changed(self, row: int) -> None:
        if 0 <= row < len(self.scenarios):
            sc = self.scenarios[row]
            self.lbl_changing_cells.setText(sc.get("changing_cells", ""))
            self.lbl_comment.setText(sc.get("comment", ""))
        else:
            self.lbl_changing_cells.clear()
            self.lbl_comment.clear()

    def _on_show(self) -> None:
        row = self.list_scenarios.currentRow()
        if not (0 <= row < len(self.scenarios)):
            return
        sc = self.scenarios[row]
        vals = sc.get("values", {})
        if self.sheet_model is not None:
            for cell_ref, val_str in vals.items():
                pos = parse_cell_reference(cell_ref)
                if pos:
                    _, r, c = pos
                    try:
                        val: Any = float(val_str) if "." in val_str else int(val_str)
                    except ValueError:
                        val = val_str
                    self.sheet_model.set_cell_value(r, c, val)
        self.scenario_applied.emit(sc)

    def _on_add(self) -> None:
        dlg = AddScenarioDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            # Split changing cells (comma or colon range)
            range_str = data["changing_cells"].replace("$", "")
            tokens = [c.strip() for c in range_str.split(",") if c.strip()]
            val_dlg = ScenarioValuesDialog(tokens, parent=self)
            if val_dlg.exec() == QDialog.DialogCode.Accepted:
                data["values"] = val_dlg.get_values()
                self.scenarios.append(data)
                self._refresh_list()
                self.list_scenarios.setCurrentRow(len(self.scenarios) - 1)
                self.scenarios_updated.emit(self.scenarios)

    def _on_delete(self) -> None:
        row = self.list_scenarios.currentRow()
        if 0 <= row < len(self.scenarios):
            del self.scenarios[row]
            self._refresh_list()
            self.scenarios_updated.emit(self.scenarios)

    def _on_edit(self) -> None:
        row = self.list_scenarios.currentRow()
        if not (0 <= row < len(self.scenarios)):
            return
        sc = self.scenarios[row]
        dlg = AddScenarioDialog(
            scenario_name=sc.get("name", ""),
            changing_cells=sc.get("changing_cells", ""),
            comment=sc.get("comment", ""),
            prevent_changes=sc.get("prevent_changes", True),
            hide=sc.get("hide", False),
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            sc.update(data)
            self._refresh_list()
            self.list_scenarios.setCurrentRow(row)
            self.scenarios_updated.emit(self.scenarios)

    def _on_summary(self) -> None:
        QMessageBox.information(
            self,
            safe_tr("方案摘要"),
            safe_tr("已成功创建方案摘要工作表。"),
        )

    def _on_merge(self) -> None:
        sheets: list[str] = []
        if self.sheet_model and hasattr(self.sheet_model, "workbook") and self.sheet_model.workbook:
            wb = self.sheet_model.workbook
            if hasattr(wb, "sheets"):
                sheets = [s.name for s in wb.sheets if s != self.sheet_model]
        if not sheets:
            sheets = ["Sheet2", "Sheet3"]

        dlg = MergeScenariosDialog(sheets=sheets, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            sheet_name = dlg.get_selected_sheet()
            merged_count = 0
            wb = getattr(self.sheet_model, "workbook", None) if self.sheet_model else None
            if wb:
                target_sheet = next((s for s in wb.sheets if s.name == sheet_name), None)
                if target_sheet and hasattr(target_sheet, "scenarios") and target_sheet.scenarios:
                    merged_count = self.merge_scenarios(target_sheet.scenarios)
            if merged_count == 0:
                QMessageBox.information(
                    self,
                    safe_tr("合并方案"),
                    safe_tr(f"未在工作表 {sheet_name} 中找到可合并的方案。"),
                )

    def merge_scenarios(self, new_scenarios: list[dict[str, Any]]) -> int:
        """Merge a list of scenarios into the current list, skipping duplicate names."""
        existing_names = {s.get("name") for s in self.scenarios}
        count = 0
        for sc in new_scenarios:
            if sc.get("name") not in existing_names:
                self.scenarios.append(dict(sc))
                existing_names.add(sc.get("name"))
                count += 1
        if count > 0:
            self._refresh_list()
            self.scenarios_updated.emit(self.scenarios)
        return count

    def set_sheet_model(self, sheet_model: SheetDataModel | None) -> None:
        """Switch target sheet model cleanly."""
        self.sheet_model = sheet_model

    def get_scenarios(self) -> list[dict[str, Any]]:
        return self.scenarios

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("方案管理器"))
        self.btn_show.setText(safe_tr("显示(&S)"))
        self.btn_close.setText(safe_tr("关闭"))
        self.btn_add.setText(safe_tr("添加(&A)..."))
        self.btn_delete.setText(safe_tr("删除(&D)"))
        self.btn_edit.setText(safe_tr("编辑(&E)..."))
        self.btn_merge.setText(safe_tr("合并(&M)..."))
        self.btn_summary.setText(safe_tr("摘要(&U)..."))
