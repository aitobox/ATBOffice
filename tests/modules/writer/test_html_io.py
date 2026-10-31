"""Unit tests for Quire HTML Document bidirectional import and semantic export."""

from __future__ import annotations

from atboffice.core.window_manager import WindowManager
from atboffice.modules.writer.models.document import (
    Cell,
    Document,
    Paragraph,
    Row,
    Table,
    TextItem,
    ptext,
)
from atboffice.modules.writer.models.drawing import PictureItem
from atboffice.modules.writer.models.properties import (
    RunProperties,
)


def test_read_empty_html() -> None:
    from atboffice.modules.writer.io.html_io import HtmlReader, read_html

    reader = HtmlReader()
    doc1 = reader.read("")
    assert isinstance(doc1, Document)
    assert len(doc1.main.blocks) >= 1
    assert isinstance(doc1.main.blocks[0], Paragraph)

    doc2 = read_html("   \n\t   ")
    assert isinstance(doc2, Document)
    assert len(doc2.main.blocks) >= 1


def test_read_inline_formatting() -> None:
    from atboffice.modules.writer.io.html_io import read_html

    html = (
        "<p>"
        "<b>Bold</b> "
        "<i>Italic</i> "
        "<u>Underline</u> "
        "<s>Strike</s> "
        "<sup>Super</sup> "
        "<sub>Sub</sub> "
        "<code>Code</code> "
        "<span style='color: #FF0000; font-size: 16pt; font-family: Arial;'>Styled</span>"
        "</p>"
    )
    doc = read_html(html)
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    
    full_text = ptext(p)
    assert "Bold" in full_text
    assert "Italic" in full_text
    assert "Underline" in full_text
    assert "Strike" in full_text
    assert "Super" in full_text
    assert "Sub" in full_text
    assert "Code" in full_text
    assert "Styled" in full_text

    # Verify run properties on specific runs
    runs = p.runs
    bold_runs = [r for r in runs if getattr(r, "text", "") == "Bold"]
    assert len(bold_runs) == 1
    assert bold_runs[0].r_pr.bold is True

    italic_runs = [r for r in runs if getattr(r, "text", "") == "Italic"]
    assert len(italic_runs) == 1
    assert italic_runs[0].r_pr.italic is True

    underline_runs = [r for r in runs if getattr(r, "text", "") == "Underline"]
    assert len(underline_runs) == 1
    assert underline_runs[0].r_pr.underline == "single"

    strike_runs = [r for r in runs if getattr(r, "text", "") == "Strike"]
    assert len(strike_runs) == 1
    assert strike_runs[0].r_pr.strike is True

    super_runs = [r for r in runs if getattr(r, "text", "") == "Super"]
    assert len(super_runs) == 1
    assert super_runs[0].r_pr.vert_align == "superscript"

    sub_runs = [r for r in runs if getattr(r, "text", "") == "Sub"]
    assert len(sub_runs) == 1
    assert sub_runs[0].r_pr.vert_align == "subscript"

    code_runs = [r for r in runs if getattr(r, "text", "") == "Code"]
    assert len(code_runs) == 1
    assert code_runs[0].r_pr.font_family == "Courier New"

    styled_runs = [r for r in runs if getattr(r, "text", "") == "Styled"]
    assert len(styled_runs) == 1
    assert styled_runs[0].r_pr.color == "FF0000"
    assert styled_runs[0].r_pr.font_size == 16.0
    assert styled_runs[0].r_pr.font_family == "Arial"


