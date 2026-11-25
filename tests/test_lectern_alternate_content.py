"""Lectern: mc:AlternateContent resolution, OMML math text and AC round trip (issue #377)."""

from __future__ import annotations

import io
import re
from atboffice.vfs import etree as ET
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.presentation.io.alternate_content import select_branch
from atboffice.modules.presentation.io.pptx_reader import read_pptx
from atboffice.modules.presentation.io.pptx_writer import write_pptx
from atboffice.modules.presentation.models.shape import Shape

FIXTURE = Path(__file__).parent / "docs" / "powerpoint" / "pptx" / "libreoffice__tdf129372.pptx"
SLIDE = "ppt/slides/slide1.xml"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
PARTIAL = "\U0001d715"  # MATHEMATICAL ITALIC PARTIAL DIFFERENTIAL, as stored in the fixture

pytestmark = pytest.mark.skipif(not FIXTURE.exists(), reason="fixture missing")


def _slide_xml(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return zf.read(SLIDE).decode("utf-8")


def _rewrite_slide(transform) -> bytes:
    """Return the fixture package with slide1.xml passed through ``transform``."""
    src = FIXTURE.read_bytes()
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src)) as zin, zipfile.ZipFile(out, "w") as zout:
        for item in zin.infolist():
            payload = zin.read(item.filename)
            if item.filename == SLIDE:
                payload = transform(payload.decode("utf-8")).encode("utf-8")
            zout.writestr(item, payload)
    return out.getvalue()


def _ac_count(xml: str) -> int:
    root = ET.fromstring(xml.encode("utf-8"))
    return sum(1 for _ in root.iter(f"{{{MC}}}AlternateContent"))


def _all_text(shape: Shape) -> str:
    parts = [shape.text.plain_text] if shape.text else []
    parts.extend(_all_text(k) for k in shape.kids)
    return "".join(parts)


# --- branch selection -------------------------------------------------------------


def _ac(xml_body: str) -> ET.Element:
    return ET.fromstring(f'<mc:AlternateContent xmlns:mc="{MC}">{xml_body}</mc:AlternateContent>')


def test_select_branch_prefers_supported_choice() -> None:
    ac = _ac('<mc:Choice Requires="a14"><x/></mc:Choice><mc:Fallback><y/></mc:Fallback>')
    branch = select_branch(ac)
    assert branch is not None and branch[0].tag == "x"


def test_select_branch_uses_fallback_for_unsupported_choice() -> None:
    ac = _ac('<mc:Choice Requires="p14 a14"><x/></mc:Choice><mc:Fallback><y/></mc:Fallback>')
    branch = select_branch(ac)
    assert branch is not None and branch[0].tag == "y"


def test_select_branch_empty_returns_none() -> None:
    assert select_branch(_ac('<mc:Choice Requires="zz"><x/></mc:Choice><mc:Fallback/>')) is None
    assert select_branch(_ac("")) is None


# --- reading ------------------------------------------------------------------------


def test_math_slide_has_centered_partial_symbol() -> None:
    pres = read_pptx(FIXTURE)
    slide = pres.slides[0]
    assert len(slide.shapes) >= 1
    math_shapes = [s for s in slide.shapes if PARTIAL in _all_text(s)]
    assert math_shapes, "the math symbol must survive as shape text"
    shape = math_shapes[0]
    cx, cy = shape.x + shape.w / 2, shape.y + shape.h / 2
    assert abs(cx - pres.w / 2) < pres.w * 0.1
    assert abs(cy - pres.h / 2) < pres.h * 0.1

    run = next(r for p in shape.text.paragraphs for r in p.runs if PARTIAL in r.text)
    assert run.math is not None
    assert run.font == "Cambria Math"
    assert shape.type != "image"


def test_unsupported_choice_falls_back_to_picture_fill() -> None:
    data = _rewrite_slide(lambda s: s.replace('Requires="a14"', 'Requires="zz9"'))
    pres = read_pptx(data)
    shapes = pres.slides[0].shapes
    assert len(shapes) == 1
    assert shapes[0].type == "image" and shapes[0].media == "ppt/media/image1.png"
    assert PARTIAL not in _all_text(shapes[0])


def test_alternate_content_inside_group() -> None:
    def wrap_in_group(s: str) -> str:
        start = s.index("<mc:AlternateContent")
        end = s.index("</mc:AlternateContent>") + len("</mc:AlternateContent>")
        grp = (
            '<p:grpSp><p:nvGrpSpPr><p:cNvPr id="10" name="Group 9"/><p:cNvGrpSpPr/><p:nvPr/>'
            '</p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="12192000" '
            'cy="6858000"/><a:chOff x="0" y="0"/><a:chExt cx="12192000" cy="6858000"/>'
            "</a:xfrm></p:grpSpPr>" + s[start:end] + "</p:grpSp>"
        )
        return s[:start] + grp + s[end:]

    pres = read_pptx(_rewrite_slide(wrap_in_group))
    group = pres.slides[0].shapes[0]
    assert group.type == "group"
    assert PARTIAL in _all_text(group)


