"""Unit and integration tests for Quire list counters, multi-level numbering, and picture bullets.

Issue #364 / TASK-DOC-Q02.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from atboffice.modules.writer.layout.portions import map_symbol_char


def test_map_symbol_char() -> None:
    """Verify Symbol and Wingdings glyph mappings to standard Unicode characters."""
    # Wingdings mappings
    assert map_symbol_char("\uf06c", "Wingdings") == "●"
    assert map_symbol_char("l", "Wingdings") == "●"
    assert map_symbol_char("\uf06e", "Wingdings") == "■"
    assert map_symbol_char("n", "Wingdings") == "■"
    assert map_symbol_char("\uf075", "Wingdings") == "◆"
    assert map_symbol_char("u", "Wingdings") == "◆"
    assert map_symbol_char("\uf0fc", "Wingdings") == "✓"
    assert map_symbol_char("ü", "Wingdings") == "✓"
    assert map_symbol_char("\uf0d8", "Wingdings") == "➢"
    assert map_symbol_char("\uf0a7", "Wingdings") == "▪"
    assert map_symbol_char("§", "Wingdings") == "▪"

    # Symbol mappings
    assert map_symbol_char("\uf0b7", "Symbol") == "•"
    assert map_symbol_char("·", "Symbol") == "•"

    # Private use fallbacks
    assert map_symbol_char("\uf005") == "•"

    # Normal characters without symbol font remain unchanged
    assert map_symbol_char("A", "Arial") == "A"
    assert map_symbol_char("1", "Calibri") == "1"


def test_document_blocks_traversal() -> None:
    """Verify Document.blocks and all_paras traversal in reading order including tables."""
    from atboffice.modules.writer.models.document import Cell, Document, Paragraph, Row, Story, Table

    p1 = Paragraph()
    p1.label = "1."
    p2 = Paragraph()
    p2.label = "2."
    p3 = Paragraph()
    p3.label = "5."
    p4 = Paragraph()
    p4.label = "3."
    p5 = Paragraph()
    p5.label = "4."

    tbl = Table(rows=[Row(cells=[Cell(blocks=[p4, p5])])])
    doc = Document(main=Story(kind="main", blocks=[p1, p2, tbl, p3]))

    # Verify Paragraph.label exists and defaults to empty string on new paragraph
    p_new = Paragraph()
    assert p_new.label == ""

    # Verify doc.blocks traverses in reading order
    blocks = doc.blocks
    assert blocks == [p1, p2, tbl, p4, p5, p3]

    # Verify list comprehension pattern from acceptance criteria
    labels = [b.label for b in doc.blocks if hasattr(b, "label") and b.label]
    assert labels == ["1.", "2.", "3.", "4.", "5."]

    # Verify doc.all_paras returns only paragraphs
    assert doc.all_paras() == [p1, p2, p4, p5, p3]


def test_parse_num_pic_bullet() -> None:
    """Verify DocxReader parses numPicBullet and lvlPicBulletId in bullet-complex fixture."""
    from atboffice.modules.writer.io.docx_reader import DocxReader

    fixture_path = "tests/docs/word/docx/openxml-sdk__bullet-complex.docx"
    doc = DocxReader().read(fixture_path)

    # Verify pic_bullets parsed in numbering
    pic_bullets = doc.numbering.get("pic_bullets", {})
    assert len(pic_bullets) >= 3
    assert "0" in pic_bullets
    assert "1" in pic_bullets
    assert "2" in pic_bullets

    pb0 = pic_bullets["0"]
    assert "image_part" in pb0
    assert pb0["image_part"].endswith(".gif")

    # Verify abstractNum 14 has pic_bullet_id
    abs14 = doc.numbering.get("abs", {}).get("14")
    assert abs14 is not None
    lv0 = abs14["levels"][0]
    assert lv0.get("pic_bullet_id") == "0"
    assert "pic_bullet" in lv0


def test_tdf132802_list_counters() -> None:
    """Verify libreoffice__tdf132802.docx numbering counters 1. through 8. and style inheritance."""
    from atboffice.modules.writer.io.docx_reader import DocxReader

    fixture_path = "tests/docs/word/docx/libreoffice__tdf132802.docx"
    doc = DocxReader().read(fixture_path)

    # Acceptance Criteria 1:
    # libreoffice__tdf132802.docx labels are '1.' through '8.' in document order,
    # with 'Not numbered paragraph' unlabeled.
    labels = [b.label for b in doc.blocks if hasattr(b, "label") and b.label]
    assert labels == ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8."]

    # Find the 'Not numbered paragraph1' paragraph and confirm it has empty label
    unlabeled = [
        b
        for b in doc.blocks
        if hasattr(b, "runs")
        and any("Not numbered paragraph" in getattr(r, "text", "") for r in b.runs)
    ]
    assert len(unlabeled) == 1
    assert unlabeled[0].label == ""


def test_tdf125881_multilevel_patterns() -> None:
    """Verify libreoffice__tdf125881.docx multi-level patterns I., I.1., I.2., I.3."""
    from atboffice.modules.writer.io.docx_reader import DocxReader

    fixture_path = "tests/docs/word/docx/libreoffice__tdf125881.docx"
    doc = DocxReader().read(fixture_path)

    # Acceptance Criteria 2:
    # libreoffice__tdf125881.docx labels are 'I.', 'I.1.', 'I.2.', 'I.3.'
    # (Roman numeral parent + Arabic children).
    labels = [b.label for b in doc.blocks if hasattr(b, "label") and b.label]
    assert labels == ["I.", "I.1.", "I.2.", "I.3."]


def test_portion_picture_bullet_and_hanging_indent() -> None:
    """Verify decompose_paragraph_to_portions creates GRAPHIC portion for picture bullets and applies indents."""
    from atboffice.modules.writer.io.docx_reader import DocxReader
    from atboffice.modules.writer.layout.portions import (
        PortionType,
        decompose_paragraph_to_portions,
        layout_paragraph,
    )

    fixture_path = "tests/docs/word/docx/openxml-sdk__bullet-complex.docx"
    doc = DocxReader().read(fixture_path)

    # Paragraph with picture bullet (e.g. using abstractNum 14, 19, or 24)
    # Find paragraph with picture bullet in doc
    pic_paras = []
    for b in doc.blocks:
        if hasattr(b, "runs"):
            portions = decompose_paragraph_to_portions(b, doc)
            if any(po.type == PortionType.GRAPHIC for po in portions):
                pic_paras.append((b, portions))

    assert len(pic_paras) > 0, "Should have synthesized graphic portions for picture bullet paragraphs"
    p, portions = pic_paras[0]
    graphic_po = [po for po in portions if po.type == PortionType.GRAPHIC][0]
    assert graphic_po.width > 0
    assert graphic_po.ascent > 0
    assert graphic_po.data is not None

    # Verify hanging indent on a numbered paragraph
    layout = layout_paragraph(p, doc=doc, container_width=468.0)
    assert len(layout.lines) > 0
    first_line = layout.lines[0]
    assert first_line.indent_left >= 0


def test_all_word_fixtures_no_percent_in_labels() -> None:
    """Acceptance Criteria 4: All 24 Word fixtures: no label text contains a '%' character."""
    import glob
    from atboffice.modules.writer.io.docx_reader import read_docx

    fixtures = sorted(glob.glob("tests/docs/word/docx/*.docx"))
    assert len(fixtures) >= 24

    for fixture_path in fixtures:
        fname = os.path.basename(fixture_path)
        if "protected" in fname:
            continue
        doc = read_docx(fixture_path)
        for i, b in enumerate(doc.blocks):
            label = getattr(b, "label", "")
            assert "%" not in label, f"Fixture {fname} block {i} label '{label}' contains literal '%'"





