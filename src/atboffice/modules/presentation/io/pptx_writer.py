"""ECMA-376 PresentationML writer for PPTX, PPSX, and POTX files."""

from __future__ import annotations

import io
import os
import posixpath
import xml.etree.ElementTree as ET
from pathlib import Path

from atboffice.modules.presentation.io.writer_slide import notes_slide_to_xml, slide_to_xml
from atboffice.modules.presentation.io.writer_templates import (
    build_app_properties_xml,
    build_core_properties_xml,
    build_notes_master_xml,
    build_pres_props_xml,
    build_slide_layout_xml,
    build_slide_master_xml,
    build_table_styles_xml,
    build_theme_xml,
    build_view_props_xml,
)
from atboffice.modules.presentation.io.xml_utils import (
    CT_APP,
    CT_CORE,
    CT_DIAGRAM_COLORS,
    CT_DIAGRAM_DATA,
    CT_DIAGRAM_LAYOUT,
    CT_DIAGRAM_STYLE,
    CT_NOTES_MASTER,
    CT_NOTES_SLIDE,
    CT_PRES_PROPS,
    CT_PRESENTATION,
    CT_SLIDE,
    CT_SLIDE_LAYOUT,
    CT_SLIDE_MASTER,
    CT_SLIDESHOW,
    CT_TABLE_STYLES,
    CT_TEMPLATE,
    CT_THEME,
    CT_VIEW_PROPS,
    NS_A,
    NS_P,
    NS_R,
    REL_DIAGRAM_COLORS,
    REL_DIAGRAM_DATA,
    REL_DIAGRAM_LAYOUT,
    REL_DIAGRAM_STYLE,
    REL_IMAGE,
    REL_MEDIA,
    REL_NOTES_MASTER,
    REL_NOTES_SLIDE,
    REL_OFFICE_DOCUMENT,
    REL_SLIDE,
    REL_SLIDE_LAYOUT,
    REL_SLIDE_MASTER,
    REL_THEME,
    REL_VIDEO,
    REL_AUDIO,
    XML_DECL,
    RelationshipBuilder,
    pt_to_emu,
)
from atboffice.modules.presentation.models.media_item import guess_media_content_type
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.smartart.io import (
    colors_xml,
    data_xml,
    layout_xml,
    style_xml,
)
from atboffice.vfs.opc import PackageWriter, SourcePackage
from atboffice.vfs.order import enforce_schema_order


