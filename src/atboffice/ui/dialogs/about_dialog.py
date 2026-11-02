"""Comprehensive About dialog for ATBOffice matching VibeOffice 008_dialog_about."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atboffice import __app_name__, __version__
from atboffice.core.i18n import safe_tr


class AboutDialog(QDialog):
    """About dialog providing product overview, versioning, and link to OSS licenses."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(440, 280)
        self.resize(480, 310)

        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        # Header with app name and version
        self.lbl_title = QLabel(self)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.lbl_title.setFont(title_font)
        layout.addWidget(self.lbl_title)

        # Apps description
        self.lbl_apps = QLabel(self)
        self.lbl_apps.setWordWrap(True)
        self.lbl_apps.setStyleSheet("font-size: 13px; color: #1E293B;")
        layout.addWidget(self.lbl_apps)

        # Storage / Privacy note
        self.lbl_privacy = QLabel(self)
        self.lbl_privacy.setWordWrap(True)
        self.lbl_privacy.setStyleSheet("font-size: 12px; color: #64748B; line-height: 1.4;")
        layout.addWidget(self.lbl_privacy)

        # Open Source statement with license action button
        self.lbl_oss = QLabel(self)
        self.lbl_oss.setWordWrap(True)
        self.lbl_oss.setStyleSheet("font-size: 12px; color: #334155;")
        layout.addWidget(self.lbl_oss)

        layout.addStretch(1)

        # Bottom actions
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_licenses = QPushButton(self)
        self.btn_licenses.clicked.connect(self._on_open_licenses)
        btn_layout.addWidget(self.btn_licenses)

        self.btn_check_update = QPushButton(self)
        self.btn_check_update.clicked.connect(self._on_check_update)
        btn_layout.addWidget(self.btn_check_update)

        btn_layout.addStretch(1)

        self.btn_ok = QPushButton(self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_ok)

        layout.addLayout(btn_layout)

    def _on_open_licenses(self) -> None:
        from atboffice.ui.dialogs.license_dialog import LicenseDialog

        dlg = LicenseDialog(self)
        dlg.exec()

    def _on_check_update(self) -> None:
        from atboffice.core.updater import check_for_updates

        check_for_updates(parent=self, manual=True)

    def retranslate_ui(self) -> None:
        """Update localized UI text dynamically."""
        self.setWindowTitle(
            safe_tr("关于 {app_name}").format(app_name=__app_name__)
        )
        self.lbl_title.setText(
            f"{__app_name__}  v{__version__}"
        )
        self.lbl_apps.setText(
            safe_tr("ATBOffice 原生跨平台办公套件：包含 Quire（文本文档）、Ledger（电子表格）与 Lectern（演示文稿）。")
        )
        self.lbl_privacy.setText(
            safe_tr("所有文档均完全运行在您的本地设备上并安全存取。最近文档仅在本地保留快捷打开缓存。")
        )
        self.lbl_oss.setText(
            safe_tr("由全球优秀的开源软件与字体赋能构建。")
        )
        self.btn_licenses.setText(safe_tr("开源许可证与鸣谢(&L)..."))
        self.btn_check_update.setText(safe_tr("检查更新(&U)..."))
        self.btn_ok.setText(safe_tr("确定"))
