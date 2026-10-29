"""Tests for advanced DOCX reader capabilities (Issue #108).

Covers:
- Multi-level numbering lists (abstractNum, num, lvl, lvlOverride, numFmt, lvlText)
- Complex tables (gridSpan, vMerge, trHeight, tcMar, tblCellMar)
- DrawingML inline & floating anchor pictures (extent, posH, posV, wrapMode, z-index)
- VML legacy pictures (w:pict)
- Footnotes, endnotes, bookmarks, and section break properties
"""

from __future__ import annotations

import io
import zipfile

import pytest

from atboffice.modules.writer.io import read_docx
from atboffice.modules.writer.models.document import (
    NoteRefItem,
    Paragraph,
    Table,
)
from atboffice.modules.writer.models.drawing import PictureItem, WrapMode

_NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _make_docx_package(parts: dict[str, str | bytes]) -> bytes:
    """Build an in-memory DOCX zip package with specified parts and sensible defaults."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Default Content_Types if not provided
        if "[Content_Types].xml" not in parts:
            ct = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                '  <Default Extension="rels" '
                'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                '  <Default Extension="xml" ContentType="application/xml"/>\n'
                '  <Default Extension="png" ContentType="image/png"/>\n'
                '  <Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
                '  <Override PartName="/word/numbering.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>\n'
                '  <Override PartName="/word/footnotes.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>\n'
                '  <Override PartName="/word/endnotes.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"/>\n'
                "</Types>"
            )
            zf.writestr("[Content_Types].xml", ct)

        # Default _rels/.rels if not provided
        if "_rels/.rels" not in parts:
            root_rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                f'  <Relationship Id="rId1" Type="{_NS_REL}/officeDocument" '
                'Target="word/document.xml"/>\n'
                "</Relationships>"
            )
            zf.writestr("_rels/.rels", root_rels)

        # Default word/_rels/document.xml.rels if not provided
        if "word/_rels/document.xml.rels" not in parts:
            doc_rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                f'  <Relationship Id="rIdNum" Type="{_NS_REL}/numbering" '
                'Target="numbering.xml"/>\n'
                f'  <Relationship Id="rIdImg1" Type="{_NS_REL}/image" '
                'Target="media/image1.png"/>\n'
                f'  <Relationship Id="rIdFn" Type="{_NS_REL}/footnotes" '
                'Target="footnotes.xml"/>\n'
                f'  <Relationship Id="rIdEn" Type="{_NS_REL}/endnotes" '
                'Target="endnotes.xml"/>\n'
                "</Relationships>"
            )
            zf.writestr("word/_rels/document.xml.rels", doc_rels)

        # Write provided parts
        for path, content in parts.items():
            if isinstance(content, str):
                zf.writestr(path, content.encode("utf-8"))
            else:
                zf.writestr(path, content)

    return buf.getvalue()


def test_numbering_advanced_parsing() -> None:
    """Test reading word/numbering.xml with abstractNum, lvl, lvlOverride, and paragraph linkage."""
    numbering_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="10">
    <w:multiLevelType w:val="multilevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="decimal"/>
      <w:lvlText w:val="%1."/>
      <w:lvlJc w:val="left"/>
      <w:pPr>
        <w:ind w:left="720" w:hanging="360"/>
      </w:pPr>
      <w:rPr>
        <w:b/>
        <w:rFonts w:ascii="Calibri"/>
      </w:rPr>
    </w:lvl>
    <w:lvl w:ilvl="1">
      <w:start w:val="1"/>
      <w:numFmt w:val="lowerLetter"/>
      <w:lvlText w:val="(%2)"/>
      <w:lvlJc w:val="left"/>
      <w:pPr>
        <w:ind w:left="1440" w:hanging="360"/>
      </w:pPr>
    </w:lvl>
    <w:lvl w:ilvl="2">
      <w:start w:val="5"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val=""/>
      <w:pPr>
        <w:ind w:left="2160" w:hanging="360"/>
      </w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1">
    <w:abstractNumId w:val="10"/>
    <w:lvlOverride w:ilvl="0">
      <w:startOverride w:val="3"/>
    </w:lvlOverride>
  </w:num>
</w:numbering>"""

    doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr>
        <w:numPr>
          <w:ilvl w:val="0"/>
          <w:numId w:val="1"/>
        </w:numPr>
      </w:pPr>
      <w:r><w:t>First Level Item</w:t></w:r>
    </w:p>
    <w:p>
      <w:pPr>
        <w:numPr>
          <w:ilvl w:val="1"/>
          <w:numId w:val="1"/>
        </w:numPr>
      </w:pPr>
      <w:r><w:t>Nested Letter Item</w:t></w:r>
    </w:p>
  </w:body>
