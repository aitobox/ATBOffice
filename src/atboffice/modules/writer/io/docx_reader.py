"""ECMA-376 WordprocessingML reader for DOCX and DOCM files."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

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
    NoteRefItem,
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
from atboffice.modules.writer.models.drawing import (
    Crop,
    FloatProperties,
    PictureItem,
    PositionH,
    PositionV,
    WrapDist,
    WrapMode,
    WrapSide,
)
from atboffice.modules.writer.models.omml import parse_omml
from atboffice.modules.writer.models.properties import (
    BorderProperties,
    CellProperties,
    ColumnsProperties,
    DocGridProperties,
    IndentProperties,
    NumberingRef,
    ParagraphProperties,
    RowProperties,
    RunProperties,
    SectionProperties,
    ShadingProperties,
    SpacingProperties,
    TableProperties,
    TabStop,
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
NS_V = "urn:schemas-microsoft-com:vml"
NS_O = "urn:schemas-microsoft-com:office:office"
NS_W10 = "urn:schemas-microsoft-com:office:word"

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


def _emu_to_pt(val: str | int | float | None, default: float = 0.0) -> float:
    """Convert EMUs (English Metric Units, 1 pt = 12700 EMUs) to points."""
    if val is None or val == "":
        return default
    try:
        return float(val) / 12700.0
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
        self._parse_numbering()
        self._parse_settings()
        self._parse_fonts()
        self._parse_body()
        self._parse_headers_footers()
        self._parse_footnotes()
        self._parse_endnotes()
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

            def_elem = style_elem.find(f"{{{NS_W}}}default")
            is_default = _bool_val(def_elem, False) or _get_attr(style_elem, "default") == "1"

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

    def _parse_numbering(self) -> None:
        """Parse word/numbering.xml into doc.numbering."""
        num_path = self._rel_target("numbering") or "word/numbering.xml"
        if not self.pkg.has_part(num_path):
            self.doc.numbering = {"abs": {}, "nums": {}}
            return

        try:
            root = ET.fromstring(self.pkg.read_part(num_path))
        except Exception:
            self.doc.numbering = {"abs": {}, "nums": {}}
            return

        abs_map: dict[str, dict[str, Any]] = {}
        nums_map: dict[str, dict[str, Any]] = {}

        # 1. Parse abstractNum elements
        for an in root.findall(f"{{{NS_W}}}abstractNum"):
            an_id = _get_attr(an, "abstractNumId")
            if not an_id:
                continue

            multi_elem = an.find(f"{{{NS_W}}}multiLevelType")
            multi = (
                _get_attr(multi_elem, "val", "multilevel")
                if multi_elem is not None
                else "multilevel"
            )

            style_link_elem = an.find(f"{{{NS_W}}}numStyleLink")
            style_link = _get_attr(style_link_elem, "val") if style_link_elem is not None else None

            name_elem = an.find(f"{{{NS_W}}}name")
            name = _get_attr(name_elem, "val", "") if name_elem is not None else ""

            levels: list[dict[str, Any]] = [{} for _ in range(9)]
            for lv in an.findall(f"{{{NS_W}}}lvl"):
                ilvl_str = _get_attr(lv, "ilvl", "0")
                try:
                    ilvl = int(ilvl_str)
                except ValueError:
                    continue
                if not (0 <= ilvl < 9):
                    continue

                start_elem = lv.find(f"{{{NS_W}}}start")
                start_val = (
                    int(_get_attr(start_elem, "val", "1") or "1") if start_elem is not None else 1
                )

                fmt_elem = lv.find(f"{{{NS_W}}}numFmt")
                fmt_val = (
                    _get_attr(fmt_elem, "val", "decimal") if fmt_elem is not None else "decimal"
                )

                text_elem = lv.find(f"{{{NS_W}}}lvlText")
                text_val = (
                    _get_attr(text_elem, "val", f"%{ilvl + 1}.")
                    if text_elem is not None
                    else f"%{ilvl + 1}."
                )

                jc_elem = lv.find(f"{{{NS_W}}}lvlJc")
                jc_val = _get_attr(jc_elem, "val", "left") if jc_elem is not None else "left"

                suff_elem = lv.find(f"{{{NS_W}}}suff")
                suff_val = _get_attr(suff_elem, "val", "tab") if suff_elem is not None else "tab"

                is_lgl = lv.find(f"{{{NS_W}}}isLgl") is not None

                restart_elem = lv.find(f"{{{NS_W}}}lvlRestart")
                restart = (
                    int(_get_attr(restart_elem, "val", "0") or "0") - 1
                    if restart_elem is not None
                    else None
                )

                p_style_elem = lv.find(f"{{{NS_W}}}pStyle")
                p_style = _get_attr(p_style_elem, "val") if p_style_elem is not None else None

                # Indents & Spacing in pPr
                ind_dict = {"l": 0.0, "fl": 0.0}
                p_pr_elem = lv.find(f"{{{NS_W}}}pPr")
                tab_pos = None
                if p_pr_elem is not None:
                    ind_elem = p_pr_elem.find(f"{{{NS_W}}}ind")
                    if ind_elem is not None:
                        ind_dict["l"] = _twips_to_pt(
                            _get_attr(ind_elem, "left") or _get_attr(ind_elem, "start")
                        )
                        if _get_attr(ind_elem, "hanging") is not None:
                            ind_dict["fl"] = -_twips_to_pt(_get_attr(ind_elem, "hanging"))
                        elif _get_attr(ind_elem, "firstLine") is not None:
                            ind_dict["fl"] = _twips_to_pt(_get_attr(ind_elem, "firstLine"))

                    tabs_elem = p_pr_elem.find(f"{{{NS_W}}}tabs")
                    if tabs_elem is not None:
                        tab_elem = tabs_elem.find(f"{{{NS_W}}}tab")
                        if tab_elem is not None:
                            tab_pos = _twips_to_pt(_get_attr(tab_elem, "pos"))

                # Run properties
                r_pr_elem = lv.find(f"{{{NS_W}}}rPr")
                r_pr = self._parse_r_pr(r_pr_elem) if r_pr_elem is not None else RunProperties()

                levels[ilvl] = {
                    "ilvl": ilvl,
                    "start": start_val,
                    "fmt": fmt_val,
                    "text": text_val,
                    "jc": jc_val,
                    "suff": suff_val,
                    "ind": ind_dict,
                    "tab_pos": tab_pos,
                    "is_lgl": is_lgl,
                    "restart": restart,
                    "p_style": p_style,
                    "r_pr": r_pr,
                }

            # Fill missing levels up to 9
            for i in range(9):
                if not levels[i]:
                    levels[i] = {
                        "ilvl": i,
                        "start": 1,
                        "fmt": "decimal",
                        "text": f"%{i + 1}.",
                        "jc": "left",
                        "suff": "tab",
                        "ind": {"l": 0.0, "fl": 0.0},
                        "tab_pos": None,
                        "is_lgl": False,
                        "restart": None,
                        "p_style": None,
                        "r_pr": RunProperties(),
                    }

            abs_map[an_id] = {
                "id": an_id,
                "multi": multi,
                "name": name,
                "style_link": style_link,
                "levels": levels,
            }

        # 2. Parse num elements
        for n in root.findall(f"{{{NS_W}}}num"):
            num_id = _get_attr(n, "numId")
            if not num_id:
                continue

            abs_ref_elem = n.find(f"{{{NS_W}}}abstractNumId")
            abs_ref = _get_attr(abs_ref_elem, "val", "") if abs_ref_elem is not None else ""

            ov_map: dict[int, dict[str, Any]] = {}
            for ov in n.findall(f"{{{NS_W}}}lvlOverride"):
                ov_ilvl_str = _get_attr(ov, "ilvl", "0")
                try:
                    ov_ilvl = int(ov_ilvl_str)
                except ValueError:
                    continue

                ov_dict: dict[str, Any] = {}
                start_ov = ov.find(f"{{{NS_W}}}startOverride")
                if start_ov is not None:
                    ov_dict["start"] = int(_get_attr(start_ov, "val", "1") or "1")

                lvl_ov = ov.find(f"{{{NS_W}}}lvl")
                if lvl_ov is not None:
                    fmt_elem = lvl_ov.find(f"{{{NS_W}}}numFmt")
                    if fmt_elem is not None:
                        ov_dict["fmt"] = _get_attr(fmt_elem, "val", "decimal")
                    text_elem = lvl_ov.find(f"{{{NS_W}}}lvlText")
                    if text_elem is not None:
                        ov_dict["text"] = _get_attr(text_elem, "val", f"%{ov_ilvl + 1}.")
                    start_elem = lvl_ov.find(f"{{{NS_W}}}start")
                    if start_elem is not None:
                        ov_dict["start"] = int(_get_attr(start_elem, "val", "1") or "1")

                ov_map[ov_ilvl] = ov_dict

            nums_map[num_id] = {
                "id": num_id,
                "abs": abs_ref,
                "ov": ov_map,
            }

        self.doc.numbering = {"abs": abs_map, "nums": nums_map}

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
                elif c_tag == "drawing":
                    self._parse_drawing(child, runs, r_pr)
                elif c_tag == "pict":
                    self._parse_vml_pict(child, runs, r_pr)
                elif c_tag == "footnoteReference":
                    n_id = _get_attr(child, "id", "0") or "0"
                    runs.append(NoteRefItem(kind="fn", note_id=n_id, r_pr=r_pr))
                elif c_tag == "endnoteReference":
                    n_id = _get_attr(child, "id", "0") or "0"
                    runs.append(NoteRefItem(kind="en", note_id=n_id, r_pr=r_pr))
                elif c_tag == "bookmarkStart":
                    name = _get_attr(child, "name", "")
                    b_id = int(_get_attr(child, "id", "0") or "0")
                    runs.append(BookmarkStartItem(name=name, bookmark_id=b_id))
                    if name:
                        self.doc.props.setdefault("bookmarks", {})[name] = b_id
                elif c_tag == "bookmarkEnd":
                    b_id = int(_get_attr(child, "id", "0") or "0")
                    runs.append(BookmarkEndItem(bookmark_id=b_id))
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

        elif tag == "drawing":
            self._parse_drawing(elem, runs, inherited_r_pr)

        elif tag == "pict":
            self._parse_vml_pict(elem, runs, inherited_r_pr)

        elif tag == "footnoteReference":
            n_id = _get_attr(elem, "id", "0") or "0"
            runs.append(NoteRefItem(kind="fn", note_id=n_id, r_pr=inherited_r_pr))

        elif tag == "endnoteReference":
            n_id = _get_attr(elem, "id", "0") or "0"
            runs.append(NoteRefItem(kind="en", note_id=n_id, r_pr=inherited_r_pr))

        elif tag == "bookmarkStart":
            name = _get_attr(elem, "name", "")
            b_id = int(_get_attr(elem, "id", "0") or "0")
            runs.append(BookmarkStartItem(name=name, bookmark_id=b_id))
            if name:
                self.doc.props.setdefault("bookmarks", {})[name] = b_id

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

        elif tag in ("oMath", "oMathPara"):
            runs.append(parse_omml(elem))

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
                b_elem = child.find(f"{{{NS_W}}}beforeAutospacing")
                a_elem = child.find(f"{{{NS_W}}}afterAutospacing")
                b_auto = _bool_val(b_elem, False) or _get_attr(child, "beforeAutospacing") == "1"
                a_auto = _bool_val(a_elem, False) or _get_attr(child, "afterAutospacing") == "1"
                p_pr.sp = SpacingProperties(
                    before=b,
                    after=a,
                    line=line,
                    line_rule=rule,
                    before_auto=b_auto,
                    after_auto=a_auto,
                )
            elif tag == "ind":
                ind_left = _twips_to_pt(_get_attr(child, "left") or _get_attr(child, "start"))
                ind_right = _twips_to_pt(_get_attr(child, "right") or _get_attr(child, "end"))
                fl = 0.0
                if _get_attr(child, "hanging") is not None:
                    fl = -_twips_to_pt(_get_attr(child, "hanging"))
                elif _get_attr(child, "firstLine") is not None:
                    fl = _twips_to_pt(_get_attr(child, "firstLine"))
                p_pr.ind = IndentProperties(left=ind_left, right=ind_right, first_line=fl)
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
                ilvl_str = _get_attr(ilvl_elem if ilvl_elem is not None else child, "val", "0")
                ilvl = int(ilvl_str or "0")
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

            # Table Cell Margins (w:tblCellMar)
            tbl_cell_mar_elem = tbl_pr_elem.find(f"{{{NS_W}}}tblCellMar")
            if tbl_cell_mar_elem is not None:
                cell_mar: dict[str, float] = {}
                for side, tag_name in (
                    ("t", "top"),
                    ("b", "bottom"),
                    ("l", "left"),
                    ("r", "right"),
                ):
                    mar_side = tbl_cell_mar_elem.find(f"{{{NS_W}}}{tag_name}")
                    if mar_side is not None:
                        cell_mar[side] = _twips_to_pt(_get_attr(mar_side, "w", "0"))
                if cell_mar:
                    tbl_pr.cell_mar = cell_mar

            # Table Borders (w:tblBorders)
            tbl_bds_elem = tbl_pr_elem.find(f"{{{NS_W}}}tblBorders")
            if tbl_bds_elem is not None:
                tbl_bds: dict[str, BorderProperties] = {}
                for b_tag in ("top", "left", "bottom", "right", "insideH", "insideV"):
                    b_elem = tbl_bds_elem.find(f"{{{NS_W}}}{b_tag}")
                    if b_elem is not None:
                        val = _get_attr(b_elem, "val", "none")
                        sz = _eighths_to_pt(_get_attr(b_elem, "sz", "4"))
                        color = _get_attr(b_elem, "color", "auto")
                        tbl_bds[b_tag] = BorderProperties(val=val, sz=sz, color=color)
                tbl_pr.borders = tbl_bds

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
                        vm_val = _get_attr(vm_elem, "val")
                        tc_pr.v_merge = vm_val if vm_val else "continue"
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
                    # Cell Margins (w:tcMar)
                    tc_mar_elem = tc_pr_elem.find(f"{{{NS_W}}}tcMar")
                    if tc_mar_elem is not None:
                        tc_mar: dict[str, float] = {}
                        for side, tag_name in (
                            ("t", "top"),
                            ("b", "bottom"),
                            ("l", "left"),
                            ("r", "right"),
                        ):
                            mar_side = tc_mar_elem.find(f"{{{NS_W}}}{tag_name}")
                            if mar_side is not None:
                                tc_mar[side] = _twips_to_pt(_get_attr(mar_side, "w", "0"))
                        tc_pr.tc_mar = tc_mar

                    # Cell Borders (w:tcBorders)
                    tc_bds_elem = tc_pr_elem.find(f"{{{NS_W}}}tcBorders")
                    if tc_bds_elem is not None:
                        tc_bds: dict[str, BorderProperties] = {}
                        for b_tag in ("top", "left", "bottom", "right"):
                            b_elem = tc_bds_elem.find(f"{{{NS_W}}}{b_tag}")
                            if b_elem is not None:
                                val = _get_attr(b_elem, "val", "none")
                                sz = _eighths_to_pt(_get_attr(b_elem, "sz", "4"))
                                color = _get_attr(b_elem, "color", "auto")
                                tc_bds[b_tag] = BorderProperties(val=val, sz=sz, color=color)
                        tc_pr.borders = tc_bds
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

        # Document grid
        doc_grid_elem = sect_elem.find(f"{{{NS_W}}}docGrid")
        if doc_grid_elem is not None:
            dg_type = _get_attr(doc_grid_elem, "type", "lines")
            dg_pitch = _twips_to_pt(_get_attr(doc_grid_elem, "linePitch"), 15.6)
            dg_char = _twips_to_pt(_get_attr(doc_grid_elem, "charSpace"), 0.0)
            sect.doc_grid = DocGridProperties(type=dg_type, line_pitch=dg_pitch, char_space=dg_char)
        else:
            sect.doc_grid = DocGridProperties(type="none", line_pitch=15.6, char_space=0.0)

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

    def _parse_footnotes(self) -> None:
        """Parse word/footnotes.xml into doc.fn."""
        fn_path = self._rel_target("footnotes") or "word/footnotes.xml"
        if not self.pkg.has_part(fn_path):
            return

        try:
            root = ET.fromstring(self.pkg.read_part(fn_path))
            for fn in root:
                if _local_tag(fn) != "footnote":
                    continue
                fn_type = _get_attr(fn, "type", "normal")
                if fn_type in ("separator", "continuationSeparator", "continuationNotice"):
                    continue
                fn_id = _get_attr(fn, "id")
                if not fn_id:
                    continue
                blocks: list[Paragraph | Table] = []
                for child in fn:
                    c_tag = _local_tag(child)
                    if c_tag == "p":
                        blocks.append(self._parse_paragraph(child))
                    elif c_tag == "tbl":
                        blocks.append(self._parse_table(child))
                if not blocks:
                    blocks.append(Paragraph())
                self.doc.fn[fn_id] = Story(kind="footnote", blocks=blocks)
        except Exception:
            pass

    def _parse_endnotes(self) -> None:
        """Parse word/endnotes.xml into doc.en."""
        en_path = self._rel_target("endnotes") or "word/endnotes.xml"
        if not self.pkg.has_part(en_path):
            return

        try:
            root = ET.fromstring(self.pkg.read_part(en_path))
            for en in root:
                if _local_tag(en) != "endnote":
                    continue
                en_type = _get_attr(en, "type", "normal")
                if en_type in ("separator", "continuationSeparator", "continuationNotice"):
                    continue
                en_id = _get_attr(en, "id")
                if not en_id:
                    continue
                blocks: list[Paragraph | Table] = []
                for child in en:
                    c_tag = _local_tag(child)
                    if c_tag == "p":
                        blocks.append(self._parse_paragraph(child))
                    elif c_tag == "tbl":
                        blocks.append(self._parse_table(child))
                if not blocks:
                    blocks.append(Paragraph())
                self.doc.en[en_id] = Story(kind="endnote", blocks=blocks)
        except Exception:
            pass

    def _parse_drawing(
        self,
        elem: ET.Element,
        runs: list[RunItem],
        r_pr: RunProperties | None = None,
    ) -> None:
        """Parse <w:drawing> element containing <wp:inline> or <wp:anchor>."""
        container = None
        is_anchor = False
        for c in elem:
            c_tag = _local_tag(c)
            if c_tag == "inline":
                container = c
                is_anchor = False
                break
            elif c_tag == "anchor":
                container = c
                is_anchor = True
                break

        if container is None:
            return

        width_pt = 72.0
        height_pt = 72.0
        for c in container:
            if _local_tag(c) == "extent":
                width_pt = _emu_to_pt(_get_attr(c, "cx"), 72.0)
                height_pt = _emu_to_pt(_get_attr(c, "cy"), 72.0)
                break

        name = ""
        alt_text = ""
        doc_id = 0
        for c in container:
            if _local_tag(c) == "docPr":
                name = _get_attr(c, "name", "")
                alt_text = _get_attr(c, "descr", "") or _get_attr(c, "title", "")
                try:
                    doc_id = int(_get_attr(c, "id", "0") or "0")
                except ValueError:
                    doc_id = 0
                break

        float_pr = None
        if is_anchor:
            float_pr = self._parse_float_properties(container)

        image_part = ""
        crop = Crop()
        rotation = 0.0

        for gd in container.iter():
            tag = _local_tag(gd)
            if tag == "blip":
                r_id = (
                    _get_attr(gd, "embed")
                    or _get_attr(gd, "link")
                    or _get_attr(gd, "r:embed")
                    or _get_attr(gd, "r:link")
                )
                if r_id and r_id in self.rels:
                    rel = self.rels[r_id]
                    t = rel.target.lstrip("/")
                    if not t.startswith("word/") and not t.startswith("docProps/"):
                        t = f"word/{t}"
                    image_part = t
            elif tag == "srcRect":
                crop_l = float(_get_attr(gd, "l", "0") or "0") / 100000.0
                crop_t = float(_get_attr(gd, "t", "0") or "0") / 100000.0
                crop_r = float(_get_attr(gd, "r", "0") or "0") / 100000.0
                crop_b = float(_get_attr(gd, "b", "0") or "0") / 100000.0
                crop = Crop(left=crop_l, top=crop_t, right=crop_r, bottom=crop_b)
            elif tag == "xfrm":
                rot_str = _get_attr(gd, "rot")
                if rot_str:
                    try:
                        rotation = float(rot_str) / 60000.0
                    except ValueError:
                        rotation = 0.0

        pic = PictureItem(
            id=doc_id,
            name=name,
            width=width_pt,
            height=height_pt,
            rotation=rotation,
            float_pr=float_pr,
            r_pr=r_pr or RunProperties(),
            image_part=image_part,
            alt_text=alt_text,
            crop=crop,
        )
        runs.append(pic)

    def _parse_float_properties(self, anchor: ET.Element) -> FloatProperties:
        """Parse floating layout parameters from <wp:anchor>."""
        pos_h = PositionH(rel="column", offset=0.0)
        pos_v = PositionV(rel="paragraph", offset=0.0)
        dist = WrapDist(top=0.0, bottom=0.0, left=9.0, right=9.0)
        wrap_mode = WrapMode.SQUARE
        wrap_side = WrapSide.BOTH
        behind = (
            _bool_val(anchor.find(f"{{{NS_WP}}}behindDoc"), False)
            or _get_attr(anchor, "behindDoc") == "1"
        )

        dist_t = _get_attr(anchor, "distT")
        if dist_t is not None:
            dist.top = _emu_to_pt(dist_t)
        dist_b = _get_attr(anchor, "distB")
        if dist_b is not None:
            dist.bottom = _emu_to_pt(dist_b)
        dist_l = _get_attr(anchor, "distL")
        if dist_l is not None:
            dist.left = _emu_to_pt(dist_l)
        dist_r = _get_attr(anchor, "distR")
        if dist_r is not None:
            dist.right = _emu_to_pt(dist_r)

        z_index = 0
        rel_h = _get_attr(anchor, "relativeHeight")
        if rel_h is not None:
            try:
                z_index = int(rel_h)
            except ValueError:
                pass

        for c in anchor:
            c_tag = _local_tag(c)
            if c_tag == "positionH":
                pos_h.rel = _get_attr(c, "relativeFrom", "column") or "column"
                for sub in c:
                    sub_tag = _local_tag(sub)
                    if sub_tag == "align" and sub.text:
                        pos_h.align = sub.text.strip()
                    elif sub_tag == "posOffset" and sub.text:
                        pos_h.offset = _emu_to_pt(sub.text.strip())
            elif c_tag == "positionV":
                pos_v.rel = _get_attr(c, "relativeFrom", "paragraph") or "paragraph"
                for sub in c:
                    sub_tag = _local_tag(sub)
                    if sub_tag == "align" and sub.text:
                        pos_v.align = sub.text.strip()
                    elif sub_tag == "posOffset" and sub.text:
                        pos_v.offset = _emu_to_pt(sub.text.strip())
            elif c_tag == "wrapSquare":
                wrap_mode = WrapMode.SQUARE
                ws_val = _get_attr(c, "wrapText", "bothSides")
                if ws_val == "left":
                    wrap_side = WrapSide.LEFT
                elif ws_val == "right":
                    wrap_side = WrapSide.RIGHT
                elif ws_val == "largest":
                    wrap_side = WrapSide.LARGEST
                else:
                    wrap_side = WrapSide.BOTH
            elif c_tag == "wrapTight":
                wrap_mode = WrapMode.TIGHT
            elif c_tag == "wrapThrough":
                wrap_mode = WrapMode.TIGHT
            elif c_tag == "wrapTopAndBottom":
                wrap_mode = WrapMode.TOP_BOTTOM
            elif c_tag == "wrapNone":
                wrap_mode = WrapMode.BEHIND if behind else WrapMode.IN_FRONT

        return FloatProperties(
            wrap=wrap_mode,
            side=wrap_side,
            dist=dist,
            pos_h=pos_h,
            pos_v=pos_v,
            z_index=z_index,
            behind=behind,
        )

    def _parse_vml_pict(
        self,
        elem: ET.Element,
        runs: list[RunItem],
        r_pr: RunProperties | None = None,
    ) -> None:
        """Parse legacy VML <w:pict> image and shape elements."""
        for shape in elem.iter():
            tag = _local_tag(shape)
            if tag in ("shape", "rect"):
                style_str = _get_attr(shape, "style", "")
                props = self._parse_vml_style(style_str)

                image_part = ""
                alt_text = ""
                for child in shape.iter():
                    c_tag = _local_tag(child)
                    if c_tag == "imagedata":
                        r_id = (
                            _get_attr(child, "id")
                            or _get_attr(child, "href")
                            or _get_attr(child, "r:id")
                            or _get_attr(child, "r:href")
                        )
                        if r_id and r_id in self.rels:
                            rel = self.rels[r_id]
                            t = rel.target.lstrip("/")
                            if not t.startswith("word/") and not t.startswith("docProps/"):
                                t = f"word/{t}"
                            image_part = t
                        alt_text = _get_attr(child, "title", "") or _get_attr(shape, "alt", "")

                float_pr = None
                if (
                    props.get("position") == "absolute"
                    or "margin-left" in props
                    or "margin-top" in props
                ):
                    pos_h = PositionH(rel="column", offset=props.get("margin-left", 0.0))
                    pos_v = PositionV(rel="paragraph", offset=props.get("margin-top", 0.0))
                    z_index = int(props.get("z-index", 0))
                    float_pr = FloatProperties(
                        wrap=WrapMode.SQUARE,
                        pos_h=pos_h,
                        pos_v=pos_v,
                        z_index=z_index,
                    )

                pic = PictureItem(
                    width=props.get("width", 72.0),
                    height=props.get("height", 72.0),
                    float_pr=float_pr,
                    r_pr=r_pr or RunProperties(),
                    image_part=image_part,
                    alt_text=alt_text,
                )
                runs.append(pic)

    def _parse_vml_style(self, style_str: str) -> dict[str, Any]:
        """Parse CSS-like style string from VML elements into numerical point values."""
        res: dict[str, Any] = {}
        for part in style_str.split(";"):
            if ":" not in part:
                continue
            k, v = part.split(":", 1)
            k = k.strip().lower()
            v = v.strip()
            if v.endswith("pt"):
                try:
                    res[k] = float(v[:-2])
                except ValueError:
                    pass
            elif v.endswith("in"):
                try:
                    res[k] = float(v[:-2]) * 72.0
                except ValueError:
                    pass
            elif v.endswith("px"):
                try:
                    res[k] = float(v[:-2]) * 0.75
                except ValueError:
                    pass
            else:
                try:
                    res[k] = float(v)
                except ValueError:
                    res[k] = v
        return res


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
