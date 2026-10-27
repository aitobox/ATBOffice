"""XML and OpenXML DrawingML utilities for PresentationML serialization."""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from typing import Any

from atboffice.modules.presentation.models.designs import DesignTemplate, resolve_color
from atboffice.modules.presentation.models.shape import Fill, Line, Shadow

# Standard Namespaces
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
NS_P188 = "http://schemas.microsoft.com/office/powerpoint/2018/8/main"

ET.register_namespace("p", NS_P)
ET.register_namespace("a", NS_A)
ET.register_namespace("r", NS_R)
ET.register_namespace("p14", NS_P14)
ET.register_namespace("p188", NS_P188)

# Relationship Types
REL_OFFICE_DOCUMENT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
REL_SLIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
REL_SLIDE_MASTER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster"
REL_SLIDE_LAYOUT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
REL_THEME = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
REL_NOTES_SLIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
REL_NOTES_MASTER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster"
REL_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
REL_VIDEO = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/video"
REL_AUDIO = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/audio"
REL_MEDIA = "http://schemas.microsoft.com/office/2007/relationships/media"
REL_HYPERLINK = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
REL_DIAGRAM_DATA = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData"
REL_DIAGRAM_LAYOUT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramLayout"
)
REL_DIAGRAM_COLORS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramColors"
)
REL_DIAGRAM_STYLE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramQuickStyle"
)
REL_COMMENT_AUTHORS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors"
)
REL_COMMENTS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
)
REL_AUTHORS_MODERN = "http://schemas.microsoft.com/office/2018/10/relationships/authors"
REL_COMMENTS_MODERN = "http://schemas.microsoft.com/office/2018/10/relationships/comments"

# Content Types
CT_PRESENTATION = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
)
CT_SLIDESHOW = "application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml"
CT_TEMPLATE = "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"
CT_SLIDE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
CT_SLIDE_LAYOUT = "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"
CT_SLIDE_MASTER = "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"
CT_THEME = "application/vnd.openxmlformats-officedocument.theme+xml"
CT_NOTES_SLIDE = "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
CT_NOTES_MASTER = "application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"
CT_PRES_PROPS = "application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"
CT_VIEW_PROPS = "application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"
CT_TABLE_STYLES = "application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"
CT_CORE = "application/vnd.openxmlformats-package.core-properties+xml"
CT_APP = "application/vnd.openxmlformats-officedocument.extended-properties+xml"
CT_DIAGRAM_DATA = "application/vnd.openxmlformats-officedocument.drawingml.diagramData+xml"
CT_DIAGRAM_LAYOUT = "application/vnd.openxmlformats-officedocument.drawingml.diagramLayout+xml"
CT_DIAGRAM_COLORS = "application/vnd.openxmlformats-officedocument.drawingml.diagramColors+xml"
CT_DIAGRAM_STYLE = "application/vnd.openxmlformats-officedocument.drawingml.diagramStyle+xml"
CT_COMMENT_AUTHORS = (
    "application/vnd.openxmlformats-officedocument.presentationml.commentAuthors+xml"
)
CT_COMMENTS = "application/vnd.openxmlformats-officedocument.presentationml.comments+xml"
CT_AUTHORS_MODERN = "application/vnd.ms-powerpoint.authors+xml"
CT_COMMENTS_MODERN = "application/vnd.ms-powerpoint.comments+xml"

EMUS_PER_PT = 12700.0
XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
NS_DECL = f'xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}"'

SCHEME_COLORS = {
    "bg1",
    "tx1",
    "bg2",
    "tx2",
    "dk1",
    "lt1",
    "dk2",
    "lt2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
    "phClr",
}


def pt_to_emu(pt: float | int | None, default: int = 0) -> int:
    """Convert points to EMUs (1 pt = 12700 EMUs)."""
    if pt is None:
        return default
    try:
        return int(round(float(pt) * EMUS_PER_PT))
    except (ValueError, TypeError):
        return default


def emu_to_pt(emu: float | int | None, default: float = 0.0) -> float:
    """Convert EMUs to points."""
    if emu is None:
        return default
    try:
        return round(float(emu) / EMUS_PER_PT, 2)
    except (ValueError, TypeError):
        return default


