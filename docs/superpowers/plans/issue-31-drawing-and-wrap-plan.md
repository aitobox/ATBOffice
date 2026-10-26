# Quire Drawing Objects, Text Wrapping, and Linked Text Boxes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement drawing object representations (pictures, shapes, text boxes), Word 2003 text wrapping modes, and linked text box story flowing for Quire.

**Architecture:** Create `src/atboffice/modules/writer/models/drawing.py` for DrawingML data models, manipulation transforms (8-handle resize, rotate, crop), and properties. Create `src/atboffice/modules/writer/layout/wrap.py` for floating coordinate resolution, line obstacle avoidance calculations, and linked text box story overflow layout. Integrate with `document.py` and `portions.py`.

**Tech Stack:** Python 3.12+, PySide6, pytest.

**Spec:** `docs/superpowers/specs/issue-31-drawing-and-wrap-spec.md`

## Global Constraints
- Target Python 3.12+ with strict typing and dataclasses.
- Pure algorithm layout logic without hard GUI dependencies; fully unit-testable via pytest.
- Maintain lossless preservation dictionary (`raw_data`) for unedited DrawingML properties.
- Full edge case safety: zero/negative dimension guards, coordinate clamping, empty chain handling.

---

### Task 1: Drawing Object Data Models & Manipulation Primitives

**Files:**
- Create: `src/atboffice/modules/writer/models/drawing.py`
- Test: `tests/unit/writer/test_drawing_wrap.py`

