"""DrawingML and Word 2003 drawing object models for Quire word processing module.

Includes data models for inline and floating pictures, shapes, text boxes,
positioning, text wrapping modes, manipulation handles, and linked text boxes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from atboffice.modules.writer.models.document import RunItem, Story
from atboffice.modules.writer.models.properties import RunProperties


class WrapMode(StrEnum):
    """Text wrapping mode around a drawing object."""

    INLINE = "inline"
    SQUARE = "square"
    TIGHT = "tight"
    BEHIND = "behind"
    IN_FRONT = "inFront"
    TOP_BOTTOM = "topBottom"


class WrapSide(StrEnum):
    """Side on which text wraps around a floating obstacle."""

    BOTH = "both"
    LEFT = "left"
    RIGHT = "right"
    LARGEST = "largest"


class AnchorHandle(StrEnum):
    """8-point selection/resize and rotation anchor handles."""

    NW = "nw"
    N = "n"
    NE = "ne"
    E = "e"
    SE = "se"
    S = "s"
    SW = "sw"
    W = "w"
    ROT = "rot"


@dataclass
class WrapDist:
    """Distance padding between floating obstacle and wrapped text (points)."""

    top: float = 0.0
    bottom: float = 0.0
    left: float = 9.0
    right: float = 9.0


@dataclass
class PositionH:
    """Horizontal positioning properties for a floating object.

    rel choices: page, margin, column, character, leftMargin, rightMargin,
                 insideMargin, outsideMargin
    """

    rel: str = "column"
    align: str | None = None  # left, center, right, inside, outside
    offset: float = 0.0  # offset in points
    percent: float | None = None


@dataclass
class PositionV:
    """Vertical positioning properties for a floating object.

    rel choices: page, margin, topMargin, bottomMargin, paragraph, line,
                 insideMargin, outsideMargin
    """

    rel: str = "paragraph"
    align: str | None = None  # top, center, bottom, inside, outside
    offset: float = 0.0  # offset in points
    percent: float | None = None


@dataclass
class FloatProperties:
    """Floating layout properties for anchored objects."""

    wrap: WrapMode = WrapMode.SQUARE
    side: WrapSide = WrapSide.BOTH
    dist: WrapDist = field(default_factory=WrapDist)
    pos_h: PositionH = field(default_factory=PositionH)
    pos_v: PositionV = field(default_factory=PositionV)
    z_index: int = 0
    behind: bool = False
    layout_in_cell: bool = False


@dataclass
class Crop:
    """Fractional cropping offsets (0.0 to 1.0) on picture edges."""

    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0


@dataclass
class LinkedTextBoxChain:
    """Pointer and sequence info for story-linked text boxes."""

    chain_id: str = ""
    seq: int = 0
    next_chain_id: str | None = None


@dataclass
class DrawingObject(RunItem):
    """Base class for inline and floating drawing objects."""

    id: int = 0
    name: str = ""
    width: float = 72.0
    height: float = 72.0
    rotation: float = 0.0
    float_pr: FloatProperties | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: int = 0,
        name: str = "",
        width: float = 72.0,
        height: float = 72.0,
        rotation: float = 0.0,
        float_pr: FloatProperties | None = None,
        r_pr: RunProperties | None = None,
        raw_data: dict[str, Any] | None = None,
        t: str = "drawing",
    ) -> None:
        super().__init__(t=t, r_pr=r_pr or RunProperties())
        self.id = id
        self.name = name
        self.width = float(width)
        self.height = float(height)
        self.rotation = float(rotation)
        self.float_pr = float_pr
        self.raw_data = raw_data or {}


@dataclass
class PictureItem(DrawingObject):
    """Picture / Image drawing object."""

    image_part: str = ""
    alt_text: str = ""
    crop: Crop = field(default_factory=Crop)
    natural_width: float = 72.0
    natural_height: float = 72.0
    brightness: float = 0.0
    contrast: float = 0.0
    grayscale: bool = False
    washout: bool = False

    def __init__(
        self,
        id: int = 0,
        name: str = "",
        width: float = 72.0,
        height: float = 72.0,
        rotation: float = 0.0,
        float_pr: FloatProperties | None = None,
        r_pr: RunProperties | None = None,
        raw_data: dict[str, Any] | None = None,
        image_part: str = "",
        alt_text: str = "",
        crop: Crop | None = None,
        natural_width: float | None = None,
        natural_height: float | None = None,
        brightness: float = 0.0,
        contrast: float = 0.0,
        grayscale: bool = False,
        washout: bool = False,
    ) -> None:
        super().__init__(
            id=id,
            name=name,
            width=width,
            height=height,
            rotation=rotation,
            float_pr=float_pr,
            r_pr=r_pr,
            raw_data=raw_data,
            t="picture",
        )
        self.image_part = image_part
        self.alt_text = alt_text
        self.crop = crop or Crop()
        self.natural_width = float(natural_width if natural_width is not None else width)
        self.natural_height = float(natural_height if natural_height is not None else height)
        self.brightness = float(brightness)
        self.contrast = float(contrast)
        self.grayscale = bool(grayscale)
        self.washout = bool(washout)


@dataclass
class TextBoxItem(DrawingObject):
    """Text box drawing object that contains its own Story."""

    story: Story = field(default_factory=Story)
    chain: LinkedTextBoxChain | None = None
    internal_margins: tuple[float, float, float, float] = (7.2, 3.6, 7.2, 3.6)
    autofit: bool = False
    vertical_align: str = "top"  # top, center, bottom

    def __init__(
        self,
        id: int = 0,
        name: str = "",
        width: float = 72.0,
        height: float = 72.0,
        rotation: float = 0.0,
        float_pr: FloatProperties | None = None,
        r_pr: RunProperties | None = None,
        raw_data: dict[str, Any] | None = None,
        story: Story | None = None,
        chain: LinkedTextBoxChain | None = None,
        internal_margins: tuple[float, float, float, float] = (7.2, 3.6, 7.2, 3.6),
        autofit: bool = False,
        vertical_align: str = "top",
    ) -> None:
        super().__init__(
            id=id,
            name=name,
            width=width,
            height=height,
            rotation=rotation,
            float_pr=float_pr,
            r_pr=r_pr,
            raw_data=raw_data,
            t="textbox",
        )
        self.story = story or Story()
        self.chain = chain
        self.internal_margins = internal_margins
        self.autofit = autofit
        self.vertical_align = vertical_align


# ---------------------------------------------------------------------------
# Object Manipulation & Transformation Utilities
# ---------------------------------------------------------------------------


def resize_object(
    obj: DrawingObject,
    new_w: float,
    new_h: float,
    lock_aspect: bool = False,
) -> None:
    """Resize drawing object with optional aspect ratio preservation."""
    min_dim = 2.0
    w0 = max(min_dim, obj.width)
    h0 = max(min_dim, obj.height)

    nw = max(min_dim, float(new_w))
    nh = max(min_dim, float(new_h))

    if lock_aspect:
        ratio = max(nw / w0, nh / h0)
        nw = max(min_dim, round(w0 * ratio, 2))
        nh = max(min_dim, round(h0 * ratio, 2))
    else:
        nw = round(nw, 2)
        nh = round(nh, 2)

    obj.width = nw
    obj.height = nh


def drag_handle_resize(
    obj: DrawingObject,
    handle: AnchorHandle,
    dx: float,
    dy: float,
    lock_aspect: bool = False,
) -> tuple[float, float, float, float]:
    """Calculate new dimensions and origin offsets when dragging a handle.

    Returns:
        (new_width, new_height, delta_x, delta_y)
    """
    min_dim = 2.0
    w0 = max(min_dim, obj.width)
    h0 = max(min_dim, obj.height)
    h_str = handle.value

    # Horizontal delta
    if "e" in h_str:
        nw = w0 + dx
    elif "w" in h_str:
        nw = w0 - dx
    else:
        nw = w0

    # Vertical delta
    if "s" in h_str:
        nh = h0 + dy
    elif "n" in h_str:
        nh = h0 - dy
    else:
        nh = h0

    is_corner = len(h_str) == 2
    if is_corner and lock_aspect:
        ratio = max(nw / w0, nh / h0)
        nw = w0 * ratio
        nh = h0 * ratio

    nw = max(min_dim, round(nw, 2))
    nh = max(min_dim, round(nh, 2))

    # Origin offset when dragging west or north handles
    dxl = round(w0 - nw, 2) if "w" in h_str else 0.0
    dyt = round(h0 - nh, 2) if "n" in h_str else 0.0

    obj.width = nw
    obj.height = nh

    if obj.float_pr and (dxl != 0.0 or dyt != 0.0):
        obj.float_pr.pos_h.offset = round(obj.float_pr.pos_h.offset + dxl, 2)
        obj.float_pr.pos_v.offset = round(obj.float_pr.pos_v.offset + dyt, 2)

    return nw, nh, dxl, dyt


def rotate_object(
    obj: DrawingObject,
    delta_degrees: float,
    snap_15: bool = False,
) -> None:
    """Rotate drawing object by delta degrees with optional 15-degree snapping."""
    ang = (obj.rotation + delta_degrees) % 360.0
    if snap_15:
        ang = round(ang / 15.0) * 15.0
    ang = (ang % 360.0 + 360.0) % 360.0
    obj.rotation = round(ang, 1)


def crop_object(
    pic: PictureItem,
    left: float = 0.0,
    top: float = 0.0,
    right: float = 0.0,
    bottom: float = 0.0,
) -> None:
    """Set fractional cropping offsets on picture edges [0.0, 0.99]."""
    pic.crop.left = max(0.0, min(0.99, float(left)))
    pic.crop.top = max(0.0, min(0.99, float(top)))
    pic.crop.right = max(0.0, min(0.99 - pic.crop.left, float(right)))
    pic.crop.bottom = max(0.0, min(0.99 - pic.crop.top, float(bottom)))


def get_visible_dimensions(pic: PictureItem) -> tuple[float, float]:
    """Return visible width and height of picture after cropping."""
    c = pic.crop
    fw = max(0.01, 1.0 - c.left - c.right)
    fh = max(0.01, 1.0 - c.top - c.bottom)
    return round(pic.width * fw, 2), round(pic.height * fh, 2)
