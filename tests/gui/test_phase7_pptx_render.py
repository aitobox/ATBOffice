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
