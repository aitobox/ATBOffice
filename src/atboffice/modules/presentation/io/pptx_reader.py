"""ECMA-376 PresentationML reader for PPTX, PPSX, and POTX files."""

from __future__ import annotations

import copy
import io
import math
import posixpath
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from atboffice.modules.presentation.models.comment import (
    Comment,
    CommentAuthor,
    CommentReply,
)
from atboffice.modules.presentation.models.designs import (
    COLOR_SLOT_MAP,
    ColorScheme,
    DesignTemplate,
    apply_color_mods,
    resolve_color,
)
from atboffice.modules.presentation.models.media_item import (
    MediaItem,
    PlaybackSettings,
    guess_media_content_type,
    is_audio_extension,
    is_video_extension,
)
from atboffice.modules.presentation.models.presentation import (
    Presentation,
)
from atboffice.modules.presentation.models.shape import (
    Fill,
    Line,
    PlaceholderInfo,
    Shadow,
    Shape,
)
from atboffice.modules.presentation.models.slide import Animation, Slide, Transition
from atboffice.modules.presentation.models.text import (
    BulletInfo,
    Paragraph,
    Run,
    TextBody,
)
from atboffice.vfs.opc import SourcePackage

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


def emu_to_pt(emu: float | int | str | None, default: float = 0.0) -> float:
    """Convert EMUs (English Metric Units) to points (1 pt = 12700 EMUs)."""
    if emu is None:
        return default
    try:
        return round(float(emu) / EMUS_PER_PT, 2)
    except (ValueError, TypeError):
        return default


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


@dataclass
class PlaceholderTemplate:
    type: str
    idx: int
    shape_id: str
    xfrm: tuple[float, float, float, float, float] | None = None
    fill: Fill | None = None
    line: Line | None = None
    text_body: TextBody | None = None


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
        try:
            return float(tok)
        except (ValueError, TypeError):
            return 0.0

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


