"""Multimedia item and playback settings model for Lectern."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from typing import Any

MEDIA_MIME_TYPES: dict[str, str] = {
    "mp4": "video/mp4",
    "m4v": "video/mp4",
    "avi": "video/x-msvideo",
    "wmv": "video/x-ms-wmv",
    "mov": "video/quicktime",
    "mkv": "video/x-matroska",
    "webm": "video/webm",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "wma": "audio/x-ms-wma",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
    "mid": "audio/midi",
    "midi": "audio/midi",
}


def guess_media_content_type(file_or_part_name: str, default: str = "video/mp4") -> str:
    """Infer media MIME content type from filename or part path."""
    ext = file_or_part_name.rsplit(".", 1)[-1].lower() if "." in file_or_part_name else ""
    return MEDIA_MIME_TYPES.get(ext, default)


def is_audio_extension(ext: str) -> bool:
    """Check if file extension corresponds to an audio format."""
    ext_clean = ext.lower().lstrip(".")
    return ext_clean in {"mp3", "wav", "wma", "m4a", "aac", "ogg", "flac", "mid", "midi"}


def is_video_extension(ext: str) -> bool:
    """Check if file extension corresponds to a video format."""
    ext_clean = ext.lower().lstrip(".")
    return ext_clean in {"mp4", "m4v", "avi", "wmv", "mov", "mkv", "webm"}


@dataclass
class PlaybackSettings:
    """Playback options and timing configuration for media elements."""

    auto_play: bool = False
    loop: bool = False
    volume: float = 0.8  # 0.0 to 1.0 (PresentationML 0 to 100000)
    hide_while_not_playing: bool = False
    rewind: bool = True
    play_across_slides: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "autoPlay": self.auto_play,
            "loop": self.loop,
            "vol": round(self.volume, 2),
            "hideWhenStopped": self.hide_while_not_playing,
            "rewind": self.rewind,
            "playAcrossSlides": self.play_across_slides,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PlaybackSettings:
        if not data:
            return cls()
        return cls(
            auto_play=bool(data.get("autoPlay", False)),
            loop=bool(data.get("loop", False)),
            volume=float(data.get("vol", 0.8)),
            hide_while_not_playing=bool(
                data.get("hideWhenStopped", data.get("hide_while_not_playing", False))
            ),
            rewind=bool(data.get("rewind", True)),
            play_across_slides=bool(
                data.get("playAcrossSlides", data.get("play_across_slides", False))
            ),
        )


@dataclass
class MediaItem:
    """Represents an embedded video or audio asset in a slide."""

    media_type: str = "video"  # "video" or "audio"
    media_path: str = ""  # e.g. "ppt/media/media1.mp4"
    content_type: str = "video/mp4"
    media_bytes: bytes | None = None
    poster_path: str | None = None  # e.g. "ppt/media/image1.png"
    poster_bytes: bytes | None = None
    playback: PlaybackSettings = field(default_factory=PlaybackSettings)
    original_element: str = "videoFile"  # "videoFile", "audioFile", "p14:media"

    def __post_init__(self) -> None:
        if not self.content_type and self.media_path:
            self.content_type = guess_media_content_type(self.media_path)
        if not self.media_type:
            ext = self.extension
            self.media_type = "audio" if is_audio_extension(ext) else "video"

    @property
    def is_video(self) -> bool:
        return self.media_type == "video"

    @property
    def is_audio(self) -> bool:
        return self.media_type == "audio"

    @property
    def extension(self) -> str:
        if "." in self.media_path:
            return self.media_path.rsplit(".", 1)[-1].lower()
        return "mp4" if self.is_video else "mp3"

    @property
    def file_name(self) -> str:
        return posixpath.basename(self.media_path) if self.media_path else f"media.{self.extension}"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.media_type,
            "path": self.media_path,
            "contentType": self.content_type,
            "playback": self.playback.to_dict(),
            "origEl": self.original_element,
        }
        if self.poster_path:
            d["posterPath"] = self.poster_path
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MediaItem | None:
        if not data:
            return None
        m_type = data.get("type", "video")
        m_path = data.get("path", "")
        c_type = data.get("contentType", guess_media_content_type(m_path))
        playback = PlaybackSettings.from_dict(data.get("playback"))
        poster_path = data.get("posterPath")
        orig_el = data.get("origEl", "videoFile" if m_type == "video" else "audioFile")
        return cls(
            media_type=m_type,
            media_path=m_path,
            content_type=c_type,
            poster_path=poster_path,
            playback=playback,
            original_element=orig_el,
        )
