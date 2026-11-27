"""ECMA-376 WordprocessingML writer for DOCX and DOCM files."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from atboffice.modules.writer.io.docx_reader import (
    comments_signature,
    normalize_strict_namespaces,
)
from atboffice.modules.writer.models.document import (
    BookmarkEndItem,
    BookmarkStartItem,
    BreakItem,
    CommentRangeEnd,
    CommentRangeStart,
    CommentRefItem,
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    NoteRefItem,
    Paragraph,
    RunItem,
    SdtEndItem,
    SdtStartItem,
    Story,
    SymbolItem,
    TabItem,
    Table,
    TextItem,
)
from atboffice.modules.writer.models.drawing import (
    ChartItem,
    DrawingObject,
    PictureItem,
    ShapeItem,
    WrapMode,
    WrapSide,
)
from atboffice.modules.writer.models.omml import OfficeMathItem, serialize_omml
from atboffice.modules.writer.models.properties import (
    ParagraphProperties,
    RunProperties,
    SectionProperties,
    pt_to_dxa,
)
from atboffice.modules.writer.models.styles import Style, builtin_styles
from atboffice.vfs import etree as ET
from atboffice.vfs.opc import (
    PackageWriter,
    Relationship,
    SourcePackage,
    get_rels_path,
    resolve_part_uri,
)
from atboffice.vfs.order import enforce_schema_order
from atboffice.vfs.xml_tree import serialize_xml

# Standard Namespaces
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
NS_WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
NS_XML = "http://www.w3.org/XML/1998/namespace"

CT_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
CT_DOCM = "application/vnd.ms-word.document.macroEnabled.main+xml"
CT_STYLES = "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"
CT_SETTINGS = "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"
CT_FONTS = "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"
CT_HEADER = "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"
CT_FOOTER = "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"
CT_COMMENTS = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
CT_RELS = "application/vnd.openxmlformats-package.relationships+xml"
CT_XML = "application/xml"

REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
REL_STYLES = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
REL_SETTINGS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings"
REL_FONTS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable"
REL_HEADER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"
REL_FOOTER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer"
REL_HYPERLINK = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
REL_COMMENTS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
REL_COMMENTS_EXT = "http://schemas.microsoft.com/office/2011/relationships/commentsExtended"
REL_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

_IMAGE_MIME_TYPES: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "webp": "image/webp",
}

# Register standard prefixes with ElementTree
ET.register_namespace("w", NS_W)
ET.register_namespace("r", NS_R)
ET.register_namespace("m", NS_M)
ET.register_namespace("wp", NS_WP)
ET.register_namespace("a", NS_A)
ET.register_namespace("pic", NS_PIC)
ET.register_namespace("wps", NS_WPS)
ET.register_namespace("wpg", "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup")
ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")
ET.register_namespace("v", "urn:schemas-microsoft-com:vml")
ET.register_namespace("o", "urn:schemas-microsoft-com:office:office")
ET.register_namespace("w10", "urn:schemas-microsoft-com:office:word")
ET.register_namespace("w14", "http://schemas.microsoft.com/office/word/2010/wordml")
ET.register_namespace("w15", "http://schemas.microsoft.com/office/word/2012/wordml")


def _w(tag: str) -> str:
    """Helper to return Clark notation for WordprocessingML tag."""
    return f"{{{NS_W}}}{tag}"


def _r(tag: str) -> str:
    """Helper to return Clark notation for Relationship tag."""
    return f"{{{NS_R}}}{tag}"


def _wp(tag: str) -> str:
    """Helper to return Clark notation for WordprocessingDrawing tag."""
    return f"{{{NS_WP}}}{tag}"


def _a(tag: str) -> str:
    """Helper to return Clark notation for DrawingML main tag."""
    return f"{{{NS_A}}}{tag}"


def _pic(tag: str) -> str:
    """Helper to return Clark notation for DrawingML picture tag."""
    return f"{{{NS_PIC}}}{tag}"


def _wps(tag: str) -> str:
    """Helper to return Clark notation for WordprocessingShape tag."""
    return f"{{{NS_WPS}}}{tag}"


def _pt_to_emu(pt: float) -> str:
    """Convert points to EMU integer string (1 pt = 12700 EMU)."""
    return str(int(round(float(pt) * 12700)))


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
        self._main_path: str = doc.keep.get("main_part") or "word/document.xml"
        self._added_media: dict[str, tuple[bytes, str]] = {}
        self._next_drawing_id = 1
        self._used_drawing_ids: set[int] = set()

    def _gen_r_id(self) -> str:
        r_id = f"rId{self._next_r_id}"
        self._next_r_id += 1
        return r_id

    def _alloc_drawing_id(self, preferred: int = 0) -> int:
        if preferred and preferred > 0 and preferred not in self._used_drawing_ids:
            self._used_drawing_ids.add(preferred)
            return preferred
        while self._next_drawing_id in self._used_drawing_ids:
            self._next_drawing_id += 1
        did = self._next_drawing_id
        self._used_drawing_ids.add(did)
        self._next_drawing_id += 1
        return did

    def _comments_part_path(self) -> str:
        return self.doc.keep.get("comments_part") or resolve_part_uri(
            self._main_path, "comments.xml"
        )

    def _are_comments_unchanged(self) -> bool:
        if self.source_pkg is None or "comments_snapshot" not in self.doc.keep:
            return False
        comments_part = self._comments_part_path()
        if not self.source_pkg.has_part(comments_part):
            return False
        return comments_signature(self.doc.comments) == self.doc.keep["comments_snapshot"]

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

        main_path = self._main_path
        main_rels_path = get_rels_path(main_path)

        ct = CT_DOCM if self.doc_format == "docm" else CT_DOCX
        writer.replace_part(main_path, doc_xml, ct)
        writer.replace_part(main_rels_path, doc_rels, CT_RELS)

        # Write headers/footers if present in doc.hf
        for old_id, story in self.doc.hf.items():
            new_id = hf_id_map.get(old_id)
            rel = next((r for r in self.rels if r.id == new_id), None)
            if rel:
                part_path = resolve_part_uri(main_path, rel.target)
                hf_xml = self._build_hf_xml(story)
                part_ct = CT_HEADER if rel.type == REL_HEADER else CT_FOOTER
                if self.source_pkg.has_part(part_path):
                    writer.replace_part(part_path, hf_xml, part_ct)
                else:
                    writer.add_part(part_path, hf_xml, part_ct)

        # styles.xml: edit the original in place; carried untouched when unchanged.
        styles_path = self.doc.keep.get("styles_part") or resolve_part_uri(main_path, "styles.xml")
        if self.source_pkg.has_part(styles_path) and "styles_snapshot" in self.doc.keep:
            original = self.source_pkg.read_part(styles_path)
            styles_xml = self._patch_styles_xml(original)
            if styles_xml is not original:
                writer.replace_part(styles_path, styles_xml, CT_STYLES)
        else:
            writer.replace_part(styles_path, self._build_styles_xml(), CT_STYLES)

        # Added media parts (newly inserted pictures without raw_xml)
        for part_path, (media_bytes, media_ct) in self._added_media.items():
            writer.add_part(part_path, media_bytes, media_ct)

        # comments.xml: preserve byte-for-byte when unchanged, update/add/delete otherwise.
        comments_part = self._comments_part_path()
        if not self._are_comments_unchanged():
            if self.doc.comments:
                cm_rel = next((r for r in self.rels if r.type == REL_COMMENTS), None)
                target_cm = resolve_part_uri(main_path, cm_rel.target) if cm_rel else comments_part
                comments_xml = self._build_comments_xml()
                if self.source_pkg.has_part(target_cm):
                    writer.replace_part(target_cm, comments_xml, CT_COMMENTS)
                else:
                    writer.add_part(target_cm, comments_xml, CT_COMMENTS)
            else:
                if self.source_pkg.has_part(comments_part):
                    writer.delete_part(comments_part)
                for r in self.source_pkg.get_relationships(main_path):
                    if r.type == REL_COMMENTS_EXT:
                        ext_part = resolve_part_uri(main_path, r.target)
                        if self.source_pkg.has_part(ext_part):
                            writer.delete_part(ext_part)
                default_ext = resolve_part_uri(main_path, "commentsExtended.xml")
                if self.source_pkg.has_part(default_ext):
                    writer.delete_part(default_ext)

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
                part_path = resolve_part_uri("word/document.xml", rel.target)
                hf_xml = self._build_hf_xml(story)
                part_ct = CT_HEADER if rel.type == REL_HEADER else CT_FOOTER
                writer.add_part(part_path, hf_xml, part_ct)

        # Added media parts
        for part_path, (media_bytes, media_ct) in self._added_media.items():
            writer.add_part(part_path, media_bytes, media_ct)

        # Comments part when comments exist
        if self.doc.comments:
            writer.add_part("word/comments.xml", self._build_comments_xml(), CT_COMMENTS)

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

    def _sync_comments_rels(self) -> None:
        """Ensure document relationships match current ``doc.comments`` state."""
        if self._are_comments_unchanged():
            return
        if self.doc.comments:
            if not any(r.type == REL_COMMENTS for r in self.rels):
                self.rels.append(
                    Relationship(id=self._gen_r_id(), type=REL_COMMENTS, target="comments.xml")
                )
        else:
            self.rels = [r for r in self.rels if r.type not in (REL_COMMENTS, REL_COMMENTS_EXT)]

    def _build_document_and_rels(self) -> tuple[bytes, bytes, dict[str, str]]:
        """Build <w:document> XML and word/_rels/document.xml.rels XML."""
        self.rels = []
        self._added_media = {}
        self._next_drawing_id = 1
        self._used_drawing_ids = set()
        existing_styles_id = None
        existing_settings_id = None
        existing_fonts_id = None

        existing_hf_rels: dict[str, Relationship] = {}
        if self.source_pkg is not None:
            for r in self.source_pkg.get_relationships(self._main_path):
                if r.type == REL_STYLES:
                    existing_styles_id = r.id
                elif r.type == REL_SETTINGS:
                    existing_settings_id = r.id
                elif r.type == REL_FONTS:
                    existing_fonts_id = r.id
                elif r.type in (REL_HEADER, REL_FOOTER):
                    existing_hf_rels[r.id] = r
                    continue
                self.rels.append(r)

        max_id = 0
        for r in self.rels:
            if r.id.startswith("rId") and r.id[3:].isdigit():
                max_id = max(max_id, int(r.id[3:]))
        for r_id in existing_hf_rels:
            if r_id.startswith("rId") and r_id[3:].isdigit():
                max_id = max(max_id, int(r_id[3:]))
        self._next_r_id = max_id + 1

        # Add or preserve standard relationships
        if existing_styles_id:
            r_styles = existing_styles_id
        else:
            r_styles = self._gen_r_id()
            self.rels.append(Relationship(id=r_styles, type=REL_STYLES, target="styles.xml"))

        if not existing_settings_id:
            r_settings = self._gen_r_id()
            self.rels.append(Relationship(id=r_settings, type=REL_SETTINGS, target="settings.xml"))

        if not existing_fonts_id:
            r_fonts = self._gen_r_id()
            self.rels.append(Relationship(id=r_fonts, type=REL_FONTS, target="fontTable.xml"))

        # Map header/footer relationships (preserve original targets and IDs if present in
        # source_pkg)
        hf_id_map: dict[str, str] = {}
        hdr_idx = 1
        ftr_idx = 1
        used_targets = {r.target for r in existing_hf_rels.values()}
        for old_id, story in self.doc.hf.items():
            is_hdr = story.kind == "header"
            rel_type = REL_HEADER if is_hdr else REL_FOOTER
            if old_id in existing_hf_rels:
                orig_rel = existing_hf_rels[old_id]
                new_id = orig_rel.id
                target_name = orig_rel.target
            else:
                new_id = self._gen_r_id()
                if is_hdr:
                    while f"header{hdr_idx}.xml" in used_targets:
                        hdr_idx += 1
                    target_name = f"header{hdr_idx}.xml"
                    used_targets.add(target_name)
                    hdr_idx += 1
                else:
                    while f"footer{ftr_idx}.xml" in used_targets:
                        ftr_idx += 1
                    target_name = f"footer{ftr_idx}.xml"
                    used_targets.add(target_name)
                    ftr_idx += 1
            self.rels.append(Relationship(id=new_id, type=rel_type, target=target_name))
            hf_id_map[old_id] = new_id

        # Build Document XML
        root = ET.Element(_w("document"))

        # Serialize document background if preserved
        bg_info = self.doc.keep.get("background")
        if bg_info:
            raw_xml = bg_info.get("raw_xml")
            if raw_xml:
                try:
                    norm_raw = normalize_strict_namespaces(raw_xml) or raw_xml
                    bg_el = ET.fromstring(norm_raw)
                    root.append(bg_el)
                except Exception:
                    bg_el = ET.SubElement(root, _w("background"))
                    for k, v in bg_info.get("attrib", {}).items():
                        bg_el.set(k if k.startswith("{") else _w(k), v)
            else:
                bg_el = ET.SubElement(root, _w("background"))
                for k, v in bg_info.get("attrib", {}).items():
                    bg_el.set(k if k.startswith("{") else _w(k), v)

        body = ET.SubElement(root, _w("body"))

        # Serialize main story blocks with block SDT wrapping
        self._serialize_block_sequence(body, self.doc.main.blocks, hf_id_map)

        # Trailing section properties
        sect_elem = self._serialize_sect_pr(self.doc.sect, hf_id_map)
        body.append(sect_elem)

        doc_xml = serialize_xml(root, standalone=True)

        self._sync_comments_rels()

        # Build document.xml.rels
        rels_elem = ET.Element(
            "{http://schemas.openxmlformats.org/package/2006/relationships}Relationships"
        )
        for r in self.rels:
            r_elem = ET.SubElement(
                rels_elem,
                "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship",
            )
            r_elem.set("Id", r.id)
            r_elem.set("Type", r.type)
            r_elem.set("Target", r.target)
            if r.target_mode != "Internal":
                r_elem.set("TargetMode", r.target_mode)

        rels_xml = serialize_xml(rels_elem, standalone=True)
        return doc_xml, rels_xml, hf_id_map

    def _serialize_block_sequence(
        self,
        container: ET.Element,
        blocks: list[Paragraph | Table],
        hf_id_map: dict[str, str] | None = None,
    ) -> None:
        """Serialize a sequence of Paragraph/Table blocks with stack-based SDT wrapping."""
        # Stack entries: (sdt_elem, current_content_elem, control_dict)
        stack: list[tuple[ET.Element | None, ET.Element, dict[str, Any] | None]] = [
            (None, container, None)
        ]

        for block in blocks:
            pr = block.p_pr if isinstance(block, Paragraph) else block.tbl_pr
            for ctrl in getattr(pr, "sdts", []):
                shell_xml = ctrl.get("shell_xml")
                if shell_xml:
                    try:
                        sdt_elem = ET.fromstring(shell_xml)
                        sc = sdt_elem.find(f"{{{NS_W}}}sdtContent")
                        if sc is None:
                            sc = ET.SubElement(sdt_elem, _w("sdtContent"))
                        stack.append((sdt_elem, sc, ctrl))
                    except Exception:
                        pass

            _, curr_content, _ = stack[-1]

            if isinstance(block, Table):
                tbl_elem = self._serialize_table(block, hf_id_map)
                curr_content.append(tbl_elem)
            else:
                p_elem = self._serialize_paragraph(block, hf_id_map)
                curr_content.append(p_elem)

            for key in getattr(pr, "sdte", []):
                if len(stack) > 1 and stack[-1][2] and stack[-1][2].get("key") == key:
                    finished_sdt, _, _ = stack.pop()
                    if finished_sdt is not None:
                        stack[-1][1].append(finished_sdt)

        while len(stack) > 1:
            finished_sdt, _, _ = stack.pop()
            if finished_sdt is not None:
                stack[-1][1].append(finished_sdt)

    def _serialize_paragraph(
        self, p: Paragraph, hf_id_map: dict[str, str] | None = None
    ) -> ET.Element:
        """Serialize a Paragraph into <w:p> with schema-ordered properties."""
        p_elem = ET.Element(_w("p"))

        # Paragraph Properties
        p_pr_elem = ET.Element(_w("pPr"))
        self._populate_p_pr(p_pr_elem, p.p_pr, p)

        if p.sect is not None:
            sect_elem = self._serialize_sect_pr(p.sect, hf_id_map)
            p_pr_elem.append(sect_elem)

        # Enforce strict schema ordering on pPr
        if len(p_pr_elem) > 0:
            enforce_schema_order(p_pr_elem, "wordprocessingml_ppr")
            p_elem.append(p_pr_elem)

        # Runs & Inline Items
        self._serialize_runs_sequence(p_elem, p.runs)

        return p_elem

    def _populate_p_pr(
        self, p_pr_elem: ET.Element, p_pr: ParagraphProperties, p: Paragraph | None = None
    ) -> None:
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

        if getattr(p_pr, "frame_pr", None) is not None:
            fp = ET.SubElement(p_pr_elem, _w("framePr"))
            seen_locals = set()
            for k, v in p_pr.frame_pr.items():
                if "}" in k:
                    local = k.split("}", 1)[-1]
                elif ":" in k:
                    local = k.split(":", 1)[-1]
                else:
                    local = k
                if local in seen_locals:
                    continue
                seen_locals.add(local)
                fp.set(_w(local), str(v))

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
        if (
            ind.left
            or ind.right
            or ind.first_line
            or ind.left_explicit
            or ind.right_explicit
            or ind.first_line_explicit
        ):
            ind_elem = ET.SubElement(p_pr_elem, _w("ind"))
            if ind.left or ind.left_explicit:
                ind_elem.set(_w("left"), str(pt_to_dxa(ind.left)))
            if ind.right or ind.right_explicit:
                ind_elem.set(_w("right"), str(pt_to_dxa(ind.right)))
            if ind.first_line > 0 or (ind.first_line_explicit and not ind.first_line):
                ind_elem.set(_w("firstLine"), str(pt_to_dxa(ind.first_line)))
            elif ind.first_line < 0:
                ind_elem.set(_w("hanging"), str(pt_to_dxa(-ind.first_line)))

        if p_pr.contextual is not None:
            ctx_elem = ET.SubElement(p_pr_elem, _w("contextualSpacing"))
            if not p_pr.contextual:
                ctx_elem.set(_w("val"), "0")

        # Alignment
        if p_pr.jc and p_pr.jc != "left":
            jc_elem = ET.SubElement(p_pr_elem, _w("jc"))
            jc_elem.set(_w("val"), p_pr.jc)

        # Outline Level
        if p_pr.outline_level is not None:
            lvl_elem = ET.SubElement(p_pr_elem, _w("outlineLvl"))
            lvl_elem.set(_w("val"), str(p_pr.outline_level))

        # Check for paragraph mark styling and revisions in pPr/rPr
        mark_ins = getattr(p, "mark_ins", None) if p else None
        mark_del = getattr(p, "mark_del", None) if p else None
        p_r_pr = getattr(p, "r_pr", None) if p else None
        has_r_pr = (
            mark_ins is not None
            or mark_del is not None
            or (
                p_r_pr
                and (
                    p_r_pr.style
                    or p_r_pr.font != "Times New Roman"
                    or p_r_pr.b
                    or p_r_pr.i
                    or p_r_pr.color
                )
            )
        )
        if has_r_pr:
            r_pr_elem = ET.Element(_w("rPr"))
            if mark_ins is not None:
                ins = ET.SubElement(r_pr_elem, _w("ins"))
                ins.set(_w("id"), str(mark_ins.id))
                ins.set(_w("author"), mark_ins.author)
                if mark_ins.date:
                    ins.set(_w("date"), mark_ins.date)
            if mark_del is not None:
                del_elem = ET.SubElement(r_pr_elem, _w("del"))
                del_elem.set(_w("id"), str(mark_del.id))
                del_elem.set(_w("author"), mark_del.author)
                if mark_del.date:
                    del_elem.set(_w("date"), mark_del.date)
            if p_r_pr:
                self._populate_r_pr(r_pr_elem, p_r_pr)
            p_pr_elem.append(r_pr_elem)

    def _serialize_runs_sequence(self, p_elem: ET.Element, runs: list[RunItem]) -> None:
        """Serialize inline runs handling inline SDTs, links, and revisions."""
        i = 0
        while i < len(runs):
            item = runs[i]
            # 1. Inline SDT Start
            if getattr(item, "t", "") == "sdts" or isinstance(item, SdtStartItem):
                ctrl = getattr(item, "control", {}) or {}
                key = ctrl.get("key")
                end_idx = -1
                for j in range(i + 1, len(runs)):
                    if (
                        getattr(runs[j], "t", "") == "sdte" or isinstance(runs[j], SdtEndItem)
                    ) and getattr(runs[j], "key", "") == key:
                        end_idx = j
                        break
                if end_idx != -1:
                    shell_xml = ctrl.get("shell_xml")
                    if shell_xml:
                        try:
                            sdt_elem = ET.fromstring(shell_xml)
                            sc = sdt_elem.find(f"{{{NS_W}}}sdtContent")
                            if sc is None:
                                sc = ET.SubElement(sdt_elem, _w("sdtContent"))
                            self._serialize_runs_sequence(sc, runs[i + 1 : end_idx])
                            p_elem.append(sdt_elem)
                            i = end_idx + 1
                            continue
                        except Exception:
                            pass
                i += 1
                continue

            if getattr(item, "t", "") == "sdte" or isinstance(item, SdtEndItem):
                i += 1
                continue

            # 2. Check for PictureItem with raw_xml
            if isinstance(item, PictureItem) and item.raw_xml:
                try:
                    raw = normalize_strict_namespaces(item.raw_xml) or item.raw_xml
                    elem = ET.fromstring(raw)
                    if (
                        elem.tag.endswith("AlternateContent")
                        or elem.tag.endswith("drawing")
                        or elem.tag.endswith("pict")
                    ):
                        r_elem = ET.SubElement(p_elem, _w("r"))
                        r_elem.append(elem)
                    else:
                        p_elem.append(elem)
                    i += 1
                    continue
                except Exception:
                    pass

            # 3. Group consecutive items sharing link, ins, del_rev
            link_info = getattr(item.r_pr, "link", None) if hasattr(item, "r_pr") else None
            ins_info = getattr(item.r_pr, "ins", None) if hasattr(item, "r_pr") else None
            del_info = getattr(item.r_pr, "del_rev", None) if hasattr(item, "r_pr") else None

            j = i + 1
            if link_info or ins_info or del_info:
                while j < len(runs):
                    next_item = runs[j]
                    if getattr(next_item, "t", "") in ("sdts", "sdte") or isinstance(
                        next_item, (SdtStartItem, SdtEndItem)
                    ):
                        break
                    if isinstance(next_item, PictureItem) and next_item.raw_xml:
                        break
                    n_r = getattr(next_item, "r_pr", None)
                    n_link = getattr(n_r, "link", None) if n_r else None
                    n_ins = getattr(n_r, "ins", None) if n_r else None
                    n_del = getattr(n_r, "del_rev", None) if n_r else None
                    if n_link != link_info or n_ins != ins_info or n_del != del_info:
                        break
                    j += 1

            target_container = p_elem
            if link_info and isinstance(link_info, dict):
                url = link_info.get("url", "")
                anchor = link_info.get("anchor", "")
                h_elem = ET.SubElement(target_container, _w("hyperlink"))
                if url:
                    r_id = self._gen_r_id()
                    self.rels.append(
                        Relationship(
                            id=r_id, type=REL_HYPERLINK, target=url, target_mode="External"
                        )
                    )
                    h_elem.set(_r("id"), r_id)
                if anchor:
                    h_elem.set(_w("anchor"), anchor)
                target_container = h_elem

            if ins_info:
                ins_elem = ET.SubElement(target_container, _w("ins"))
                ins_elem.set(_w("id"), str(ins_info.id))
                ins_elem.set(_w("author"), ins_info.author)
                if ins_info.date:
                    ins_elem.set(_w("date"), ins_info.date)
                target_container = ins_elem
            elif del_info:
                del_elem = ET.SubElement(target_container, _w("del"))
                del_elem.set(_w("id"), str(del_info.id))
                del_elem.set(_w("author"), del_info.author)
                if del_info.date:
                    del_elem.set(_w("date"), del_info.date)
                target_container = del_elem

            for k in range(i, j):
                self._serialize_run_item(target_container, runs[k], is_del=bool(del_info))

            i = j

    def _serialize_run_item(self, parent: ET.Element, item: RunItem, is_del: bool = False) -> None:
        """Serialize a RunItem into corresponding XML elements under <w:p> or wrapper."""
        if isinstance(item, OfficeMathItem):
            math_elem = serialize_omml(item)
            parent.append(math_elem)
            return

        if isinstance(item, BookmarkStartItem):
            bm_s = ET.SubElement(parent, _w("bookmarkStart"))
            bm_s.set(_w("id"), str(item.bookmark_id))
            bm_s.set(_w("name"), item.name)
            return

        if isinstance(item, BookmarkEndItem):
            bm_e = ET.SubElement(parent, _w("bookmarkEnd"))
            bm_e.set(_w("id"), str(item.bookmark_id))
            return

        if isinstance(item, CommentRangeStart):
            cm_s = ET.SubElement(parent, _w("commentRangeStart"))
            cm_s.set(_w("id"), str(item.comment_id))
            return

        if isinstance(item, CommentRangeEnd):
            cm_e = ET.SubElement(parent, _w("commentRangeEnd"))
            cm_e.set(_w("id"), str(item.comment_id))
            return

        if isinstance(item, PictureItem):
            if item.raw_xml:
                try:
                    raw = normalize_strict_namespaces(item.raw_xml) or item.raw_xml
                    elem = ET.fromstring(raw)
                    if (
                        elem.tag.endswith("AlternateContent")
                        or elem.tag.endswith("drawing")
                        or elem.tag.endswith("pict")
                    ):
                        if parent.tag.endswith(("ins", "del", "hyperlink")):
                            r_elem = ET.SubElement(parent, _w("r"))
                            r_elem.append(elem)
                        else:
                            parent.append(elem)
                    else:
                        parent.append(elem)
                    return
                except Exception:
                    pass
            if isinstance(item, ShapeItem):
                r_elem = ET.SubElement(parent, _w("r"))
                r_elem.append(self._build_shape_drawing_elem(item))
                return
            if not isinstance(item, ChartItem):
                drawing_el = self._build_picture_drawing_elem(item)
                if drawing_el is not None:
                    r_elem = ET.SubElement(parent, _w("r"))
                    r_elem.append(drawing_el)
            return

        r_elem = ET.SubElement(parent, _w("r"))
        r_pr_elem = ET.Element(_w("rPr"))
        if hasattr(item, "r_pr") and item.r_pr:
            self._populate_r_pr(r_pr_elem, item.r_pr)

        if len(r_pr_elem) > 0:
            enforce_schema_order(r_pr_elem, "wordprocessingml_rpr")
            r_elem.append(r_pr_elem)

        if isinstance(item, TextItem):
            t_tag = _w("delText") if is_del else _w("t")
            t_elem = ET.SubElement(r_elem, t_tag)
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

        elif isinstance(item, NoteRefItem):
            tag = "endnoteReference" if item.kind == "en" else "footnoteReference"
            ref = ET.SubElement(r_elem, _w(tag))
            ref.set(_w("id"), str(item.note_id))
            if item.custom_mark:
                ref.set(_w("customMarkFollows"), "1")
                mark = ET.SubElement(r_elem, _w("t"))
                mark.text = item.custom_mark

        elif isinstance(item, CommentRefItem):
            ref = ET.SubElement(r_elem, _w("commentReference"))
            ref.set(_w("id"), str(item.comment_id))

    def _populate_r_pr(self, r_pr_elem: ET.Element, r_pr: RunProperties) -> None:
        """Add child formatting elements to <w:rPr>."""
        if r_pr.style:
            r_style = ET.SubElement(r_pr_elem, _w("rStyle"))
            r_style.set(_w("val"), r_pr.style)

        font_changed = (
            r_pr.font != "Times New Roman"
            or r_pr.font_ea != "SimSun"
            or r_pr.font_cs != "Times New Roman"
            or r_pr.font_explicit
            or r_pr.font_ea_explicit
            or r_pr.font_cs_explicit
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
        elif r_pr.strike_off:
            ET.SubElement(r_pr_elem, _w("strike")).set(_w("val"), "0")

        if r_pr.dstrike:
            ET.SubElement(r_pr_elem, _w("dstrike"))
        elif r_pr.dstrike_off:
            ET.SubElement(r_pr_elem, _w("dstrike")).set(_w("val"), "0")

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

        if r_pr.sz != 12.0 or r_pr.sz_explicit:
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

    def _serialize_table(self, tbl: Table, hf_id_map: dict[str, str] | None = None) -> ET.Element:
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

        # Table Indent (w:tblInd)
        if tbl.tbl_pr.ind is not None:
            ind_elem = ET.SubElement(tbl_pr_elem, _w("tblInd"))
            ind_elem.set(_w("w"), str(pt_to_dxa(tbl.tbl_pr.ind)))
            ind_elem.set(_w("type"), "dxa")

        # Table Cell Margins (w:tblCellMar)
        if tbl.tbl_pr.cell_mar:
            mar_elem = ET.SubElement(tbl_pr_elem, _w("tblCellMar"))
            for side, tag_name in (
                ("t", "top"),
                ("l", "left"),
                ("b", "bottom"),
                ("r", "right"),
            ):
                if side in tbl.tbl_pr.cell_mar:
                    side_elem = ET.SubElement(mar_elem, _w(tag_name))
                    side_elem.set(_w("w"), str(pt_to_dxa(tbl.tbl_pr.cell_mar[side])))
                    side_elem.set(_w("type"), "dxa")

        # Table Borders (w:tblBorders)
        if tbl.tbl_pr.borders:
            bds_elem = ET.SubElement(tbl_pr_elem, _w("tblBorders"))
            for b_tag in ("top", "left", "bottom", "right", "insideH", "insideV"):
                if b_tag in tbl.tbl_pr.borders:
                    bp = tbl.tbl_pr.borders[b_tag]
                    b_el = ET.SubElement(bds_elem, _w(b_tag))
                    b_el.set(_w("val"), bp.val)
                    b_el.set(_w("sz"), str(int(round(bp.sz * 8.0))))
                    b_el.set(_w("space"), "0")
                    b_el.set(_w("color"), _clean_hex(bp.color) or "auto")

        # Table Grid
        if tbl.grid:
            grid_elem = ET.SubElement(tbl_elem, _w("tblGrid"))
            for col_w in tbl.grid:
                col_elem = ET.SubElement(grid_elem, _w("gridCol"))
                col_elem.set(_w("w"), str(pt_to_dxa(col_w)))

        # Rows
        row_stack: list[tuple[ET.Element | None, ET.Element, dict[str, Any] | None]] = [
            (None, tbl_elem, None)
        ]
        for row in tbl.rows:
            tr_pr = row.tr_pr
            for ctrl in getattr(tr_pr, "sdts", []):
                shell_xml = ctrl.get("shell_xml")
                if shell_xml:
                    try:
                        sdt_elem = ET.fromstring(shell_xml)
                        sc = sdt_elem.find(f"{{{NS_W}}}sdtContent")
                        if sc is None:
                            sc = ET.SubElement(sdt_elem, _w("sdtContent"))
                        row_stack.append((sdt_elem, sc, ctrl))
                    except Exception:
                        pass

            _, curr_row_container, _ = row_stack[-1]
            tr_elem = ET.SubElement(curr_row_container, _w("tr"))
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
            cell_stack: list[tuple[ET.Element | None, ET.Element, dict[str, Any] | None]] = [
                (None, tr_elem, None)
            ]
            for cell in row.cells:
                tc_pr = cell.tc_pr
                for ctrl in getattr(tc_pr, "sdts", []):
                    shell_xml = ctrl.get("shell_xml")
                    if shell_xml:
                        try:
                            sdt_elem = ET.fromstring(shell_xml)
                            sc = sdt_elem.find(f"{{{NS_W}}}sdtContent")
                            if sc is None:
                                sc = ET.SubElement(sdt_elem, _w("sdtContent"))
                            cell_stack.append((sdt_elem, sc, ctrl))
                        except Exception:
                            pass

                _, curr_cell_container, _ = cell_stack[-1]
                tc_elem = ET.SubElement(curr_cell_container, _w("tc"))
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

                # Cell Margins (w:tcMar)
                if tc_pr.tc_mar:
                    mar_elem = ET.SubElement(tc_pr_elem, _w("tcMar"))
                    for side, tag_name in (
                        ("t", "top"),
                        ("l", "left"),
                        ("b", "bottom"),
                        ("r", "right"),
                    ):
                        if side in tc_pr.tc_mar:
                            side_elem = ET.SubElement(mar_elem, _w(tag_name))
                            side_elem.set(_w("w"), str(pt_to_dxa(tc_pr.tc_mar[side])))
                            side_elem.set(_w("type"), "dxa")

                # Cell Borders (w:tcBorders)
                if tc_pr.borders:
                    bds_elem = ET.SubElement(tc_pr_elem, _w("tcBorders"))
                    for b_tag in ("top", "left", "bottom", "right"):
                        if b_tag in tc_pr.borders:
                            bp = tc_pr.borders[b_tag]
                            b_el = ET.SubElement(bds_elem, _w(b_tag))
                            b_el.set(_w("val"), bp.val)
                            b_el.set(_w("sz"), str(int(round(bp.sz * 8.0))))
                            b_el.set(_w("space"), "0")
                            b_el.set(_w("color"), _clean_hex(bp.color) or "auto")

                # Cell Blocks
                self._serialize_block_sequence(tc_elem, cell.blocks, hf_id_map)

                for key in getattr(tc_pr, "sdte", []):
                    if (
                        len(cell_stack) > 1
                        and cell_stack[-1][2]
                        and cell_stack[-1][2].get("key") == key
                    ):
                        finished_sdt, _, _ = cell_stack.pop()
                        if finished_sdt is not None:
                            cell_stack[-1][1].append(finished_sdt)

            while len(cell_stack) > 1:
                finished_sdt, _, _ = cell_stack.pop()
                if finished_sdt is not None:
                    cell_stack[-1][1].append(finished_sdt)

            for key in getattr(tr_pr, "sdte", []):
                if len(row_stack) > 1 and row_stack[-1][2] and row_stack[-1][2].get("key") == key:
                    finished_sdt, _, _ = row_stack.pop()
                    if finished_sdt is not None:
                        row_stack[-1][1].append(finished_sdt)

        while len(row_stack) > 1:
            finished_sdt, _, _ = row_stack.pop()
            if finished_sdt is not None:
                row_stack[-1][1].append(finished_sdt)

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
        if cols.sep:
            cols_elem.set(_w("sep"), "1")
        if not cols.equal_width:
            cols_elem.set(_w("equalWidth"), "0")
            for index, width in enumerate(cols.widths):
                col_elem = ET.SubElement(cols_elem, _w("col"))
                col_elem.set(_w("w"), str(pt_to_dxa(width)))
                gap = cols.spaces[index] if index < len(cols.spaces) else cols.space
                col_elem.set(_w("space"), str(pt_to_dxa(gap)))

        if sect.title_pg:
            ET.SubElement(sect_elem, _w("titlePg"))

        return sect_elem

    def _build_hf_xml(self, story: Story) -> bytes:
        """Serialize a header or footer story to XML."""
        root_tag = "hdr" if story.kind == "header" else "ftr"
        root = ET.Element(_w(root_tag))

        self._serialize_block_sequence(root, story.blocks, None)

        return serialize_xml(root, standalone=True)

    def _style_element(self, st: Style) -> ET.Element:
        """Serialize one style definition as ``<w:style>``."""
        s_elem = ET.Element(_w("style"))
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

        p_pr_elem = ET.Element(_w("pPr"))
        self._populate_p_pr(p_pr_elem, st.p_pr)
        if len(p_pr_elem) > 0:
            enforce_schema_order(p_pr_elem, "wordprocessingml_ppr")
            s_elem.append(p_pr_elem)

        r_pr_elem = ET.Element(_w("rPr"))
        self._populate_r_pr(r_pr_elem, st.r_pr)
        if len(r_pr_elem) > 0:
            enforce_schema_order(r_pr_elem, "wordprocessingml_rpr")
            s_elem.append(r_pr_elem)
        return s_elem

    def _patch_styles_xml(self, original: bytes) -> bytes:
        """Apply style edits to the original styles.xml.

        Styles that still equal their loaded state keep their original element, with
        every property the model does not represent. Edited styles are rewritten, new
        ones appended and deleted ones removed. ``latentStyles`` and ``docDefaults`` are
        always carried. Returns ``original`` itself when nothing changed.
        """
        snapshot: dict[str, Style] = self.doc.keep.get("styles_snapshot") or {}
        current = {k: v for k, v in (self.doc.styles or {}).items() if isinstance(v, Style)}
        changed_ids = [k for k, st in current.items() if snapshot.get(k) != st]
        removed_ids = [k for k in snapshot if k not in current]
        if not changed_ids and not removed_ids:
            return original

        root = ET.fromstring(original)
        by_id = {el.get(_w("styleId")): el for el in root if el.tag == _w("style")}
        for s_id in removed_ids:
            el = by_id.get(s_id)
            if el is not None:
                root.remove(el)
        for s_id in changed_ids:
            new_el = self._style_element(current[s_id])
            old_el = by_id.get(s_id)
            if old_el is not None:
                root.replace(old_el, new_el)
            elif s_id in snapshot or not current[s_id].builtin:
                root.append(new_el)
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
        def_r_pr = (getattr(self.doc, "defaults", None) or {}).get("r_pr")
        def_sz = def_r_pr.sz if def_r_pr is not None else 12.0
        sz = ET.SubElement(r_pr_def, _w("sz"))
        sz.set(_w("val"), str(round(def_sz * 2)))

        # Styles
        styles_dict = self.doc.styles or builtin_styles()
        for st in styles_dict.values():
            if isinstance(st, Style):
                root.append(self._style_element(st))

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

    def _build_drawing_container(
        self, item: DrawingObject, doc_id: int, name: str, descr: str
    ) -> tuple[ET.Element, ET.Element]:
        """Build ``<w:drawing>`` wrapper and return ``(drawing, graphicData)``."""
        drawing_el = ET.Element(_w("drawing"))
        cx = _pt_to_emu(max(1.0, float(item.width)))
        cy = _pt_to_emu(max(1.0, float(item.height)))
        fp = item.float_pr
        if fp is not None:
            container = ET.SubElement(drawing_el, _wp("anchor"))
            container.set("distT", _pt_to_emu(fp.dist.top))
            container.set("distB", _pt_to_emu(fp.dist.bottom))
            container.set("distL", _pt_to_emu(fp.dist.left))
            container.set("distR", _pt_to_emu(fp.dist.right))
            container.set("simplePos", "0")
            container.set("relativeHeight", str(max(0, int(fp.z_index))))
            behind = bool(fp.behind or fp.wrap == WrapMode.BEHIND)
            container.set("behindDoc", "1" if behind else "0")
            container.set("locked", "0")
            container.set("layoutInCell", "1")
            container.set("allowOverlap", "1")

            simple_pos = ET.SubElement(container, _wp("simplePos"))
            simple_pos.set("x", "0")
            simple_pos.set("y", "0")

            pos_h = ET.SubElement(container, _wp("positionH"))
            pos_h.set("relativeFrom", fp.pos_h.rel or "column")
            if fp.pos_h.align:
                al = ET.SubElement(pos_h, _wp("align"))
                al.text = fp.pos_h.align
            else:
                off = ET.SubElement(pos_h, _wp("posOffset"))
                off.text = _pt_to_emu(fp.pos_h.offset)

            pos_v = ET.SubElement(container, _wp("positionV"))
            pos_v.set("relativeFrom", fp.pos_v.rel or "paragraph")
            if fp.pos_v.align:
                al = ET.SubElement(pos_v, _wp("align"))
                al.text = fp.pos_v.align
            else:
                off = ET.SubElement(pos_v, _wp("posOffset"))
                off.text = _pt_to_emu(fp.pos_v.offset)

            ext = ET.SubElement(container, _wp("extent"))
            ext.set("cx", cx)
            ext.set("cy", cy)
            eff = ET.SubElement(container, _wp("effectExtent"))
            eff.set("l", "0")
            eff.set("t", "0")
            eff.set("r", "0")
            eff.set("b", "0")

            wrap_side = {
                WrapSide.LEFT: "left",
                WrapSide.RIGHT: "right",
                WrapSide.LARGEST: "largest",
                WrapSide.BOTH: "bothSides",
            }.get(fp.side, "bothSides")
            if fp.wrap == WrapMode.SQUARE:
                w_el = ET.SubElement(container, _wp("wrapSquare"))
                w_el.set("wrapText", wrap_side)
            elif fp.wrap == WrapMode.TIGHT:
                w_el = ET.SubElement(container, _wp("wrapTight"))
                w_el.set("wrapText", wrap_side)
            elif fp.wrap == WrapMode.TOP_BOTTOM:
                ET.SubElement(container, _wp("wrapTopAndBottom"))
            else:
                ET.SubElement(container, _wp("wrapNone"))
        else:
            container = ET.SubElement(drawing_el, _wp("inline"))
            container.set("distT", "0")
            container.set("distB", "0")
            container.set("distL", "0")
            container.set("distR", "0")
            ext = ET.SubElement(container, _wp("extent"))
            ext.set("cx", cx)
            ext.set("cy", cy)
            eff = ET.SubElement(container, _wp("effectExtent"))
            eff.set("l", "0")
            eff.set("t", "0")
            eff.set("r", "0")
            eff.set("b", "0")

        doc_pr = ET.SubElement(container, _wp("docPr"))
        doc_pr.set("id", str(doc_id))
        doc_pr.set("name", name)
        if descr:
            doc_pr.set("descr", descr)
        ET.SubElement(container, _wp("cNvGraphicFramePr"))
        graphic = ET.SubElement(container, _a("graphic"))
        graphic_data = ET.SubElement(graphic, _a("graphicData"))
        return drawing_el, graphic_data

    def _build_shape_drawing_elem(self, item: ShapeItem) -> ET.Element:
        """Build ``<w:drawing>`` containing ``<wps:wsp>`` for a newly created ``ShapeItem``."""
        doc_id = self._alloc_drawing_id(int(getattr(item, "id", 0) or 0))
        name = item.name or f"Shape {doc_id}"
        descr = getattr(item, "alt_text", "") or ""
        drawing_el, graphic_data = self._build_drawing_container(item, doc_id, name, descr)
        graphic_data.set("uri", NS_WPS)

        cx = _pt_to_emu(max(1.0, float(item.width)))
        cy = _pt_to_emu(max(1.0, float(item.height)))

        wsp = ET.SubElement(graphic_data, _wps("wsp"))
        c_nv_pr = ET.SubElement(wsp, _wps("cNvPr"))
        c_nv_pr.set("id", str(doc_id))
        c_nv_pr.set("name", name)

        c_nv_sp_pr = ET.SubElement(wsp, _wps("cNvSpPr"))
        if item.story is not None:
            c_nv_sp_pr.set("txBox", "1")

        sp_pr = ET.SubElement(wsp, _wps("spPr"))
        xfrm = ET.SubElement(sp_pr, _a("xfrm"))
        if item.rotation:
            xfrm.set("rot", str(int(round(float(item.rotation) * 60000))))
        if item.flip_h:
            xfrm.set("flipH", "1")
        if item.flip_v:
            xfrm.set("flipV", "1")
        off = ET.SubElement(xfrm, _a("off"))
        off.set("x", "0")
        off.set("y", "0")
        ext = ET.SubElement(xfrm, _a("ext"))
        ext.set("cx", cx)
        ext.set("cy", cy)

        prst_geom = ET.SubElement(sp_pr, _a("prstGeom"))
        prst_geom.set("prst", item.geometry or "rect")
        av_lst = ET.SubElement(prst_geom, _a("avLst"))
        for k, v in (getattr(item, "adjustments", None) or {}).items():
            gd = ET.SubElement(av_lst, _a("gd"))
            gd.set("name", str(k))
            gd.set("fmla", f"val {int(round(float(v)))}")

        fill_kind = getattr(item.fill, "kind", "none") if item.fill is not None else "none"
        fill_color = (
            _clean_hex(getattr(item.fill, "color", None)) if item.fill is not None else None
        )
        if fill_kind == "solid" and fill_color and fill_color != "auto":
            sf = ET.SubElement(sp_pr, _a("solidFill"))
            clr = ET.SubElement(sf, _a("srgbClr"))
            clr.set("val", fill_color)
        else:
            ET.SubElement(sp_pr, _a("noFill"))

        ln_w = getattr(item.line, "width", 1.0) if item.line is not None else 1.0
        ln = ET.SubElement(sp_pr, _a("ln"))
        ln.set("w", _pt_to_emu(ln_w))
        line_vis = bool(getattr(item.line, "visible", False)) if item.line is not None else False
        line_color = (
            _clean_hex(getattr(item.line, "color", None)) if item.line is not None else None
        )
        if line_vis and line_color and line_color != "auto":
            sf = ET.SubElement(ln, _a("solidFill"))
            clr = ET.SubElement(sf, _a("srgbClr"))
            clr.set("val", line_color)
        else:
            ET.SubElement(ln, _a("noFill"))

        if item.story is not None:
            txbx = ET.SubElement(wsp, _wps("txbx"))
            txbx_content = ET.SubElement(txbx, _w("txbxContent"))
            blocks = item.story.blocks if item.story.blocks else [Paragraph()]
            self._serialize_block_sequence(txbx_content, blocks)

        insets = item.insets if len(getattr(item, "insets", ())) == 4 else (7.2, 3.6, 7.2, 3.6)
        body_pr = ET.SubElement(wsp, _wps("bodyPr"))
        body_pr.set("lIns", _pt_to_emu(insets[0]))
        body_pr.set("tIns", _pt_to_emu(insets[1]))
        body_pr.set("rIns", _pt_to_emu(insets[2]))
        body_pr.set("bIns", _pt_to_emu(insets[3]))
        body_pr.set("anchor", item.v_anchor or "t")

        return drawing_el

    def _build_picture_drawing_elem(self, item: PictureItem) -> ET.Element | None:
        """Build ``<w:drawing>`` containing ``<pic:pic>`` and register media part/relationship."""
        raw_data = item.raw_data if isinstance(item.raw_data, dict) else {}
        img_bytes = raw_data.get("bytes")
        if isinstance(img_bytes, bytearray):
            img_bytes = bytes(img_bytes)
        if not isinstance(img_bytes, bytes) and self.source_pkg is not None and item.image_part:
            cand = item.image_part.lstrip("/")
            if not cand.startswith("word/") and not cand.startswith("docProps/"):
                cand = resolve_part_uri(self._main_path, cand)
            if self.source_pkg.has_part(cand):
                img_bytes = self.source_pkg.read_part(cand)
        if not isinstance(img_bytes, bytes) or not img_bytes:
            return None

        ext = (
            str(raw_data.get("ext") or Path(item.image_part or "").suffix or "png")
            .lstrip(".")
            .lower()
            or "png"
        )
        mime_type = _IMAGE_MIME_TYPES.get(ext, "image/png")

        idx = 1
        while True:
            rel_target = f"media/image{idx}.{ext}"
            part_path = resolve_part_uri(self._main_path, rel_target)
            in_src = self.source_pkg is not None and self.source_pkg.has_part(part_path)
            if not in_src and part_path not in self._added_media:
                break
            idx += 1

        self._added_media[part_path] = (bytes(img_bytes), mime_type)
        r_id = self._gen_r_id()
        self.rels.append(Relationship(id=r_id, type=REL_IMAGE, target=rel_target))

        doc_id = self._alloc_drawing_id(int(getattr(item, "id", 0) or 0))
        name = item.name or f"Picture {doc_id}"
        descr = getattr(item, "alt_text", "") or ""
        drawing_el, graphic_data = self._build_drawing_container(item, doc_id, name, descr)
        graphic_data.set("uri", NS_PIC)

        cx = _pt_to_emu(max(1.0, float(item.width)))
        cy = _pt_to_emu(max(1.0, float(item.height)))

        pic = ET.SubElement(graphic_data, _pic("pic"))
        nv_pic_pr = ET.SubElement(pic, _pic("nvPicPr"))
        c_nv_pr = ET.SubElement(nv_pic_pr, _pic("cNvPr"))
        c_nv_pr.set("id", str(doc_id))
        c_nv_pr.set("name", name)
        if descr:
            c_nv_pr.set("descr", descr)
        ET.SubElement(nv_pic_pr, _pic("cNvPicPr"))

        blip_fill = ET.SubElement(pic, _pic("blipFill"))
        blip = ET.SubElement(blip_fill, _a("blip"))
        blip.set(_r("embed"), r_id)
        stretch = ET.SubElement(blip_fill, _a("stretch"))
        ET.SubElement(stretch, _a("fillRect"))

        sp_pr = ET.SubElement(pic, _pic("spPr"))
        xfrm = ET.SubElement(sp_pr, _a("xfrm"))
        if item.rotation:
            xfrm.set("rot", str(int(round(float(item.rotation) * 60000))))
        off = ET.SubElement(xfrm, _a("off"))
        off.set("x", "0")
        off.set("y", "0")
        ext_el = ET.SubElement(xfrm, _a("ext"))
        ext_el.set("cx", cx)
        ext_el.set("cy", cy)
        prst_geom = ET.SubElement(sp_pr, _a("prstGeom"))
        prst_geom.set("prst", "rect")
        ET.SubElement(prst_geom, _a("avLst"))

        return drawing_el

    def _build_comments_xml(self) -> bytes:
        """Serialize ``doc.comments`` into ``word/comments.xml``."""
        root = ET.Element(_w("comments"))
        for cid, cm in self.doc.comments.items():
            cm_el = ET.SubElement(root, _w("comment"))
            cm_el.set(_w("id"), str(cid))
            if isinstance(cm, dict):
                author = str(cm.get("author", "Author") or "Author")
                initials = str(cm.get("initials", "") or "")
                date = str(cm.get("date", "") or "")
                raw_blocks = cm.get("blocks")
                if raw_blocks is not None:
                    blocks = list(raw_blocks) or [Paragraph()]
                else:
                    txt = str(cm.get("text", "") or "")
                    blocks = [Paragraph(runs=[TextItem(text=txt)])] if txt else [Paragraph()]
            else:
                author = str(getattr(cm, "author", "Author") or "Author")
                initials = str(getattr(cm, "initials", "") or "")
                date = str(getattr(cm, "date", "") or "")
                blocks = list(getattr(cm, "blocks", None) or []) or [Paragraph()]

            cm_el.set(_w("author"), author)
            if initials:
                cm_el.set(_w("initials"), initials)
            if date:
                cm_el.set(_w("date"), date)
            self._serialize_block_sequence(cm_el, blocks)

        return serialize_xml(root, standalone=True)


def write_docx(doc: Document, target: str | Path | io.BytesIO | None = None) -> bytes:
    """Convenience function to serialize Document to DOCX/DOCM bytes or file."""
    writer = DocxWriter(doc)
    return writer.write(target)
