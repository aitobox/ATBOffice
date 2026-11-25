"""ECMA-376 PresentationML reader for PPTX, PPSX, and POTX files."""

from __future__ import annotations

import copy
import io
from pathlib import Path
from typing import Any

from atboffice.modules.presentation.io import alternate_content as mce
from atboffice.modules.presentation.io import pptx_table_styles as tstyles
from atboffice.modules.presentation.io.pptx_common import (  # noqa: F401  re-exported
    _OFFICE_DIAGRAM_URN,
    EMUS_PER_PT,
    NS_A,
    NS_P,
    NS_P188,
    NS_R,
    REL_AUDIO,
    REL_AUTHORS_MODERN,
    REL_COMMENT_AUTHORS,
    REL_COMMENTS,
    REL_COMMENTS_MODERN,
    REL_IMAGE,
    REL_MEDIA,
    REL_NOTES_SLIDE,
    REL_OFFICE_DOCUMENT,
    REL_SLIDE,
    REL_SLIDE_LAYOUT,
    REL_SLIDE_MASTER,
    REL_THEME,
    REL_VIDEO,
    LayoutInfo,
    MasterInfo,
    PlaceholderTemplate,
    _diagram_color_style,
    _eval_guides,
    _get_attr,
    _get_child,
    _get_children,
    _guide_env,
    _local_tag,
    _mirror_in_group,
    _resolve_path,
    _resolve_theme_typefaces,
    _theme_typeface,
    clamp_alpha,
    emu_to_pt,
    safe_float,
    safe_int,
)
from atboffice.modules.presentation.io.pptx_shape_parser import PptxShapeParserMixin
from atboffice.modules.presentation.io.pptx_slide_extras import PptxSlideExtrasMixin
from atboffice.modules.presentation.io.pptx_text_parser import PptxTextParserMixin
from atboffice.modules.presentation.io.pptx_theme_parser import PptxThemeParserMixin
from atboffice.modules.presentation.models.designs import (
    ColorScheme,
    DesignTemplate,
)
from atboffice.modules.presentation.models.presentation import (
    LoadWarning,
    Presentation,
)
from atboffice.modules.presentation.models.shape import (
    Fill,
)
from atboffice.modules.presentation.models.slide import Slide
from atboffice.vfs import etree as ET
from atboffice.vfs.opc import SourcePackage