class PptxWriter:
    """Serializer and OPC packager for PresentationML documents."""

    def __init__(self, presentation: Presentation, format: str = "pptx") -> None:
        self.pres = presentation
        self.format = format.lower().strip()
        if self.format not in ("pptx", "ppsx", "potx"):
            self.format = "pptx"

        self.source_pkg: SourcePackage | None = presentation.props.get("_source_package")
        self.pkg_writer = PackageWriter(source_package=self.source_pkg)
        self.primary_design = (
            list(presentation.designs.values())[0]
            if presentation.designs
            else presentation.get_design_for_slide(None)
        )
        self._media_counter = 1
        self._chart_counter = 1

    def _resolve_main_content_type(self) -> str:
        if self.format == "ppsx":
            return CT_SLIDESHOW
        if self.format == "potx":
            return CT_TEMPLATE
        return CT_PRESENTATION

    def write(self) -> bytes:
        """Serialize presentation to byte buffer."""
        if self.source_pkg:
            self._write_lossless_roundtrip()
        else:
            self._write_from_scratch()

        return self.pkg_writer.to_bytes()

    def write_to(self, target: Path | str) -> None:
        """Write presentation bytes directly to disk."""
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.write()
        path.write_bytes(data)

    def _write_from_scratch(self) -> None:
        """Synthesize a complete valid PresentationML container from scratch."""
        main_ct = self._resolve_main_content_type()
        pres_part = "ppt/presentation.xml"
        self.pkg_writer.replace_part(pres_part, b"", content_type=main_ct)

        # 1. Package root rels (_rels/.rels)
        root_rels = RelationshipBuilder()
        root_rels.add(REL_OFFICE_DOCUMENT, pres_part)
        self.pkg_writer.replace_part(
            "_rels/.rels",
            root_rels.to_xml(),
            content_type="application/vnd.openxmlformats-package.relationships+xml",
        )

        # 2. Themes (ppt/theme/theme1.xml)
        theme_part = "ppt/theme/theme1.xml"
        theme_xml = build_theme_xml(self.primary_design, name=self.primary_design.name)
        self.pkg_writer.replace_part(theme_part, theme_xml.encode("utf-8"), content_type=CT_THEME)

        # 3. Slide Layouts (ppt/slideLayouts/slideLayout{1..3}.xml)
        layout_parts = [
            ("ppt/slideLayouts/slideLayout1.xml", "title"),
            ("ppt/slideLayouts/slideLayout2.xml", "content"),
            ("ppt/slideLayouts/slideLayout3.xml", "blank"),
        ]
        for l_part, l_type in layout_parts:
            l_xml = build_slide_layout_xml(l_type)
            self.pkg_writer.replace_part(
                l_part, l_xml.encode("utf-8"), content_type=CT_SLIDE_LAYOUT
            )
            # Layout rel to master
            l_rels = RelationshipBuilder()
            l_rels.add(REL_SLIDE_MASTER, "../slideMasters/slideMaster1.xml")
            l_rels_path = f"ppt/slideLayouts/_rels/{posixpath.basename(l_part)}.rels"
            self.pkg_writer.replace_part(
                l_rels_path,
                l_rels.to_xml(),
                content_type="application/vnd.openxmlformats-package.relationships+xml",
            )

        # 4. Slide Master (ppt/slideMasters/slideMaster1.xml)
        master_part = "ppt/slideMasters/slideMaster1.xml"
        master_rels = RelationshipBuilder()
        layout_entries: list[tuple[int, str]] = []
        for idx, (l_part, _) in enumerate(layout_parts, start=1):
            r_id = master_rels.add(
                REL_SLIDE_LAYOUT, f"../slideLayouts/{posixpath.basename(l_part)}"
            )
            layout_entries.append((2147483648 + idx, r_id))
        master_rels.add(REL_THEME, "../theme/theme1.xml")

        master_xml = build_slide_master_xml(self.primary_design, layout_entries)
        self.pkg_writer.replace_part(
            master_part, master_xml.encode("utf-8"), content_type=CT_SLIDE_MASTER
        )
        master_rels_path = "ppt/slideMasters/_rels/slideMaster1.xml.rels"
        self.pkg_writer.replace_part(
            master_rels_path,
            master_rels.to_xml(),
            content_type="application/vnd.openxmlformats-package.relationships+xml",
        )

        # 5. Slides serialization & relationships
        pres_rels = RelationshipBuilder()
        pres_rels.add(REL_SLIDE_MASTER, "slideMasters/slideMaster1.xml")

        slide_id_entries: list[tuple[int, str]] = []
        has_any_notes = any(bool(s.notes and s.notes.strip()) for s in self.pres.slides)
        if has_any_notes:
            notes_master_part = "ppt/notesMasters/notesMaster1.xml"
            nm_xml = build_notes_master_xml()
            self.pkg_writer.replace_part(
                notes_master_part, nm_xml.encode("utf-8"), content_type=CT_NOTES_MASTER
            )

        for i, slide in enumerate(self.pres.slides, start=1):
            slide_part = f"ppt/slides/slide{i}.xml"
            s_rels = RelationshipBuilder()
            # Default rel to slideLayout1 or slideLayout2
            layout_target = (
                "../slideLayouts/slideLayout1.xml"
                if slide.layout == "title"
                else "../slideLayouts/slideLayout2.xml"
            )
            s_rels.add(REL_SLIDE_LAYOUT, layout_target)

            # Media resolver for embedded pictures, multimedia and charts
            def make_media_resolver(slide_rels: RelationshipBuilder):
                media_cache: dict[str, dict[str, str]] = {}

                def media_resolver(media_key: str) -> str:
                    if media_key.startswith(("media_poster:", "media_p14:", "media_file:")):
                        prefix, shape_id = media_key.split(":", 1)
                        if shape_id not in media_cache:
                            target_shape = next((sh for sh in slide.shapes if sh.id == shape_id), None)
                            m_item = target_shape.media_item if target_shape else None
                            media_map = self.pres.props.get("_media_map", {})

                            # 1. Media binary Part
                            raw_media = m_item.media_bytes if m_item else None
                            if raw_media is None and m_item and m_item.media_path:
                                raw_media = media_map.get(m_item.media_path)
                                if raw_media is None and os.path.exists(m_item.media_path):
                                    try:
                                        raw_media = Path(m_item.media_path).read_bytes()
                                    except OSError:
                                        pass
                            if raw_media is None:
                                raw_media = b""

                            m_ext = m_item.extension if m_item else "mp4"
                            m_filename = f"media{self._media_counter}.{m_ext}"
                            self._media_counter += 1
                            m_part = f"ppt/media/{m_filename}"
                            ct = (m_item.content_type if m_item else None) or guess_media_content_type(m_filename)
                            self.pkg_writer.replace_part(m_part, raw_media, content_type=ct)

                            p14_rid = slide_rels.add(REL_MEDIA, f"../media/{m_filename}")
                            if m_item and m_item.is_audio:
                                file_rid = slide_rels.add(REL_AUDIO, f"../media/{m_filename}")
                            else:
                                file_rid = slide_rels.add(REL_VIDEO, f"../media/{m_filename}")

                            # 2. Poster image Part
                            raw_poster = m_item.poster_bytes if m_item else None
                            if raw_poster is None and m_item and m_item.poster_path:
                                raw_poster = media_map.get(m_item.poster_path)
                            if raw_poster is None and target_shape and target_shape.media:
                                raw_poster = media_map.get(target_shape.media)
                                if raw_poster is None and os.path.exists(target_shape.media):
                                    try:
                                        raw_poster = Path(target_shape.media).read_bytes()
                                    except OSError:
                                        pass
                            if raw_poster is None:
                                # Default minimal 1x1 transparent PNG
                                raw_poster = (
                                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
                                    b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
                                    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
                                )

                            p_ext = "png"
                            if m_item and m_item.poster_path and "." in m_item.poster_path:
                                cand = m_item.poster_path.rsplit(".", 1)[-1].lower()
                                if cand in ("png", "jpg", "jpeg", "gif", "bmp", "webp"):
                                    p_ext = cand
                            elif target_shape and target_shape.media and "." in target_shape.media:
                                cand = target_shape.media.rsplit(".", 1)[-1].lower()
                                if cand in ("png", "jpg", "jpeg", "gif", "bmp", "webp"):
                                    p_ext = cand

                            p_filename = f"image{self._media_counter}.{p_ext}"
                            self._media_counter += 1
                            p_part = f"ppt/media/{p_filename}"
                            self.pkg_writer.replace_part(p_part, raw_poster, content_type=f"image/{p_ext}")
                            poster_rid = slide_rels.add(REL_IMAGE, f"../media/{p_filename}")

                            media_cache[shape_id] = {
                                "poster": poster_rid,
                                "p14": p14_rid,
                                "file": file_rid,
                            }

                        info = media_cache[shape_id]
                        if prefix == "media_poster":
                            return info["poster"]
                        elif prefix == "media_p14":
                            return info["p14"]
                        else:
                            return info["file"]

                    if media_key.startswith("chart:"):
                        chart_id = media_key.split(":", 1)[1]
                        c_idx = self._chart_counter
                        self._chart_counter += 1
                        chart_shape = next((sh for sh in slide.shapes if sh.id == chart_id), None)
                        c_data = chart_shape.chart if chart_shape and chart_shape.chart else {}
                        from atboffice.modules.presentation.chart.io import (
                            chart_to_xml,
                            create_embedded_workbook,
                        )
                        from atboffice.modules.presentation.chart.model import ChartData

                        c_xml = chart_to_xml(c_data).encode("utf-8")
                        chart_part = f"ppt/charts/chart{c_idx}.xml"
                        self.pkg_writer.replace_part(
                            chart_part,
                            c_xml,
                            content_type="application/vnd.openxmlformats-officedocument.drawingml.chart+xml",
                        )

                        chart_data_obj = (
                            c_data
                            if isinstance(c_data, ChartData)
                            else ChartData.from_dict(c_data)
                        )
                        wb_bytes = (
                            chart_data_obj.embedded_workbook
                            if chart_data_obj.embedded_workbook
                            else create_embedded_workbook(chart_data_obj)
                        )
                        if wb_bytes:
                            wb_part = f"ppt/embeddings/Microsoft_Excel_Worksheet{c_idx}.xlsx"
                            self.pkg_writer.replace_part(
                                wb_part,
                                wb_bytes,
                                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            )
                            c_rels = RelationshipBuilder()
                            c_rels.add(
                                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/package",
                                f"../embeddings/Microsoft_Excel_Worksheet{c_idx}.xlsx",
                            )
                            self.pkg_writer.replace_part(
                                f"ppt/charts/_rels/chart{c_idx}.xml.rels",
                                c_rels.to_xml(),
                                content_type="application/vnd.openxmlformats-package.relationships+xml",
                            )

                        return slide_rels.add(
                            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart",
                            f"../charts/chart{c_idx}.xml",
                        )

                    media_map = self.pres.props.get("_media_map", {})
                    raw_bytes = media_map.get(media_key)
                    if raw_bytes is None and os.path.exists(media_key):
                        try:
                            raw_bytes = Path(media_key).read_bytes()
                        except OSError:
                            pass
                    if raw_bytes is None:
                        raw_bytes = b""

                    ext = "png"
                    if "." in media_key:
                        ext = media_key.rsplit(".", 1)[-1].lower()

                    m_filename = f"image{self._media_counter}.{ext}"
                    self._media_counter += 1
                    m_part = f"ppt/media/{m_filename}"
                    self.pkg_writer.replace_part(m_part, raw_bytes, content_type=f"image/{ext}")
                    return slide_rels.add(REL_IMAGE, f"../media/{m_filename}")

                return media_resolver

            resolver = make_media_resolver(s_rels)
            s_xml = slide_to_xml(slide, design=self.primary_design, media_resolver=resolver)
            self.pkg_writer.replace_part(slide_part, s_xml.encode("utf-8"), content_type=CT_SLIDE)

            # SmartArt diagram parts
            diag_idx = 0
            for sh in slide.shapes:
                if sh.is_diagram and sh.sa:
                    diag_idx += 1
                    diag_tag = f"diag_s{i}_{diag_idx}"
                    d_xml = data_xml(sh.sa, key=diag_tag).encode("utf-8")
                    l_xml = layout_xml(sh.sa.get("layout", "process")).encode("utf-8")
                    c_xml = colors_xml(sh.sa.get("colors", "ocean")).encode("utf-8")
                    q_xml = style_xml(sh.sa.get("style", "moderate")).encode("utf-8")

                    d_part = f"ppt/diagrams/data_{diag_tag}.xml"
                    l_part = f"ppt/diagrams/layout_{diag_tag}.xml"
                    c_part = f"ppt/diagrams/colors_{diag_tag}.xml"
                    q_part = f"ppt/diagrams/quickStyle_{diag_tag}.xml"

                    self.pkg_writer.replace_part(d_part, d_xml, content_type=CT_DIAGRAM_DATA)
                    self.pkg_writer.replace_part(l_part, l_xml, content_type=CT_DIAGRAM_LAYOUT)
                    self.pkg_writer.replace_part(c_part, c_xml, content_type=CT_DIAGRAM_COLORS)
                    self.pkg_writer.replace_part(q_part, q_xml, content_type=CT_DIAGRAM_STYLE)

                    s_rels.add(REL_DIAGRAM_DATA, f"../diagrams/data_{diag_tag}.xml")
                    s_rels.add(REL_DIAGRAM_LAYOUT, f"../diagrams/layout_{diag_tag}.xml")
                    s_rels.add(REL_DIAGRAM_COLORS, f"../diagrams/colors_{diag_tag}.xml")
                    s_rels.add(REL_DIAGRAM_STYLE, f"../diagrams/quickStyle_{diag_tag}.xml")

            # Speaker Notes
            if slide.notes and slide.notes.strip():
                notes_part = f"ppt/notesSlides/notesSlide{i}.xml"
                n_xml = notes_slide_to_xml(slide.notes)
                self.pkg_writer.replace_part(
                    notes_part, n_xml.encode("utf-8"), content_type=CT_NOTES_SLIDE
                )

                n_rels = RelationshipBuilder()
                n_rels.add(REL_NOTES_MASTER, "../notesMasters/notesMaster1.xml")
                n_rels.add(REL_SLIDE, f"../slides/slide{i}.xml")
                n_rels_path = f"ppt/notesSlides/_rels/notesSlide{i}.xml.rels"
                self.pkg_writer.replace_part(
                    n_rels_path,
                    n_rels.to_xml(),
                    content_type="application/vnd.openxmlformats-package.relationships+xml",
                )

                s_rels.add(REL_NOTES_SLIDE, f"../notesSlides/notesSlide{i}.xml")

            s_rels_path = f"ppt/slides/_rels/slide{i}.xml.rels"
            self.pkg_writer.replace_part(
                s_rels_path,
                s_rels.to_xml(),
                content_type="application/vnd.openxmlformats-package.relationships+xml",
            )

            r_id = pres_rels.add(REL_SLIDE, f"slides/slide{i}.xml")
            slide_id_entries.append((255 + i, r_id))

        # Auxiliary Parts
        self.pkg_writer.replace_part(
            "ppt/presProps.xml", build_pres_props_xml().encode("utf-8"), content_type=CT_PRES_PROPS
        )
        self.pkg_writer.replace_part(
            "ppt/viewProps.xml", build_view_props_xml().encode("utf-8"), content_type=CT_VIEW_PROPS
        )
        self.pkg_writer.replace_part(
            "ppt/tableStyles.xml",
            build_table_styles_xml().encode("utf-8"),
            content_type=CT_TABLE_STYLES,
        )
        self.pkg_writer.replace_part(
            "docProps/core.xml",
            build_core_properties_xml(self.pres.title, self.pres.props.get("author", "")).encode(
                "utf-8"
            ),
            content_type=CT_CORE,
        )
        self.pkg_writer.replace_part(
            "docProps/app.xml",
            build_app_properties_xml(len(self.pres.slides)).encode("utf-8"),
            content_type=CT_APP,
        )

        # 6. ppt/presentation.xml and its rels
        pres_rels_path = "ppt/_rels/presentation.xml.rels"
        self.pkg_writer.replace_part(
            pres_rels_path,
            pres_rels.to_xml(),
            content_type="application/vnd.openxmlformats-package.relationships+xml",
        )

        w_emu = pt_to_emu(self.pres.w, default=12192000)
        h_emu = pt_to_emu(self.pres.h, default=6858000)
        sld_id_items = "".join(
            f'<p:sldId id="{sid}" r:id="{rid}"/>' for sid, rid in slide_id_entries
        )

        pres_xml_str = (
            f'<p:presentation xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
            '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
            f"<p:sldIdLst>{sld_id_items}</p:sldIdLst>"
            f'<p:sldSz cx="{w_emu}" cy="{h_emu}"/>'
            '<p:notesSz cx="6858000" cy="9144000"/>'
            '<p:defaultTextStyle><a:defPPr><a:defRPr lang="en-US"/></a:defPPr></p:defaultTextStyle>'
            "</p:presentation>"
        )
        elem = ET.fromstring(pres_xml_str)
        enforce_schema_order(elem, "presentation")
        final_pres_xml = f"{XML_DECL}{ET.tostring(elem, encoding='unicode')}"
        self.pkg_writer.replace_part(
            pres_part, final_pres_xml.encode("utf-8"), content_type=main_ct
        )

    def _write_lossless_roundtrip(self) -> None:
        """Preserve unmodified slides, masters, themes, and media byte-for-byte."""
        assert self.source_pkg is not None
        main_ct = self._resolve_main_content_type()
        slide_part_map: dict[str, str] = self.pres.props.get("_slide_part_map", {})

        # Track existing slide parts
        existing_parts_set = set(slide_part_map.values())
        live_slides_parts: list[tuple[Slide, str]] = []

        max_slide_num = 0
        for p in self.source_pkg.parts():
            if p.startswith("ppt/slides/slide") and p.endswith(".xml"):
                num_str = p[len("ppt/slides/slide") : -4]
                if num_str.isdigit():
                    max_slide_num = max(max_slide_num, int(num_str))

        # Check each slide in presentation
        for slide in self.pres.slides:
            part_name = slide_part_map.get(slide.id)
            if not part_name:
                max_slide_num += 1
                part_name = f"ppt/slides/slide{max_slide_num}.xml"
                slide_part_map[slide.id] = part_name

            live_slides_parts.append((slide, part_name))

            # Check if slide is unmodified
            orig_state = getattr(slide, "_original_state", None)
            is_dirty = getattr(slide, "is_dirty", False)

            if (
                not is_dirty
                and orig_state is not None
                and slide.to_dict() == orig_state
                and self.source_pkg.has_part(part_name)
            ):
                # Unmodified: Keep byte-for-byte!
                continue

            # Modified or newly added slide: Re-serialize
            s_rels_path = f"ppt/slides/_rels/{posixpath.basename(part_name)}.rels"
            s_rels = RelationshipBuilder()
            if self.source_pkg.has_part(s_rels_path):
                # Copy existing relationships
                for r in self.source_pkg.get_relationships(part_name):
                    s_rels.add(r.type, r.target, target_mode=r.target_mode, rel_id=r.id)
            else:
                s_rels.add(REL_SLIDE_LAYOUT, "../slideLayouts/slideLayout1.xml")

            def make_media_resolver(slide_rels: RelationshipBuilder):
                def media_resolver(media_key: str) -> str:
                    media_map = self.pres.props.get("_media_map", {})
                    raw_bytes = media_map.get(media_key)
                    if raw_bytes is None and os.path.exists(media_key):
                        try:
                            raw_bytes = Path(media_key).read_bytes()
                        except OSError:
                            pass
                    if raw_bytes is None:
                        raw_bytes = b""

                    ext = "png"
                    if "." in media_key:
                        ext = media_key.rsplit(".", 1)[-1].lower()

                    m_filename = f"image{self._media_counter}.{ext}"
                    self._media_counter += 1
                    m_part = f"ppt/media/{m_filename}"
                    self.pkg_writer.replace_part(m_part, raw_bytes, content_type=f"image/{ext}")
                    return slide_rels.add(REL_IMAGE, f"../media/{m_filename}")

                return media_resolver

            resolver = make_media_resolver(s_rels)
            s_xml = slide_to_xml(slide, design=self.primary_design, media_resolver=resolver)
            self.pkg_writer.replace_part(part_name, s_xml.encode("utf-8"), content_type=CT_SLIDE)
            self.pkg_writer.replace_part(
                s_rels_path,
                s_rels.to_xml(),
                content_type="application/vnd.openxmlformats-package.relationships+xml",
            )

        # Delete any removed slides
        live_parts_set = {p for _, p in live_slides_parts}
        for dead_part in existing_parts_set - live_parts_set:
            self.pkg_writer.delete_part(dead_part)
            dead_rels = f"ppt/slides/_rels/{posixpath.basename(dead_part)}.rels"
            self.pkg_writer.delete_part(dead_rels)

        # Update ppt/presentation.xml and its rels
        pres_part = "ppt/presentation.xml"
        pres_rels_path = "ppt/_rels/presentation.xml.rels"

        pres_rels = RelationshipBuilder()
        rel_map_by_target: dict[str, str] = {}
        for r in self.source_pkg.get_relationships(pres_part):
            target_norm = posixpath.normpath(posixpath.join("ppt", r.target)).replace("\\", "/")
            if target_norm.startswith("ppt/"):
                target_rel = target_norm[4:]
            else:
                target_rel = r.target
            rel_map_by_target[target_rel] = r.id
            pres_rels.add(r.type, r.target, target_mode=r.target_mode, rel_id=r.id)

        slide_id_entries: list[tuple[int, str]] = []
        for i, (_, p_name) in enumerate(live_slides_parts, start=1):
            p_rel = f"slides/{posixpath.basename(p_name)}"
            rid = rel_map_by_target.get(p_rel)
            if not rid:
                rid = pres_rels.add(REL_SLIDE, p_rel)
                rel_map_by_target[p_rel] = rid
            slide_id_entries.append((255 + i, rid))

        self.pkg_writer.replace_part(
            pres_rels_path,
            pres_rels.to_xml(),
            content_type="application/vnd.openxmlformats-package.relationships+xml",
        )

        # Update ppt/presentation.xml content
        pres_bytes = self.source_pkg.read_part(pres_part)
        pres_elem = ET.fromstring(pres_bytes)

        # Update dimensions
        sz_elem = pres_elem.find(f"{{{NS_P}}}sldSz")
        if sz_elem is None:
            sz_elem = pres_elem.find("sldSz")
        if sz_elem is not None:
            sz_elem.set("cx", str(pt_to_emu(self.pres.w)))
            sz_elem.set("cy", str(pt_to_emu(self.pres.h)))

        # Update slide ID list
        sld_id_lst = pres_elem.find(f"{{{NS_P}}}sldIdLst")
        if sld_id_lst is None:
            sld_id_lst = pres_elem.find("sldIdLst")
        if sld_id_lst is None:
            sld_id_lst = ET.SubElement(pres_elem, f"{{{NS_P}}}sldIdLst")
        else:
            sld_id_lst.clear()

        for sid, rid in slide_id_entries:
            ET.SubElement(sld_id_lst, f"{{{NS_P}}}sldId", id=str(sid), **{f"{{{NS_R}}}id": rid})

        enforce_schema_order(pres_elem, "presentation")
        final_pres_xml = f"{XML_DECL}{ET.tostring(pres_elem, encoding='unicode')}"
        self.pkg_writer.replace_part(
            pres_part, final_pres_xml.encode("utf-8"), content_type=main_ct
        )


def write_pptx(
    presentation: Presentation,
    target: Path | str | io.BytesIO | None = None,
    format: str = "pptx",
) -> bytes:
    """Serialize presentation to PPTX/PPSX/POTX package bytes or write to target."""
    writer = PptxWriter(presentation, format=format)
    data = writer.write()
    if isinstance(target, (str, Path)):
        Path(target).write_bytes(data)
    elif isinstance(target, io.BytesIO):
        target.write(data)
        target.seek(0)
    return data
