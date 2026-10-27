"""Comprehensive unit tests for multimedia video/audio lossless preservation, PPTX I/O, and canvas view."""

from __future__ import annotations

import hashlib
import io
import xml.etree.ElementTree as ET
import zipfile

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QGraphicsScene, QGraphicsSceneMouseEvent

from atboffice.modules.presentation.io import (
    PptxReader,
    PptxWriter,
    read_pptx,
    write_pptx,
)
from atboffice.modules.presentation.models.media_item import (
    MEDIA_MIME_TYPES,
    MediaItem,
    PlaybackSettings,
    guess_media_content_type,
    is_audio_extension,
    is_video_extension,
)
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.views.shape_item import ShapeGraphicsItem


# 1x1 Transparent dummy PNG
DUMMY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Simulated MP4 binary stream
DUMMY_MP4 = (
    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42\x00\x00\x00\x08free"
    b"LECTERN_TEST_VIDEO_PAYLOAD_BYTE_PRESERVE_1234567890"
)

# Simulated MP3 binary stream
DUMMY_MP3 = (
    b"\xff\xfb\x90\x44\x00\x00\x00\x00"
    b"LECTERN_TEST_AUDIO_PAYLOAD_BYTE_PRESERVE_9876543210"
)


def test_media_item_model_creation_and_dict():
    """Verify PlaybackSettings and MediaItem properties, MIME resolution, and serialization."""
    pb = PlaybackSettings(
        auto_play=True,
        loop=True,
        volume=0.85,
        hide_while_not_playing=True,
        rewind=False,
    )
    pb_dict = pb.to_dict()
    assert pb_dict["autoPlay"] is True
    assert pb_dict["loop"] is True
    assert pb_dict["vol"] == 0.85
    assert pb_dict["hideWhenStopped"] is True
    assert pb_dict["rewind"] is False

    pb_restored = PlaybackSettings.from_dict(pb_dict)
    assert pb_restored.auto_play is True
    assert pb_restored.loop is True
    assert pb_restored.volume == 0.85
    assert pb_restored.hide_while_not_playing is True
    assert pb_restored.rewind is False

    item = MediaItem(
        media_type="video",
        media_path="ppt/media/intro.mp4",
        media_bytes=DUMMY_MP4,
        poster_path="ppt/media/poster1.png",
        poster_bytes=DUMMY_PNG,
        playback=pb,
    )
    assert item.is_video is True
    assert item.is_audio is False
    assert item.extension == "mp4"
    assert item.file_name == "intro.mp4"
    assert item.content_type == "video/mp4"

    d = item.to_dict()
    assert d["type"] == "video"
    assert d["path"] == "ppt/media/intro.mp4"
    assert d["contentType"] == "video/mp4"
    assert d["posterPath"] == "ppt/media/poster1.png"

    restored = MediaItem.from_dict(d)
    assert restored is not None
    assert restored.is_video is True
    assert restored.media_path == "ppt/media/intro.mp4"
    assert restored.poster_path == "ppt/media/poster1.png"
    assert restored.playback.loop is True


def test_shape_media_item_integration():
    """Verify Shape model integrates media_item in to_dict/from_dict."""
    item = MediaItem(
        media_type="audio",
        media_path="ppt/media/track.mp3",
        content_type="audio/mpeg",
        media_bytes=DUMMY_MP3,
    )
    sh = Shape(
        id="m_sh1",
        type="image",
        name="Music Track",
        x=50.0,
        y=80.0,
        w=150.0,
        h=120.0,
        media="ppt/media/track.mp3",
        media_item=item,
    )
    d = sh.to_dict()
    assert "media_item" in d
    assert d["media_item"]["type"] == "audio"
    assert d["media_item"]["path"] == "ppt/media/track.mp3"

    sh_restored = Shape.from_dict(d)
    assert sh_restored.media_item is not None
    assert sh_restored.media_item.is_audio is True
    assert sh_restored.media_item.media_path == "ppt/media/track.mp3"


