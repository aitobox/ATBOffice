"""Quire WordprocessingML DOCX and DOCM I/O subsystem."""

from atboffice.modules.writer.io.docx_reader import DocxReader, read_docx
from atboffice.modules.writer.io.docx_writer import DocxWriter, write_docx

__all__ = ["DocxReader", "DocxWriter", "read_docx", "write_docx"]
