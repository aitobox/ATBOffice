"""Resilience and fault-isolation unit tests for PresentationML reading and chart scaling."""

from __future__ import annotations

import io
import zipfile

import pytest

from atboffice.modules.presentation.chart.scale import scale as compute_chart_scale
from atboffice.modules.presentation.io import pptx_reader, read_pptx, write_pptx
from atboffice.modules.presentation.models.presentation import LoadWarning, Presentation
from atboffice.modules.presentation.models.shape import PlaceholderInfo, Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import TextBody
from atboffice.vfs.opc import SourcePackage


def _mutate_zip_part(raw_bytes: bytes, replacements: dict[str, bytes]) -> bytes:
    """Return a modified ZIP archive with specific part payloads replaced."""
    src_buf = io.BytesIO(raw_bytes)
    dst_buf = io.BytesIO()
    with zipfile.ZipFile(src_buf, "r") as zin, zipfile.ZipFile(dst_buf, "w") as zout:
        written: set[str] = set()
        for info in zin.infolist():
            name = info.filename
            data = replacements.get(name, zin.read(name))
            zout.writestr(info, data)
            written.add(name)
        for name, data in replacements.items():
            if name not in written:
                zout.writestr(name, data)
    return dst_buf.getvalue()


def test_safe_int_and_safe_float_handle_percent_nan_empty():
    """safe_int and safe_float safely coerce percentages and reject NaN/Inf/empty."""
    assert pptx_reader.safe_int("42") == 42
    assert pptx_reader.safe_int("50.8") == 50
    assert pptx_reader.safe_int("75%", default=-1) == 75
    assert pptx_reader.safe_int("", default=7) == 7
    assert pptx_reader.safe_int(None, default=9) == 9
    assert pptx_reader.safe_int("not-a-number", default=3) == 3
    assert pptx_reader.safe_int("nan", default=5) == 5

    assert pptx_reader.safe_float("12.5") == pytest.approx(12.5)
    assert pptx_reader.safe_float("25.5%") == pytest.approx(25.5)
    assert pptx_reader.safe_float("nan", default=1.0) == pytest.approx(1.0)
    assert pptx_reader.safe_float("inf", default=2.0) == pytest.approx(2.0)
    assert pptx_reader.safe_float("-inf", default=3.0) == pytest.approx(3.0)
    assert pptx_reader.safe_float("", default=4.5) == pytest.approx(4.5)
    assert pptx_reader.safe_float(None, default=6.25) == pytest.approx(6.25)


def test_read_pptx_isolates_broken_chart_and_populates_load_warnings():
    """A corrupt chart XML part degrades gracefully without losing the slide or source package."""
    pres = Presentation.create_new(title="Chart Test", empty=True)
    slide = Slide(id="s1", layout="blank")
    slide.add_shape(
        Shape(
            id="t1",
            type="text",
            name="Title 1",
            x=40.0,
            y=30.0,
            w=400.0,
            h=60.0,
            text=TextBody.from_plain_text("Surviving Text"),
        )
    )
    chart_shape = Shape(
        id="c1",
        type="chart",
        name="Chart 1",
        x=100.0,
        y=120.0,
        w=500.0,
        h=300.0,
        chart={
            "type": "bar",
            "title": "Sales",
            "categories": ["Q1", "Q2"],
            "series": [{"name": "2026", "values": [10.0, 20.0]}],
        },
    )
    slide.add_shape(chart_shape)
    pres.slides.append(slide)

    valid_bytes = write_pptx(pres)
    corrupt_bytes = _mutate_zip_part(
        valid_bytes,
        {"ppt/charts/chart1.xml": b"<c:chartSpace><broken"},
    )

    restored = read_pptx(corrupt_bytes)
    assert restored.props.get("_source_package") is not None
    assert len(restored.slides) == 1
    assert any(
        s.text and "Surviving Text" in s.text.to_plain_text() for s in restored.slides[0].shapes
    )
    assert any(isinstance(w, LoadWarning) and w.scope == "chart" for w in restored.load_warnings)


def test_read_pptx_isolates_corrupt_slide_xml_while_loading_valid_slides():
    """Corrupt XML in slide 1 degrades slide 1 cleanly while slide 2 still loads intact."""
    pres = Presentation.create_new(title="Two Slides", empty=True)
    s1 = Slide(id="s1", layout="blank")
    s1.add_shape(
        Shape(
            id="t1",
            type="text",
            name="Bad Slide Title",
            x=50.0,
            y=50.0,
            w=400.0,
            h=80.0,
            text=TextBody.from_plain_text("Will Break"),
        )
    )
    s2 = Slide(id="s2", layout="title")
    s2.add_shape(
        Shape(
            id="t2",
            type="text",
            name="Good Slide Title",
            x=50.0,
            y=50.0,
            w=400.0,
            h=80.0,
            placeholder=PlaceholderInfo(type="title", idx=0),
            text=TextBody.from_plain_text("Intact Slide Two"),
        )
    )
    pres.slides.extend([s1, s2])

    valid_bytes = write_pptx(pres)
    corrupt_bytes = _mutate_zip_part(
        valid_bytes,
        {"ppt/slides/slide1.xml": b"<<<not xml at all>>>"},
    )

    restored = read_pptx(corrupt_bytes)
    assert len(restored.slides) == 2
    assert restored.slides[1].get_title() == "Intact Slide Two"
    assert any(isinstance(w, LoadWarning) and w.scope == "slide" for w in restored.load_warnings)
    # LoadWarning should not break Presentation equality or to_dict serialization
    assert "load_warnings" not in restored.to_dict()


def test_source_package_tolerates_corrupt_optional_zip_member():
    """SourcePackage.from_bytes isolates corrupt optional ZIP streams."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        zf.writestr("ppt/media/corrupt.bin", b"A" * 256)
    raw = bytearray(buf.getvalue())

    # Flip compressed payload bytes only for the second entry (ppt/media/corrupt.bin)
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        info = zf.getinfo("ppt/media/corrupt.bin")
        data_offset = info.header_offset + 30 + len(info.filename.encode("utf-8")) + len(info.extra)
        corrupt_end = min(len(raw), data_offset + max(1, info.compress_size))
        for idx in range(data_offset, corrupt_end):
            raw[idx] ^= 0xFF

    pkg = SourcePackage.from_bytes(bytes(raw))
    assert pkg.has_part("[Content_Types].xml")
    assert "ppt/media/corrupt.bin" in pkg._corrupt_parts


def test_chart_scale_terminates_on_extreme_log_or_tiny_step():
    """Axis scale tick generation stays bounded on extreme log ranges or tiny steps."""
    log_result = compute_chart_scale(
        1e-12,
        1e12,
        ax={"log": 10, "min": 1e-12, "max": 1e12, "base": 10},
        length=400.0,
        label_sz=24.0,
    )
    assert len(log_result["ticks"]) <= 512

    tiny_step_result = compute_chart_scale(
        0.0,
        1e9,
        ax={"min": 0.0, "max": 1e9, "major": 1e-12},
        length=400.0,
        label_sz=24.0,
    )
    assert len(tiny_step_result["ticks"]) <= 512

    bad_str_result = compute_chart_scale(
        10.0,
        20.0,
        ax={"min": "bad", "max": "NaN", "major": "0"},
        length=400.0,
        label_sz=24.0,
    )
    assert len(bad_str_result["ticks"]) >= 1
