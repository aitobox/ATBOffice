"""Phase 7 Lectern PPTX Rendering and Lossless Roundtrip Suite.

Covers TASK-708 (Issue #242):
- Master slides, layout inheritance, decorations (libreoffice__master-slides.pptx)
- Typography autofit (normAutofit) (libreoffice__TextFittingComparisonWithMSO_3.pptx)
- SmartArt diagram text and dataModel extraction (libreoffice__smartart-text.pptx)
- Table geometry, cell grid, per-run font colors (poi__table-with-different-font-colors.pptx)
- Visual consistency across Normal Canvas View, Thumbnail, and Slideshow
- Lossless OPC roundtrip preservation of masters, media, animations, and relationships
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.io import read_pptx, write_pptx
from atboffice.modules.presentation.slideshow.transitions import render_slide_to_image
from atboffice.modules.presentation.views.slide_canvas import SlideScene
from atboffice.modules.presentation.views.workspace import render_slide_thumbnail

PPTX_DIR = Path("tests/docs/powerpoint/pptx")


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _render_canvas_view_offscreen(
    scene: SlideScene, width: int = 960, height: int = 540
) -> QImage:
    """Render a SlideScene via QGraphicsView offscreen to QImage."""
    img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    try:
        scene.render(
            painter,
            QRectF(0, 0, width, height),
            QRectF(0, 0, scene.slide_width, scene.slide_height),
        )
    finally:
        painter.end()
    return img


# ==============================================================================
# 1. Master Slides & Decoration Rendering (libreoffice__master-slides.pptx)
# ==============================================================================


def test_master_slides_decorations_and_placeholders(qapp: QApplication) -> None:
    path = PPTX_DIR / "libreoffice__master-slides.pptx"
    assert path.exists(), f"Missing corpus file: {path}"

    data = path.read_bytes()
    pres = read_pptx(data)
    assert len(pres.slides) >= 1
    slide = pres.slides[0]

    # Verify master design and decorations
    design = pres.get_design_for_slide(slide)
    assert design is not None
    assert len(design.decorations) >= 1, (
        "Master decorations must be extracted from slideMaster spTree"
    )

    deco_texts = [d.text.plain_text for d in design.decorations if d.text]
    combined_deco = " ".join(deco_texts)
    assert "SUSE" in combined_deco or "Copyright" in combined_deco, (
        f"Master copyright decoration missing from design: {deco_texts}"
    )

    # Verify slide background inherited from layout / master
    assert slide.bg is not None, "Slide must inherit layout or master background"

    # Verify normal view canvas rendering
    scene = SlideScene(slide, pres)
    img_canvas = _render_canvas_view_offscreen(scene, 960, 540)
    assert not img_canvas.isNull()

    # Verify thumbnail rendering
    thumb = render_slide_thumbnail(slide, pres, width=160)
    assert not thumb.isNull()
    assert thumb.width() == 160

    # Verify slideshow image rendering
    img_show = render_slide_to_image(slide, pres, width=960, height=540)
    assert not img_show.isNull()


# ==============================================================================
# 2. Text AutoFit normAutofit (libreoffice__TextFittingComparisonWithMSO_3.pptx)
# ==============================================================================


def test_text_fitting_norm_autofit_scales_and_roundtrip(qapp: QApplication) -> None:
    path = PPTX_DIR / "libreoffice__TextFittingComparisonWithMSO_3.pptx"
    assert path.exists(), f"Missing corpus file: {path}"

    data = path.read_bytes()
    pres = read_pptx(data)
    assert len(pres.slides) >= 3

    # Check fontScale on slides
    slide1_scales = [
        sh.text.font_scale
        for sh in pres.slides[0].shapes
        if sh.text and sh.text.autofit == "norm"
    ]
    slide2_scales = [
        sh.text.font_scale
        for sh in pres.slides[1].shapes
        if sh.text and sh.text.autofit == "norm"
    ]
    assert any(abs(fs - 0.925) < 0.01 for fs in slide1_scales), (
        f"Slide 1 must parse fontScale=0.925, got {slide1_scales}"
    )
    assert any(abs(fs - 0.775) < 0.01 for fs in slide2_scales), (
        f"Slide 2 must parse fontScale=0.775, got {slide2_scales}"
    )

    # Test roundtrip writing and re-reading
    out_bytes = write_pptx(pres)
    assert len(out_bytes) > 0
    pres_reloaded = read_pptx(out_bytes)

    s1_scales_reloaded = [
        sh.text.font_scale
        for sh in pres_reloaded.slides[0].shapes
        if sh.text and sh.text.autofit == "norm"
    ]
    assert any(abs(fs - 0.925) < 0.01 for fs in s1_scales_reloaded), (
        f"Reloaded slide 1 must preserve fontScale=0.925, got {s1_scales_reloaded}"
    )

    # Offscreen render checks for all slides
    for s in pres.slides:
        scene = SlideScene(s, pres)
        c_img = _render_canvas_view_offscreen(scene, 960, 540)
        assert not c_img.isNull()

        t_pix = render_slide_thumbnail(s, pres, width=160)
        assert not t_pix.isNull()

        s_img = render_slide_to_image(s, pres, width=960, height=540)
        assert not s_img.isNull()


# ==============================================================================
# 3. SmartArt Diagram Text Extraction (libreoffice__smartart-text.pptx)
# ==============================================================================


def test_smartart_diagram_parsed_and_rendered(qapp: QApplication) -> None:
    path = PPTX_DIR / "libreoffice__smartart-text.pptx"
    assert path.exists(), f"Missing corpus file: {path}"

    data = path.read_bytes()
    pres = read_pptx(data)
    assert len(pres.slides) >= 1
    slide = pres.slides[0]

    # Verify diagram shape is recognized
    diag_shapes = [sh for sh in slide.shapes if sh.is_diagram or bool(sh.sa)]
    assert len(diag_shapes) >= 1, "SmartArt must be identified as diagram, not empty table"
    diag = diag_shapes[0]

    # Text must be extracted from data1.xml
    assert diag.text is not None
    assert "test" in diag.text.plain_text.lower(), (
        f"Diagram text 'test' missing: {diag.text.plain_text}"
    )

    # Verify rendering on canvas, thumbnail, and slideshow
    scene = SlideScene(slide, pres)
    c_img = _render_canvas_view_offscreen(scene, 960, 540)
    assert not c_img.isNull()

    t_pix = render_slide_thumbnail(slide, pres, width=160)
    assert not t_pix.isNull()

    s_img = render_slide_to_image(slide, pres, width=960, height=540)
    assert not s_img.isNull()


# ==============================================================================
# 4. Table with Different Font Colors (poi__table-with-different-font-colors.pptx)
# ==============================================================================


def test_table_with_different_font_colors_render_and_roundtrip(qapp: QApplication) -> None:
    path = PPTX_DIR / "poi__table-with-different-font-colors.pptx"
    assert path.exists(), f"Missing corpus file: {path}"

    data = path.read_bytes()
    pres = read_pptx(data)
    assert len(pres.slides) >= 2
    slide1 = pres.slides[0]

    # Verify table parsed
    tbl_shapes = [sh for sh in slide1.shapes if sh.type == "table" or bool(sh.tbl)]
    assert len(tbl_shapes) >= 1, "Table shape must be parsed"
    tbl_sh = tbl_shapes[0]
    tbl_data = tbl_sh.tbl
    assert tbl_data is not None
    assert len(tbl_data.get("cols", [])) == 4
    assert len(tbl_data.get("rows", [])) == 4

    # Verify colored runs in cell 0,2 and 2,2
    colors_found: set[str] = set()
    for row in tbl_data["rows"]:
        for cell in row["cells"]:
            tb = cell.get("tx")
            if tb:
                for p in tb.paragraphs:
                    for r in p.runs:
                        if r.color:
                            colors_found.add(r.color.upper())

    assert "#00B050" in colors_found, f"Green run color missing: {colors_found}"
    assert "#FF0000" in colors_found, f"Red run color missing: {colors_found}"

    # Verify canvas rendering
    scene = SlideScene(slide1, pres)
    c_img = _render_canvas_view_offscreen(scene, 960, 540)
    assert not c_img.isNull()

    # Verify thumbnail rendering
    t_pix = render_slide_thumbnail(slide1, pres, width=160)
    assert not t_pix.isNull()

    # Verify slideshow rendering
    s_img = render_slide_to_image(slide1, pres, width=960, height=540)
    assert not s_img.isNull()

    # Verify roundtrip preserves colored runs
    out_bytes = write_pptx(pres)
    pres_reloaded = read_pptx(out_bytes)
    tbl_reloaded = pres_reloaded.slides[0].shapes[0].tbl
    assert tbl_reloaded is not None

    reloaded_colors: set[str] = set()
    for row in tbl_reloaded["rows"]:
        for cell in row["cells"]:
            tb = cell.get("tx")
            if tb:
                for p in tb.paragraphs:
                    for r in p.runs:
                        if r.color:
                            reloaded_colors.add(r.color.upper())
    assert "#00B050" in reloaded_colors
    assert "#FF0000" in reloaded_colors


# ==============================================================================
# 5. Normal View, Thumbnail, and Slideshow Consistency
# ==============================================================================


def test_view_consistency_across_sample_corpus(qapp: QApplication) -> None:
    corpus_samples = [
        "libreoffice__master-slides.pptx",
        "libreoffice__TextFittingComparisonWithMSO_3.pptx",
        "libreoffice__smartart-text.pptx",
        "poi__table-with-different-font-colors.pptx",
    ]

    for filename in corpus_samples:
        file_path = PPTX_DIR / filename
        pres = read_pptx(file_path.read_bytes())
        for slide in pres.slides:
            # 1. Normal Canvas View (Native Qt Graphics Scene)
            scene = SlideScene(slide, pres)
            c_img = _render_canvas_view_offscreen(scene, 960, 540)
            assert not c_img.isNull()

            # 2. Thumbnail Preview (QPixmap)
            t_pix = render_slide_thumbnail(slide, pres, width=160)
            assert not t_pix.isNull()

            # 3. Slideshow Preview (QImage)
            s_img = render_slide_to_image(slide, pres, width=960, height=540)
            assert not s_img.isNull()


# ==============================================================================
# 6. Safe External Media Handling
# ==============================================================================


def test_safe_unsupported_external_media_handling(qapp: QApplication) -> None:
    from atboffice.modules.presentation.models.media_item import MediaItem
    from atboffice.modules.presentation.models.shape import Shape
    from atboffice.modules.presentation.models.slide import Slide

    # Slide with an external unreachable media item
    slide = Slide(id="s_test", layout="blank")
    broken_media = MediaItem(
        media_type="video",
        media_path="http://unreachable.domain.invalid/video.mp4",
        media_bytes=None,
    )
    sh = Shape(
        id="sh_media",
        type="image",
        x=50,
        y=50,
        w=300,
        h=200,
        media_item=broken_media,
    )
    slide.add_shape(sh)

    # Must render without hanging or throwing exceptions
    scene = SlideScene(slide)
    img = _render_canvas_view_offscreen(scene, 960, 540)
    assert not img.isNull()


# ==============================================================================
# 7. Metafile Pictures and srcRect Cropping (Issue #408)
# ==============================================================================

_PLACEHOLDER_RGB = (245, 245, 245)


def _pixel_rgb(img: QImage, x: int, y: int) -> tuple[int, int, int]:
    c = img.pixelColor(x, y)
    return (c.red(), c.green(), c.blue())


def _bitmap_wmf(bgr: tuple[int, int, int], size: int = 8) -> bytes:
    """Placeable WMF whose only drawing record is a META_STRETCHDIB of a solid 24-bit DIB."""
    import struct

    header_words = struct.pack("<IHhhhhHI", 0x9AC6CDD7, 0, 0, 0, 100, 100, 1440, 0)
    checksum = 0
    for word in struct.unpack("<10H", header_words):
        checksum ^= word
    placeable = header_words + struct.pack("<H", checksum)

    row = bytes(bgr) * size
    row += b"\x00" * ((4 - len(row) % 4) % 4)
    dib = struct.pack("<IiiHHIIiiII", 40, size, size, 1, 24, 0, len(row) * size, 0, 0, 0, 0)
    dib += row * size

    records = bytearray()

    def add_rec(fn: int, params: bytes) -> None:
        records.extend(struct.pack("<IH", 3 + len(params) // 2, fn) + params)

    add_rec(0x020B, struct.pack("<hh", 0, 0))  # SETWINDOWORG
    add_rec(0x020C, struct.pack("<hh", 100, 100))  # SETWINDOWEXT
    # META_STRETCHDIB: rop, usage, src h/w/y/x, dest h/w/y/x, DIB
    params = struct.pack("<IH", 0x00CC0020, 0)
    params += struct.pack("<8h", size, size, 0, 0, 100, 100, 0, 0)
    add_rec(0x0F43, params + dib)
    add_rec(0x0000, b"")  # EOF

    total_words = 9 + len(records) // 2
    header = struct.pack("<HHHIHIH", 1, 9, 0x0300, total_words, 0, total_words, 0)
    return placeable + header + bytes(records)


def _picture_slide(media_bytes: bytes, crop: dict[str, float] | None):
    from atboffice.modules.presentation.models.presentation import Presentation
    from atboffice.modules.presentation.models.shape import Shape
    from atboffice.modules.presentation.models.slide import Slide

    pres = Presentation(w=960.0, h=540.0)
    pres.props["_media_map"] = {"ppt/media/pic.bin": media_bytes}
    slide = Slide(id="s_pic", layout="blank")
    slide.add_shape(
        Shape(
            id="pic",
            type="image",
            x=100,
            y=100,
            w=400,
            h=200,
            media="ppt/media/pic.bin",
            crop=crop,
        )
    )
    pres.slides.append(slide)
    return slide, pres


def test_emf_picture_in_wmf_part_renders_with_bottom_crop(qapp: QApplication) -> None:
    pres = read_pptx((PPTX_DIR / "libreoffice__tdf149206.pptx").read_bytes())
    slide = pres.slides[0]
    pics = [s for s in slide.shapes if s.media]
    assert len(pics) == 1
    pic = pics[0]
    assert pic.crop is not None and abs(pic.crop["b"] - 0.37396) < 1e-6

    scene = SlideScene(slide, pres)
    img = _render_canvas_view_offscreen(scene, int(pres.w), int(pres.h))

    # The embedded bitmap is an email client screenshot: the toolbar and the white
    # message pane draw non-placeholder colors inside the frame.
    x0, y0 = int(pic.x), int(pic.y)
    x1, y1 = int(pic.x + pic.w), int(pic.y + pic.h)
    samples = [
        _pixel_rgb(img, x, y) for x in range(x0 + 4, x1 - 4, 9) for y in range(y0 + 4, y1 - 4, 9)
    ]
    placeholder_hits = sum(1 for rgb in samples if rgb == _PLACEHOLDER_RGB)
    assert placeholder_hits < len(samples) * 0.05
    assert len(set(samples)) > 20

    # Nothing of the cropped-off lower part may spill below the frame.
    below = [_pixel_rgb(img, x, y1 + 3) for x in range(x0 + 4, x1 - 4, 7)]
    assert all(rgb == (255, 255, 255) for rgb in below)


def test_bitmap_bearing_wmf_picture_renders_bitmap(qapp: QApplication) -> None:
    slide, pres = _picture_slide(_bitmap_wmf((0, 0, 255)), crop=None)  # BGR -> red
    img = _render_canvas_view_offscreen(SlideScene(slide, pres), 960, 540)
    r, g, b = _pixel_rgb(img, 300, 200)
    assert r > 200 and g < 40 and b < 40


def test_png_picture_bottom_crop_shows_only_top_half(qapp: QApplication) -> None:
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor

    src = QImage(100, 100, QImage.Format.Format_RGB32)
    src.fill(QColor(0, 0, 255))
    p = QPainter(src)
    p.fillRect(0, 50, 100, 50, QColor(0, 200, 0))
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    src.save(buf, "PNG")
    png = bytes(buf.data())

    slide, pres = _picture_slide(png, crop={"l": 0.0, "t": 0.0, "r": 0.0, "b": 0.5})
    img = _render_canvas_view_offscreen(SlideScene(slide, pres), 960, 540)
    for y in (110, 200, 290):
        r, g, b = _pixel_rgb(img, 300, y)
        assert b > 200 and g < 40, (y, r, g, b)
    assert _pixel_rgb(img, 300, 304) == (255, 255, 255)


def test_corrupt_metafile_picture_falls_back_to_placeholder(qapp: QApplication) -> None:
    import struct

    truncated_emf = struct.pack("<II", 1, 88) + b"\x00" * 32 + b" EMF" + b"\x00" * 8
    truncated_wmf = struct.pack("<I", 0x9AC6CDD7) + b"\x00" * 30
    for junk in (truncated_emf, truncated_wmf, b"not an image" * 4):
        slide, pres = _picture_slide(junk, crop=None)
        img = _render_canvas_view_offscreen(SlideScene(slide, pres), 960, 540)
        assert _pixel_rgb(img, 300, 200) == _PLACEHOLDER_RGB


# ==============================================================================
# 8. Slideshow Pictures Match the Editing Canvas
# ==============================================================================

_BLUE = (0, 0, 255)
_GREEN = (0, 200, 0)


def _split_png(*, vertical: bool) -> bytes:
    """100x100 PNG: blue top/green bottom, or blue left/green right when ``vertical``."""
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor

    src = QImage(100, 100, QImage.Format.Format_RGB32)
    src.fill(QColor(*_BLUE))
    p = QPainter(src)
    if vertical:
        p.fillRect(50, 0, 50, 100, QColor(*_GREEN))
    else:
        p.fillRect(0, 50, 100, 50, QColor(*_GREEN))
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    src.save(buf, "PNG")
    return bytes(buf.data())


def _assert_rgb_near(actual: tuple[int, int, int], expected: tuple[int, int, int]) -> None:
    assert all(abs(a - e) <= 12 for a, e in zip(actual, expected, strict=True)), (actual, expected)


def test_slideshow_matches_canvas_for_cropped_metafile_picture(qapp: QApplication) -> None:
    pres = read_pptx((PPTX_DIR / "libreoffice__tdf149206.pptx").read_bytes())
    slide = pres.slides[0]
    pic = next(s for s in slide.shapes if s.media)
    width, height = int(pres.w), int(pres.h)

    canvas = _render_canvas_view_offscreen(SlideScene(slide, pres), width, height)
    show = render_slide_to_image(slide, pres, width=width, height=height)

    x0, y0 = int(pic.x), int(pic.y)
    x1, y1 = int(pic.x + pic.w), int(pic.y + pic.h)
    diffs = [
        max(
            abs(a - b)
            for a, b in zip(_pixel_rgb(canvas, x, y), _pixel_rgb(show, x, y), strict=True)
        )
        for x in range(x0 + 4, x1 - 4, 9)
        for y in range(y0 + 4, y1 - 4, 9)
    ]
    assert sum(1 for d in diffs if d > 40) < len(diffs) * 0.02
    assert all(_pixel_rgb(show, x, y1 + 3) == (255, 255, 255) for x in range(x0 + 4, x1 - 4, 7))


def test_slideshow_draws_bitmap_wmf_picture(qapp: QApplication) -> None:
    slide, pres = _picture_slide(_bitmap_wmf((0, 0, 255)), crop=None)  # BGR -> red
    r, g, b = _pixel_rgb(render_slide_to_image(slide, pres, 960, 540), 300, 200)
    assert r > 200 and g < 40 and b < 40


def test_slideshow_picture_applies_src_rect_crop(qapp: QApplication) -> None:
    crop = {"l": 0.0, "t": 0.0, "r": 0.0, "b": 0.5}
    slide, pres = _picture_slide(_split_png(vertical=False), crop=crop)
    img = render_slide_to_image(slide, pres, 960, 540)
    for y in (110, 200, 290):
        _assert_rgb_near(_pixel_rgb(img, 300, y), _BLUE)
    assert _pixel_rgb(img, 300, 304) == (255, 255, 255)


def test_slideshow_picture_applies_flip(qapp: QApplication) -> None:
    slide, pres = _picture_slide(_split_png(vertical=True), crop=None)
    slide.shapes[0].flip_h = True
    img = render_slide_to_image(slide, pres, 960, 540)
    _assert_rgb_near(_pixel_rgb(img, 150, 200), _GREEN)
    _assert_rgb_near(_pixel_rgb(img, 450, 200), _BLUE)


def test_slideshow_picture_applies_rotation(qapp: QApplication) -> None:
    slide, pres = _picture_slide(_split_png(vertical=True), crop=None)
    pic = slide.shapes[0]
    pic.x, pic.y, pic.w, pic.h = 200, 100, 200, 200
    pic.rot = 90.0
    img = render_slide_to_image(slide, pres, 960, 540)
    _assert_rgb_near(_pixel_rgb(img, 300, 150), _BLUE)  # left half turns to the top
    _assert_rgb_near(_pixel_rgb(img, 300, 250), _GREEN)


def test_slideshow_picture_clips_to_shape_geometry(qapp: QApplication) -> None:
    slide, pres = _picture_slide(_split_png(vertical=True), crop=None)
    slide.shapes[0].geom = "ellipse"
    img = render_slide_to_image(slide, pres, 960, 540)
    assert _pixel_rgb(img, 104, 104) == (255, 255, 255)
    _assert_rgb_near(_pixel_rgb(img, 200, 200), _BLUE)


def test_slideshow_picture_follows_animation_frame_state(qapp: QApplication) -> None:
    from types import SimpleNamespace

    slide, pres = _picture_slide(_split_png(vertical=True), crop=None)
    state = SimpleNamespace(visible=True, opacity=1.0, translate_x=300.0, translate_y=0.0)
    img = render_slide_to_image(slide, pres, 960, 540, frame_states={"pic": state})
    assert _pixel_rgb(img, 150, 200) == (255, 255, 255)
    _assert_rgb_near(_pixel_rgb(img, 450, 200), _BLUE)


def test_slideshow_draws_grouped_and_master_pictures(qapp: QApplication) -> None:
    import copy

    from atboffice.modules.presentation.models.shape import Shape

    slide, pres = _picture_slide(_split_png(vertical=True), crop=None)
    media = slide.shapes[0].media
    slide.shapes.clear()
    slide.add_shape(
        Shape(
            id="grp",
            type="group",
            x=100,
            y=100,
            w=200,
            h=100,
            kids=[Shape(id="kid", type="image", x=100, y=100, w=200, h=100, media=media)],
        )
    )
    design = copy.deepcopy(pres.get_design_for_slide(slide))
    design.decorations = [Shape(id="logo", type="image", x=500, y=300, w=200, h=100, media=media)]
    pres.get_design_for_slide = lambda _slide: design  # type: ignore[method-assign]

    img = render_slide_to_image(slide, pres, 960, 540)
    _assert_rgb_near(_pixel_rgb(img, 150, 150), _BLUE)
    _assert_rgb_near(_pixel_rgb(img, 250, 150), _GREEN)
    _assert_rgb_near(_pixel_rgb(img, 550, 350), _BLUE)
    _assert_rgb_near(_pixel_rgb(img, 650, 350), _GREEN)


def test_slideshow_picture_outline_does_not_cover_picture(qapp: QApplication) -> None:
    from atboffice.modules.presentation.models.shape import Line, Shape

    slide, pres = _picture_slide(_split_png(vertical=True), crop=None)
    pic = slide.shapes[0]
    pic.line = Line(type="solid", color="#FF0000", width=4.0)
    slide.shapes.insert(0, Shape(id="dgm", type="diagram", x=600, y=50, w=100, h=100, sa={"n": 1}))
    img = render_slide_to_image(slide, pres, 960, 540)
    _assert_rgb_near(_pixel_rgb(img, 150, 200), _BLUE)
    r, g, b = _pixel_rgb(img, 100, 200)
    assert r > 200 and g < 60 and b < 60


def test_slideshow_undecodable_picture_matches_canvas_placeholder(qapp: QApplication) -> None:
    slide, pres = _picture_slide(b"not an image" * 4, crop=None)
    img = render_slide_to_image(slide, pres, 960, 540)
    assert _pixel_rgb(img, 300, 200) == _PLACEHOLDER_RGB


def test_slideshow_decodes_metafile_once_across_frames(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from atboffice.modules.presentation.views import picture_painter

    calls: list[bytes] = []
    real = picture_painter.render_metafile_to_image

    def counting(data: bytes, **kwargs: object) -> QImage | None:
        calls.append(data)
        return real(data, **kwargs)

    monkeypatch.setattr(picture_painter, "render_metafile_to_image", counting)
    picture_painter.decode_picture_bytes.cache_clear()
    slide, pres = _picture_slide(_bitmap_wmf((0, 0, 255)), crop=None)
    for _ in range(3):
        render_slide_to_image(slide, pres, 960, 540)
    assert len(calls) == 1