class PptxReader(
    PptxThemeParserMixin, PptxShapeParserMixin, PptxTextParserMixin, PptxSlideExtrasMixin
):
    """Parser for ECMA-376 PresentationML packages (.pptx, .ppsx, .potx)."""

    def __init__(self, package: SourcePackage) -> None:
        self.package = package
        self.rels_map: dict[str, dict[str, Any]] = {}
        self.themes: dict[str, ColorScheme] = {}
        self.theme_fmt: dict[str, dict[str, list[ET.Element]]] = {}
        self.media_map: dict[str, bytes] = {}
        self.default_text_style: dict[int, dict[str, Any]] = {}
        self._layouts: dict[str, LayoutInfo] = {}
        self._masters: dict[str, MasterInfo] = {}
        self._warnings: list[LoadWarning] = []
        self._theme_fonts: dict[str, tuple[str | None, str | None]] = {}
        self._table_styles = tstyles.TableStyleCatalog()
        self._table_style_cache: dict[tuple[str, int], dict[str, Any] | None] = {}

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
        self._warnings = []
        for corrupt_part in sorted(getattr(self.package, "_corrupt_parts", ())):
            self._warnings.append(
                LoadWarning(
                    scope="package",
                    location=corrupt_part,
                    message="ZIP member could not be decompressed",
                )
            )

        # 1. Locate presentation part via root relationships
        pres_part = self._locate_presentation_part()
        pres_bytes = self.package.read_part(pres_part)
        pres_xml = ET.fromstring(pres_bytes)

        # 2. Presentation Dimensions & Settings
        sz_elem = _get_child(pres_xml, "sldSz")
        width_pt = emu_to_pt(_get_attr(sz_elem, "cx"), default=960.0)
        height_pt = emu_to_pt(_get_attr(sz_elem, "cy"), default=540.0)

        fn_val = _get_attr(pres_xml, "firstSlideNum")
        first_num = safe_int(fn_val, 1) if fn_val else 1

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

        # 2.1 Presentation Default Text Style
        dft_elem = _get_child(pres_xml, "defaultTextStyle")
        self.default_text_style = self._parse_style_levels(dft_elem) if dft_elem is not None else {}
        pres.props["default_text_style"] = self.default_text_style

        # 3. Resolve presentation relationships
        pres_rels = self.package.get_relationships(pres_part)
        rel_by_id = {r.id: r for r in pres_rels}

        # 4. Parse Themes
        self._parse_themes(pres_part, pres_rels, pres)

        # 4.0 Table style catalog (ppt/tableStyles.xml)
        self._load_table_styles(pres_part, pres_rels)

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
                        try:
                            slide = self._parse_slide(slide_path, pres)
                        except Exception as exc:
                            self._warnings.append(
                                LoadWarning(
                                    scope="slide",
                                    location=slide_path,
                                    message=str(exc),
                                )
                            )
                            fallback_design = pres.get_design_for_slide(None)
                            slide = Slide(
                                id=f"degraded_{len(pres.slides) + 1}",
                                layout="blank",
                                design_id=fallback_design.id,
                            )
                        for sh in slide.shapes:
                            if sh.alt_content is not None:
                                sh.alt_content.fingerprint = mce.shape_fingerprint(sh)
                        num_id = sld_id_elem.get("id")
                        if num_id and num_id.isdigit():
                            slide.pres_slide_id = int(num_id)
                        slide._original_state = slide.to_dict()
                        pres.slides.append(slide)
                        slide_part_map[slide.id] = slide_path

        # If presentation had zero slides, create default slide
        if not pres.slides:
            pres.add_slide(layout="title")

        pres.load_warnings = list(self._warnings)
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

    def _parse_slide(self, slide_path: str, pres: Presentation) -> Slide:
        """Parse individual slide part XML."""
        slide_bytes = self.package.read_part(slide_path)
        slide_xml = ET.fromstring(slide_bytes)
        part_namespaces: dict[str, str] | None = None

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
                d_colors = self._get_theme_colors(m_info.theme_path) or next(
                    iter(self.themes.values()), ColorScheme()
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
                for sp_idx, child in enumerate(sp_tree):
                    try:
                        shape = self._parse_shape(
                            child,
                            slide_path,
                            rel_map,
                            timing_map=timing_map,
                            layout_info=layout_info,
                            slide_clr_map_ovr=slide_clr_map_ovr,
                        )
                        if shape:
                            if mce.is_alternate_content(child):
                                if part_namespaces is None:
                                    part_namespaces = mce.collect_namespaces(slide_bytes)
                                shape.alt_content = mce.capture(
                                    child,
                                    slide_path,
                                    rel_map,
                                    part_namespaces,
                                    self._read_media_part,
                                )
                            slide.shapes.append(shape)
                    except Exception as exc:
                        self._warnings.append(
                            LoadWarning(
                                scope="shape",
                                location=f"{slide_path}#{sp_idx}",
                                message=str(exc),
                            )
                        )

        # 1.0 Theme typefaces (+mj-lt / +mn-lt) still on runs become the master's fonts
        m_fonts = layout_info.master if layout_info else None
        _resolve_theme_typefaces(
            slide.shapes,
            m_fonts.major_font if m_fonts else None,
            m_fonts.minor_font if m_fonts else None,
        )

        # 1.1 Animation Timings
        try:
            slide.animations = self._parse_slide_animations(timing_elem, slide.shapes)
        except Exception as exc:
            self._warnings.append(
                LoadWarning(scope="animation", location=slide_path, message=str(exc))
            )

        # 2. Slide Transition
        trans_elem = _get_child(slide_xml, "transition")
        if trans_elem is not None:
            try:
                slide.transition = self._parse_transition(trans_elem)
            except Exception as exc:
                self._warnings.append(
                    LoadWarning(scope="transition", location=slide_path, message=str(exc))
                )

        # 3. Slide Speaker Notes
        try:
            notes_text = self._extract_notes(slide_path, rel_map)
            if notes_text:
                slide.notes = notes_text
        except Exception as exc:
            self._warnings.append(LoadWarning(scope="notes", location=slide_path, message=str(exc)))

        # 4. Slide Comments
        self._parse_slide_comments(slide_path, rel_map, slide, pres)

        return slide


def read_pptx(source: Path | str | bytes | io.BytesIO) -> Presentation:
    """Read presentation from file path or bytes."""
    if isinstance(source, (str, Path)):
        return PptxReader.open(source)
    if isinstance(source, io.BytesIO):
        source = source.getvalue()
    return PptxReader.from_bytes(source)