def test_pptx_video_embed_and_lossless_roundtrip():
    """Verify embedding a video file, writing to PPTX, and byte-level lossless preservation upon reload."""
    pres = Presentation.create_new(title="Video Preservation Test", empty=True)
    slide = Slide(id="s1", layout="blank")

    pb = PlaybackSettings(
        auto_play=False,
        loop=True,
        volume=0.75,
        hide_while_not_playing=True,
    )
    media_item = MediaItem(
        media_type="video",
        media_path="ppt/media/sample_video.mp4",
        content_type="video/mp4",
        media_bytes=DUMMY_MP4,
        poster_path="ppt/media/poster_thumb.png",
        poster_bytes=DUMMY_PNG,
        playback=pb,
    )

    video_shape = Shape(
        id="vid1",
        type="image",
        name="Sample Video",
        x=100.0,
        y=80.0,
        w=480.0,
        h=270.0,
        media="ppt/media/poster_thumb.png",
        media_item=media_item,
    )
    slide.add_shape(video_shape)
    pres.slides.append(slide)

    # 1. Write to PPTX bytes
    pptx_bytes = write_pptx(pres)
    assert len(pptx_bytes) > 0

    # 2. Inspect ZIP OPC Package directly
    with zipfile.ZipFile(io.BytesIO(pptx_bytes), "r") as zf:
        namelist = zf.namelist()
        # Ensure media binary and poster image parts are present
        media_parts = [n for n in namelist if n.startswith("ppt/media/")]
        assert len(media_parts) >= 2

        # Verify raw bytes of the saved video part match original exactly
        found_video_part = next((n for n in media_parts if n.endswith(".mp4")), None)
        assert found_video_part is not None
        saved_video_bytes = zf.read(found_video_part)
        assert hashlib.sha256(saved_video_bytes).hexdigest() == hashlib.sha256(DUMMY_MP4).hexdigest()

        # Check slide XML for <p:pic> with p14:media and p:videoFile
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "p14:media" in slide_xml
        assert "p:videoFile" in slide_xml
        assert "ppaction://media" in slide_xml

        # Check timing node for volume and playback settings
        assert "p:timing" in slide_xml
        assert "p:cMediaNode" in slide_xml
        assert 'vol="75000"' in slide_xml
        assert 'showWhenStopped="0"' in slide_xml
        assert 'repeatCount="indefinite"' in slide_xml

        # Check slide relationships for image, video, and media
        rels_xml = zf.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
        assert "relationships/image" in rels_xml
        assert "relationships/video" in rels_xml
        assert "relationships/media" in rels_xml

    # 3. Read back via PptxReader
    restored_pres = read_pptx(pptx_bytes)
    assert len(restored_pres.slides) == 1
    restored_slide = restored_pres.slides[0]
    assert len(restored_slide.shapes) == 1

    restored_shape = restored_slide.shapes[0]
    assert restored_shape.media_item is not None
    m_restored = restored_shape.media_item
    assert m_restored.is_video is True
    assert m_restored.media_bytes is not None

    # Byte-level 100% hash check
    assert hashlib.sha256(m_restored.media_bytes).hexdigest() == hashlib.sha256(DUMMY_MP4).hexdigest()
    assert m_restored.poster_bytes is not None
    assert hashlib.sha256(m_restored.poster_bytes).hexdigest() == hashlib.sha256(DUMMY_PNG).hexdigest()

    # Playback settings check
    assert m_restored.playback.volume == 0.75
    assert m_restored.playback.loop is True
    assert m_restored.playback.hide_while_not_playing is True


def test_pptx_audio_embed_and_lossless_roundtrip():
    """Verify embedding an audio file, writing to PPTX, and preserving audio part losslessly."""
    pres = Presentation.create_new(title="Audio Preservation Test", empty=True)
    slide = Slide(id="s1", layout="blank")

    pb = PlaybackSettings(auto_play=True, volume=0.9)
    media_item = MediaItem(
        media_type="audio",
        media_path="ppt/media/bgm.mp3",
        content_type="audio/mpeg",
        media_bytes=DUMMY_MP3,
        playback=pb,
    )

    audio_shape = Shape(
        id="aud1",
        type="image",
        name="Background Audio",
        x=40.0,
        y=40.0,
        w=60.0,
        h=60.0,
        media="ppt/media/bgm.mp3",
        media_item=media_item,
    )
    slide.add_shape(audio_shape)
    pres.slides.append(slide)

    pptx_bytes = write_pptx(pres)
    assert len(pptx_bytes) > 0

    with zipfile.ZipFile(io.BytesIO(pptx_bytes), "r") as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "p:audioFile" in slide_xml

        rels_xml = zf.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
        assert "relationships/audio" in rels_xml

        # Verify raw audio part
        audio_part = next((n for n in zf.namelist() if n.endswith(".mp3")), None)
        assert audio_part is not None
        saved_audio = zf.read(audio_part)
        assert hashlib.sha256(saved_audio).hexdigest() == hashlib.sha256(DUMMY_MP3).hexdigest()

    # Read back and assert audio byte hash
    restored_pres = read_pptx(pptx_bytes)
    restored_shape = restored_pres.slides[0].shapes[0]
    assert restored_shape.media_item is not None
    assert restored_shape.media_item.is_audio is True
    assert hashlib.sha256(restored_shape.media_item.media_bytes).hexdigest() == hashlib.sha256(DUMMY_MP3).hexdigest()


