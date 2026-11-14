"""Generate deterministic malformed .pptx fixtures under tests/docs/powerpoint/malformed/."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from atboffice.modules.presentation.io import write_pptx
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Line, PlaceholderInfo, Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import Paragraph, Run, TextBody

OUT_DIR = Path(__file__).resolve().parents[1] / "tests" / "docs" / "powerpoint" / "malformed"


def _rewrite_zip(
    raw_bytes: bytes,
    replacements: dict[str, bytes],
    additions: dict[str, bytes] | None = None,
) -> bytes:
    """Return deterministic ZIP bytes with specified parts replaced or added."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as zin, zipfile.ZipFile(
        out, "w", compression=zipfile.ZIP_DEFLATED
    ) as zout:
        written: set[str] = set()
        for info in zin.infolist():
            name = info.filename
            data = replacements.get(name, zin.read(name))
            zi = zipfile.ZipInfo(filename=name, date_time=(2026, 11, 15, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(zi, data)
            written.add(name)
        for name, data in sorted((additions or {}).items()):
            if name not in written:
                zi = zipfile.ZipInfo(filename=name, date_time=(2026, 11, 15, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(zi, data)
    return out.getvalue()


def _build_malformed_numeric_attrs() -> bytes:
    pres = Presentation.create_new(title="Numeric Edge Cases", empty=True)
    sl = Slide(id="s1", layout="blank")
    sl.add_shape(
        Shape(
            id="t1",
            type="text",
            name="Numeric Box",
            x=40.0,
            y=40.0,
            w=420.0,
            h=120.0,
            text=TextBody.from_plain_text("Numeric Attrs Test"),
        )
    )
    pres.slides.append(sl)
    base = write_pptx(pres)

    with zipfile.ZipFile(io.BytesIO(base), "r") as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")

    # Inject NaN/Inf/percentage/non-numeric attributes into transform and text formatting
    slide_xml = slide_xml.replace('x="508000"', 'x="NaN"', 1)
    slide_xml = slide_xml.replace('y="508000"', 'y="50%"', 1)
    slide_xml = slide_xml.replace('sz="1800"', 'sz="badSize"', 1)
    slide_xml = slide_xml.replace('<a:alpha val="100000"/>', '<a:alpha val="NaN"/>', 1)

    return _rewrite_zip(
        base,
        {"ppt/slides/slide1.xml": slide_xml.encode("utf-8")},
        additions={"ppt/comments/comment1.xml": b"<p:cmLst><broken_comment_xml"},
    )


def _build_broken_chart_and_rels() -> bytes:
    pres = Presentation.create_new(title="Broken Chart", empty=True)
    sl = Slide(id="s1", layout="blank")
    sl.add_shape(
        Shape(
            id="title1",
            type="text",
            name="Surviving Heading",
            x=40.0,
            y=30.0,
            w=400.0,
            h=60.0,
            text=TextBody.from_plain_text("Quarterly Fallback"),
        )
    )
    sl.add_shape(
        Shape(
            id="ch1",
            type="chart",
            name="Corrupt Chart",
            x=80.0,
            y=110.0,
            w=500.0,
            h=300.0,
            chart={
                "type": "bar",
                "title": "Revenue",
                "categories": ["Q1", "Q2"],
                "series": [{"name": "2026", "values": [12.0, 24.0]}],
            },
        )
    )
    pres.slides.append(sl)
    base = write_pptx(pres)

    return _rewrite_zip(
        base,
        {"ppt/charts/chart1.xml": b"<c:chartSpace><c:chart><unclosed"},
    )


def _build_degenerate_shapes_and_cycles() -> bytes:
    pres = Presentation.create_new(title="Degenerate Geometry", empty=True)
    sl = Slide(id="s1", layout="blank")
    sl.add_shape(Shape(id="zero1", type="shape", geom="rect", x=20.0, y=20.0, w=0.0, h=0.0))
    sl.add_shape(Shape(id="dup_id", type="shape", geom="ellipse", x=60.0, y=40.0, w=80.0, h=50.0))
    sl.add_shape(
        Shape(
            id="dup_id",
            type="text",
            x=160.0,
            y=40.0,
            w=240.0,
            h=60.0,
            text=TextBody(
                autofit="norm",
                paragraphs=[
                    Paragraph(
                        runs=[Run(text="Cycle & Degenerate Shapes " * 3, size=14.0)],
                        props={"marL": None, "indent": None},
                    )
                ],
            ),
        )
    )
    sl.add_shape(
        Shape(
            id="cx1",
            type="line",
            geom="straightConnector1",
            x=10.0,
            y=120.0,
            w=120.0,
            h=40.0,
            line=Line(type="solid", color="#112233", width=1.5),
            cxn_start={"id": "cx2", "idx": 0},
            cxn_end={"id": "cx2", "idx": 1},
        )
    )
    sl.add_shape(
        Shape(
            id="cx2",
            type="line",
            geom="straightConnector1",
            x=150.0,
            y=120.0,
            w=120.0,
            h=40.0,
            line=Line(type="solid", color="#445566", width=1.5),
            cxn_start={"id": "cx1", "idx": 0},
            cxn_end={"id": "cx1", "idx": 1},
        )
    )
    sl.add_shape(
        Shape(
            id="tbl1",
            type="table",
            x=40.0,
            y=200.0,
            w=320.0,
            h=100.0,
            tbl={"cols": [0.0, 0.0], "rows": [{"h": 24.0, "cells": []}]},
        )
    )
    sl.add_shape(
        Shape(
            id="img_bad",
            type="image",
            x=400.0,
            y=200.0,
            w=120.0,
            h=90.0,
            media="ppt/media/broken_img.png",
        )
    )
    pres.slides.append(sl)
    base = write_pptx(pres)

    return _rewrite_zip(
        base,
        {},
        additions={"ppt/media/broken_img.png": b"not-a-valid-png-payload"},
    )


def _build_partial_corrupt_slide() -> bytes:
    pres = Presentation.create_new(title="Partial Corrupt Slide", empty=True)
    s1 = Slide(id="s1", layout="blank")
    s1.add_shape(
        Shape(
            id="b1",
            type="text",
            x=40.0,
            y=40.0,
            w=300.0,
            h=60.0,
            text=TextBody.from_plain_text("Broken Slide 1"),
        )
    )
    s2 = Slide(id="s2", layout="title")
    s2.add_shape(
        Shape(
            id="g2",
            type="text",
            x=60.0,
            y=80.0,
            w=400.0,
            h=80.0,
            placeholder=PlaceholderInfo(type="title", idx=0),
            text=TextBody.from_plain_text("Surviving Slide Two"),
        )
    )
    pres.slides.extend([s1, s2])
    base = write_pptx(pres)

    return _rewrite_zip(
        base,
        {"ppt/slides/slide1.xml": b"<?xml version='1.0'?><p:sld><broken_xml_payload"},
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fixtures: dict[str, bytes] = {
        "malformed_numeric_attrs.pptx": _build_malformed_numeric_attrs(),
        "broken_chart_and_rels.pptx": _build_broken_chart_and_rels(),
        "degenerate_shapes_and_cycles.pptx": _build_degenerate_shapes_and_cycles(),
        "partial_corrupt_slide.pptx": _build_partial_corrupt_slide(),
    }
    for name, payload in fixtures.items():
        target = OUT_DIR / name
        target.write_bytes(payload)
        print(f"Wrote {target} ({len(payload)} bytes)")


if __name__ == "__main__":
    main()
