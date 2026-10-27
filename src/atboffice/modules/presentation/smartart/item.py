"""SmartArt item data models and outline tree manipulation operations."""

from __future__ import annotations

import copy
import itertools
import time
from dataclasses import dataclass, field
from typing import Any

_seq = itertools.count(1)


def new_id() -> str:
    """Generate a unique item ID (e.g., 'i' + hex timestamp + sequence)."""
    ts = int(time.time() * 1000)
    return f"i{ts:x}{next(_seq):x}"


@dataclass
class SmartArtItem:
    """A node in the SmartArt outline hierarchy."""

    id: str
    text: str = ""
    kids: list[SmartArtItem] = field(default_factory=list)
    fmt: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize SmartArtItem to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "kids": [k.to_dict() if isinstance(k, SmartArtItem) else k for k in self.kids],
            "fmt": copy.deepcopy(self.fmt),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SmartArtItem:
        """Construct SmartArtItem from dictionary."""
        kids = [cls.from_dict(k) if isinstance(k, dict) else k for k in data.get("kids", [])]
        return cls(
            id=str(data.get("id", new_id())),
            text=str(data.get("text", "")),
            kids=kids,
            fmt=copy.deepcopy(data.get("fmt", {})),
        )


def outline(items: list[SmartArtItem]) -> list[dict[str, Any]]:
    """Flatten tree into depth-first outline list: [{item, level, parent}]."""
    out: list[dict[str, Any]] = []

    def _walk(item_list: list[SmartArtItem], level: int, parent: SmartArtItem | None) -> None:
        for it in item_list:
            out.append({"item": it, "level": level, "parent": parent})
            if it.kids:
                _walk(it.kids, level + 1, it)

    _walk(items, 0, None)
    return out


def locate(items: list[SmartArtItem], item_id: str) -> dict[str, Any] | None:
    """Locate item in tree. Return {item, parent, list, index} or None."""

    def _find(item_list: list[SmartArtItem], parent: SmartArtItem | None) -> dict[str, Any] | None:
        for idx, it in enumerate(item_list):
            if it.id == item_id:
                return {"item": it, "parent": parent, "list": item_list, "index": idx}
            if it.kids:
                res = _find(it.kids, it)
                if res is not None:
                    return res
        return None

    return _find(items, None)


def blank(layout_id: str, n: int | None = None) -> list[SmartArtItem]:
    """Generate blank outline items for a fresh diagram of given layout."""
    if layout_id in ("orgChart", "hierarchy", "hHierarchy"):
        top = SmartArtItem(
            id=new_id(),
            text="",
            kids=[
                SmartArtItem(id=new_id(), text=""),
                SmartArtItem(id=new_id(), text=""),
                SmartArtItem(id=new_id(), text=""),
            ],
        )
        return [top]

    if layout_id == "radial":
        centre = SmartArtItem(
            id=new_id(),
            text="",
            kids=[
                SmartArtItem(id=new_id(), text=""),
                SmartArtItem(id=new_id(), text=""),
                SmartArtItem(id=new_id(), text=""),
                SmartArtItem(id=new_id(), text=""),
            ],
        )
        return [centre]

    count = (
        n
        if n is not None
        else (3 if layout_id in ("venn", "target") else (5 if layout_id == "cycle" else 3))
    )
    return [SmartArtItem(id=new_id(), text="") for _ in range(count)]


def add_after(items: list[SmartArtItem], target_id: str, text: str = "") -> str:
    """Add a new item after target_id in the same level. Return new item id."""
    info = locate(items, target_id)
    new_item = SmartArtItem(id=new_id(), text=text)
    if info is not None:
        info["list"].insert(info["index"] + 1, new_item)
    else:
        items.append(new_item)
    return new_item.id


def add_before(items: list[SmartArtItem], target_id: str, text: str = "") -> str:
    """Add a new item before target_id in the same level. Return new item id."""
    info = locate(items, target_id)
    new_item = SmartArtItem(id=new_id(), text=text)
    if info is not None:
        info["list"].insert(info["index"], new_item)
    else:
        items.insert(0, new_item)
    return new_item.id


def add_below(items: list[SmartArtItem], target_id: str, text: str = "") -> str:
    """Add a child item under target_id. Return new item id."""
    info = locate(items, target_id)
    new_item = SmartArtItem(id=new_id(), text=text)
    if info is not None:
        info["item"].kids.append(new_item)
    return new_item.id


def add_above(items: list[SmartArtItem], target_id: str, text: str = "") -> str:
    """Add an item above target_id (at parent level or before target). Return new item id."""
    info = locate(items, target_id)
    new_item = SmartArtItem(id=new_id(), text=text)
    if info is not None and info["parent"] is not None:
        p_info = locate(items, info["parent"].id)
        if p_info is not None:
            p_info["list"].insert(p_info["index"] + 1, new_item)
            return new_item.id
    return add_before(items, target_id, text)


def demote(items: list[SmartArtItem], target_id: str) -> bool:
    """Demote target item into a child of its preceding sibling."""
    info = locate(items, target_id)
    if info is None or info["index"] == 0:
        return False
    lst = info["list"]
    idx = info["index"]
    item = lst.pop(idx)
    prev_sibling = lst[idx - 1]
    prev_sibling.kids.append(item)
    return True


def promote(items: list[SmartArtItem], target_id: str) -> bool:
    """Promote target item from child level to its parent's level."""
    info = locate(items, target_id)
    if info is None or info["parent"] is None:
        return False
    p_info = locate(items, info["parent"].id)
    if p_info is None:
        return False
    item = info["list"].pop(info["index"])
    p_info["list"].insert(p_info["index"] + 1, item)
    return True


def move_up(items: list[SmartArtItem], target_id: str) -> bool:
    """Swap target item with preceding sibling in same list."""
    info = locate(items, target_id)
    if info is None or info["index"] == 0:
        return False
    lst = info["list"]
    idx = info["index"]
    lst[idx - 1], lst[idx] = lst[idx], lst[idx - 1]
    return True


def move_down(items: list[SmartArtItem], target_id: str) -> bool:
    """Swap target item with succeeding sibling in same list."""
    info = locate(items, target_id)
    if info is None or info["index"] >= len(info["list"]) - 1:
        return False
    lst = info["list"]
    idx = info["index"]
    lst[idx], lst[idx + 1] = lst[idx + 1], lst[idx]
    return True


def remove_item(items: list[SmartArtItem], target_id: str) -> bool:
    """Remove target item from the tree."""
    info = locate(items, target_id)
    if info is None:
        return False
    info["list"].pop(info["index"])
    return True


def items_from_outline(lines: list[str]) -> list[SmartArtItem]:
    """Parse indented text lines into SmartArtItem tree."""
    roots: list[SmartArtItem] = []
    stack: list[tuple[int, SmartArtItem]] = []

    for raw_line in lines:
        if raw_line is None:
            continue
        stripped_right = raw_line.rstrip("\r\n")
        if not stripped_right.strip():
            continue

        # Count leading indentation (tab = 1 level, 4 spaces = 1 level)
        leading = len(raw_line) - len(raw_line.lstrip(" \t"))
        indent_str = raw_line[:leading]
        level = indent_str.count("\t") + (indent_str.count(" ") // 4)
        text = stripped_right.strip()

        item = SmartArtItem(id=new_id(), text=text)

        while stack and stack[-1][0] >= level:
            stack.pop()

        if not stack:
            roots.append(item)
        else:
            stack[-1][1].kids.append(item)

        stack.append((level, item))

    return roots
