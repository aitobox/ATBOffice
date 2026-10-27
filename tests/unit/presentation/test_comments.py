"""Unit tests for Lectern slide comments, authors graph, and review navigation."""

from __future__ import annotations

import io
import zipfile

from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.io import read_pptx, write_pptx
from atboffice.modules.presentation.models.comment import (
    Comment,
    CommentAuthor,
    CommentReply,
    extract_initials,
    format_relative_time,
)
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.slide import dup_slide
from atboffice.modules.presentation.views.comment_overlay import (
    CommentCardWidget,
)
from atboffice.modules.presentation.views.slide_canvas import SlideScene
from atboffice.modules.presentation.views.workspace import LecternWorkspace


def test_comment_models_and_dict():
    """Verify CommentAuthor, CommentReply, and Comment serialization and defaults."""
    author = CommentAuthor(
        id="0",
        name="John Doe",
        last_idx=2,
        color_idx=1,
        user_id="john@example.com",
    )
    assert author.initials == "JD"
    d_author = author.to_dict()
    assert d_author["name"] == "John Doe"
    assert d_author["userId"] == "john@example.com"
    restored_author = CommentAuthor.from_dict(d_author)
    assert restored_author.id == "0"
    assert restored_author.name == "John Doe"
    assert restored_author.initials == "JD"

    # Initials helper
    assert extract_initials("Alice") == "AL"
    assert extract_initials("Bob Smith") == "BS"
    assert extract_initials("") == "A"

    # Relative time
    assert format_relative_time("") == "刚刚"

    # CommentReply
    reply = CommentReply(
        id="rep_1",
        author_id="0",
        created="2026-10-27T10:00:00Z",
        text="Looks great!",
    )
    d_rep = reply.to_dict()
    restored_rep = CommentReply.from_dict(d_rep)
    assert restored_rep.text == "Looks great!"

    # Comment
    comment = Comment(
        id="cm_1",
        author_id="0",
        text="Please revise this paragraph.",
        x=50.0,
        y=100.0,
        idx=1,
        created="2026-10-27T10:00:00Z",
        shape_id="s_123",
        status="active",
        replies=[reply],
    )
    d_cm = comment.to_dict()
    assert d_cm["shapeId"] == "s_123"
    assert len(d_cm["replies"]) == 1

    restored_cm = Comment.from_dict(d_cm)
    assert restored_cm.text == "Please revise this paragraph."
    assert restored_cm.x == 50.0
    assert restored_cm.y == 100.0
    assert restored_cm.shape_id == "s_123"
    assert len(restored_cm.replies) == 1
    assert restored_cm.replies[0].text == "Looks great!"


def test_presentation_and_slide_integration():
    """Verify author graph management in Presentation and comment cloning in dup_slide."""
    pres = Presentation.create_new(title="Comment Test")
    auth1 = pres.get_or_create_author("Alice Smith")
    assert auth1.id == "0"
    assert auth1.initials == "AS"

    # Fetching same name returns existing author
    auth1_repeat = pres.get_or_create_author("alice smith")
    assert auth1_repeat.id == "0"

    auth2 = pres.get_or_create_author("Bob Jones")
    assert auth2.id == "1"
    assert auth2.initials == "BJ"

    slide = pres.slides[0]
    cm = Comment(
        id="cm_01",
        author_id=auth1.id,
        text="Test comment 1",
        x=30.0,
        y=40.0,
        shape_id="shape_orig",
    )
    slide.comments.append(cm)

    all_comments = pres.all_comments()
    assert len(all_comments) == 1
    assert all_comments[0][0] == 0  # Slide index 0
    assert all_comments[0][1].text == "Test comment 1"

    # Duplicating slide clones comments with new IDs
    cloned_slide = dup_slide(slide)
    assert len(cloned_slide.comments) == 1
    assert cloned_slide.comments[0].id != cm.id
    assert cloned_slide.comments[0].text == "Test comment 1"