**Interfaces:**
- Produces:
  - `WrapMode(Enum)`: `INLINE`, `SQUARE`, `TIGHT`, `BEHIND`, `IN_FRONT`, `TOP_BOTTOM`
  - `WrapSide(Enum)`: `BOTH`, `LEFT`, `RIGHT`, `LARGEST`
  - `AnchorHandle(Enum)`: `NW`, `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `ROT`
  - `WrapDist`, `PositionH`, `PositionV`, `FloatProperties`, `Crop`, `LinkedTextBoxChain`
  - `DrawingObject`, `PictureItem`, `TextBoxItem`
  - `resize_object(obj, new_w, new_h, lock_aspect=False)`
  - `drag_handle_resize(obj, handle, dx, dy, lock_aspect=False) -> tuple[float, float, float, float]`
  - `rotate_object(obj, delta_degrees, snap_15=False)`
  - `crop_object(pic, left=0.0, top=0.0, right=0.0, bottom=0.0)`
  - `get_visible_dimensions(pic) -> tuple[float, float]`

- [ ] **Step 1: Write failing test for drawing models and manipulation**

```python
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

    # Rotate with 15 snap
    rotate_object(pic, 23.0, snap_15=True)
    assert pic.rotation == 30.0

    # Crop
    crop_object(pic, left=0.1, top=0.2, right=0.1, bottom=0.2)
    vw, vh = get_visible_dimensions(pic)
    assert round(vw, 1) == round(170.0 * 0.8, 1)
    assert round(vh, 1) == round(136.0 * 0.6, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_drawing_wrap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atboffice.modules.writer.models.drawing'`

- [ ] **Step 3: Implement `src/atboffice/modules/writer/models/drawing.py`**

Create `src/atboffice/modules/writer/models/drawing.py` containing complete enum declarations, dataclasses, bounds checking, and transformation functions.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_drawing_wrap.py -v`
Expected: PASS

- [ ] **Step 5: Commit progress**

```bash
git add src/atboffice/modules/writer/models/drawing.py tests/unit/writer/test_drawing_wrap.py
git commit -m "feat(writer): implement drawing object models and manipulation primitives"
```

---

### Task 2: Text Wrapping & Line Obstacle Avoidance

**Files:**
- Create: `src/atboffice/modules/writer/layout/wrap.py`
- Modify: `tests/unit/writer/test_drawing_wrap.py`

**Interfaces:**
- Consumes: `DrawingObject`, `FloatProperties`, `WrapMode`, `WrapSide` from `models.drawing`
- Produces:
  - `FloatBox`: Bounding box of positioned float on physical page
  - `resolve_float_box(item, page_dims, margin_dims, col_dims, para_top) -> FloatBox`
  - `calculate_line_segments(col_left, col_right, y, line_height, float_boxes) -> list[tuple[float, float]]`

- [ ] **Step 1: Write failing test for wrapping calculations**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_drawing_wrap.py -k test_text_wrap_calculations -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atboffice.modules.writer.layout.wrap'`

- [ ] **Step 3: Implement `src/atboffice/modules/writer/layout/wrap.py` wrapping engine**

Implement `resolve_float_box` and `calculate_line_segments` supporting `square`, `tight`, `topBottom`, `behind`, and `inFront`, with support for wrap sides (`both`, `left`, `right`, `largest`).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_drawing_wrap.py -v`
Expected: PASS

- [ ] **Step 5: Commit progress**

```bash
git add src/atboffice/modules/writer/layout/wrap.py tests/unit/writer/test_drawing_wrap.py
git commit -m "feat(writer): implement floating positioning and line obstacle wrap engine"
```

---

### Task 3: Linked Text Boxes Story Flow

**Files:**
- Modify: `src/atboffice/modules/writer/layout/wrap.py`
- Modify: `tests/unit/writer/test_drawing_wrap.py`

**Interfaces:**
- Consumes: `TextBoxItem`, `LinkedTextBoxChain` from `models.drawing`
- Produces:
  - `TextBoxFlowResult`
  - `flow_linked_text_boxes(boxes: list[TextBoxItem], story: Story) -> TextBoxFlowResult`

- [ ] **Step 1: Write failing test for linked text boxes**

```python
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
        height=50.0,
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

    # Story with several paragraphs that will exceed Box 0 (usable height = 40.0)
    story = Story(
        paras=[
            Paragraph(runs=[TextItem(text="Line 1 in story. " * 3)]),
            Paragraph(runs=[TextItem(text="Line 2 in story. " * 3)]),
            Paragraph(runs=[TextItem(text="Line 3 in story. " * 3)]),
            Paragraph(runs=[TextItem(text="Line 4 in story. " * 3)]),
        ]
    )

    res = flow_linked_text_boxes([box0, box1], story)
    assert res.is_complete is True
    assert 1 in res.placed_blocks
    assert 2 in res.placed_blocks
    assert len(res.placed_blocks[1]) > 0
    assert len(res.placed_blocks[2]) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_drawing_wrap.py -k test_linked_text_boxes_overflow -v`
Expected: FAIL with `ImportError: cannot import name 'flow_linked_text_boxes'`

- [ ] **Step 3: Implement `flow_linked_text_boxes` in `src/atboffice/modules/writer/layout/wrap.py`**

Implement sequential overflow flow calculation that splits story paragraphs across linked boxes according to usable height and margins.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_drawing_wrap.py -v`
Expected: PASS

- [ ] **Step 5: Commit progress**

```bash
git add src/atboffice/modules/writer/layout/wrap.py tests/unit/writer/test_drawing_wrap.py
git commit -m "feat(writer): implement linked text boxes story overflow layout engine"
```

---

### Task 4: Integration with Document Models, Portions, and Full Verification

**Files:**
- Modify: `src/atboffice/modules/writer/models/document.py` (ensure DrawingObject run item integration)
- Modify: `src/atboffice/modules/writer/layout/portions.py` (ensure DrawingObject portion creation)
- Modify: `tests/unit/writer/test_drawing_wrap.py` (full test coverage)

**Interfaces:**
- Run full test suite: `pytest tests/unit/writer/test_drawing_wrap.py -v` and `pytest tests/unit/writer/ -v`.

- [ ] **Step 1: Write integration tests verifying document paragraphs containing drawings**
- [ ] **Step 2: Run tests and ensure portions properly handle DrawingObjects**
- [ ] **Step 3: Verify 100% tests pass across the entire writer test suite**
- [ ] **Step 4: Commit**

```bash
git add src/atboffice/modules/writer/ tests/unit/writer/test_drawing_wrap.py
git commit -m "feat(writer): integrate drawing objects into document run items and layout portions"
```