def escape_xml(text: str | None) -> str:
    """Escape text for XML content or attribute values."""
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


class RelationshipBuilder:
    """Helper to collect and build package/part relationships XML."""

    def __init__(self, start_id: int = 1) -> None:
        self._rels: list[dict[str, str]] = []
        self._next_id = start_id

    def has_type(self, rel_type: str) -> bool:
        """Check if a relationship with the given type is already registered."""
        return any(r["type"] == rel_type for r in self._rels)

    @property
    def _relationships(self) -> list[Any]:
        """Compatibility property exposing objects with .type, .target, .id."""
        class _RelProxy:
            def __init__(self, d: dict[str, str]) -> None:
                self.id = d["id"]
                self.type = d["type"]
                self.target = d["target"]
                self.target_mode = d.get("target_mode", "Internal")

        return [_RelProxy(r) for r in self._rels]

    def add(
        self,
        rel_type: str,
        target: str,
        target_mode: str = "Internal",
        rel_id: str | None = None,
    ) -> str:
        """Add relationship and return its relationship ID (e.g. rId1)."""
        if not rel_id:
            rel_id = f"rId{self._next_id}"
            self._next_id += 1
        self._rels.append(
            {
                "id": rel_id,
                "type": rel_type,
                "target": target,
                "target_mode": target_mode,
            }
        )
        return rel_id

    def to_xml(self) -> bytes:
        """Serialize relationship list into .rels XML bytes."""
        root = ET.Element("Relationships", xmlns=NS_RELS)
        for r in self._rels:
            attrib = {"Id": r["id"], "Type": r["type"], "Target": r["target"]}
            if r["target_mode"] != "Internal":
                attrib["TargetMode"] = r["target_mode"]
            ET.SubElement(root, "Relationship", **attrib)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def color_to_xml(
    color: str | None,
    alpha: float | None = None,
    design: DesignTemplate | None = None,
) -> str:
    """Generate <a:srgbClr> or <a:schemeClr> XML element."""
    alpha_xml = ""
    if alpha is not None and 0.0 <= alpha < 1.0:
        alpha_val = int(round(alpha * 100000))
        alpha_xml = f'<a:alpha val="{alpha_val}"/>'

    c = color or "#000000"
    if c and not c.startswith("#") and c in SCHEME_COLORS:
        return (
            f'<a:schemeClr val="{c}">{alpha_xml}</a:schemeClr>'
            if alpha_xml
            else f'<a:schemeClr val="{c}"/>'
        )

    if design is not None:
        resolved = resolve_color(c, design).replace("#", "").upper()
    else:
        resolved = c.replace("#", "").upper()

    if len(resolved) != 6:
        resolved = "000000"

    return (
        f'<a:srgbClr val="{resolved}">{alpha_xml}</a:srgbClr>'
        if alpha_xml
        else f'<a:srgbClr val="{resolved}"/>'
    )


def fill_to_xml(
    fill: Fill | None,
    design: DesignTemplate | None = None,
    embed_rid: str | None = None,
) -> str:
    """Generate DrawingML fill XML (<a:solidFill>, <a:noFill>, etc.)."""
    if not fill or fill.type == "none":
        return "<a:noFill/>"

    if fill.type == "solid":
        clr_elem = color_to_xml(fill.color, fill.alpha, design)
        return f"<a:solidFill>{clr_elem}</a:solidFill>"

    if fill.type == "grad":
        stops = sorted(fill.stops, key=lambda s: s.get("p", 0.0))
        if len(stops) < 2:
            stops = [{"p": 0.0, "c": "#FFFFFF"}, {"p": 1.0, "c": "#000000"}]
        gs_items: list[str] = []
        for s in stops:
            pos = int(round(min(1.0, max(0.0, float(s.get("p", 0.0)))) * 100000))
            c_xml = color_to_xml(s.get("c", "#000000"), s.get("a", 1.0), design)
            gs_items.append(f'<a:gs pos="{pos}">{c_xml}</a:gs>')
        gs_lst = "".join(gs_items)
        ang_val = int(round((((fill.angle % 360) + 360) % 360) * 60000))
        lin = f'<a:lin ang="{ang_val}" scaled="1"/>'
        return f'<a:gradFill rotWithShape="1"><a:gsLst>{gs_lst}</a:gsLst>{lin}</a:gradFill>'

    if fill.type == "patt":
        prst = fill.pattern or "pct50"
        fg_clr = color_to_xml(fill.fg or "#000000", design=design)
        bg_clr = color_to_xml(fill.bg or "#FFFFFF", design=design)
        return (
            f'<a:pattFill prst="{prst}">'
            f"<a:fgClr>{fg_clr}</a:fgClr>"
            f"<a:bgClr>{bg_clr}</a:bgClr>"
            "</a:pattFill>"
        )

    if fill.type == "img" and embed_rid:
        return (
            f'<a:blipFill dpi="0" rotWithShape="1">'
            f'<a:blip r:embed="{embed_rid}"/>'
            "<a:stretch><a:fillRect/></a:stretch>"
            "</a:blipFill>"
        )

    return ""


