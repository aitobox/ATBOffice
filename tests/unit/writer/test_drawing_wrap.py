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


def test_linked_text_boxes_overflow():
    from atboffice.modules.writer.layout.wrap import flow_linked_text_boxes
    from atboffice.modules.writer.models.document import Paragraph, Story, TextItem
    from atboffice.modules.writer.models.drawing import (
        LinkedTextBoxChain,
        TextBoxItem,
    )

    box0 = TextBoxItem(
        id=1,
        width=100.0,
        height=40.0,
        chain=LinkedTextBoxChain(chain_id="chain1", seq=0, next_chain_id="chain1_seq1"),
        internal_margins=(5.0, 5.0, 5.0, 5.0),
    )
    box1 = TextBoxItem(
        id=2,
        width=100.0,
        height=100.0,
        chain=LinkedTextBoxChain(chain_id="chain1", seq=1),
        internal_margins=(5.0, 5.0, 5.0, 5.0),
    )

    # Story with several paragraphs that will exceed Box 0 (usable height = 30.0)
    story = Story(
        paras=[
            Paragraph(runs=[TextItem(text="Line 1 in story.")]),
            Paragraph(runs=[TextItem(text="Line 2 in story.")]),
            Paragraph(runs=[TextItem(text="Line 3 in story.")]),
            Paragraph(runs=[TextItem(text="Line 4 in story.")]),
        ]
    )

    res = flow_linked_text_boxes([box0, box1], story)
    assert res.is_complete is True
    assert 1 in res.placed_blocks
    assert 2 in res.placed_blocks
    assert len(res.placed_blocks[1]) > 0
    assert len(res.placed_blocks[2]) > 0

    # Test overflowing completely when chain capacity is exceeded
    small_box = TextBoxItem(
        id=3,
        width=100.0,
        height=25.0,
        chain=LinkedTextBoxChain(chain_id="chain2", seq=0),
        internal_margins=(2.0, 2.0, 2.0, 2.0),
    )
    res_overflow = flow_linked_text_boxes([small_box], story)
    assert res_overflow.is_complete is False
    assert res_overflow.overflow_story is not None
    assert len(res_overflow.overflow_story.paras) > 0


def test_document_and_portions_integration():
    from atboffice.modules.writer.layout.portions import (
        PortionType,
        decompose_paragraph_to_portions,
    )
    from atboffice.modules.writer.models.document import (
        Document,
        Paragraph,
        TextItem,
        ilen,
        plain_text,
    )
    from atboffice.modules.writer.models.drawing import (
        FloatProperties,
        PictureItem,
        TextBoxItem,
        WrapMode,
    )

    doc = Document()
    p = Paragraph(id=10)

    # 1. Inline picture
    inline_pic = PictureItem(width=50.0, height=30.0)
    p.runs.append(TextItem(text="Hello "))
    p.runs.append(inline_pic)
    p.runs.append(TextItem(text=" world"))

    doc.main.paras.append(p)

    # Test ilen
    assert ilen(inline_pic) == 1

    # Decompose into portions: inline graphic should count for width & height
    portions = decompose_paragraph_to_portions(p, doc)
    graphic_portions = [pt for pt in portions if pt.type == PortionType.GRAPHIC]
    assert len(graphic_portions) == 1
    assert graphic_portions[0].width == 50.0
    assert graphic_portions[0].ascent == 30.0
    assert graphic_portions[0].counts_for_height is True

    # 2. Floating picture anchor
    p_float = Paragraph(id=11)
    float_pic = PictureItem(
        width=120.0,
        height=80.0,
        float_pr=FloatProperties(wrap=WrapMode.SQUARE),
    )
    p_float.runs.append(TextItem(text="Anchored "))
    p_float.runs.append(float_pic)

    float_portions = decompose_paragraph_to_portions(p_float, doc)
    float_graphic_portions = [pt for pt in float_portions if pt.type == PortionType.GRAPHIC]
    assert len(float_graphic_portions) == 1
    assert float_graphic_portions[0].width == 0.0
    assert float_graphic_portions[0].counts_for_height is False
    assert float_graphic_portions[0].data == float_pic


def test_wrap_sides_and_largest():
    from atboffice.modules.writer.layout.wrap import (
        FloatBox,
        calculate_line_segments,
    )
    from atboffice.modules.writer.models.drawing import (
        WrapDist,
        WrapMode,
        WrapSide,
    )

    # Obstacle placed slightly to the left of center in column [0, 400]
    # Box spans [100, 200] with 10 padding -> [90, 210]
    fb_both = FloatBox(
        x=100.0,
        y=50.0,
        w=100.0,
        h=100.0,
        wrap_mode=WrapMode.SQUARE,
        side=WrapSide.BOTH,
        dist=WrapDist(left=10.0, right=10.0, top=10.0, bottom=10.0),
    )

    # BOTH sides: left segment [0, 90] (width 90), right segment [210, 400] (width 190)
    segs_both = calculate_line_segments(0.0, 400.0, 80.0, 14.0, [fb_both])
    assert segs_both == [(0.0, 90.0), (210.0, 400.0)]

    # LEFT only: only segment to left of obstacle
    fb_left = FloatBox(
        x=100.0,
        y=50.0,
        w=100.0,
        h=100.0,
        wrap_mode=WrapMode.SQUARE,
        side=WrapSide.LEFT,
        dist=WrapDist(left=10.0, right=10.0, top=10.0, bottom=10.0),
    )
    segs_left = calculate_line_segments(0.0, 400.0, 80.0, 14.0, [fb_left])
    assert segs_left == [(0.0, 90.0)]

    # RIGHT only: only segment to right of obstacle
    fb_right = FloatBox(
        x=100.0,
        y=50.0,
        w=100.0,
        h=100.0,
        wrap_mode=WrapMode.SQUARE,
        side=WrapSide.RIGHT,
        dist=WrapDist(left=10.0, right=10.0, top=10.0, bottom=10.0),
    )
    segs_right = calculate_line_segments(0.0, 400.0, 80.0, 14.0, [fb_right])
    assert segs_right == [(210.0, 400.0)]

    # LARGEST: right segment (190) is wider than left (90)
    fb_largest = FloatBox(
        x=100.0,
        y=50.0,
        w=100.0,
        h=100.0,
        wrap_mode=WrapMode.SQUARE,
        side=WrapSide.LARGEST,
        dist=WrapDist(left=10.0, right=10.0, top=10.0, bottom=10.0),
    )
    segs_largest = calculate_line_segments(0.0, 400.0, 80.0, 14.0, [fb_largest])
    assert segs_largest == [(210.0, 400.0)]
