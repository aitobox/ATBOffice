"""Unit tests for Quire GitHub Flavored Markdown and RTF 1.5 I/O subsystem."""

from __future__ import annotations

from atboffice.modules.writer.io import (
    MarkdownReader,
    MarkdownWriter,
    RtfReader,
    RtfWriter,
    read_markdown,
    read_markdown_zip,
    read_rtf,
    write_markdown,
    write_markdown_zip,
    write_rtf,
)
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    Table,
    TextItem,
    ptext,
)
from atboffice.modules.writer.models.properties import (
    RunProperties,
)


def test_module_exports() -> None:
    """Verify that Markdown and RTF I/O functions and classes are properly exported."""
    assert callable(read_markdown)
    assert callable(write_markdown)
    assert callable(read_markdown_zip)
    assert callable(write_markdown_zip)
    assert callable(read_rtf)
    assert callable(write_rtf)
    assert MarkdownReader is not None
    assert MarkdownWriter is not None
    assert RtfReader is not None
    assert RtfWriter is not None


def test_markdown_headings_and_inlines() -> None:
    """Verify parsing of ATX headings and inline styling."""
    md_text = (
        "# Title Level 1\n\n"
        "## Subtitle Level 2\n\n"
        "Here is **bold text**, *italic text*, and `code text` with a [link](https://example.com).\n"
    )
    doc = read_markdown(md_text)
    assert len(doc.main.blocks) >= 3

    p0 = doc.main.blocks[0]
    assert isinstance(p0, Paragraph)
    assert p0.p_pr.style == "Heading1"
    assert "Title Level 1" in ptext(p0)

    p1 = doc.main.blocks[1]
    assert isinstance(p1, Paragraph)
    assert p1.p_pr.style == "Heading2"
    assert "Subtitle Level 2" in ptext(p1)

    p2 = doc.main.blocks[2]
    assert isinstance(p2, Paragraph)
    runs = p2.runs
    bold_runs = [r for r in runs if isinstance(r, TextItem) and r.r_pr.b]
    assert any("bold text" in r.text for r in bold_runs)
    italic_runs = [r for r in runs if isinstance(r, TextItem) and r.r_pr.i]
    assert any("italic text" in r.text for r in italic_runs)
    code_runs = [r for r in runs if isinstance(r, TextItem) and r.r_pr.style == "HTMLCode"]
    assert any("code text" in r.text for r in code_runs)


def test_markdown_code_blocks() -> None:
    """Verify fenced code blocks convert to preformatted paragraphs."""
    md_text = "```python\ndef hello():\n    print('world')\n```\n"
    doc = read_markdown(md_text)
    assert len(doc.main.blocks) == 2
    for b in doc.main.blocks:
        assert isinstance(b, Paragraph)
        assert b.p_pr.style == "HTMLPreformatted"
    assert "def hello():" in ptext(doc.main.blocks[0])
    assert "print('world')" in ptext(doc.main.blocks[1])


def test_markdown_blockquotes_and_alerts() -> None:
    """Verify standard blockquotes and GitHub-style alerts."""
    md_text = (
        "> Standard quote line\n\n"
        "> [!NOTE]\n"
        "> This is an important note alert.\n\n"
        "> [!WARNING]\n"
        "> Watch out for this warning!\n"
    )
    doc = read_markdown(md_text)
    assert len(doc.main.blocks) >= 3

    # Check that alert blocks are marked
    note_blocks = [
        b
        for b in doc.main.blocks
        if isinstance(b, Paragraph) and getattr(b.p_pr, "md_alert", None) == "note"
    ]
    assert len(note_blocks) >= 1

    warning_blocks = [
        b
        for b in doc.main.blocks
        if isinstance(b, Paragraph) and getattr(b.p_pr, "md_alert", None) == "warning"
    ]
    assert len(warning_blocks) >= 1


