"""Classic Excel 2003 Protect Sheet & Protect Workbook Dialogs."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


def safe_tr(text: str) -> str:
    """Safely translate ProtectDialog UI string."""
    return QCoreApplication.translate("ProtectDialog", text)


SHEET_PERMISSIONS = [
    ("select_locked_cells", "选定锁定单元格", "Select locked cells", True),
    ("select_unlocked_cells", "选定未锁定单元格", "Select unlocked cells", True),
    ("format_cells", "设置单元格格式", "Format cells", False),
    ("format_columns", "设置列格式", "Format columns", False),
    ("format_rows", "设置行格式", "Format rows", False),
    ("insert_columns", "插入列", "Insert columns", False),
    ("insert_rows", "插入行", "Insert rows", False),
    ("insert_hyperlinks", "插入超链接", "Insert hyperlinks", False),
    ("delete_columns", "删除列", "Delete columns", False),
    ("delete_rows", "删除行", "Delete rows", False),
    ("sort", "排序", "Sort", False),
    ("use_autofilter", "使用自动筛选", "Use AutoFilter", False),
    ("use_pivot_reports", "使用数据透视表", "Use PivotTable reports", False),
    ("edit_objects", "编辑对象", "Edit objects", False),
    ("edit_scenarios", "编辑方案", "Edit scenarios", False),
]


class ConfirmPasswordDialog(QDialog):
    """Sub-dialog to re-enter password for verification."""

    def __init__(self, original_password: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.original_password = original_password
        self.setWindowTitle(safe_tr("确认密码"))
        self.setFixedWidth(320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(QLabel(safe_tr("请再次输入密码以继续。此密码需区分大小写。")))

        self.edit_confirm = QLineEdit(self)
        self.edit_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.edit_confirm)

        layout.addWidget(
            QLabel(
                safe_tr(
                    "<b>注意:</b> 如果您丢失或忘记了密码，将无法恢复该密码。"
                    "建议将密码和相应的工作簿及工作表名称保存在安全的地方。"
                )
            )
        )

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
        if self.edit_confirm.text() != self.original_password:
            QMessageBox.critical(
                self,
                safe_tr("错误"),
                safe_tr("确认的密码与提供的密码不一致。"),
            )
            return
        self.accept()


class ProtectSheetDialog(QDialog):
    """Excel 2003 classic Protect Sheet Dialog."""

    sheet_protected = Signal(dict)

    def __init__(
        self,
        sheet_model: SheetDataModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sheet_model = sheet_model

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("保护工作表"))
        self.resize(360, 440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Protect contents checkbox
        self.check_protect_contents = QCheckBox(safe_tr("保护工作表及锁定的单元格内容(&C)"), self)
        self.check_protect_contents.setChecked(True)
        main_layout.addWidget(self.check_protect_contents)

        # Password input
        h_pwd = QHBoxLayout()
        h_pwd.addWidget(QLabel(safe_tr("取消工作表保护时使用的密码(&P):")))
        self.edit_password = QLineEdit(self)
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        h_pwd.addWidget(self.edit_password)
        main_layout.addLayout(h_pwd)

        # Permissions checklist
        main_layout.addWidget(QLabel(safe_tr("允许此工作表的所有用户进行(&A):"), self))
        self.list_permissions = QListWidget(self)
        for perm_id, zh, en, default_chk in SHEET_PERMISSIONS:
            item = QListWidgetItem(f"{zh} ({en})", self.list_permissions)
            item.setData(Qt.ItemDataRole.UserRole, perm_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if default_chk else Qt.CheckState.Unchecked)
        main_layout.addWidget(self.list_permissions, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton(safe_tr("确定"), self)
        self.btn_cancel = QPushButton(safe_tr("取消"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)

    def get_protection_data(self) -> dict[str, Any]:
        perms = {}
        for idx in range(self.list_permissions.count()):
            item = self.list_permissions.item(idx)
            perm_id = item.data(Qt.ItemDataRole.UserRole)
            perms[perm_id] = (item.checkState() == Qt.CheckState.Checked)

        pwd = self.edit_password.text()
        pwd_hash = hashlib.sha256(pwd.encode("utf-8")).hexdigest() if pwd else ""
        return {
            "locked": self.check_protect_contents.isChecked(),
            "password_hash": pwd_hash,
            "has_password": bool(pwd),
            "permissions": perms,
        }

    def _on_ok(self) -> None:
        pwd = self.edit_password.text()
        if pwd:
            confirm_dlg = ConfirmPasswordDialog(pwd, parent=self)
            if confirm_dlg.exec() != QDialog.DialogCode.Accepted:
                return

        prot_data = self.get_protection_data()
        if self.sheet_model is not None:
            self.sheet_model.protection = prot_data

        self.sheet_protected.emit(prot_data)
        self.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("保护工作表"))
        self.check_protect_contents.setText(safe_tr("保护工作表及锁定的单元格内容(&C)"))
        self.btn_ok.setText(safe_tr("确定"))
        self.btn_cancel.setText(safe_tr("取消"))


class UnprotectSheetDialog(QDialog):
    """Excel 2003 classic Unprotect Sheet Dialog."""

    sheet_unprotected = Signal()

    def __init__(
        self,
        sheet_model: SheetDataModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sheet_model = sheet_model

        self.setWindowTitle(safe_tr("撤消工作表保护"))
        self.setFixedWidth(320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(QLabel(safe_tr("密码(&P):")))
        self.edit_password = QLineEdit(self)
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.edit_password)

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
        if self.sheet_model is not None and getattr(self.sheet_model, "protection", None):
            expected_hash = self.sheet_model.protection.get("password_hash", "")
            if expected_hash:
                input_hash = hashlib.sha256(self.edit_password.text().encode("utf-8")).hexdigest()
                if input_hash != expected_hash:
                    QMessageBox.critical(self, safe_tr("错误"), safe_tr("密码不正确。"))
                    return
            self.sheet_model.protection = None

        self.sheet_unprotected.emit()
        self.accept()


class ProtectWorkbookDialog(QDialog):
    """Excel 2003 classic Protect Workbook Dialog."""

    workbook_protected = Signal(dict)

    def __init__(
        self,
        workbook_model: WorkbookModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.workbook_model = workbook_model

        self.setWindowTitle(safe_tr("保护工作簿"))
        self.setFixedWidth(320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        grp_opt = QGroupBox(safe_tr("保护工作簿的内容:"), self)
        v_opt = QVBoxLayout(grp_opt)
        self.chk_structure = QCheckBox(safe_tr("结构(&S)"), grp_opt)
        self.chk_structure.setChecked(True)
        self.chk_windows = QCheckBox(safe_tr("窗口(&W)"), grp_opt)
        self.chk_windows.setChecked(False)
        v_opt.addWidget(self.chk_structure)
        v_opt.addWidget(self.chk_windows)
        layout.addWidget(grp_opt)

        h_pwd = QHBoxLayout()
        h_pwd.addWidget(QLabel(safe_tr("密码(可选)(&P):")))
        self.edit_password = QLineEdit(self)
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        h_pwd.addWidget(self.edit_password)
        layout.addLayout(h_pwd)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(safe_tr("确定"), self)
        btn_cancel = QPushButton(safe_tr("取消"), self)
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def get_protection_data(self) -> dict[str, Any]:
        pwd = self.edit_password.text()
        pwd_hash = hashlib.sha256(pwd.encode("utf-8")).hexdigest() if pwd else ""
        return {
            "structure": self.chk_structure.isChecked(),
            "windows": self.chk_windows.isChecked(),
            "password_hash": pwd_hash,
            "has_password": bool(pwd),
        }

    def _on_ok(self) -> None:
        pwd = self.edit_password.text()
        if pwd:
            confirm_dlg = ConfirmPasswordDialog(pwd, parent=self)
            if confirm_dlg.exec() != QDialog.DialogCode.Accepted:
                return

        prot_data = self.get_protection_data()
        if self.workbook_model is not None:
            self.workbook_model.protection = prot_data

        self.workbook_protected.emit(prot_data)
        self.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("保护工作簿"))
        self.chk_structure.setText(safe_tr("结构(&S)"))
        self.chk_windows.setText(safe_tr("窗口(&W)"))
