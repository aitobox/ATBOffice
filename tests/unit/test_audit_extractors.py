from __future__ import annotations

from pathlib import Path

from atboffice.deep.audit.core import load_package_xml
from atboffice.deep.audit.excel import extract_excel_features
from atboffice.deep.audit.presentation import extract_presentation_features
from atboffice.deep.audit.word import count_document_words, extract_word_features


def test_extract_word_features_on_curated() -> None:
    sample_docx = next(Path("tests/docs/word/docx").glob("*.docx"))
    names, files = load_package_xml(sample_docx)
    feats = extract_word_features(names, files)
    assert isinstance(feats, dict)
    assert len(feats) >= 40
    words = count_document_words(files)
    assert isinstance(words, int)
    assert words >= 0


def test_extract_excel_features_on_curated() -> None:
    sample_xlsx = next(Path("tests/docs/excel/xlsx").glob("*.xlsx"))
    names, files = load_package_xml(sample_xlsx)
    feats = extract_excel_features(names, files)
    assert isinstance(feats, dict)
    assert len(feats) >= 20
    assert "worksheets" in feats


def test_extract_presentation_features_on_curated() -> None:
    sample_pptx = next(Path("tests/docs/powerpoint/pptx").glob("*.pptx"))
    names, files = load_package_xml(sample_pptx)
    feats = extract_presentation_features(names, files)
    assert isinstance(feats, dict)
    assert len(feats) >= 20
    assert "slides" in feats
