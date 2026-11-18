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
from atboffice.modules.writer.models.properties import ColumnsProperties

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