class PptxReader:
    """Parser for ECMA-376 PresentationML packages (.pptx, .ppsx, .potx)."""

    def __init__(self, package: SourcePackage) -> None:
        self.package = package
        self.rels_map: dict[str, dict[str, Any]] = {}
        self.themes: dict[str, ColorScheme] = {}
        self.theme_fmt: dict[str, dict[str, list[ET.Element]]] = {}
        self.media_map: dict[str, bytes] = {}
        self._layouts: dict[str, LayoutInfo] = {}
        self._masters: dict[str, MasterInfo] = {}
        self._theme_fonts: dict[str, tuple[str | None, str | None]] = {}

    @classmethod
    def open(cls, file_path: Path | str) -> Presentation:
        """Open a PPTX/PPSX/POTX file from disk."""
        pkg = SourcePackage.open(file_path)
        reader = cls(pkg)
        pres = reader.read()
        pres.props["file_path"] = str(file_path)
        return pres

    @classmethod
    def from_bytes(cls, data: bytes) -> Presentation:
        """Read a presentation from raw package bytes."""
        pkg = SourcePackage.from_bytes(data)
        reader = cls(pkg)
        return reader.read()

    def read(self) -> Presentation:
        """Parse presentation document and return populated Presentation model."""
        # 1. Locate presentation part via root relationships
        pres_part = self._locate_presentation_part()
        pres_bytes = self.package.read_part(pres_part)
        pres_xml = ET.fromstring(pres_bytes)

        # 2. Presentation Dimensions & Settings
        sz_elem = _get_child(pres_xml, "sldSz")
        width_pt = emu_to_pt(_get_attr(sz_elem, "cx"), default=960.0)
        height_pt = emu_to_pt(_get_attr(sz_elem, "cy"), default=540.0)

        first_num = 1
        fn_val = _get_attr(pres_xml, "firstSlideNum")
        if fn_val:
            try:
                first_num = int(fn_val)
            except ValueError:
                first_num = 1

        pres = Presentation.create_new(
            title="",
            design_key="default",
            w=width_pt,
            h=height_pt,
            empty=True,
        )
        pres.first_num = first_num

        # Attach source package and tracking dictionaries for lossless preservation
        pres.props["_source_package"] = self.package
        pres.props["_media_map"] = self.media_map
        slide_part_map: dict[str, str] = {}
        pres.props["_slide_part_map"] = slide_part_map

        # 3. Resolve presentation relationships
        pres_rels = self.package.get_relationships(pres_part)
        rel_by_id = {r.id: r for r in pres_rels}

        # 4. Parse Themes
        self._parse_themes(pres_part, pres_rels, pres)

        # 4.1 Parse Comment Authors
        self._parse_comment_authors(pres_part, pres_rels, pres)

        # 5. Parse Slide ID List
        sld_id_lst = _get_child(pres_xml, "sldIdLst")
        if sld_id_lst is not None:
            for sld_id_elem in _get_children(sld_id_lst, "sldId"):
                r_id = _get_attr(sld_id_elem, "id") or ""
                # Could be r:id attribute
                for k, v in sld_id_elem.attrib.items():
                    if _local_tag(k) == "id" and "relationships" in k:
                        r_id = v
                        break
                    if k.endswith(":id") or k == "id":
                        r_id = v

                rel = rel_by_id.get(r_id)
                if not rel:
                    # Look by ID case-insensitively
                    for rid, r in rel_by_id.items():
                        if rid.lower() == r_id.lower():
                            rel = r
                            break

                if rel and (rel.type == REL_SLIDE or rel.type.endswith("/slide")):
                    slide_path = _resolve_path(pres_part, rel.target)
                    if self.package.has_part(slide_path):
                        slide = self._parse_slide(slide_path, pres)
                        slide._original_state = slide.to_dict()
                        pres.slides.append(slide)
                        slide_part_map[slide.id] = slide_path

        # If presentation had zero slides, create default slide
        if not pres.slides:
            pres.add_slide(layout="title")

        return pres

    def _locate_presentation_part(self) -> str:
        """Find the main presentation part name from root relationships."""
        root_rels = self.package.get_relationships("")
        for rel in root_rels:
            if rel.type == REL_OFFICE_DOCUMENT or rel.type.endswith("/officeDocument"):
                return _resolve_path("", rel.target)
        if self.package.has_part("ppt/presentation.xml"):
            return "ppt/presentation.xml"
        raise ValueError("Package does not contain an officeDocument presentation part.")

    def _parse_themes(self, pres_part: str, pres_rels: list[Any], pres: Presentation) -> None:
        """Parse theme colors and fonts from theme part."""
        theme_parts: list[str] = []
        for rel in pres_rels:
            if rel.type == REL_THEME or rel.type.endswith("/theme"):
                theme_parts.append(_resolve_path(pres_part, rel.target))

        # Check standard location if not found in presentation rels
        if not theme_parts and self.package.has_part("ppt/theme/theme1.xml"):
            theme_parts.append("ppt/theme/theme1.xml")

        for t_part in theme_parts:
            if not self.package.has_part(t_part):
                continue
            try:
                t_bytes = self.package.read_part(t_part)
                t_xml = ET.fromstring(t_bytes)
                clr_scheme_elem = None
                for elem in t_xml.iter():
                    if _local_tag(elem.tag) == "clrScheme":
                        clr_scheme_elem = elem
                        break

                if clr_scheme_elem is not None:
                    colors = self._parse_color_scheme(clr_scheme_elem)
                    self.themes[t_part] = colors
                    # Update primary presentation design template colors
                    primary_design = next(iter(pres.designs.values()), None)
                    if primary_design:
                        primary_design.colors = colors

                # Parse and cache fmtScheme (fills, lines, bgFills)
                fm_elem = None
                for elem in t_xml.iter():
                    if _local_tag(elem.tag) == "fmtScheme":
                        fm_elem = elem
                        break
                if fm_elem is not None:
                    fill_lst = _get_child(fm_elem, "fillStyleLst")
                    ln_lst = _get_child(fm_elem, "lnStyleLst")
                    bg_lst = _get_child(fm_elem, "bgFillStyleLst")
                    self.theme_fmt[t_part] = {
                        "fills": list(fill_lst) if fill_lst is not None else [],
                        "lines": list(ln_lst) if ln_lst is not None else [],
                        "bgFills": list(bg_lst) if bg_lst is not None else [],
                    }
            except Exception:
                pass

    def _parse_color_scheme(self, elem: ET.Element) -> ColorScheme:
        """Parse 12-slot color scheme from a:clrScheme XML element."""
        slots: dict[str, str] = {}
        for child in elem:
            tag = _local_tag(child.tag)
            # Find color definition inside child (srgbClr, sysClr)
            color_val = self._extract_color(child)
            if color_val:
                slots[tag] = color_val

        return ColorScheme(
            lt1=slots.get("lt1", "#FFFFFF"),
            dk1=slots.get("dk1", "#000000"),
            lt2=slots.get("lt2", "#808080"),
            dk2=slots.get("dk2", "#000000"),
            accent1=slots.get("accent1", "#BBE0E3"),
            accent2=slots.get("accent2", "#333399"),
            accent3=slots.get("accent3", "#FFFFFF"),
            accent4=slots.get("accent4", "#000000"),
            accent5=slots.get("accent5", "#ADADD6"),
            accent6=slots.get("accent6", "#008A8A"),
            hlink=slots.get("hlink", "#009999"),
            folHlink=slots.get("folHlink", "#99CC00"),
        )

    def _extract_color_detail(
        self,
        parent: ET.Element | None,
        ph_clr: str | None = None,
        theme_colors: ColorScheme | None = None,
        clr_map: dict[str, str] | None = None,
        clr_map_ovr: dict[str, str] | None = None,
        keep_scheme: bool = False,
    ) -> tuple[str | None, float]:
        """Extract resolved color string and alpha from XML element, applying mods and color maps."""
        if parent is None:
            return None, 1.0

        target = parent
        tag = _local_tag(parent.tag)
        if tag not in ("srgbClr", "sysClr", "schemeClr", "scrgbClr"):
            target = None
            for child in parent:
                c_tag = _local_tag(child.tag)
                if c_tag in ("srgbClr", "sysClr", "schemeClr", "scrgbClr"):
                    target = child
                    tag = c_tag
                    break

        if target is None:
            return None, 1.0

        # Parse modifiers and alpha
        alpha = 1.0
        mods: list[dict[str, Any]] = []
        for m in target:
            mtag = _local_tag(m.tag)
            mval_str = _get_attr(m, "val")
            mval = float(mval_str) if mval_str else 0.0
            if mtag == "alpha":
                alpha = mval / 100000.0
            elif mtag == "alphaMod":
                alpha *= mval / 100000.0
            elif mtag == "alphaOff":
                alpha += mval / 100000.0
            else:
                mods.append({"name": mtag, "val": mval})

        alpha = max(0.0, min(1.0, alpha))

        if tag == "schemeClr" and not mods and keep_scheme:
            val = _get_attr(target, "val")
            if val == "phClr" and ph_clr:
                if ph_clr.startswith("#"):
                    return ph_clr, alpha
                token = ph_clr
                if clr_map_ovr and token in clr_map_ovr:
                    token = clr_map_ovr[token]
                if clr_map and token in clr_map:
                    token = clr_map[token]
                return token, alpha
            elif val and val != "phClr":
                token = val
                if clr_map_ovr and token in clr_map_ovr:
                    token = clr_map_ovr[token]
                if clr_map and token in clr_map:
                    token = clr_map[token]
                return token, alpha

        base: str | None = None
        if tag == "srgbClr":
            val = _get_attr(target, "val")
            if val:
                base = f"#{val.upper()}"
        elif tag == "sysClr":
            last_clr = _get_attr(target, "lastClr")
            base = f"#{last_clr.upper()}" if last_clr else "#000000"
        elif tag == "schemeClr":
            val = _get_attr(target, "val")
            if val == "phClr" and ph_clr:
                val = ph_clr
            if val:
                token = val
                if clr_map_ovr and token in clr_map_ovr:
                    token = clr_map_ovr[token]
                if clr_map and token in clr_map:
                    token = clr_map[token]
                slot = COLOR_SLOT_MAP.get(token, token)
                if theme_colors and hasattr(theme_colors, slot):
                    base = getattr(theme_colors, slot)
                elif val.startswith("#"):
                    base = val
                else:
                    base = resolve_color(token, fallback=val)
        elif tag == "scrgbClr":
            r_val = float(_get_attr(target, "r", "0") or 0) / 100000.0
            g_val = float(_get_attr(target, "g", "0") or 0) / 100000.0
            b_val = float(_get_attr(target, "b", "0") or 0) / 100000.0
            r = max(0, min(255, round(r_val * 255.0)))
            g = max(0, min(255, round(g_val * 255.0)))
            b = max(0, min(255, round(b_val * 255.0)))
            base = f"#{r:02X}{g:02X}{b:02X}"

        if base and mods and base.startswith("#"):
            base = apply_color_mods(base, mods)

        return base, alpha

    def _extract_color(self, parent: ET.Element | None) -> str | None:
        """Extract hex color string or theme color slot token from XML element."""
        if parent is None:
            return None
        for child in parent:
            tag = _local_tag(child.tag)
            if tag == "srgbClr":
                val = _get_attr(child, "val")
                if val:
                    return f"#{val.upper()}"
            elif tag == "sysClr":
                last_clr = _get_attr(child, "lastClr")
                if last_clr:
                    return f"#{last_clr.upper()}"
            elif tag == "schemeClr":
                val = _get_attr(child, "val")
                if val:
                    return val
            elif tag == "scrgbClr":
                clr, _ = self._extract_color_detail(child)
                return clr
        return None

    def _get_theme_colors(self, theme_path: str) -> ColorScheme | None:
        themes = getattr(self, "themes", {})
        if not theme_path:
            return next(iter(themes.values()), None)
        clean_path = theme_path.lstrip("/")
        for k, v in themes.items():
            if k == theme_path or k.lstrip("/") == clean_path or Path(k).name == Path(clean_path).name:
                return v
        return next(iter(themes.values()), None)

    def _get_theme_fmt(self, theme_path: str) -> dict[str, list[ET.Element]]:
        theme_fmt = getattr(self, "theme_fmt", {})
        if not theme_path:
            return next(iter(theme_fmt.values()), {"fills": [], "lines": [], "bgFills": []})
        clean_path = theme_path.lstrip("/")
        for k, v in theme_fmt.items():
            if k == theme_path or k.lstrip("/") == clean_path or Path(k).name == Path(clean_path).name:
                return v
        return next(iter(theme_fmt.values()), {"fills": [], "lines": [], "bgFills": []})

    def _resolve_theme_context(
        self,
        layout_info: LayoutInfo | None = None,
        slide_clr_map_ovr: dict[str, str] | None = None,
    ) -> tuple[ColorScheme | None, dict[str, list[ET.Element]], dict[str, str], dict[str, str]]:
        themes = getattr(self, "themes", {})
        theme_fmt_dict = getattr(self, "theme_fmt", {})
        theme_colors = None
        theme_fmt: dict[str, list[ET.Element]] = {"fills": [], "lines": [], "bgFills": []}
        clr_map: dict[str, str] = {}
        clr_map_ovr: dict[str, str] = dict(slide_clr_map_ovr or {})
        if layout_info:
            if not clr_map_ovr and layout_info.clr_map_ovr:
                clr_map_ovr = dict(layout_info.clr_map_ovr)
            if layout_info.master:
                m = layout_info.master
                clr_map = dict(m.clr_map)
                theme_colors = self._get_theme_colors(m.theme_path)
                theme_fmt = self._get_theme_fmt(m.theme_path)
        if theme_colors is None:
            theme_colors = next(iter(themes.values()), None)
            theme_fmt = next(iter(theme_fmt_dict.values()), {"fills": [], "lines": [], "bgFills": []})
        return theme_colors, theme_fmt, clr_map, clr_map_ovr

    def _parse_style_refs(
        self,
        style_elem: ET.Element | None,
        theme_colors: ColorScheme | None = None,
        theme_fmt: dict[str, list[ET.Element]] | None = None,
        clr_map: dict[str, str] | None = None,
        clr_map_ovr: dict[str, str] | None = None,
    ) -> tuple[Fill | None, Line | None, str | None, str | None]:
        """Parse <p:style> element, returning (fill, line, font_color, font_type)."""
        if style_elem is None:
            return None, None, None, None

        fmt = theme_fmt or {"fills": [], "lines": [], "bgFills": []}
        theme_lines = fmt.get("lines", [])
        theme_fills = fmt.get("fills", [])
        theme_bg_fills = fmt.get("bgFills", [])

        fill: Fill | None = None
        line: Line | None = None
        font_color: str | None = None
        font_type: str | None = None

        # Line ref
        ln_ref = _get_child(style_elem, "lnRef")
        if ln_ref is not None:
            idx_str = _get_attr(ln_ref, "idx", "0") or "0"
            try:
                idx = int(idx_str)
            except ValueError:
                idx = 0
            if idx == 0:
                line = Line.none()
            elif idx > 0:
                ph_clr, alpha = self._extract_color_detail(
                    ln_ref,
                    theme_colors=theme_colors,
                    clr_map=clr_map,
                    clr_map_ovr=clr_map_ovr,
                    keep_scheme=True,
                )
                if theme_lines and idx - 1 < len(theme_lines):
                    th_ln = theme_lines[idx - 1]
                    line = self._parse_line(
                        th_ln,
                        ph_clr=ph_clr,
                        theme_colors=theme_colors,
                        clr_map=clr_map,
                        clr_map_ovr=clr_map_ovr,
                    )
                else:
                    line = Line(type="solid", color=ph_clr or "tx1", width=0.75)

        # Fill ref
        fill_ref = _get_child(style_elem, "fillRef")
        if fill_ref is not None:
            idx_str = _get_attr(fill_ref, "idx", "0") or "0"
            try:
                idx = int(idx_str)
            except ValueError:
                idx = 0
            if idx == 0:
                fill = Fill.none()
            elif idx > 0:
                ph_clr, alpha = self._extract_color_detail(
                    fill_ref,
                    theme_colors=theme_colors,
                    clr_map=clr_map,
                    clr_map_ovr=clr_map_ovr,
                    keep_scheme=True,
                )
                th_fill = None
                if idx >= 1001:
                    bg_idx = idx - 1001
                    if theme_bg_fills and bg_idx < len(theme_bg_fills):
                        th_fill = theme_bg_fills[bg_idx]
                else:
                    f_idx = idx - 1
                    if theme_fills and f_idx < len(theme_fills):
                        th_fill = theme_fills[f_idx]

                if th_fill is not None:
                    parsed_fill = self._parse_fill(
                        th_fill,
                        ph_clr=ph_clr,
                        theme_colors=theme_colors,
                        clr_map=clr_map,
                        clr_map_ovr=clr_map_ovr,
                    )
                    if parsed_fill.type == "gradient" and ph_clr:
                        fill = Fill.solid(ph_clr, alpha)
                    else:
                        fill = parsed_fill
                else:
                    fill = Fill.solid(ph_clr or "#FFFFFF", alpha)

        # Font ref
        font_ref = _get_child(style_elem, "fontRef")
        if font_ref is not None:
            idx_str = _get_attr(font_ref, "idx", "") or ""
            font_color, _ = self._extract_color_detail(
                font_ref,
                theme_colors=theme_colors,
                clr_map=clr_map,
                clr_map_ovr=clr_map_ovr,
            )
            if idx_str == "major":
                font_type = "+mj"
            elif idx_str == "minor":
                font_type = "+mn"

        return fill, line, font_color, font_type

    def _parse_slide(self, slide_path: str, pres: Presentation) -> Slide:
        """Parse individual slide part XML."""
        slide_bytes = self.package.read_part(slide_path)
        slide_xml = ET.fromstring(slide_bytes)

        # Slide relationships (for images, notes, etc.)
        slide_rels = self.package.get_relationships(slide_path)
        rel_map = {r.id: r for r in slide_rels}

        slide_id = Path(slide_path).stem
        slide = Slide(id=slide_id, layout="text", is_imported=True)

        # Parse slide colour map override
        slide_clr_map_ovr: dict[str, str] = {}
        s_clr_map_ovr_elem = _get_child(slide_xml, "clrMapOvr")
        if s_clr_map_ovr_elem is not None:
            s_ovr_el = _get_child(s_clr_map_ovr_elem, "overrideClrMapping")
            if s_ovr_el is not None:
                for k in (
                    "bg1",
                    "tx1",
                    "bg2",
                    "tx2",
                    "accent1",
                    "accent2",
                    "accent3",
                    "accent4",
                    "accent5",
                    "accent6",
                    "hlink",
                    "folHlink",
                ):
                    v = _get_attr(s_ovr_el, k)
                    if v:
                        slide_clr_map_ovr[k] = v

        # Parse media timing from <p:timing>
        timing_elem = _get_child(slide_xml, "timing")
        if timing_elem is not None:
            slide.has_timing = True
            slide.raw_timing_xml = ET.tostring(timing_elem, encoding="unicode")
        timing_map = self._parse_slide_media_timing(timing_elem)

        # Resolve layout for this slide
        layout_info: LayoutInfo | None = None
        for r in slide_rels:
            if r.type == REL_SLIDE_LAYOUT or r.type.endswith("/slideLayout"):
                layout_path = _resolve_path(slide_path, r.target)
                layout_info = self._load_layout(layout_path)
                break

        if not slide_clr_map_ovr and layout_info and layout_info.clr_map_ovr:
            slide_clr_map_ovr = dict(layout_info.clr_map_ovr)
        slide.clr_map_ovr = slide_clr_map_ovr

        if layout_info and layout_info.master:
            m_info = layout_info.master
            if layout_info.layout_type:
                from atboffice.modules.presentation.models.layouts import LAYOUTS

                ox_to_key = {lyt.ox: lyt.key for lyt in LAYOUTS}
                slide.layout = ox_to_key.get(layout_info.layout_type, "text")
            else:
                ph_types = [p.type for p in layout_info.placeholders]
                if "ctrTitle" in ph_types:
                    slide.layout = "title"
                elif "title" in ph_types:
                    slide.layout = "text" if len(ph_types) > 1 else "titleOnly"
                elif not ph_types:
                    slide.layout = "blank"
                else:
                    slide.layout = "content"

            if m_info.design is None:
                d_stem = Path(m_info.master_path).stem
                d_colors = (
                    self._get_theme_colors(m_info.theme_path)
                    or next(iter(self.themes.values()), ColorScheme())
                )
                d_fonts = {
                    "major": m_info.major_font or "Arial",
                    "minor": m_info.minor_font or "Arial",
                }
                d_bg = m_info.bg or Fill.solid("bg1")
                # Combine master decorations and layout decorations
                all_decos = list(m_info.decorations)
                if layout_info.decorations:
                    for ld in layout_info.decorations:
                        if ld not in all_decos:
                            all_decos.append(ld)

                concrete_ph: dict[str, tuple[float, float, float, float]] = {}
                for p in m_info.placeholders:
                    if p.xfrm:
                        concrete_ph[p.type] = (p.xfrm[0], p.xfrm[1], p.xfrm[2], p.xfrm[3])
                if layout_info:
                    for p in layout_info.placeholders:
                        if p.xfrm and p.type not in concrete_ph:
                            concrete_ph[p.type] = (p.xfrm[0], p.xfrm[1], p.xfrm[2], p.xfrm[3])

                m_info.design = DesignTemplate(
                    id=f"dsn_{d_stem}",
                    key=d_stem,
                    name=f"Master {d_stem}",
                    colors=d_colors,
                    fonts=d_fonts,
                    bg=d_bg,
                    clr_map=dict(m_info.clr_map),
                    decorations=all_decos,
                    placeholder_frames=concrete_ph,
                    text_styles={
                        "title": m_info.title_style,
                        "body": m_info.body_style,
                        "other": m_info.other_style,
                    },
                )
                pres.designs[m_info.design.id] = m_info.design
            slide.design_id = m_info.design.id

        # 1. Slide Shapes
        c_sld = _get_child(slide_xml, "cSld")
        if c_sld is not None:
            bg_elem = _get_child(c_sld, "bg")
            if bg_elem is not None:
                bg_pr = _get_child(bg_elem, "bgPr")
                if bg_pr is not None:
                    slide.bg = self._parse_fill(bg_pr)
            if _get_attr(c_sld, "showMasterSp") == "0":
                slide.hide_master = True

        if slide.bg is None:
            if layout_info and layout_info.bg:
                slide.bg = copy.deepcopy(layout_info.bg)
            elif layout_info and layout_info.master and layout_info.master.bg:
                slide.bg = copy.deepcopy(layout_info.master.bg)

        if c_sld is not None:
            sp_tree = _get_child(c_sld, "spTree")
            if sp_tree is not None:
                for child in sp_tree:
                    shape = self._parse_shape(
                        child,
                        slide_path,
                        rel_map,
                        timing_map=timing_map,
                        layout_info=layout_info,
                        slide_clr_map_ovr=slide_clr_map_ovr,
                    )
                    if shape:
                        slide.shapes.append(shape)

        # 1.1 Animation Timings
        slide.animations = self._parse_slide_animations(timing_elem, slide.shapes)

        # 2. Slide Transition
        trans_elem = _get_child(slide_xml, "transition")
        if trans_elem is not None:
            slide.transition = self._parse_transition(trans_elem)

        # 3. Slide Speaker Notes
        notes_text = self._extract_notes(slide_path, rel_map)
        if notes_text:
            slide.notes = notes_text

        # 4. Slide Comments
        self._parse_slide_comments(slide_path, rel_map, slide, pres)

        return slide

    def _parse_slide_media_timing(
        self,
        timing_elem: ET.Element | None,
    ) -> dict[str, PlaybackSettings]:
        """Extract media playback settings keyed by target shape ID."""
        if timing_elem is None:
            return {}
        settings_by_id: dict[str, PlaybackSettings] = {}
        for node in timing_elem.iter():
            ltag = _local_tag(node.tag)
            if ltag in ("cMediaNode", "video", "audio"):
                spid = None
                for child in node.iter():
                    if _local_tag(child.tag) == "spTgt":
                        spid = _get_attr(child, "spid")
                        break
                if not spid:
                    continue

                vol_str = _get_attr(node, "vol")
                volume = 0.8
                if vol_str is not None:
                    try:
                        volume = max(0.0, min(1.0, float(vol_str) / 100000.0))
                    except (ValueError, TypeError):
                        pass

                show_when_stopped = _get_attr(node, "showWhenStopped", "1")
                hide_while_not_playing = show_when_stopped == "0"

                loop = False
                c_tn = _get_child(node, "cTn")
                if c_tn is not None:
                    repeat_count = _get_attr(c_tn, "repeatCount", "")
                    if repeat_count in ("indefinite", "INF"):
                        loop = True

                settings_by_id[spid] = PlaybackSettings(
                    volume=volume,
                    hide_while_not_playing=hide_while_not_playing,
                    loop=loop,
                )
        return settings_by_id

    def _parse_shape(
        self,
        elem: ET.Element,
        slide_path: str,
        rel_map: dict[str, Any],
        timing_map: dict[str, PlaybackSettings] | None = None,
        layout_info: LayoutInfo | None = None,
        slide_clr_map_ovr: dict[str, str] | None = None,
        group_fill: Fill | None = None,
    ) -> Shape | None:
        """Parse shape, picture, table, or group element."""
        tag = _local_tag(elem.tag)

        if tag in ("sp", "cxnSp"):
            return self._parse_sp_element(
                elem,
                slide_path=slide_path,
                rel_map=rel_map,
                timing_map=timing_map,
                layout_info=layout_info,
                slide_clr_map_ovr=slide_clr_map_ovr,
                group_fill=group_fill,
            )
        elif tag == "pic":
            return self._parse_pic_element(elem, slide_path, rel_map, timing_map=timing_map)
        elif tag == "graphicFrame":
            return self._parse_graphic_frame(elem, slide_path=slide_path, rel_map=rel_map)
        elif tag == "grpSp":
            return self._parse_group_element(
                elem,
                slide_path=slide_path,
                rel_map=rel_map,
                layout_info=layout_info,
                slide_clr_map_ovr=slide_clr_map_ovr,
                group_fill=group_fill,
            )
        return None

    def _parse_sp_element(
        self,
        elem: ET.Element,
        slide_path: str = "",
        rel_map: dict[str, Any] | None = None,
        timing_map: dict[str, PlaybackSettings] | None = None,
        layout_info: LayoutInfo | None = None,
        slide_clr_map_ovr: dict[str, str] | None = None,
        group_fill: Fill | None = None,
    ) -> Shape:
        """Parse standard <p:sp> shape or text box."""
        nv_sp_pr = _get_child(elem, "nvSpPr")
        if nv_sp_pr is None:
            nv_sp_pr = _get_child(elem, "nvCxnSpPr")
        c_nv_pr = _get_child(nv_sp_pr, "cNvPr") if nv_sp_pr is not None else None
        nv_pr = _get_child(nv_sp_pr, "nvPr") if nv_sp_pr is not None else None

        # Parse connector start/end points if present (<a:stCxn>, <a:endCxn>)
        cxn_start = None
        cxn_end = None
        c_nv_cxn_pr = _get_child(nv_sp_pr, "cNvCxnSpPr") if nv_sp_pr is not None else None
        if c_nv_cxn_pr is not None:
            st_cxn = _get_child(c_nv_cxn_pr, "stCxn")
            if st_cxn is not None:
                cxn_start = {
                    "id": _get_attr(st_cxn, "id", ""),
                    "idx": int(_get_attr(st_cxn, "idx", "0") or 0),
                }
            end_cxn = _get_child(c_nv_cxn_pr, "endCxn")
            if end_cxn is not None:
                cxn_end = {
                    "id": _get_attr(end_cxn, "id", ""),
                    "idx": int(_get_attr(end_cxn, "idx", "0") or 0),
                }

        shape_id = _get_attr(c_nv_pr, "id", f"sp_{id(elem)}")
        shape_name = _get_attr(c_nv_pr, "name", "Shape")

        # Placeholder info
        placeholder: PlaceholderInfo | None = None
        ph_elem = _get_child(nv_pr, "ph") if nv_pr is not None else None
        if ph_elem is not None:
            ph_type = _get_attr(ph_elem, "type", "body") or "body"
            ph_idx = int(_get_attr(ph_elem, "idx", "0") or 0)
            placeholder = PlaceholderInfo(type=ph_type, idx=ph_idx)

        # Resolve theme context for colors & formatting
        theme_colors, theme_fmt, clr_map, clr_map_ovr = self._resolve_theme_context(
            layout_info, slide_clr_map_ovr
        )

        style_elem = _get_child(elem, "style")
        style_fill, style_line, style_font_color, style_font = self._parse_style_refs(
            style_elem,
            theme_colors=theme_colors,
            theme_fmt=theme_fmt,
            clr_map=clr_map,
            clr_map_ovr=clr_map_ovr,
        )

        # Shape Properties (transform, geometry, fill, line)
        sp_pr = _get_child(elem, "spPr")
        has_xfrm = sp_pr is not None and _get_child(sp_pr, "xfrm") is not None
        x, y, w, h, rot = self._parse_transform(sp_pr)
        geom, custom_path = self._parse_geometry(sp_pr)

        # Match placeholder in layout / master if this shape is a placeholder
        lp = None
        mp = None
        if placeholder is not None and layout_info is not None:
            lp = self._match_layout_ph(layout_info.placeholders, placeholder)
            master_phs = layout_info.master.placeholders if layout_info.master else []
            mp = self._match_master_ph(master_phs, placeholder.type)

            # Inherit missing transform
            if not has_xfrm:
                if lp and lp.xfrm is not None:
                    x, y, w, h, rot = lp.xfrm
                elif mp and mp.xfrm is not None:
                    x, y, w, h, rot = mp.xfrm

        # Fill precedence: own spPr > useBgFill > style > layout placeholder > master placeholder
        fill: Fill | None = None
        has_sp_fill = sp_pr is not None and (
            _get_child(sp_pr, "solidFill") is not None
            or _get_child(sp_pr, "gradFill") is not None
            or _get_child(sp_pr, "noFill") is not None
            or _get_child(sp_pr, "grpFill") is not None
        )
        if has_sp_fill:
            fill = self._parse_fill(
                sp_pr,
                theme_colors=theme_colors,
                clr_map=clr_map,
                clr_map_ovr=clr_map_ovr,
                group_fill=group_fill,
            )
        elif _get_attr(elem, "useBgFill") in ("1", "true", "True"):
            fill = Fill(type="bg")
        elif style_fill is not None:
            fill = copy.deepcopy(style_fill)
        elif lp and lp.fill and lp.fill.type != "none":
            fill = copy.deepcopy(lp.fill)
        elif mp and mp.fill and mp.fill.type != "none":
            fill = copy.deepcopy(mp.fill)
        else:
            fill = Fill.none()

        # Line precedence: style > layout placeholder > master placeholder, then overlaid by spPr/ln
        ln_base = Line.none()
        if style_line is not None:
            ln_base = copy.deepcopy(style_line)
        elif lp and lp.line and lp.line.type != "none":
            ln_base = copy.deepcopy(lp.line)
        elif mp and mp.line and mp.line.type != "none":
            ln_base = copy.deepcopy(mp.line)

        line = self._parse_line(
            sp_pr,
            base_line=ln_base,
            theme_colors=theme_colors,
            clr_map=clr_map,
            clr_map_ovr=clr_map_ovr,
        )

        shadow = self._parse_shadow(sp_pr)

        # Resolve default font from style_font (+mj / +mn)
        resolved_font = None
        if style_font == "+mj" and layout_info and layout_info.master and layout_info.master.major_font:
            resolved_font = layout_info.master.major_font
        elif style_font == "+mn" and layout_info and layout_info.master and layout_info.master.minor_font:
            resolved_font = layout_info.master.minor_font
        elif style_font:
            resolved_font = style_font

        # Text Body
        tx_body_elem = _get_child(elem, "txBody")
        text_body = (
            self._parse_text_body(
                tx_body_elem,
                default_color=style_font_color,
                default_font=resolved_font,
                rel_map=rel_map,
            )
            if tx_body_elem is not None
            else None
        )

        if placeholder is not None and text_body is not None and layout_info is not None:
            self._apply_placeholder_text_inheritance(text_body, placeholder, layout_info, lp, mp)

        shape_type = (
            "text"
            if (geom == "rect" and text_body and not fill.type != "none" and line.type == "none")
            else "shape"
        )
        if placeholder and placeholder.type in ("title", "ctrTitle", "subTitle"):
            shape_type = "text"

        # Check for media in nvPr (e.g. standalone audio icon/shape)
        media_item = None
        media_key = None
        if nv_pr is not None and rel_map is not None:
            for child in nv_pr:
                ltag = _local_tag(child.tag)
                if ltag in ("audioFile", "videoFile", "quickTimeFile", "audioCd"):
                    m_rid = ""
                    for k, v in child.attrib.items():
                        if _local_tag(k) in ("link", "embed"):
                            m_rid = v
                            break
                    if m_rid and m_rid in rel_map:
                        rel = rel_map[m_rid]
                        media_path = _resolve_path(slide_path, rel.target)
                        media_bytes = (
                            self.package.read_part(media_path)
                            if self.package.has_part(media_path)
                            else None
                        )
                        if media_bytes:
                            self.media_map[media_path] = media_bytes
                        c_type = (
                            self.package.get_content_type(media_path)
                            if self.package.has_part(media_path)
                            else guess_media_content_type(media_path)
                        )
                        is_aud = ltag in ("audioFile", "audioCd") or is_audio_extension(media_path)
                        pb = (timing_map or {}).get(shape_id, PlaybackSettings())
                        media_item = MediaItem(
                            media_type="audio" if is_aud else "video",
                            media_path=media_path,
                            content_type=c_type,
                            media_bytes=media_bytes,
                            playback=pb,
                            original_element=ltag,
                        )
                        media_key = media_path
                        shape_type = "image"
                        break

        if shape_type == "shape" and (
            geom in (
                "line",
                "straightConnector1",
                "bentConnector2",
                "bentConnector3",
                "bentConnector4",
                "bentConnector5",
                "curvedConnector2",
                "curvedConnector3",
            )
            or bool(cxn_start or cxn_end)
        ):
            shape_type = "line"

        return Shape(
            id=shape_id or "sp_1",
            type=shape_type,
            name=shape_name or "Shape",
            geom=geom,
            x=x,
            y=y,
            w=w,
            h=h,
            rot=rot,
            fill=fill,
            line=line,
            shadow=shadow,
            placeholder=placeholder,
            text=text_body,
            media=media_key,
            media_item=media_item,
            custom_path=custom_path,
            cxn_start=cxn_start,
            cxn_end=cxn_end,
        )

    def _parse_pic_element(
        self,
        elem: ET.Element,
        slide_path: str,
        rel_map: dict[str, Any],
        timing_map: dict[str, PlaybackSettings] | None = None,
    ) -> Shape:
        """Parse <p:pic> image or multimedia element."""
        nv_pic_pr = _get_child(elem, "nvPicPr")
        c_nv_pr = _get_child(nv_pic_pr, "cNvPr") if nv_pic_pr is not None else None
        nv_pr = _get_child(nv_pic_pr, "nvPr") if nv_pic_pr is not None else None
        pic_id = _get_attr(c_nv_pr, "id", f"pic_{id(elem)}")
        pic_name = _get_attr(c_nv_pr, "name", "Picture")

        sp_pr = _get_child(elem, "spPr")
        x, y, w, h, rot = self._parse_transform(sp_pr)

        # 1. Poster image embed relationship from <p:blipFill>/<a:blip>
        blip_fill = _get_child(elem, "blipFill")
        blip = _get_child(blip_fill, "blip") if blip_fill is not None else None
        embed_id = ""
        if blip is not None:
            for k, v in blip.attrib.items():
                if _local_tag(k) == "embed":
                    embed_id = v
                    break

        poster_path: str | None = None
        poster_bytes: bytes | None = None
        p_rel = rel_map.get(embed_id)
        if p_rel:
            resolved_p = _resolve_path(slide_path, p_rel.target)
            if self.package.has_part(resolved_p):
                poster_bytes = self.package.read_part(resolved_p)
                self.media_map[resolved_p] = poster_bytes
                poster_path = resolved_p
            else:
                poster_path = resolved_p

        # 2. Check for media references in nvPr (videoFile, audioFile, quickTimeFile)
        media_rel_id = ""
        media_tag_name = ""
        if nv_pr is not None:
            for child in nv_pr:
                ltag = _local_tag(child.tag)
                if ltag in ("videoFile", "audioFile", "quickTimeFile", "audioCd"):
                    media_tag_name = ltag
                    for k, v in child.attrib.items():
                        if _local_tag(k) in ("link", "embed"):
                            media_rel_id = v
                            break
                    if media_rel_id:
                        break

        # Check cNvPr extension list for p14:media
        if not media_rel_id and c_nv_pr is not None:
            ext_lst = _get_child(c_nv_pr, "extLst")
            if ext_lst is not None:
                for ext in ext_lst:
                    for child in ext:
                        if _local_tag(child.tag) == "media":
                            for k, v in child.attrib.items():
                                if _local_tag(k) == "embed":
                                    media_rel_id = v
                                    media_tag_name = "p14:media"
                                    break

        # Fallback: What if embed_id itself targets a video/audio file?
        if not media_rel_id and p_rel:
            t_lower = p_rel.target.lower()
            is_target_media = (
                is_audio_extension(t_lower)
                or is_video_extension(t_lower)
                or p_rel.type in (REL_VIDEO, REL_AUDIO, REL_MEDIA)
            )
            if is_target_media:
                media_rel_id = embed_id
                media_tag_name = "audioFile" if is_audio_extension(t_lower) else "videoFile"
                # Poster is not a separate image
                poster_path = None
                poster_bytes = None

        media_item: MediaItem | None = None
        if media_rel_id and media_rel_id in rel_map:
            m_rel = rel_map[media_rel_id]
            resolved_m = _resolve_path(slide_path, m_rel.target)
            media_bytes = (
                self.package.read_part(resolved_m) if self.package.has_part(resolved_m) else None
            )
            if media_bytes:
                self.media_map[resolved_m] = media_bytes
            c_type = (
                self.package.get_content_type(resolved_m)
                if self.package.has_part(resolved_m)
                else guess_media_content_type(resolved_m)
            )
            is_aud = (
                media_tag_name in ("audioFile", "audioCd")
                or is_audio_extension(resolved_m)
                or m_rel.type == REL_AUDIO
            )
            pb = (timing_map or {}).get(pic_id, PlaybackSettings())
            media_item = MediaItem(
                media_type="audio" if is_aud else "video",
                media_path=resolved_m,
                content_type=c_type,
                media_bytes=media_bytes,
                poster_path=poster_path,
                poster_bytes=poster_bytes,
                playback=pb,
                original_element=media_tag_name or "videoFile",
            )
        elif poster_bytes:
            media_item = MediaItem(
                media_type="image",
                media_path=poster_path or "",
                poster_path=poster_path,
                poster_bytes=poster_bytes,
            )

        media_key = poster_path or (media_item.media_path if media_item else None)

        return Shape(
            id=pic_id or "pic_1",
            type="image",
            name=pic_name or "Picture",
            geom="rect",
            x=x,
            y=y,
            w=w,
            h=h,
            rot=rot,
            fill=Fill.none(),
            line=Line.none(),
            media=media_key,
            media_item=media_item,
        )

    def _parse_graphic_frame(
        self,
        elem: ET.Element,
        slide_path: str = "",
        rel_map: dict[str, Any] | None = None,
    ) -> Shape:
        """Parse <p:graphicFrame> table or chart element."""
        c_nv_pr = None
        nv_frame_pr = _get_child(elem, "nvGraphicFramePr")
        if nv_frame_pr is not None:
            c_nv_pr = _get_child(nv_frame_pr, "cNvPr")

        frame_id = _get_attr(c_nv_pr, "id", f"gf_{id(elem)}")
        frame_name = _get_attr(c_nv_pr, "name", "Table")

        xfrm = _get_child(elem, "xfrm")
        x, y, w, h, rot = self._parse_xfrm_element(xfrm)

        graphic = _get_child(elem, "graphic")
        graphic_data = _get_child(graphic, "graphicData") if graphic is not None else None

        # 1. Check if graphicData has chart
        chart_elem = None
        if graphic_data is not None:
            for child in graphic_data:
                if child.tag.endswith("chart"):
                    chart_elem = child
                    break

        if chart_elem is not None:
            r_id = _get_attr(chart_elem, "id")
            chart_dict = None
            if r_id and rel_map and r_id in rel_map:
                rel = rel_map[r_id]
                chart_target = rel.target if hasattr(rel, "target") else str(rel)
                chart_path = _resolve_path(slide_path, chart_target)
                if self.package.has_part(chart_path):
                    from atboffice.modules.presentation.chart.io import parse_chart_xml

                    chart_bytes = self.package.read_part(chart_path)
                    chart_obj = parse_chart_xml(chart_bytes)

                    # Look for embedded workbook in chart rels
                    chart_rels = self.package.get_relationships(chart_path)
                    for cr in chart_rels:
                        if (
                            "spreadsheetml" in cr.type.lower()
                            or "package" in cr.type.lower()
                            or cr.target.endswith(".xlsx")
                        ):
                            wb_path = _resolve_path(chart_path, cr.target)
                            if self.package.has_part(wb_path):
                                chart_obj.embedded_workbook = self.package.read_part(wb_path)
                                break
                    chart_dict = chart_obj.to_dict()

            return Shape(
                id=frame_id or "chart_1",
                type="chart",
                name=frame_name or "Chart",
                x=x,
                y=y,
                w=w,
                h=h,
                rot=rot,
                chart=chart_dict,
            )

        # 1.5 Check if graphicData has diagram / SmartArt
        g_uri = _get_attr(graphic_data, "uri") or ""
        is_diagram = "diagram" in g_uri.lower() or any(
            child.tag.endswith("relIds") or "diagram" in child.tag
            for child in (graphic_data if graphic_data is not None else [])
        )
        if is_diagram:
            rel_ids_elem = None
            if graphic_data is not None:
                for child in graphic_data:
                    if child.tag.endswith("relIds"):
                        rel_ids_elem = child
                        break

            diag_texts: list[str] = []
            diag_layout = "process"
            if rel_ids_elem is not None and rel_map is not None:
                dm_rid = ""
                lo_rid = ""
                for k, v in rel_ids_elem.attrib.items():
                    if k.endswith("dm"):
                        dm_rid = v
                    elif k.endswith("lo"):
                        lo_rid = v

                if dm_rid and dm_rid in rel_map:
                    dm_rel = rel_map[dm_rid]
                    dm_target = dm_rel.target if hasattr(dm_rel, "target") else str(dm_rel)
                    dm_path = _resolve_path(slide_path, dm_target)
                    if self.package.has_part(dm_path):
                        try:
                            dm_xml = ET.fromstring(self.package.read_part(dm_path))
                            for pt in dm_xml.iter():
                                if pt.tag.endswith("pt"):
                                    pt_type = pt.attrib.get("type", "node")
                                    if pt_type not in ("node", "doc"):
                                        continue
                                    t_runs: list[str] = []
                                    for t_node in pt.iter():
                                        if (
                                            t_node.tag.endswith("t")
                                            and t_node.text
                                            and t_node.text.strip()
                                        ):
                                            t_runs.append(t_node.text.strip())
                                    if t_runs:
                                        full_line = " ".join(t_runs).strip()
                                        if full_line and full_line not in diag_texts:
                                            diag_texts.append(full_line)
                        except Exception:
                            pass

                if lo_rid and lo_rid in rel_map:
                    lo_rel = rel_map[lo_rid]
                    lo_target = lo_rel.target if hasattr(lo_rel, "target") else str(lo_rel)
                    lo_path = _resolve_path(slide_path, lo_target)
                    if self.package.has_part(lo_path):
                        try:
                            lo_xml = ET.fromstring(self.package.read_part(lo_path))
                            uid = lo_xml.attrib.get("uniqueId", "")
                            if uid:
                                diag_layout = uid.split("/")[-1]
                        except Exception:
                            pass

            sa_items = [{"text": t} for t in diag_texts] if diag_texts else [{"text": "SmartArt"}]
            sa_obj = {
                "layout": diag_layout,
                "items": sa_items,
            }
            combined_txt = "\n".join(diag_texts) if diag_texts else "SmartArt"
            return Shape(
                id=frame_id or "diag_1",
                type="group" if diag_texts else "shape",
                name=frame_name or "Diagram",
                geom="roundRect",
                x=x,
                y=y,
                w=w,
                h=h,
                rot=rot,
                sa=sa_obj,
                text=TextBody.from_text(combined_txt),
            )

        # 2. Find table in graphicData
        tbl_dict: dict[str, Any] = {"cols": [], "rows": []}
        tbl_elem = _get_child(graphic_data, "tbl") if graphic_data is not None else None

        if tbl_elem is not None:
            tbl_grid = _get_child(tbl_elem, "tblGrid")
            if tbl_grid is not None:
                for col_elem in _get_children(tbl_grid, "gridCol"):
                    tbl_dict["cols"].append(emu_to_pt(_get_attr(col_elem, "w"), default=100.0))

            for tr_elem in _get_children(tbl_elem, "tr"):
                h_pt = emu_to_pt(_get_attr(tr_elem, "h"), default=30.0)
                row_cells: list[dict[str, Any]] = []
                for tc_elem in _get_children(tr_elem, "tc"):
                    tx_body = _get_child(tc_elem, "txBody")
                    cell_text = (
                        self._parse_text_body(tx_body) if tx_body is not None else TextBody()
                    )
                    row_cells.append({"tx": cell_text, "text": cell_text.plain_text})
                tbl_dict["rows"].append({"h": h_pt, "cells": row_cells})

        return Shape(
            id=frame_id or "tbl_1",
            type="table",
            name=frame_name or "Table",
            x=x,
            y=y,
            w=w,
            h=h,
            rot=rot,
            tbl=tbl_dict,
        )

    def _parse_group_element(
        self,
        elem: ET.Element,
        slide_path: str,
        rel_map: dict[str, Any],
        layout_info: LayoutInfo | None = None,
        slide_clr_map_ovr: dict[str, str] | None = None,
        group_fill: Fill | None = None,
    ) -> Shape:
        """Parse <p:grpSp> group element recursively."""
        nv_grp_pr = _get_child(elem, "nvGrpSpPr")
        c_nv_pr = _get_child(nv_grp_pr, "cNvPr") if nv_grp_pr is not None else None
        grp_id = _get_attr(c_nv_pr, "id", f"grp_{id(elem)}")
        grp_name = _get_attr(c_nv_pr, "name", "Group")

        grp_sp_pr = _get_child(elem, "grpSpPr")
        x, y, w, h, rot = self._parse_transform(grp_sp_pr)

        # Inherit or parse group fill
        theme_colors, theme_fmt, clr_map, clr_map_ovr = self._resolve_theme_context(
            layout_info, slide_clr_map_ovr
        )
        grp_fill = None
        if grp_sp_pr is not None:
            parsed_grp_fill = self._parse_fill(
                grp_sp_pr,
                theme_colors=theme_colors,
                clr_map=clr_map,
                clr_map_ovr=clr_map_ovr,
                group_fill=group_fill,
            )
            if parsed_grp_fill.type != "none":
                grp_fill = parsed_grp_fill
        if grp_fill is None and group_fill is not None:
            grp_fill = group_fill

        xfrm = _get_child(grp_sp_pr, "xfrm") if grp_sp_pr is not None else None
        ch_off = _get_child(xfrm, "chOff") if xfrm is not None else None
        ch_ext = _get_child(xfrm, "chExt") if xfrm is not None else None
        chx = emu_to_pt(_get_attr(ch_off, "x"), default=0.0) if ch_off is not None else 0.0
        chy = emu_to_pt(_get_attr(ch_off, "y"), default=0.0) if ch_off is not None else 0.0
        chw = emu_to_pt(_get_attr(ch_ext, "cx"), default=w) if ch_ext is not None else w
        chh = emu_to_pt(_get_attr(ch_ext, "cy"), default=h) if ch_ext is not None else h
        sx = (w / chw) if chw > 0.001 else 1.0
        sy = (h / chh) if chh > 0.001 else 1.0

        kids: list[Shape] = []
        for child in elem:
            tag = _local_tag(child.tag)
            if tag in ("sp", "pic", "graphicFrame", "grpSp"):
                kid_shape = self._parse_shape(
                    child,
                    slide_path,
                    rel_map,
                    layout_info=layout_info,
                    slide_clr_map_ovr=slide_clr_map_ovr,
                    group_fill=grp_fill,
                )
                if kid_shape:
                    if ch_off is not None or ch_ext is not None:
                        kid_shape.x = round(x + (kid_shape.x - chx) * sx, 2)
                        kid_shape.y = round(y + (kid_shape.y - chy) * sy, 2)
                        kid_shape.w = round(kid_shape.w * sx, 2)
                        kid_shape.h = round(kid_shape.h * sy, 2)
                    kids.append(kid_shape)

        return Shape(
            id=grp_id or "grp_1",
            type="group",
            name=grp_name or "Group",
            x=x,
            y=y,
            w=w,
            h=h,
            rot=rot,
            kids=kids,
        )

    def _parse_transform(
        self, sp_pr: ET.Element | None
    ) -> tuple[float, float, float, float, float]:
        """Extract x, y, w, h and rotation from <a:xfrm> inside spPr."""
        if sp_pr is None:
            return (0.0, 0.0, 100.0, 100.0, 0.0)
        xfrm = _get_child(sp_pr, "xfrm")
        return self._parse_xfrm_element(xfrm)

    def _parse_xfrm_element(
        self, xfrm: ET.Element | None
    ) -> tuple[float, float, float, float, float]:
        """Parse an <a:xfrm> element into (x, y, w, h, rot) in points."""
        if xfrm is None:
            return (0.0, 0.0, 100.0, 100.0, 0.0)

        off = _get_child(xfrm, "off")
        ext = _get_child(xfrm, "ext")

        x = emu_to_pt(_get_attr(off, "x"), default=0.0)
        y = emu_to_pt(_get_attr(off, "y"), default=0.0)
        w = emu_to_pt(_get_attr(ext, "cx"), default=100.0)
        h = emu_to_pt(_get_attr(ext, "cy"), default=100.0)

        rot_val = _get_attr(xfrm, "rot")
        rot = round(float(rot_val) / 60000.0, 2) if rot_val else 0.0

        return (x, y, w, h, rot)

    def _parse_geometry(self, sp_pr: ET.Element | None) -> tuple[str, dict[str, Any] | None]:
        """Parse preset geometry name or DrawingML a:custGeom custom path."""
        if sp_pr is None:
            return "rect", None
        prst_geom = _get_child(sp_pr, "prstGeom")
        if prst_geom is not None:
            return _get_attr(prst_geom, "prst", "rect") or "rect", None
        cust_geom = _get_child(sp_pr, "custGeom")
        if cust_geom is not None:
            xfrm = _get_child(sp_pr, "xfrm")
            ext = _get_child(xfrm, "ext") if xfrm is not None else None
            ext_w = float(_get_attr(ext, "cx", "0") or 0)
            ext_h = float(_get_attr(ext, "cy", "0") or 0)
            custom_path = self._parse_custom_geometry(cust_geom, ext_w, ext_h)
            if custom_path:
                return "custom", custom_path
        return "rect", None

    def _parse_custom_geometry(
        self, cust_geom: ET.Element, ext_w_emu: float, ext_h_emu: float
    ) -> dict[str, Any] | None:
        """Parse <a:custGeom> with avLst/gdLst guide evaluation and pathLst commands."""
        env = _guide_env(ext_w_emu, ext_h_emu)
        av_lst = _get_child(cust_geom, "avLst")
        if av_lst is not None:
            _eval_guides(_get_children(av_lst, "gd"), env)
        gd_lst = _get_child(cust_geom, "gdLst")
        if gd_lst is not None:
            _eval_guides(_get_children(gd_lst, "gd"), env)

        def resolve_val(tok: str | None) -> float:
            if tok is None:
                return 0.0
            if tok in env:
                return env[tok]
            try:
                return float(tok)
            except (ValueError, TypeError):
                return 0.0

        path_lst = _get_child(cust_geom, "pathLst")
        if path_lst is None:
            return None

        paths: list[dict[str, Any]] = []
        for p_elem in _get_children(path_lst, "path"):
            pw_str = _get_attr(p_elem, "w")
            ph_str = _get_attr(p_elem, "h")
            pw = float(pw_str) if pw_str else ext_w_emu
            ph = float(ph_str) if ph_str else ext_h_emu
            pw_pt = emu_to_pt(pw, default=ext_w_emu / EMUS_PER_PT if ext_w_emu else 100.0)
            ph_pt = emu_to_pt(ph, default=ext_h_emu / EMUS_PER_PT if ext_h_emu else 100.0)

            cmds: list[list[Any]] = []
            for cmd_elem in p_elem:
                tag = _local_tag(cmd_elem.tag)
                pts: list[tuple[float, float]] = []
                for pt_elem in _get_children(cmd_elem, "pt"):
                    px = emu_to_pt(resolve_val(_get_attr(pt_elem, "x")))
                    py = emu_to_pt(resolve_val(_get_attr(pt_elem, "y")))
                    pts.append((px, py))

                if tag == "moveTo" and pts:
                    cmds.append(["M", pts[0][0], pts[0][1]])
                elif tag == "lnTo" and pts:
                    cmds.append(["L", pts[0][0], pts[0][1]])
                elif tag == "cubicBezTo" and len(pts) >= 3:
                    cmds.append(
                        [
                            "C",
                            pts[0][0],
                            pts[0][1],
                            pts[1][0],
                            pts[1][1],
                            pts[2][0],
                            pts[2][1],
                        ]
                    )
                elif tag == "quadBezTo" and len(pts) >= 2:
                    cmds.append(["Q", pts[0][0], pts[0][1], pts[1][0], pts[1][1]])
                elif tag == "arcTo":
                    wr = emu_to_pt(resolve_val(_get_attr(cmd_elem, "wR")))
                    hr = emu_to_pt(resolve_val(_get_attr(cmd_elem, "hR")))
                    st_ang = resolve_val(_get_attr(cmd_elem, "stAng")) / 60000.0
                    sw_ang = resolve_val(_get_attr(cmd_elem, "swAng")) / 60000.0
                    cmds.append(["A", wr, hr, st_ang, sw_ang])
                elif tag == "close":
                    cmds.append(["Z"])

            if cmds:
                paths.append(
                    {
                        "w": pw_pt,
                        "h": ph_pt,
                        "cmds": cmds,
                        "fill": _get_attr(p_elem, "fill", "norm"),
                        "stroke": _get_attr(p_elem, "stroke", "1") not in ("0", "false"),
                    }
                )

        if paths:
            return {"paths": paths}
        return None

    def _load_theme_fonts(self, theme_path: str) -> tuple[str | None, str | None]:
        """Extract major (title) and minor (body) font typefaces from theme XML."""
        if theme_path in self._theme_fonts:
            return self._theme_fonts[theme_path]
        if not self.package.has_part(theme_path):
            return None, None
        try:
            t_bytes = self.package.read_part(theme_path)
            t_xml = ET.fromstring(t_bytes)
            font_scheme = None
            for elem in t_xml.iter():
                if _local_tag(elem.tag) == "fontScheme":
                    font_scheme = elem
                    break
            major = None
            minor = None
            if font_scheme is not None:
                maj_el = _get_child(font_scheme, "majorFont")
                if maj_el is not None:
                    lat = _get_child(maj_el, "latin")
                    if lat is not None:
                        major = _get_attr(lat, "typeface")
                min_el = _get_child(font_scheme, "minorFont")
                if min_el is not None:
                    lat = _get_child(min_el, "latin")
                    if lat is not None:
                        minor = _get_attr(lat, "typeface")
            self._theme_fonts[theme_path] = (major, minor)
            return major, minor
        except Exception:
            return None, None

    def _parse_style_levels(self, style_elem: ET.Element | None) -> dict[int, dict[str, Any]]:
        """Parse paragraph and run styles for levels 1..9 from a txStyles or lstStyle element."""
        levels: dict[int, dict[str, Any]] = {}
        if style_elem is None:
            return levels
        for lvl_idx in range(1, 10):
            lvl_elem = _get_child(style_elem, f"lvl{lvl_idx}pPr")
            if lvl_elem is None:
                continue
            props: dict[str, Any] = {}
            algn = _get_attr(lvl_elem, "algn")
            if algn:
                props["algn"] = algn
            mar_l = _get_attr(lvl_elem, "marL")
            if mar_l is not None:
                props["marL"] = emu_to_pt(mar_l)
            indent = _get_attr(lvl_elem, "indent")
            if indent is not None:
                props["indent"] = emu_to_pt(indent)

            def _parse_spacing(spc_elem: ET.Element | None) -> dict[str, float] | None:
                if spc_elem is None:
                    return None
                pct_elem = _get_child(spc_elem, "spcPct")
                if pct_elem is not None:
                    try:
                        return {"pct": float(_get_attr(pct_elem, "val", 0)) / 1000.0}
                    except (ValueError, TypeError):
                        return None
                pts_elem = _get_child(spc_elem, "spcPts")
                if pts_elem is not None:
                    try:
                        return {"pts": float(_get_attr(pts_elem, "val", 0)) / 100.0}
                    except (ValueError, TypeError):
                        return None
                return None

            ln_spc = _parse_spacing(_get_child(lvl_elem, "lnSpc"))
            if ln_spc:
                props["lnSpc"] = ln_spc
            spc_bef = _parse_spacing(_get_child(lvl_elem, "spcBef"))
            if spc_bef:
                props["spcBef"] = spc_bef
            spc_aft = _parse_spacing(_get_child(lvl_elem, "spcAft"))
            if spc_aft:
                props["spcAft"] = spc_aft

            bu_char = _get_child(lvl_elem, "buChar")
            if bu_char is not None:
                props["bu"] = {"t": "char", "ch": _get_attr(bu_char, "char", "•") or "•"}
            elif _get_child(lvl_elem, "buAutoNum") is not None:
                props["bu"] = {"t": "auto", "ch": "1."}
            elif _get_child(lvl_elem, "buNone") is not None:
                props["bu"] = {"t": "none"}

            def_r_pr = _get_child(lvl_elem, "defRPr")
            if def_r_pr is not None:
                sz = _get_attr(def_r_pr, "sz")
                if sz:
                    try:
                        props["sz"] = round(float(sz) / 100.0, 1)
                    except ValueError:
                        pass
                b_val = _get_attr(def_r_pr, "b")
                if b_val in ("1", "true", "on"):
                    props["b"] = True
                i_val = _get_attr(def_r_pr, "i")
                if i_val in ("1", "true", "on"):
                    props["i"] = True
                latin = _get_child(def_r_pr, "latin")
                if latin is not None:
                    props["font"] = _get_attr(latin, "typeface")
                solid_fill = _get_child(def_r_pr, "solidFill")
                if solid_fill is not None:
                    clr = self._extract_color(solid_fill)
                    if clr:
                        props["color"] = clr
            levels[lvl_idx - 1] = props
        return levels

    def _extract_placeholders_from_tree(
        self, sp_tree: ET.Element | None
    ) -> list[PlaceholderTemplate]:
        """Extract placeholder shapes and properties from an spTree element."""
        placeholders: list[PlaceholderTemplate] = []
        if sp_tree is None:
            return placeholders
        for sp in sp_tree:
            if _local_tag(sp.tag) != "sp":
                continue
            nv_sp_pr = _get_child(sp, "nvSpPr")
            c_nv_pr = _get_child(nv_sp_pr, "cNvPr") if nv_sp_pr is not None else None
            nv_pr = _get_child(nv_sp_pr, "nvPr") if nv_sp_pr is not None else None
            ph_elem = _get_child(nv_pr, "ph") if nv_pr is not None else None
            if ph_elem is None:
                continue

            ph_type = _get_attr(ph_elem, "type", "body") or "body"
            ph_idx = int(_get_attr(ph_elem, "idx", "0") or 0)
            sp_id = _get_attr(c_nv_pr, "id", "") or ""

            sp_pr = _get_child(sp, "spPr")
            xfrm = None
            if sp_pr is not None and _get_child(sp_pr, "xfrm") is not None:
                xfrm = self._parse_transform(sp_pr)
            fill = self._parse_fill(sp_pr) if sp_pr is not None else None
            line = self._parse_line(sp_pr) if sp_pr is not None else None
            tx_body = _get_child(sp, "txBody")
            text_body = self._parse_text_body(tx_body) if tx_body is not None else None

            placeholders.append(
                PlaceholderTemplate(
                    type=ph_type,
                    idx=ph_idx,
                    shape_id=sp_id,
                    xfrm=xfrm,
                    fill=fill,
                    line=line,
                    text_body=text_body,
                )
            )
        return placeholders

    def _load_master(self, master_path: str) -> MasterInfo | None:
        """Load and cache slideMaster.xml, its placeholders, and text style hierarchies."""
        if master_path in self._masters:
            return self._masters[master_path]
        if not self.package.has_part(master_path):
            return None
        try:
            m_bytes = self.package.read_part(master_path)
            m_xml = ET.fromstring(m_bytes)
            m_rels = self.package.get_relationships(master_path)

            theme_rel = next(
                (r for r in m_rels if r.type == REL_THEME or r.type.endswith("/theme")),
                None,
            )
            major_font = None
            minor_font = None
            t_path = ""
            if theme_rel:
                t_path = _resolve_path(master_path, theme_rel.target)
                major_font, minor_font = self._load_theme_fonts(t_path)

            clr_map_elem = _get_child(m_xml, "clrMap")
            m_clr_map: dict[str, str] = {}
            if clr_map_elem is not None:
                for k in (
                    "bg1",
                    "tx1",
                    "bg2",
                    "tx2",
                    "accent1",
                    "accent2",
                    "accent3",
                    "accent4",
                    "accent5",
                    "accent6",
                    "hlink",
                    "folHlink",
                ):
                    v = _get_attr(clr_map_elem, k)
                    if v:
                        m_clr_map[k] = v

            c_sld = _get_child(m_xml, "cSld")
            sp_tree = _get_child(c_sld, "spTree") if c_sld is not None else None
            phs = self._extract_placeholders_from_tree(sp_tree)

            m_rel_map = {r.id: r for r in m_rels}
            m_decos: list[Shape] = []
            if sp_tree is not None:
                for child in sp_tree:
                    ltag = _local_tag(child.tag)
                    if ltag in ("sp", "pic", "graphicFrame", "grpSp"):
                        has_ph = any(_local_tag(sub.tag) == "ph" for sub in child.iter())
                        if not has_ph:
                            sh = self._parse_shape(child, master_path, m_rel_map)
                            if sh:
                                m_decos.append(sh)

            m_bg: Fill | None = None
            if c_sld is not None:
                bg_elem = _get_child(c_sld, "bg")
                if bg_elem is not None:
                    bg_pr = _get_child(bg_elem, "bgPr")
                    if bg_pr is not None:
                        m_bg = self._parse_fill(bg_pr)

            tx_styles = _get_child(m_xml, "txStyles")
            t_style = self._parse_style_levels(
                _get_child(tx_styles, "titleStyle") if tx_styles is not None else None
            )
            b_style = self._parse_style_levels(
                _get_child(tx_styles, "bodyStyle") if tx_styles is not None else None
            )
            o_style = self._parse_style_levels(
                _get_child(tx_styles, "otherStyle") if tx_styles is not None else None
            )

            info = MasterInfo(
                master_path=master_path,
                placeholders=phs,
                title_style=t_style,
                body_style=b_style,
                other_style=o_style,
                major_font=major_font,
                minor_font=minor_font,
                decorations=m_decos,
                bg=m_bg,
                clr_map=m_clr_map,
                theme_path=t_path,
            )
            self._masters[master_path] = info
            return info
        except Exception:
            return None

    def _load_layout(self, layout_path: str) -> LayoutInfo | None:
        """Load and cache slideLayout.xml, its link to master, and its placeholder shapes."""
        if layout_path in self._layouts:
            return self._layouts[layout_path]
        if not self.package.has_part(layout_path):
            return None
        try:
            l_bytes = self.package.read_part(layout_path)
            l_xml = ET.fromstring(l_bytes)
            l_rels = self.package.get_relationships(layout_path)

            m_rel = next(
                (
                    r
                    for r in l_rels
                    if r.type == REL_SLIDE_MASTER or r.type.endswith("/slideMaster")
                ),
                None,
            )
            master_info = None
            if m_rel:
                m_path = _resolve_path(layout_path, m_rel.target)
                master_info = self._load_master(m_path)

            c_sld = _get_child(l_xml, "cSld")
            sp_tree = _get_child(c_sld, "spTree") if c_sld is not None else None
            phs = self._extract_placeholders_from_tree(sp_tree)

            l_rel_map = {r.id: r for r in l_rels}
            l_decos: list[Shape] = []
            if sp_tree is not None:
                for child in sp_tree:
                    ltag = _local_tag(child.tag)
                    if ltag in ("sp", "pic", "graphicFrame", "grpSp"):
                        has_ph = any(_local_tag(sub.tag) == "ph" for sub in child.iter())
                        if not has_ph:
                            sh = self._parse_shape(child, layout_path, l_rel_map)
                            if sh:
                                l_decos.append(sh)

            l_bg: Fill | None = None
            if c_sld is not None:
                bg_elem = _get_child(c_sld, "bg")
                if bg_elem is not None:
                    bg_pr = _get_child(bg_elem, "bgPr")
                    if bg_pr is not None:
                        l_bg = self._parse_fill(bg_pr)

            show_master = _get_attr(l_xml, "showMasterSp") != "0"
            l_type = _get_attr(l_xml, "type", "") or ""

            clr_map_ovr_elem = _get_child(l_xml, "clrMapOvr")
            l_clr_map_ovr: dict[str, str] = {}
            if clr_map_ovr_elem is not None:
                ovr_el = _get_child(clr_map_ovr_elem, "overrideClrMapping")
                if ovr_el is not None:
                    for k in (
                        "bg1",
                        "tx1",
                        "bg2",
                        "tx2",
                        "accent1",
                        "accent2",
                        "accent3",
                        "accent4",
                        "accent5",
                        "accent6",
                        "hlink",
                        "folHlink",
                    ):
                        v = _get_attr(ovr_el, k)
                        if v:
                            l_clr_map_ovr[k] = v

            info = LayoutInfo(
                layout_path=layout_path,
                master=master_info,
                placeholders=phs,
                decorations=l_decos,
                bg=l_bg,
                show_master=show_master,
                layout_type=l_type,
                clr_map_ovr=l_clr_map_ovr,
            )
            self._layouts[layout_path] = info
            return info
        except Exception:
            return None

    def _match_layout_ph(
        self, layout_phs: list[PlaceholderTemplate], ph: PlaceholderInfo
    ) -> PlaceholderTemplate | None:
        """Find matching placeholder in slideLayout."""
        for lp in layout_phs:
            if lp.type == ph.type and lp.idx == ph.idx:
                return lp
        t = ph.type or "body"
        want = (
            ["title", "ctrTitle"]
            if t in ("title", "ctrTitle")
            else (["body", "obj"] if t in ("body", "obj", "subTitle") else [t])
        )
        for w in want:
            for lp in layout_phs:
                if lp.type == w:
                    return lp
        return None

    def _match_master_ph(
        self, master_phs: list[PlaceholderTemplate], ph_type: str
    ) -> PlaceholderTemplate | None:
        """Find matching placeholder in slideMaster by type."""
        t = ph_type or "obj"
        want = (
            ["title", "ctrTitle"]
            if t in ("title", "ctrTitle")
            else ([t] if t in ("dt", "ftr", "sldNum", "hdr") else ["body", "obj"])
        )
        for w in want:
            for mp in master_phs:
                if mp.type == w:
                    return mp
        return None

    def _apply_placeholder_text_inheritance(
        self,
        text_body: TextBody,
        ph: PlaceholderInfo,
        layout_info: LayoutInfo | None,
        lp: PlaceholderTemplate | None,
        mp: PlaceholderTemplate | None,
    ) -> None:
        """Inherit missing font sizes, typefaces, colors, and alignments from layout and master."""
        master_info = layout_info.master if layout_info else None
        ph_type = ph.type or "body"
        is_title = ph_type in ("title", "ctrTitle")

        style_dict: dict[int, dict[str, Any]] = {}
        default_font = None
        if master_info:
            style_dict = master_info.title_style if is_title else master_info.body_style
            default_font = master_info.major_font if is_title else master_info.minor_font

        lp_paras = lp.text_body.paragraphs if (lp and lp.text_body) else []
        mp_paras = mp.text_body.paragraphs if (mp and mp.text_body) else []

        # Inherit bodyPr properties if missing on shape text_body
        lp_tb = lp.text_body if lp else None
        mp_tb = mp.text_body if mp else None

        if text_body.anchor == "t":
            if lp_tb and lp_tb.anchor != "t":
                text_body.anchor = lp_tb.anchor
            elif mp_tb and mp_tb.anchor != "t":
                text_body.anchor = mp_tb.anchor

        if not text_body.anchor_ctr:
            if lp_tb and lp_tb.anchor_ctr:
                text_body.anchor_ctr = True
            elif mp_tb and mp_tb.anchor_ctr:
                text_body.anchor_ctr = True

        if text_body.autofit == "none":
            if lp_tb and lp_tb.autofit != "none":
                text_body.autofit = lp_tb.autofit
            elif mp_tb and mp_tb.autofit != "none":
                text_body.autofit = mp_tb.autofit

        if not text_body.has_explicit_font_scale:
            if lp_tb and lp_tb.has_explicit_font_scale:
                text_body.font_scale = lp_tb.font_scale
                text_body.ln_spc_reduction = lp_tb.ln_spc_reduction
                text_body.has_explicit_font_scale = True
            elif mp_tb and mp_tb.has_explicit_font_scale:
                text_body.font_scale = mp_tb.font_scale
                text_body.ln_spc_reduction = mp_tb.ln_spc_reduction
                text_body.has_explicit_font_scale = True

        for p in text_body.paragraphs:
            lvl = p.level
            lp_p = next((x for x in lp_paras if x.level == lvl), lp_paras[0] if lp_paras else None)
            mp_p = next((x for x in mp_paras if x.level == lvl), mp_paras[0] if mp_paras else None)
            lvl_style = style_dict.get(lvl) or style_dict.get(0) or {}

            # Alignment
            if "algn" not in p.props:
                if lp_p and "algn" in lp_p.props:
                    p.props["algn"] = lp_p.props["algn"]
                elif mp_p and "algn" in mp_p.props:
                    p.props["algn"] = mp_p.props["algn"]
                elif "algn" in lvl_style:
                    p.props["algn"] = lvl_style["algn"]

            # Bullet
            if "bu" not in p.props:
                if lp_p and "bu" in lp_p.props:
                    p.props["bu"] = copy.deepcopy(lp_p.props["bu"])
                elif mp_p and "bu" in mp_p.props:
                    p.props["bu"] = copy.deepcopy(mp_p.props["bu"])
                elif "bu" in lvl_style:
                    p.props["bu"] = copy.deepcopy(lvl_style["bu"])

            # Left margin and indent
            if "marL" not in p.props:
                if lp_p and "marL" in lp_p.props:
                    p.props["marL"] = lp_p.props["marL"]
                elif mp_p and "marL" in mp_p.props:
                    p.props["marL"] = mp_p.props["marL"]
                elif "marL" in lvl_style:
                    p.props["marL"] = lvl_style["marL"]

            if "indent" not in p.props:
                if lp_p and "indent" in lp_p.props:
                    p.props["indent"] = lp_p.props["indent"]
                elif mp_p and "indent" in mp_p.props:
                    p.props["indent"] = mp_p.props["indent"]
                elif "indent" in lvl_style:
                    p.props["indent"] = lvl_style["indent"]

            # Spacing
            if "lnSpc" not in p.props:
                if lp_p and "lnSpc" in lp_p.props:
                    p.props["lnSpc"] = copy.deepcopy(lp_p.props["lnSpc"])
                elif mp_p and "lnSpc" in mp_p.props:
                    p.props["lnSpc"] = copy.deepcopy(mp_p.props["lnSpc"])
                elif "lnSpc" in lvl_style:
                    p.props["lnSpc"] = copy.deepcopy(lvl_style["lnSpc"])

            if "spcBef" not in p.props:
                if lp_p and "spcBef" in lp_p.props:
                    p.props["spcBef"] = copy.deepcopy(lp_p.props["spcBef"])
                elif mp_p and "spcBef" in mp_p.props:
                    p.props["spcBef"] = copy.deepcopy(mp_p.props["spcBef"])
                elif "spcBef" in lvl_style:
                    p.props["spcBef"] = copy.deepcopy(lvl_style["spcBef"])

            if "spcAft" not in p.props:
                if lp_p and "spcAft" in lp_p.props:
                    p.props["spcAft"] = copy.deepcopy(lp_p.props["spcAft"])
                elif mp_p and "spcAft" in mp_p.props:
                    p.props["spcAft"] = copy.deepcopy(mp_p.props["spcAft"])
                elif "spcAft" in lvl_style:
                    p.props["spcAft"] = copy.deepcopy(lvl_style["spcAft"])

            lp_r = lp_p.runs[0] if (lp_p and lp_p.runs) else None
            mp_r = mp_p.runs[0] if (mp_p and mp_p.runs) else None

            for r in p.runs:
                # Size
                if r.size is None:
                    if lp_r and lp_r.size is not None:
                        r.size = lp_r.size
                    elif mp_r and mp_r.size is not None:
                        r.size = mp_r.size
                    elif "sz" in lvl_style:
                        r.size = lvl_style["sz"]

                # Color
                if r.color is None:
                    if lp_r and lp_r.color is not None:
                        r.color = lp_r.color
                    elif mp_r and mp_r.color is not None:
                        r.color = mp_r.color
                    elif "color" in lvl_style:
                        r.color = lvl_style["color"]

                # Font
                if r.font is None:
                    if lp_r and lp_r.font is not None:
                        r.font = lp_r.font
                    elif mp_r and mp_r.font is not None:
                        r.font = mp_r.font
                    elif "font" in lvl_style:
                        r.font = lvl_style["font"]
                    elif default_font:
                        r.font = default_font

                # Bold
                if not r.bold:
                    if lp_r and lp_r.bold:
                        r.bold = True
                    elif mp_r and mp_r.bold:
                        r.bold = True
                    elif lvl_style.get("b"):
                        r.bold = True

                # Italic
                if not r.italic:
                    if lp_r and lp_r.italic:
                        r.italic = True
                    elif mp_r and mp_r.italic:
                        r.italic = True
                    elif lvl_style.get("i"):
                        r.italic = True

    def _parse_slide_animations(
        self,
        timing_elem: ET.Element | None,
        shapes: list[Shape],
    ) -> list[Animation]:
        """Parse sequential and parallel animation effects from <p:timing>."""
        if timing_elem is None:
            return []

        # Find mainSeq cTn element
        main_seq = None
        for elem in timing_elem.iter():
            if _local_tag(elem.tag) == "cTn" and _get_attr(elem, "nodeType") == "mainSeq":
                main_seq = elem
                break

        target_root = main_seq if main_seq is not None else timing_elem

        id_map: dict[str, str] = {}
        for s in shapes:
            id_map[s.id] = s.id
            if s.name:
                id_map[s.name] = s.id

        ENTR_MAP = {
            1: "appear",
            2: "flyIn",
            3: "blinds",
            4: "box",
            5: "checkerboard",
            6: "circle",
            8: "diamond",
            9: "dissolve",
            10: "fade",
            12: "peekIn",
            13: "plus",
            14: "randomBars",
            16: "split",
            18: "strips",
            20: "wedge",
            21: "wheel",
            22: "wipe",
            23: "zoom",
            42: "ascend",
            47: "descend",
            49: "spinner",
            55: "expand",
        }
        EXIT_MAP = {
            "appear": "disappear",
            "flyIn": "flyOut",
            "ascend": "descend",
            "expand": "fade",
            "spinner": "zoom",
        }
        EMPH_MAP = {
            6: "growShrink",
            8: "spin",
            9: "transparency",
            32: "teeter",
            35: "blink",
        }
        DIR_MAP = {
            1: "b",
            2: "l",
            4: "r",
            8: "t",
            5: "rb",
            9: "rt",
            6: "lb",
            10: "lt",
        }

        animations: list[Animation] = []

        for ctn in target_root.iter():
            if _local_tag(ctn.tag) != "cTn":
                continue
            cls = _get_attr(ctn, "presetClass")
            if not cls or cls not in ("entr", "exit", "emph", "path"):
                continue

            spid = None
            para_idx = None
            for descendant in ctn.iter():
                dtag = _local_tag(descendant.tag)
                if dtag == "spTgt":
                    spid = _get_attr(descendant, "spid")
                    prg = _get_child(descendant, "pRg")
                    if prg is not None:
                        st = _get_attr(prg, "st")
                        if st is not None:
                            try:
                                para_idx = int(st)
                            except ValueError:
                                pass
                    break

            if not spid:
                continue

            sid = id_map.get(spid, spid)

            node_type = _get_attr(ctn, "nodeType")
            if node_type == "clickEffect":
                start = "click"
            elif node_type == "afterEffect":
                start = "after"
            elif node_type == "withEffect":
                start = "with"
            else:
                has_click = False
                has_after = False
                for cond in ctn.iter():
                    if _local_tag(cond.tag) == "cond":
                        delay_attr = _get_attr(cond, "delay", "")
                        evt_attr = _get_attr(cond, "evt", "")
                        if delay_attr == "indefinite" or evt_attr in ("onClick", "onNext"):
                            has_click = True
                        elif evt_attr == "onEnd":
                            has_after = True
                if has_click:
                    start = "click"
                elif has_after:
                    start = "after"
                else:
                    start = "with"

            dur_val = _get_attr(ctn, "dur")
            dur = 500
            if dur_val and dur_val != "indefinite":
                try:
                    dur = int(float(dur_val))
                except ValueError:
                    dur = 500

            delay = 0
            for cond in ctn.iter():
                if _local_tag(cond.tag) == "cond":
                    d_val = _get_attr(cond, "delay")
                    if d_val and d_val != "indefinite":
                        try:
                            delay = int(float(d_val))
                            break
                        except ValueError:
                            pass

            pid = 10
            pid_str = _get_attr(ctn, "presetID")
            if pid_str:
                try:
                    pid = int(pid_str)
                except ValueError:
                    pid = 10

            sub = 0
            sub_str = _get_attr(ctn, "presetSubtype")
            if sub_str:
                try:
                    sub = int(sub_str)
                except ValueError:
                    sub = 0

            direction = None
            if cls in ("entr", "exit"):
                eff = ENTR_MAP.get(pid)
                if not eff:
                    anim_effect = next(
                        (c for c in ctn.iter() if _local_tag(c.tag) == "animEffect"), None
                    )
                    eff = _get_attr(anim_effect, "filter", "fade") or "fade"

                if cls == "exit":
                    eff = EXIT_MAP.get(eff, eff)

                direction = DIR_MAP.get(sub)
                if not direction and eff in ("flyIn", "flyOut"):
                    direction = "b"

                if eff in ("appear", "disappear"):
                    dur = 1

            elif cls == "emph":
                eff = EMPH_MAP.get(pid, "growShrink")
            elif cls == "path":
                eff = "custom"
            else:
                eff = "fade"

            by = "para" if para_idx is not None else "all"

            anim = Animation(
                id=f"a_{uuid.uuid4().hex[:6]}",
                sid=sid,
                cls=cls,
                eff=eff,
                dir=direction,
                start=start,
                dur=dur,
                delay=delay,
                by=by,
                para=para_idx,
            )
            animations.append(anim)

        return animations

    def _parse_fill(
        self,
        sp_pr: ET.Element | None,
        ph_clr: str | None = None,
        theme_colors: ColorScheme | None = None,
        clr_map: dict[str, str] | None = None,
        clr_map_ovr: dict[str, str] | None = None,
        group_fill: Fill | None = None,
    ) -> Fill:
        """Parse shape fill style (solid, gradient, none, group fill)."""
        if sp_pr is None:
            return Fill.none()

        tag = _local_tag(sp_pr.tag)
        if tag == "noFill":
            return Fill.none()
        elif tag == "solidFill":
            clr, alpha = self._extract_color_detail(
                sp_pr,
                ph_clr=ph_clr,
                theme_colors=theme_colors,
                clr_map=clr_map,
                clr_map_ovr=clr_map_ovr,
                keep_scheme=True,
            )
            return Fill.solid(clr or "#FFFFFF", alpha)
        elif tag == "gradFill":
            gs_lst = _get_child(sp_pr, "gsLst")
            stops: list[dict[str, Any]] = []
            if gs_lst is not None:
                for gs in _get_children(gs_lst, "gs"):
                    pos = float(_get_attr(gs, "pos", "0") or 0) / 100000.0
                    clr, alpha = self._extract_color_detail(
                        gs,
                        ph_clr=ph_clr,
                        theme_colors=theme_colors,
                        clr_map=clr_map,
                        clr_map_ovr=clr_map_ovr,
                    )
                    stops.append({"p": pos, "c": clr or "#FFFFFF", "a": alpha})
            return Fill.gradient(stops)

        if _get_child(sp_pr, "noFill") is not None:
            return Fill.none()

        if _get_child(sp_pr, "grpFill") is not None:
            if group_fill is not None:
                return copy.deepcopy(group_fill)
            return Fill.none()

        solid_fill = _get_child(sp_pr, "solidFill")
        if solid_fill is not None:
            clr, alpha = self._extract_color_detail(
                solid_fill,
                ph_clr=ph_clr,
                theme_colors=theme_colors,
                clr_map=clr_map,
                clr_map_ovr=clr_map_ovr,
                keep_scheme=True,
            )
            return Fill.solid(clr or "#FFFFFF", alpha)

        grad_fill = _get_child(sp_pr, "gradFill")
        if grad_fill is not None:
            gs_lst = _get_child(grad_fill, "gsLst")
            stops = []
            if gs_lst is not None:
                for gs in _get_children(gs_lst, "gs"):
                    pos = float(_get_attr(gs, "pos", "0") or 0) / 100000.0
                    clr, alpha = self._extract_color_detail(
                        gs,
                        ph_clr=ph_clr,
                        theme_colors=theme_colors,
                        clr_map=clr_map,
                        clr_map_ovr=clr_map_ovr,
                    )
                    stops.append({"p": pos, "c": clr or "#FFFFFF", "a": alpha})
            return Fill.gradient(stops)

        return Fill.none()

    def _parse_line(
        self,
        sp_pr: ET.Element | None,
        base_line: Line | None = None,
        ph_clr: str | None = None,
        theme_colors: ColorScheme | None = None,
        clr_map: dict[str, str] | None = None,
        clr_map_ovr: dict[str, str] | None = None,
    ) -> Line:
        """Parse shape outline line style."""
        res = copy.deepcopy(base_line) if base_line is not None else Line.none()
        if sp_pr is None:
            return res

        ln_elem = sp_pr if _local_tag(sp_pr.tag) == "ln" else _get_child(sp_pr, "ln")
        if ln_elem is None:
            return res

        if _get_child(ln_elem, "noFill") is not None:
            return Line.none()

        w_emu = _get_attr(ln_elem, "w")
        if w_emu:
            res.width = emu_to_pt(w_emu, default=res.width or 0.75)
        elif res.type == "none":
            res.width = 0.75

        solid_fill = _get_child(ln_elem, "solidFill")
        if solid_fill is not None:
            clr, _ = self._extract_color_detail(
                solid_fill,
                ph_clr=ph_clr,
                theme_colors=theme_colors,
                clr_map=clr_map,
                clr_map_ovr=clr_map_ovr,
                keep_scheme=True,
            )
            if clr:
                res.color = clr
                res.type = "solid"

        prst_dash = _get_child(ln_elem, "prstDash")
        if prst_dash is not None:
            res.dash = _get_attr(prst_dash, "val", "solid") or "solid"

        cust_dash = _get_child(ln_elem, "custDash")
        if cust_dash is not None:
            dashes: list[float] = []
            for ds in _get_children(cust_dash, "ds"):
                d_val = float(_get_attr(ds, "d", "0") or 0) / 100000.0
                sp_val = float(_get_attr(ds, "sp", "0") or 0) / 100000.0
                dashes.extend([d_val, sp_val])
            if dashes:
                res.custom_dash = dashes
                res.dash = "custom"

        if res.type == "none" and (
            solid_fill is not None
            or w_emu is not None
            or prst_dash is not None
            or cust_dash is not None
        ):
            res.type = "solid"
            if not res.color:
                res.color = "tx1"

        return res

    def _parse_shadow(self, sp_pr: ET.Element | None) -> Shadow | None:
        """Parse drop shadow from <a:effectLst>/<a:outerShdw>."""
        if sp_pr is None:
            return None
        effect_lst = _get_child(sp_pr, "effectLst")
        if effect_lst is None:
            return None
        outer_shdw = _get_child(effect_lst, "outerShdw")
        if outer_shdw is None:
            return None

        blur = emu_to_pt(_get_attr(outer_shdw, "blurRad"), default=3.0)
        dist = emu_to_pt(_get_attr(outer_shdw, "dist"), default=1.0)
        clr = self._extract_color(outer_shdw) or "#000000"
        return Shadow(blur=blur, dist=dist, color=clr)

    def _parse_text_body(
        self,
        tx_body: ET.Element | None,
        default_color: str | None = None,
        default_font: str | None = None,
        rel_map: dict[str, Any] | None = None,
    ) -> TextBody:
        """Parse <p:txBody> into TextBody with paragraphs and runs."""
        if tx_body is None:
            return TextBody()

        body_pr = _get_child(tx_body, "bodyPr")
        insets = (7.2, 3.6, 7.2, 3.6)
        wrap = True
        anchor = "t"
        anchor_ctr = False
        autofit = "none"

        font_scale = 1.0
        ln_spc_red = 0.0
        has_explicit_font_scale = False
        if body_pr is not None:
            l_ins = emu_to_pt(_get_attr(body_pr, "lIns"), default=7.2)
            t_ins = emu_to_pt(_get_attr(body_pr, "tIns"), default=3.6)
            r_ins = emu_to_pt(_get_attr(body_pr, "rIns"), default=7.2)
            b_ins = emu_to_pt(_get_attr(body_pr, "bIns"), default=3.6)
            insets = (l_ins, t_ins, r_ins, b_ins)

            anchor_val = _get_attr(body_pr, "anchor")
            if anchor_val:
                if anchor_val in ("just", "dist"):
                    anchor = "ctr"
                elif anchor_val in ("t", "ctr", "b"):
                    anchor = anchor_val
                else:
                    anchor = anchor_val

            anchor_ctr_val = _get_attr(body_pr, "anchorCtr")
            if anchor_ctr_val in ("1", "true", "True"):
                anchor_ctr = True

            wrap_val = _get_attr(body_pr, "wrap")
            if wrap_val == "none":
                wrap = False

            norm_elem = _get_child(body_pr, "normAutofit")
            if norm_elem is not None:
                autofit = "norm"
                fs_attr = _get_attr(norm_elem, "fontScale")
                if fs_attr:
                    try:
                        font_scale = max(0.01, min(1.0, float(fs_attr) / 100000.0))
                        has_explicit_font_scale = True
                    except ValueError:
                        font_scale = 1.0
                ls_attr = _get_attr(norm_elem, "lnSpcReduction")
                if ls_attr:
                    try:
                        ln_spc_red = max(0.0, min(1.0, float(ls_attr) / 100000.0))
                    except ValueError:
                        ln_spc_red = 0.0
            elif _get_child(body_pr, "spAutoFit") is not None:
                autofit = "shape"

        lst_style_elem = _get_child(tx_body, "lstStyle")
        lst_styles = (
            self._parse_style_levels(lst_style_elem)
            if lst_style_elem is not None
            else {}
        )

        paragraphs: list[Paragraph] = []
        for p_elem in _get_children(tx_body, "p"):
            p = self._parse_paragraph(
                p_elem,
                default_color=default_color,
                default_font=default_font,
                rel_map=rel_map,
            )
            if lst_styles:
                lvl_style = lst_styles.get(p.level) or lst_styles.get(0) or {}
                for k in ("algn", "marL", "indent", "bu", "lnSpc", "spcBef", "spcAft"):
                    if k not in p.props and k in lvl_style:
                        p.props[k] = copy.deepcopy(lvl_style[k])
                for r in p.runs:
                    if r.size is None and "sz" in lvl_style:
                        r.size = lvl_style["sz"]
                    if r.font is None and "font" in lvl_style:
                        r.font = lvl_style["font"]
                    if r.color is None and "color" in lvl_style:
                        r.color = lvl_style["color"]
                    if not r.bold and lvl_style.get("b"):
                        r.bold = True
            paragraphs.append(p)

        return TextBody(
            paragraphs=paragraphs,
            insets=insets,
            wrap=wrap,
            anchor=anchor,
            anchor_ctr=anchor_ctr,
            autofit=autofit,
            font_scale=font_scale,
            ln_spc_reduction=ln_spc_red,
            has_explicit_font_scale=has_explicit_font_scale,
        )

    def _parse_paragraph(
        self,
        p_elem: ET.Element,
        default_color: str | None = None,
        default_font: str | None = None,
        rel_map: dict[str, Any] | None = None,
    ) -> Paragraph:
        """Parse <a:p> paragraph element."""
        p_pr = _get_child(p_elem, "pPr")
        level = 0
        algn_val = None
        bullet = BulletInfo(type="none")
        mar_l_val = None
        indent_val = None
        ln_spc = None
        spc_bef = None
        spc_aft = None

        if p_pr is not None:
            lvl_val = _get_attr(p_pr, "lvl")
            if lvl_val:
                try:
                    level = int(lvl_val)
                except ValueError:
                    level = 0

            algn_val = _get_attr(p_pr, "algn")

            mar_l_str = _get_attr(p_pr, "marL")
            if mar_l_str is not None:
                mar_l_val = emu_to_pt(mar_l_str)

            indent_str = _get_attr(p_pr, "indent")
            if indent_str is not None:
                indent_val = emu_to_pt(indent_str)

            def _parse_spacing(spc_elem: ET.Element | None) -> dict[str, float] | None:
                if spc_elem is None:
                    return None
                pct_elem = _get_child(spc_elem, "spcPct")
                if pct_elem is not None:
                    try:
                        return {"pct": float(_get_attr(pct_elem, "val", 0)) / 1000.0}
                    except (ValueError, TypeError):
                        return None
                pts_elem = _get_child(spc_elem, "spcPts")
                if pts_elem is not None:
                    try:
                        return {"pts": float(_get_attr(pts_elem, "val", 0)) / 100.0}
                    except (ValueError, TypeError):
                        return None
                return None

            ln_spc = _parse_spacing(_get_child(p_pr, "lnSpc"))
            spc_bef = _parse_spacing(_get_child(p_pr, "spcBef"))
            spc_aft = _parse_spacing(_get_child(p_pr, "spcAft"))

            bu_char = _get_child(p_pr, "buChar")
            if bu_char is not None:
                char_val = _get_attr(bu_char, "char", "•") or "•"
                bullet = BulletInfo(type="char", char=char_val)
            elif _get_child(p_pr, "buAutoNum") is not None:
                bullet = BulletInfo(type="auto", char="1.")

        runs: list[Run] = []
        for child in p_elem:
            ltag = _local_tag(child.tag)
            if ltag == "r":
                runs.append(
                    self._parse_run(
                        child,
                        default_color=default_color,
                        default_font=default_font,
                        rel_map=rel_map,
                    )
                )
            elif ltag == "fld":
                fld_type = _get_attr(child, "type", "") or ""
                r = self._parse_run(
                    child,
                    default_color=default_color,
                    default_font=default_font,
                    rel_map=rel_map,
                )
                r.field = fld_type
                runs.append(r)
            elif ltag == "br":
                runs.append(Run(text="\n"))

        props: dict[str, Any] = {}
        if algn_val:
            props["algn"] = algn_val
        if mar_l_val is not None:
            props["marL"] = mar_l_val
        if indent_val is not None:
            props["indent"] = indent_val
        if ln_spc:
            props["lnSpc"] = ln_spc
        if spc_bef:
            props["spcBef"] = spc_bef
        if spc_aft:
            props["spcAft"] = spc_aft
        if bullet and bullet.type != "none":
            props["bu"] = bullet.to_dict()

        return Paragraph(
            level=level,
            props=props,
            runs=runs,
        )

    def _parse_run(
        self,
        r_elem: ET.Element,
        default_color: str | None = None,
        default_font: str | None = None,
        rel_map: dict[str, Any] | None = None,
    ) -> Run:
        """Parse <a:r> run element."""
        r_pr = _get_child(r_elem, "rPr")
        t_elem = _get_child(r_elem, "t")
        text = t_elem.text if (t_elem is not None and t_elem.text) else ""

        font: str | None = None
        size: float | None = None
        color: str | None = None
        bold = False
        italic = False
        underline = False
        strike = False
        link: str | None = None

        if r_pr is not None:
            sz_val = _get_attr(r_pr, "sz")
            if sz_val:
                try:
                    size = round(float(sz_val) / 100.0, 1)
                except ValueError:
                    pass

            b_val = _get_attr(r_pr, "b")
            bold = b_val in ("1", "true", "on")

            i_val = _get_attr(r_pr, "i")
            italic = i_val in ("1", "true", "on")

            u_val = _get_attr(r_pr, "u")
            underline = u_val not in (None, "none")

            strike_val = _get_attr(r_pr, "strike")
            strike = strike_val not in (None, "noStrike")

            latin = _get_child(r_pr, "latin")
            if latin is not None:
                font = _get_attr(latin, "typeface")

            solid_fill = _get_child(r_pr, "solidFill")
            if solid_fill is not None:
                color = self._extract_color(solid_fill)

            hlink_elem = _get_child(r_pr, "hlinkClick")
            if hlink_elem is not None:
                r_id = ""
                for k, v in hlink_elem.attrib.items():
                    if _local_tag(k) in ("id", "link", "embed"):
                        r_id = v
                        break
                if r_id and rel_map and r_id in rel_map:
                    rel = rel_map[r_id]
                    link = rel.target
                elif not link:
                    link = _get_attr(hlink_elem, "action", "")
                if link:
                    color = "hlink"
                    underline = True

        if color is None and default_color:
            color = default_color
        if font is None and default_font:
            font = default_font

        return Run(
            text=text,
            font=font,
            size=size,
            color=color,
            bold=bold,
            italic=italic,
            underline=underline,
            strike=strike,
            link=link,
        )

    def _parse_transition(self, trans_elem: ET.Element | None) -> Transition:
        """Parse slide transition timing and type."""
        if trans_elem is None:
            return Transition()

        trans_type = "none"
        dir_val = None
        orient_val = None
        spokes_val = None
        thru_blk = False

        KNOWN_TRANSITIONS = (
            "fade",
            "wipe",
            "push",
            "split",
            "cover",
            "pull",
            "wheel",
            "zoom",
            "blinds",
            "checker",
            "comb",
            "cut",
            "dissolve",
            "newsflash",
            "plus",
            "randomBar",
            "circle",
            "diamond",
            "strips",
            "wedge",
            "random",
        )

        for child in trans_elem:
            tag = _local_tag(child.tag)
            if tag in KNOWN_TRANSITIONS:
                trans_type = tag
                dir_val = _get_attr(child, "dir")
                orient_val = _get_attr(child, "orient")
                sp_attr = _get_attr(child, "spokes")
                if sp_attr:
                    try:
                        spokes_val = int(sp_attr)
                    except ValueError:
                        pass
                thru_attr = _get_attr(child, "thruBlk")
                if thru_attr in ("1", "true"):
                    thru_blk = True
                break

        speed = _get_attr(trans_elem, "spd", "fast") or "fast"
        adv_click = _get_attr(trans_elem, "advClick", "1") in ("1", "true")
        adv_tm = _get_attr(trans_elem, "advTm")
        after = float(adv_tm) / 1000.0 if adv_tm else None

        return Transition(
            type=trans_type,
            speed=speed,
            click=adv_click,
            after=after,
            dir=dir_val,
            orient=orient_val,
            spokes=spokes_val,
            thruBlk=thru_blk,
        )

    def _extract_notes(self, slide_path: str, rel_map: dict[str, Any]) -> str:
        """Extract speaker notes text from associated notesSlide if present."""
        for rel in rel_map.values():
            if rel.type == REL_NOTES_SLIDE or rel.type.endswith("/notesSlide"):
                notes_path = _resolve_path(slide_path, rel.target)
                if self.package.has_part(notes_path):
                    try:
                        n_bytes = self.package.read_part(notes_path)
                        n_xml = ET.fromstring(n_bytes)
                        texts: list[str] = []
                        for sp in n_xml.iter():
                            if _local_tag(sp.tag) == "sp":
                                nv_sp_pr = _get_child(sp, "nvSpPr")
                                nv_pr = (
                                    _get_child(nv_sp_pr, "nvPr") if nv_sp_pr is not None else None
                                )
                                ph = _get_child(nv_pr, "ph") if nv_pr is not None else None
                                if ph is not None and _get_attr(ph, "type") == "body":
                                    tx_body = _get_child(sp, "txBody")
                                    if tx_body is not None:
                                        for p in _get_children(tx_body, "p"):
                                            p_text = "".join(
                                                t.text
                                                for t in p.iter()
                                                if _local_tag(t.tag) == "t" and t.text
                                            )
                                            texts.append(p_text)
                        if texts:
                            return "\n".join(texts)
                    except Exception:
                        pass
        return ""

    def _parse_comment_authors(
        self, pres_part: str, pres_rels: list[Any], pres: Presentation
    ) -> None:
        """Parse legacy and modern comment authors into presentation model."""
        author_targets: list[str] = []
        for rel in pres_rels:
            r_type = rel.type or ""
            if (
                r_type == REL_COMMENT_AUTHORS
                or r_type == REL_AUTHORS_MODERN
                or r_type.endswith("/commentAuthors")
                or r_type.endswith("/authors")
            ):
                author_targets.append(_resolve_path(pres_part, rel.target))

        # Check default paths if relationships omitted
        if not author_targets:
            if self.package.has_part("ppt/commentAuthors.xml"):
                author_targets.append("ppt/commentAuthors.xml")
            if self.package.has_part("ppt/authors.xml"):
                author_targets.append("ppt/authors.xml")

        for part_path in author_targets:
            if not self.package.has_part(part_path):
                continue
            try:
                xml_data = self.package.read_part(part_path)
                root = ET.fromstring(xml_data)
                for elem in root.iter():
                    tag = _local_tag(elem.tag)
                    if tag in ("cmAuthor", "author"):
                        aid = _get_attr(elem, "id", "") or ""
                        name = _get_attr(elem, "name", "") or "Author"
                        initials = _get_attr(elem, "initials", "") or ""
                        last_idx = int(_get_attr(elem, "lastIdx", "0") or "0")
                        clr_idx = int(_get_attr(elem, "clrIdx", "0") or "0")
                        user_id = _get_attr(elem, "userId", "") or ""
                        provider_id = _get_attr(elem, "providerId", "") or ""
                        author = CommentAuthor(
                            id=aid,
                            name=name,
                            initials=initials,
                            last_idx=last_idx,
                            color_idx=clr_idx,
                            user_id=user_id,
                            provider_id=provider_id,
                        )
                        if not any(a.id == aid for a in pres.comment_authors):
                            pres.comment_authors.append(author)
            except Exception:
                continue

    def _parse_slide_comments(
        self,
        slide_path: str,
        rel_map: dict[str, Any],
        slide: Slide,
        pres: Presentation,
    ) -> None:
        """Parse legacy and modern comments associated with this slide."""
        comment_parts: list[str] = []
        for rel in rel_map.values():
            r_type = rel.type or ""
            if (
                r_type == REL_COMMENTS
                or r_type == REL_COMMENTS_MODERN
                or r_type.endswith("/comments")
            ):
                target = _resolve_path(slide_path, rel.target)
                if self.package.has_part(target) and target not in comment_parts:
                    comment_parts.append(target)

        # Fallback check for standard naming
        if not comment_parts:
            stem = Path(slide_path).stem
            # e.g. slide1 -> comment1.xml
            idx_part = "".join(ch for ch in stem if ch.isdigit())
            candidate = f"ppt/comments/comment{idx_part}.xml" if idx_part else ""
            if candidate and self.package.has_part(candidate):
                comment_parts.append(candidate)

        for part_path in comment_parts:
            try:
                xml_data = self.package.read_part(part_path)
                root = ET.fromstring(xml_data)
                is_modern = (
                    "2018/8" in (root.tag or "")
                    or "2018/8" in (root.attrib.get("xmlns", "") or "")
                    or any("2018/8" in str(v) for v in root.attrib.values())
                )

                for elem in root.iter():
                    if _local_tag(elem.tag) != "cm":
                        continue

                    cm_id = _get_attr(elem, "id", "") or f"cm_{len(slide.comments) + 1}"
                    author_id = _get_attr(elem, "authorId", "0") or "0"
                    created = _get_attr(elem, "created", _get_attr(elem, "dt", "") or "") or ""
                    idx = int(_get_attr(elem, "idx", "1") or "1")
                    status = _get_attr(elem, "status", "active") or "active"

                    # Coordinates from <pos>
                    pos_elem = _get_child(elem, "pos")
                    if pos_elem is None:
                        for sub in elem:
                            if _local_tag(sub.tag) == "pos":
                                pos_elem = sub
                                break

                    x_val, y_val = 20.0, 20.0
                    if pos_elem is not None:
                        raw_x = _get_attr(pos_elem, "x", "254000")
                        raw_y = _get_attr(pos_elem, "y", "254000")
                        try:
                            fx = float(raw_x or 254000)
                            fy = float(raw_y or 254000)
                            x_val = round(fx / 12700.0, 2) if fx > 2000.0 else round(fx, 2)
                            y_val = round(fy / 12700.0, 2) if fy > 2000.0 else round(fy, 2)
                        except ValueError:
                            pass

                    # Extract text
                    text = ""
                    text_elem = _get_child(elem, "text")
                    if text_elem is not None and text_elem.text:
                        text = text_elem.text
                    else:
                        tx_body = _get_child(elem, "txBody")
                        if tx_body is not None:
                            body_parts = [
                                node.text
                                for node in tx_body.iter()
                                if _local_tag(node.tag) == "t" and node.text
                            ]
                            text = "".join(body_parts).strip()

                    # Shape anchor: search for <spMk id="...">
                    shape_id = None
                    for node in elem.iter():
                        if _local_tag(node.tag) == "spMk":
                            shape_id = _get_attr(node, "id")
                            if shape_id:
                                break

                    # Modern replies
                    replies: list[CommentReply] = []
                    reply_lst = _get_child(elem, "replyLst")
                    if reply_lst is not None:
                        for rep in _get_children(reply_lst, "reply"):
                            rep_id = _get_attr(rep, "id", "") or f"rep_{len(replies) + 1}"
                            rep_auth = _get_attr(rep, "authorId", author_id) or author_id
                            rep_created = _get_attr(rep, "created", created) or created
                            rep_text_parts: list[str] = [
                                t.text for t in rep.iter() if _local_tag(t.tag) == "t" and t.text
                            ]
                            replies.append(
                                CommentReply(
                                    id=rep_id,
                                    author_id=rep_auth,
                                    created=rep_created,
                                    text="".join(rep_text_parts).strip(),
                                )
                            )

                    # Ensure author exists in presentation
                    if not pres.find_author(author_id):
                        pres.get_or_create_author(name=f"Author {author_id}")

                    slide.comments.append(
                        Comment(
                            id=cm_id,
                            author_id=author_id,
                            text=text,
                            x=x_val,
                            y=y_val,
                            idx=idx,
                            created=created,
                            shape_id=shape_id,
                            status=status,
                            replies=replies,
                            is_modern=is_modern,
                        )
                    )
            except Exception:
                continue


def read_pptx(source: Path | str | bytes | io.BytesIO) -> Presentation:
    """Read presentation from file path or bytes."""
    if isinstance(source, (str, Path)):
        return PptxReader.open(source)
    if isinstance(source, io.BytesIO):
        source = source.getvalue()
    return PptxReader.from_bytes(source)
