"""PPTX reader: themes, colour schemes, table styles and style references."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atboffice.modules.presentation.io import pptx_table_styles as tstyles
from atboffice.modules.presentation.io.pptx_common import (
    REL_THEME,
    LayoutInfo,
    _get_attr,
    _get_child,
    _local_tag,
    _resolve_path,
    clamp_alpha,
    safe_float,
)
from atboffice.modules.presentation.models.designs import (
    COLOR_SLOT_MAP,
    ColorScheme,
    apply_color_mods,
    resolve_color,
)
from atboffice.modules.presentation.models.presentation import (
    LoadWarning,
    Presentation,
)
from atboffice.modules.presentation.models.shape import (
    Fill,
    Line,
)
from atboffice.vfs import etree as ET


class PptxThemeParserMixin:
    """Reads themes, colour schemes, colours, table styles and style references."""

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
        """Extract resolved color string and alpha from XML element, applying mods and maps."""
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
            mval = safe_float(mval_str, 0.0) if mval_str else 0.0
            if mtag == "alpha":
                alpha = mval / 100000.0
            elif mtag == "alphaMod":
                alpha *= mval / 100000.0
            elif mtag == "alphaOff":
                alpha += mval / 100000.0
            else:
                mods.append({"name": mtag, "val": mval})

        alpha = clamp_alpha(alpha, 1.0)

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
            r_val = safe_float(_get_attr(target, "r", "0"), 0.0) / 100000.0
            g_val = safe_float(_get_attr(target, "g", "0"), 0.0) / 100000.0
            b_val = safe_float(_get_attr(target, "b", "0"), 0.0) / 100000.0
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
                    # Keep tint/shade/lumMod… on the slot ("tx1|tint=75000"); alpha is
                    # not part of the color
                    mods = [
                        f"{_local_tag(m.tag)}={_get_attr(m, 'val')}"
                        for m in child
                        if _get_attr(m, "val") is not None
                        and not _local_tag(m.tag).startswith("alpha")
                    ]
                    return f"{val}|{','.join(mods)}" if mods else val
            elif tag == "scrgbClr":
                clr, _ = self._extract_color_detail(child)
                return clr
        return None

    def _load_table_styles(self, pres_part: str, pres_rels: list[Any]) -> None:
        """Load the table style catalog referenced by the presentation part."""
        ts_path = "ppt/tableStyles.xml"
        for rel in pres_rels:
            if str(getattr(rel, "type", "")).endswith("/tableStyles"):
                ts_path = _resolve_path(pres_part, rel.target)
                break
        if not self.package.has_part(ts_path):
            return
        try:
            self._table_styles = tstyles.TableStyleCatalog.from_xml(self.package.read_part(ts_path))
        except ET.ParseError as exc:
            self._warnings.append(
                LoadWarning(scope="tableStyles", location=ts_path, message=str(exc))
            )

    def _get_theme_colors(self, theme_path: str) -> ColorScheme | None:
        themes = getattr(self, "themes", {})
        if not theme_path:
            return next(iter(themes.values()), None)
        clean_path = theme_path.lstrip("/")
        for k, v in themes.items():
            k_clean = k.lstrip("/")
            if k == theme_path or k_clean == clean_path or Path(k).name == Path(clean_path).name:
                return v
        return next(iter(themes.values()), None)

    def _get_theme_fmt(self, theme_path: str) -> dict[str, list[ET.Element]]:
        theme_fmt = getattr(self, "theme_fmt", {})
        if not theme_path:
            return next(iter(theme_fmt.values()), {"fills": [], "lines": [], "bgFills": []})
        clean_path = theme_path.lstrip("/")
        for k, v in theme_fmt.items():
            k_clean = k.lstrip("/")
            if k == theme_path or k_clean == clean_path or Path(k).name == Path(clean_path).name:
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
            dft_fmt = {"fills": [], "lines": [], "bgFills": []}
            theme_fmt = next(iter(theme_fmt_dict.values()), dft_fmt)
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