def test_markdown_lists_and_tasklists() -> None:
    """Verify unordered, ordered, and task list items."""
    md_text = (
        "- Item A\n"
        "- Item B\n\n"
        "1. First item\n"
        "2. Second item\n\n"
        "- [ ] Task unchecked\n"
        "- [x] Task checked\n"
    )
    doc = read_markdown(md_text)
    assert len(doc.main.blocks) >= 6

    task_p1 = doc.main.blocks[4]
    task_p2 = doc.main.blocks[5]
    assert isinstance(task_p1, Paragraph)
    assert isinstance(task_p2, Paragraph)
    assert "Task unchecked" in ptext(task_p1)
    assert "Task checked" in ptext(task_p2)
    assert getattr(task_p1.p_pr, "md_task", None) is False
    assert getattr(task_p2.p_pr, "md_task", None) is True


def test_markdown_pipe_tables() -> None:
    """Verify pipe tables parsing into Quire Table models."""
    md_text = (
        "| Name | Age | City |\n"
        "| :--- | :---: | ---: |\n"
        "| Alice | 30 | Paris |\n"
        "| Bob | 25 | London |\n"
    )
    doc = read_markdown(md_text)
    tables = [b for b in doc.main.blocks if isinstance(b, Table)]
    assert len(tables) == 1
    tbl = tables[0]
    assert len(tbl.rows) == 3
    assert len(tbl.grid) == 3

    header_cells = tbl.rows[0].cells
    assert len(header_cells) == 3
    assert ptext(header_cells[0].blocks[0]).strip() == "Name"
    assert ptext(header_cells[1].blocks[0]).strip() == "Age"
    assert ptext(header_cells[2].blocks[0]).strip() == "City"

    row1_cells = tbl.rows[1].cells
    assert ptext(row1_cells[0].blocks[0]).strip() == "Alice"
    assert row1_cells[0].blocks[0].p_pr.jc == "left"
    assert row1_cells[1].blocks[0].p_pr.jc == "center"
    assert row1_cells[2].blocks[0].p_pr.jc == "right"


def test_markdown_roundtrip() -> None:
    """Verify document serialization to Markdown text and back."""
    original_md = (
        "# Document Header\n\n"
        "A paragraph with **bold** and *italic* formatting.\n\n"
        "- List element one\n"
        "- List element two\n\n"
        "| Col1 | Col2 |\n"
        "| --- | --- |\n"
        "| Val1 | Val2 |\n"
    )
    doc = read_markdown(original_md)
    out_md, images = write_markdown(doc)

    assert "# Document Header" in out_md
    assert "**bold**" in out_md or "**bold**" in out_md.replace("  ", " ")
    assert "*italic*" in out_md
    assert "- List element one" in out_md or "* List element one" in out_md
    assert "| Col1 | Col2 |" in out_md

    doc2 = read_markdown(out_md)
    assert len(doc2.main.blocks) >= 4


def test_markdown_zip_roundtrip() -> None:
    """Verify packaging and extracting Markdown with images in a ZIP archive."""
    doc = Document()
    p1 = Paragraph()
    p1.p_pr.style = "Heading1"
    p1.runs.append(TextItem("Document with Image"))

    p2 = Paragraph()
    p2.runs.append(TextItem("Here is the diagram:"))
    doc.main.blocks = [p1, p2]

    zip_bytes = write_markdown_zip(doc, main_filename="index.md")
    assert isinstance(zip_bytes, bytes)
    assert len(zip_bytes) > 0

    doc_back = read_markdown_zip(zip_bytes)
    assert len(doc_back.main.blocks) >= 2
    assert "Document with Image" in ptext(doc_back.main.blocks[0])


