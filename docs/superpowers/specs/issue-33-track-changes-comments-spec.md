# Specification: Issue #33 — Quire 审阅修订 (Track Changes) 与文字批注 (Comments)

## 1. Overview & Context

- **Issue**: [#33 [Quire] 审阅修订 (Track Changes) 与文字批注 (Comments)](https://github.com/aitobox/ATBOffice/issues/33)
- **Parent Epic**: #22 (`[Epic] ATBOffice Quire (Word 2003) 文字处理与分页排版引擎完整移植`)
- **Sequence**: Step 11 of 15
- **Reference Implementation**: `.vibeoffice/public/quire/js/review.js` and `.vibeoffice/public/quire/js/render.js`

This feature implements the complete Word 2003 / Quire document reviewing and collaboration engine in pure Python / PySide6, covering:
1. **Track Changes (修订追踪)**: Toggle tracking state, record insertions, deletions, character formatting changes, and paragraph break changes with author metadata and timestamps.
2. **Revision Resolution & Navigation (接受/拒绝与导航)**: Accept or reject individual or all revisions, navigate between revisions sequentially.
3. **Comments (批注)**: Anchor comments to specific character ranges (`CommentRangeStart` / `CommentRangeEnd`), support reply threads, author initials, dates, and plain/rich text blocks.
4. **Collision-free Balloon Layout (气泡自适应排版)**: Calculate vertical positioning for page-margin comment balloons ensuring zero visual overlap via a stacking layout algorithm.
5. **Reviewing Pane & Toolbar (审阅窗格与审阅工具栏)**: Word 2003 styled docking side/bottom pane and reviewing toolbar with full internationalization (`safe_tr`, `retranslate_ui`).

---

## 2. Architecture & Data Model

### 2.1 Revisions Data Model (`src/atboffice/modules/writer/models/revision.py`)

#### Revision Stamp
```python
@dataclass
class RevisionStamp:
    author: str = "Author"
    date: str = ""  # ISO 8601 string, e.g. "2026-10-26T12:00:00Z"
    id: int = 0
    old: dict[str, Any] = field(default_factory=dict)
```

#### Revision Types
- `ins`: Inline run insertion (rendered with underline and reviewer color).
- `del`: Inline run deletion (rendered with strikethrough and reviewer color).
- `chg`: Inline run formatting change (with `old` formatting in stamp).
- `pchg`: Paragraph property formatting change (with `old` p_pr in stamp).
- `mins`: Paragraph mark insertion (¶ insertion).
- `mdel`: Paragraph mark deletion (¶ deletion).

#### Revision Item
```python
@dataclass
class RevisionItem:
    type: str  # 'ins', 'del', 'chg', 'pchg', 'mins', 'mdel'
    stamp: RevisionStamp
    para: Paragraph
    start: int
    end: int
    text: str = ""
```

#### Document & Properties Extensions
- `RunProperties`: Add optional fields `ins: RevisionStamp | None = None`, `del_rev: RevisionStamp | None = None` (or `del`), `chg: RevisionStamp | None = None`.
- `ParagraphProperties`: Add optional field `chg: RevisionStamp | None = None`.
- `Paragraph`: Add optional fields `mark_ins: RevisionStamp | None = None`, `mark_del: RevisionStamp | None = None`.
- `Document`: Already contains `settings: dict[str, Any]` (where `settings["track"]` records boolean tracking state) and `comments: dict[str, Story | Comment]`.

### 2.2 Author Colors
Deterministic palette matching `.vibeoffice/public/quire/js/render.js`:
```python
AUTHOR_COLORS: list[str] = [
    "#C00000",  # Red
    "#1F4FBF",  # Blue
    "#2E8B37",  # Green
    "#9B3FB0",  # Purple
    "#C06000",  # Orange
    "#008080",  # Teal
    "#7F6000",  # Olive
    "#B03060",  # Maroon
]
```

`author_color(author: str) -> str` uses a registry or deterministic hash to return consistent colors across revisions and comment markers.

### 2.3 Comments Data Model
```python
@dataclass
class Comment:
    id: str
    author: str = "Author"
    initials: str = ""
    date: str = ""
    blocks: list[Paragraph] = field(default_factory=lambda: [Paragraph()])
    parent: str | None = None  # None for top-level, or parent comment ID for replies
```

- Anchored in document body via `CommentRangeStart(comment_id=id)` and `CommentRangeEnd(comment_id=id)` inline run markers.
- Stored in `doc.comments[str(id)]`.

### 2.4 Balloon Stacking Layout Algorithm
Given page height and a list of comments on that page with their target anchor Y positions:
```python
def layout_balloons(
    items: list[BalloonItem],
    page_top: float = 0.0,
    page_bottom: float = 841.9,
    min_gap: float = 6.0,
) -> list[BalloonPlacement]:
```
1. Sort balloons in anchor Y ascending order (matching reading order).
2. For each balloon: `y = max(item.anchor_y - 2, current_bottom + min_gap)`.
3. Track `current_bottom = y + item.height`.
4. If bottom exceeds page_bottom, shift upwards without overlapping earlier items where space permits.
5. Generate connector line coordinates from anchor point `(lx, ly)` to the balloon left edge `(bx, by)`.

---

## 3. UI Views (`src/atboffice/modules/writer/views/review_pane.py`)

### 3.1 Reviewing Pane (`ReviewPane`)
- Standard Word 2003 docking side pane:
  - Header: Label "Reviewing Pane" / "审阅窗格", Close button (`✕`).
  - Stats: Total revisions count, total comments count.
  - Reviewer Filter: Combobox with "All Reviewers" / "所有审阅者" and individual reviewer names.
  - Scrollable list of revision & comment cards:
    - Revision Card: Colored author indicator, action type (Inserted, Deleted, Formatted), author name, date/time, content snippet.
    - Comment Card: Colored author indicator, `Comment [Author#]`, author name, date/time, comment text body, reply indicator.
  - Action Context Menu / Toolbar on selection:
    - Accept Revision
    - Reject Revision
    - Delete Comment
    - Reply to Comment
  - Double click comment item opens comment editing dialog.
  - Single click focuses the corresponding paragraph/offset in the document.

### 3.2 Reviewing Toolbar (`ReviewToolbar`)
- Standard Office 2003 styled toolbar:
  - Track Changes toggle button with checked state.
  - Display for Review dropdown (Final Showing Markup, Final, Original Showing Markup, Original).
  - Show markup dropdown (Comments, Revisions).
  - Previous Revision / Next Revision navigation buttons.
  - Accept Change / Accept All Changes dropdown button.
  - Reject Change / Reject All Changes dropdown button.
  - New Comment button.
  - Delete Comment / Delete All Comments dropdown button.
  - Reviewing Pane toggle button.

### 3.3 Balloon Overlay View (`CommentBalloonOverlay`)
- Canvas overlay component displaying balloons on the right margin of the document page.
- Renders connector lines (dashed with author color) from text selection to balloon.
- Interactive: clicking balloon highlights comment and activates inline editor.

---

## 4. Internationalization (i18n) & Edge Cases

- 100% of UI strings wrapped with `safe_tr(text)`:
  - English and Chinese translations for all buttons, menus, tooltips, dialogs, and status labels.
- `retranslate_ui()` implemented on all view widgets.
- Edge cases handled:
  - Empty document or zero revisions/comments (clean empty-state message).
  - Adjacent runs with same revision merged into single logical revision.
  - Rejecting insertion properly removes run and normalizes paragraph.
  - Accepting deletion properly removes run and normalizes paragraph.
  - Nested comments and comment deletions cascading to replies.
  - Document boundary handling in previous/next revision navigation.

---

## 5. Verification Plan

- Unit test suite in `tests/unit/writer/test_review.py`:
  1. Tracking toggle and state verification.
  2. Revision listing, merging of adjacent runs, and author color extraction.
  3. Accept / Reject for `ins`, `del`, `chg`, `mins`, `mdel`, and accept/reject all.
  4. Comment insertion, anchoring `cs`/`ce`, editing, replying, and deletion cascade.
  5. Sequential revision and comment navigation (next / previous / boundary).
  6. Balloon layout non-overlapping stacking coordinates calculation.
  7. ReviewPane and ReviewToolbar widget lifecycle, signal emission, and i18n retranslation.
