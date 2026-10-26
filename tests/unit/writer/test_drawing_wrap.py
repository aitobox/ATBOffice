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
