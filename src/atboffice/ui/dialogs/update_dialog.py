"""Software update dialog for ATBOffice matching VibeOffice updater UI specifications."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atboffice import __version__
from atboffice.core.i18n import safe_tr

if TYPE_CHECKING:
    from atboffice.core.updater import VersionInfo


class UpdateDialog(QDialog):
    """Dialog displaying new release information and download action matching 009_dialog_update."""

    def __init__(
        self,
        info: VersionInfo | None = None,
        current_version: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.info = info
        self.current_version = current_version or __version__

        self.setMinimumSize(480, 360)
        self.resize(520, 390)

        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Title / Version header
        self.label_header = QLabel(self)
        header_font = QFont()
        header_font.setPointSize(15)
        header_font.setBold(True)
        self.label_header.setFont(header_font)
        layout.addWidget(self.label_header)

        # Version status message
        self.label_version = QLabel(self)
        self.label_version.setWordWrap(True)
        self.label_version.setStyleSheet("font-size: 13px; color: #1E293B;")
        layout.addWidget(self.label_version)

        # Release prompt message
        self.label_prompt = QLabel(self)
        self.label_prompt.setWordWrap(True)
        self.label_prompt.setStyleSheet("font-size: 12px; color: #64748B;")
        layout.addWidget(self.label_prompt)

        # Changelog section header
        self.label_notes_title = QLabel(self)
        notes_hdr_font = QFont()
        notes_hdr_font.setBold(True)
        self.label_notes_title.setFont(notes_hdr_font)
        layout.addWidget(self.label_notes_title)

        # Changelog / Release notes text edit
        self.text_notes = QPlainTextEdit(self)
        self.text_notes.setReadOnly(True)
        raw_notes = self.info.body if self.info is not None else ""
        self.text_notes.setPlainText(raw_notes or safe_tr("暂无详细更新日志。"))
        layout.addWidget(self.text_notes, stretch=1)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)

        self.btn_later = QPushButton(self)
        self.btn_later.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_later)

        self.btn_download = QPushButton(self)
        self.btn_download.setDefault(True)
        self.btn_download.setStyleSheet(
            "background-color: #0284C7; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;"
        )
        self.btn_download.clicked.connect(self._on_download_clicked)
        btn_layout.addWidget(self.btn_download)

        layout.addLayout(btn_layout)

    def _on_download_clicked(self) -> None:
        url = self.info.html_url if self.info and self.info.html_url else "https://github.com/aitobox/ATBOffice/releases"
        QDesktopServices.openUrl(QUrl(url))
        self.accept()

    def retranslate_ui(self) -> None:
        """Update localized UI text across all widgets."""
        self.setWindowTitle(safe_tr("软件更新 — ATBOffice"))
        self.label_header.setText(safe_tr("发现新版本 ATBOffice"))

        new_ver = self.info.version if self.info else "1.0.1"
        self.label_version.setText(
            safe_tr("有更高版本的 ATBOffice 可用。当前版本为 v{cur_ver}，最新版本为 v{new_ver}。").format(
                cur_ver=self.current_version, new_ver=new_ver
            )
        )
        self.label_prompt.setText(
            safe_tr("现在下载更新吗？您的文档和最近打开的文件将保持原样。")
        )
        self.label_notes_title.setText(safe_tr("更新说明与日志："))
        self.btn_later.setText(safe_tr("稍后提醒(&L)"))
        self.btn_download.setText(safe_tr("前往下载(&D)"))
