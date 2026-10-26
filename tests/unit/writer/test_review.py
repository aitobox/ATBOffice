"""Unit tests for Quire Track Changes (revisions), comments, balloon layout, and reviewing UI."""

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.models.document import (
    CommentRangeEnd,
    CommentRangeStart,
    Document,
    Paragraph,
    TextItem,
    plain_text,
    reindex,
)
from atboffice.modules.writer.models.properties import (
    RevisionStamp,
    RunProperties,
)
from atboffice.modules.writer.models.revision import (
    BalloonItem,
    BalloonPlacement,
    Comment,
    accept_all_revisions,
    accept_revision,
    author_color,
    comment_at,
    comment_number,
    delete_all_comments,
    delete_comment,
    edit_comment,
    insert_comment,
    is_tracking,
    layout_balloons,
    list_authors,
    list_revisions,
    navigate_revision,
    reject_all_revisions,
    reject_revision,
    reply_comment,
    revision_at,
    set_tracking,
    toggle_tracking,
)
from atboffice.modules.writer.views.review_pane import (
    CommentBalloonWidget,
    ReviewPane,
    ReviewToolbar,
    safe_tr,
)


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QCoreApplication / QApplication exists for GUI widget tests."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


# ===========================================================================
# 1. Tracking State & Defaults
# ===========================================================================
def test_track_changes_toggle_and_defaults():
    doc = Document()
    assert is_tracking(doc) is False

    set_tracking(doc, True)
    assert is_tracking(doc) is True

    new_val = toggle_tracking(doc)
    assert new_val is False
    assert is_tracking(doc) is False

    new_val = toggle_tracking(doc)
    assert new_val is True
    assert is_tracking(doc) is True


# ===========================================================================
# 2. Author Colors & Author Listing
# ===========================================================================
def test_author_colors_and_authors_list():
    c1 = author_color("Alice")
    c2 = author_color("Bob")
    assert c1.startswith("#")
    assert c2.startswith("#")
    assert c1 == author_color("Alice")  # Deterministic

    doc = Document()
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    p.runs = [
        TextItem(
            text="Hello ",
            r_pr=RunProperties(ins=RevisionStamp(author="Alice", date="2026-10-26T12:00:00Z")),
        ),
        TextItem(
            text="world",
            r_pr=RunProperties(del_rev=RevisionStamp(author="Bob", date="2026-10-26T12:00:00Z")),
        ),
    ]
    doc.comments["1"] = Comment(id="1", author="Charlie", text="Check this")

    authors = list_authors(doc)
    assert "Alice" in authors
    assert "Bob" in authors
    assert "Charlie" in authors


# ===========================================================================
# 3. Revision Listing & Adjacent Run Merging
# ===========================================================================
def test_list_revisions_and_adjacent_run_merging():
    doc = Document()
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)

    stamp = RevisionStamp(author="Alice", date="2026-10-26T10:00:00Z")
    # Two adjacent runs with identical insertion revision
    p.runs = [
        TextItem(text="Hello ", r_pr=RunProperties(ins=stamp)),
        TextItem(text="beautiful ", r_pr=RunProperties(ins=stamp)),
        TextItem(text="world", r_pr=RunProperties()),
    ]

    revs = list_revisions(doc)
    assert len(revs) == 1
    r = revs[0]
    assert r.type == "ins"
    assert r.stamp.author == "Alice"
    assert r.start == 0
    assert r.end == len("Hello beautiful ")
    assert r.text == "Hello beautiful "

    # Check revision_at query
    hit = revision_at(doc, p, 3)
    assert hit is not None
    assert hit.type == "ins"

    miss = revision_at(doc, p, 20)
    assert miss is None


# ===========================================================================
# 4. Accept / Reject Insertions
# ===========================================================================
def test_accept_reject_insertions():
    # Case A: Accept insertion
    doc = Document()
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    stamp = RevisionStamp(author="Alice")
    p.runs = [
        TextItem(text="Existing "),
        TextItem(text="inserted ", r_pr=RunProperties(ins=stamp)),
        TextItem(text="tail"),
    ]
    revs = list_revisions(doc)
    assert len(revs) == 1

    accept_revision(doc, revs[0])
    assert len(list_revisions(doc)) == 0
    assert plain_text(p) == "Existing inserted tail"
    # ins stamp cleared from runs
    for it in p.runs:
        assert getattr(it.r_pr, "ins", None) is None

    # Case B: Reject insertion
    doc2 = Document()
    p2 = doc2.main.blocks[0]
    assert isinstance(p2, Paragraph)
    p2.runs = [
        TextItem(text="Existing "),
        TextItem(text="inserted ", r_pr=RunProperties(ins=stamp)),
        TextItem(text="tail"),
    ]
    revs2 = list_revisions(doc2)
    reject_revision(doc2, revs2[0])
    assert len(list_revisions(doc2)) == 0
    assert plain_text(p2) == "Existing tail"


