"""Asynchronous update checker for ATBOffice based on GitHub Releases API."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from urllib.error import HTTPError, URLError

import shiboken6
from packaging import version
from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal
from PySide6.QtWidgets import (
    QMessageBox,
    QWidget,
)

from atboffice.core.i18n import safe_tr
from atboffice.ui.dialogs.update_dialog import UpdateDialog

DEFAULT_RELEASES_API = "https://api.github.com/repos/aitobox/ATBOffice/releases/latest"

#: Seconds the release request may take; quitting waits at most a little longer.
REQUEST_TIMEOUT_S = 5.0


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
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if self.isInterruptionRequested():
                return

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
            if self.isInterruptionRequested():
                return
            self.check_failed.emit(
                safe_tr("网络连接失败，请检查网络设置: {err}").format(err=str(e))
            )
        except Exception as e:
            self.check_failed.emit(
                safe_tr("检查更新出错: {err}").format(err=str(e))
            )


# Running checks. The workers have no Qt parent, so closing the window that
# started a check can't destroy a thread that is still running; they are
# released when they finish, and waited for when the application quits.
_active_workers: set[UpdateCheckWorker] = set()
_quit_hook_installed = False


def _release_worker(worker: UpdateCheckWorker) -> None:
    _active_workers.discard(worker)
    worker.deleteLater()


def stop_update_checks(timeout_s: float = REQUEST_TIMEOUT_S + 1.0) -> None:
    """Ask running checks to stop and wait for their threads to end."""
    for worker in list(_active_workers):
        worker.requestInterruption()
        worker.wait(int(timeout_s * 1000))
        _active_workers.discard(worker)


def _install_quit_hook() -> None:
    global _quit_hook_installed
    app = QCoreApplication.instance()
    if app is None or _quit_hook_installed:
        return
    app.aboutToQuit.connect(stop_update_checks)
    _quit_hook_installed = True


def _alive(widget: QWidget | None) -> QWidget | None:
    """``widget`` if it still exists (the window may have closed meanwhile)."""
    return widget if widget is not None and shiboken6.isValid(widget) else None


def check_for_updates(
    parent: QWidget | None = None,
    manual: bool = True,
    api_url: str | None = None,
) -> None:
    """Trigger update check.

    If manual is True, shows feedback dialogs on up-to-date and failure.
    If manual is False (background check), silently ignores failures.
    """
    from atboffice import __version__

    worker = UpdateCheckWorker(current_version=__version__, api_url=api_url)
    _active_workers.add(worker)
    _install_quit_hook()

    def on_success(has_update: bool, info: VersionInfo) -> None:
        owner = _alive(parent)
        if has_update:
            dlg = UpdateDialog(info=info, current_version=__version__, parent=owner)
            dlg.exec()
        elif manual:
            QMessageBox.information(
                owner,
                safe_tr("检查更新"),
                safe_tr("您使用的是最新版本 ATBOffice (v{ver})，暂无可用更新。").format(
                    ver=__version__
                ),
            )

    def on_error(err_msg: str) -> None:
        if manual:
            QMessageBox.warning(_alive(parent), safe_tr("检查更新失败"), err_msg)

    worker.check_completed.connect(on_success)
    worker.check_failed.connect(on_error)
    worker.finished.connect(lambda: _release_worker(worker))
    worker.start()
