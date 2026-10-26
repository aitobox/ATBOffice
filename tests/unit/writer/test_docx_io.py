"""Unit and roundtrip tests for Quire WordprocessingML DOCX and DOCM IO."""

from __future__ import annotations

import hashlib
import io
import xml.etree.ElementTree as ET
import zipfile

import pytest

from atboffice.modules.writer.io import DocxReader, DocxWriter, read_docx, write_docx
from atboffice.modules.writer.models.document import (
    Cell,
    Document,
    Paragraph,
    Row,
    Story,
    Table,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    CellProperties,
    IndentProperties,
    ParagraphProperties,
    RowProperties,
    RunProperties,
    SectionProperties,
    ShadingProperties,
    SpacingProperties,
    TableProperties,
)
from atboffice.vfs.opc import SourcePackage
from atboffice.vfs.order import SCHEMA_ORDERS


def test_module_exports() -> None:
    """Verify standard exports from io package."""
    assert callable(read_docx)
    assert callable(write_docx)
    assert DocxReader is not None
    assert DocxWriter is not None


def test_docx_new_document_roundtrip() -> None:
    """Create a new document with formatted paragraphs and runs, serialize, and read back."""
    doc = Document()

    # Paragraph 1: Heading with custom spacing and run formatting
    p1 = Paragraph()
    p1.p_pr = ParagraphProperties(
        style="Heading1",
        jc="center",
        sp=SpacingProperties(before=12.0, after=6.0, line=1.5),
        keep_next=True,
    )
    r1 = TextItem(
        text="Executive Summary",
        r_pr=RunProperties(font="Arial", sz=18.0, b=True, color="#003366"),
    )
    p1.runs.append(r1)

    # Paragraph 2: Body text with mixed styles
    p2 = Paragraph()
    p2.p_pr = ParagraphProperties(
        style="Normal",
        jc="both",
        ind=IndentProperties(left=36.0, right=36.0, first_line=18.0),
        sp=SpacingProperties(after=8.0, line=1.15),
    )
    r2_1 = TextItem(
        text="This is regular body text with ",
        r_pr=RunProperties(font="Times New Roman", sz=11.0),
    )
    r2_2 = TextItem(
        text="bold and italic formatting",
        r_pr=RunProperties(font="Times New Roman", sz=11.0, b=True, i=True),
    )
    r2_3 = TextItem(
        text=" and yellow highlighting.",
        r_pr=RunProperties(font="Times New Roman", sz=11.0, highlight="yellow"),
    )
    p2.runs.extend([r2_1, r2_2, r2_3])

    doc.main.blocks = [p1, p2]

    # Section geometry
    doc.sect = SectionProperties(
        pg_w=612.0,
        pg_h=792.0,
        orient="portrait",
        mt=72.0,
        mb=72.0,
        ml=90.0,
        mr=90.0,
    )

    # Write to DOCX bytes
    docx_bytes = write_docx(doc)
    assert len(docx_bytes) > 0

    # Read back
    doc_loaded = read_docx(docx_bytes)
    assert len(doc_loaded.main.blocks) == 2

    lp1 = doc_loaded.main.blocks[0]
    assert isinstance(lp1, Paragraph)
    assert lp1.p_pr.style == "Heading1"
    assert lp1.p_pr.jc == "center"
    assert lp1.p_pr.keep_next is True
    assert lp1.p_pr.sp.before == pytest.approx(12.0)
    assert lp1.p_pr.sp.after == pytest.approx(6.0)
    assert len(lp1.runs) == 1
    assert lp1.runs[0].text == "Executive Summary"
    assert lp1.runs[0].r_pr.font == "Arial"
    assert lp1.runs[0].r_pr.sz == pytest.approx(18.0)
    assert lp1.runs[0].r_pr.b is True
    assert lp1.runs[0].r_pr.color == "#003366"

    lp2 = doc_loaded.main.blocks[1]
    assert isinstance(lp2, Paragraph)
    assert lp2.p_pr.jc == "both"
    assert lp2.p_pr.ind.left == pytest.approx(36.0)
    assert lp2.p_pr.ind.first_line == pytest.approx(18.0)
    assert len(lp2.runs) == 3
    assert lp2.runs[1].r_pr.b is True
    assert lp2.runs[1].r_pr.i is True
    assert lp2.runs[2].r_pr.highlight == "yellow"

    # Section properties
    assert doc_loaded.sect.pg_w == pytest.approx(612.0)
    assert doc_loaded.sect.pg_h == pytest.approx(792.0)
    assert doc_loaded.sect.mt == pytest.approx(72.0)
    assert doc_loaded.sect.ml == pytest.approx(90.0)