def test_read_headings() -> None:
    from atboffice.modules.writer.io.html_io import read_html

    html = "<h1>Heading One</h1><h2>Heading Two</h2><h3>Heading Three</h3>"
    doc = read_html(html)
    assert len(doc.main.blocks) == 3

    h1 = doc.main.blocks[0]
    assert isinstance(h1, Paragraph)
    assert h1.p_pr.style_id == "Heading 1"
    assert "Heading One" in ptext(h1)

    h2 = doc.main.blocks[1]
    assert isinstance(h2, Paragraph)
    assert h2.p_pr.style_id == "Heading 2"
    assert "Heading Two" in ptext(h2)

    h3 = doc.main.blocks[2]
    assert isinstance(h3, Paragraph)
    assert h3.p_pr.style_id == "Heading 3"
    assert "Heading Three" in ptext(h3)


def test_read_paragraph_alignments_and_margins() -> None:
    from atboffice.modules.writer.io.html_io import read_html

    html = (
        "<p style='text-align: center; margin-left: 36pt; margin-top: 12pt; text-indent: 18pt;'>"
        "Centered and indented"
        "</p>"
    )
    doc = read_html(html)
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    assert p.p_pr.jc == "center"
    assert p.p_pr.ind.left == 36.0
    assert p.p_pr.sp.space_before == 12.0
    assert p.p_pr.ind.first_line == 18.0


def test_read_hyperlinks() -> None:
    from atboffice.modules.writer.io.html_io import read_html

    html = (
        '<p>Visit <a href="https://example.com">Example Site</a> '
        'or jump to <a href="#target">Target</a>.</p>'
    )
    doc = read_html(html)
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)

    runs = p.runs
    ext_link_run = [r for r in runs if getattr(r, "text", "") == "Example Site"][0]
    assert ext_link_run.r_pr.link == {"url": "https://example.com"}

    int_link_run = [r for r in runs if getattr(r, "text", "") == "Target"][0]
    assert int_link_run.r_pr.link == {"anchor": "target"}


def test_read_lists() -> None:
    from atboffice.modules.writer.io.html_io import read_html

    html = (
        "<ul>"
        "<li>Bullet A</li>"
        "<li>Bullet B"
        "  <ul><li>Sub-bullet B1</li></ul>"
        "</li>"
        "</ul>"
        "<ol type='1'>"
        "<li>Numbered 1</li>"
        "<li>Numbered 2</li>"
        "</ol>"
    )
    doc = read_html(html)
    blocks = doc.main.blocks
    assert len(blocks) == 5

    # All list items become paragraphs with num_id and num_level
    b0 = blocks[0]
    assert isinstance(b0, Paragraph)
    assert b0.p_pr.num_id is not None
    assert b0.p_pr.num_level == 0
    assert "Bullet A" in ptext(b0)

    b1 = blocks[1]
    assert isinstance(b1, Paragraph)
    assert b1.p_pr.num_id is not None
    assert b1.p_pr.num_level == 0
    assert "Bullet B" in ptext(b1)

    b2 = blocks[2]
    assert isinstance(b2, Paragraph)
    assert b2.p_pr.num_id is not None
    assert b2.p_pr.num_level == 1
    assert "Sub-bullet B1" in ptext(b2)

    o0 = blocks[3]
    assert isinstance(o0, Paragraph)
    assert o0.p_pr.num_id is not None
    assert "Numbered 1" in ptext(o0)


def test_read_table() -> None:
    from atboffice.modules.writer.io.html_io import read_html

    html = (
        "<table border='1'>"
        "<tr><th>Header 1</th><th>Header 2</th></tr>"
        "<tr><td>Row 1 Col 1</td><td>Row 1 Col 2</td></tr>"
        "<tr><td colspan='2' bgcolor='#FFFF00'>Span 2 Cols</td></tr>"
        "</table>"
    )
    doc = read_html(html)
    assert len(doc.main.blocks) >= 1
    tbl = [b for b in doc.main.blocks if isinstance(b, Table)][0]
    assert len(tbl.rows) == 3
    assert len(tbl.rows[0].cells) == 2
    assert len(tbl.rows[1].cells) == 2
    
    # Check headers
    cell0 = tbl.rows[0].cells[0]
    p_hdr = cell0.blocks[0]
    assert isinstance(p_hdr, Paragraph)
    assert "Header 1" in ptext(p_hdr)

    # Check colspan cell
    span_cell = tbl.rows[2].cells[0]
    assert span_cell.tc_pr.span == 2
    p_span = span_cell.blocks[0]
    assert isinstance(p_span, Paragraph)
    assert "Span 2 Cols" in ptext(p_span)
    assert span_cell.tc_pr.shd.get("fill") == "FFFF00"