# ===========================================================================
# 5. Accept / Reject Deletions
# ===========================================================================
def test_accept_reject_deletions():
    # Case A: Accept deletion (text should disappear)
    doc = Document()
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    stamp = RevisionStamp(author="Bob")
    p.runs = [
        TextItem(text="Keep "),
        TextItem(text="deleted ", r_pr=RunProperties(del_rev=stamp)),
        TextItem(text="rest"),
    ]
    revs = list_revisions(doc)
    assert len(revs) == 1
    assert revs[0].type == "del"

    accept_revision(doc, revs[0])
    assert len(list_revisions(doc)) == 0
    assert plain_text(p) == "Keep rest"

    # Case B: Reject deletion (text should stay, del_rev cleared)
    doc2 = Document()
    p2 = doc2.main.blocks[0]
    assert isinstance(p2, Paragraph)
    p2.runs = [
        TextItem(text="Keep "),
        TextItem(text="deleted ", r_pr=RunProperties(del_rev=stamp)),
        TextItem(text="rest"),
    ]
    revs2 = list_revisions(doc2)
    reject_revision(doc2, revs2[0])
    assert len(list_revisions(doc2)) == 0
    assert plain_text(p2) == "Keep deleted rest"
    for it in p2.runs:
        assert getattr(it.r_pr, "del_rev", None) is None


# ===========================================================================
# 6. Accept / Reject Formatting Changes
# ===========================================================================
def test_accept_reject_formatting_changes():
    # Character formatting change
    doc = Document()
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    stamp = RevisionStamp(author="Charlie", old={"b": False, "sz": 12.0})
    p.runs = [TextItem(text="Styled text", r_pr=RunProperties(b=True, sz=16.0, chg=stamp))]

    revs = list_revisions(doc)
    assert len(revs) == 1
    assert revs[0].type == "chg"

    # Reject restores old
    reject_revision(doc, revs[0])
    assert len(list_revisions(doc)) == 0
    assert p.runs[0].r_pr.b is False
    assert p.runs[0].r_pr.sz == 12.0
    assert p.runs[0].r_pr.chg is None

    # Paragraph formatting change
    doc2 = Document()
    p2 = doc2.main.blocks[0]
    assert isinstance(p2, Paragraph)
    p2.p_pr.jc = "center"
    p2.p_pr.chg = RevisionStamp(author="Charlie", old={"jc": "left"})
    revs2 = list_revisions(doc2)
    assert len(revs2) == 1
    assert revs2[0].type == "pchg"

    reject_revision(doc2, revs2[0])
    assert p2.p_pr.jc == "left"
    assert p2.p_pr.chg is None


# ===========================================================================
# 7. Accept / Reject Paragraph Marks (mins / mdel)
# ===========================================================================
def test_accept_reject_paragraph_marks():
    # Case A: Paragraph split (mins). Rejecting joins p1 and p2 back together.
    doc = Document()
    p1 = doc.main.blocks[0]
    assert isinstance(p1, Paragraph)
    p1.runs = [TextItem(text="First line ")]
    p1.mark_ins = RevisionStamp(author="Alice")

    p2 = Paragraph(runs=[TextItem(text="Second line")])
    doc.main.blocks.append(p2)
    reindex(doc)

    revs = list_revisions(doc)
    assert any(r.type == "mins" for r in revs)
    mins_rev = next(r for r in revs if r.type == "mins")

    reject_revision(doc, mins_rev)
    assert len(doc.main.blocks) == 1
    assert plain_text(doc.main.blocks[0]) == "First line Second line"


