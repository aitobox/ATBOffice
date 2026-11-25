"""PPTX reader: shapes, pictures, graphic frames, tables, groups, geometry, fills and lines."""

from __future__ import annotations

import copy
from typing import Any

from atboffice.modules.presentation.io import alternate_content as mce
from atboffice.modules.presentation.io import pptx_table_styles as tstyles
from atboffice.modules.presentation.io.pptx_common import (
    EMUS_PER_PT,
    REL_AUDIO,
    REL_MEDIA,
    REL_VIDEO,
    LayoutInfo,
    _diagram_color_style,
    _eval_guides,
    _get_attr,
    _get_child,
    _get_children,
    _guide_env,
    _local_tag,
    _mirror_in_group,
    _resolve_path,
    emu_to_pt,
    safe_float,
    safe_int,
)
from atboffice.modules.presentation.models.designs import (
    COLOR_SLOT_MAP,
    ColorScheme,
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
    LoadWarning,
)
from atboffice.modules.presentation.models.shape import (
    Fill,
    Line,
    PlaceholderInfo,
    Shadow,
    Shape,
)
from atboffice.modules.presentation.models.text import (
    TextBody,
)
from atboffice.vfs import etree as ET


class PptxShapeParserMixin:
    """Reads shapes, pictures, frames, tables, groups, geometry, fills, lines and shadows."""

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
            return self._parse_graphic_frame(
                elem,
                slide_path=slide_path,
                rel_map=rel_map,
                layout_info=layout_info,
                slide_clr_map_ovr=slide_clr_map_ovr,
            )
        elif tag == "grpSp":
            return self._parse_group_element(
                elem,
                slide_path=slide_path,
                rel_map=rel_map,
                layout_info=layout_info,
                slide_clr_map_ovr=slide_clr_map_ovr,
                group_fill=group_fill,
            )
        elif tag == "AlternateContent":
            return self._parse_alternate_content(
                elem,
                slide_path=slide_path,
                rel_map=rel_map,
                timing_map=timing_map,
                layout_info=layout_info,
                slide_clr_map_ovr=slide_clr_map_ovr,
                group_fill=group_fill,
            )
        return None

    def _parse_alternate_content(
        self,
        elem: ET.Element,
        slide_path: str,
        rel_map: dict[str, Any],
        timing_map: dict[str, PlaybackSettings] | None = None,
        layout_info: LayoutInfo | None = None,
        slide_clr_map_ovr: dict[str, str] | None = None,
        group_fill: Fill | None = None,
    ) -> Shape | None:
        """Parse the readable branch of an <mc:AlternateContent> in a shape tree."""
        branch = mce.select_branch(elem)
        if branch is None:
            return None
        shapes: list[Shape] = []
        for child in branch:
            sh = self._parse_shape(
                child,
                slide_path,
                rel_map,
                timing_map=timing_map,
                layout_info=layout_info,
                slide_clr_map_ovr=slide_clr_map_ovr,
                group_fill=group_fill,
            )
            if sh is not None:
                if _local_tag(child.tag) == "sp" and sh.type != "image":
                    self._apply_picture_fill(child, sh, slide_path, rel_map)
                shapes.append(sh)
        if not shapes:
            return None
        if len(shapes) == 1:
            return shapes[0]
        # Several objects in one branch: keep them together as a group (absolute coords).
        x0 = min(sh.x for sh in shapes)
        y0 = min(sh.y for sh in shapes)
        x1 = max(sh.x + sh.w for sh in shapes)
        y1 = max(sh.y + sh.h for sh in shapes)
        return Shape(
            id=f"{shapes[0].id}_ac",
            type="group",
            name="Group",
            x=x0,
            y=y0,
            w=x1 - x0,
            h=y1 - y0,
            kids=shapes,
        )

    def _apply_picture_fill(
        self, sp: ET.Element, shape: Shape, slide_path: str, rel_map: dict[str, Any]
    ) -> None:
        """Show an <p:sp> filled with a picture (typical mc:Fallback rendering) as an image."""
        sp_pr = _get_child(sp, "spPr")
        blip = _get_child(_get_child(sp_pr, "blipFill"), "blip")
        r_id = _get_attr(blip, "embed") if blip is not None else None
        rel = rel_map.get(r_id) if r_id else None
        if rel is None or rel.is_external:
            return
        media_path = _resolve_path(slide_path, rel.target)
        data = self._read_media_part(media_path)
        if not data:
            return
        shape.type = "image"
        shape.media = media_path
        shape.media_item = MediaItem(
            media_type="image",
            media_path=media_path,
            poster_path=media_path,
            poster_bytes=data,
        )
        if shape.text is not None and not shape.text.plain_text.strip():
            shape.text = None

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
                    "idx": safe_int(_get_attr(st_cxn, "idx", "0"), 0),
                }
            end_cxn = _get_child(c_nv_cxn_pr, "endCxn")
            if end_cxn is not None:
                cxn_end = {
                    "id": _get_attr(end_cxn, "id", ""),
                    "idx": safe_int(_get_attr(end_cxn, "idx", "0"), 0),
                }

        shape_id = _get_attr(c_nv_pr, "id", f"sp_{id(elem)}")
        shape_name = _get_attr(c_nv_pr, "name", "Shape")

        # Placeholder info
        placeholder: PlaceholderInfo | None = None
        ph_elem = _get_child(nv_pr, "ph") if nv_pr is not None else None
        if ph_elem is not None:
            ph_type = _get_attr(ph_elem, "type", "body") or "body"
            ph_idx = safe_int(_get_attr(ph_elem, "idx", "0"), 0)
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
        flip_h, flip_v = self._parse_flip(sp_pr)
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
        m_info = layout_info.master if layout_info else None
        if style_font == "+mj" and m_info and m_info.major_font:
            resolved_font = m_info.major_font
        elif style_font == "+mn" and m_info and m_info.minor_font:
            resolved_font = m_info.minor_font
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
        elif placeholder is None and text_body is not None:
            self._apply_shape_text_inheritance(text_body, layout_info, shape_elem=elem)

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
            geom
            in (
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
            flip_h=flip_h,
            flip_v=flip_v,
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
        flip_h, flip_v = self._parse_flip(sp_pr)

        # 1. Poster image embed relationship from <p:blipFill>/<a:blip>
        blip_fill = _get_child(elem, "blipFill")
        blip = _get_child(blip_fill, "blip") if blip_fill is not None else None
        crop = self._parse_src_rect(blip_fill)
        clr_change = None
        clr_from = _get_child(_get_child(blip, "clrChange"), "clrFrom")
        srgb = _get_child(clr_from, "srgbClr") if clr_from is not None else None
        if srgb is not None and _get_attr(srgb, "val"):
            clr_change = "#" + str(_get_attr(srgb, "val")).upper()
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
            flip_h=flip_h,
            flip_v=flip_v,
            fill=Fill.none(),
            line=Line.none(),
            media=media_key,
            media_item=media_item,
            crop=crop,
            clr_change=clr_change,
        )

    @staticmethod
    def _parse_src_rect(blip_fill: ET.Element | None) -> dict[str, float] | None:
        """Parse <a:srcRect l t r b> (1/1000 percent) into crop fractions.

        Values may be negative (the picture is padded rather than cropped). Returns
        None when no edge is cropped or the crop would leave nothing visible.
        """
        src_rect = _get_child(blip_fill, "srcRect") if blip_fill is not None else None
        if src_rect is None:
            return None
        crop: dict[str, float] = {}
        for key in ("l", "t", "r", "b"):
            try:
                crop[key] = float(_get_attr(src_rect, key, "0") or 0) / 100000.0
            except (TypeError, ValueError):
                crop[key] = 0.0
        if not any(crop.values()):
            return None
        if crop["l"] + crop["r"] >= 1.0 or crop["t"] + crop["b"] >= 1.0:
            return None
        return crop

    def _parse_graphic_frame(
        self,
        elem: ET.Element,
        slide_path: str = "",
        rel_map: dict[str, Any] | None = None,
        layout_info: LayoutInfo | None = None,
        slide_clr_map_ovr: dict[str, str] | None = None,
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
                    try:
                        from atboffice.modules.presentation.chart.io import parse_chart_xml

                        chart_bytes = self.package.read_part(chart_path)
                        scheme = self._resolve_theme_context(layout_info, slide_clr_map_ovr)[0]
                        accents = (
                            [getattr(scheme, f"accent{i}") for i in range(1, 7)]
                            if scheme is not None
                            else None
                        )
                        chart_obj = parse_chart_xml(
                            chart_bytes, theme_accents=accents, auto_title=True
                        )

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
                    except Exception as exc:
                        self._warnings.append(
                            LoadWarning(scope="chart", location=chart_path, message=str(exc))
                        )
                        chart_dict = None

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
            diag_colors: str | None = None
            diag_style: str | None = None
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
                            diag_colors, diag_style = _diagram_color_style(dm_xml)
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
                        except Exception as exc:
                            self._warnings.append(
                                LoadWarning(scope="smartart", location=dm_path, message=str(exc))
                            )

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
                        except Exception as exc:
                            self._warnings.append(
                                LoadWarning(scope="smartart", location=lo_path, message=str(exc))
                            )

            sa_items = [{"text": t} for t in diag_texts] if diag_texts else [{"text": "SmartArt"}]
            sa_obj: dict[str, Any] = {
                "layout": diag_layout,
                "items": sa_items,
            }
            if diag_colors:
                # Colour the diagram from this file's theme, as PowerPoint does.
                sa_obj["colors"] = diag_colors
                theme = self._get_theme_colors("")
                if theme is not None:
                    sa_obj["theme"] = {
                        slot: getattr(theme, slot)
                        for slot in (
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
                        )
                        if getattr(theme, slot, None)
                    }
            if diag_style:
                sa_obj["style"] = diag_style
            combined_txt = "\n".join(diag_texts) if diag_texts else "SmartArt"
            diagram = Shape(
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
            if diag_texts:
                # Lay out diagrams whose Office layout the engine draws, so they are painted
                # from their own shapes; any other layout keeps the placeholder.
                try:
                    from atboffice.modules.presentation.smartart.engine import relayout
                    from atboffice.modules.presentation.smartart.layouts import get_layout

                    if get_layout(diag_layout) is not None:
                        relayout(diagram)
                except Exception as exc:
                    self._warnings.append(
                        LoadWarning(scope="smartart", location=slide_path, message=str(exc))
                    )
                    diagram.kids = []
            return diagram

        # 2. Find table in graphicData
        tbl_dict: dict[str, Any] = {"cols": [], "rows": []}
        tbl_elem = _get_child(graphic_data, "tbl") if graphic_data is not None else None

        if tbl_elem is not None:
            self._parse_table(tbl_elem, tbl_dict, layout_info, slide_clr_map_ovr)

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

    def _parse_table(
        self,
        tbl_elem: ET.Element,
        tbl_dict: dict[str, Any],
        layout_info: LayoutInfo | None,
        slide_clr_map_ovr: dict[str, str] | None,
    ) -> None:
        """Parse <a:tbl> grid, cells, cell properties and the referenced table style."""
        master_info = layout_info.master if layout_info else None
        other_style = master_info.other_style if master_info else {}
        default_style = getattr(self, "default_text_style", {})
        theme_colors, _fmt, clr_map, clr_map_ovr = self._resolve_theme_context(
            layout_info, slide_clr_map_ovr
        )

        def cell_color(e: ET.Element) -> tuple[str | None, float]:
            return self._extract_color_detail(
                e,
                theme_colors=theme_colors,
                clr_map=clr_map,
                clr_map_ovr=clr_map_ovr,
                keep_scheme=True,
            )

        def style_color(e: ET.Element) -> tuple[str | None, float]:
            return self._extract_color_detail(
                e, theme_colors=theme_colors, clr_map=clr_map, clr_map_ovr=clr_map_ovr
            )

        def line_of(e: ET.Element) -> dict[str, Any]:
            ln = self._parse_line(
                e,
                theme_colors=theme_colors,
                clr_map=clr_map,
                clr_map_ovr=clr_map_ovr,
            )
            if ln.type == "none":
                return {"c": None, "w": 0.0, "dash": "solid"}
            return {"c": ln.color or "tx1", "w": float(ln.width or 0.75), "dash": ln.dash}

        tbl_pr = _get_child(tbl_elem, "tblPr")
        flags = {
            name: _get_attr(tbl_pr, name) in ("1", "true", "on")
            for name in ("firstRow", "lastRow", "firstCol", "lastCol", "bandRow", "bandCol")
        }
        style_id = tstyles.table_style_id(tbl_pr)
        if style_id:
            tbl_dict["style_id"] = style_id
        tbl_dict.update(flags)

        tbl_grid = _get_child(tbl_elem, "tblGrid")
        if tbl_grid is not None:
            for col_elem in _get_children(tbl_grid, "gridCol"):
                tbl_dict["cols"].append(emu_to_pt(_get_attr(col_elem, "w"), default=100.0))

        for tr_elem in _get_children(tbl_elem, "tr"):
            h_pt = emu_to_pt(_get_attr(tr_elem, "h"), default=30.0)
            row_cells: list[dict[str, Any]] = []
            for tc_elem in _get_children(tr_elem, "tc"):
                tx_body = _get_child(tc_elem, "txBody")
                cell_text = self._parse_text_body(tx_body) if tx_body is not None else TextBody()
                tc_pr = _get_child(tc_elem, "tcPr")
                if _get_attr(tc_pr, "anchor") in ("ctr", "b"):
                    cell_text.anchor = _get_attr(tc_pr, "anchor")
                fill, bd, own = tstyles.parse_cell_properties(tc_pr, cell_color, line_of)
                cell: dict[str, Any] = {
                    "tx": cell_text,
                    "text": cell_text.plain_text,
                    "fill": fill,
                    "bd": bd,
                    "own": own,
                }
                for key, attr in (("gs", "gridSpan"), ("rs", "rowSpan")):
                    span = safe_int(_get_attr(tc_elem, attr, "1"), 1)
                    if span > 1:
                        cell[key] = span
                for key, attr in (("hm", "hMerge"), ("vm", "vMerge")):
                    if _get_attr(tc_elem, attr) in ("1", "true", "on"):
                        cell[key] = True
                row_cells.append(cell)
            tbl_dict["rows"].append({"h": h_pt, "cells": row_cells})

        if style_id:
            cache_key = (style_id, id(theme_colors))
            if cache_key not in self._table_style_cache:

                def scheme_hex(token: str) -> str:
                    slot = COLOR_SLOT_MAP.get(token, token)
                    if theme_colors is not None and hasattr(theme_colors, slot):
                        return str(getattr(theme_colors, slot))
                    return resolve_color(token, fallback="#4472C4")

                def tint(hex_color: str, val: float) -> str:
                    return apply_color_mods(hex_color, [{"name": "tint", "val": val}])

                self._table_style_cache[cache_key] = tstyles.resolve_style_parts(
                    style_id,
                    self._table_styles,
                    style_color,
                    line_of,
                    scheme_hex,
                    tint,
                )
            parts = self._table_style_cache[cache_key]
            if parts:
                tstyles.apply_table_style(
                    tbl_dict["rows"], len(tbl_dict["cols"]), copy.deepcopy(parts), flags
                )

        # Table cells inherit remaining text properties from otherStyle and defaultTextStyle
        for row in tbl_dict["rows"]:
            for cell in row["cells"]:
                for p in cell["tx"].paragraphs:
                    lvl = p.level
                    def_s = default_style.get(lvl) or default_style.get(0) or {}
                    oth_s = other_style.get(lvl) or other_style.get(0) or {}
                    base_s = copy.deepcopy(def_s)
                    base_s.update(oth_s)
                    sz = base_s.get("sz", 18.0)
                    font = base_s.get("font") or (
                        master_info.minor_font if master_info else "Arial"
                    )
                    clr = base_s.get("color")
                    for r in p.runs:
                        if r.size is None:
                            r.size = sz
                        if r.font is None:
                            r.font = font
                        if r.color is None and clr:
                            r.color = clr

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
        grp_flip_h, grp_flip_v = self._parse_flip(grp_sp_pr)

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
            if tag in ("sp", "cxnSp", "pic", "graphicFrame", "grpSp", "AlternateContent"):
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
                    if grp_flip_h or grp_flip_v:
                        _mirror_in_group(kid_shape, x, y, w, h, grp_flip_h, grp_flip_v)
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
        rot = round(safe_float(rot_val, 0.0) / 60000.0, 2) if rot_val else 0.0

        return (x, y, w, h, rot)

    @staticmethod
    def _parse_flip(xfrm_parent: ET.Element | None) -> tuple[bool, bool]:
        """Return (flipH, flipV) from the <a:xfrm> child of spPr/grpSpPr."""
        xfrm = _get_child(xfrm_parent, "xfrm") if xfrm_parent is not None else None
        if xfrm is None:
            return False, False
        return (
            _get_attr(xfrm, "flipH", "0") in ("1", "true"),
            _get_attr(xfrm, "flipV", "0") in ("1", "true"),
        )

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
            ext_w = safe_float(_get_attr(ext, "cx", "0"), 0.0)
            ext_h = safe_float(_get_attr(ext, "cy", "0"), 0.0)
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

        # Path coordinates live in each path's own (w, h) space, which may be tiny
        # (e.g. w="100"): convert without emu_to_pt's 0.01 pt rounding, which would
        # collapse such paths. The renderer rescales (w, h) to the shape box.
        def to_pt(val: float) -> float:
            return val / EMUS_PER_PT

        paths: list[dict[str, Any]] = []
        for p_elem in _get_children(path_lst, "path"):
            pw_str = _get_attr(p_elem, "w")
            ph_str = _get_attr(p_elem, "h")
            pw = safe_float(pw_str, ext_w_emu) if pw_str else ext_w_emu
            ph = safe_float(ph_str, ext_h_emu) if ph_str else ext_h_emu
            pw_pt = to_pt(pw) if pw > 0 else 100.0
            ph_pt = to_pt(ph) if ph > 0 else 100.0

            cmds: list[list[Any]] = []
            for cmd_elem in p_elem:
                tag = _local_tag(cmd_elem.tag)
                pts: list[tuple[float, float]] = []
                for pt_elem in _get_children(cmd_elem, "pt"):
                    px = to_pt(resolve_val(_get_attr(pt_elem, "x")))
                    py = to_pt(resolve_val(_get_attr(pt_elem, "y")))
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
                    wr = to_pt(resolve_val(_get_attr(cmd_elem, "wR")))
                    hr = to_pt(resolve_val(_get_attr(cmd_elem, "hR")))
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
                    pos = safe_float(_get_attr(gs, "pos", "0"), 0.0) / 100000.0
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
                    pos = safe_float(_get_attr(gs, "pos", "0"), 0.0) / 100000.0
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

        ln_elem = (
            sp_pr
            if _local_tag(sp_pr.tag) in ("ln", "lnL", "lnR", "lnT", "lnB")
            else _get_child(sp_pr, "ln")
        )
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
                d_val = safe_float(_get_attr(ds, "d", "0"), 0.0) / 100000.0
                sp_val = safe_float(_get_attr(ds, "sp", "0"), 0.0) / 100000.0
                dashes.extend([d_val, sp_val])
            if dashes:
                res.custom_dash = dashes
                res.dash = "custom"

        for end_name, attr in (("headEnd", "head"), ("tailEnd", "tail")):
            end_elem = _get_child(ln_elem, end_name)
            end_type = _get_attr(end_elem, "type") if end_elem is not None else None
            if end_type and end_type != "none":
                end_dict = {"type": end_type}
                for key in ("w", "len"):
                    val = _get_attr(end_elem, key)
                    if val:
                        end_dict[key] = val
                setattr(res, attr, end_dict)

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
