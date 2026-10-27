"""Comprehensive unit tests for ECMA-376 PresentationML I/O and lossless preservation."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile

from atboffice.modules.presentation.io import (
    PptxReader,
    PptxWriter,
    read_pptx,
    write_pptx,
)
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Fill, Line, PlaceholderInfo, Shadow, Shape
from atboffice.modules.presentation.models.slide import Slide, Transition
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun
from atboffice.vfs.opc import SourcePackage
from atboffice.vfs.order import SCHEMA_ORDERS


def test_presentation_io_module_exports():
    """Verify standard API exports."""
    assert callable(read_pptx)
    assert callable(write_pptx)
    assert PptxReader is not None
    assert PptxWriter is not None


def test_pptx_clean_roundtrip_from_scratch():
    """Verify creating a presentation from scratch, writing to PPTX, and reading back."""
    pres = Presentation.create_new(title="Quarterly Review", empty=True)
    pres.w = 960.0
    pres.h = 540.0

    slide1 = Slide(id="s1", layout="title")
    title_box = Shape(
        id="t1",
        type="text",
        name="Title 1",
        x=100.0,
        y=150.0,
        w=760.0,
        h=100.0,
        placeholder=PlaceholderInfo(type="title", idx=0),
        text=TextBody.from_plain_text("Welcome to Lectern"),
    )
    slide1.add_shape(title_box)
    pres.slides.append(slide1)

    # Write to bytes
    pptx_bytes = write_pptx(pres)
    assert len(pptx_bytes) > 0

    # Read back
    restored = read_pptx(pptx_bytes)
    assert len(restored.slides) == 1
    assert restored.w == 960.0
    assert restored.h == 540.0
    assert restored.slides[0].get_title() == "Welcome to Lectern"


def test_pptx_ppsx_potx_content_types():
    """Verify distinct Content-Type headers for pptx, ppsx, and potx formats."""
    pres = Presentation.create_new(title="Formats Test", empty=True)
    pres.slides.append(Slide(id="s1", layout="blank"))

    formats = {
        "pptx": (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
        ),
        "ppsx": (
            "application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml"
        ),
        "potx": (
            "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"
        ),
    }

    for fmt, expected_ct in formats.items():
        data = write_pptx(pres, format=fmt)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            ct_xml = zf.read("[Content_Types].xml")
            root = ET.fromstring(ct_xml)
            found = False
            for override in root.findall(
                "{http://schemas.openxmlformats.org/package/2006/content-types}Override"
            ):
                if override.attrib.get("PartName") == "/ppt/presentation.xml":
                    assert override.attrib.get("ContentType") == expected_ct
                    found = True
                    break
            assert found, f"Override for /ppt/presentation.xml not found in {fmt}"


def test_rich_text_formatting_roundtrip():
    """Verify font styling, colors, sizes, alignment, and run properties."""
    pres = Presentation.create_new(title="Rich Text", empty=True)
    slide = Slide(id="s1", layout="text")

    run1 = TextRun(text="Bold Accent", bold=True, size=28.0, color="accent1", font="Trebuchet MS")
    run2 = TextRun(text=" Italic Dark", italic=True, size=24.0, color="dk1", font="Calibri")
    para1 = Paragraph(level=0, props={"algn": "ctr"}, runs=[run1, run2])

    run3 = TextRun(text="Underline Strike", underline=True, strike=True, size=18.0)
    para2 = Paragraph(level=1, props={"algn": "l"}, runs=[run3])

    tx = TextBody(paragraphs=[para1, para2])
    sh = Shape(id="box1", type="text", name="TextBox 1", x=50.0, y=50.0, w=500.0, h=300.0, text=tx)
    slide.add_shape(sh)
    pres.slides.append(slide)

    data = write_pptx(pres)
    restored = read_pptx(data)

    s0 = restored.slides[0]
    sh_restored = s0.shapes[0]
    assert sh_restored.text is not None
    assert len(sh_restored.text.paragraphs) == 2

    p0 = sh_restored.text.paragraphs[0]
    assert len(p0.runs) == 2
    assert p0.runs[0].bold is True
    assert p0.runs[0].size == 28.0
    assert p0.runs[1].italic is True

    p1 = sh_restored.text.paragraphs[1]
    assert p1.runs[0].underline is True
    assert p1.runs[0].strike is True


def test_shapes_and_geometries():
    """Verify shapes with fill styles, line styles, shadows, and coordinates."""
    pres = Presentation.create_new(title="Geometry", empty=True)
    slide = Slide(id="s1", layout="blank")

    sh_rect = Shape(
        id="rect1",
        geom="roundRect",
        x=80.0,
        y=90.0,
        w=200.0,
        h=120.0,
        fill=Fill.solid("accent2", alpha=0.85),
        line=Line(color="dk1", width=2.0, dash="dash"),
        shadow=Shadow(color="#000000", alpha=0.3, dist=5.0, blur=4.0),
    )

    stops = [{"p": 0.0, "c": "#FF0000"}, {"p": 1.0, "c": "#0000FF"}]
    sh_ellipse = Shape(
        id="el1",
        geom="ellipse",
        x=350.0,
        y=90.0,
        w=150.0,
        h=150.0,
        fill=Fill.gradient(stops, angle=45.0),
        line=Line(width=0),
    )

    slide.add_shape(sh_rect)
    slide.add_shape(sh_ellipse)
    pres.slides.append(slide)

    data = write_pptx(pres)
    restored = read_pptx(data)

    shapes = restored.slides[0].shapes
    assert len(shapes) == 2

    r0 = shapes[0]
    assert r0.geom == "roundRect"
    assert r0.x == 80.0
    assert r0.y == 90.0
    assert r0.fill.color == "accent2"

    r1 = shapes[1]
    assert r1.geom == "ellipse"
    assert r1.fill.type == "grad"
    assert len(r1.fill.stops) == 2


def test_table_serialization_and_deserialization():
    """Verify table frames with columns, rows, and cell texts."""
    pres = Presentation.create_new(title="Table Test", empty=True)
    slide = Slide(id="s1", layout="blank")

    tbl_data = {
        "cols": [200.0, 300.0],
        "rows": [
            {
                "h": 40.0,
                "cells": [
                    {"tx": TextBody.from_plain_text("Header 1")},
                    {"tx": TextBody.from_plain_text("Header 2")},
                ],
            },
            {
                "h": 35.0,
                "cells": [
                    {"tx": TextBody.from_plain_text("Data 1")},
                    {"tx": TextBody.from_plain_text("Data 2")},
                ],
            },
        ],
    }

    tbl_shape = Shape(
        id="tbl1",
        type="table",
        name="Table 1",
        x=50.0,
        y=50.0,
        w=500.0,
        h=75.0,
        tbl=tbl_data,
    )
    slide.add_shape(tbl_shape)
    pres.slides.append(slide)

    data = write_pptx(pres)
    restored = read_pptx(data)

    s0 = restored.slides[0]
    assert len(s0.shapes) == 1
    t_restored = s0.shapes[0]
    assert t_restored.type == "table"
    assert t_restored.tbl is not None
    assert len(t_restored.tbl["rows"]) == 2
    assert t_restored.tbl["rows"][0]["cells"][0]["tx"].plain_text == "Header 1"
    assert t_restored.tbl["rows"][1]["cells"][1]["tx"].plain_text == "Data 2"


def test_picture_embedding_and_extraction():
    """Verify embedding picture bytes and extracting via reader."""
    pres = Presentation.create_new(title="Picture Test", empty=True)
    slide = Slide(id="s1", layout="blank")

    dummy_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    pres.props["_media_map"] = {"img_logo.png": dummy_png}

    pic = Shape(
        id="pic1",
        type="image",
        name="Logo Picture",
        x=100.0,
        y=100.0,
        w=200.0,
        h=200.0,
        media="img_logo.png",
    )
    slide.add_shape(pic)
    pres.slides.append(slide)

    data = write_pptx(pres)
    restored = read_pptx(data)

    s0 = restored.slides[0]
    assert len(s0.shapes) == 1
    p0 = s0.shapes[0]
    assert p0.type == "image"
    assert p0.media is not None
    # Verify the image bytes were preserved in restored media_map
    media_map = restored.props.get("_media_map", {})
    assert p0.media in media_map
    assert media_map[p0.media] == dummy_png


def test_slide_transitions_and_notes():
    """Verify slide transition timing and speaker notes extraction."""
    pres = Presentation.create_new(title="Transitions", empty=True)
    slide = Slide(
        id="s1",
        layout="blank",
        notes="Important meeting talking points:\n1. Revenue growth\n2. Next steps",
        transition=Transition(type="wipe", speed="med", click=False, after=3.5),
    )
    pres.slides.append(slide)

    data = write_pptx(pres)
    restored = read_pptx(data)

    s0 = restored.slides[0]
    assert "Important meeting talking points:" in s0.notes
    assert "1. Revenue growth" in s0.notes
    assert s0.transition.type == "wipe"
    assert s0.transition.speed == "med"
    assert s0.transition.click is False
    assert s0.transition.after == 3.5


def test_lossless_preservation_unmodified_slides_byte_identical():
    """Verify editing 1 slide in a 3-slide package preserves other 2 slides byte-for-byte."""
    # 1. Create baseline 3-slide presentation
    pres_orig = Presentation.create_new(title="Lossless Preservation Test", empty=True)
    for i in range(1, 4):
        s = Slide(id=f"slide_{i}", layout="text")
        s.add_shape(
            Shape(
                id=f"title_{i}",
                type="text",
                name=f"Title {i}",
                x=50.0,
                y=50.0,
                w=600.0,
                h=80.0,
                text=TextBody.from_plain_text(f"Slide Number {i} Content"),
            )
        )
        pres_orig.slides.append(s)

    orig_pptx_bytes = write_pptx(pres_orig)

    # 2. Read into reader (sets _source_package and _slide_part_map)
    pres_loaded = read_pptx(orig_pptx_bytes)
    assert len(pres_loaded.slides) == 3

    # Extract original raw XML bytes of slide 1 and slide 3
    orig_pkg = pres_loaded.props["_source_package"]
    assert isinstance(orig_pkg, SourcePackage)
    slide1_raw_before = orig_pkg.read_part("ppt/slides/slide1.xml")
    slide3_raw_before = orig_pkg.read_part("ppt/slides/slide3.xml")

    # 3. Modify ONLY slide 2
    slide2 = pres_loaded.slides[1]
    slide2.shapes.append(
        Shape(
            id="new_box",
            type="text",
            name="New Shape On Slide 2",
            x=100.0,
            y=200.0,
            w=300.0,
            h=50.0,
            text=TextBody.from_plain_text("This slide was edited!"),
        )
    )
    # Slides 1 and 3 are untouched!

    # 4. Write back using lossless carry-over
    modified_pptx_bytes = write_pptx(pres_loaded)

    # 5. Inspect the newly written package ZIP
    with zipfile.ZipFile(io.BytesIO(modified_pptx_bytes)) as zf:
        slide1_raw_after = zf.read("ppt/slides/slide1.xml")
        slide2_raw_after = zf.read("ppt/slides/slide2.xml")
        slide3_raw_after = zf.read("ppt/slides/slide3.xml")

    # Assert 100% byte-for-byte identity for unmodified slides
    assert slide1_raw_after == slide1_raw_before, "Unmodified slide 1 was altered!"
    assert slide3_raw_after == slide3_raw_before, "Unmodified slide 3 was altered!"
    # Assert slide 2 actually changed
    assert b"This slide was edited!" in slide2_raw_after


def test_schema_ordering_conformance():
    """Verify that generated PresentationML XML nodes conform strictly to SCHEMA_ORDERS."""
    pres = Presentation.create_new(title="Schema Order Test", empty=True)
    slide = Slide(id="s1", layout="text")

    sh = Shape(
        id="sp1",
        name="Ordered Shape",
        x=50.0,
        y=50.0,
        w=200.0,
        h=100.0,
        fill=Fill.solid("accent1"),
        line=Line(width=1.0),
        text=TextBody.from_plain_text("Testing order"),
    )
    slide.add_shape(sh)
    pres.slides.append(slide)

    data = write_pptx(pres)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml")
        root = ET.fromstring(slide_xml)

        # Check p:sld child ordering
        sld_expected = SCHEMA_ORDERS["presentationml_slide"]
        children_tags = [c.tag.split("}")[-1] for c in root]
        sld_filtered = [t for t in sld_expected if t in children_tags]
        actual_filtered = [t for t in children_tags if t in sld_expected]
        assert actual_filtered == sld_filtered, (
            f"Slide order mismatch: {actual_filtered} != {sld_filtered}"
        )

        # Check p:sp child ordering
        sp_elem = None
        for el in root.iter():
            if el.tag.endswith("sp") and not el.tag.endswith("grpSp"):
                sp_elem = el
                break
        assert sp_elem is not None
        sp_expected = SCHEMA_ORDERS["presentationml_sp"]
        sp_tags = [c.tag.split("}")[-1] for c in sp_elem]
        sp_filtered = [t for t in sp_expected if t in sp_tags]
        actual_sp = [t for t in sp_tags if t in sp_expected]
        assert actual_sp == sp_filtered, (
            f"Shape order mismatch: {actual_sp} != {sp_filtered}"
        )
