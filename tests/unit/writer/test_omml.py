"""Unit tests for Office Math ML (OMML) models, parsing, serialization, and layout."""

import xml.etree.ElementTree as ET
import pytest

from atboffice.modules.writer.models.omml import (
    OfficeMathItem,
    MathRun,
    MathFraction,
    MathSup,
    MathSub,
    MathSubSup,
    MathRadical,
    MathDelimiter,
    MathNary,
    MathMatrix,
    parse_omml,
    serialize_omml,
    NS_M,
)


def test_parse_fraction():
    xml = f"""<m:oMath xmlns:m="{NS_M}">
        <m:f>
            <m:num><m:r><m:t>1</m:t></m:r></m:num>
            <m:den><m:r><m:t>2</m:t></m:r></m:den>
        </m:f>
    </m:oMath>"""
    item = parse_omml(xml)
    assert isinstance(item, OfficeMathItem)
    assert len(item.nodes) == 1
    frac = item.nodes[0]
    assert isinstance(frac, MathFraction)
    assert len(frac.num) == 1 and isinstance(frac.num[0], MathRun)
    assert frac.num[0].text == "1"
    assert len(frac.den) == 1 and isinstance(frac.den[0], MathRun)
    assert frac.den[0].text == "2"


def test_parse_scripts():
    xml = f"""<m:oMath xmlns:m="{NS_M}">
        <m:sSup>
            <m:e><m:r><m:t>x</m:t></m:r></m:e>
            <m:sup><m:r><m:t>2</m:t></m:r></m:sup>
        </m:sSup>
        <m:sSub>
            <m:e><m:r><m:t>y</m:t></m:r></m:e>
            <m:sub><m:r><m:t>i</m:t></m:r></m:sub>
        </m:sSub>
        <m:sSubSup>
            <m:e><m:r><m:t>z</m:t></m:r></m:e>
            <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
            <m:sup><m:r><m:t>k</m:t></m:r></m:sup>
        </m:sSubSup>
    </m:oMath>"""
    item = parse_omml(xml)
    assert len(item.nodes) == 3
    assert isinstance(item.nodes[0], MathSup)
    assert isinstance(item.nodes[1], MathSub)
    assert isinstance(item.nodes[2], MathSubSup)


def test_parse_radical():
    xml = f"""<m:oMath xmlns:m="{NS_M}">
        <m:rad>
            <m:deg><m:r><m:t>3</m:t></m:r></m:deg>
            <m:e><m:r><m:t>x</m:t></m:r></m:e>
        </m:rad>
    </m:oMath>"""
    item = parse_omml(xml)
    assert len(item.nodes) == 1
    rad = item.nodes[0]
    assert isinstance(rad, MathRadical)
    assert not rad.deg_hide
    assert len(rad.deg) == 1 and rad.deg[0].text == "3"


def test_parse_delimiter():
    xml = f"""<m:oMath xmlns:m="{NS_M}">
        <m:d>
            <m:dPr><m:begChr m:val="["/><m:endChr m:val="]"/></m:dPr>
            <m:e><m:r><m:t>a</m:t></m:r></m:e>
        </m:d>
    </m:oMath>"""
    item = parse_omml(xml)
    assert len(item.nodes) == 1
    d = item.nodes[0]
    assert isinstance(d, MathDelimiter)
    assert d.beg_chr == "["
    assert d.end_chr == "]"
    assert len(d.items) == 1


def test_parse_nary():
    xml = f"""<m:oMath xmlns:m="{NS_M}">
        <m:nary>
            <m:naryPr><m:chr m:val="∫"/></m:naryPr>
            <m:sub><m:r><m:t>0</m:t></m:r></m:sub>
            <m:sup><m:r><m:t>1</m:t></m:r></m:sup>
            <m:e><m:r><m:t>x dx</m:t></m:r></m:e>
        </m:nary>
    </m:oMath>"""
    item = parse_omml(xml)
    assert len(item.nodes) == 1
    nary = item.nodes[0]
    assert isinstance(nary, MathNary)
    assert nary.op == "∫"
    assert len(nary.sub) == 1 and nary.sub[0].text == "0"
    assert len(nary.sup) == 1 and nary.sup[0].text == "1"


def test_parse_matrix():
    xml = f"""<m:oMath xmlns:m="{NS_M}">
        <m:m>
            <m:mr>
                <m:e><m:r><m:t>1</m:t></m:r></m:e>
                <m:e><m:r><m:t>2</m:t></m:r></m:e>
            </m:mr>
            <m:mr>
                <m:e><m:r><m:t>3</m:t></m:r></m:e>
                <m:e><m:r><m:t>4</m:t></m:r></m:e>
            </m:mr>
        </m:m>
    </m:oMath>"""
    item = parse_omml(xml)
    assert len(item.nodes) == 1
    mat = item.nodes[0]
    assert isinstance(mat, MathMatrix)
    assert len(mat.rows) == 2
    assert len(mat.rows[0]) == 2
    assert len(mat.rows[1]) == 2