def test_docx_table_roundtrip() -> None:
    """Create a document with a styled table, serialize, and read back."""
    doc = Document()

    tbl = Table()
    tbl.tbl_pr = TableProperties(style="TableGrid", jc="center", w=400.0, w_type="dxa")
    tbl.grid = [200.0, 200.0]

    # Row 1 (Header)
    r1 = Row()
    r1.tr_pr = RowProperties(h=24.0, tbl_header=True)
    c1_1 = Cell(
        tc_pr=CellProperties(w=200.0, shd=ShadingProperties(val="clear", fill="#CCCCCC")),
        blocks=[Paragraph(runs=[TextItem(text="Header Col 1", r_pr=RunProperties(b=True))])],
    )
    c1_2 = Cell(
        tc_pr=CellProperties(w=200.0, shd=ShadingProperties(val="clear", fill="#CCCCCC")),
        blocks=[Paragraph(runs=[TextItem(text="Header Col 2", r_pr=RunProperties(b=True))])],
    )
    r1.cells = [c1_1, c1_2]

    # Row 2 (Data)
    r2 = Row()
    c2_1 = Cell(
        tc_pr=CellProperties(w=200.0),
        blocks=[Paragraph(runs=[TextItem(text="Data 1")])],
    )
    c2_2 = Cell(
        tc_pr=CellProperties(w=200.0),
        blocks=[Paragraph(runs=[TextItem(text="Data 2")])],
    )
    r2.cells = [c2_1, c2_2]

    tbl.rows = [r1, r2]
    doc.main.blocks = [tbl]

    data = write_docx(doc)
    doc_read = read_docx(data)

    assert len(doc_read.main.blocks) == 1
    t = doc_read.main.blocks[0]
    assert isinstance(t, Table)
    assert t.tbl_pr.jc == "center"
    assert len(t.grid) == 2
    assert t.grid[0] == pytest.approx(200.0)
    assert len(t.rows) == 2
    assert t.rows[0].tr_pr.tbl_header is True
    assert t.rows[0].cells[0].tc_pr.shd.fill == "#CCCCCC"
    assert t.rows[0].cells[0].blocks[0].runs[0].text == "Header Col 1"
    assert t.rows[1].cells[1].blocks[0].runs[0].text == "Data 2"


def test_schema_ordering_enforcement() -> None:
    """Verify that generated <w:pPr> and <w:rPr> elements strictly obey ECMA-376 schema ordering."""
    doc = Document()
    p = Paragraph()
    # Configure properties that might appear in conflicting order
    p.p_pr = ParagraphProperties(
        style="Heading2",
        jc="right",
        keep_next=True,
        keep_lines=True,
        page_break_before=True,
        sp=SpacingProperties(before=10.0, after=5.0),
        ind=IndentProperties(left=20.0),
        outline_level=2,
    )
    p.runs = [
        TextItem(
            text="Ordered text",
            r_pr=RunProperties(
                style="Strong",
                font="Calibri",
                b=True,
                i=True,
                color="#112233",
                sz=14.0,
                highlight="green",
                u="single",
                strike=True,
                vert="superscript",
            ),
        )
    ]
    doc.main.blocks = [p]

    docx_bytes = write_docx(doc)

    # Inspect XML directly from ZIP
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zf:
        doc_xml = zf.read("word/document.xml")

    root = ET.fromstring(doc_xml)
    p_elem = root.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")
    assert p_elem is not None

    p_pr = p_elem.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr")
    assert p_pr is not None

    # Check that children of pPr match sequence order in SCHEMA_ORDERS["wordprocessingml_ppr"]
    ppr_order = SCHEMA_ORDERS["wordprocessingml_ppr"]
    p_tags = [
        c.tag.split("}", 1)[1] if "}" in c.tag else c.tag
        for c in p_pr
    ]
    indices = [ppr_order.index(t) for t in p_tags if t in ppr_order]
    assert indices == sorted(indices), f"pPr child tags not in schema order: {p_tags}"

    # Check children of rPr
    r_elem = p_elem.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r")
    assert r_elem is not None
    r_pr = r_elem.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr")
    assert r_pr is not None

    rpr_order = SCHEMA_ORDERS["wordprocessingml_rpr"]
    r_tags = [
        c.tag.split("}", 1)[1] if "}" in c.tag else c.tag
        for c in r_pr
    ]
    r_indices = [rpr_order.index(t) for t in r_tags if t in rpr_order]
    assert r_indices == sorted(r_indices), f"rPr child tags not in schema order: {r_tags}"


