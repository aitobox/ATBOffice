"""Unit tests for drawing objects, text wrapping modes, and linked text boxes."""

from __future__ import annotations

import pytest


def test_drawing_models_and_manipulation():
    from atboffice.modules.writer.models.drawing import (
        AnchorHandle,
        Crop,
        DrawingObject,
        FloatProperties,
        PictureItem,
        TextBoxItem,
        WrapMode,
        WrapSide,
        crop_object,
        drag_handle_resize,
        get_visible_dimensions,
        resize_object,
        rotate_object,
    )

    pic = PictureItem(width=100.0, height=80.0, natural_width=100.0, natural_height=80.0)
    assert pic.width == 100.0
    assert pic.height == 80.0
    assert pic.float_pr is None  # inline by default

    # Resize with aspect lock
    resize_object(pic, 150.0, 100.0, lock_aspect=True)
    assert pic.width == 150.0
    assert pic.height == 120.0  # 150 * (80 / 100)

    # 8-handle drag resize (se handle)
    nw, nh, dxl, dyt = drag_handle_resize(pic, AnchorHandle.SE, dx=20.0, dy=16.0, lock_aspect=True)
    assert nw == 170.0
    assert nh == 136.0
    assert dxl == 0.0
    assert dyt == 0.0

    # 8-handle drag resize (nw handle - offsets position)
    nw2, nh2, dxl2, dyt2 = drag_handle_resize(pic, AnchorHandle.NW, dx=-10.0, dy=-8.0, lock_aspect=False)
    assert nw2 == 180.0
    assert nh2 == 144.0
    assert dxl2 == -10.0
    assert dyt2 == -8.0

    # Rotate with 15 snap
    rotate_object(pic, 23.0, snap_15=True)
    assert pic.rotation == 30.0

    # Rotate normal
    rotate_object(pic, 12.0, snap_15=False)
    assert pic.rotation == 42.0

    # Crop
    crop_object(pic, left=0.1, top=0.2, right=0.1, bottom=0.2)
    vw, vh = get_visible_dimensions(pic)
    assert round(vw, 1) == round(180.0 * 0.8, 1)
    assert round(vh, 1) == round(144.0 * 0.6, 1)


def test_text_wrap_calculations():
    from atboffice.modules.writer.layout.wrap import (
        FloatBox,
        calculate_line_segments,
        resolve_float_box,
    )
    from atboffice.modules.writer.models.drawing import (
        FloatProperties,
        PictureItem,
        PositionH,
        PositionV,
        WrapDist,
        WrapMode,
        WrapSide,
    )

    pic = PictureItem(
        width=100.0,
        height=100.0,
        float_pr=FloatProperties(
            wrap=WrapMode.SQUARE,
            side=WrapSide.BOTH,
            dist=WrapDist(top=10.0, bottom=10.0, left=10.0, right=10.0),
            pos_h=PositionH(rel="column", align="center"),
            pos_v=PositionV(rel="paragraph", offset=20.0),
        ),
    )

    page_dims = (612.0, 792.0)
    margin_dims = (72.0, 72.0, 72.0, 72.0)  # ml, mr, mt, mb
    col_dims = (72.0, 468.0)  # left, width
    para_top = 100.0

    fb = resolve_float_box(pic, page_dims, margin_dims, col_dims, para_top)
    assert fb.w == 100.0
    assert fb.h == 100.0
    assert fb.x == 72.0 + (468.0 - 100.0) / 2  # center = 256.0
    assert fb.y == 120.0  # para_top + 20 = 120.0

    # Line overlapping obstacle vertically: y=150, height=14
    segs = calculate_line_segments(72.0, 540.0, 150.0, 14.0, [fb])
    assert len(segs) == 2
    # Left segment: [72.0, 256.0 - 10.0] = [72.0, 246.0]
    assert segs[0] == (72.0, 246.0)
    # Right segment: [256.0 + 100.0 + 10.0, 540.0] = [366.0, 540.0]
    assert segs[1] == (366.0, 540.0)

    # Line below obstacle: y=250 (fb.y + fb.h + 10 = 230)
    clear_segs = calculate_line_segments(72.0, 540.0, 250.0, 14.0, [fb])
    assert clear_segs == [(72.0, 540.0)]

    # Test topBottom wrap: rejects lines that overlap vertically
    pic_tb = PictureItem(
        width=100.0,
        height=50.0,
        float_pr=FloatProperties(
            wrap=WrapMode.TOP_BOTTOM,
            dist=WrapDist(top=10.0, bottom=10.0, left=10.0, right=10.0),
            pos_h=PositionH(rel="column", align="left"),
            pos_v=PositionV(rel="paragraph", offset=0.0),
        ),
    )
    fb_tb = resolve_float_box(pic_tb, page_dims, margin_dims, col_dims, 100.0)
    tb_segs = calculate_line_segments(72.0, 540.0, 120.0, 14.0, [fb_tb])
    assert tb_segs == []  # line rejected (pushed down)

    # Test behind & inFront wrap: does not obstruct line segments
    for mode in (WrapMode.BEHIND, WrapMode.IN_FRONT):
        pic_pass = PictureItem(
            width=100.0,
            height=50.0,
            float_pr=FloatProperties(wrap=mode),
        )
        fb_pass = resolve_float_box(pic_pass, page_dims, margin_dims, col_dims, 100.0)
        pass_segs = calculate_line_segments(72.0, 540.0, 120.0, 14.0, [fb_pass])
        assert pass_segs == [(72.0, 540.0)]
