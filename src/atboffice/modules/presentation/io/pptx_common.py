"""Types and helpers shared by the pptx_reader modules."""

from __future__ import annotations

import math
import posixpath
from dataclasses import dataclass, field
from typing import Any

from atboffice.modules.presentation.models.designs import (
    DesignTemplate,
)
from atboffice.modules.presentation.models.shape import (
    Fill,
    Line,
    Shape,
)
from atboffice.modules.presentation.models.text import (
    TextBody,
)
from atboffice.vfs import etree as ET

# PresentationML & DrawingML Namespaces
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"


NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


REL_OFFICE_DOCUMENT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)


REL_SLIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"


REL_SLIDE_MASTER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"


REL_SLIDE_LAYOUT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"


REL_THEME = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"


REL_NOTES_SLIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"


REL_NOTES_MASTER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster"


REL_HANDOUT_MASTER = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/handoutMaster"
)


REL_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


REL_VIDEO = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/video"


REL_AUDIO = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/audio"


REL_MEDIA = "http://schemas.microsoft.com/office/2007/relationships/media"


REL_COMMENT_AUTHORS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors"
)


REL_COMMENTS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"


REL_AUTHORS_MODERN = "http://schemas.microsoft.com/office/2018/10/relationships/authors"


REL_COMMENTS_MODERN = "http://schemas.microsoft.com/office/2018/10/relationships/comments"


NS_P188 = "http://schemas.microsoft.com/office/powerpoint/2018/8/main"


EMUS_PER_PT = 12700.0


def safe_int(val: Any, default: int = 0) -> int:
    """Safely parse integers including float-like or percentage strings."""
    if val is None or isinstance(val, bool):
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val) if math.isfinite(val) else default
    s = str(val).strip().rstrip("%").strip()
    if not s:
        return default
    try:
        return int(s)
    except ValueError:
        try:
            f = float(s)
            return int(f) if math.isfinite(f) else default
        except (ValueError, TypeError):
            return default


def _theme_typeface(font: str | None, major: str | None, minor: str | None) -> str | None:
    """Theme font references (+mj-lt, +mn-lt, +mj-ea, …) to the master theme's faces.

    Only the Latin faces are read from the theme, so other slots fall back to them.
    """
    if not font or not font.startswith("+"):
        return font
    if font.startswith("+mj"):
        return major or minor or font
    if font.startswith("+mn"):
        return minor or major or font
    return font


def _resolve_theme_typefaces(shapes: list[Any], major: str | None, minor: str | None) -> None:
    """Replace theme font references on every run of the given shapes, in place."""
    if not major and not minor:
        return

    def fix_body(body: Any) -> None:
        if body is None:
            return
        runs = [r for p in getattr(body, "paragraphs", []) for r in p.runs]
        prompt = getattr(body, "prompt_run", None)
        if prompt is not None:
            runs.append(prompt)
        for run in runs:
            run.font = _theme_typeface(run.font, major, minor)
            run.font_ea = _theme_typeface(run.font_ea, major, minor)

    for sh in shapes:
        fix_body(getattr(sh, "text", None))
        tbl = getattr(sh, "tbl", None)
        if isinstance(tbl, dict):
            for row in tbl.get("rows", []):
                for cell in row.get("cells", []):
                    if isinstance(cell, dict):
                        fix_body(cell.get("tx"))
        kids = getattr(sh, "kids", None)
        if kids:
            _resolve_theme_typefaces(kids, major, minor)


def safe_float(val: Any, default: float = 0.0) -> float:
    """Safely parse finite floats including percentage strings, rejecting NaN/Inf."""
    if val is None or isinstance(val, bool):
        return default
    if isinstance(val, (int, float)):
        f = float(val)
        return f if math.isfinite(f) else default
    s = str(val).strip().rstrip("%").strip()
    if not s:
        return default
    try:
        f = float(s)
        return f if math.isfinite(f) else default
    except (ValueError, TypeError):
        return default


def clamp_alpha(val: Any, default: float = 1.0) -> float:
    """Clamp alpha values safely into [0.0, 1.0]."""
    f = safe_float(val, default)
    return max(0.0, min(1.0, f))


def emu_to_pt(emu: float | int | str | None, default: float = 0.0) -> float:
    """Convert EMUs (English Metric Units) to points (1 pt = 12700 EMUs)."""
    if emu is None:
        return default
    val = safe_float(emu, float("nan"))
    if not math.isfinite(val):
        return default
    return round(val / EMUS_PER_PT, 2)