def test_docm_macro_lossless_preservation() -> None:
    """Verify that editing a DOCM file carries untouched VBA binaries and other parts byte-for-byte."""
    vba_binary_payload = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"REALISTIC_VBA_PROJECT_BINARY_PAYLOAD" * 50
    image_payload = b"\x89PNG\r\n\x1a\n" + b"FAKE_PNG_BINARY_DATA" * 20
    theme_xml = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme"/>'

    vba_hash_orig = hashlib.sha256(vba_binary_payload).hexdigest()
    image_hash_orig = hashlib.sha256(image_payload).hexdigest()
    theme_hash_orig = hashlib.sha256(theme_xml).hexdigest()

    # Create synthetic DOCM package
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        ct_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/>\n'
            '  <Default Extension="png" ContentType="image/png"/>\n'
            '  <Override PartName="/word/document.xml" ContentType="application/vnd.ms-word.document.macroEnabled.main+xml"/>\n'
            '  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>\n'
            "</Types>"
        )
        zf.writestr("[Content_Types].xml", ct_xml.encode("utf-8"))

        # _rels/.rels
        zf.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n'
                "</Relationships>"
            ).encode("utf-8"),
        )

        # word/document.xml
        zf.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
                "  <w:body>\n"
                "    <w:p><w:r><w:t>Original Unmodified Paragraph</w:t></w:r></w:p>\n"
                "    <w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/></w:sectPr>\n"
                "  </w:body>\n"
                "</w:document>"
            ).encode("utf-8"),
        )

        # word/_rels/document.xml.rels
        zf.writestr(
            "word/_rels/document.xml.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                '  <Relationship Id="rId1" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/>\n'
                '  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>\n'
                '  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>\n'
                "</Relationships>"
            ).encode("utf-8"),
        )

        zf.writestr("word/vbaProject.bin", vba_binary_payload)
        zf.writestr("word/media/image1.png", image_payload)
        zf.writestr("word/theme/theme1.xml", theme_xml)

    orig_docm_bytes = buf.getvalue()

    # Load with DocxReader
    doc = read_docx(orig_docm_bytes)
    assert getattr(doc, "_doc_format", "") == "docm"
    assert len(doc.main.blocks) == 1
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    assert p.runs[0].text == "Original Unmodified Paragraph"

    # Edit document: change text
    p.runs[0].text = "Edited Macro-Enabled Paragraph"

    # Save
    saved_docm_bytes = write_docx(doc)

    # Verify saved package
    saved_pkg = SourcePackage.from_bytes(saved_docm_bytes)

    # 1. Byte-for-byte SHA256 preservation of untouched binary / theme parts
    assert hashlib.sha256(saved_pkg.read_part("word/vbaProject.bin")).hexdigest() == vba_hash_orig
    assert hashlib.sha256(saved_pkg.read_part("word/media/image1.png")).hexdigest() == image_hash_orig
    assert hashlib.sha256(saved_pkg.read_part("word/theme/theme1.xml")).hexdigest() == theme_hash_orig

    # 2. Document content type remains macroEnabled
    ct = saved_pkg.get_content_type("word/document.xml")
    assert ct == "application/vnd.ms-word.document.macroEnabled.main+xml"

    # 3. Reload and verify edited text is present
    reloaded_doc = read_docx(saved_docm_bytes)
    assert reloaded_doc.main.blocks[0].runs[0].text == "Edited Macro-Enabled Paragraph"


