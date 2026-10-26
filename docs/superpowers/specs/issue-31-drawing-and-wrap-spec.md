# Design Specification: Quire Drawing Objects, Text Wrapping, and Linked Text Boxes

## 1. Overview & Objectives

This specification defines the architecture, data models, layout algorithms, and interactive manipulation primitives for DrawingML objects, text wrapping, and story-linked text boxes in the ATBOffice Quire (Word 2003 port) word processing module.
It addresses [Issue #31](https://github.com/aitobox/ATBOffice/issues/31) and satisfies the following criteria:

1. **Drawing Object Model (`src/atboffice/modules/writer/models/drawing.py`)**:
   - Unified support for inline and floating objects (pictures, shapes, text boxes, and groups).
   - Full 5-mode Word text wrapping semantics: `inline`, `square`, `tight`, `behind`, `inFront`, plus `topBottom`.
   - Positioning model with horizontal alignment (`left`, `center`, `right`, `inside`, `outside`) or offset relative to `page`, `margin`, `column`, `character`.
   - Vertical alignment (`top`, `center`, `bottom`, `inside`, `outside`) or offset relative to `page`, `margin`, `paragraph`, `line`.
   - 8-anchor resize handles (`nw`, `n`, `ne`, `e`, `se`, `s`, `sw`, `w`), proportional aspect locking, rotation snapping (15° increments with Shift or continuous), and fractional cropping (`Crop(l, t, r, b)`).
   - Lossless preservation dictionary (`raw_data`) to maintain original DrawingML XML fidelity on roundtripping.

2. **Text Wrap & Flow Engine (`src/atboffice/modules/writer/layout/wrap.py`)**:
   - Absolute coordinate resolution for floating objects on physical pages.
   - Line exclusion intervals calculation (`calculate_line_segments`): computes available horizontal spans `(start_x, end_x)` for paragraph lines passing around floating bounding boxes.
   - Support for `both`, `left-only`, `right-only`, or `largest-side` text flow around wrapped obstacles.
   - `topBottom` wrap mode clears line flow across full column width and pushes text below bottom margin of the obstacle.

3. **Linked Text Boxes (Story Chains) (`src/atboffice/modules/writer/layout/wrap.py`)**:
   - Support story chains across multiple text boxes (`tb_id`, `tb_link`, `chain_id`, `seq`).
   - Flow text into `seq=0`. When text height exceeds the box's inner height, cleanly segment text and cascade overflow runs into `seq=1`, `seq=2`, etc.
   - Handle dynamic chain addition, deletion, and disconnection without corruption or orphaned story loss.

4. **Verification Plan**:
   - Comprehensive test suite `tests/unit/writer/test_drawing_wrap.py` exercising model creation, 8-handle resizing, proportional scaling, rotation, cropping, wrap exclusion line segmentation, and linked text box overflow.

---

## 2. Architecture & Data Structures

### 2.1 Drawing Models (`src/atboffice/modules/writer/models/drawing.py`)

#### Enums
- `WrapMode(Enum)`:
  - `INLINE = "inline"`
  - `SQUARE = "square"`
  - `TIGHT = "tight"`
  - `BEHIND = "behind"`
  - `IN_FRONT = "inFront"`
  - `TOP_BOTTOM = "topBottom"`

- `WrapSide(Enum)`:
  - `BOTH = "both"`
  - `LEFT = "left"`
  - `RIGHT = "right"`
  - `LARGEST = "largest"`

- `AnchorHandle(Enum)`:
  - `NW = "nw"`, `N = "n"`, `NE = "ne"`, `E = "e"`
  - `SE = "se"`, `S = "s"`, `SW = "sw"`, `W = "w"`
  - `ROT = "rot"`

#### Value Objects
- `WrapDist`:
  - `top: float = 0.0` (pt)
  - `bottom: float = 0.0` (pt)
  - `left: float = 9.0` (pt)
  - `right: float = 9.0` (pt)

- `PositionH`:
  - `rel: str = "column"` (choices: `"page"`, `"margin"`, `"column"`, `"character"`, `"leftMargin"`, `"rightMargin"`, `"insideMargin"`, `"outsideMargin"`)
  - `align: str | None = None` (choices: `"left"`, `"center"`, `"right"`, `"inside"`, `"outside"`)
  - `offset: float = 0.0` (pt)
  - `percent: float | None = None`

- `PositionV`:
  - `rel: str = "paragraph"` (choices: `"page"`, `"margin"`, `"topMargin"`, `"bottomMargin"`, `"paragraph"`, `"line"`, `"insideMargin"`, `"outsideMargin"`)
  - `align: str | None = None` (choices: `"top"`, `"center"`, `"bottom"`, `"inside"`, `"outside"`)
  - `offset: float = 0.0` (pt)
  - `percent: float | None = None`

- `FloatProperties`:
  - `wrap: WrapMode = WrapMode.SQUARE`
  - `side: WrapSide = WrapSide.BOTH`
  - `dist: WrapDist = field(default_factory=WrapDist)`
  - `pos_h: PositionH = field(default_factory=PositionH)`
  - `pos_v: PositionV = field(default_factory=PositionV)`
  - `z_index: int = 0`
  - `behind: bool = False`
  - `layout_in_cell: bool = False`

- `Crop`:
  - `left: float = 0.0` (fractional 0.0 ~ 1.0)
  - `top: float = 0.0`
  - `right: float = 0.0`
  - `bottom: float = 0.0`

- `LinkedTextBoxChain`:
  - `chain_id: str`
  - `seq: int = 0`
  - `next_chain_id: str | None = None`

#### Object Hierarchy
- `DrawingObject(RunItem)`:
  - `id: int`
  - `name: str = ""`
  - `width: float = 72.0` (pt)
  - `height: float = 72.0` (pt)
  - `rotation: float = 0.0` (degrees in [0, 360))
  - `float_pr: FloatProperties | None = None` (None indicates inline object)
  - `raw_data: dict[str, Any] = field(default_factory=dict)`

- `PictureItem(DrawingObject)`:
  - `image_part: str = ""`
  - `alt_text: str = ""`
  - `crop: Crop = field(default_factory=Crop)`
  - `natural_width: float = 72.0`
  - `natural_height: float = 72.0`
  - `brightness: float = 0.0`
  - `contrast: float = 0.0`
  - `grayscale: bool = False`
  - `washout: bool = False`

- `TextBoxItem(DrawingObject)`:
  - `story: Story = field(default_factory=Story)`
  - `chain: LinkedTextBoxChain | None = None`
  - `internal_margins: tuple[float, float, float, float] = (7.2, 3.6, 7.2, 3.6)`
  - `autofit: bool = False`
  - `vertical_align: str = "top"` (choices: `"top"`, `"center"`, `"bottom"`)

#### Manipulation Helpers
- `resize_object(obj, new_w, new_h, lock_aspect=False)`:
  Adjusts width and height, guaranteeing minimum dimension >= 2.0 pt. If `lock_aspect` is True, calculates maximum proportional ratio.
- `drag_handle_resize(obj, handle, dx, dy, lock_aspect=False) -> tuple[float, float, float, float]`:
  Calculates delta shifts `(new_w, new_h, delta_x, delta_y)` based on active anchor handle. Handles west/north drags by offsetting position so opposite corner remains stationary.
- `rotate_object(obj, angle_delta, snap_15=False)`:
  Updates `rotation = (rotation + angle_delta) % 360`. If `snap_15` is True, rounds to nearest 15-degree increment.
- `crop_object(pic, left=0.0, top=0.0, right=0.0, bottom=0.0)`:
  Updates crop parameters clamped between 0.0 and 0.99.
- `get_visible_dimensions(pic) -> tuple[float, float]`:
  Calculates effective visible width/height after applying crop fraction.

---

### 2.2 Text Wrapping Engine (`src/atboffice/modules/writer/layout/wrap.py`)

#### Coordinate Mapping
- `FloatBox`:
  - `x: float`, `y: float`, `w: float`, `h: float`
  - `wrap_mode: WrapMode`
  - `side: WrapSide`
  - `dist: WrapDist`
  - `z_index: int`
  - `behind: bool`
  - `item: DrawingObject`

- `resolve_float_box(item, page_dims, margin_dims, col_dims, para_top) -> FloatBox`:
  Computes exact top-left `(x, y)` and bounding box of a floating object on the physical page following Word 2003 alignment rules:
  - `pos_h`:
    - `page`: `x0 = 0`, `aw = page_w`
    - `margin`: `x0 = margin_left`, `aw = page_w - ml - mr`
    - `column`: `x0 = col_left`, `aw = col_w`
    - `align == 'left'`: `x = x0`
    - `align == 'center'`: `x = x0 + (aw - ow) / 2`
    - `align == 'right'`: `x = x0 + aw - ow`
    - `offset`: `x = x0 + off`
  - `pos_v`:
    - `page`: `y0 = 0`, `ah = page_h`
    - `margin`: `y0 = margin_top`, `ah = page_h - mt - mb`
    - `paragraph`: `y0 = para_top`
    - `align == 'top'`: `y = y0`
    - `align == 'center'`: `y = y0 + (ah - oh) / 2`
    - `align == 'bottom'`: `y = y0 + ah - oh`
    - `offset`: `y = y0 + off`

#### Line Obstacle Avoidance
- `calculate_line_segments(col_left, col_right, y, line_height, float_boxes) -> list[tuple[float, float]]`:
  1. Filters floating boxes that overlap line vertically: `box.y - dist.t <= y + line_height` and `box.y + box.h + dist.b >= y`.
  2. Filters out `WrapMode.BEHIND` and `WrapMode.IN_FRONT` (text does not avoid them).
  3. If any obstacle has `WrapMode.TOP_BOTTOM`: returns `[]` (entire line cannot be placed here; line must drop below obstacle).
  4. For `WrapMode.SQUARE` or `WrapMode.TIGHT`:
     - Identifies forbidden horizontal interval `[obs_left, obs_right] = [max(col_left, box.x - dist.l), min(col_right, box.x + box.w + dist.r)]`.
     - Subdivides `[col_left, col_right]` into non-overlapping left segment `[col_left, obs_left]` and right segment `[obs_right, col_right]`.
     - If `side == WrapSide.LEFT`: keeps only left segment.
     - If `side == WrapSide.RIGHT`: keeps only right segment.
     - If `side == WrapSide.LARGEST`: keeps whichever segment is wider.
     - If `side == WrapSide.BOTH`: keeps both segments if width >= minimum threshold (e.g. 18 pt).
  5. Returns remaining valid spans sorted from left to right.

---

### 2.3 Linked Text Boxes Engine (`src/atboffice/modules/writer/layout/wrap.py`)

- `TextBoxFlowResult`:
  - `placed_blocks: dict[int, list[LayoutLine]]`: Mapping of `box.id` to placed lines.
  - `overflow_story: Story | None`: Any remaining runs/paragraphs that did not fit across the entire chain.
  - `is_complete: bool`: True if all content in the story fit in the linked chain.

- `flow_linked_text_boxes(boxes: list[TextBoxItem], story: Story, line_layout_fn) -> TextBoxFlowResult`:
  1. Sorts `boxes` by `box.chain.seq` ascending (0, 1, 2, ...).
  2. Iterates through the story paragraphs and runs.
  3. For current box:
     - Usable width = `box.width - ins_l - ins_r`
     - Usable height = `box.height - ins_t - ins_b`
     - Lays out lines sequentially. Accumulates line heights until usable height would be exceeded.
  4. When usable height is reached:
     - Splits the paragraph at current line/character boundary.
     - Advances to the next linked text box (`seq + 1`).
     - Resumes layout in the next box.
  5. If all boxes are filled and content remains, returns unplaced content in `overflow_story` and sets `is_complete = False`.
  6. If content completes before exhausting all boxes, remaining downstream boxes receive empty content.

---

## 3. Edge Cases & Robustness Handling

1. **Aspect Ratio Lock**: When dragging diagonal handles (`nw`, `ne`, `se`, `sw`), images maintain aspect ratio unless Shift is held. For cardinal handles (`n`, `s`, `e`, `w`), one dimension is stretched independently.
2. **Minimum Dimensions**: Shapes and images cannot be resized smaller than 2x2 pt or inverted to negative dimensions.
3. **Position Clamping**: Out-of-bounds offsets are handled without crash; zero-width columns or boxes return empty segment lists gracefully.
4. **Broken Chains**: If a linked text box references a missing `next_chain_id` or non-sequential `seq`, the engine gracefully treats the chain as terminating at the last valid box.
5. **Lossless Roundtrip**: All unedited properties (DrawingML namespaces, `spPr`, `blipFill`, `w14` attributes) stored in `raw_data` are preserved.

---

## 4. Verification Plan

Test file: `tests/unit/writer/test_drawing_wrap.py`
1. **Model & Properties Tests**:
   - `test_drawing_object_defaults_and_enum`: Verify default fields, `WrapMode`, `WrapSide`, `AnchorHandle`.
   - `test_picture_item_crop_and_filters`: Test `Crop` bounds clamping, `get_visible_dimensions`, and image attributes.
2. **Manipulation Tests**:
   - `test_resize_object_free_and_proportional`: Verify 8-handle resizing and proportional lock.
   - `test_rotate_object_with_snapping`: Verify angle normalization [0, 360) and 15° snapping.
   - `test_crop_object`: Verify fractional cropping and visible width/height recalculation.
3. **Wrapping Calculation Tests**:
   - `test_resolve_float_box_alignments`: Test horizontal/vertical alignments against page, margin, and paragraph.
   - `test_line_segments_square_wrap_both_sides`: Verify text splitting into left and right spans around a centered box.
   - `test_line_segments_left_and_right_only`: Verify single-sided wrap behavior.
   - `test_line_segments_top_bottom_clearing`: Verify line rejection when overlapping a top/bottom wrap obstacle.
   - `test_behind_and_in_front_wrap_passthrough`: Verify no text obstruction when z-order is behind or inFront.
4. **Linked Text Boxes Tests**:
   - `test_linked_text_box_chain_overflow`: Verify multi-box overflow where content fills Box 0 and continues in Box 1.
   - `test_linked_text_box_complete_and_empty`: Verify downstream box state when upstream box fits entire story.
   - `test_linked_text_box_unplaced_overflow`: Verify detection of overflow when text exceeds all boxes in chain.

Execution:
`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/writer/test_drawing_wrap.py -v`
Followed by running full test suite:
`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/writer/ -v`
