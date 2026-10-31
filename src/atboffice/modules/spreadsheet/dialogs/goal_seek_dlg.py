"""Excel 2003 classic Goal Seek input and status dialogs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.goal_seek import (
    GoalSeekParams,
    GoalSeekResult,
    parse_cell_reference,
    solve_goal_seek,
)
from atboffice.modules.spreadsheet.calc.references import cell_name

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


def safe_tr(text: str) -> str:
    """Translate UI text safely for Goal Seek dialogs."""
    return QCoreApplication.translate("GoalSeekDialog", text)


def _get_sheet(workbook: Any, name: str) -> Any:
    """Look up sheet by name."""
    if hasattr(workbook, "get_sheet_by_name"):
        return workbook.get_sheet_by_name(name)
    sheets = getattr(workbook, "sheets", [])
    for s in sheets:
        if getattr(s, "name", "") == name:
            return s
    return None


class GoalSeekDialog(QDialog):
    """Excel 2003 classic Goal Seek input dialog."""

    def __init__(
        self,
        workbook: WorkbookModel | None = None,
        current_sheet: SheetDataModel | None = None,
        initial_r: int = 0,
        initial_c: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.workbook = workbook
        self.current_sheet = current_sheet
        self.initial_r = initial_r
        self.initial_c = initial_c

        self._init_ui()

    def _init_ui(self) -> None:
        self.setFixedWidth(340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Left input fields
        form_layout = QGridLayout()
        form_layout.setVerticalSpacing(8)
        form_layout.setHorizontalSpacing(8)

        self.lbl_target = QLabel(self)
        self.edit_target_cell = QLineEdit(self)
        self.lbl_target.setBuddy(self.edit_target_cell)

        self.lbl_goal = QLabel(self)
        self.edit_goal_value = QLineEdit(self)
        self.lbl_goal.setBuddy(self.edit_goal_value)

        self.lbl_changing = QLabel(self)
        self.edit_changing_cell = QLineEdit(self)
        self.lbl_changing.setBuddy(self.edit_changing_cell)

        form_layout.addWidget(self.lbl_target, 0, 0)
        form_layout.addWidget(self.edit_target_cell, 0, 1)

        form_layout.addWidget(self.lbl_goal, 1, 0)
        form_layout.addWidget(self.edit_goal_value, 1, 1)

        form_layout.addWidget(self.lbl_changing, 2, 0)
        form_layout.addWidget(self.edit_changing_cell, 2, 1)

        main_layout.addLayout(form_layout)

        # Right action buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_ok = QPushButton(self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok_clicked)
        btn_layout.addWidget(self.btn_ok)

        self.btn_cancel = QPushButton(self)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # Default values
        default_ref = cell_name(self.initial_r, self.initial_c, ra=True, ca=True)
        self.edit_target_cell.setText(default_ref)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Update localized UI text."""
        self.setWindowTitle(safe_tr("单变量求解"))
        self.lbl_target.setText(safe_tr("目标单元格(&E):"))
        self.lbl_goal.setText(safe_tr("目标值(&V):"))
        self.lbl_changing.setText(safe_tr("可变单元格(&C):"))
        self.btn_ok.setText(safe_tr("确定"))
        self.btn_cancel.setText(safe_tr("取消"))

    def _on_ok_clicked(self) -> None:
        """Validate inputs and launch numerical solve."""
        if self.workbook is None:
            QMessageBox.warning(self, safe_tr("单变量求解"), safe_tr("未找到活动工作簿。"))
            return

        default_sheet_name = self.current_sheet.name if self.current_sheet else "Sheet1"

        # 1. Parse target cell
        raw_target = self.edit_target_cell.text().strip()
        try:
            t_sheet, t_r, t_c = parse_cell_reference(raw_target, default_sheet=default_sheet_name)
        except ValueError:
            QMessageBox.warning(
                self,
                safe_tr("单变量求解"),
                safe_tr("目标单元格必须是有效的单元格引用。"),
            )
            self.edit_target_cell.setFocus()
            return

        # 2. Parse goal value
        raw_goal = self.edit_goal_value.text().strip()
        try:
            goal_num = float(raw_goal)
        except (ValueError, TypeError):
            QMessageBox.warning(
                self,
                safe_tr("单变量求解"),
                safe_tr("请输入有效的数字目标值。"),
            )
            self.edit_goal_value.setFocus()
            return

        # 3. Parse changing cell
        raw_changing = self.edit_changing_cell.text().strip()
        try:
            ch_sheet, ch_r, ch_c = parse_cell_reference(
                raw_changing, default_sheet=default_sheet_name
            )
        except ValueError:
            QMessageBox.warning(
                self,
                safe_tr("单变量求解"),
                safe_tr("可变单元格必须是有效的单元格引用。"),
            )
            self.edit_changing_cell.setFocus()
            return

        # 4. Check formula constraints
        target_sh = _get_sheet(self.workbook, t_sheet)
        if target_sh is None:
            QMessageBox.warning(
                self,
                safe_tr("单变量求解"),
                safe_tr("目标工作表不存在。"),
            )
            return

        t_cell = target_sh.get_cell(t_r, t_c)
        if t_cell is None or not t_cell.formula:
            QMessageBox.warning(
                self,
                safe_tr("单变量求解"),
                safe_tr("目标单元格必须包含公式。"),
            )
            self.edit_target_cell.setFocus()
            return

        changing_sh = _get_sheet(self.workbook, ch_sheet)
        if changing_sh is None:
            QMessageBox.warning(
                self,
                safe_tr("单变量求解"),
                safe_tr("可变工作表不存在。"),
            )
            return

        ch_cell = changing_sh.get_cell(ch_r, ch_c)
        if ch_cell is not None and ch_cell.formula:
            QMessageBox.warning(
                self,
                safe_tr("单变量求解"),
                safe_tr("可变单元格必须包含数值，不能包含公式。"),
            )
            self.edit_changing_cell.setFocus()
            return

        if t_sheet == ch_sheet and t_r == ch_r and t_c == ch_c:
            QMessageBox.warning(
                self,
                safe_tr("单变量求解"),
                safe_tr("目标单元格与可变单元格不能为同一单元格。"),
            )
            return

        params = GoalSeekParams(
            target_sheet=t_sheet,
            target_row=t_r,
            target_col=t_c,
            goal_value=goal_num,
            changing_sheet=ch_sheet,
            changing_row=ch_r,
            changing_col=ch_c,
        )

        try:
            result = solve_goal_seek(self.workbook, params)
        except Exception as exc:
            QMessageBox.warning(self, safe_tr("单变量求解"), str(exc))
            return

        # Temporarily apply solution to view so status dialog can show current value
        if changing_sh is not None:
            c_cell = changing_sh.get_cell(ch_r, ch_c)
            if c_cell is None:
                from atboffice.modules.spreadsheet.models.sheet_model import CellData

                c_cell = CellData(value=result.solution)
                changing_sh.set_cell(ch_r, ch_c, c_cell)
            else:
                c_cell.value = result.solution
            self.workbook.recalculate()

        # Display status result dialog
        status_dlg = GoalSeekStatusDialog(
            workbook=self.workbook,
            result=result,
            parent=self.parentWidget(),
        )

        if status_dlg.exec() == QDialog.DialogCode.Accepted:
            status_dlg.apply_solution()
            self.accept()
        else:
            status_dlg.revert_solution()