def test_headers_and_footers_roundtrip() -> None:
    """Verify headers and footers are properly serialized, linked, and deserialized."""
    doc = Document()
    doc.main.blocks = [Paragraph(runs=[TextItem(text="Body content")])]

    # Header story
    hdr_story = Story(kind="header", blocks=[Paragraph(runs=[TextItem(text="Header Page 1")])])
    ftr_story = Story(kind="footer", blocks=[Paragraph(runs=[TextItem(text="Footer - Confidential")])])

    doc.hf["rIdHdr1"] = hdr_story
    doc.hf["rIdFtr1"] = ftr_story

    doc.sect.refs = {
        "hdr": {"default": "rIdHdr1"},
        "ftr": {"default": "rIdFtr1"},
    }

    docx_bytes = write_docx(doc)
    doc_reloaded = read_docx(docx_bytes)

    assert len(doc_reloaded.sect.refs.get("hdr", {})) == 1
    assert len(doc_reloaded.sect.refs.get("ftr", {})) == 1

    hdr_id = doc_reloaded.sect.refs["hdr"]["default"]
    ftr_id = doc_reloaded.sect.refs["ftr"]["default"]

    assert hdr_id in doc_reloaded.hf
    assert ftr_id in doc_reloaded.hf

    assert doc_reloaded.hf[hdr_id].blocks[0].runs[0].text == "Header Page 1"
    assert doc_reloaded.hf[ftr_id].blocks[0].runs[0].text == "Footer - Confidential"


def test_hyperlinks_and_breaks_and_symbols_roundtrip() -> None:
    """Verify inline hyperlinks, breaks, symbols, and tabs roundtrip cleanly."""
    from atboffice.modules.writer.models.document import BreakItem, SymbolItem, TabItem

    doc = Document()
    p = Paragraph()

    # Text before tab
    r1 = TextItem(text="Chapter 1")
    # Tab
    r_tab = TabItem()
    # Hyperlink run
    r_link = TextItem(
        text="Click here to visit OpenAI",
        r_pr=RunProperties(u="single", color="#0000FF"),
    )
    r_link.r_pr.link = {"url": "https://openai.com", "anchor": "overview"}  # type: ignore[attr-defined]

    # Breaks
    r_br_line = BreakItem(break_type="line")
    r_br_page = BreakItem(break_type="page")

    # Symbol
    r_sym = SymbolItem(font="Wingdings", char="★")

    p.runs = [r1, r_tab, r_link, r_br_line, r_br_page, r_sym]
    doc.main.blocks = [p]

    docx_bytes = write_docx(doc)
    doc_reloaded = read_docx(docx_bytes)

    loaded_p = doc_reloaded.main.blocks[0]
    assert isinstance(loaded_p, Paragraph)
    # Check runs
    item_types = [it.t for it in loaded_p.runs]
    assert "text" in item_types
    assert "tab" in item_types
    assert "br" in item_types
    assert "sym" in item_types

    # Find the link item
    link_item = next(
        (it for it in loaded_p.runs if getattr(it.r_pr, "link", None) is not None), None
    )
    assert link_item is not None
    link_info = getattr(link_item.r_pr, "link")
    assert link_info.get("url") == "https://openai.com"
    assert link_info.get("anchor") == "overview"


def test_unmodified_document_preserves_all_parts() -> None:
    """Verify that loading and saving an unmodified document preserves byte-for-byte fidelity."""
    doc = Document()
    p = Paragraph(runs=[TextItem(text="Static content")])
    doc.main.blocks = [p]
    initial_bytes = write_docx(doc)

    initial_pkg = SourcePackage.from_bytes(initial_bytes)
    initial_hashes = {
        name: hashlib.sha256(initial_pkg.read_part(name)).hexdigest()
        for name in initial_pkg.parts()
    }

    # Load with DocxReader
    doc_loaded = read_docx(initial_bytes)

    # Save immediately without any mutations
    resaved_bytes = write_docx(doc_loaded)
    resaved_pkg = SourcePackage.from_bytes(resaved_bytes)

    # Assert all untouched parts have identical SHA256 hashes
    for part_name, expected_hash in initial_hashes.items():
        if part_name not in ("word/document.xml", "word/_rels/document.xml.rels"):
            actual_hash = hashlib.sha256(resaved_pkg.read_part(part_name)).hexdigest()
            assert actual_hash == expected_hash, f"Part {part_name} diverged in hash!"
