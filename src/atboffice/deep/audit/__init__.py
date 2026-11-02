"""Document compatibility loss-audit and feature preservation suite."""

from atboffice.deep.audit.core import AuditSession, load_package_xml, xml_text
from atboffice.deep.audit.excel import EXCEL_FEATURES, extract_excel_features
from atboffice.deep.audit.presentation import (
    PRESENTATION_FEATURES,
    extract_presentation_features,
)
from atboffice.deep.audit.word import (
    WORD_FEATURES,
    count_document_words,
    extract_word_features,
)

__all__ = [
    "AuditSession",
    "load_package_xml",
    "xml_text",
    "WORD_FEATURES",
    "extract_word_features",
    "count_document_words",
    "EXCEL_FEATURES",
    "extract_excel_features",
    "PRESENTATION_FEATURES",
    "extract_presentation_features",
]
