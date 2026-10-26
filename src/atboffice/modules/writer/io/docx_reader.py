"""ECMA-376 WordprocessingML reader for DOCX and DOCM files."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from atboffice.modules.writer.models.document import (
    BookmarkEndItem,
    BookmarkStartItem,
    BreakItem,
    Cell,
    CommentRangeEnd,
    CommentRangeStart,
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    Row,
    RunItem,
    Story,
    SymbolItem,
    TabItem,
    Table,
    TextItem,
    normalize,
)
from atboffice.modules.writer.models.properties import (
    BorderProperties,
    CellProperties,
    ColumnsProperties,
    DocGridProperties,
    IndentProperties,
    NumberingRef,
    PageNumberProperties,
    ParagraphProperties,
    RowProperties,
    RunProperties,
    SectionProperties,
    ShadingProperties,
    SpacingProperties,
    TableProperties,
    TabStop,
    dxa_to_pt,
)
from atboffice.modules.writer.models.styles import Style, builtin_styles
from atboffice.vfs.opc import Relationship, SourcePackage

# Common XML Namespaces
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
NS_XML = "http://www.w3.org/XML/1998/namespace"

CT_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
CT_DOCM = "application/vnd.ms-word.document.macroEnabled.main+xml"
CT_DOTX = "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"


def _local_tag(elem: ET.Element | str) -> str:
    """Extract tag name stripped of namespace or Clark notation."""
    tag = elem.tag if isinstance(elem, ET.Element) else elem
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    if ":" in tag:
        return tag.split(":", 1)[1]
    return tag


def _get_attr(elem: ET.Element, name: str, default: str | None = None) -> str | None:
    """Get attribute value matching local name regardless of namespace."""
    if name in elem.attrib:
        return elem.attrib[name]
    for k, v in elem.attrib.items():
        local = k.split("}", 1)[1] if k.startswith("{") else (k.split(":", 1)[1] if ":" in k else k)
        if local == name:
            return v
    return default


def _bool_val(elem: ET.Element | None, default: bool = False) -> bool:
    """Extract boolean value from OOXML element (w:val='1|true|on' or presence)."""
    if elem is None:
        return default
    val = _get_attr(elem, "val")
    if val is None:
        return True
    val_lower = val.strip().lower()
    return val_lower not in ("0", "false", "off", "no")


def _twips_to_pt(val: str | int | float | None, default: float = 0.0) -> float:
    """Convert twips/dxa (1/20 of a pt) to points."""
    if val is None or val == "":
        return default
    try:
        return float(val) / 20.0
    except (ValueError, TypeError):
        return default


def _hp_to_pt(val: str | int | float | None, default: float = 12.0) -> float:
    """Convert half-points (1/2 pt) to points."""
    if val is None or val == "":
        return default
    try:
        return float(val) / 2.0
    except (ValueError, TypeError):
        return default


def _eighths_to_pt(val: str | int | float | None, default: float = 0.5) -> float:
    """Convert eighth-points (1/8 pt) to points."""
    if val is None or val == "":
        return default
    try:
        return float(val) / 8.0
    except (ValueError, TypeError):
        return default


class DocxReader:
    """Reads ECMA-376 WordprocessingML (.docx, .docm) into Quire Document."""

    def __init__(self, source_pkg: SourcePackage) -> None:
        self.pkg = source_pkg
        self.main_path = "word/document.xml"
        self.doc_format = "docx"
        self.rels: dict[str, Relationship] = {}
        self.doc = Document()
        self.doc._source_pkg = source_pkg  # type: ignore[attr-defined]

    def read(self) -> Document:
        """Parse the complete package and return the populated Document."""
        self._discover_main_part()
        self._load_document_relationships()
        self._parse_styles()
        self._parse_settings()
        self._parse_fonts()
        self._parse_body()
        self._parse_headers_footers()
        self.doc._doc_format = self.doc_format  # type: ignore[attr-defined]
        return self.doc

    def _discover_main_part(self) -> None:
        """Locate main document part from root _rels/.rels and detect format."""
        root_rels = self.pkg.get_relationships("")
        for r in root_rels:
            if r.type.endswith("/officeDocument"):
                target = r.target.lstrip("/")
                self.main_path = target
                break

        ct = self.pkg.get_content_type(self.main_path)
        if ct == CT_DOCM or self.pkg.has_part("word/vbaProject.bin"):
            self.doc_format = "docm"
        elif ct == CT_DOTX:
            self.doc_format = "dotx"
        else:
            self.doc_format = "docx"

    def _load_document_relationships(self) -> None:
        """Load relationship entries for main document part."""
        rels_list = self.pkg.get_relationships(self.main_path)
        self.rels = {r.id: r for r in rels_list}

    def _rel_target(self, rel_type_suffix: str) -> str | None:
        """Find relationship target matching type suffix."""
        for r in self.rels.values():
            if r.type.endswith("/" + rel_type_suffix) or r.type.endswith(rel_type_suffix):
                if r.target_mode == "Internal":
                    # Target may be relative to word/
                    target = r.target.lstrip("/")
                    if not target.startswith("word/") and not target.startswith("docProps/"):
                        target = f"word/{target}"
                    return target
        return None

    def _parse_styles(self) -> None:
        """Parse word/styles.xml into doc.styles and doc.defaults."""
        styles_path = self._rel_target("styles") or "word/styles.xml"
        if not self.pkg.has_part(styles_path):
            self.doc.styles = builtin_styles()
            return

        try:
            root = ET.fromstring(self.pkg.read_part(styles_path))
        except Exception:
            self.doc.styles = builtin_styles()
            return

        styles = builtin_styles()

        # Parse docDefaults
        doc_defaults = root.find(f"{{{NS_W}}}docDefaults")
        if doc_defaults is not None:
            r_pr_def = doc_defaults.find(f".//{{{NS_W}}}rPr")
            p_pr_def = doc_defaults.find(f".//{{{NS_W}}}pPr")
            if r_pr_def is not None:
                self.doc.defaults["r_pr"] = self._parse_r_pr(r_pr_def)
            if p_pr_def is not None:
                self.doc.defaults["p_pr"] = self._parse_p_pr(p_pr_def)

        # Parse style elements
        for style_elem in root.findall(f"{{{NS_W}}}style"):
            s_id = _get_attr(style_elem, "styleId")
            s_type = _get_attr(style_elem, "type", "paragraph")
            if not s_id:
                continue

            name_elem = style_elem.find(f"{{{NS_W}}}name")
            s_name = _get_attr(name_elem, "val", s_id) if name_elem is not None else s_id

            based_on_elem = style_elem.find(f"{{{NS_W}}}basedOn")
            based_on = _get_attr(based_on_elem, "val") if based_on_elem is not None else None

            next_elem = style_elem.find(f"{{{NS_W}}}next")
            next_s = _get_attr(next_elem, "val") if next_elem is not None else None

            is_default = _bool_val(style_elem.find(f"{{{NS_W}}}default"), False) or _get_attr(style_elem, "default") == "1"

            p_pr = None
            p_pr_elem = style_elem.find(f"{{{NS_W}}}pPr")
            if p_pr_elem is not None:
                p_pr = self._parse_p_pr(p_pr_elem)

            r_pr = None
            r_pr_elem = style_elem.find(f"{{{NS_W}}}rPr")
            if r_pr_elem is not None:
                r_pr = self._parse_r_pr(r_pr_elem)

            styles[s_id] = Style(
                id=s_id,
                name=s_name,
                style_type=s_type,
                based_on=based_on,
                next_style=next_s,
                p_pr=p_pr or ParagraphProperties(),
                r_pr=r_pr or RunProperties(),
                builtin=False,
                is_default=is_default,
            )

        self.doc.styles = styles

    def _parse_settings(self) -> None:
        """Parse word/settings.xml into doc.settings."""
        settings_path = self._rel_target("settings") or "word/settings.xml"
        if not self.pkg.has_part(settings_path):
            return

        try:
            root = ET.fromstring(self.pkg.read_part(settings_path))
            settings: dict[str, Any] = {}
            for child in root:
                tag = _local_tag(child)
                val = _get_attr(child, "val")
                settings[tag] = val if val is not None else True
            self.doc.settings = settings
        except Exception:
            pass

    def _parse_fonts(self) -> None:
        """Parse word/fontTable.xml into doc.props['fonts']."""
        fonts_path = self._rel_target("fontTable") or "word/fontTable.xml"
        if not self.pkg.has_part(fonts_path):
            return

        try:
            root = ET.fromstring(self.pkg.read_part(fonts_path))
            fonts: list[str] = []
            for font_elem in root.findall(f"{{{NS_W}}}font"):
                name = _get_attr(font_elem, "name")
                if name:
                    fonts.append(name)
            self.doc.props["fonts"] = fonts
        except Exception:
            pass

    def _parse_body(self) -> None:
        """Parse main story body blocks from word/document.xml."""
        if not self.pkg.has_part(self.main_path):
            raise ValueError(f"Package missing main document part: {self.main_path}")

        root = ET.fromstring(self.pkg.read_part(self.main_path))
        body = root.find(f"{{{NS_W}}}body")
        if body is None:
            return

        blocks: list[Paragraph | Table] = []
        for child in body:
            tag = _local_tag(child)
            if tag == "p":
                p = self._parse_paragraph(child)
                blocks.append(p)
            elif tag == "tbl":
                tbl = self._parse_table(child)
                blocks.append(tbl)
            elif tag == "sectPr":
                self.doc.sect = self._parse_sect_pr(child)

        self.doc.main = Story(kind="main", blocks=blocks)

    def _parse_paragraph(self, p_elem: ET.Element) -> Paragraph:
        """Parse <w:p> element into Paragraph."""
        p = Paragraph()
        p_pr_elem = p_elem.find(f"{{{NS_W}}}pPr")
        if p_pr_elem is not None:
            p.p_pr = self._parse_p_pr(p_pr_elem)
            # Check for section properties attached to paragraph
            sect_elem = p_pr_elem.find(f"{{{NS_W}}}sectPr")
            if sect_elem is not None:
                p.sect = self._parse_sect_pr(sect_elem)

        # Parse inline runs and items
        runs: list[RunItem] = []
        for child in p_elem:
            tag = _local_tag(child)
            if tag == "pPr":
                continue
            self._parse_inline_element(child, runs)

        p.runs = runs
        normalize(p)
        return p

    def _parse_inline_element(
        self,
        elem: ET.Element,
        runs: list[RunItem],
        inherited_r_pr: RunProperties | None = None,
        link_info: dict[str, Any] | None = None,
    ) -> None:
        """Parse child inline element of <w:p> into runs."""
        tag = _local_tag(elem)

        if tag == "r":
            r_pr_elem = elem.find(f"{{{NS_W}}}rPr")
            r_pr = self._parse_r_pr(r_pr_elem) if r_pr_elem is not None else RunProperties()
            if link_info:
                r_pr.link = link_info  # type: ignore[attr-defined]

            for child in elem:
                c_tag = _local_tag(child)
                if c_tag == "rPr":
                    continue
                elif c_tag == "t":
                    text = child.text or ""
                    runs.append(TextItem(text=text, r_pr=r_pr))
                elif c_tag == "tab":
                    runs.append(TabItem(r_pr=r_pr))
                elif c_tag == "br" or c_tag == "cr":
                    br_type = _get_attr(child, "type", "line")
                    runs.append(BreakItem(break_type=br_type, r_pr=r_pr))
                elif c_tag == "sym":
                    font = _get_attr(child, "font", "Symbol")
                    char_code = _get_attr(child, "char", "")
                    try:
                        char = chr(int(char_code, 16)) if char_code else ""
                    except Exception:
                        char = ""
                    runs.append(SymbolItem(font=font, char=char, r_pr=r_pr))
                elif c_tag == "noBreakHyphen":
                    runs.append(TextItem(text="‑", r_pr=r_pr))
                elif c_tag == "softHyphen":
                    runs.append(TextItem(text="­", r_pr=r_pr))
                elif c_tag == "fldChar":
                    fld_type = _get_attr(child, "fldCharType", "")
                    if fld_type == "begin":
                        runs.append(FieldBeginItem(r_pr=r_pr))
                    elif fld_type == "separate":
                        runs.append(FieldSeparateItem(r_pr=r_pr))
                    elif fld_type == "end":
                        runs.append(FieldEndItem(r_pr=r_pr))
                elif c_tag == "instrText":
                    # Field instruction text
                    text = child.text or ""
                    if runs and isinstance(runs[-1], FieldBeginItem):
                        runs[-1].instr += text
                    else:
                        runs.append(TextItem(text=text, r_pr=r_pr))

        elif tag == "hyperlink":
            r_id = _get_attr(elem, "id") or _get_attr(elem, "rid") or _get_attr(elem, "r:id")
            anchor = _get_attr(elem, "anchor") or ""
            url = ""
            if r_id and r_id in self.rels:
                url = self.rels[r_id].target
            h_link = {"url": url, "anchor": anchor} if (url or anchor) else None
            for child in elem:
                self._parse_inline_element(child, runs, inherited_r_pr, h_link)

        elif tag == "bookmarkStart":
            name = _get_attr(elem, "name", "")
            b_id = int(_get_attr(elem, "id", "0") or "0")
            runs.append(BookmarkStartItem(name=name, bookmark_id=b_id))

        elif tag == "bookmarkEnd":
            b_id = int(_get_attr(elem, "id", "0") or "0")
            runs.append(BookmarkEndItem(bookmark_id=b_id))

        elif tag == "commentRangeStart":
            c_id = _get_attr(elem, "id", "0") or "0"
            runs.append(CommentRangeStart(comment_id=c_id))

        elif tag == "commentRangeEnd":
            c_id = _get_attr(elem, "id", "0") or "0"
            runs.append(CommentRangeEnd(comment_id=c_id))

        elif tag == "fldSimple":
            instr = _get_attr(elem, "instr", "")
            runs.append(FieldBeginItem(instr=instr))
            runs.append(FieldSeparateItem())
            for child in elem:
                self._parse_inline_element(child, runs)
            runs.append(FieldEndItem())

    def _parse_p_pr(self, p_pr_elem: ET.Element) -> ParagraphProperties:
        """Parse <w:pPr> element into ParagraphProperties."""
        p_pr = ParagraphProperties()
        for child in p_pr_elem:
            tag = _local_tag(child)
            if tag == "pStyle":
                style_val = _get_attr(child, "val")
                if style_val:
                    p_pr.style = style_val
            elif tag == "jc":
                jc_val = _get_attr(child, "val")
                if jc_val:
                    jc_map = {
                        "start": "left",
                        "end": "right",
                        "left": "left",
                        "right": "right",
                        "center": "center",
                        "both": "both",
                        "justify": "both",
                        "distribute": "distribute",
                    }
                    p_pr.jc = jc_map.get(jc_val, "left")
            elif tag == "spacing":
                b = _twips_to_pt(_get_attr(child, "before"))
                a = _twips_to_pt(_get_attr(child, "after"))
                rule = _get_attr(child, "lineRule", "auto")
                line_val = _get_attr(child, "line")
                if line_val is not None:
                    line_num = float(line_val)
                    line = line_num / 240.0 if rule == "auto" else line_num / 20.0
                else:
                    line = 1.0
                b_auto = _bool_val(child.find(f"{{{NS_W}}}beforeAutospacing"), False) or _get_attr(child, "beforeAutospacing") == "1"
                a_auto = _bool_val(child.find(f"{{{NS_W}}}afterAutospacing"), False) or _get_attr(child, "afterAutospacing") == "1"
                p_pr.sp = SpacingProperties(
                    before=b,
                    after=a,
                    line=line,
                    line_rule=rule,
                    before_auto=b_auto,
                    after_auto=a_auto,
                )
            elif tag == "ind":
                l = _twips_to_pt(_get_attr(child, "left") or _get_attr(child, "start"))
                r = _twips_to_pt(_get_attr(child, "right") or _get_attr(child, "end"))
                fl = 0.0
                if _get_attr(child, "hanging") is not None:
                    fl = -_twips_to_pt(_get_attr(child, "hanging"))
                elif _get_attr(child, "firstLine") is not None:
                    fl = _twips_to_pt(_get_attr(child, "firstLine"))
                p_pr.ind = IndentProperties(left=l, right=r, first_line=fl)
            elif tag == "keepNext":
                p_pr.keep_next = _bool_val(child, True)
            elif tag == "keepLines":
                p_pr.keep_lines = _bool_val(child, True)
            elif tag == "pageBreakBefore":
                p_pr.page_break_before = _bool_val(child, True)
            elif tag == "widowControl":
                p_pr.widow_control = _bool_val(child, True)
            elif tag == "outlineLvl":
                lvl_val = _get_attr(child, "val")
                if lvl_val is not None:
                    try:
                        p_pr.outline_level = int(lvl_val)
                    except ValueError:
                        pass
            elif tag == "numPr":
                num_id_elem = child.find(f"{{{NS_W}}}numId")
                num_id = _get_attr(num_id_elem if num_id_elem is not None else child, "val", "0")
                ilvl_elem = child.find(f"{{{NS_W}}}ilvl")
                ilvl = int(_get_attr(ilvl_elem if ilvl_elem is not None else child, "val", "0") or "0")
                p_pr.num = NumberingRef(id=str(num_id), lvl=ilvl)
            elif tag == "tabs":
                tabs: list[TabStop] = []
                for tab_elem in child.findall(f"{{{NS_W}}}tab"):
                    pos = _twips_to_pt(_get_attr(tab_elem, "pos"))
                    align = _get_attr(tab_elem, "val", "left")
                    leader = _get_attr(tab_elem, "leader", "none")
                    tabs.append(TabStop(pos=pos, align=align, leader=leader))
                p_pr.tabs = tabs
        return p_pr

    def _parse_r_pr(self, r_pr_elem: ET.Element) -> RunProperties:
        """Parse <w:rPr> element into RunProperties."""
        r_pr = RunProperties()
        for child in r_pr_elem:
            tag = _local_tag(child)
            if tag == "rStyle":
                r_pr.style = _get_attr(child, "val")
            elif tag == "rFonts":
                ascii_f = _get_attr(child, "ascii") or _get_attr(child, "hAnsi")
                if ascii_f:
                    r_pr.font = ascii_f
                ea_f = _get_attr(child, "eastAsia")
                if ea_f:
                    r_pr.font_ea = ea_f
                cs_f = _get_attr(child, "cs")
                if cs_f:
                    r_pr.font_cs = cs_f
            elif tag == "b":
                r_pr.b = _bool_val(child, True)
            elif tag == "i":
                r_pr.i = _bool_val(child, True)
            elif tag == "u":
                u_val = _get_attr(child, "val", "single")
                r_pr.u = u_val if u_val != "none" else "none"
            elif tag == "sz":
                r_pr.sz = _hp_to_pt(_get_attr(child, "val"), 12.0)
            elif tag == "szCs":
                r_pr.sz_cs = _hp_to_pt(_get_attr(child, "val"))
            elif tag == "color":
                c_val = _get_attr(child, "val")
                if c_val:
                    r_pr.color = c_val if c_val.lower() == "auto" else f"#{c_val.upper()}"
            elif tag == "highlight":
                r_pr.highlight = _get_attr(child, "val")
            elif tag == "strike":
                r_pr.strike = _bool_val(child, True)
            elif tag == "dstrike":
                r_pr.dstrike = _bool_val(child, True)
            elif tag == "caps":
                r_pr.caps = _bool_val(child, True)
            elif tag == "smallCaps":
                r_pr.small_caps = _bool_val(child, True)
            elif tag == "vertAlign":
                r_pr.vert = _get_attr(child, "val", "baseline")
            elif tag == "spacing":
                r_pr.spacing = _twips_to_pt(_get_attr(child, "val"))
            elif tag == "kern":
                r_pr.kern = _hp_to_pt(_get_attr(child, "val"))
            elif tag == "lang":
                lang_val = _get_attr(child, "val")
                if lang_val:
                    r_pr.lang = lang_val
                ea_lang = _get_attr(child, "eastAsia")
                if ea_lang:
                    r_pr.lang_ea = ea_lang
        return r_pr

    def _parse_table(self, tbl_elem: ET.Element) -> Table:
        """Parse <w:tbl> element into Table."""
        tbl = Table()

        # Table Properties
        tbl_pr_elem = tbl_elem.find(f"{{{NS_W}}}tblPr")
        if tbl_pr_elem is not None:
            tbl_pr = TableProperties()
            style_elem = tbl_pr_elem.find(f"{{{NS_W}}}tblStyle")
            if style_elem is not None:
                tbl_pr.style = _get_attr(style_elem, "val", "TableNormal")
            jc_elem = tbl_pr_elem.find(f"{{{NS_W}}}jc")
            if jc_elem is not None:
                tbl_pr.jc = _get_attr(jc_elem, "val", "left")
            w_elem = tbl_pr_elem.find(f"{{{NS_W}}}tblW")
            if w_elem is not None:
                tbl_pr.w_type = _get_attr(w_elem, "type", "auto")
                tbl_pr.w = _twips_to_pt(_get_attr(w_elem, "w", "0"))
            tbl.tbl_pr = tbl_pr

        # Table Grid
        tbl_grid_elem = tbl_elem.find(f"{{{NS_W}}}tblGrid")
        if tbl_grid_elem is not None:
            for col_elem in tbl_grid_elem.findall(f"{{{NS_W}}}gridCol"):
                w = _twips_to_pt(_get_attr(col_elem, "w", "0"))
                tbl.grid.append(w)

        # Table Rows
        rows: list[Row] = []
        for tr_elem in tbl_elem.findall(f"{{{NS_W}}}tr"):
            row = Row()
            tr_pr_elem = tr_elem.find(f"{{{NS_W}}}trPr")
            if tr_pr_elem is not None:
                tr_pr = RowProperties()
                h_elem = tr_pr_elem.find(f"{{{NS_W}}}trHeight")
                if h_elem is not None:
                    tr_pr.h = _twips_to_pt(_get_attr(h_elem, "val", "0"))
                    tr_pr.h_rule = _get_attr(h_elem, "hRule", "auto")
                if tr_pr_elem.find(f"{{{NS_W}}}tblHeader") is not None:
                    tr_pr.tbl_header = True
                if tr_pr_elem.find(f"{{{NS_W}}}cantSplit") is not None:
                    tr_pr.cant_split = True
                row.tr_pr = tr_pr

            # Table Cells
            cells: list[Cell] = []
            for tc_elem in tr_elem.findall(f"{{{NS_W}}}tc"):
                cell = Cell()
                tc_pr_elem = tc_elem.find(f"{{{NS_W}}}tcPr")
                if tc_pr_elem is not None:
                    tc_pr = CellProperties()
                    w_elem = tc_pr_elem.find(f"{{{NS_W}}}tcW")
                    if w_elem is not None:
                        tc_pr.w = _twips_to_pt(_get_attr(w_elem, "w", "0"))
                        tc_pr.w_type = _get_attr(w_elem, "type", "dxa")
                    gs_elem = tc_pr_elem.find(f"{{{NS_W}}}gridSpan")
                    if gs_elem is not None:
                        tc_pr.grid_span = int(_get_attr(gs_elem, "val", "1") or "1")
                    vm_elem = tc_pr_elem.find(f"{{{NS_W}}}vMerge")
                    if vm_elem is not None:
                        tc_pr.v_merge = _get_attr(vm_elem, "val", "continue")
                    va_elem = tc_pr_elem.find(f"{{{NS_W}}}vAlign")
                    if va_elem is not None:
                        tc_pr.v_align = _get_attr(va_elem, "val", "top")
                    shd_elem = tc_pr_elem.find(f"{{{NS_W}}}shd")
                    if shd_elem is not None:
                        fill = _get_attr(shd_elem, "fill", "auto")
                        tc_pr.shd = ShadingProperties(
                            val=_get_attr(shd_elem, "val", "clear"),
                            color=_get_attr(shd_elem, "color", "auto"),
                            fill=f"#{fill.upper()}" if fill and fill.lower() != "auto" else "auto",
                        )
                    cell.tc_pr = tc_pr

                # Cell Blocks
                cell_blocks: list[Paragraph | Table] = []
                for c_child in tc_elem:
                    c_tag = _local_tag(c_child)
                    if c_tag == "p":
                        cell_blocks.append(self._parse_paragraph(c_child))
                    elif c_tag == "tbl":
                        cell_blocks.append(self._parse_table(c_child))

                if not cell_blocks:
                    cell_blocks.append(Paragraph())
                cell.blocks = cell_blocks
                cells.append(cell)

            row.cells = cells
            rows.append(row)

        tbl.rows = rows
        return tbl

    def _parse_sect_pr(self, sect_elem: ET.Element) -> SectionProperties:
        """Parse <w:sectPr> element into SectionProperties."""
        sect = SectionProperties()

        pg_sz_elem = sect_elem.find(f"{{{NS_W}}}pgSz")
        if pg_sz_elem is not None:
            sect.pg_w = _twips_to_pt(_get_attr(pg_sz_elem, "w"), 612.0)
            sect.pg_h = _twips_to_pt(_get_attr(pg_sz_elem, "h"), 792.0)
            sect.orient = _get_attr(pg_sz_elem, "orient", "portrait")

        pg_mar_elem = sect_elem.find(f"{{{NS_W}}}pgMar")
        if pg_mar_elem is not None:
            sect.mt = _twips_to_pt(_get_attr(pg_mar_elem, "top"), 72.0)
            sect.mb = _twips_to_pt(_get_attr(pg_mar_elem, "bottom"), 72.0)
            sect.ml = _twips_to_pt(_get_attr(pg_mar_elem, "left"), 90.0)
            sect.mr = _twips_to_pt(_get_attr(pg_mar_elem, "right"), 90.0)
            sect.hdr = _twips_to_pt(_get_attr(pg_mar_elem, "header"), 36.0)
            sect.ftr = _twips_to_pt(_get_attr(pg_mar_elem, "footer"), 36.0)
            sect.gutter = _twips_to_pt(_get_attr(pg_mar_elem, "gutter"), 0.0)

        cols_elem = sect_elem.find(f"{{{NS_W}}}cols")
        if cols_elem is not None:
            num = int(_get_attr(cols_elem, "num", "1") or "1")
            space = _twips_to_pt(_get_attr(cols_elem, "space", "720"))
            sect.cols = ColumnsProperties(num=num, space=space)

        type_elem = sect_elem.find(f"{{{NS_W}}}type")
        if type_elem is not None:
            sect.sect_type = _get_attr(type_elem, "val", "nextPage")

        if sect_elem.find(f"{{{NS_W}}}titlePg") is not None:
            sect.title_pg = True

        # Header and Footer References
        refs: dict[str, dict[str, str]] = {"hdr": {}, "ftr": {}}
        for hdr_ref in sect_elem.findall(f"{{{NS_W}}}headerReference"):
            r_type = _get_attr(hdr_ref, "type", "default")
            r_id = _get_attr(hdr_ref, "id") or _get_attr(hdr_ref, "rid")
            if r_id:
                refs["hdr"][r_type] = r_id
        for ftr_ref in sect_elem.findall(f"{{{NS_W}}}footerReference"):
            r_type = _get_attr(ftr_ref, "type", "default")
            r_id = _get_attr(ftr_ref, "id") or _get_attr(ftr_ref, "rid")
            if r_id:
                refs["ftr"][r_type] = r_id
        sect.refs = refs

        return sect

    def _parse_headers_footers(self) -> None:
        """Parse referenced header and footer stories into doc.hf."""
        all_refs: list[tuple[str, str]] = []
        for kind in ("hdr", "ftr"):
            for r_id in self.doc.sect.refs.get(kind, {}).values():
                all_refs.append((kind, r_id))

        # Check section references inside paragraphs
        for block in self.doc.main.blocks:
            if isinstance(block, Paragraph) and block.sect:
                for kind in ("hdr", "ftr"):
                    for r_id in block.sect.refs.get(kind, {}).values():
                        all_refs.append((kind, r_id))

        for kind, r_id in all_refs:
            if r_id in self.rels:
                rel = self.rels[r_id]
                part_path = rel.target.lstrip("/")
                if not part_path.startswith("word/"):
                    part_path = f"word/{part_path}"
                if self.pkg.has_part(part_path):
                    try:
                        root = ET.fromstring(self.pkg.read_part(part_path))
                        hf_blocks: list[Paragraph | Table] = []
                        for child in root:
                            c_tag = _local_tag(child)
                            if c_tag == "p":
                                hf_blocks.append(self._parse_paragraph(child))
                            elif c_tag == "tbl":
                                hf_blocks.append(self._parse_table(child))
                        self.doc.hf[r_id] = Story(
                            kind="header" if kind == "hdr" else "footer",
                            blocks=hf_blocks,
                        )
                    except Exception:
                        pass


def read_docx(source: str | Path | bytes | io.BytesIO) -> Document:
    """Convenience function to read a DOCX/DOCM file or buffer into Document."""
    if isinstance(source, (str, Path)):
        pkg = SourcePackage.open(source)
    elif isinstance(source, bytes):
        pkg = SourcePackage.from_bytes(source)
    elif isinstance(source, io.BytesIO):
        pkg = SourcePackage.from_bytes(source.getvalue())
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")

    reader = DocxReader(pkg)
    return reader.read()