</w:document>"""

    pkg_bytes = _make_docx_package(
        {
            "word/numbering.xml": numbering_xml,
            "word/document.xml": doc_xml,
        }
    )

    doc = read_docx(pkg_bytes)

    # 1. Verify doc.numbering structure
    assert "abs" in doc.numbering
    assert "nums" in doc.numbering
    assert "10" in doc.numbering["abs"]
    abs_num = doc.numbering["abs"]["10"]
    assert abs_num["id"] == "10"
    assert abs_num["multi"] == "multilevel"
    assert len(abs_num["levels"]) == 9  # Padded to 9 levels

    lvl0 = abs_num["levels"][0]
    assert lvl0["fmt"] == "decimal"
    assert lvl0["text"] == "%1."
    assert lvl0["start"] == 1
    assert lvl0["ind"]["l"] == 36.0  # 720 twips = 36 pt
    assert lvl0["ind"]["fl"] == -18.0  # hanging 360 twips = -18 pt

    lvl1 = abs_num["levels"][1]
    assert lvl1["fmt"] == "lowerLetter"
    assert lvl1["text"] == "(%2)"

    lvl2 = abs_num["levels"][2]
    assert lvl2["fmt"] == "bullet"
    assert lvl2["text"] == ""

    # 2. Verify num instance and lvlOverride
    assert "1" in doc.numbering["nums"]
    num1 = doc.numbering["nums"]["1"]
    assert num1["abs"] == "10"
    assert 0 in num1["ov"]
    assert num1["ov"][0]["start"] == 3

    # 3. Verify paragraph linkage
    p0 = doc.main.blocks[0]
    assert isinstance(p0, Paragraph)
    assert p0.p_pr.num is not None
    assert p0.p_pr.num.id == "1"
    assert p0.p_pr.num.lvl == 0

    p1 = doc.main.blocks[1]
    assert isinstance(p1, Paragraph)
    assert p1.p_pr.num is not None
    assert p1.p_pr.num.id == "1"
    assert p1.p_pr.num.lvl == 1


def test_table_complex_spans_and_margins() -> None:
    """Test reading complex tables with gridSpan, vMerge, trHeight, and cell/table margins."""
    doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:tbl>
      <w:tblPr>
        <w:tblW w:w="5000" w:type="dxa"/>
        <w:jc w:val="center"/>
        <w:tblCellMar>
          <w:top w:w="120" w:type="dxa"/>
          <w:bottom w:w="120" w:type="dxa"/>
          <w:left w:w="180" w:type="dxa"/>
          <w:right w:w="180" w:type="dxa"/>
        </w:tblCellMar>
      </w:tblPr>
      <w:tblGrid>
        <w:gridCol w:w="2500"/>
        <w:gridCol w:w="2500"/>
      </w:tblGrid>
      <w:tr>
        <w:trPr>
          <w:trHeight w:val="720" w:hRule="exact"/>
          <w:tblHeader/>
          <w:cantSplit/>
        </w:trPr>
        <w:tc>
          <w:tcPr>
            <w:gridSpan w:val="2"/>
            <w:tcMar>
              <w:top w:w="200"/>
              <w:left w:w="300"/>
            </w:tcMar>
          </w:tcPr>
          <w:p><w:r><w:t>Spanned Header</w:t></w:r></w:p>
        </w:tc>
      </w:tr>
      <w:tr>
        <w:trPr>
          <w:trHeight w:val="500" w:hRule="atLeast"/>
        </w:trPr>
        <w:tc>
          <w:tcPr>
            <w:vMerge w:val="restart"/>
          </w:tcPr>
          <w:p><w:r><w:t>Merged Row 1</w:t></w:r></w:p>
        </w:tc>
        <w:tc>
          <w:p><w:r><w:t>Cell 1,2</w:t></w:r></w:p>
        </w:tc>
      </w:tr>
      <w:tr>
        <w:tc>
          <w:tcPr>
            <w:vMerge/>
          </w:tcPr>
          <w:p><w:r><w:t>Merged Row 2</w:t></w:r></w:p>
        </w:tc>
        <w:tc>
          <w:p><w:r><w:t>Cell 2,2</w:t></w:r></w:p>
        </w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>"""

    pkg_bytes = _make_docx_package({"word/document.xml": doc_xml})
    doc = read_docx(pkg_bytes)

    assert len(doc.main.blocks) == 1
    tbl = doc.main.blocks[0]
    assert isinstance(tbl, Table)

    # Table properties & margins
    assert tbl.tbl_pr.jc == "center"
    assert tbl.tbl_pr.cell_mar["t"] == 6.0  # 120 / 20
    assert tbl.tbl_pr.cell_mar["b"] == 6.0  # 120 / 20
    assert tbl.tbl_pr.cell_mar["l"] == 9.0  # 180 / 20
    assert tbl.tbl_pr.cell_mar["r"] == 9.0  # 180 / 20

    # Row 0: Spanned header
    r0 = tbl.rows[0]
    assert r0.tr_pr.h == 36.0  # 720 / 20
    assert r0.tr_pr.h_rule == "exact"
    assert r0.tr_pr.tbl_header is True
    assert r0.tr_pr.cant_split is True
    assert len(r0.cells) == 1
    assert r0.cells[0].tc_pr.grid_span == 2
    assert r0.cells[0].tc_pr.tc_mar["t"] == 10.0  # 200 / 20
    assert r0.cells[0].tc_pr.tc_mar["l"] == 15.0  # 300 / 20

    # Row 1: vMerge restart
    r1 = tbl.rows[1]
    assert r1.tr_pr.h == 25.0  # 500 / 20
    assert r1.tr_pr.h_rule == "atLeast"
    assert r1.cells[0].tc_pr.v_merge == "restart"

    # Row 2: vMerge continue (default when val is missing)
    r2 = tbl.rows[2]
    assert r2.cells[0].tc_pr.v_merge == "continue"


