"""Classic Excel 2003 Advanced Filter Dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.goal_seek import parse_cell_reference

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def safe_tr(text: str) -> str:
    """Safely translate AdvancedFilterDialog UI string."""
    return QCoreApplication.translate("AdvancedFilterDialog", text)


class AdvancedFilterDialog(QDialog):
    """Excel 2003 classic Advanced Filter Dialog."""

    filter_applied = Signal(dict)

    def __init__(
        self,
        sheet_model: SheetDataModel | None = None,
        initial_list_range: str = "$A$1:$D$20",
        initial_criteria_range: str = "$F$1:$G$2",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sheet_model = sheet_model
        self.list_range = initial_list_range
        self.criteria_range = initial_criteria_range

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("高级筛选"))
        self.setFixedWidth(360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)

        # Action radio buttons
        grp_action = QGroupBox(safe_tr("方式"), self)
        v_act = QVBoxLayout(grp_action)
        self.radio_in_place = QRadioButton(safe_tr("在原有区域显示筛选结果(&F)"), grp_action)
        self.radio_in_place.setChecked(True)
        self.radio_copy_to = QRadioButton(safe_tr("将筛选结果复制到其他位置(&C)"), grp_action)
        v_act.addWidget(self.radio_in_place)
        v_act.addWidget(self.radio_copy_to)
        left_layout.addWidget(grp_action)

        # Range edits
        grid_ranges = QGridLayout()
        grid_ranges.addWidget(QLabel(safe_tr("列表区域(&L):")), 0, 0)
        self.edit_list = QLineEdit(self.list_range, self)
        grid_ranges.addWidget(self.edit_list, 0, 1)

        grid_ranges.addWidget(QLabel(safe_tr("条件区域(&R):")), 1, 0)
        self.edit_criteria = QLineEdit(self.criteria_range, self)
        grid_ranges.addWidget(self.edit_criteria, 1, 1)

        grid_ranges.addWidget(QLabel(safe_tr("复制到(&O):")), 2, 0)
        self.edit_copy_to = QLineEdit(self)
        self.edit_copy_to.setEnabled(False)
        grid_ranges.addWidget(self.edit_copy_to, 2, 1)
        left_layout.addLayout(grid_ranges)

        self.radio_copy_to.toggled.connect(self._on_action_toggled)

        self.check_unique = QCheckBox(safe_tr("选择不重复的记录(&U)"), self)
        left_layout.addWidget(self.check_unique)

        main_layout.addLayout(left_layout, 1)

        # Right buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)
        self.btn_ok = QPushButton(safe_tr("确定"), self)
        self.btn_cancel = QPushButton(safe_tr("取消"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)
        main_layout.addLayout(btn_layout)

    def _on_action_toggled(self, checked: bool) -> None:
        self.edit_copy_to.setEnabled(checked)

    def get_filter_params(self) -> dict[str, Any]:
        return {
            "action": "copy_to" if self.radio_copy_to.isChecked() else "in_place",
            "list_range": self.edit_list.text().strip(),
            "criteria_range": self.edit_criteria.text().strip(),
            "copy_to": self.edit_copy_to.text().strip() if self.radio_copy_to.isChecked() else "",
            "unique_only": self.check_unique.isChecked(),
        }

    def _on_ok(self) -> None:
        params = self.get_filter_params()
        if not params["list_range"]:
            QMessageBox.warning(self, safe_tr("错误"), safe_tr("列表区域不能为空。"))
            return
        if not params["criteria_range"]:
            QMessageBox.warning(self, safe_tr("错误"), safe_tr("条件区域不能为空。"))
            return
        if params["action"] == "copy_to" and not params["copy_to"]:
            QMessageBox.warning(self, safe_tr("错误"), safe_tr("必须指定目标复制区域。"))
            return

        self.filter_applied.emit(params)
        self.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("高级筛选"))
        self.radio_in_place.setText(safe_tr("在原有区域显示筛选结果(&F)"))
        self.radio_copy_to.setText(safe_tr("将筛选结果复制到其他位置(&C)"))
        self.check_unique.setText(safe_tr("选择不重复的记录(&U)"))
        self.btn_ok.setText(safe_tr("确定"))
        self.btn_cancel.setText(safe_tr("取消"))