def test_alternate_content_inside_paragraph() -> None:
    def para_level(s: str) -> str:
        # Turn the slide-level AC into a plain sp whose paragraph carries the AC.
        start = s.index("<mc:AlternateContent")
        end = s.index("</mc:AlternateContent>") + len("</mc:AlternateContent>")
        block = s[start:end]
        m_start = block.index("<a14:m>")
        m_end = block.index("</a14:m>") + len("</a14:m>")
        math = block[m_start:m_end]
        sp = (
            '<p:sp><p:nvSpPr><p:cNvPr id="5" name="TextBox 4"/><p:cNvSpPr txBox="1"/><p:nvPr/>'
            '</p:nvSpPr><p:spPr><a:xfrm><a:off x="100" y="100"/><a:ext cx="1000000" cy="400000"/>'
            "</a:xfrm></p:spPr><p:txBody><a:bodyPr/><a:p>"
            f'<a:r><a:t>f = </a:t></a:r><mc:AlternateContent xmlns:mc="{MC}">'
            '<mc:Choice xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main" '
            f'Requires="a14">{math}</mc:Choice><mc:Fallback><a:r><a:t>[math]</a:t></a:r>'
            "</mc:Fallback></mc:AlternateContent></a:p></p:txBody></p:sp>"
        )
        return s[:start] + sp + s[end:]

    pres = read_pptx(_rewrite_slide(para_level))
    text = _all_text(pres.slides[0].shapes[0])
    assert text.startswith("f = ")
    assert PARTIAL in text and "[math]" not in text


# --- round trip ---------------------------------------------------------------------


def test_roundtrip_unmodified_keeps_alternate_content() -> None:
    before = _ac_count(_slide_xml(FIXTURE.read_bytes()))
    out = write_pptx(read_pptx(FIXTURE))
    assert _ac_count(_slide_xml(out)) == before == 1


def test_roundtrip_dirty_slide_rewrites_alternate_content_verbatim() -> None:
    pres = read_pptx(FIXTURE)
    slide = pres.slides[0]
    slide.shapes.append(Shape(id="extra", type="shape", x=10, y=10, w=50, h=50))
    out = write_pptx(pres)
    xml = _slide_xml(out)
    assert _ac_count(xml) == 1
    assert 'Requires="a14"' in xml and "xmlns:a14=" in xml

    # Fallback picture relationship must point at an existing image part.
    rid = re.search(r'r:embed="(rId\d+)"', xml).group(1)
    with zipfile.ZipFile(io.BytesIO(out)) as zf:
        rels = zf.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
        target = re.search(rf'Id="{rid}"[^>]*Target="([^"]+)"', rels) or re.search(
            rf'Target="([^"]+)"[^>]*Id="{rid}"', rels
        )
        assert target is not None
        assert "ppt/media/" + target.group(1).rsplit("/", 1)[-1] in zf.namelist()

    # Ids are unique across the slide and both branches share the shape id.
    ids = re.findall(r'<p:cNvPr id="(\d+)"', xml)
    choice_id, fallback_id = ids[-3], ids[-2]  # AC shape (Choice, Fallback) then extra shape
    assert choice_id == fallback_id
    assert len(set(ids)) == len(ids) - 1

    reread = read_pptx(out)
    assert any(PARTIAL in _all_text(s) for s in reread.slides[0].shapes)


def test_edited_shape_is_serialized_from_model() -> None:
    pres = read_pptx(FIXTURE)
    shape = pres.slides[0].shapes[0]
    shape.x += 20
    out = write_pptx(pres)
    xml = _slide_xml(out)
    assert _ac_count(xml) == 0
    reread = read_pptx(out)
    assert any(PARTIAL in _all_text(s) for s in reread.slides[0].shapes)


# --- painting -----------------------------------------------------------------------


def test_math_glyph_is_painted_near_slide_center(qapp) -> None:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from atboffice.modules.presentation.views.slide_canvas import SlideScene

    pres = read_pptx(FIXTURE)
    scene = SlideScene(slide=pres.slides[0], presentation=pres)
    w, h = int(pres.w), int(pres.h)
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("white"))
    painter = QPainter(img)
    scene.render(painter, QRectF(0, 0, w, h), QRectF(0, 0, w, h))
    painter.end()

    # Ignore the 2px slide frame; look for ink in the middle of the slide.
    dark = [
        (x, y)
        for y in range(4, h - 4)
        for x in range(4, w - 4)
        if QColor(img.pixel(x, y)).lightness() < 100
    ]
    assert dark, "math glyph was not painted"
    cx = sum(x for x, _ in dark) / len(dark)
    cy = sum(y for _, y in dark) / len(dark)
    assert abs(cx - w / 2) < w * 0.05
    assert abs(cy - h / 2) < h * 0.05