def test_rtf_read_basic() -> None:
    """Verify reading RTF 1.5 into Document with formatting."""
    rtf_content = (
        r"{\rtf1\ansi\deff0"
        r"{\fonttbl{\f0 Arial;}{\f1 Times New Roman;}}"
        r"{\colortbl;\red255\green0\blue0;\red0\green0\blue255;}"
        r"\pard\qc\fs24 Hello \b World\b0  in \cf1 Red\cf0  and \i Italic\i0 .\par"
        r"\pard\ql Second paragraph.\par"
        r"}"
    )
    doc = read_rtf(rtf_content)
    assert len(doc.main.blocks) >= 2

    p0 = doc.main.blocks[0]
    assert isinstance(p0, Paragraph)
    assert p0.p_pr.jc == "center"

    bold_runs = [r for r in p0.runs if isinstance(r, TextItem) and r.r_pr.b]
    assert any("World" in r.text for r in bold_runs)

    italic_runs = [r for r in p0.runs if isinstance(r, TextItem) and r.r_pr.i]
    assert any("Italic" in r.text for r in italic_runs)

    red_runs = [
        r
        for r in p0.runs
        if isinstance(r, TextItem) and (r.r_pr.color == "FF0000" or r.r_pr.color == "#FF0000")
    ]
    assert any("Red" in r.text for r in red_runs)


def test_rtf_tables() -> None:
    """Verify RTF table parsing with rows, cells, and widths."""
    rtf_content = (
        r"{\rtf1\ansi"
        r"\trowd\cellx2000\cellx4000"
        r"\intbl Cell 1\cell Cell 2\cell\row"
        r"\trowd\cellx2000\cellx4000"
        r"\intbl Cell 3\cell Cell 4\cell\row"
        r"}"
    )
    doc = read_rtf(rtf_content)
    tables = [b for b in doc.main.blocks if isinstance(b, Table)]
    assert len(tables) == 1
    tbl = tables[0]
    assert len(tbl.rows) == 2
    assert len(tbl.rows[0].cells) == 2
    assert "Cell 1" in ptext(tbl.rows[0].cells[0].blocks[0])
    assert "Cell 2" in ptext(tbl.rows[0].cells[1].blocks[0])


def test_rtf_hyperlinks() -> None:
    """Verify parsing and writing RTF fields including hyperlinks."""
    rtf_content = (
        r"{\rtf1\ansi"
        r"{\field{\*\fldinst {HYPERLINK \"https://google.com\"}}{\fldrslt Visit Google}}"
        r"\par}"
    )
    doc = read_rtf(rtf_content)
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    link_runs = [r for r in p.runs if isinstance(r, TextItem) and getattr(r.r_pr, "link", None)]
    assert len(link_runs) >= 1
    assert link_runs[0].r_pr.link.get("url") == "https://google.com"
    assert "Visit Google" in link_runs[0].text


def test_rtf_roundtrip() -> None:
    """Verify Document serialization to RTF and parsing back."""
    doc = Document()
    p1 = Paragraph()
    p1.p_pr.jc = "center"
    p1.runs.append(TextItem("Centered Title", RunProperties(b=True, sz=16.0)))

    p2 = Paragraph()
    p2.runs.append(TextItem("Normal text with "))
    p2.runs.append(TextItem("italic portion", RunProperties(i=True)))
    doc.main.blocks = [p1, p2]

    rtf_data = write_rtf(doc)
    assert isinstance(rtf_data, bytes)
    assert b"\\rtf1" in rtf_data
    assert b"Centered Title" in rtf_data

    doc2 = read_rtf(rtf_data)
    assert len(doc2.main.blocks) >= 2
    assert "Centered Title" in ptext(doc2.main.blocks[0])
    assert doc2.main.blocks[0].p_pr.jc == "center"


def test_empty_inputs() -> None:
    """Verify robust handling of empty string or blank inputs."""
    doc_md = read_markdown("")
    assert isinstance(doc_md, Document)
    assert len(doc_md.main.blocks) >= 1

    doc_rtf = read_rtf("")
    assert isinstance(doc_rtf, Document)
    assert len(doc_rtf.main.blocks) >= 1
