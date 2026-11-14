"""GUI tests for render caching, paint bounds guards, and incremental thumbnails."""

from __future__ import annotations

import math

from PySide6.QtCore import QBuffer, QIODevice, QRectF
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QStyleOptionGraphicsItem

from atboffice.modules.presentation.models.media_item import MediaItem
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Fill, Line, Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import Paragraph, Run, TextBody
from atboffice.modules.presentation.slideshow.transitions import render_slide_to_image
from atboffice.modules.presentation.views import background_renderer, text_editor
from atboffice.modules.presentation.views.shape_item import ShapeGraphicsItem
from atboffice.modules.presentation.views.text_editor import (
    ShapeTextEditorItem,
    solve_norm_autofit_scale,
)
from atboffice.modules.presentation.views.workspace import (
    LecternWorkspace,
    render_slide_thumbnail,
)


def _make_tiny_png_bytes() -> bytes:
    img = QImage(4, 4, QImage.Format.Format_ARGB32)
    img.fill(0xFF336699)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def test_shape_paint_handles_none_fill_line_bad_alpha_zero_dash_and_corrupt_image(qapp):
    """ShapeGraphicsItem.paint handles None fill/line, NaN alpha, zero dashes, and bad images."""
    pix = QPixmap(200, 150)
    pix.fill(0xFFFFFFFF)
    painter = QPainter(pix)
    opt = QStyleOptionGraphicsItem()

    try:
        sh_none = Shape(id="s_none", type="shape", geom="rect", x=0, y=0, w=80, h=40)
        sh_none.fill = None  # type: ignore[assignment]
        sh_none.line = None  # type: ignore[assignment]
        item_none = ShapeGraphicsItem(sh_none)
        item_none.paint(painter, opt, None)

        sh_bad = Shape(
            id="s_bad",
            type="shape",
            geom="rect",
            x=0,
            y=0,
            w=80,
            h=40,
            fill=Fill(type="solid", color="#112233", alpha=float("nan")),
            line=Line(type="solid", color="#445566", width=1.0, custom_dash=[0.0, -1.0]),
        )
        item_bad = ShapeGraphicsItem(sh_bad)
        item_bad.paint(painter, opt, None)

        sh_img = Shape(
            id="s_img",
            type="image",
            geom="rect",
            x=0,
            y=0,
            w=80,
            h=60,
            media_item=MediaItem(
                media_type="video",
                media_path="ppt/media/bad.mp4",
                poster_bytes=b"corrupt-img-bytes",
            ),
        )
        item_img = ShapeGraphicsItem(sh_img)
        item_img.paint(painter, opt, None)
        assert getattr(item_img, "_media_decode_failed", False) is True
    finally:
        painter.end()


def test_shape_image_pixmap_is_cached_across_repaints(qapp, monkeypatch):
    """Decoding image bytes happens once when repainting the same media payload."""
    png_bytes = _make_tiny_png_bytes()
    sh = Shape(
        id="s_cached_img",
        type="image",
        geom="rect",
        x=0,
        y=0,
        w=100,
        h=80,
        media_item=MediaItem(
            media_type="video",
            media_path="ppt/media/ok.mp4",
            poster_bytes=png_bytes,
        ),
    )
    item = ShapeGraphicsItem(sh)

    calls = 0
    orig_from_data = QImage.fromData

    def counting_from_data(*args, **kwargs):
        nonlocal calls
        calls += 1
        return orig_from_data(*args, **kwargs)

    monkeypatch.setattr(QImage, "fromData", counting_from_data)

    pix = QPixmap(120, 100)
    opt = QStyleOptionGraphicsItem()
    for _ in range(3):
        painter = QPainter(pix)
        try:
            item.paint(painter, opt, None)
        finally:
            painter.end()

    assert calls == 1
    assert item._cached_pixmap is not None
    assert item._cached_media_key is not None


