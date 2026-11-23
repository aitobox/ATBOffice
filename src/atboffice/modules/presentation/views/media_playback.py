"""Real audio/video preview playback for media shapes on the editing canvas."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QUrl

try:  # QtMultimedia is optional (minimal Qt builds)
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
except ImportError:  # pragma: no cover - depends on the Qt build
    QMediaPlayer = None  # type: ignore[assignment,misc]
    QAudioOutput = None  # type: ignore[assignment,misc]


def multimedia_available() -> bool:
    return QMediaPlayer is not None


class MediaPlayback(QObject):
    """Plays a shape's embedded media; repaints ``on_change`` as the position moves."""

    def __init__(self, media_item: Any, on_change: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.media_item = media_item
        self._on_change = on_change
        self.player: Any = None
        self.audio: Any = None
        self.error = ""
        self._tmp: Path | None = None

    def on_change(self) -> None:
        import shiboken6

        owner = getattr(self._on_change, "__self__", None)
        if owner is not None and not shiboken6.isValid(owner):
            self.release()
            return
        self._on_change()

    def _source(self) -> QUrl | None:
        item = self.media_item
        data = getattr(item, "media_bytes", None)
        if data:
            if self._tmp is None:
                suffix = "." + (getattr(item, "extension", "") or "bin")
                fd, name = tempfile.mkstemp(prefix="atb_media_", suffix=suffix)
                with open(fd, "wb") as fh:
                    fh.write(data)
                self._tmp = Path(name)
            return QUrl.fromLocalFile(str(self._tmp))
        path = getattr(item, "media_path", "")
        if path and Path(path).exists():
            return QUrl.fromLocalFile(str(Path(path).resolve()))
        return None

    def _ensure_player(self) -> bool:
        if self.player is not None:
            return True
        if not multimedia_available():
            self.error = "unavailable"
            return False
        source = self._source()
        if source is None:
            self.error = "no-media"
            return False
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.positionChanged.connect(lambda _p: self.on_change())
        self.player.durationChanged.connect(lambda _d: self.on_change())
        self.player.errorOccurred.connect(self._on_error)
        self.player.setSource(source)
        return True

    def _on_error(self, *_args: Any) -> None:
        self.error = self.player.errorString() if self.player is not None else "error"
        self.on_change()

    def play(self) -> bool:
        if not self._ensure_player():
            return False
        self.player.play()
        return True

    def pause(self) -> None:
        if self.player is not None:
            self.player.pause()

    def stop(self) -> None:
        if self.player is not None:
            self.player.stop()

    def position(self) -> int:
        return int(self.player.position()) if self.player is not None else 0

    def duration(self) -> int:
        return int(self.player.duration()) if self.player is not None else 0

    def fraction(self) -> float:
        dur = self.duration()
        return max(0.0, min(1.0, self.position() / dur)) if dur > 0 else 0.0

    def release(self) -> None:
        if self.player is not None:
            self.player.stop()
            self.player.setSource(QUrl())
        if self._tmp is not None:
            self._tmp.unlink(missing_ok=True)
            self._tmp = None


def fmt_ms(ms: int) -> str:
    s = max(0, ms) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"