def test_read_images() -> None:
    from atboffice.modules.writer.io.html_io import read_html

    # 1x1 transparent PNG data uri
    data_uri = (
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    html = f'<p>Image: <img src="{data_uri}" width="100" height="80" alt="Logo"></p>'
    doc = read_html(html)
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)

    pics = [
        r
        for r in p.runs
        if isinstance(r, PictureItem)
        or getattr(r, "t", "") == "picture"
        or getattr(r, "t", "") == "img"
    ]
    assert len(pics) == 1
    pic = pics[0]
    assert pic.alt_text == "Logo"
    assert pic.width == 75.0  # 100px * 0.75 = 75pt
    assert pic.height == 60.0  # 80px * 0.75 = 60pt


def test_write_html_and_roundtrip() -> None:
    from atboffice.modules.writer.io.html_io import read_html, write_html

    doc = Document()
    p1 = Paragraph()
    p1.p_pr.style_id = "Heading 1"
    p1.runs.append(TextItem("Document Title", r_pr=RunProperties(b=True)))

    p2 = Paragraph()
    p2.runs.append(TextItem("Normal text with "))
    p2.runs.append(TextItem("italic", r_pr=RunProperties(i=True)))
    p2.runs.append(TextItem(" and "))
    p2.runs.append(TextItem("red color", r_pr=RunProperties(color="FF0000")))

    tbl = Table()
    tbl.grid = [100.0, 100.0]
    r1 = Row()
    c1 = Cell(blocks=[Paragraph(runs=[TextItem("A1")])])
    c2 = Cell(blocks=[Paragraph(runs=[TextItem("B1")])])
    r1.cells = [c1, c2]
    tbl.rows.append(r1)

    doc.main.blocks = [p1, p2, tbl]

    html_out = write_html(doc)
    assert "<!DOCTYPE html>" in html_out
    assert "<h1" in html_out
    assert "Document Title" in html_out
    assert "<i>italic</i>" in html_out or "font-style:italic" in html_out
    assert "color:#FF0000" in html_out or "color:#ff0000" in html_out
    assert "<table" in html_out
    assert "A1" in html_out
    assert "B1" in html_out

    # Roundtrip: import back into Quire Document
    doc_back = read_html(html_out)
    assert len(doc_back.main.blocks) >= 3
    assert "Document Title" in ptext(doc_back.main.blocks[0])
    assert "Normal text with" in ptext(doc_back.main.blocks[1])
    back_tables = [b for b in doc_back.main.blocks if isinstance(b, Table)]
    assert len(back_tables) == 1
    assert "A1" in ptext(back_tables[0].rows[0].cells[0].blocks[0])


def test_vfs_html_io_export() -> None:
    import atboffice.vfs.html_io as vfs_html

    assert hasattr(vfs_html, "read_html")
    assert hasattr(vfs_html, "write_html")
    assert hasattr(vfs_html, "HtmlReader")
    assert hasattr(vfs_html, "HtmlWriter")

    doc = vfs_html.read_html("<p>VFS Bridge Test</p>")
    assert "VFS Bridge Test" in ptext(doc.main.blocks[0])


def test_window_manager_routing_and_filters() -> None:
    wm = WindowManager.get_instance()
    assert ".html" in wm.QUIRE_EXTENSIONS
    assert ".htm" in wm.QUIRE_EXTENSIONS

    assert wm.detect_app_type("report.html") == "quire"
    assert wm.detect_app_type("document.htm") == "quire"
