"""PPTX reader: text bodies, paragraphs, runs, masters, layouts and placeholder inheritance."""

from __future__ import annotations

import copy
import math
from typing import Any

from atboffice.modules.presentation.io import alternate_content as mce
from atboffice.modules.presentation.io.pptx_common import (
    NS_A,
    REL_SLIDE_MASTER,
    REL_THEME,
    LayoutInfo,
    MasterInfo,
    PlaceholderTemplate,
    _get_attr,
    _get_child,
    _get_children,
    _local_tag,
    _resolve_path,
    emu_to_pt,
    safe_float,
    safe_int,
)
from atboffice.modules.presentation.models.shape import (
    Fill,
    PlaceholderInfo,
    Shape,
)
from atboffice.modules.presentation.models.text import (
    BulletInfo,
    Paragraph,
    Run,
    TextBody,
)
from atboffice.modules.writer.models.omml import parse_omml
from atboffice.vfs import etree as ET


class PptxTextParserMixin:
    """Reads text, masters and layouts, and applies placeholder text inheritance."""

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
            ph_idx = safe_int(_get_attr(ph_elem, "idx", "0"), 0)
            sp_id = _get_attr(c_nv_pr, "id", "") or ""

            sp_pr = _get_child(sp, "spPr")
            xfrm = None
            if sp_pr is not None and _get_child(sp_pr, "xfrm") is not None:
                xfrm = self._parse_transform(sp_pr)
            fill = self._parse_fill(sp_pr) if sp_pr is not None else None
            line = self._parse_line(sp_pr) if sp_pr is not None else None
            tx_body = _get_child(sp, "txBody")
            text_body = self._parse_text_body(tx_body) if tx_body is not None else None
            lst_el = _get_child(tx_body, "lstStyle") if tx_body is not None else None

            placeholders.append(
                PlaceholderTemplate(
                    type=ph_type,
                    idx=ph_idx,
                    shape_id=sp_id,
                    xfrm=xfrm,
                    fill=fill,
                    line=line,
                    text_body=text_body,
                    custom_prompt=_get_attr(ph_elem, "hasCustomPrompt") in ("1", "true"),
                    lst_levels=self._parse_style_levels(lst_el) if lst_el is not None else {},
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
                    if ltag in ("sp", "pic", "graphicFrame", "grpSp", "AlternateContent"):
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
                    if ltag in ("sp", "pic", "graphicFrame", "grpSp", "AlternateContent"):
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

        if text_body.cols <= 1:
            if lp_tb and lp_tb.cols > 1:
                text_body.cols = lp_tb.cols
                text_body.col_gap = lp_tb.col_gap
                text_body.rtl_col = lp_tb.rtl_col
            elif mp_tb and mp_tb.cols > 1:
                text_body.cols = mp_tb.cols
                text_body.col_gap = mp_tb.col_gap
                text_body.rtl_col = mp_tb.rtl_col

        if text_body.wrap:
            if lp_tb and not lp_tb.wrap:
                text_body.wrap = False
            elif mp_tb and not mp_tb.wrap:
                text_body.wrap = False

        default_style = getattr(self, "default_text_style", {})

        is_empty = text_body.is_empty()
        custom_prompt = ""
        if is_empty and lp is not None and lp.custom_prompt and lp.text_body is not None:
            custom_prompt = lp.text_body.plain_text.strip()

        for p in text_body.paragraphs:
            lvl = p.level
            lp_p = next((x for x in lp_paras if x.level == lvl), lp_paras[0] if lp_paras else None)
            mp_p = next((x for x in mp_paras if x.level == lvl), mp_paras[0] if mp_paras else None)
            # Paragraph formatting comes from the layout's and master's lstStyle only
            lp_props = lp.lst_levels.get(lvl, {}) if lp is not None else {}
            mp_props = mp.lst_levels.get(lvl, {}) if mp is not None else {}
            def_lvl_s = default_style.get(lvl) or default_style.get(0) or {}
            master_lvl_s = style_dict.get(lvl) or style_dict.get(0) or {}
            lvl_style = copy.deepcopy(def_lvl_s)
            lvl_style.update(master_lvl_s)

            # Alignment
            if "algn" not in p.props:
                if "algn" in lp_props:
                    p.props["algn"] = lp_props["algn"]
                elif "algn" in mp_props:
                    p.props["algn"] = mp_props["algn"]
                elif "algn" in lvl_style:
                    p.props["algn"] = lvl_style["algn"]
                else:
                    # Nothing in the file aligns it: PowerPoint's default, not the
                    # app's design default (a subtitle on a body layout is left-aligned)
                    p.props["algn"] = "l"

            # Bullet
            if "bu" not in p.props:
                if "bu" in lp_props:
                    p.props["bu"] = copy.deepcopy(lp_props["bu"])
                elif "bu" in mp_props:
                    p.props["bu"] = copy.deepcopy(mp_props["bu"])
                elif "bu" in lvl_style:
                    p.props["bu"] = copy.deepcopy(lvl_style["bu"])

            # Left margin and indent
            if "marL" not in p.props:
                if "marL" in lp_props:
                    p.props["marL"] = lp_props["marL"]
                elif "marL" in mp_props:
                    p.props["marL"] = mp_props["marL"]
                elif "marL" in lvl_style:
                    p.props["marL"] = lvl_style["marL"]

            if "indent" not in p.props:
                if "indent" in lp_props:
                    p.props["indent"] = lp_props["indent"]
                elif "indent" in mp_props:
                    p.props["indent"] = mp_props["indent"]
                elif "indent" in lvl_style:
                    p.props["indent"] = lvl_style["indent"]

            # Spacing
            if "lnSpc" not in p.props:
                if "lnSpc" in lp_props:
                    p.props["lnSpc"] = copy.deepcopy(lp_props["lnSpc"])
                elif "lnSpc" in mp_props:
                    p.props["lnSpc"] = copy.deepcopy(mp_props["lnSpc"])
                elif "lnSpc" in lvl_style:
                    p.props["lnSpc"] = copy.deepcopy(lvl_style["lnSpc"])

            if "spcBef" not in p.props:
                if "spcBef" in lp_props:
                    p.props["spcBef"] = copy.deepcopy(lp_props["spcBef"])
                elif "spcBef" in mp_props:
                    p.props["spcBef"] = copy.deepcopy(mp_props["spcBef"])
                elif "spcBef" in lvl_style:
                    p.props["spcBef"] = copy.deepcopy(lvl_style["spcBef"])

            if "spcAft" not in p.props:
                if "spcAft" in lp_props:
                    p.props["spcAft"] = copy.deepcopy(lp_props["spcAft"])
                elif "spcAft" in mp_props:
                    p.props["spcAft"] = copy.deepcopy(mp_props["spcAft"])
                elif "spcAft" in lvl_style:
                    p.props["spcAft"] = copy.deepcopy(lvl_style["spcAft"])

            lp_r = lp_p.runs[0] if (lp_p and lp_p.runs) else None
            mp_r = mp_p.runs[0] if (mp_p and mp_p.runs) else None

            # An empty placeholder keeps no runs; cascade into a prompt run so the
            # edit view can draw its prompt in the inherited style.
            targets = p.runs
            if is_empty and p is text_body.paragraphs[0] and not p.runs:
                text_body.prompt_run = Run(text=custom_prompt)
                targets = [text_body.prompt_run]

            for r in targets:
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

    def _apply_shape_text_inheritance(
        self,
        text_body: TextBody,
        layout_info: LayoutInfo | None,
        shape_elem: ET.Element | None = None,
    ) -> None:
        """Apply defaultTextStyle and master otherStyle inheritance to non-placeholder shapes."""
        master_info = layout_info.master if layout_info else None
        other_style = master_info.other_style if master_info else {}
        default_style = getattr(self, "default_text_style", {})

        shape_lst_styles: dict[int, dict[str, Any]] = {}
        if shape_elem is not None:
            tx_body_elem = _get_child(shape_elem, "txBody")
            if tx_body_elem is not None:
                lst_style_elem = _get_child(tx_body_elem, "lstStyle")
                if lst_style_elem is not None:
                    shape_lst_styles = self._parse_style_levels(lst_style_elem)

        default_font = master_info.minor_font if master_info and master_info.minor_font else "Arial"

        for p in text_body.paragraphs:
            lvl = p.level
            def_s = default_style.get(lvl) or default_style.get(0) or {}
            oth_s = other_style.get(lvl) or other_style.get(0) or {}
            own_lst_s = shape_lst_styles.get(lvl) or shape_lst_styles.get(0) or {}

            # Precedence: defaultTextStyle < otherStyle < shape lstStyle
            base_s = copy.deepcopy(def_s)
            base_s.update(oth_s)
            base_s.update(own_lst_s)

            # DrawingML default font size for otherStyle / regular shapes is 18.0 pt
            sz = base_s.get("sz", 18.0)
            font = base_s.get("font") or default_font
            color = base_s.get("color") or "tx1"

            for k in ("algn", "marL", "indent", "bu", "lnSpc", "spcBef", "spcAft"):
                if k not in p.props and k in base_s:
                    p.props[k] = copy.deepcopy(base_s[k])

            for r in p.runs:
                if r.size is None:
                    r.size = sz
                if r.font is None:
                    r.font = font
                if r.color is None and color:
                    r.color = color
                if not r.bold and base_s.get("b"):
                    r.bold = True
                if not r.italic and base_s.get("i"):
                    r.italic = True

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
        cols = 1
        col_gap = 0.0
        rtl_col = False
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

            num_col_attr = _get_attr(body_pr, "numCol")
            if num_col_attr:
                try:
                    num_col_val = int(num_col_attr)
                    if num_col_val > 1:
                        cols = num_col_val
                        spc_col_attr = _get_attr(body_pr, "spcCol")
                        if spc_col_attr:
                            col_gap = emu_to_pt(spc_col_attr, default=0.0)
                except ValueError:
                    pass

            rtl_col_attr = _get_attr(body_pr, "rtlCol")
            if rtl_col_attr in ("1", "true", "True"):
                rtl_col = True

            norm_elem = _get_child(body_pr, "normAutofit")
            if norm_elem is not None:
                autofit = "norm"
                # The stored scale is the file's fitted state; no fontScale means 100%.
                # PowerPoint (and the original) only re-fit once the text is edited.
                has_explicit_font_scale = True
                fs_attr = _get_attr(norm_elem, "fontScale")
                if fs_attr:
                    fs_num = safe_float(fs_attr, float("nan"))
                    if math.isfinite(fs_num) and fs_num > 0:
                        font_scale = max(0.01, min(1.0, fs_num / 100000.0))
                        has_explicit_font_scale = True
                    else:
                        font_scale = 1.0
                ls_attr = _get_attr(norm_elem, "lnSpcReduction")
                if ls_attr:
                    ls_num = safe_float(ls_attr, 0.0)
                    ln_spc_red = max(0.0, min(1.0, ls_num / 100000.0))
            elif _get_child(body_pr, "spAutoFit") is not None:
                autofit = "shape"

        lst_style_elem = _get_child(tx_body, "lstStyle")
        lst_styles = self._parse_style_levels(lst_style_elem) if lst_style_elem is not None else {}

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
            cols=cols,
            col_gap=col_gap,
            rtl_col=rtl_col,
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

            p_def_r_pr = _get_child(p_pr, "defRPr")
            p_def_sz = None
            p_def_b = None
            p_def_i = None
            p_def_font = None
            p_def_color = None
            if p_def_r_pr is not None:
                sz_attr = _get_attr(p_def_r_pr, "sz")
                if sz_attr:
                    try:
                        p_def_sz = round(float(sz_attr) / 100.0, 1)
                    except ValueError:
                        pass
                b_attr = _get_attr(p_def_r_pr, "b")
                if b_attr in ("1", "true", "on"):
                    p_def_b = True
                i_attr = _get_attr(p_def_r_pr, "i")
                if i_attr in ("1", "true", "on"):
                    p_def_i = True
                latin_el = _get_child(p_def_r_pr, "latin")
                if latin_el is not None:
                    p_def_font = _get_attr(latin_el, "typeface")
                solid_fill = _get_child(p_def_r_pr, "solidFill")
                if solid_fill is not None:
                    p_def_color = self._extract_color(solid_fill)

        runs: list[Run] = []
        display_math_jc: str | None = None

        def _consume(child: ET.Element) -> None:
            nonlocal display_math_jc
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
            elif ltag == "m":  # a14:m inline OMML math zone
                for zone in child:
                    math_run = self._parse_math_zone(
                        zone, default_color=default_color, rel_map=rel_map
                    )
                    if math_run is not None:
                        runs.append(math_run)
                        item = math_run.math
                        if item.display and display_math_jc is None:
                            display_math_jc = item.jc or "centerGroup"
            elif ltag == "AlternateContent":
                branch = mce.select_branch(child)
                if branch is not None:
                    for sub in branch:
                        _consume(sub)

        for child in p_elem:
            _consume(child)

        if display_math_jc is not None and not algn_val:
            algn_val = {"left": "l", "right": "r"}.get(display_math_jc, "ctr")

        if p_pr is not None and p_def_r_pr is not None:
            for r in runs:
                if r.size is None and p_def_sz is not None:
                    r.size = p_def_sz
                if r.font is None and p_def_font is not None:
                    r.font = p_def_font
                if r.color is None and p_def_color is not None:
                    r.color = p_def_color
                if not r.bold and p_def_b:
                    r.bold = True
                if not r.italic and p_def_i:
                    r.italic = True

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

    def _parse_math_zone(
        self,
        zone: ET.Element,
        default_color: str | None = None,
        rel_map: dict[str, Any] | None = None,
    ) -> Run | None:
        """Turn an <m:oMathPara>/<m:oMath> zone into a run carrying the parsed formula."""
        if _local_tag(zone.tag) not in ("oMathPara", "oMath"):
            return None
        item = parse_omml(zone)
        text = item.plain_text()
        if not text:
            return None
        # Formatting comes from the first DrawingML a:rPr inside a math run.
        proto = ET.Element("r")
        for el in zone.iter():
            if el.tag == f"{{{NS_A}}}rPr":
                proto.append(el)
                break
        run = self._parse_run(proto, default_color=default_color, rel_map=rel_map)
        run.text = text
        run.font = run.font or "Cambria Math"
        run.math = item
        return run

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