def test_pptx_read_write_roundtrip():
    """Verify lossless serialization and reading of comments and comment authors in PPTX."""
    pres = Presentation.create_new(title="Roundtrip Presentation")
    a1 = pres.get_or_create_author("Reviewer One", initials="R1")
    a2 = pres.get_or_create_author("Reviewer Two", initials="R2")

    slide1 = pres.slides[0]
    slide1.comments.append(
        Comment(
            id="cm_s1_1",
            author_id=a1.id,
            text="First comment on slide 1",
            x=50.0,
            y=60.0,
            idx=1,
            created="2026-10-27T10:00:00Z",
        )
    )
    slide1.comments.append(
        Comment(
            id="cm_s1_2",
            author_id=a2.id,
            text="Second comment on slide 1",
            x=150.0,
            y=80.0,
            idx=1,
            created="2026-10-27T10:05:00Z",
        )
    )

    slide2 = pres.add_slide(layout="content")
    slide2.comments.append(
        Comment(
            id="cm_s2_1",
            author_id=a1.id,
            text="Comment on slide 2",
            x=200.0,
            y=120.0,
            idx=2,
            created="2026-10-27T10:10:00Z",
        )
    )

    # Serialize to PPTX bytes
    pptx_bytes = write_pptx(pres)
    assert len(pptx_bytes) > 0

    # Inspect zip parts directly
    with zipfile.ZipFile(io.BytesIO(pptx_bytes), "r") as z:
        names = z.namelist()
        assert "ppt/commentAuthors.xml" in names
        assert "ppt/comments/comment1.xml" in names
        assert "ppt/comments/comment2.xml" in names

        # Validate commentAuthors.xml content
        authors_xml = z.read("ppt/commentAuthors.xml").decode("utf-8")
        assert "Reviewer One" in authors_xml
        assert "Reviewer Two" in authors_xml

        # Validate comment1.xml content
        c1_xml = z.read("ppt/comments/comment1.xml").decode("utf-8")
        assert "First comment on slide 1" in c1_xml
        assert "Second comment on slide 1" in c1_xml

    # Re-read PPTX via reader
    pres_loaded = read_pptx(pptx_bytes)
    assert len(pres_loaded.comment_authors) >= 2
    assert len(pres_loaded.slides) == 2

    loaded_s1 = pres_loaded.slides[0]
    assert len(loaded_s1.comments) == 2
    assert loaded_s1.comments[0].text == "First comment on slide 1"
    assert loaded_s1.comments[0].x == 50.0
    assert loaded_s1.comments[0].y == 60.0

    loaded_s2 = pres_loaded.slides[1]
    assert len(loaded_s2.comments) == 1
    assert loaded_s2.comments[0].text == "Comment on slide 2"
    assert loaded_s2.comments[0].x == 200.0
    assert loaded_s2.comments[0].y == 120.0


def test_legacy_and_modern_comment_parsing():
    """Verify parsing of modern comment threads with replyLst and shape anchor."""
    # Synthesize PPTX containing modern comments
    pres = Presentation.create_new(title="Modern Test Deck")
    pptx_bytes = write_pptx(pres)

    # Patch ZIP to contain modern comments XML
    M = "http://schemas.microsoft.com/office/powerpoint/2018/8/main"
    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    AC = "http://schemas.microsoft.com/office/drawing/2013/main/command"
    REL = "http://schemas.microsoft.com/office/2018/10/relationships/"

    author_guid = "{10000000-0000-4000-8000-000000000001}"
    reply_author_guid = "{10000000-0000-4000-8000-000000000002}"

    modern_authors = (
        f'<p188:authorLst xmlns:p188="{M}">'
        f'<p188:author id="{author_guid}" name="Lead Reviewer" initials="LR"/>'
        f'<p188:author id="{reply_author_guid}" name="Peer Reviewer" initials="PR"/>'
        "</p188:authorLst>"
    ).encode()

    modern_comments = (
        f'<p188:cmLst xmlns:p188="{M}" xmlns:a="{A}" xmlns:ac="{AC}">'
        f'<p188:cm id="{{30000000-0000-4000-8000-000000000001}}" authorId="{author_guid}"'
        ' created="2026-10-27T10:00:00Z" status="resolved">'
        '<p188:pos x="127000" y="254000"/>'
        '<ac:spMk id="target_shape_42"/>'
        '<p188:replyLst>'
        f'<p188:reply id="{{30000000-0000-4000-8000-000000000002}}"'
        f' authorId="{reply_author_guid}" created="2026-10-27T10:30:00Z">'
        "<p188:txBody><a:p><a:r><a:t>Modern reply message</a:t></a:r></a:p></p188:txBody>"
        "</p188:reply>"
        "</p188:replyLst>"
        "<p188:txBody><a:p><a:r><a:t>Modern shape comment</a:t></a:r></a:p></p188:txBody>"
        "</p188:cm></p188:cmLst>"
    ).encode()

    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(pptx_bytes), "r") as zin:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "ppt/_rels/presentation.xml.rels":
                    data = data.replace(
                        b"</Relationships>",
                        f'<Relationship Id="rIdModAuth" Type="{REL}authors"'
                        f' Target="authors.xml"/></Relationships>'.encode(),
                    )
                elif item.filename == "ppt/slides/_rels/slide1.xml.rels":
                    data = data.replace(
                        b"</Relationships>",
                        f'<Relationship Id="rIdModCm" Type="{REL}comments"'
                        f' Target="../comments/modern1.xml"/></Relationships>'.encode(),
                    )
                zout.writestr(item, data)
            zout.writestr("ppt/authors.xml", modern_authors)
            zout.writestr("ppt/comments/modern1.xml", modern_comments)

    loaded_pres = read_pptx(buf.getvalue())
    assert any(a.name == "Lead Reviewer" for a in loaded_pres.comment_authors)
    s1 = loaded_pres.slides[0]
    assert len(s1.comments) == 1
    c = s1.comments[0]
    assert c.text == "Modern shape comment"
    assert c.x == 10.0  # 127000 / 12700
    assert c.y == 20.0  # 254000 / 12700
    assert c.shape_id == "target_shape_42"
    assert c.status == "resolved"
    assert len(c.replies) == 1
    assert c.replies[0].text == "Modern reply message"