def test_drawingml_inline_and_anchor() -> None:
    """Test parsing DrawingML inline and anchor pictures with positioning and text wrapping."""
    doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p>
      <w:r>
        <w:drawing>
          <wp:inline>
            <wp:extent cx="1270000" cy="635000"/>
            <wp:docPr id="1" name="InlinePicture1" descr="Alt description for picture 1"/>
            <a:graphic>
              <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:pic>
                  <pic:blipFill>
                    <a:blip r:embed="rIdImg1"/>
                    <a:srcRect l="10000" t="20000" r="10000" b="20000"/>
                  </pic:blipFill>
                  <pic:spPr>
                    <a:xfrm rot="5400000"/>
                  </pic:spPr>
                </pic:pic>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
    <w:p>
      <w:drawing>
        <wp:anchor distT="0" distB="0" distL="114300" distR="114300"
                   relativeHeight="251659264" behindDoc="0">
          <wp:positionH relativeFrom="column">
            <wp:posOffset>381000</wp:posOffset>
          </wp:positionH>
          <wp:positionV relativeFrom="paragraph">
            <wp:posOffset>254000</wp:posOffset>
          </wp:positionV>
          <wp:extent cx="2540000" cy="1270000"/>
          <wp:wrapSquare wrapText="bothSides"/>
          <wp:docPr id="2" name="FloatingAnchorPic" descr="Floating banner"/>
          <a:graphic>
            <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
              <pic:pic>
                <pic:blipFill>
                  <a:blip r:embed="rIdImg1"/>
                </pic:blipFill>
              </pic:pic>
            </a:graphicData>
          </a:graphic>
        </wp:anchor>
      </w:drawing>
    </w:p>
  </w:body>
