"""Slide comment and author models for Lectern presentations."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any


def format_iso_timestamp(dt: datetime.datetime | None = None) -> str:
    """Format a datetime in ISO 8601 UTC representation (e.g. 2026-10-27T12:00:00Z)."""
    if dt is None:
        dt = datetime.datetime.now(datetime.UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_relative_time(iso_str: str) -> str:
    """Format an ISO 8601 timestamp into a readable relative time string."""
    if not iso_str:
        return "刚刚"
    try:
        clean_iso = iso_str.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(clean_iso)
        now = datetime.datetime.now(datetime.UTC)
        diff = (now - dt).total_seconds()
        if diff < 60:
            return "刚刚"
        if diff < 3600:
            return f"{int(diff // 60)} 分钟前"
        if diff < 86400:
            return f"{int(diff // 3600)} 小时前"
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str[:10] if len(iso_str) >= 10 else iso_str


def extract_initials(name: str) -> str:
    """Extract 1-2 character uppercase initials from an author name."""
    parts = [p.strip() for p in name.split() if p.strip()]
    if not parts:
        return "A"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


@dataclass
class CommentAuthor:
    """Comment author metadata representing a reviewer or editor."""

    id: str
    name: str
    initials: str = ""
    last_idx: int = 0
    color_idx: int = 0
    user_id: str = ""
    provider_id: str = ""

    def __post_init__(self) -> None:
        if not self.initials and self.name:
            self.initials = extract_initials(self.name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "initials": self.initials,
            "lastIdx": self.last_idx,
            "colorIdx": self.color_idx,
            "userId": self.user_id,
            "providerId": self.provider_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CommentAuthor:
        if not data:
            return cls(id=str(uuid.uuid4()), name="Author")
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "Author")),
            initials=str(data.get("initials", "")),
            last_idx=int(data.get("lastIdx", data.get("last_idx", 0))),
            color_idx=int(data.get("colorIdx", data.get("color_idx", 0))),
            user_id=str(data.get("userId", data.get("user_id", ""))),
            provider_id=str(data.get("providerId", data.get("provider_id", ""))),
        )


@dataclass
class CommentReply:
    """A reply thread message attached to a modern comment."""

    id: str
    author_id: str
    created: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "authorId": self.author_id,
            "created": self.created,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CommentReply:
        if not data:
            return cls(
                id=str(uuid.uuid4()),
                author_id="",
                created=format_iso_timestamp(),
                text="",
            )
        return cls(
            id=str(data.get("id", uuid.uuid4().hex)),
            author_id=str(data.get("authorId", data.get("author_id", ""))),
            created=str(data.get("created", format_iso_timestamp())),
            text=str(data.get("text", "")),
        )


@dataclass
class Comment:
    """Individual slide comment positioned on the canvas or anchored to a shape."""

    id: str
    author_id: str
    text: str
    x: float = 20.0
    y: float = 20.0
    idx: int = 1
    created: str = field(default_factory=format_iso_timestamp)
    shape_id: str | None = None
    status: str = "active"  # "active" or "resolved"
    replies: list[CommentReply] = field(default_factory=list)
    is_modern: bool = False

    def add_reply(self, author_id: str, text: str) -> CommentReply:
        """Append a reply to this comment thread."""
        reply = CommentReply(
            id=f"rep_{uuid.uuid4().hex[:8]}",
            author_id=author_id,
            created=format_iso_timestamp(),
            text=text,
        )
        self.replies.append(reply)
        return reply

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "authorId": self.author_id,
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "idx": self.idx,
            "created": self.created,
            "status": self.status,
            "isModern": self.is_modern,
        }
        if self.shape_id:
            d["shapeId"] = self.shape_id
        if self.replies:
            d["replies"] = [r.to_dict() for r in self.replies]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Comment:
        if not data:
            return cls(
                id=f"cm_{uuid.uuid4().hex[:8]}",
                author_id="",
                text="",
            )
        replies_raw = data.get("replies", [])
        replies = [CommentReply.from_dict(r) for r in replies_raw]
        return cls(
            id=str(data.get("id", f"cm_{uuid.uuid4().hex[:8]}")),
            author_id=str(data.get("authorId", data.get("author_id", ""))),
            text=str(data.get("text", "")),
            x=float(data.get("x", 20.0)),
            y=float(data.get("y", 20.0)),
            idx=int(data.get("idx", 1)),
            created=str(data.get("created", format_iso_timestamp())),
            shape_id=str(data["shapeId"]) if "shapeId" in data else data.get("shape_id"),
            status=str(data.get("status", "active")),
            replies=replies,
            is_modern=bool(data.get("isModern", data.get("is_modern", False))),
        )