def test_comment_marker_item_and_scene_ui():
    """Verify CommentMarkerItem rendering, mouse events, and scene addition/deletion."""
    _ = QApplication.instance() or QApplication([])

    pres = Presentation.create_new(title="UI Scene Deck")
    slide = pres.slides[0]

    scene = SlideScene(slide=slide, presentation=pres)
    assert len(scene.get_comment_markers()) == 0

    # Add comment at (100, 200)
    cm = scene.add_comment_at(100.0, 200.0, text="Canvas marker test")
    assert len(slide.comments) == 1
    assert len(scene.get_comment_markers()) == 1

    marker = scene.get_comment_markers()[0]
    assert marker.comment == cm
    assert marker.pos().x() == 100.0
    assert marker.pos().y() == 200.0

    # Test paint execution without error
    pixmap = QPixmap(50, 50)
    pixmap.fill(QColor("#FFFFFF"))
    painter = QPainter(pixmap)
    try:
        marker.paint(painter, None)
    finally:
        painter.end()

    # Move marker position
    marker.setPos(120.0, 220.0)
    assert cm.x == 120.0
    assert cm.y == 220.0

    # Remove comment
    scene.remove_comment(cm)
    assert len(slide.comments) == 0
    assert len(scene.get_comment_markers()) == 0


def test_comment_card_widget_interactions():
    """Verify CommentCardWidget status toggle, reply adding, and signals."""
    _ = QApplication.instance() or QApplication([])

    pres = Presentation.create_new(title="Card Interaction")
    cm = Comment(
        id="cm_card_test",
        author_id="0",
        text="Original remark",
        x=50.0,
        y=50.0,
    )

    card = CommentCardWidget(cm, pres)
    assert card.text_edit.toPlainText() == "Original remark"

    # Toggle status
    assert cm.status == "active"
    card._toggle_status()
    assert cm.status == "resolved"
    card._toggle_status()
    assert cm.status == "active"

    # Add reply
    card.reply_input.setText("Here is my feedback")
    card._submit_reply()
    assert len(cm.replies) == 1
    assert cm.replies[0].text == "Here is my feedback"


def test_comment_navigation_across_slides():
    """Verify bidirectional comment navigation in LecternWorkspace across slides."""
    _ = QApplication.instance() or QApplication([])

    pres = Presentation.create_new(title="Navigation Deck")
    s1 = pres.slides[0]
    pres.add_slide(layout="blank")
    s3 = pres.add_slide(layout="blank")

    c1 = Comment(id="c1", author_id="0", text="Comment on slide 1", x=10, y=10)
    c3 = Comment(id="c3", author_id="0", text="Comment on slide 3", x=20, y=20)
    s1.comments.append(c1)
    s3.comments.append(c3)

    workspace = LecternWorkspace(presentation=pres)
    assert workspace.current_slide_index == 0

    # Navigate forward -> jumps to c3 on slide index 2
    res = workspace.navigate_comment(direction=1)
    assert res is not None
    assert res[0] == 2  # Slide 3 (index 2)
    assert res[1].id == "c3"
    assert workspace.current_slide_index == 2

    # Navigate forward again -> loops back to c1 on slide index 0
    res2 = workspace.navigate_comment(direction=1)
    assert res2 is not None
    assert res2[0] == 0
    assert res2[1].id == "c1"
    assert workspace.current_slide_index == 0

    # Navigate backward -> jumps back to c3 on slide index 2
    res3 = workspace.navigate_comment(direction=-1)
    assert res3 is not None
    assert res3[0] == 2
    assert res3[1].id == "c3"
