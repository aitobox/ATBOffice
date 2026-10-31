"""Asynchronous update checker for ATBOffice based on GitHub Releases API."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError

from packaging import version
from PySide6.QtCore import QObject, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate text with fallback to original."""
    app = QApplication.instance()
    if app:
        translated = app.translate("Updater", text)
        if translated and translated != text:
            return translated
    return text


DEFAULT_RELEASES_API = "https://api.github.com/repos/aitobox/ATBOffice/releases/latest"


@dataclass
class VersionInfo:
    """Release information extracted from GitHub release."""

    version: str
    tag_name: str
    name: str
    body: str
    html_url: str
    published_at: str


def compare_versions(current_ver: str, remote_ver: str) -> int:
    """Compare two semantic version strings.

    Returns:
        1 if remote_ver is newer than current_ver
        0 if both versions are identical
        -1 if remote_ver is older than current_ver
    """
    clean_cur = current_ver.strip().lstrip("vV")
    clean_rem = remote_ver.strip().lstrip("vV")

    try:
        v_cur = version.parse(clean_cur)
        v_rem = version.parse(clean_rem)
        if v_rem > v_cur:
            return 1
        elif v_rem < v_cur:
            return -1
        return 0
    except Exception:
        # Fallback to simple tuple comparison if packaging fails
        def to_tuple(v: str) -> tuple[int, ...]:
            parts = []
            for token in v.split("."):
                num = "".join(filter(str.isdigit, token))
                parts.append(int(num) if num else 0)
            return tuple(parts)

        t_cur = to_tuple(clean_cur)
        t_rem = to_tuple(clean_rem)
        if t_rem > t_cur:
            return 1
        elif t_rem < t_cur:
            return -1
        return 0


class UpdateCheckWorker(QThread):
    """Background worker thread to query GitHub Releases API."""

    check_completed = Signal(bool, object)  # (has_update, VersionInfo)
    check_failed = Signal(str)  # (error_message)

    def __init__(
        self,
        current_version: str,
        api_url: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.current_version = current_version
        self.api_url = api_url or DEFAULT_RELEASES_API

    def run(self) -> None:
        """Fetch release information from GitHub without blocking UI thread."""
        req = urllib.request.Request(
            self.api_url,
            headers={
                "User-Agent": "ATBOffice-Updater",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            tag_name = data.get("tag_name", "")
            remote_ver = tag_name.lstrip("vV") if tag_name else "0.0.0"
            info = VersionInfo(
                version=remote_ver,
                tag_name=tag_name,
                name=data.get("name", f"ATBOffice {tag_name}"),
                body=data.get("body", ""),
                html_url=data.get(
                    "html_url", "https://github.com/aitobox/ATBOffice/releases"
                ),
                published_at=data.get("published_at", ""),
            )

            has_update = compare_versions(self.current_version, remote_ver) > 0
            self.check_completed.emit(has_update, info)

        except (HTTPError, URLError, TimeoutError) as e:
            self.check_failed.emit(
                safe_tr("网络连接失败，请检查网络设置: {err}").format(err=str(e))
            )
        except Exception as e:
            self.check_failed.emit(
                safe_tr("检查更新出错: {err}").format(err=str(e))
            )


class UpdateDialog(QDialog):
    """Dialog displaying new release information and download action."""

    def __init__(
        self,
        info: VersionInfo,
        current_version: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.info = info
        self.current_version = current_version

        self.setWindowTitle(safe_tr("软件更新 — ATBOffice"))
        self.setMinimumSize(480, 360)
        self.resize(520, 400)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Title / Version header
        self.label_header = QLabel(f"<h3>{safe_tr('发现新版本 ATBOffice')}</h3>", self)
        layout.addWidget(self.label_header)

        self.label_version = QLabel(
            safe_tr("最新版本: v{new_ver}  (当前版本: v{cur_ver})").format(
                new_ver=self.info.version, cur_ver=self.current_version
            ),
            self,
        )
        self.label_version.setStyleSheet("font-weight: bold; color: #2e6bc6;")
        layout.addWidget(self.label_version)

        # Changelog / Release notes
        self.label_notes_title = QLabel(safe_tr("更新日志:"), self)
        layout.addWidget(self.label_notes_title)

        self.text_notes = QPlainTextEdit(self)
        self.text_notes.setReadOnly(True)
        self.text_notes.setPlainText(self.info.body or safe_tr("暂无详细更新日志。"))
        layout.addWidget(self.text_notes, stretch=1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_later = QPushButton(safe_tr("稍后提醒(&L)"), self)
        self.btn_later.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_later)

        self.btn_download = QPushButton(safe_tr("前往下载(&D)"), self)
        self.btn_download.setDefault(True)
        self.btn_download.setStyleSheet(
            "background-color: #2e6bc6; color: white; font-weight: bold; padding: 6px 14px;"
        )
        self.btn_download.clicked.connect(self._on_download_clicked)
        btn_layout.addWidget(self.btn_download)

        layout.addLayout(btn_layout)

    def _on_download_clicked(self) -> None:
        if self.info.html_url:
            QDesktopServices.openUrl(QUrl(self.info.html_url))
        self.accept()


# Module-level active worker reference to prevent Python garbage collection mid-flight
_active_worker: UpdateCheckWorker | None = None


def check_for_updates(
    parent: QWidget | None = None,
    manual: bool = True,
    api_url: str | None = None,
) -> None:
    """Trigger update check.

    If manual is True, shows feedback dialogs on up-to-date and failure.
    If manual is False (background check), silently ignores failures.
    """
    global _active_worker
    from atboffice import __version__

    worker = UpdateCheckWorker(current_version=__version__, api_url=api_url, parent=parent)
    _active_worker = worker

    def on_success(has_update: bool, info: VersionInfo) -> None:
        global _active_worker
        _active_worker = None
        if has_update:
            dlg = UpdateDialog(info=info, current_version=__version__, parent=parent)
            dlg.exec()
        elif manual:
            QMessageBox.information(
                parent,
                safe_tr("检查更新"),
                safe_tr("您使用的是最新版本 ATBOffice (v{ver})，暂无可用更新。").format(
                    ver=__version__
                ),
            )

    def on_error(err_msg: str) -> None:
        global _active_worker
        _active_worker = None
        if manual:
            QMessageBox.warning(
                parent,
                safe_tr("检查更新失败"),
                err_msg,
            )

    worker.check_completed.connect(on_success)
    worker.check_failed.connect(on_error)
    worker.start()
