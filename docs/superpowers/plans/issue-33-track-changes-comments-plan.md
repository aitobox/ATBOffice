# Implementation Plan: Issue #33 — Quire 审阅修订 (Track Changes) 与文字批注 (Comments)

## Context & Objectives
Implement the complete revision tracking, comment annotation, collision-free balloon layout, and reviewing pane/toolbar features for ATBOffice Quire module, matching `.vibeoffice/public/quire/js/review.js`.

---

## Tasks Breakdown (TDD Ordered)

### Task 1: Model Foundations (`properties.py` and `document.py`)
- Extend `RunProperties` in `src/atboffice/modules/writer/models/properties.py` with revision fields:
  - `ins: RevisionStamp | None = None`
  - `del_rev: RevisionStamp | None = None`
  - `chg: RevisionStamp | None = None`
- Extend `ParagraphProperties` with:
  - `chg: RevisionStamp | None = None`
- Extend `Paragraph` in `src/atboffice/modules/writer/models/document.py` with:
  - `mark_ins: RevisionStamp | None = None`
  - `mark_del: RevisionStamp | None = None`
- Verify backwards compatibility with existing documents.

### Task 2: Core Revision & Comment Engine (`src/atboffice/modules/writer/models/revision.py`)
- Implement:
  1. `RevisionStamp`, `RevisionItem`, `Comment`, `BalloonPlacement`.
  2. Palette and `author_color(author: str) -> str`.
  3. Tracking toggle: `is_tracking()`, `set_tracking()`, `toggle_tracking()`.
  4. Listing & queries: `list_revisions()`, `list_authors()`, `revision_at()`.
  5. Resolution: `accept_revision()`, `reject_revision()`, `accept_all_revisions()`, `reject_all_revisions()`.
  6. Comment lifecycle: `insert_comment()`, `delete_comment()`, `delete_all_comments()`, `edit_comment()`, `reply_comment()`, `comment_at()`, `comment_number()`, `list_comments()`.
  7. Sequential navigation: `navigate_revision(doc, cur_para, cur_offset, direction)`.
  8. Balloon stacking layout algorithm: `layout_balloons(items, page_top, page_bottom, min_gap)`.

### Task 3: Unit Tests (`tests/unit/writer/test_review.py`)
- Create comprehensive tests:
  - `test_track_changes_toggle_and_defaults()`
  - `test_author_colors_and_authors_list()`
  - `test_list_revisions_and_adjacent_run_merging()`
  - `test_accept_reject_insertions()`
  - `test_accept_reject_deletions()`
  - `test_accept_reject_formatting_changes()`
  - `test_accept_reject_paragraph_marks()`
  - `test_accept_reject_all()`
  - `test_comment_insertion_and_markers()`
  - `test_comment_reply_and_deletion_cascade()`
  - `test_comment_editing_and_numbering()`
  - `test_revision_and_comment_navigation()`
  - `test_balloon_collision_free_layout()`

### Task 4: UI Views (`src/atboffice/modules/writer/views/review_pane.py`)
- Implement:
  1. `ReviewPane`: Dockable/collapsible sidebar widget with stats, author filter, revisions & comments list, click-to-navigate, context actions.
  2. `ReviewToolbar`: Office 2003 styled toolbar with tracking toggle, display mode selector, next/previous buttons, accept/reject dropdowns, comment buttons, and pane toggle.
  3. `CommentBalloonWidget`: Renderable balloon card with connector line calculations.
  4. Complete i18n support: `safe_tr()` and `retranslate_ui()`.

### Task 5: Integration with `WriterView` & Module Exports
- Update `src/atboffice/modules/writer/views/__init__.py` and `src/atboffice/modules/writer/models/__init__.py`.
- Add ReviewPane and ReviewToolbar toggles into `WriterView` in `src/atboffice/modules/writer/view.py`.
- Ensure clean signal-slot connections between `ReviewPane`, `ReviewToolbar`, and `canvas_view`.

### Task 6: Full Verification & Code Quality
- Run `pytest tests/unit/writer/test_review.py -v`.
- Run full writer unit test suite: `pytest tests/unit/writer/ -v`.
- Verify zero regressions and code style adherence.
