"""Office 2003 classic In-App Save As dialog with Tools security options."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QDir, QModelIndex, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileSystemModel,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for InAppSaveAsDialog."""
    return QCoreApplication.translate("InAppSaveAsDialog", text)


class ConfirmPasswordDialog(QDialog):
    """Secondary confirmation dialog for file encryption password."""

    def __init__(
        self, prompt: str = "请重新输入打开权限密码:", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("确认密码"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        lbl_prompt = QLabel(safe_tr(prompt), self)
        layout.addWidget(lbl_prompt)

        self.edit_pwd = QLineEdit(self)
        self.edit_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.edit_pwd)

        lbl_warn = QLabel(
            safe_tr("警告: 如果您丢失或遗忘了密码，将无法恢复。请妥善保管密码及其对应文档的名称。"),
            self,
        )
        lbl_warn.setWordWrap(True)
        lbl_warn.setStyleSheet("color: #666666; font-size: 11px;")
        layout.addWidget(lbl_warn)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText(safe_tr("确定"))
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText(safe_tr("取消"))
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def confirmed_password(self) -> str:
        return self.edit_pwd.text()


class SecurityOptionsDialog(QDialog):
    """File encryption and protection options dialog."""

    def __init__(
        self, initial_options: dict[str, Any] | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("安全选项"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setFixedWidth(400)

        self._options: dict[str, Any] = dict(initial_options or {})

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # File encryption group
        lbl_enc = QLabel(safe_tr("此文档的文件加密选项:"), self)
        lbl_enc.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_enc)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        self.edit_open_pwd = QLineEdit(self)
        self.edit_open_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_open_pwd.setText(self._options.get("password", ""))
        form.addRow(safe_tr("打开权限密码(&O):"), self.edit_open_pwd)

        self.edit_modify_pwd = QLineEdit(self)
        self.edit_modify_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_modify_pwd.setText(self._options.get("modify_password", ""))
        form.addRow(safe_tr("修改权限密码(&M):"), self.edit_modify_pwd)

        layout.addLayout(form)

        # File sharing options
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        lbl_share = QLabel(safe_tr("文件共享选项:"), self)
        lbl_share.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_share)

        self.chk_read_only = QCheckBox(safe_tr("建议以只读方式打开(&R)"), self)
        self.chk_read_only.setChecked(bool(self._options.get("read_only_recommended", False)))
        layout.addWidget(self.chk_read_only)

        lbl_note = QLabel(
            safe_tr(
                "注意: 使用密码保存的文件将进行加密保护（AES-256）。"
                "若未设置密码，则以普通无密码格式保存。"
            ),
            self,
        )
        lbl_note.setWordWrap(True)
        lbl_note.setStyleSheet("color: #555555; font-size: 11px;")
        layout.addWidget(lbl_note)

        # Dialog Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText(safe_tr("确定"))
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText(safe_tr("取消"))
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_accept(self) -> None:
        open_pwd = self.edit_open_pwd.text()
        # If open password changed and non-empty, prompt for confirmation
        if open_pwd and open_pwd != self._options.get("password", ""):
            dlg = ConfirmPasswordDialog("请重新输入打开权限密码:", self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            if dlg.confirmed_password() != open_pwd:
                QMessageBox.warning(
                    self, safe_tr("密码不匹配"), safe_tr("两次输入的密码不一致，请重试。")
                )
                return

        self._options["password"] = open_pwd
        self._options["modify_password"] = self.edit_modify_pwd.text()
        self._options["read_only_recommended"] = self.chk_read_only.isChecked()
        self.accept()

    def get_security_options(self) -> dict[str, Any]:
        return dict(self._options)


class InAppSaveAsDialog(QDialog):
    """In-app Office 2003 Save As dialog with file system browser and Tools options."""

    def __init__(
        self,
        initial_path: str | Path | None = None,
        filter_str: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("另存为"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.resize(620, 440)

        if initial_path:
            p = Path(initial_path).resolve()
            if p.is_dir():
                self._current_dir = p
                self._initial_name = "未命名文档"
            else:
                self._current_dir = p.parent
                self._initial_name = p.stem
        else:
            self._current_dir = Path.home()
            self._initial_name = "未命名文档"

        self._filter_str = filter_str or safe_tr(
            "Word 文档 (*.docx);;Word 97-2003 文档 (*.doc);;纯文本 (*.txt);;所有文件 (*.*)"
        )
        self._security_options: dict[str, Any] = {}
        self._result_path: Path | None = None

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Top Bar: Look In / Save In
        top_layout = QHBoxLayout()
        top_layout.setSpacing(6)
        lbl_look_in = QLabel(safe_tr("保存在(&I):"), self)
        top_layout.addWidget(lbl_look_in)

        self.combo_dir = QComboBox(self)
        self.combo_dir.addItem(self._current_dir.name, str(self._current_dir))
        self.combo_dir.setEnabled(False)
        top_layout.addWidget(self.combo_dir, stretch=1)

        # Up one level button
        btn_up = QToolButton(self)
        btn_up.setText("↑")
        btn_up.setToolTip(safe_tr("向上"))
        btn_up.clicked.connect(self._on_navigate_up)
        top_layout.addWidget(btn_up)

        layout.addLayout(top_layout)

        # File List View
        self.fs_model = QFileSystemModel(self)
        self.fs_model.setRootPath(str(self._current_dir))
        filter_flags = QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot
        self.fs_model.setFilter(filter_flags)

        self.file_view = QListView(self)
        self.file_view.setModel(self.fs_model)
        self.file_view.setRootIndex(self.fs_model.index(str(self._current_dir)))
        self.file_view.doubleClicked.connect(self._on_file_double_clicked)
        self.file_view.clicked.connect(self._on_file_clicked)
        layout.addWidget(self.file_view, stretch=1)

        # Bottom Form: File Name & Save As Type
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(6)

        self.edit_filename = QLineEdit(self._initial_name, self)
        form.addRow(safe_tr("文件名(&N):"), self.edit_filename)

        self.combo_type = QComboBox(self)
        filters = [f.strip() for f in self._filter_str.split(";;") if f.strip()]
        for f in filters:
            self.combo_type.addItem(f)
        form.addRow(safe_tr("保存类型(&T):"), self.combo_type)

        layout.addLayout(form)

        # Bottom action bar: Tools menu button & Save/Cancel buttons
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        # Tools Menu Button
        self.btn_tools = QToolButton(self)
        self.btn_tools.setText(safe_tr("工具(&L) ▼"))
        self.btn_tools.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        tools_menu = QMenu(self.btn_tools)
        act_sec = tools_menu.addAction(safe_tr("安全选项(&S)..."))
        act_sec.triggered.connect(self._open_security_options)
        self.btn_tools.setMenu(tools_menu)
        bottom_bar.addWidget(self.btn_tools)

        bottom_bar.addStretch(1)

        self.btn_save = QPushButton(safe_tr("保存(&S)"), self)
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._on_save_clicked)
        bottom_bar.addWidget(self.btn_save)

        self.btn_cancel = QPushButton(safe_tr("取消"), self)
        self.btn_cancel.clicked.connect(self.reject)
        bottom_bar.addWidget(self.btn_cancel)

        layout.addLayout(bottom_bar)

    def _on_navigate_up(self) -> None:
        parent = self._current_dir.parent
        if parent and parent != self._current_dir and parent.exists():
            self._set_directory(parent)

    def _set_directory(self, path: Path) -> None:
        self._current_dir = path
        self.combo_dir.clear()
        self.combo_dir.addItem(self._current_dir.name, str(self._current_dir))
        self.file_view.setRootIndex(self.fs_model.index(str(self._current_dir)))

    def _on_file_clicked(self, index: QModelIndex) -> None:
        file_path = Path(self.fs_model.filePath(index))
        if file_path.is_file():
            self.edit_filename.setText(file_path.stem)

    def _on_file_double_clicked(self, index: QModelIndex) -> None:
        file_path = Path(self.fs_model.filePath(index))
        if file_path.is_dir():
            self._set_directory(file_path)
        else:
            self.edit_filename.setText(file_path.stem)
            self._on_save_clicked()

    def _open_security_options(self) -> None:
        dlg = SecurityOptionsDialog(self._security_options, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._security_options = dlg.get_security_options()

    def _on_save_clicked(self) -> None:
        name = self.edit_filename.text().strip()
        if not name:
            QMessageBox.warning(self, safe_tr("提示"), safe_tr("请输入文件名。"))
            return

        # Determine extension from selected type filter
        type_text = self.combo_type.currentText()
        ext = ".docx"
        if "(*." in type_text:
            raw_ext = type_text.split("(*.")[1].split(")")[0]
            if not raw_ext.startswith("*"):
                ext = f".{raw_ext}"

        if not name.endswith(ext):
            target_file = f"{name}{ext}"
        else:
            target_file = name

        self._result_path = self._current_dir / target_file

        if self._result_path.exists():
            res = QMessageBox.warning(
                self,
                safe_tr("确认另存为"),
                safe_tr("文件“{name}”已存在。\n是否替换现有文件？").format(name=target_file),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if res != QMessageBox.StandardButton.Yes:
                return

        self.accept()

    def get_save_info(self) -> tuple[Path | None, str, dict[str, Any]]:
        """Return (target_path, selected_type_filter, security_options)."""
        return self._result_path, self.combo_type.currentText(), dict(self._security_options)