# ===========================================================================
# 8. Accept / Reject All Revisions
# ===========================================================================
def test_accept_reject_all():
    doc = Document()
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    stamp = RevisionStamp(author="Alice")
    p.runs = [
        TextItem(text="A", r_pr=RunProperties(ins=stamp)),
        TextItem(text="B", r_pr=RunProperties(del_rev=stamp)),
        TextItem(text="C", r_pr=RunProperties(ins=stamp)),
    ]

    assert len(list_revisions(doc)) == 3
    accepted_count = accept_all_revisions(doc)
    assert accepted_count == 3
    assert len(list_revisions(doc)) == 0
    assert plain_text(p) == "AC"

    # Reject all on another doc
    doc2 = Document()
    p2 = doc2.main.blocks[0]
    assert isinstance(p2, Paragraph)
    p2.runs = [
        TextItem(text="A", r_pr=RunProperties(ins=stamp)),
        TextItem(text="B", r_pr=RunProperties(del_rev=stamp)),
        TextItem(text="C", r_pr=RunProperties(ins=stamp)),
    ]
    rejected_count = reject_all_revisions(doc2)
    assert rejected_count == 3
    assert len(list_revisions(doc2)) == 0
    assert plain_text(p2) == "B"


# ===========================================================================
# 9. Comment Insertion, Numbering, & Anchoring
# ===========================================================================
def test_comment_insertion_and_markers():
    doc = Document()
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    p.runs = [TextItem(text="The quick brown fox jumps over the lazy dog")]

    # Insert comment over "brown fox" (offset 10 to 19)
    cmt = insert_comment(
        doc,
        start_pos=(p, 10),
        end_pos=(p, 19),
        text="Check animal name",
        author="Editor",
        initials="ED",
    )
    assert cmt.id in doc.comments
    assert cmt.author == "Editor"
    assert cmt.initials == "ED"
    assert cmt.text == "Check animal name"

    # Verify range markers exist in p
    cs_items = [it for it in p.runs if isinstance(it, CommentRangeStart)]
    ce_items = [it for it in p.runs if isinstance(it, CommentRangeEnd)]
    assert len(cs_items) == 1
    assert len(ce_items) == 1
    assert str(cs_items[0].comment_id) == cmt.id
    assert str(ce_items[0].comment_id) == cmt.id

    # Verify comment_at
    assert comment_at(doc, p, 12) == cmt.id
    assert comment_at(doc, p, 2) is None

    # Verify comment number
    assert comment_number(doc, cmt.id) == 1


# ===========================================================================
# 10. Comment Reply & Cascading Deletion
# ===========================================================================
def test_comment_reply_and_deletion_cascade():
    doc = Document()
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    p.runs = [TextItem(text="Discussion topic text.")]

    cmt = insert_comment(
        doc,
        start_pos=(p, 0),
        end_pos=(p, 10),
        text="First question",
        author="Alice",
    )

    # Reply to comment
    reply = reply_comment(
        doc,
        parent_id=cmt.id,
        text="I agree with this.",
        author="Bob",
    )
    assert reply is not None
    assert reply.parent == cmt.id
    assert reply.id in doc.comments
    assert len(doc.comments) == 2

    # Delete parent: cascades to reply and removes markers
    ok = delete_comment(doc, cmt.id)
    assert ok is True
    assert len(doc.comments) == 0

    # Markers should be gone
    assert not any(isinstance(it, (CommentRangeStart, CommentRangeEnd)) for it in p.runs)


# ===========================================================================
# 11. Comment Editing & Delete All
# ===========================================================================
def test_comment_editing_and_numbering():
    doc = Document()
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    p.runs = [TextItem(text="Sample paragraph")]

    c1 = insert_comment(doc, (p, 0), (p, 6), text="Initial text", author="User")
    assert edit_comment(doc, c1.id, "Revised comment note") is True
    assert doc.comments[c1.id].text == "Revised comment note"

    insert_comment(doc, (p, 7), (p, 16), text="Second note", author="User")
    assert len(doc.comments) == 2

    count = delete_all_comments(doc)
    assert count == 2
    assert len(doc.comments) == 0


