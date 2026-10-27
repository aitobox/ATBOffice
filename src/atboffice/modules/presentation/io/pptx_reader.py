"""ECMA-376 PresentationML reader for PPTX, PPSX, and POTX files."""

from __future__ import annotations

import io
import posixpath
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from atboffice.modules.presentation.models.designs import (
    ColorScheme,
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
from atboffice.modules.presentation.models.slide import Slide, Transition
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


class PptxReader:
    """Parser for ECMA-376 PresentationML packages (.pptx, .ppsx, .potx)."""

    def __init__(self, package: SourcePackage) -> None:
        self.package = package
        self.rels_map: dict[str, dict[str, Any]] = {}
        self.themes: dict[str, ColorScheme] = {}
        self.media_map: dict[str, bytes] = {}

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
        return None

    def _parse_slide(self, slide_path: str, pres: Presentation) -> Slide:
        """Parse individual slide part XML."""
        slide_bytes = self.package.read_part(slide_path)
        slide_xml = ET.fromstring(slide_bytes)

        # Slide relationships (for images, notes, etc.)
        slide_rels = self.package.get_relationships(slide_path)
        rel_map = {r.id: r for r in slide_rels}

        slide_id = Path(slide_path).stem
        slide = Slide(id=slide_id, layout="text")

        # Parse media timing from <p:timing>
        timing_elem = _get_child(slide_xml, "timing")
        timing_map = self._parse_slide_media_timing(timing_elem)

        # 1. Slide Shapes
        c_sld = _get_child(slide_xml, "cSld")
        if c_sld is not None:
            sp_tree = _get_child(c_sld, "spTree")
            if sp_tree is not None:
                for child in sp_tree:
                    shape = self._parse_shape(
                        child, slide_path, rel_map, timing_map=timing_map
                    )
                    if shape:
                        slide.shapes.append(shape)

        # 2. Slide Transition
        trans_elem = _get_child(slide_xml, "transition")
        if trans_elem is not None:
            slide.transition = self._parse_transition(trans_elem)

        # 3. Slide Speaker Notes
        notes_text = self._extract_notes(slide_path, rel_map)
        if notes_text:
            slide.notes = notes_text

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
                hide_while_not_playing = (show_when_stopped == "0")

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
    ) -> Shape | None:
        """Parse shape, picture, table, or group element."""
        tag = _local_tag(elem.tag)

        if tag == "sp":
            return self._parse_sp_element(elem, slide_path=slide_path, rel_map=rel_map, timing_map=timing_map)
        elif tag == "pic":
            return self._parse_pic_element(elem, slide_path, rel_map, timing_map=timing_map)
        elif tag == "graphicFrame":
            return self._parse_graphic_frame(elem, slide_path=slide_path, rel_map=rel_map)
        elif tag == "grpSp":
            return self._parse_group_element(elem, slide_path, rel_map)
        return None

    def _parse_sp_element(
        self,
        elem: ET.Element,
        slide_path: str = "",
        rel_map: dict[str, Any] | None = None,
        timing_map: dict[str, PlaybackSettings] | None = None,
    ) -> Shape:
        """Parse standard <p:sp> shape or text box."""
        nv_sp_pr = _get_child(elem, "nvSpPr")
        c_nv_pr = _get_child(nv_sp_pr, "cNvPr") if nv_sp_pr is not None else None
        nv_pr = _get_child(nv_sp_pr, "nvPr") if nv_sp_pr is not None else None

        shape_id = _get_attr(c_nv_pr, "id", f"sp_{id(elem)}")
        shape_name = _get_attr(c_nv_pr, "name", "Shape")

        # Placeholder info
        placeholder: PlaceholderInfo | None = None
        ph_elem = _get_child(nv_pr, "ph") if nv_pr is not None else None
        if ph_elem is not None:
            ph_type = _get_attr(ph_elem, "type", "body") or "body"
            ph_idx = int(_get_attr(ph_elem, "idx", "0") or 0)
            placeholder = PlaceholderInfo(type=ph_type, idx=ph_idx)

        # Shape Properties (transform, geometry, fill, line)
        sp_pr = _get_child(elem, "spPr")
        x, y, w, h, rot = self._parse_transform(sp_pr)
        geom = self._parse_geometry(sp_pr)
        fill = self._parse_fill(sp_pr)
        line = self._parse_line(sp_pr)
        shadow = self._parse_shadow(sp_pr)

        # Text Body
        tx_body_elem = _get_child(elem, "txBody")
        text_body = self._parse_text_body(tx_body_elem) if tx_body_elem is not None else None

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
            if is_audio_extension(t_lower) or is_video_extension(t_lower) or p_rel.type in (REL_VIDEO, REL_AUDIO, REL_MEDIA):
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
                self.package.read_part(resolved_m)
                if self.package.has_part(resolved_m)
                else None
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
    ) -> Shape:
        """Parse <p:grpSp> group element recursively."""
        nv_grp_pr = _get_child(elem, "nvGrpSpPr")
        c_nv_pr = _get_child(nv_grp_pr, "cNvPr") if nv_grp_pr is not None else None
        grp_id = _get_attr(c_nv_pr, "id", f"grp_{id(elem)}")
        grp_name = _get_attr(c_nv_pr, "name", "Group")

        grp_sp_pr = _get_child(elem, "grpSpPr")
        x, y, w, h, rot = self._parse_transform(grp_sp_pr)

        kids: list[Shape] = []
        for child in elem:
            tag = _local_tag(child.tag)
            if tag in ("sp", "pic", "graphicFrame", "grpSp"):
                kid_shape = self._parse_shape(child, slide_path, rel_map)
                if kid_shape:
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

    def _parse_geometry(self, sp_pr: ET.Element | None) -> str:
        """Parse preset geometry name from <a:prstGeom>."""
        if sp_pr is None:
            return "rect"
        prst_geom = _get_child(sp_pr, "prstGeom")
        if prst_geom is not None:
            return _get_attr(prst_geom, "prst", "rect") or "rect"
        return "rect"

    def _parse_fill(self, sp_pr: ET.Element | None) -> Fill:
        """Parse shape fill style (solid, gradient, none)."""
        if sp_pr is None:
            return Fill.none()

        if _get_child(sp_pr, "noFill") is not None:
            return Fill.none()

        solid_fill = _get_child(sp_pr, "solidFill")
        if solid_fill is not None:
            clr = self._extract_color(solid_fill) or "#FFFFFF"
            # Alpha
            alpha = 1.0
            for child in solid_fill:
                alpha_elem = _get_child(child, "alpha")
                if alpha_elem is not None:
                    aval = _get_attr(alpha_elem, "val")
                    if aval:
                        alpha = float(aval) / 100000.0
            return Fill.solid(clr, alpha)

        grad_fill = _get_child(sp_pr, "gradFill")
        if grad_fill is not None:
            gs_lst = _get_child(grad_fill, "gsLst")
            stops: list[dict[str, Any]] = []
            if gs_lst is not None:
                for gs in _get_children(gs_lst, "gs"):
                    pos = float(_get_attr(gs, "pos", "0") or 0) / 100000.0
                    clr = self._extract_color(gs) or "#FFFFFF"
                    stops.append({"p": pos, "c": clr, "a": 1.0})
            return Fill.gradient(stops)

        return Fill.none()

    def _parse_line(self, sp_pr: ET.Element | None) -> Line:
        """Parse shape outline line style."""
        if sp_pr is None:
            return Line.none()

        ln_elem = _get_child(sp_pr, "ln")
        if ln_elem is None or _get_child(ln_elem, "noFill") is not None:
            return Line.none()

        w_emu = _get_attr(ln_elem, "w")
        width_pt = emu_to_pt(w_emu, default=0.75) if w_emu else 0.75

        clr = self._extract_color(_get_child(ln_elem, "solidFill")) or "tx1"

        prst_dash = _get_child(ln_elem, "prstDash")
        dash_style = _get_attr(prst_dash, "val", "solid") or "solid"

        return Line(
            type="solid",
            color=clr,
            width=width_pt,
            dash=dash_style,
        )

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

    def _parse_text_body(self, tx_body: ET.Element | None) -> TextBody:
        """Parse <p:txBody> into TextBody with paragraphs and runs."""
        if tx_body is None:
            return TextBody()

        body_pr = _get_child(tx_body, "bodyPr")
        insets = (7.2, 3.6, 7.2, 3.6)
        wrap = True
        anchor = "t"
        autofit = "none"

        if body_pr is not None:
            l_ins = emu_to_pt(_get_attr(body_pr, "lIns"), default=7.2)
            t_ins = emu_to_pt(_get_attr(body_pr, "tIns"), default=3.6)
            r_ins = emu_to_pt(_get_attr(body_pr, "rIns"), default=7.2)
            b_ins = emu_to_pt(_get_attr(body_pr, "bIns"), default=3.6)
            insets = (l_ins, t_ins, r_ins, b_ins)

            anchor_val = _get_attr(body_pr, "anchor")
            if anchor_val:
                anchor = anchor_val

            wrap_val = _get_attr(body_pr, "wrap")
            if wrap_val == "none":
                wrap = False

            if _get_child(body_pr, "normAutofit") is not None:
                autofit = "norm"
            elif _get_child(body_pr, "spAutoFit") is not None:
                autofit = "shape"

        paragraphs: list[Paragraph] = []
        for p_elem in _get_children(tx_body, "p"):
            p = self._parse_paragraph(p_elem)
            paragraphs.append(p)

        return TextBody(
            paragraphs=paragraphs,
            insets=insets,
            wrap=wrap,
            anchor=anchor,
            autofit=autofit,
        )

    def _parse_paragraph(self, p_elem: ET.Element) -> Paragraph:
        """Parse <a:p> paragraph element."""
        p_pr = _get_child(p_elem, "pPr")
        level = 0
        algn_val = None
        bullet = BulletInfo(type="none")

        if p_pr is not None:
            lvl_val = _get_attr(p_pr, "lvl")
            if lvl_val:
                try:
                    level = int(lvl_val)
                except ValueError:
                    level = 0

            algn_val = _get_attr(p_pr, "algn")

            bu_char = _get_child(p_pr, "buChar")
            if bu_char is not None:
                char_val = _get_attr(bu_char, "char", "•") or "•"
                bullet = BulletInfo(type="char", char=char_val)
            elif _get_child(p_pr, "buAutoNum") is not None:
                bullet = BulletInfo(type="auto", char="1.")

        runs: list[Run] = []
        for r_elem in _get_children(p_elem, "r"):
            r = self._parse_run(r_elem)
            runs.append(r)

        props: dict[str, Any] = {}
        if algn_val:
            props["algn"] = algn_val
        if bullet and bullet.type != "none":
            props["bu"] = bullet.to_dict()

        return Paragraph(
            level=level,
            props=props,
            runs=runs,
        )

    def _parse_run(self, r_elem: ET.Element) -> Run:
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

        return Run(
            text=text,
            font=font,
            size=size,
            color=color,
            bold=bold,
            italic=italic,
            underline=underline,
            strike=strike,
        )

    def _parse_transition(self, trans_elem: ET.Element) -> Transition:
        """Parse slide transition timing and type."""
        trans_type = "none"
        for child in trans_elem:
            tag = _local_tag(child.tag)
            if tag in ("fade", "wipe", "push", "split", "cover", "pull", "wheel", "zoom"):
                trans_type = tag
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
                        # Find body placeholder shape in notesSlide
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


def read_pptx(source: Path | str | bytes | io.BytesIO) -> Presentation:
    """Read presentation from file path or bytes."""
    if isinstance(source, (str, Path)):
        return PptxReader.open(source)
    if isinstance(source, io.BytesIO):
        source = source.getvalue()
    return PptxReader.from_bytes(source)
