"""A run can explicitly switch off strike formatting inherited from a style."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile

import pytest

from atboffice.modules.writer.io import read_docx, write_docx
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TextItem,
    normalize,
)
from atboffice.modules.writer.models.properties import RunProperties
from atboffice.modules.writer.models.styles import Style, merge_r_props, resolve_r_props

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@pytest.mark.parametrize(
    ("attr", "off_attr"),
    [("strike", "strike_off"), ("dstrike", "dstrike_off")],
)
def test_merge_explicit_off_clears_inherited_value(attr: str, off_attr: str) -> None:
    base = RunProperties(**{attr: True})
    merged = merge_r_props(base, RunProperties(**{off_attr: True}))

    assert getattr(merged, attr) is False


@pytest.mark.parametrize("attr", ["strike", "dstrike"])
def test_merge_unset_run_keeps_inherited_value(attr: str) -> None:
    merged = merge_r_props(RunProperties(**{attr: True}), RunProperties())

    assert getattr(merged, attr) is True


def test_merge_later_style_can_turn_strike_back_on() -> None:
    off = merge_r_props(RunProperties(strike=True), RunProperties(strike_off=True))
    on_again = merge_r_props(off, RunProperties(strike=True))

    assert on_again.strike is True
    assert on_again.strike_off is False


def _doc_with_strike_style(run: RunProperties) -> tuple[Document, Paragraph, TextItem]:
    doc = Document()
    doc.styles["Struck"] = Style(
        id="Struck",
        name="Struck",
        style_type="character",
        r_pr=RunProperties(strike=True, dstrike=False),
    )
    run.style = "Struck"
    item = TextItem(text="Text", r_pr=run)
    para = Paragraph(runs=[item])
    doc.main.blocks = [para]
    return doc, para, item


def test_resolve_run_off_overrides_character_style() -> None:
    doc, para, item = _doc_with_strike_style(RunProperties(strike_off=True))

    assert resolve_r_props(doc, para, item).strike is False


def test_resolve_run_without_override_inherits_character_style() -> None:
    doc, para, item = _doc_with_strike_style(RunProperties())

    assert resolve_r_props(doc, para, item).strike is True


def _strike_elements(docx_bytes: bytes) -> list[ET.Element]:
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    return root.findall(f".//{W_NS}r/{W_NS}rPr/{W_NS}strike")


def test_docx_round_trip_preserves_explicit_off() -> None:
    doc, _, _ = _doc_with_strike_style(RunProperties(strike_off=True))
    data = write_docx(doc)

    elements = _strike_elements(data)
    assert [el.get(f"{W_NS}val") for el in elements] == ["0"]

    loaded = read_docx(data)
    para = loaded.main.blocks[0]
    assert para.runs[0].r_pr.strike_off is True
    assert resolve_r_props(loaded, para, para.runs[0]).strike is False


def test_docx_writer_omits_strike_when_unset() -> None:
    doc = Document()
    doc.main.blocks = [Paragraph(runs=[TextItem(text="Text", r_pr=RunProperties())])]

    assert _strike_elements(write_docx(doc)) == []


def test_normalize_keeps_explicit_off_run_separate() -> None:
    para = Paragraph(
        runs=[
            TextItem(text="inherits", r_pr=RunProperties()),
            TextItem(text="off", r_pr=RunProperties(strike_off=True)),
        ]
    )

    assert len(normalize(para).runs) == 2