# ===========================================================================
# 12. Sequential Revision & Comment Navigation
# ===========================================================================
def test_revision_and_comment_navigation():
    doc = Document()
    p1 = doc.main.blocks[0]
    assert isinstance(p1, Paragraph)
    stamp = RevisionStamp(author="Alice")
    p1.runs = [
        TextItem(text="First "),
        TextItem(text="revised ", r_pr=RunProperties(ins=stamp)),
        TextItem(text="text."),
    ]

    p2 = Paragraph(runs=[TextItem(text="Second paragraph with comment.")])
    doc.main.blocks.append(p2)
    insert_comment(doc, (p2, 7), (p2, 16), text="A comment", author="Bob")
    reindex(doc)

    # Forward navigation from (p1, 0)
    item1 = navigate_revision(doc, cur_para=p1, cur_offset=0, direction=1)
    assert item1 is not None
    assert item1.kind == "rev"
    assert item1.start == 6

    # Forward navigation from item1 to comment in p2
    item2 = navigate_revision(doc, cur_para=item1.para, cur_offset=item1.start, direction=1)
    assert item2 is not None
    assert item2.kind == "cmt"
    assert item2.para is p2

    # Forward from item2 should reach end
    item3 = navigate_revision(doc, cur_para=item2.para, cur_offset=item2.start + 1, direction=1)
    assert item3 is None

    # Backward navigation from end
    b1 = navigate_revision(doc, cur_para=p2, cur_offset=25, direction=-1)
    assert b1 is not None
    assert b1.kind == "cmt"

    b2 = navigate_revision(doc, cur_para=b1.para, cur_offset=b1.start - 1, direction=-1)
    assert b2 is not None
    assert b2.kind == "rev"


# ===========================================================================
# 13. Balloon Collision-Free Layout Algorithm
# ===========================================================================
def test_balloon_collision_free_layout():
    # Create 3 balloon items positioned closely vertically
    items = [
        BalloonItem(id="1", anchor_x=450.0, anchor_y=100.0, height=50.0, author="Alice"),
        BalloonItem(id="2", anchor_x=450.0, anchor_y=110.0, height=50.0, author="Bob"),
        BalloonItem(id="3", anchor_x=450.0, anchor_y=120.0, height=50.0, author="Charlie"),
    ]

    placements = layout_balloons(items, page_top=72.0, min_gap=8.0)
    assert len(placements) == 3

    # Verify no overlaps: placement[i+1].y >= placement[i].y + height + gap
    for i in range(len(placements) - 1):
        prev = placements[i]
        curr = placements[i + 1]
        assert curr.y >= prev.y + prev.height + 7.9  # with float precision

    # Verify connector line coordinates generated
    assert len(placements[0].connector_lines) > 0


# ===========================================================================
# 14. UI Views & i18n
# ===========================================================================
def test_review_ui_widgets_and_i18n(qapp):
    doc = Document()
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    stamp = RevisionStamp(author="Alice")
    p.runs = [
        TextItem(text="Hello "),
        TextItem(text="World", r_pr=RunProperties(ins=stamp)),
    ]
    insert_comment(doc, (p, 0), (p, 5), text="Greeting comment", author="Bob")

    # Test ReviewToolbar
    toolbar = ReviewToolbar()
    assert toolbar.objectName() == "ReviewToolbar"

    toggled = []
    toolbar.track_changes_toggled.connect(toggled.append)
    toolbar.act_track.setChecked(True)
    assert toggled == [True]

    prev_called = []
    toolbar.previous_requested.connect(lambda: prev_called.append(True))
    toolbar.act_prev.trigger()
    assert prev_called == [True]

    toolbar.retranslate_ui()

    # Test ReviewPane
    pane = ReviewPane(doc=doc)
    assert pane.list_widget.count() == 2

    # Verify filter
    pane.combo_authors.setCurrentText("Alice")
    # Only Alice's revision shown
    assert pane.list_widget.count() == 1

    pane.combo_authors.setCurrentIndex(0)  # All
    assert pane.list_widget.count() == 2

    pane.retranslate_ui()

    # Test CommentBalloonWidget
    placement = BalloonPlacement(
        id="1",
        y=100.0,
        height=60.0,
        color="#C00000",
        author="Alice",
        initials="AL",
        date="2026-10-26",
        text="Balloon text",
        reply=False,
    )
    balloon = CommentBalloonWidget(placement)
    assert balloon.objectName() == "Balloon_1"

    # Test safe_tr
    assert safe_tr("Track Changes") in ["Track Changes", "修订"]
    assert safe_tr("Reviewing Pane") in ["Reviewing Pane", "审阅窗格"]