def test_text_autofit_handles_explicit_none_marl_indent_and_caps_steps(qapp):
    """Autofit measurement/render tolerates explicit None marL/indent and caches result."""
    tb = TextBody(
        autofit="norm",
        paragraphs=[
            Paragraph(
                runs=[Run(text="Overflowing text " * 25, size=24.0)],
                props={"marL": None, "indent": None, "bu": {"t": "char", "ch": "•"}},
            )
        ],
    )
    scale, red = solve_norm_autofit_scale(tb, avail_w=120.0, avail_h=40.0)
    assert math.isfinite(scale) and 0.1 <= scale <= 1.0
    assert math.isfinite(red) and 0.0 <= red <= 0.25

    sh = Shape(id="s_txt", type="text", geom="rect", x=0, y=0, w=120, h=50, text=tb)
    item = ShapeGraphicsItem(sh)
    pix = QPixmap(140, 70)
    opt = QStyleOptionGraphicsItem()
    painter = QPainter(pix)
    try:
        item.paint(painter, opt, None)
        ShapeTextEditorItem.render_static_text(painter, tb, QRectF(4, 4, 110, 40))
    finally:
        painter.end()

    assert hasattr(item, "_cached_autofit") and item._cached_autofit is not None


def test_background_renderer_zero_size_rect_and_cache_clear(qapp):
    """Zero/negative paint rects never crash QPixmap.scaled, and cache clears cleanly."""
    pix = QPixmap(64, 64)
    painter = QPainter(pix)
    try:
        background_renderer.paint_fill_rect(
            painter,
            QRectF(0.0, 0.0, 0.0, 0.0),
            Fill(type="img", image_path="羊皮纸"),
            None,
        )
    finally:
        painter.end()

    _ = background_renderer.get_procedural_texture("羊皮纸")
    assert len(background_renderer._TEXTURE_CACHE) >= 1
    background_renderer.clear_texture_cache()
    assert len(background_renderer._TEXTURE_CACHE) == 0

    # Also check offscreen render helpers handle empty/degenerate slides safely
    pres = Presentation.create_new(title="Deg", empty=True)
    sl = Slide(id="s1", layout="blank")
    sl.add_shape(Shape(id="tb1", type="table", x=10, y=10, w=100, h=60, tbl={"cols": [0.0], "rows": [{"cells": []}]}))
    pres.slides.append(sl)
    assert render_slide_thumbnail(sl, pres, width=0).width() >= 1
    assert render_slide_to_image(sl, pres, width=0, height=0).width() >= 1


def test_incremental_thumbnails_cancel_stale_generation_on_reload(qtbot, monkeypatch):
    """Chunked thumbnails increment _thumb_load_gen and cancel stale batches on reload."""
    pres15 = Presentation.create_new(title="Many", empty=True)
    for idx in range(15):
        pres15.slides.append(Slide(id=f"s15_{idx}", layout="blank"))

    pres3 = Presentation.create_new(title="Few", empty=True)
    for idx in range(3):
        pres3.slides.append(Slide(id=f"s3_{idx}", layout="blank"))

    ws = LecternWorkspace(presentation=pres15)
    qtbot.addWidget(ws)
    ws.show()
    gen1 = ws._thumb_load_gen

    # Immediately reload smaller deck before deferred chunks settle
    ws.load_presentation(pres3)
    gen2 = ws._thumb_load_gen
    assert gen2 > gen1

    qtbot.waitUntil(lambda: ws.thumbnail_list.count() == 3, timeout=2000)
    # Process remaining queued QTimer callbacks and ensure count remains 3
    qapp = qtbot
    _ = qapp
    from PySide6.QtWidgets import QApplication

    QApplication.processEvents()
    QApplication.processEvents()
    assert ws.thumbnail_list.count() == 3
    assert ws.sorter_view._thumb_load_gen >= 1
    assert len(ws.sorter_view.cards) == 3
