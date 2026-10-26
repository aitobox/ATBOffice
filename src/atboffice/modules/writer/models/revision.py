"""Revision tracking (Track Changes), comments, and reviewing models for Quire."""

from __future__ import annotations

import copy
import datetime
from dataclasses import dataclass, field
from typing import Any

from atboffice.modules.writer.models.document import (
    CommentRangeEnd,
    CommentRangeStart,
    Document,
    Paragraph,
    RunItem,
    Story,
    Table,
    TextItem,
    all_stories,
    ilen,
    info,
    normalize,
    plain_text,
    plen,
    reindex,
    split_at,
)
from atboffice.modules.writer.models.properties import (
    ParagraphProperties,
    RevisionStamp,
    RunProperties,
)

# ---------------------------------------------------------------------------
# Author Colors (Deterministic Palette matching Word / Quire .vibeoffice)
# ---------------------------------------------------------------------------
AUTHOR_COLORS: list[str] = [
    "#C00000",  # Dark Red
    "#1F4FBF",  # Royal Blue
    "#2E8B37",  # Forest Green
    "#9B3FB0",  # Violet Purple
    "#C06000",  # Amber Orange
    "#008080",  # Deep Teal
    "#7F6000",  # Dark Olive
    "#B03060",  # Crimson Maroon
]

_known_authors: list[str] = []


def author_color(name: str | None) -> str:
    """Return a consistent color for the reviewer author name."""
    clean = (name or "Unknown").strip()
    if clean not in _known_authors:
        _known_authors.append(clean)
    idx = _known_authors.index(clean)
    return AUTHOR_COLORS[idx % len(AUTHOR_COLORS)]


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------
@dataclass
class RevisionItem:
    """A single revision entry in story order."""

    type: str  # "ins", "del", "chg", "pchg", "mins", "mdel"
    stamp: RevisionStamp
    para: Paragraph
    start: int
    end: int
    text: str = ""


class Comment:
    """Comment annotation container."""

    def __init__(
        self,
        id: str,
        author: str = "Author",
        initials: str = "",
        date: str = "",
        blocks: list[Paragraph] | None = None,
        paras: list[Paragraph] | None = None,
        parent: str | None = None,
        kind: str = "cmt",
        text: str = "",
    ) -> None:
        self.id = str(id)
        self.author = author
        self.initials = initials or (author[:2].upper() if author else "AU")
        self.date = (
            date
            or datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        )
        if blocks is not None:
            self.blocks = blocks
        elif text:
            self.blocks = [
                Paragraph(runs=[TextItem(text=line)])
                for line in text.split("\n")
            ]
        else:
            self.blocks = [Paragraph()]
        self.paras = paras or []
        self.parent = parent
        self.kind = kind

    @property
    def text(self) -> str:
        """Plain text content of the comment."""
        lines: list[str] = []
        for b in self.blocks:
            if isinstance(b, Paragraph):
                lines.append(plain_text(b))
        return "\n".join(lines)

    @text.setter
    def text(self, val: str) -> None:
        self.blocks = [
            Paragraph(runs=[TextItem(text=line)])
            for line in (val.split("\n") if val else [""])
        ]


@dataclass
class BalloonItem:
    """Input for balloon stacking layout."""

    id: str
    anchor_x: float
    anchor_y: float
    end_x: float = 0.0
    end_y: float = 0.0
    height: float = 60.0
    author: str = "Author"
    initials: str = ""
    date: str = ""
    text: str = ""
    reply: bool = False