</w:document>"""

    fake_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00"
        b"\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    pkg_bytes = _make_docx_package(
        {
            "word/document.xml": doc_xml,
            "word/media/image1.png": fake_png,
        }
    )

    doc = read_docx(pkg_bytes)

    # 1. Inspect Paragraph 0: Inline picture
    p0 = doc.main.blocks[0]
    assert len(p0.runs) == 1
    pic1 = p0.runs[0]
    assert isinstance(pic1, PictureItem)
    assert pic1.name == "InlinePicture1"
    assert pic1.alt_text == "Alt description for picture 1"
    assert pic1.image_part == "word/media/image1.png"
    # 1270000 EMU / 12700 = 100 pt
    assert pic1.width == pytest.approx(100.0)
    # 635000 EMU / 12700 = 50 pt
    assert pic1.height == pytest.approx(50.0)
    # Crop: 10000 / 100000 = 0.1
    assert pic1.crop.left == pytest.approx(0.1)
    assert pic1.crop.top == pytest.approx(0.2)
    # Rotation: 5400000 / 60000 = 90 degrees
    assert pic1.rotation == pytest.approx(90.0)
    assert pic1.float_pr is None  # Inline

    # 2. Inspect Paragraph 1: Anchor picture
    p1 = doc.main.blocks[1]
    assert len(p1.runs) == 1
    pic2 = p1.runs[0]
    assert isinstance(pic2, PictureItem)
    assert pic2.name == "FloatingAnchorPic"
    assert pic2.width == pytest.approx(200.0)  # 2540000 / 12700
    assert pic2.height == pytest.approx(100.0)  # 1270000 / 12700
    assert pic2.float_pr is not None
    assert pic2.float_pr.wrap == WrapMode.SQUARE
    assert pic2.float_pr.pos_h.rel == "column"
    assert pic2.float_pr.pos_h.offset == pytest.approx(30.0)  # 381000 / 12700
    assert pic2.float_pr.pos_v.rel == "paragraph"
    assert pic2.float_pr.pos_v.offset == pytest.approx(
        20.0
    )  # 2540000 / 12700 = 20.0 (or 254000/12700=20)
    assert pic2.float_pr.dist.left == pytest.approx(9.0)  # 114300 / 12700 = 9.0


def test_vml_pict_backward_compat() -> None:
    """Test reading legacy VML picture element w:pict."""
    doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:v="urn:schemas-microsoft-com:vml"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p>
      <w:r>
        <w:pict>
          <v:shape id="Picture_x0020_1"
                   style="width:144pt;height:72pt;position:absolute;margin-left:18pt;margin-top:24pt;z-index:251658240">
            <v:imagedata r:id="rIdImg1" title="Legacy VML Logo"/>
          </v:shape>
        </w:pict>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""

    pkg_bytes = _make_docx_package(
        {
            "word/document.xml": doc_xml,
            "word/media/image1.png": b"fake_png_data",
        }
    )

    doc = read_docx(pkg_bytes)
    p0 = doc.main.blocks[0]
    assert len(p0.runs) == 1
    pic = p0.runs[0]
    assert isinstance(pic, PictureItem)
    assert pic.image_part == "word/media/image1.png"
    assert pic.width == pytest.approx(144.0)
    assert pic.height == pytest.approx(72.0)
    assert pic.alt_text == "Legacy VML Logo"
    assert pic.float_pr is not None
    assert pic.float_pr.pos_h.offset == pytest.approx(18.0)
    assert pic.float_pr.pos_v.offset == pytest.approx(24.0)


def test_footnotes_endnotes_bookmarks_and_sections() -> None:
    """Test reading footnotes, endnotes, bookmark catalog, and section layout."""
    fn_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="1">
    <w:p><w:r><w:t>Footnote explanation text</w:t></w:r></w:p>
  </w:footnote>
</w:footnotes>"""

    en_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:endnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:endnote w:id="2">
    <w:p><w:r><w:t>Endnote bibliographic reference</w:t></w:r></w:p>
  </w:endnote>
</w:endnotes>"""

    doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:bookmarkStart w:id="0" w:name="SectionIntro"/>
      <w:r><w:t>Main text with note</w:t></w:r>
      <w:r>
        <w:footnoteReference w:id="1"/>
      </w:r>
      <w:r>
        <w:endnoteReference w:id="2"/>
      </w:r>
      <w:bookmarkEnd w:id="0"/>
    </w:p>
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840" w:orient="landscape"/>
      <w:pgMar w:top="1440" w:bottom="1440" w:left="1440" w:right="1440"/>
      <w:cols w:num="2" w:space="720"/>
    </w:sectPr>
  </w:body>
</w:document>"""

    pkg_bytes = _make_docx_package(
        {
            "word/footnotes.xml": fn_xml,
            "word/endnotes.xml": en_xml,
            "word/document.xml": doc_xml,
        }
    )

    doc = read_docx(pkg_bytes)

    # Footnotes and Endnotes stories
    assert "1" in doc.fn
    assert len(doc.fn["1"].blocks) == 1
    assert "2" in doc.en
    assert len(doc.en["2"].blocks) == 1

    # Bookmarks
    assert "bookmarks" in doc.props
    assert doc.props["bookmarks"].get("SectionIntro") == 0

    # Section layout
    assert doc.sect.orient == "landscape"
    assert doc.sect.pg_w == pytest.approx(612.0)  # 12240 / 20
    assert doc.sect.pg_h == pytest.approx(792.0)  # 15840 / 20
    assert doc.sect.cols.num == 2

    # Inline note refs
    p0 = doc.main.blocks[0]
    note_refs = [r for r in p0.runs if isinstance(r, NoteRefItem)]
    assert len(note_refs) == 2
    assert note_refs[0].kind == "fn"
    assert note_refs[0].note_id == "1"
    assert note_refs[1].kind == "en"
    assert note_refs[1].note_id == "2"
