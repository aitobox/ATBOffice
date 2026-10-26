"""ECMA-376 WordprocessingML writer for DOCX and DOCM files."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

from atboffice.modules.writer.models.document import (
    BookmarkEndItem,
    BookmarkStartItem,
    BreakItem,
    CommentRangeEnd,
    CommentRangeStart,
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    RunItem,
    Story,
    SymbolItem,
    TabItem,
    Table,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    ParagraphProperties,
    RunProperties,
    SectionProperties,
    pt_to_dxa,
)
from atboffice.modules.writer.models.styles import Style, builtin_styles
from atboffice.modules.writer.models.omml import OfficeMathItem, serialize_omml
from atboffice.vfs.opc import PackageWriter, Relationship, SourcePackage
from atboffice.vfs.order import enforce_schema_order
from atboffice.vfs.xml_tree import serialize_xml

# Standard Namespaces
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
NS_XML = "http://www.w3.org/XML/1998/namespace"

CT_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
CT_DOCM = "application/vnd.ms-word.document.macroEnabled.main+xml"
CT_STYLES = "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"
CT_SETTINGS = "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"
CT_FONTS = "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"
CT_HEADER = "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"
CT_FOOTER = "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"
CT_RELS = "application/vnd.openxmlformats-package.relationships+xml"
CT_XML = "application/xml"

REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
REL_STYLES = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
REL_SETTINGS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings"
REL_FONTS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable"
REL_HEADER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"
REL_FOOTER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer"
REL_HYPERLINK = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"

# Register standard prefixes with ElementTree
ET.register_namespace("w", NS_W)
ET.register_namespace("r", NS_R)
ET.register_namespace("m", NS_M)
ET.register_namespace("wp", NS_WP)
ET.register_namespace("a", NS_A)
ET.register_namespace("pic", NS_PIC)


def _w(tag: str) -> str:
    """Helper to return Clark notation for WordprocessingML tag."""
    return f"{{{NS_W}}}{tag}"


def _r(tag: str) -> str:
    """Helper to return Clark notation for Relationship tag."""
    return f"{{{NS_R}}}{tag}"


def _clean_hex(color_val: str | None) -> str | None:
    """Convert '#RRGGBB' to 'RRGGBB' or preserve 'auto'."""
    if not color_val or color_val.lower() == "auto":
        return "auto" if color_val else None
    return color_val.lstrip("#").upper()


class DocxWriter:
    """Serializes Quire Document into ECMA-376 compliant DOCX or DOCM packages."""

    def __init__(self, doc: Document) -> None:
        self.doc = doc
        self.doc_format = getattr(doc, "_doc_format", "docx")
        self.source_pkg: SourcePackage | None = getattr(doc, "_source_pkg", None)
        self.rels: list[Relationship] = []
        self._next_r_id = 1

    def _gen_r_id(self) -> str:
        r_id = f"rId{self._next_r_id}"
        self._next_r_id += 1
        return r_id

    def write(self, target: str | Path | io.BytesIO | None = None) -> bytes:
        """Serialize Document and write to file path, BytesIO, or return bytes."""
        if self.source_pkg is not None:
            data = self._write_incremental()
        else:
            data = self._write_new()

        if target is not None:
            if isinstance(target, (str, Path)):
                Path(target).write_bytes(data)
            elif hasattr(target, "write"):
                target.write(data)
        return data

    def _write_incremental(self) -> bytes:
        """Losslessly update existing package carrying untouched parts byte-for-byte."""
        assert self.source_pkg is not None
        writer = PackageWriter(self.source_pkg)

        # Build document and relationships
        doc_xml, doc_rels, hf_id_map = self._build_document_and_rels()

        main_path = "word/document.xml"
        main_rels_path = "word/_rels/document.xml.rels"

        ct = CT_DOCM if self.doc_format == "docm" else CT_DOCX
        writer.replace_part(main_path, doc_xml, ct)
        writer.replace_part(main_rels_path, doc_rels, CT_RELS)

        # Write headers/footers if present in doc.hf
        for old_id, story in self.doc.hf.items():
            new_id = hf_id_map.get(old_id)
            rel = next((r for r in self.rels if r.id == new_id), None)
            if rel:
                part_path = f"word/{rel.target.lstrip('word/')}"
                hf_xml = self._build_hf_xml(story)
                part_ct = CT_HEADER if rel.type == REL_HEADER else CT_FOOTER
                if self.source_pkg.has_part(part_path):
                    writer.replace_part(part_path, hf_xml, part_ct)
                else:
                    writer.add_part(part_path, hf_xml, part_ct)

        # Update styles.xml
        styles_xml = self._build_styles_xml()
        writer.replace_part("word/styles.xml", styles_xml, CT_STYLES)

        return writer.to_bytes()

    def _write_new(self) -> bytes:
        """Create a fresh OPC package according to ECMA-376."""
        writer = PackageWriter()

        # Build document and relationships
        doc_xml, doc_rels, hf_id_map = self._build_document_and_rels()

        main_ct = CT_DOCM if self.doc_format == "docm" else CT_DOCX
        writer.add_part("word/document.xml", doc_xml, main_ct)
        writer.add_part("word/_rels/document.xml.rels", doc_rels, CT_RELS)

        # Add headers / footers
        for old_id, story in self.doc.hf.items():
            new_id = hf_id_map.get(old_id)
            rel = next((r for r in self.rels if r.id == new_id), None)
            if rel:
                part_path = f"word/{rel.target.lstrip('word/')}"
                hf_xml = self._build_hf_xml(story)
                part_ct = CT_HEADER if rel.type == REL_HEADER else CT_FOOTER
                writer.add_part(part_path, hf_xml, part_ct)

        # Add styles, settings, fontTable
        writer.add_part("word/styles.xml", self._build_styles_xml(), CT_STYLES)
        writer.add_part("word/settings.xml", self._build_settings_xml(), CT_SETTINGS)
        writer.add_part("word/fontTable.xml", self._build_fonts_xml(), CT_FONTS)

        # Add root _rels/.rels
        root_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            f'  <Relationship Id="rId1" Type="{REL_DOC}" Target="word/document.xml"/>\n'
            "</Relationships>"
        ).encode()
        writer.add_part("_rels/.rels", root_rels_xml, CT_RELS)

        return writer.to_bytes()

    def _build_document_and_rels(self) -> tuple[bytes, bytes, dict[str, str]]:
        """Build <w:document> XML and word/_rels/document.xml.rels XML."""
        self.rels = []
        self._next_r_id = 1

        # Add standard relationships
        r_styles = self._gen_r_id()
        self.rels.append(Relationship(id=r_styles, type=REL_STYLES, target="styles.xml"))

        r_settings = self._gen_r_id()
        self.rels.append(Relationship(id=r_settings, type=REL_SETTINGS, target="settings.xml"))

        r_fonts = self._gen_r_id()
        self.rels.append(Relationship(id=r_fonts, type=REL_FONTS, target="fontTable.xml"))

        # Map header/footer relationships
        hf_id_map: dict[str, str] = {}
        hf_idx = 1
        for old_id, story in self.doc.hf.items():
            new_id = self._gen_r_id()
            is_hdr = story.kind == "header"
            rel_type = REL_HEADER if is_hdr else REL_FOOTER
            prefix = "header" if is_hdr else "footer"
            target_name = f"{prefix}{hf_idx}.xml"
            hf_idx += 1
            self.rels.append(Relationship(id=new_id, type=rel_type, target=target_name))
            hf_id_map[old_id] = new_id

        # Build Document XML
        root = ET.Element(_w("document"))
        body = ET.SubElement(root, _w("body"))

        # Serialize main story blocks
        for block in self.doc.main.blocks:
            if isinstance(block, Paragraph):
                p_elem = self._serialize_paragraph(block, hf_id_map)
                body.append(p_elem)
            elif isinstance(block, Table):
                tbl_elem = self._serialize_table(block, hf_id_map)
                body.append(tbl_elem)

        # Trailing section properties
        sect_elem = self._serialize_sect_pr(self.doc.sect, hf_id_map)
        body.append(sect_elem)

        doc_xml = serialize_xml(root, standalone=True)

        # Build document.xml.rels
        rels_elem = ET.Element(
            "{http://schemas.openxmlformats.org/package/2006/relationships}Relationships"
        )
        for r in self.rels:
            r_elem = ET.SubElement(rels_elem, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
            r_elem.set("Id", r.id)
            r_elem.set("Type", r.type)
            r_elem.set("Target", r.target)
            if r.target_mode != "Internal":
                r_elem.set("TargetMode", r.target_mode)

        rels_xml = serialize_xml(rels_elem, standalone=True)
        return doc_xml, rels_xml, hf_id_map

    def _serialize_paragraph(
        self, p: Paragraph, hf_id_map: dict[str, str] | None = None
    ) -> ET.Element:
        """Serialize a Paragraph into <w:p> with schema-ordered properties."""
        p_elem = ET.Element(_w("p"))

        # Paragraph Properties
        p_pr_elem = ET.Element(_w("pPr"))
        self._populate_p_pr(p_pr_elem, p.p_pr)

        if p.sect is not None:
            sect_elem = self._serialize_sect_pr(p.sect, hf_id_map)
            p_pr_elem.append(sect_elem)

        # Enforce strict schema ordering on pPr
        if len(p_pr_elem) > 0:
            enforce_schema_order(p_pr_elem, "wordprocessingml_ppr")
            p_elem.append(p_pr_elem)

        # Runs & Inline Items
        for item in p.runs:
            self._serialize_run_item(p_elem, item)

        return p_elem

    def _populate_p_pr(self, p_pr_elem: ET.Element, p_pr: ParagraphProperties) -> None:
        """Add child elements to <w:pPr>."""
        if p_pr.style and p_pr.style != "Normal":
            p_style = ET.SubElement(p_pr_elem, _w("pStyle"))
            p_style.set(_w("val"), p_pr.style)

        if p_pr.keep_next:
            ET.SubElement(p_pr_elem, _w("keepNext"))

        if p_pr.keep_lines:
            ET.SubElement(p_pr_elem, _w("keepLines"))

        if p_pr.page_break_before:
            ET.SubElement(p_pr_elem, _w("pageBreakBefore"))

        if not p_pr.widow_control:
            widow = ET.SubElement(p_pr_elem, _w("widowControl"))
            widow.set(_w("val"), "0")

        if p_pr.num:
            num_pr = ET.SubElement(p_pr_elem, _w("numPr"))
            ilvl = ET.SubElement(num_pr, _w("ilvl"))
            ilvl.set(_w("val"), str(p_pr.num.lvl))
            num_id = ET.SubElement(num_pr, _w("numId"))
            num_id.set(_w("val"), str(p_pr.num.id))

        if p_pr.tabs:
            tabs_elem = ET.SubElement(p_pr_elem, _w("tabs"))
            for t in sorted(p_pr.tabs, key=lambda x: x.pos):
                tab = ET.SubElement(tabs_elem, _w("tab"))
                tab.set(_w("val"), t.align)
                tab.set(_w("pos"), str(pt_to_dxa(t.pos)))
                if t.leader and t.leader != "none":
                    tab.set(_w("leader"), t.leader)

        # Spacing
        sp = p_pr.sp
        if sp.before or sp.after or sp.line != 1.0 or sp.line_rule != "auto":
            sp_elem = ET.SubElement(p_pr_elem, _w("spacing"))
            if sp.before:
                sp_elem.set(_w("before"), str(pt_to_dxa(sp.before)))
            if sp.after:
                sp_elem.set(_w("after"), str(pt_to_dxa(sp.after)))
            if sp.before_auto:
                sp_elem.set(_w("beforeAutospacing"), "1")
            if sp.after_auto:
                sp_elem.set(_w("afterAutospacing"), "1")
            if sp.line != 1.0 or sp.line_rule != "auto":
                line_val = round(sp.line * 240) if sp.line_rule == "auto" else pt_to_dxa(sp.line)
                sp_elem.set(_w("line"), str(line_val))
                sp_elem.set(_w("lineRule"), sp.line_rule)

        # Indent
        ind = p_pr.ind
        if ind.left or ind.right or ind.first_line:
            ind_elem = ET.SubElement(p_pr_elem, _w("ind"))
            if ind.left:
                ind_elem.set(_w("left"), str(pt_to_dxa(ind.left)))
            if ind.right:
                ind_elem.set(_w("right"), str(pt_to_dxa(ind.right)))
            if ind.first_line > 0:
                ind_elem.set(_w("firstLine"), str(pt_to_dxa(ind.first_line)))
            elif ind.first_line < 0:
                ind_elem.set(_w("hanging"), str(pt_to_dxa(-ind.first_line)))

        # Alignment
        if p_pr.jc and p_pr.jc != "left":
            jc_elem = ET.SubElement(p_pr_elem, _w("jc"))
            jc_elem.set(_w("val"), p_pr.jc)

        # Outline Level
        if p_pr.outline_level is not None:
            lvl_elem = ET.SubElement(p_pr_elem, _w("outlineLvl"))
            lvl_elem.set(_w("val"), str(p_pr.outline_level))

    def _serialize_run_item(self, p_elem: ET.Element, item: RunItem) -> None:
        """Serialize a RunItem into corresponding XML elements under <w:p>."""
        if isinstance(item, OfficeMathItem):
            math_elem = serialize_omml(item)
            p_elem.append(math_elem)
            return

        if isinstance(item, BookmarkStartItem):
            bm_s = ET.SubElement(p_elem, _w("bookmarkStart"))
            bm_s.set(_w("id"), str(item.bookmark_id))
            bm_s.set(_w("name"), item.name)
            return

        if isinstance(item, BookmarkEndItem):
            bm_e = ET.SubElement(p_elem, _w("bookmarkEnd"))
            bm_e.set(_w("id"), str(item.bookmark_id))
            return

        if isinstance(item, CommentRangeStart):
            cm_s = ET.SubElement(p_elem, _w("commentRangeStart"))
            cm_s.set(_w("id"), str(item.comment_id))
            return

        if isinstance(item, CommentRangeEnd):
            cm_e = ET.SubElement(p_elem, _w("commentRangeEnd"))
            cm_e.set(_w("id"), str(item.comment_id))
            return

        # Check if item is inside a hyperlink
        link_info = getattr(item.r_pr, "link", None)
        parent = p_elem
        if link_info and isinstance(link_info, dict):
            url = link_info.get("url", "")
            anchor = link_info.get("anchor", "")
            h_elem = ET.SubElement(p_elem, _w("hyperlink"))
            if url:
                r_id = self._gen_r_id()
                self.rels.append(
                    Relationship(id=r_id, type=REL_HYPERLINK, target=url, target_mode="External")
                )
                h_elem.set(_r("id"), r_id)
            if anchor:
                h_elem.set(_w("anchor"), anchor)
            parent = h_elem

        r_elem = ET.SubElement(parent, _w("r"))
        r_pr_elem = ET.Element(_w("rPr"))
        self._populate_r_pr(r_pr_elem, item.r_pr)

        if len(r_pr_elem) > 0:
            enforce_schema_order(r_pr_elem, "wordprocessingml_rpr")
            r_elem.append(r_pr_elem)

        if isinstance(item, TextItem):
            t_elem = ET.SubElement(r_elem, _w("t"))
            text = item.text
            t_elem.text = text
            if text.startswith(" ") or text.endswith(" ") or "  " in text or "\n" in text:
                t_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

        elif isinstance(item, TabItem):
            ET.SubElement(r_elem, _w("tab"))

        elif isinstance(item, BreakItem):
            br_elem = ET.SubElement(r_elem, _w("br"))
            if item.break_type and item.break_type != "line":
                br_elem.set(_w("type"), item.break_type)

        elif isinstance(item, SymbolItem):
            sym = ET.SubElement(r_elem, _w("sym"))
            sym.set(_w("font"), item.font)
            code = hex(ord(item.char))[2:].upper() if item.char else "0020"
            sym.set(_w("char"), f"F0{code}" if len(code) <= 2 else code)

        elif isinstance(item, FieldBeginItem):
            fc = ET.SubElement(r_elem, _w("fldChar"))
            fc.set(_w("fldCharType"), "begin")
            if item.instr:
                r_instr = ET.SubElement(parent, _w("r"))
                instr_elem = ET.SubElement(r_instr, _w("instrText"))
                instr_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                instr_elem.text = item.instr

        elif isinstance(item, FieldSeparateItem):
            fc = ET.SubElement(r_elem, _w("fldChar"))
            fc.set(_w("fldCharType"), "separate")

        elif isinstance(item, FieldEndItem):
            fc = ET.SubElement(r_elem, _w("fldChar"))
            fc.set(_w("fldCharType"), "end")

    def _populate_r_pr(self, r_pr_elem: ET.Element, r_pr: RunProperties) -> None:
        """Add child formatting elements to <w:rPr>."""
        if r_pr.style:
            r_style = ET.SubElement(r_pr_elem, _w("rStyle"))
            r_style.set(_w("val"), r_pr.style)

        font_changed = (
            r_pr.font != "Times New Roman"
            or r_pr.font_ea != "SimSun"
            or r_pr.font_cs != "Times New Roman"
        )
        if font_changed:
            r_fonts = ET.SubElement(r_pr_elem, _w("rFonts"))
            if r_pr.font:
                r_fonts.set(_w("ascii"), r_pr.font)
                r_fonts.set(_w("hAnsi"), r_pr.font)
            if r_pr.font_ea:
                r_fonts.set(_w("eastAsia"), r_pr.font_ea)
            if r_pr.font_cs:
                r_fonts.set(_w("cs"), r_pr.font_cs)

        if r_pr.b:
            ET.SubElement(r_pr_elem, _w("b"))

        if r_pr.i:
            ET.SubElement(r_pr_elem, _w("i"))

        if r_pr.caps:
            ET.SubElement(r_pr_elem, _w("caps"))

        if r_pr.small_caps:
            ET.SubElement(r_pr_elem, _w("smallCaps"))

        if r_pr.strike:
            ET.SubElement(r_pr_elem, _w("strike"))

        if r_pr.dstrike:
            ET.SubElement(r_pr_elem, _w("dstrike"))

        clean_col = _clean_hex(r_pr.color)
        if clean_col and clean_col != "auto":
            col_elem = ET.SubElement(r_pr_elem, _w("color"))
            col_elem.set(_w("val"), clean_col)

        if r_pr.spacing:
            sp_elem = ET.SubElement(r_pr_elem, _w("spacing"))
            sp_elem.set(_w("val"), str(pt_to_dxa(r_pr.spacing)))

        if r_pr.kern:
            kern_elem = ET.SubElement(r_pr_elem, _w("kern"))
            kern_elem.set(_w("val"), str(round(r_pr.kern * 2)))

        if r_pr.sz != 12.0:
            sz_elem = ET.SubElement(r_pr_elem, _w("sz"))
            sz_elem.set(_w("val"), str(round(r_pr.sz * 2)))

        if r_pr.sz_cs:
            sz_cs = ET.SubElement(r_pr_elem, _w("szCs"))
            sz_cs.set(_w("val"), str(round(r_pr.sz_cs * 2)))

        if r_pr.highlight:
            hl_elem = ET.SubElement(r_pr_elem, _w("highlight"))
            hl_elem.set(_w("val"), r_pr.highlight)

        if r_pr.u and r_pr.u != "none":
            u_elem = ET.SubElement(r_pr_elem, _w("u"))
            u_elem.set(_w("val"), r_pr.u)

        if r_pr.vert and r_pr.vert != "baseline":
            vert_elem = ET.SubElement(r_pr_elem, _w("vertAlign"))
            vert_elem.set(_w("val"), r_pr.vert)

        if r_pr.lang:
            lang_elem = ET.SubElement(r_pr_elem, _w("lang"))
            lang_elem.set(_w("val"), r_pr.lang)
            if r_pr.lang_ea:
                lang_elem.set(_w("eastAsia"), r_pr.lang_ea)

    def _serialize_table(
        self, tbl: Table, hf_id_map: dict[str, str] | None = None
    ) -> ET.Element:
        """Serialize Table into <w:tbl>."""
        tbl_elem = ET.Element(_w("tbl"))

        # Table Properties
        tbl_pr_elem = ET.SubElement(tbl_elem, _w("tblPr"))
        if tbl.tbl_pr.style and tbl.tbl_pr.style != "TableNormal":
            st_elem = ET.SubElement(tbl_pr_elem, _w("tblStyle"))
            st_elem.set(_w("val"), tbl.tbl_pr.style)

        if tbl.tbl_pr.jc and tbl.tbl_pr.jc != "left":
            jc_elem = ET.SubElement(tbl_pr_elem, _w("jc"))
            jc_elem.set(_w("val"), tbl.tbl_pr.jc)

        if tbl.tbl_pr.w:
            w_elem = ET.SubElement(tbl_pr_elem, _w("tblW"))
            w_elem.set(_w("w"), str(pt_to_dxa(tbl.tbl_pr.w)))
            w_elem.set(_w("type"), tbl.tbl_pr.w_type)

        # Table Grid
        if tbl.grid:
            grid_elem = ET.SubElement(tbl_elem, _w("tblGrid"))
            for col_w in tbl.grid:
                col_elem = ET.SubElement(grid_elem, _w("gridCol"))
                col_elem.set(_w("w"), str(pt_to_dxa(col_w)))

        # Rows
        for row in tbl.rows:
            tr_elem = ET.SubElement(tbl_elem, _w("tr"))
            tr_pr = row.tr_pr
            if tr_pr.h is not None or tr_pr.tbl_header or tr_pr.cant_split:
                tr_pr_elem = ET.SubElement(tr_elem, _w("trPr"))
                if tr_pr.h is not None:
                    h_elem = ET.SubElement(tr_pr_elem, _w("trHeight"))
                    h_elem.set(_w("val"), str(pt_to_dxa(tr_pr.h)))
                    h_elem.set(_w("hRule"), tr_pr.h_rule)
                if tr_pr.tbl_header:
                    ET.SubElement(tr_pr_elem, _w("tblHeader"))
                if tr_pr.cant_split:
                    ET.SubElement(tr_pr_elem, _w("cantSplit"))

            # Cells
            for cell in row.cells:
                tc_elem = ET.SubElement(tr_elem, _w("tc"))
                tc_pr = cell.tc_pr
                tc_pr_elem = ET.SubElement(tc_elem, _w("tcPr"))

                if tc_pr.w:
                    tc_w = ET.SubElement(tc_pr_elem, _w("tcW"))
                    tc_w.set(_w("w"), str(pt_to_dxa(tc_pr.w)))
                    tc_w.set(_w("type"), tc_pr.w_type)

                if tc_pr.grid_span > 1:
                    gs = ET.SubElement(tc_pr_elem, _w("gridSpan"))
                    gs.set(_w("val"), str(tc_pr.grid_span))

                if tc_pr.v_merge:
                    vm = ET.SubElement(tc_pr_elem, _w("vMerge"))
                    if tc_pr.v_merge != "continue":
                        vm.set(_w("val"), tc_pr.v_merge)

                if tc_pr.v_align and tc_pr.v_align != "top":
                    va = ET.SubElement(tc_pr_elem, _w("vAlign"))
                    va.set(_w("val"), tc_pr.v_align)

                if tc_pr.shd and (tc_pr.shd.fill != "auto" or tc_pr.shd.val != "clear"):
                    shd = ET.SubElement(tc_pr_elem, _w("shd"))
                    shd.set(_w("val"), tc_pr.shd.val)
                    shd.set(_w("color"), _clean_hex(tc_pr.shd.color) or "auto")
                    shd.set(_w("fill"), _clean_hex(tc_pr.shd.fill) or "auto")

                # Cell Blocks
                for c_block in cell.blocks:
                    if isinstance(c_block, Paragraph):
                        tc_elem.append(self._serialize_paragraph(c_block, hf_id_map))
                    elif isinstance(c_block, Table):
                        tc_elem.append(self._serialize_table(c_block, hf_id_map))

        return tbl_elem

    def _serialize_sect_pr(
        self, sect: SectionProperties, hf_id_map: dict[str, str] | None = None
    ) -> ET.Element:
        """Serialize SectionProperties into <w:sectPr>."""
        sect_elem = ET.Element(_w("sectPr"))

        # Headers & Footers
        if hf_id_map:
            for h_type, old_id in sect.refs.get("hdr", {}).items():
                if old_id in hf_id_map:
                    hdr_ref = ET.SubElement(sect_elem, _w("headerReference"))
                    hdr_ref.set(_w("type"), h_type)
                    hdr_ref.set(_r("id"), hf_id_map[old_id])

            for f_type, old_id in sect.refs.get("ftr", {}).items():
                if old_id in hf_id_map:
                    ftr_ref = ET.SubElement(sect_elem, _w("footerReference"))
                    ftr_ref.set(_w("type"), f_type)
                    ftr_ref.set(_r("id"), hf_id_map[old_id])

        if sect.sect_type and sect.sect_type != "nextPage":
            type_elem = ET.SubElement(sect_elem, _w("type"))
            type_elem.set(_w("val"), sect.sect_type)

        # Page Size
        pg_sz = ET.SubElement(sect_elem, _w("pgSz"))
        pg_sz.set(_w("w"), str(pt_to_dxa(sect.pg_w)))
        pg_sz.set(_w("h"), str(pt_to_dxa(sect.pg_h)))
        if sect.orient == "landscape":
            pg_sz.set(_w("orient"), "landscape")

        # Page Margins
        pg_mar = ET.SubElement(sect_elem, _w("pgMar"))
        pg_mar.set(_w("top"), str(pt_to_dxa(sect.mt)))
        pg_mar.set(_w("right"), str(pt_to_dxa(sect.mr)))
        pg_mar.set(_w("bottom"), str(pt_to_dxa(sect.mb)))
        pg_mar.set(_w("left"), str(pt_to_dxa(sect.ml)))
        pg_mar.set(_w("header"), str(pt_to_dxa(sect.hdr)))
        pg_mar.set(_w("footer"), str(pt_to_dxa(sect.ftr)))
        if sect.gutter:
            pg_mar.set(_w("gutter"), str(pt_to_dxa(sect.gutter)))

        # Columns
        cols = sect.cols
        cols_elem = ET.SubElement(sect_elem, _w("cols"))
        if cols.num > 1:
            cols_elem.set(_w("num"), str(cols.num))
        cols_elem.set(_w("space"), str(pt_to_dxa(cols.space)))

        if sect.title_pg:
            ET.SubElement(sect_elem, _w("titlePg"))

        return sect_elem

    def _build_hf_xml(self, story: Story) -> bytes:
        """Serialize a header or footer story to XML."""
        root_tag = "hdr" if story.kind == "header" else "ftr"
        root = ET.Element(_w(root_tag))

        for block in story.blocks:
            if isinstance(block, Paragraph):
                root.append(self._serialize_paragraph(block))
            elif isinstance(block, Table):
                root.append(self._serialize_table(block))

        return serialize_xml(root, standalone=True)

    def _build_styles_xml(self) -> bytes:
        """Serialize styles into word/styles.xml."""
        root = ET.Element(_w("styles"))

        # docDefaults
        doc_defaults = ET.SubElement(root, _w("docDefaults"))
        r_pr_def_parent = ET.SubElement(doc_defaults, _w("rPrDefault"))
        r_pr_def = ET.SubElement(r_pr_def_parent, _w("rPr"))
        r_fonts = ET.SubElement(r_pr_def, _w("rFonts"))
        r_fonts.set(_w("ascii"), "Times New Roman")
        r_fonts.set(_w("hAnsi"), "Times New Roman")
        r_fonts.set(_w("eastAsia"), "SimSun")
        r_fonts.set(_w("cs"), "Times New Roman")
        sz = ET.SubElement(r_pr_def, _w("sz"))
        sz.set(_w("val"), "24")

        # Styles
        styles_dict = self.doc.styles or builtin_styles()
        for s_id, st in styles_dict.items():
            if not isinstance(st, Style):
                continue
            s_elem = ET.SubElement(root, _w("style"))
            s_elem.set(_w("type"), st.style_type)
            s_elem.set(_w("styleId"), st.id)
            if st.is_default:
                s_elem.set(_w("default"), "1")

            name = ET.SubElement(s_elem, _w("name"))
            name.set(_w("val"), st.name)

            if st.based_on:
                based = ET.SubElement(s_elem, _w("basedOn"))
                based.set(_w("val"), st.based_on)

            if st.next_style:
                nxt = ET.SubElement(s_elem, _w("next"))
                nxt.set(_w("val"), st.next_style)

            # pPr
            p_pr_elem = ET.Element(_w("pPr"))
            self._populate_p_pr(p_pr_elem, st.p_pr)
            if len(p_pr_elem) > 0:
                enforce_schema_order(p_pr_elem, "wordprocessingml_ppr")
                s_elem.append(p_pr_elem)

            # rPr
            r_pr_elem = ET.Element(_w("rPr"))
            self._populate_r_pr(r_pr_elem, st.r_pr)
            if len(r_pr_elem) > 0:
                enforce_schema_order(r_pr_elem, "wordprocessingml_rpr")
                s_elem.append(r_pr_elem)

        return serialize_xml(root, standalone=True)

    def _build_settings_xml(self) -> bytes:
        """Serialize settings into word/settings.xml."""
        root = ET.Element(_w("settings"))
        zoom = ET.SubElement(root, _w("zoom"))
        zoom.set(_w("percent"), "100")
        tab = ET.SubElement(root, _w("defaultTabStop"))
        tab.set(_w("val"), "720")
        return serialize_xml(root, standalone=True)

    def _build_fonts_xml(self) -> bytes:
        """Serialize fonts into word/fontTable.xml."""
        root = ET.Element(_w("fonts"))
        fonts = self.doc.props.get("fonts", ["Times New Roman", "Arial", "SimSun", "Calibri"])
        for font_name in fonts:
            f_elem = ET.SubElement(root, _w("font"))
            f_elem.set(_w("name"), font_name)
        return serialize_xml(root, standalone=True)


def write_docx(doc: Document, target: str | Path | io.BytesIO | None = None) -> bytes:
    """Convenience function to serialize Document to DOCX/DOCM bytes or file."""
    writer = DocxWriter(doc)
    return writer.write(target)
