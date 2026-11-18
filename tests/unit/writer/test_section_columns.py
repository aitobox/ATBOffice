"""Word section geometry and balancing regressions for Issue #412."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.io import read_docx, write_docx
from atboffice.modules.writer.layout.pagination import paginate_document
from atboffice.modules.writer.models.document import Document, Paragraph, TextItem
from atboffice.modules.writer.models.properties import (
    ColumnsProperties,
    IndentProperties,
    ParagraphProperties,
    RunProperties,
    SectionProperties,
    SpacingProperties,
)

DOCX_DIR = Path(__file__).resolve().parents[2] / "docs" / "word" / "docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _document_with_columns(attributes: str, children: str = "") -> Document:
    """Import actual OOXML column declarations without relying on their writer."""
    doc = Document()
    doc.main.blocks = [Paragraph(runs=[TextItem("A short paragraph.")])]
    source = zipfile.ZipFile(io.BytesIO(write_docx(doc)))
    output = io.BytesIO()
    with source, zipfile.ZipFile(output, "w") as target:
        for name in source.namelist():
            data = source.read(name)
            if name == "word/document.xml":
                root = ET.fromstring(data)
                sect = root.find(f"{W}body/{W}sectPr")
                assert sect is not None
                old = sect.find(f"{W}cols")
                if old is not None:
                    sect.remove(old)
                sect.append(ET.fromstring(
                    f'<w:cols xmlns:w="{W[1:-1]}" {attributes}>{children}</w:cols>'
                ))
                data = ET.tostring(root)
            target.writestr(name, data)
    return read_docx(output.getvalue())


def test_explicit_single_column_wraps_on_first_page(qapp: QApplication) -> None:
    doc = read_docx(DOCX_DIR / "libreoffice__fdo52208.docx")
    result = paginate_document(doc)
    assert result.total_pages == 1
    region = result.pages[0].regions[1]
    assert region.columns[0].width == 100.0
    lines = region.columns[0].fragments[0].lines
    assert len(lines) == 2
    assert "".join(p.text for line in lines for p in line.portions) == (
        "second para, still on the first page"
    )


@pytest.mark.parametrize("equal_width", [None, "0", "false", "off"])
def test_imported_unequal_geometry_survives_save(equal_width: str | None) -> None:
    attr = '' if equal_width is None else f'w:equalWidth="{equal_width}"'
    doc = _document_with_columns(
        f'{attr} w:sep="1"',
        '<w:col w:w="2000" w:space="0"/>'
        '<w:col w:w="4000" w:space="240"/>'
        '<w:col w:w="2160"/>',
    )
    for loaded in [doc, read_docx(write_docx(doc))]:
        cols = loaded.sect.cols
        assert cols.num == 3
        assert cols.equal_width is False
        assert cols.sep is True
        assert cols.widths == [100.0, 200.0, 108.0]
        assert cols.spaces == [0.0, 12.0, 0.0]
        frames = paginate_document(loaded).pages[0].regions[0].columns
        assert [c.width for c in frames] == [100.0, 200.0, 108.0]
        assert [c.left for c in frames] == [0.0, 100.0, 312.0]


def test_equal_columns_keep_zero_gap_and_ignore_explicit_widths() -> None:
    doc = _document_with_columns(
        'w:num="2" w:equalWidth="1" w:space="0"',
        '<w:col w:w="2000"/><w:col w:w="2000"/>',
    )
    frames = paginate_document(doc).pages[0].regions[0].columns
    assert [c.width for c in frames] == [216.0, 216.0]
    assert [c.left for c in frames] == [0.0, 216.0]


@pytest.mark.parametrize("count", ["0", "-2", "invalid"])
def test_invalid_column_count_keeps_explicit_column(count: str) -> None:
    doc = _document_with_columns(
        f'w:num="{count}" w:equalWidth="0"', '<w:col w:w="2000"/>'
    )
    frames = paginate_document(doc).pages[0].regions[0].columns
    assert len(frames) == 1
    assert frames[0].width == 100.0


def test_missing_and_invalid_widths_use_equal_fallback() -> None:
    doc = _document_with_columns(
        'w:num="3" w:equalWidth="0" w:space="240"',
        '<w:col w:w="0" w:space="0"/><w:col w:w="-40"/>',
    )
    frames = paginate_document(doc).pages[0].regions[0].columns
    assert [c.width for c in frames] == [136.0, 136.0, 136.0]
    assert [c.left for c in frames] == [0.0, 136.0, 272.0]


def test_dialog_style_unequal_columns_use_uniform_gap() -> None:
    doc = Document()
    doc.main.blocks = [Paragraph(runs=[TextItem("Column text")])]
    doc.sect.cols = ColumnsProperties(num=2, space=12.0, equal_width=False,
                                      widths=[100.0, 320.0])
    frames = paginate_document(doc).pages[0].regions[0].columns
    assert [c.width for c in frames] == [100.0, 320.0]
    assert [c.left for c in frames] == [0.0, 112.0]


def test_fixture_balances_only_before_continuous_section(qapp: QApplication) -> None:
    doc = read_docx(DOCX_DIR / "libreoffice__tdf121670_columnsInSectionsOnly.docx")
    result = paginate_document(doc)
    assert result.total_pages == 2
    opening = result.pages[0].regions[0].columns
    assert opening[0].fragments
    assert not opening[1].fragments
    assert not opening[2].fragments
    second = result.pages[1]
    assert len(second.regions) == 2
    assert all(c.fragments for c in second.regions[0].columns)
    assert len(second.regions[1].columns) == 1
    assert second.regions[1].top >= max(
        c.used_height for c in second.regions[0].columns
    )


@pytest.mark.parametrize("boundary", ["nextPage", "continuous", "final"])
def test_column_balance_depends_on_following_boundary(boundary: str) -> None:
    doc = Document()
    previous = SectionProperties(cols=ColumnsProperties(num=3, space=12.0))
    para = Paragraph(runs=[TextItem("one\ntwo\nthree\nfour\nfive\nsix")])
    if boundary == "final":
        doc.sect = previous
        doc.main.blocks = [para]
    else:
        para.sect = previous
        doc.sect.sect_type = boundary
        doc.main.blocks = [para, Paragraph(runs=[TextItem("Following section")])]
    result = paginate_document(doc)
    columns = result.pages[0].regions[0].columns
    assert [bool(c.fragments) for c in columns] == (
        [True, True, True] if boundary == "continuous" else [True, False, False]
    )
    assert result.total_pages == (2 if boundary == "nextPage" else 1)


@pytest.mark.parametrize("widths", [[300.0, 70.0], [70.0, 300.0]])
@pytest.mark.parametrize("keep_lines", [False, True])
def test_continuation_reflows_at_destination_width(
    widths: list[float], keep_lines: bool, qapp: QApplication,
) -> None:
    text = "alpha beta gamma delta " * 30 + "abcdefghij" * 20
    doc = Document()
    doc.sect.pg_h = 110.0
    doc.sect.mt = doc.sect.mb = 20.0
    doc.sect.cols = ColumnsProperties(num=2, equal_width=False, widths=widths)
    doc.main.blocks = [Paragraph(
        runs=[TextItem(text, r_pr=RunProperties(font="Arial", sz=10.0))],
        p_pr=ParagraphProperties(
            keep_lines=keep_lines, widow_control=False,
            ind=IndentProperties(first_line=10.0),
            sp=SpacingProperties(line=12.0, line_rule="exact"),
        ),
    )]
    result = paginate_document(doc)
    portions = []
    for page in result.pages:
        for col in page.regions[0].columns:
            for frag in col.fragments:
                for line in frag.lines:
                    assert line.width + line.indent_left <= col.width + 0.01
                    portions.extend(line.portions)
    assert "".join(p.text for p in portions) == text
    for portion in portions:
        assert text[portion.char_offset:portion.char_offset + portion.length] == portion.text


def test_unequal_continuous_section_keeps_measured_lines_in_their_columns() -> None:
    doc = Document()
    previous = SectionProperties(cols=ColumnsProperties(
        num=2, equal_width=False, widths=[300.0, 70.0], space=12.0,
    ))
    paragraph = Paragraph(
        runs=[TextItem("A paragraph that fills a wider column with several lines. " * 4)],
        sect=previous,
    )
    doc.main.blocks = [paragraph, Paragraph(runs=[TextItem("Following section")])]
    doc.sect.sect_type = "continuous"
    result = paginate_document(doc)
    for col in result.pages[0].regions[0].columns:
        for frag in col.fragments:
            assert all(line.width <= col.width for line in frag.lines)
