"""Asynchronous update checker for ATBOffice based on GitHub Releases API."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from urllib.error import HTTPError, URLError

from packaging import version
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QWidget,
)

from atboffice.ui.dialogs.update_dialog import UpdateDialog


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