def _local_tag(tag: str) -> str:
    """Extract local XML tag name ignoring namespace prefix or URI."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    if ":" in tag:
        return tag.split(":", 1)[1]
    return tag


def _get_child(elem: ET.Element | None, local_name: str) -> ET.Element | None:
    """Find first child element matching local name."""
    if elem is None:
        return None
    for child in elem:
        if _local_tag(child.tag) == local_name:
            return child
    return None


def _get_children(elem: ET.Element | None, local_name: str | None = None) -> list[ET.Element]:
    """Find all children matching local name, or all if local_name is None."""
    if elem is None:
        return []
    if local_name is None:
        return list(elem)
    return [c for c in elem if _local_tag(c.tag) == local_name]


_OFFICE_DIAGRAM_URN = "urn:microsoft.com/office/officeart/2005/8/"


def _diagram_color_style(dm_xml: ET.Element) -> tuple[str | None, str | None]:
    """Map an Office diagram's colours/quick style ids to the engine's ids.

    Mirrors lectern/js/smartart-io.js: ``colors/accent1_2`` → ``accent1``,
    ``colors/colorful*`` → ``colorful``; intense/3D quick styles → ``intense``,
    moderate → ``moderate``, simple2/3 → ``subtle``.
    """
    import re

    cs_id = qs_id = ""
    for el in dm_xml.iter():
        if _local_tag(el.tag) == "prSet" and el.attrib.get("csTypeId"):
            cs_id = el.attrib.get("csTypeId", "")
            qs_id = el.attrib.get("qsTypeId", "")
            break

    colors: str | None = None
    prefix = _OFFICE_DIAGRAM_URN + "colors/"
    if cs_id.startswith(prefix):
        name = cs_id[len(prefix) :]
        if re.search("colorful", name, re.IGNORECASE):
            colors = "colorful"
        else:
            m = re.match(r"accent([1-6])", name)
            if m:
                colors = f"accent{m.group(1)}"

    style: str | None = None
    prefix = _OFFICE_DIAGRAM_URN + "quickstyle/"
    if qs_id.startswith(prefix):
        name = qs_id[len(prefix) :]
        if re.search(r"intense|3d|polished|cartoon", name, re.IGNORECASE):
            style = "intense"
        elif re.search(r"moderate|simple[45]", name, re.IGNORECASE):
            style = "moderate"
        elif re.search(r"simple[23]", name, re.IGNORECASE):
            style = "subtle"
    return colors, style


def _resolve_path(base_part: str, relative_target: str) -> str:
    """Resolve an OPC relative target path from the base part directory."""
    if not base_part:
        return relative_target.lstrip("/")
    base_dir = posixpath.dirname(base_part)
    resolved = posixpath.normpath(posixpath.join(base_dir, relative_target))
    return resolved.lstrip("/")


def _get_attr(elem: ET.Element | None, name: str, default: str | None = None) -> str | None:
    """Get attribute by local name or Clark name."""
    if elem is None:
        return default
    for k, v in elem.attrib.items():
        if _local_tag(k) == name or k == name:
            return v
    return default


def _mirror_in_group(
    shape: Shape,
    gx: float,
    gy: float,
    gw: float,
    gh: float,
    flip_h: bool,
    flip_v: bool,
) -> None:
    """Bake a flipped group's mirror into a child shape (absolute coordinates).

    The child's box is reflected across the group's vertical/horizontal centre line,
    leaf shapes toggle their own flip flag, and rotation is negated because a single
    reflection reverses the rotation direction (two reflections are a 180° turn and
    keep it). Nested groups recurse so every descendant (also stored in absolute
    coordinates) is reflected once.
    """
    if flip_h:
        shape.x = round(gx + gw - (shape.x - gx) - shape.w, 2)
    if flip_v:
        shape.y = round(gy + gh - (shape.y - gy) - shape.h, 2)
    if shape.rot and flip_h != flip_v:
        shape.rot = round((360.0 - shape.rot) % 360.0, 2)
    if shape.type == "group" and shape.kids:
        for kid in shape.kids:
            _mirror_in_group(kid, gx, gy, gw, gh, flip_h, flip_v)
        return
    if flip_h:
        shape.flip_h = not shape.flip_h
    if flip_v:
        shape.flip_v = not shape.flip_v


@dataclass
class PlaceholderTemplate:
    type: str
    idx: int
    shape_id: str
    xfrm: tuple[float, float, float, float, float] | None = None
    fill: Fill | None = None
    line: Line | None = None
    text_body: TextBody | None = None
    # <p:ph hasCustomPrompt="1">: the layout's own text is the slide's prompt
    custom_prompt: bool = False
    # The placeholder's <a:lstStyle> levels: what slides inherit (its sample paragraphs'
    # own formatting stays on the layout)
    lst_levels: dict[int, dict[str, Any]] = field(default_factory=dict)


@dataclass
class MasterInfo:
    master_path: str
    placeholders: list[PlaceholderTemplate]
    title_style: dict[int, dict[str, Any]]
    body_style: dict[int, dict[str, Any]]
    other_style: dict[int, dict[str, Any]]
    major_font: str | None = None
    minor_font: str | None = None
    decorations: list[Shape] = field(default_factory=list)
    bg: Fill | None = None
    design: DesignTemplate | None = None
    clr_map: dict[str, str] = field(default_factory=dict)
    theme_path: str = ""


@dataclass
class LayoutInfo:
    layout_path: str
    master: MasterInfo | None
    placeholders: list[PlaceholderTemplate]
    decorations: list[Shape] = field(default_factory=list)
    bg: Fill | None = None
    show_master: bool = True
    layout_type: str = ""
    clr_map_ovr: dict[str, str] = field(default_factory=dict)


def _guide_env(w: float, h: float) -> dict[str, float]:
    ssv = min(w, h)
    ls = max(w, h)
    env: dict[str, float] = {
        "w": w,
        "h": h,
        "l": 0.0,
        "t": 0.0,
        "r": w,
        "b": h,
        "hc": w / 2.0,
        "vc": h / 2.0,
        "ls": ls,
        "ss": ssv,
        "cd2": 10800000.0,
        "cd4": 5400000.0,
        "cd8": 2700000.0,
        "3cd4": 16200000.0,
        "3cd8": 8100000.0,
        "5cd8": 13500000.0,
        "7cd8": 18900000.0,
    }
    for d in (2, 3, 4, 5, 6, 8, 10, 12, 16, 32):
        env[f"wd{d}"] = w / d
        env[f"hd{d}"] = h / d
        env[f"ssd{d}"] = ssv / d
    return env


def _eval_guides(guide_list: list[ET.Element], env: dict[str, float]) -> dict[str, float]:
    def val(tok: str | None) -> float:
        if tok is None:
            return 0.0
        if tok in env:
            return env[tok]
        return safe_float(tok, 0.0)

    def rad(a: float) -> float:
        return (a / 60000.0) * math.pi / 180.0

    for gd in guide_list:
        name = _get_attr(gd, "name")
        fmla = (_get_attr(gd, "fmla") or "").strip().split()
        if not name or not fmla:
            continue
        op = fmla[0]
        a1 = fmla[1] if len(fmla) > 1 else None
        b1 = fmla[2] if len(fmla) > 2 else None
        c1 = fmla[3] if len(fmla) > 3 else None
        x = val(a1)
        y = val(b1)
        z = val(c1)
        r = 0.0
        if op == "val":
            r = x
        elif op == "*/":
            r = (x * y) / z if z != 0.0 else 0.0
        elif op == "+-":
            r = x + y - z
        elif op == "+/":
            r = (x + y) / z if z != 0.0 else 0.0
        elif op == "?:":
            r = y if x > 0.0 else z
        elif op == "abs":
            r = abs(x)
        elif op == "at2":
            r = (math.atan2(y, x) * 180.0 / math.pi) * 60000.0
        elif op == "cat2":
            r = x * math.cos(math.atan2(z, y))
        elif op == "sat2":
            r = x * math.sin(math.atan2(z, y))
        elif op == "cos":
            r = x * math.cos(rad(y))
        elif op == "sin":
            r = x * math.sin(rad(y))
        elif op == "tan":
            r = x * math.tan(rad(y))
        elif op == "max":
            r = max(x, y)
        elif op == "min":
            r = min(x, y)
        elif op == "mod":
            r = math.sqrt(x * x + y * y + z * z)
        elif op == "pin":
            r = x if y < x else (z if y > z else y)
        elif op == "sqrt":
            r = math.sqrt(max(0.0, x))
        env[name] = r if math.isfinite(r) else 0.0
    return env