@dataclass
class BalloonPlacement:
    """Position and connector geometry for a laid out comment balloon."""

    id: str
    y: float
    height: float
    color: str
    author: str
    initials: str
    date: str
    text: str
    reply: bool
    connector_lines: list[tuple[float, float, float, float]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tracking State Management
# ---------------------------------------------------------------------------
def is_tracking(doc: Document) -> bool:
    """Return whether Track Changes is active."""
    return bool(doc.settings.get("track", False))


def set_tracking(doc: Document, enabled: bool) -> None:
    """Enable or disable Track Changes."""
    doc.settings["track"] = bool(enabled)


def toggle_tracking(doc: Document) -> bool:
    """Toggle Track Changes state and return new state."""
    new_state = not is_tracking(doc)
    set_tracking(doc, new_state)
    return new_state


# ---------------------------------------------------------------------------
# Revision Listing & Inspection
# ---------------------------------------------------------------------------
def _rev_of_item(item: RunItem) -> tuple[str, RevisionStamp] | None:
    rp = getattr(item, "r_pr", None)
    if not rp:
        return None
    if rp.ins:
        return ("ins", rp.ins)
    if rp.del_rev:
        return ("del", rp.del_rev)
    if rp.chg:
        return ("chg", rp.chg)
    return None


def list_revisions(doc: Document, story: Story | None = None) -> list[RevisionItem]:
    """Return all tracked changes in story order, merging adjacent matching runs."""
    reindex(doc)
    st = story or doc.main
    out: list[RevisionItem] = []

    for p in st.paras:
        o = 0
        cur: RevisionItem | None = None
        for it in p.runs:
            n = ilen(it)
            rv = _rev_of_item(it) if n > 0 else None
            if (
                rv
                and cur
                and cur.type == rv[0]
                and cur.stamp.author == rv[1].author
                and cur.stamp.date == rv[1].date
                and cur.end == o
            ):
                cur.end = o + n
                cur.text += getattr(it, "text", " " if it.t == "tab" else "")
            elif rv:
                run_text = getattr(it, "text", "\t" if it.t == "tab" else "[object]")
                cur = RevisionItem(
                    type=rv[0],
                    stamp=rv[1],
                    para=p,
                    start=o,
                    end=o + n,
                    text=run_text,
                )
                out.append(cur)
            elif n > 0:
                cur = None
            o += n

        if p.p_pr.chg:
            out.append(
                RevisionItem(
                    type="pchg",
                    stamp=p.p_pr.chg,
                    para=p,
                    start=0,
                    end=plen(p),
                    text="Paragraph formatting",
                )
            )
        if p.mark_ins:
            out.append(
                RevisionItem(
                    type="mins",
                    stamp=p.mark_ins,
                    para=p,
                    start=plen(p),
                    end=plen(p),
                    text="¶",
                )
            )
        if p.mark_del:
            out.append(
                RevisionItem(
                    type="mdel",
                    stamp=p.mark_del,
                    para=p,
                    start=plen(p),
                    end=plen(p),
                    text="¶",
                )
            )

    return out


def list_authors(doc: Document) -> list[str]:
    """Return all unique authors who contributed revisions or comments."""
    authors: set[str] = set()
    for st in all_stories(doc):
        for r in list_revisions(doc, st):
            if r.stamp.author:
                authors.add(r.stamp.author)
    for c in doc.comments.values():
        if isinstance(c, Comment) and c.author:
            authors.add(c.author)
        elif isinstance(c, dict) and c.get("author"):
            authors.add(c["author"])
    return sorted(authors)


def revision_at(doc: Document, para: Paragraph, offset: int) -> RevisionItem | None:
    """Return the revision item at the specified position if one exists."""
    revs = list_revisions(doc)
    for r in revs:
        if r.para is para:
            if r.type in {"mins", "mdel"} and offset == r.start:
                return r
            if r.start <= offset < r.end:
                return r
    return None


# ---------------------------------------------------------------------------
# Revision Resolution (Accept / Reject)
# ---------------------------------------------------------------------------
def _join_with_next(doc: Document, p: Paragraph) -> None:
    inf = info(doc, p)
    if not inf:
        return
    cont = inf.get("cont")
    idx = inf.get("i", -1)
    if not cont or idx < 0:
        return
    blocks = getattr(cont, "blocks", [])
    if idx + 1 < len(blocks) and isinstance(blocks[idx + 1], Paragraph):
        next_p = blocks[idx + 1]
        p.runs.extend(next_p.runs)
        del blocks[idx + 1]
        normalize(p)
        doc._idx_dirty = True
        reindex(doc)


def resolve_revision(doc: Document, r: RevisionItem, accept: bool) -> None:
    """Accept or reject a single revision record."""
    p = r.para

    if r.type == "pchg":
        if accept:
            p.p_pr.chg = None
        else:
            old_data = r.stamp.old or {}
            # Restore previous paragraph formatting
            for k, v in old_data.items():
                if hasattr(p.p_pr, k):
                    setattr(p.p_pr, k, copy.deepcopy(v))
            p.p_pr.chg = None
        return

    if r.type in {"mins", "mdel"}:
        joining = (r.type == "mins" and not accept) or (r.type == "mdel" and accept)
        p.mark_ins = None
        p.mark_del = None
        if joining:
            _join_with_next(doc, p)
        return

    i0 = split_at(p, r.start)
    i1 = split_at(p, r.end)
    keep: list[RunItem] = []

    for i, it in enumerate(p.runs):
        if i < i0 or i >= i1 or ilen(it) == 0:
            keep.append(it)
            continue

        rp = it.r_pr
        if r.type == "ins":
            if accept:
                rp.ins = None
                keep.append(it)
            # If rejected, insertion disappears (not kept)
        elif r.type == "del":
            if not accept:
                rp.del_rev = None
                keep.append(it)
            # If accepted, deleted text disappears (not kept)
        elif r.type == "chg":
            if accept:
                rp.chg = None
            else:
                old = copy.deepcopy(r.stamp.old) if r.stamp.old else {}
                for k, v in old.items():
                    if hasattr(rp, k):
                        setattr(rp, k, copy.deepcopy(v))
                rp.chg = None
            keep.append(it)

    p.runs = keep
    if not p.runs:
        p.runs.append(TextItem(text=""))
    normalize(p)
    doc._idx_dirty = True


def accept_revision(doc: Document, r: RevisionItem) -> None:
    """Accept a tracked change."""
    resolve_revision(doc, r, accept=True)


def reject_revision(doc: Document, r: RevisionItem) -> None:
    """Reject a tracked change."""
    resolve_revision(doc, r, accept=False)


def accept_all_revisions(doc: Document, story: Story | None = None) -> int:
    """Accept all tracked revisions in story or document; return count resolved."""
    revs = list_revisions(doc, story)
    count = len(revs)
    # Process from bottom/end to beginning so offsets remain valid
    revs.sort(key=lambda r: (r.para._o, r.start), reverse=True)
    for r in revs:
        resolve_revision(doc, r, accept=True)
    return count


def reject_all_revisions(doc: Document, story: Story | None = None) -> int:
    """Reject all tracked revisions in story or document; return count resolved."""
    revs = list_revisions(doc, story)
    count = len(revs)
    revs.sort(key=lambda r: (r.para._o, r.start), reverse=True)
    for r in revs:
        resolve_revision(doc, r, accept=False)
    return count


# ---------------------------------------------------------------------------
# Comments Management
# ---------------------------------------------------------------------------
def insert_comment(
    doc: Document,
    start_pos: tuple[Paragraph, int],
    end_pos: tuple[Paragraph, int],
    text: str = "",
    author: str = "Author",
    initials: str = "",
) -> Comment:
    """Insert a new comment anchoring across start_pos to end_pos."""
    p_start, o_start = start_pos
    p_end, o_end = end_pos

    # Determine unique string ID
    cid = 0
    while str(cid) in doc.comments:
        cid += 1
    str_id = str(cid)

    # Insert end marker first so start offset remains stable
    i_end = split_at(p_end, o_end)
    p_end.runs.insert(i_end, CommentRangeEnd(comment_id=str_id))

    i_start = split_at(p_start, o_start)
    p_start.runs.insert(i_start, CommentRangeStart(comment_id=str_id))

    cmt = Comment(
        id=str_id,
        author=author,
        initials=initials or (author[:2].upper() if author else "AU"),
        blocks=[Paragraph(runs=[TextItem(text=text)]) if text else Paragraph()],
    )
    doc.comments[str_id] = cmt
    doc._idx_dirty = True
    return cmt


def delete_comment(doc: Document, comment_id: str) -> bool:
    """Delete comment by id and all its replies, removing markers from document."""
    str_id = str(comment_id)
    if str_id not in doc.comments:
        return False

    # Find replies
    kids = [k for k, c in doc.comments.items() if getattr(c, "parent", None) == str_id]
    to_delete = {str_id, *kids}

    for cid in to_delete:
        doc.comments.pop(cid, None)

    # Remove markers from document
    reindex(doc)
    for st in all_stories(doc):
        for b in getattr(st, "blocks", []):
            if isinstance(b, Paragraph):
                b.runs = [
                    it
                    for it in b.runs
                    if not (
                        isinstance(it, (CommentRangeStart, CommentRangeEnd))
                        and str(it.comment_id) in to_delete
                    )
                ]
                normalize(b)
        for para in getattr(st, "paras", []):
            para.runs = [
                it
                for it in para.runs
                if not (
                    isinstance(it, (CommentRangeStart, CommentRangeEnd))
                    and str(it.comment_id) in to_delete
                )
            ]
            normalize(para)

    doc._idx_dirty = True
    return True


def delete_all_comments(doc: Document) -> int:
    """Delete all comments and markers; returns count deleted."""
    count = len(doc.comments)
    doc.comments.clear()
    reindex(doc)
    for st in all_stories(doc):
        for b in getattr(st, "blocks", []):
            if isinstance(b, Paragraph):
                b.runs = [
                    it
                    for it in b.runs
                    if not isinstance(it, (CommentRangeStart, CommentRangeEnd))
                ]
                normalize(b)
        for p in getattr(st, "paras", []):
            p.runs = [
                it
                for it in p.runs
                if not isinstance(it, (CommentRangeStart, CommentRangeEnd))
            ]
            normalize(p)
    doc._idx_dirty = True
    return count


def edit_comment(doc: Document, comment_id: str, new_text: str) -> bool:
    """Update text of an existing comment."""
    str_id = str(comment_id)
    cmt = doc.comments.get(str_id)
    if not cmt:
        return False
    if isinstance(cmt, Comment):
        cmt.text = new_text
    elif isinstance(cmt, dict):
        cmt["text"] = new_text
    return True


def reply_comment(
    doc: Document,
    parent_id: str,
    text: str = "",
    author: str = "Author",
    initials: str = "",
) -> Comment | None:
    """Create a reply to an existing comment."""
    str_parent = str(parent_id)
    parent = doc.comments.get(str_parent)
    if not parent:
        return None

    cid = 0
    while str(cid) in doc.comments:
        cid += 1
    str_id = str(cid)

    # Reply shares parent's anchor range markers
    reply = Comment(
        id=str_id,
        author=author,
        initials=initials or (author[:2].upper() if author else "AU"),
        blocks=[Paragraph(runs=[TextItem(text=text)]) if text else Paragraph()],
        parent=str_parent,
    )
    doc.comments[str_id] = reply
    doc._idx_dirty = True
    return reply


def comment_at(doc: Document, para: Paragraph, offset: int) -> str | None:
    """Return active comment ID at paragraph offset, or None."""
    open_cids: set[str] = set()
    pos = 0
    for it in para.runs:
        if isinstance(it, CommentRangeStart):
            open_cids.add(str(it.comment_id))
        elif isinstance(it, CommentRangeEnd):
            open_cids.discard(str(it.comment_id))

        n = ilen(it)
        if pos <= offset < pos + n and open_cids:
            return next(iter(open_cids))
        pos += n

    return None


def comment_number(doc: Document, comment_id: str) -> int:
    """Return 1-based sequential number of comment in document reading order."""
    str_id = str(comment_id)
    found_ids: list[str] = []
    for p in doc.main.paras:
        for it in p.runs:
            if (
                isinstance(it, CommentRangeStart)
                and str(it.comment_id) in doc.comments
                and str(it.comment_id) not in found_ids
            ):
                found_ids.append(str(it.comment_id))
    try:
        return found_ids.index(str_id) + 1
    except ValueError:
        try:
            return int(str_id) + 1
        except ValueError:
            return 1


# ---------------------------------------------------------------------------
# Sequential Navigation (Previous / Next Revision or Comment)
# ---------------------------------------------------------------------------
@dataclass
class NavItem:
    """Unified navigation item."""

    para: Paragraph
    start: int
    end: int
    kind: str  # "rev" or "cmt"
    id: str | None = None
    rev: RevisionItem | None = None


def list_nav_items(doc: Document, story: Story | None = None) -> list[NavItem]:
    """Collect all revisions and comments in reading order for navigation."""
    reindex(doc)
    st = story or doc.main
    items: list[NavItem] = []

    for r in list_revisions(doc, st):
        items.append(
            NavItem(
                para=r.para,
                start=r.start,
                end=r.end,
                kind="rev",
                rev=r,
            )
        )

    for p in st.paras:
        o = 0
        for it in p.runs:
            if isinstance(it, CommentRangeStart) and str(it.comment_id) in doc.comments:
                items.append(
                    NavItem(
                        para=p,
                        start=o,
                        end=o,
                        kind="cmt",
                        id=str(it.comment_id),
                    )
                )
            o += ilen(it)

    items.sort(key=lambda x: (x.para._o, x.start))
    return items


def navigate_revision(
    doc: Document,
    cur_para: Paragraph,
    cur_offset: int,
    direction: int = 1,
) -> NavItem | None:
    """Move to next (direction=+1) or previous (direction=-1) revision/comment."""
    items = list_nav_items(doc)
    if not items:
        return None

    if direction > 0:
        for it in items:
            if it.para._o > cur_para._o or (
                it.para._o == cur_para._o and it.start > cur_offset
            ):
                return it
    else:
        for it in reversed(items):
            if it.para._o < cur_para._o or (
                it.para._o == cur_para._o and it.end < cur_offset
            ):
                return it

    return None


# ---------------------------------------------------------------------------
# Balloon Stacking Layout Algorithm
# ---------------------------------------------------------------------------
def layout_balloons(
    items: list[BalloonItem],
    page_top: float = 72.0,
    page_bottom: float = 720.0,
    min_gap: float = 6.0,
    page_width: float = 595.3,
) -> list[BalloonPlacement]:
    """Calculate non-overlapping vertical positions and connector lines for comment balloons."""
    sorted_items = sorted(items, key=lambda it: it.anchor_y)
    placements: list[BalloonPlacement] = []
    current_bottom = page_top

    for it in sorted_items:
        # Place balloon at max(anchor_y - 2, current_bottom + min_gap)
        y = max(it.anchor_y - 2.0, current_bottom + min_gap)
        color = author_color(it.author)

        # Connector geometry:
        # 1. Horizontal segment from anchor (or right margin) to balloon margin
        # 2. Vertical riser if y differs significantly from anchor_y
        connector: list[tuple[float, float, float, float]] = []
        anchor_y = it.anchor_y + 8.0
        balloon_y = y + 10.0

        connector.append((it.anchor_x, anchor_y, page_width - 10.0, anchor_y))
        if abs(anchor_y - balloon_y) > 2.0:
            connector.append((page_width - 10.0, min(anchor_y, balloon_y), page_width - 10.0, max(anchor_y, balloon_y)))
            connector.append((page_width - 10.0, balloon_y, page_width + 4.0, balloon_y))

        placements.append(
            BalloonPlacement(
                id=it.id,
                y=y,
                height=it.height,
                color=color,
                author=it.author,
                initials=it.initials,
                date=it.date,
                text=it.text,
                reply=it.reply,
                connector_lines=connector,
            )
        )
        current_bottom = y + it.height

    return placements
