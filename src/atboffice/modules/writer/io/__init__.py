"""Quire document I/O subsystem: DOCX, DOCM, Markdown (GFM/ZIP), RTF, and HTML."""

from atboffice.modules.writer.io.docx_reader import DocxReader, read_docx
from atboffice.modules.writer.io.docx_writer import DocxWriter, write_docx
from atboffice.modules.writer.io.html_io import (
    HtmlReader,
    HtmlWriter,
    read_html,
    web_page,
    write_html,
)
from atboffice.modules.writer.io.markdown_io import (
    MarkdownReader,
    MarkdownWriter,
    read_markdown,
    read_markdown_zip,
    write_markdown,
    write_markdown_zip,
)
from atboffice.modules.writer.io.rtf_io import (
    RtfReader,
    RtfWriter,
    read_rtf,
    write_rtf,
)

__all__ = [
    "DocxReader",
    "DocxWriter",
    "HtmlReader",
    "HtmlWriter",
    "MarkdownReader",
    "MarkdownWriter",
    "RtfReader",
    "RtfWriter",
    "read_docx",
    "read_html",
    "read_markdown",
    "read_markdown_zip",
    "read_rtf",
    "web_page",
    "write_docx",
    "write_html",
    "write_markdown",
    "write_markdown_zip",
    "write_rtf",
]