def test_serialize_roundtrip():
    xml = f"""<m:oMath xmlns:m="{NS_M}"><m:f><m:num><m:r><m:t>a</m:t></m:r></m:num><m:den><m:r><m:t>b</m:t></m:r></m:den></m:f></m:oMath>"""
    item = parse_omml(xml)
    out_elem = serialize_omml(item)
    assert out_elem.tag == f"{{{NS_M}}}oMath"
    serialized_str = ET.tostring(out_elem, encoding="unicode")
    assert "<m:f" in serialized_str or ":f" in serialized_str


def test_math_layout_fraction():
    from atboffice.modules.writer.layout.math_layout import layout_math_item

    xml = f"""<m:oMath xmlns:m="{NS_M}">
        <m:f>
            <m:num><m:r><m:t>1</m:t></m:r></m:num>
            <m:den><m:r><m:t>x + 1</m:t></m:r></m:den>
        </m:f>
    </m:oMath>"""
    item = parse_omml(xml)
    box = layout_math_item(item, font_size=12.0)
    assert box.width > 0
    assert box.height > 12.0  # Fraction is taller than single line
    assert box.ascent > 0
    assert box.descent > 0
    assert item.width == box.width
    assert item.height == box.height


def test_math_layout_scripts_and_radical():
    from atboffice.modules.writer.layout.math_layout import layout_math_item

    xml = f"""<m:oMath xmlns:m="{NS_M}">
        <m:rad>
            <m:deg><m:r><m:t>3</m:t></m:r></m:deg>
            <m:e>
                <m:sSup>
                    <m:e><m:r><m:t>x</m:t></m:r></m:e>
                    <m:sup><m:r><m:t>2</m:t></m:r></m:sup>
                </m:sSup>
            </m:e>
        </m:rad>
    </m:oMath>"""
    item = parse_omml(xml)
    box = layout_math_item(item, font_size=14.0)
    assert box.width > 0
    assert box.height > 0
    assert len(box.render_ops) > 0


def test_paint_math_offscreen(qapp):
    from PySide6.QtGui import QImage, QPainter
    from atboffice.modules.writer.layout.math_layout import layout_math_item, paint_math

    xml = f"""<m:oMath xmlns:m="{NS_M}">
        <m:f>
            <m:num><m:r><m:t>a</m:t></m:r></m:num>
            <m:den><m:r><m:t>b</m:t></m:r></m:den>
        </m:f>
    </m:oMath>"""
    item = parse_omml(xml)
    box = layout_math_item(item, font_size=16.0)

    img = QImage(200, 100, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    painter = QPainter(img)
    try:
        paint_math(painter, item, origin_x=10.0, baseline_y=50.0, zoom=1.0)
    finally:
        painter.end()


def test_portions_math_decomposition():
    from atboffice.modules.writer.layout.portions import decompose_paragraph_to_portions, PortionType
    from atboffice.modules.writer.models.document import Paragraph, TextItem

    p = Paragraph()
    p.runs.append(TextItem("Formula: "))
    xml = f"""<m:oMath xmlns:m="{NS_M}">
        <m:f>
            <m:num><m:r><m:t>1</m:t></m:r></m:num>
            <m:den><m:r><m:t>2</m:t></m:r></m:den>
        </m:f>
    </m:oMath>"""
    math_item = parse_omml(xml)
    p.runs.append(math_item)

    portions = decompose_paragraph_to_portions(p)
    assert len(portions) >= 2
    math_portion = [po for po in portions if po.type == PortionType.GRAPHIC and isinstance(po.data, OfficeMathItem)][0]
    assert math_portion.width > 0
    assert math_portion.ascent > 0
    assert math_portion.counts_for_height is True


def test_docx_math_io_roundtrip():
    import io
    from atboffice.modules.writer.models.document import Document, Paragraph, TextItem
    from atboffice.modules.writer.io.docx_writer import write_docx
    from atboffice.modules.writer.io.docx_reader import read_docx

    doc = Document()
    p = Paragraph(runs=[TextItem("Inline equation: ")])
    xml = f"""<m:oMath xmlns:m="{NS_M}">
        <m:f>
            <m:num><m:r><m:t>E</m:t></m:r></m:num>
            <m:den><m:r><m:t>mc2</m:t></m:r></m:den>
        </m:f>
    </m:oMath>"""
    math_item = parse_omml(xml)
    p.runs.append(math_item)
    doc.main.blocks = [p]

    buf = io.BytesIO()
    write_docx(doc, buf)
    buf.seek(0)

    reloaded = read_docx(buf)
    reloaded_p = reloaded.main.blocks[0]
    math_runs = [r for r in reloaded_p.runs if isinstance(r, OfficeMathItem)]
    assert len(math_runs) == 1
    reloaded_math = math_runs[0]
    assert len(reloaded_math.nodes) == 1
    frac = reloaded_math.nodes[0]
    assert isinstance(frac, MathFraction)
    assert len(frac.num) == 1 and frac.num[0].text == "E"