def test_canvas_item_media_rendering_and_interaction(qtbot):
    """Verify ShapeGraphicsItem renders poster frame, center play button, and bottom control bar."""
    pb = PlaybackSettings(auto_play=False, volume=0.8)
    media_item = MediaItem(
        media_type="video",
        media_path="ppt/media/test.mp4",
        media_bytes=DUMMY_MP4,
        poster_bytes=DUMMY_PNG,
        playback=pb,
    )
    shape = Shape(
        id="v1",
        type="image",
        name="Canvas Video Item",
        x=20.0,
        y=20.0,
        w=320.0,
        h=180.0,
        media_item=media_item,
    )

    scene = QGraphicsScene()
    item = ShapeGraphicsItem(shape)
    scene.addItem(item)

    # 1. Paint onto a simulated QPixmap to confirm rendering executes cleanly without exceptions
    pix = QPixmap(320, 180)
    pix.fill(Qt.GlobalColor.white)
    painter = QPainter(pix)
    item.paint(painter, None)
    painter.end()

    # 2. Check tooltip is properly generated with i18n support
    tip = item.toolTip()
    assert "多媒体" in tip or "Media" in tip or "Canvas Video Item" in tip

    # 3. Simulate click on center play badge to toggle playback preview state
    assert item._is_preview_playing is False
    center_pos = QPointF(160.0, 90.0)

    # Trigger custom mouse press event
    ev = QGraphicsSceneMouseEvent(QGraphicsSceneMouseEvent.Type.GraphicsSceneMousePress)
    ev.setButton(Qt.MouseButton.LeftButton)
    ev.setPos(center_pos)
    item.mousePressEvent(ev)
    assert item._is_preview_playing is True

    # Re-click to pause
    item.mousePressEvent(ev)
    assert item._is_preview_playing is False


def test_canvas_audio_placeholder_rendering(qtbot):
    """Verify ShapeGraphicsItem renders audio speaker placeholder without poster."""
    media_item = MediaItem(
        media_type="audio",
        media_path="ppt/media/podcast.wav",
        media_bytes=b"RIFF....WAVEfmt ",
        poster_bytes=None,
    )
    shape = Shape(
        id="a1",
        type="image",
        name="Podcast Audio",
        x=10.0,
        y=10.0,
        w=120.0,
        h=100.0,
        media_item=media_item,
    )

    scene = QGraphicsScene()
    item = ShapeGraphicsItem(shape)
    scene.addItem(item)

    pix = QPixmap(120, 100)
    painter = QPainter(pix)
    item.paint(painter, None)
    painter.end()

    tip = item.toolTip()
    assert "音频" in tip or "Audio" in tip


def test_missing_media_and_corrupt_data_defenses():
    """Verify graceful handling when media bytes or poster image is empty or invalid."""
    item = MediaItem(
        media_type="video",
        media_path="ppt/media/broken.mp4",
        media_bytes=b"",  # Empty stream
        poster_bytes=b"not-a-valid-image",  # Invalid image data
    )
    sh = Shape(id="broken1", type="image", media_item=item, w=100.0, h=100.0)

    # Should not throw when painting with invalid image data
    pix = QPixmap(100, 100)
    painter = QPainter(pix)
    g_item = ShapeGraphicsItem(sh)
    g_item.paint(painter, None)
    painter.end()