def line_to_xml(
    line: Line | None,
    design: DesignTemplate | None = None,
    tag: str = "a:ln",
) -> str:
    """Generate DrawingML line XML (<a:ln>)."""
    if not line or line.width <= 0:
        return f"<{tag}><a:noFill/></{tag}>"

    w_emu = pt_to_emu(line.width, default=9525)
    attrs = [f'w="{w_emu}"']
    cap = getattr(line, "cap", None)
    if cap:
        attrs.append(f'cap="{cap}"')
    cmpd = getattr(line, "cmpd", None)
    if cmpd and cmpd != "sng":
        attrs.append(f'cmpd="{cmpd}"')

    attr_str = " ".join(attrs)
    alpha = getattr(line, "alpha", 1.0)
    c_xml = color_to_xml(line.color, alpha, design)
    inner = f"<a:solidFill>{c_xml}</a:solidFill>"

    if line.dash and line.dash != "solid":
        inner += f'<a:prstDash val="{line.dash}"/>'

    return f"<{tag} {attr_str}>{inner}</{tag}>"


def shadow_to_xml(
    shadow: Shadow | None,
    design: DesignTemplate | None = None,
) -> str:
    """Generate DrawingML shadow XML (<a:effectLst>)."""
    if not shadow:
        return ""
    dist_emu = pt_to_emu(shadow.dist, default=12700)
    blur_emu = pt_to_emu(shadow.blur, default=25400)
    dir_val = int(round((((shadow.angle % 360) + 360) % 360) * 60000))
    clr_xml = color_to_xml(shadow.color, shadow.alpha, design)
    return (
        "<a:effectLst>"
        f'<a:outerShdw blurRad="{blur_emu}" dist="{dist_emu}" '
        f'dir="{dir_val}" algn="tl" rotWithShape="0">'
        f"{clr_xml}"
        "</a:outerShdw>"
        "</a:effectLst>"
    )


def transform_to_xml(
    shape: Any,
    tag: str = "a:xfrm",
    extra: str = "",
) -> str:
    """Generate transform element (<a:xfrm> or <p:xfrm>)."""
    attrs: list[str] = []
    if tag != "p:xfrm":
        if getattr(shape, "rot", 0.0):
            rot_val = int(round((((shape.rot % 360) + 360) % 360) * 60000))
            attrs.append(f'rot="{rot_val}"')
        if getattr(shape, "flipH", False):
            attrs.append('flipH="1"')
        if getattr(shape, "flipV", False):
            attrs.append('flipV="1"')

    attr_str = f" {' '.join(attrs)}" if attrs else ""
    x_emu = pt_to_emu(shape.x)
    y_emu = pt_to_emu(shape.y)
    w_emu = max(0, pt_to_emu(shape.w))
    h_emu = max(0, pt_to_emu(shape.h))

    return (
        f"<{tag}{attr_str}>"
        f'<a:off x="{x_emu}" y="{y_emu}"/>'
        f'<a:ext cx="{w_emu}" cy="{h_emu}"/>'
        f"{extra}"
        f"</{tag}>"
    )


def geometry_to_xml(shape: Any) -> str:
    """Generate preset or custom geometry XML (<a:prstGeom> or <a:custGeom>)."""
    geom = getattr(shape, "geom", "rect") or "rect"
    return f'<a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>'