class GoalSeekStatusDialog(QDialog):
    """Excel 2003 classic Goal Seek Status results dialog."""

    def __init__(
        self,
        workbook: WorkbookModel | None = None,
        result: GoalSeekResult | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.workbook = workbook
        self.result = result

        self._init_ui()

    def _init_ui(self) -> None:
        self.setFixedWidth(320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Status text
        self.lbl_status = QLabel(self)
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # Grid box for values
        grid_box = QGroupBox(self)
        grid_layout = QGridLayout(grid_box)
        grid_layout.setContentsMargins(8, 8, 8, 8)
        grid_layout.setHorizontalSpacing(10)
        grid_layout.setVerticalSpacing(6)

        self.lbl_target_title = QLabel(self)
        self.lbl_target_val = QLabel(self)
        self.lbl_target_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.lbl_current_title = QLabel(self)
        self.lbl_current_val = QLabel(self)
        self.lbl_current_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        grid_layout.addWidget(self.lbl_target_title, 0, 0)
        grid_layout.addWidget(self.lbl_target_val, 0, 1)

        grid_layout.addWidget(self.lbl_current_title, 1, 0)
        grid_layout.addWidget(self.lbl_current_val, 1, 1)

        layout.addWidget(grid_box)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_ok = QPushButton(self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.btn_ok)

        self.btn_cancel = QPushButton(self)
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

        self._update_data()
        self.retranslate_ui()

    def _update_data(self) -> None:
        """Populate numbers and status description from result."""
        if self.result is None:
            return

        if self.result.success:
            msg = safe_tr("目标单元格 {0} 的单变量求解已找到一个解。").format(
                self.result.target_cell_name
            )
        else:
            msg = safe_tr("目标单元格 {0} 的单变量求解可能尚未找到解。").format(
                self.result.target_cell_name
            )
        self.lbl_status.setText(msg)

        # Numeric display
        self.lbl_target_val.setText(str(self.result.target_value))

        curr = self.result.current_value
        if isinstance(curr, float):
            if curr.is_integer():
                self.lbl_current_val.setText(str(int(curr)))
            else:
                self.lbl_current_val.setText(f"{curr:.4g}")
        else:
            self.lbl_current_val.setText(str(curr))

    def retranslate_ui(self) -> None:
        """Update localized UI text."""
        self.setWindowTitle(safe_tr("单变量求解状态"))
        self.lbl_target_title.setText(safe_tr("目标值:"))
        self.lbl_current_title.setText(safe_tr("当前值:"))
        self.btn_ok.setText(safe_tr("确定"))
        self.btn_cancel.setText(safe_tr("取消"))
        self._update_data()

    def apply_solution(self) -> None:
        """Write the solved value into the changing cell."""
        if self.workbook is None or self.result is None:
            return

        sh = _get_sheet(self.workbook, self.result.changing_sheet)
        if sh is not None:
            cell = sh.get_cell(self.result.changing_row, self.result.changing_col)
            if cell is None:
                from atboffice.modules.spreadsheet.models.sheet_model import CellData

                cell = CellData(value=self.result.solution)
                sh.set_cell(self.result.changing_row, self.result.changing_col, cell)
            else:
                cell.value = self.result.solution
            self.workbook.recalculate()

    def revert_solution(self) -> None:
        """Restore the initial value into the changing cell."""
        if self.workbook is None or self.result is None:
            return

        sh = _get_sheet(self.workbook, self.result.changing_sheet)
        if sh is not None:
            cell = sh.get_cell(self.result.changing_row, self.result.changing_col)
            if cell is not None:
                cell.value = self.result.initial_value
            self.workbook.recalculate()

    def _on_ok(self) -> None:
        self.apply_solution()
        self.accept()

    def _on_cancel(self) -> None:
        self.revert_solution()
        self.reject()
