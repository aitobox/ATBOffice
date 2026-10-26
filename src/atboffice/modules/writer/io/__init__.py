"""Quire document I/O subsystem: DOCX, DOCM, Markdown (GFM/ZIP), and RTF."""

from atboffice.modules.writer.io.docx_reader import DocxReader, read_docx
from atboffice.modules.writer.io.docx_writer import DocxWriter, write_docx
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
    "MarkdownReader",
    "MarkdownWriter",
    "RtfReader",
    "RtfWriter",
    "read_docx",
    "read_markdown",
    "read_markdown_zip",
    "read_rtf",
    "write_docx",
    "write_markdown",
    "write_markdown_zip",
    "write_rtf",
]
