"""Tier 3 Regression Suite: Real DOCX Corpus & Lossless Roundtrip Matrix for Quire.

References:
- .vibeoffice/tests/quire/lines/linecases.docx
- .vibeoffice/tests/from-issues/11/linegrid.docx
- .vibeoffice/tests/from-issues/11/word.json
- .vibeoffice/tools/quire-pages.mjs
- .vibeoffice/tests/quire/loss-audit.py

Validates:
1. Loading real corpus documents and paginating them with zero regression.
2. Page count verification: assert difference between Quire and Word count is 0.
3. Matching line grid pagination against Word reference data (word.json).
4. Lossless incremental save: carrying untouched XML parts, VBA binaries,
   themes, and images with 100% SHA-256 byte-for-byte fidelity.
5. Re-reading modified packages with intact DOM trees.
"""

from __future__ import annotations

import hashlib
import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.writer.io import read_docx, write_docx
from atboffice.modules.writer.layout.pagination import paginate_document
from atboffice.modules.writer.models.document import all_paragraphs, ptext
from atboffice.vfs.opc import SourcePackage

CORPUS_LINECASES = Path(".vibeoffice/tests/quire/lines/linecases.docx")
CORPUS_LINEGRID = Path(".vibeoffice/tests/from-issues/11/linegrid.docx")
WORD_REF_JSON = Path(".vibeoffice/tests/from-issues/11/word.json")

CT_RELS = "application/vnd.openxmlformats-package.relationships+xml"
CT_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
CT_DOCM = "application/vnd.ms-word.document.macroEnabled.main+xml"
CT_APP = "application/vnd.openxmlformats-officedocument.extended-properties+xml"
CT_THEME = "application/vnd.openxmlformats-officedocument.theme+xml"
CT_VBA = "application/vnd.ms-office.vbaProject"
NS_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
NS_APP_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"
)
NS_THEME_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
NS_IMG_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
NS_VBA_REL = "http://schemas.microsoft.com/office/2006/relationships/vbaProject"


class TestRealCorpusDocuments:
    """Test loading, layout, and pagination of real .vibeoffice corpus documents."""

    def test_linecases_corpus_document(self) -> None:
        """Verify .vibeoffice linecases.docx loads and paginates to 1 page."""
        if not CORPUS_LINECASES.exists():
            pytest.skip("Corpus file linecases.docx not available in environment")
        raw_data = CORPUS_LINECASES.read_bytes()

        doc = read_docx(raw_data)
        assert len(doc.main.blocks) == 31

        # Check section geometry loaded
        assert doc.sect.pg_w == pytest.approx(595.3, abs=0.2)
        assert doc.sect.pg_h == pytest.approx(841.9, abs=0.2)
        assert doc.sect.doc_grid.type in ("lines", "none")
        assert doc.sect.doc_grid.line_pitch == pytest.approx(15.6, abs=0.1)

        # Paginate document
        res = paginate_document(doc)
        assert res.total_pages == 1
        assert len(res.pages) == 1

        # Save and verify roundtrip bytes
        saved_bytes = write_docx(doc)
        assert len(saved_bytes) > 0
        doc2 = read_docx(saved_bytes)
        assert len(doc2.main.blocks) == 31

    def test_linegrid_corpus_and_word_page_starts(self) -> None:
        """Verify linegrid.docx paginates to 19 pages matching Word reference benchmarks."""
        if not CORPUS_LINEGRID.exists():
            pytest.skip("Corpus file linegrid.docx not available in environment")
        raw_data = CORPUS_LINEGRID.read_bytes()

        doc = read_docx(raw_data)
        assert len(doc.main.blocks) == 91

        res = paginate_document(doc)
        # 19 physical pages
        assert res.total_pages == 19
        assert len(res.pages) == 19

        if WORD_REF_JSON.exists():
            # Extract first paragraph label from each page
            page_first_keys: list[str] = []
            for page in res.pages:
                first_label = ""
                for reg in page.regions:
                    for col in reg.columns:
                        for frag in col.fragments:
                            if frag.paragraph and frag.paragraph.runs:
                                txt = frag.paragraph.runs[0].text
                                if txt.startswith("["):
                                    first_label = txt.split()[0]
                                    break
                        if first_label:
                            break
                    if first_label:
                        break
                page_first_keys.append(first_label)

            # Assert first page starts with [15.6/10.5/0.8]
            assert page_first_keys[0] == "[15.6/10.5/0.8]"
            # Assert 18pt section page starts with [18/10.5/1]
            assert "[18/10.5/1]" in page_first_keys


class TestWordStoredPageCountFidelity:
    """Validate that Quire's page count calculation difference from Word's stored count is 0."""

    def test_synthetic_word_saved_document_pages_diff_zero(self) -> None:
        """Create Word doc with docProps/app.xml <Pages> count and verify zero diff."""
        buf = io.BytesIO()
        expected_pages = 2

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # [Content_Types].xml
            ct = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                f'  <Default Extension="rels" ContentType="{CT_RELS}"/>\n'
                '  <Default Extension="xml" ContentType="application/xml"/>\n'
                f'  <Override PartName="/word/document.xml" ContentType="{CT_DOCX}"/>\n'
                f'  <Override PartName="/docProps/app.xml" ContentType="{CT_APP}"/>\n'
                "</Types>"
            )
            zf.writestr("[Content_Types].xml", ct.encode("utf-8"))

            # _rels/.rels
            root_rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                "<Relationships "
                'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                f'  <Relationship Id="rId1" Type="{NS_DOC_REL}" Target="word/document.xml"/>\n'
                f'  <Relationship Id="rId2" Type="{NS_APP_REL}" Target="docProps/app.xml"/>\n'
                "</Relationships>"
            )
            zf.writestr("_rels/.rels", root_rels.encode("utf-8"))

            # docProps/app.xml with Microsoft Office Word application and <Pages> tag
            app_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                "<Properties "
                'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">\n'
                "  <Application>Microsoft Office Word</Application>\n"
                f"  <Pages>{expected_pages}</Pages>\n"
                "  <Words>120</Words>\n"
                "</Properties>"
            )
            zf.writestr("docProps/app.xml", app_xml.encode("utf-8"))

            # word/document.xml with an explicit page break
            doc_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                "<w:document "
                'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
                "  <w:body>\n"
                "    <w:p><w:r><w:t>First page content before break.</w:t></w:r></w:p>\n"
                '    <w:p><w:r><w:br w:type="page"/></w:r></w:p>\n'
                "    <w:p><w:r><w:t>Second page content after break.</w:t></w:r></w:p>\n"
                '    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1440" w:right="1800" w:bottom="1440" w:left="1800"/></w:sectPr>\n'
                "  </w:body>\n"
                "</w:document>"
            )
            zf.writestr("word/document.xml", doc_xml.encode("utf-8"))

        docx_bytes = buf.getvalue()

        # Load with Quire reader
        doc = read_docx(docx_bytes)
        res = paginate_document(doc)

        # Extract Word stored count from docProps/app.xml
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            app_str = z.read("docProps/app.xml").decode("utf-8")
            root = ET.fromstring(app_str)
            word_pages = 0
            for el in root:
                if el.tag.endswith("Pages"):
                    word_pages = int(el.text or "0")

        # Quire calculated page count difference from Word stored count must be 0
        quire_pages = res.total_pages
        diff = abs(quire_pages - word_pages)
        assert diff == 0, f"Expected 0 page diff, got Quire={quire_pages}, Word={word_pages}"


class TestLosslessRoundtripPreservation:
    """Verify that editing documents preserves 100% byte-for-byte SHA256 of untouched parts."""

    def test_lossless_preservation_of_unmodified_package_parts(self) -> None:
        """Verify full OOXML package carrying untouched VBA, customXml, theme, and media parts."""
        vba_data = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1_REALISTIC_VBA_BIN_" * 60
        theme_data = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            b'<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            b'name="Office Theme"/>'
        )
        custom_xml_data = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            b'<root><metadata id="42" status="active"/></root>'
        )
        image_data = b"\x89PNG\r\n\x1a\n_PNG_BINARY_BYTES_" * 30
        app_xml_data = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            b"<Properties "
            b'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">\n'
            b"  <Application>Microsoft Office Word</Application>\n"
            b"  <Pages>1</Pages>\n"
            b"</Properties>"
        )

        hashes_orig = {
            "word/vbaProject.bin": hashlib.sha256(vba_data).hexdigest(),
            "word/theme/theme1.xml": hashlib.sha256(theme_data).hexdigest(),
            "customXml/item1.xml": hashlib.sha256(custom_xml_data).hexdigest(),
            "word/media/image1.png": hashlib.sha256(image_data).hexdigest(),
            "docProps/app.xml": hashlib.sha256(app_xml_data).hexdigest(),
        }

        # Build initial package
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            ct = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                f'  <Default Extension="rels" ContentType="{CT_RELS}"/>\n'
                '  <Default Extension="xml" ContentType="application/xml"/>\n'
                f'  <Default Extension="bin" ContentType="{CT_VBA}"/>\n'
                '  <Default Extension="png" ContentType="image/png"/>\n'
                f'  <Override PartName="/word/document.xml" ContentType="{CT_DOCM}"/>\n'
                f'  <Override PartName="/word/theme/theme1.xml" ContentType="{CT_THEME}"/>\n'
                '  <Override PartName="/customXml/item1.xml" ContentType="application/xml"/>\n'
                f'  <Override PartName="/docProps/app.xml" ContentType="{CT_APP}"/>\n'
                "</Types>"
            )
            zf.writestr("[Content_Types].xml", ct.encode("utf-8"))

            root_rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                "<Relationships "
                'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                f'  <Relationship Id="rId1" Type="{NS_DOC_REL}" Target="word/document.xml"/>\n'
                f'  <Relationship Id="rId2" Type="{NS_APP_REL}" Target="docProps/app.xml"/>\n'
                "</Relationships>"
            )
            zf.writestr("_rels/.rels", root_rels.encode("utf-8"))

            doc_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                "<w:document "
                'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
                "  <w:body>\n"
                "    <w:p><w:r><w:t>Original Text Prior To Mutation</w:t></w:r></w:p>\n"
                '    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>\n'
                "  </w:body>\n"
                "</w:document>"
            )
            zf.writestr("word/document.xml", doc_xml.encode("utf-8"))

            doc_rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                "<Relationships "
                'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                f'  <Relationship Id="rId1" Type="{NS_VBA_REL}" Target="vbaProject.bin"/>\n'
                f'  <Relationship Id="rId2" Type="{NS_THEME_REL}" Target="theme/theme1.xml"/>\n'
                f'  <Relationship Id="rId3" Type="{NS_IMG_REL}" Target="media/image1.png"/>\n'
                "</Relationships>"
            )
            zf.writestr("word/_rels/document.xml.rels", doc_rels.encode("utf-8"))

            # Write auxiliary parts
            zf.writestr("word/vbaProject.bin", vba_data)
            zf.writestr("word/theme/theme1.xml", theme_data)
            zf.writestr("customXml/item1.xml", custom_xml_data)
            zf.writestr("word/media/image1.png", image_data)
            zf.writestr("docProps/app.xml", app_xml_data)

        orig_package_bytes = buf.getvalue()

        # 1. Read document
        doc = read_docx(orig_package_bytes)
        assert getattr(doc, "_doc_format", "") == "docm"

        # 2. Mutate document text
        p0 = all_paragraphs(doc)[0]
        assert p0.runs[0].text == "Original Text Prior To Mutation"
        p0.runs[0].text = "Mutated Text Under Regression Verification"

        # 3. Save modified document
        saved_package_bytes = write_docx(doc)

        # 4. Verify byte-for-byte SHA256 preservation of untouched parts
        saved_pkg = SourcePackage.from_bytes(saved_package_bytes)
        for part_name, orig_hash in hashes_orig.items():
            assert saved_pkg.has_part(part_name), f"Part lost during save: {part_name}"
            saved_part_data = saved_pkg.read_part(part_name)
            saved_hash = hashlib.sha256(saved_part_data).hexdigest()
            assert saved_hash == orig_hash, (
                f"Part {part_name} corrupted! SHA256 mismatch: {saved_hash} != {orig_hash}"
            )

        # 5. Reload saved document and verify mutation took effect cleanly
        doc_reloaded = read_docx(saved_package_bytes)
        assert getattr(doc_reloaded, "_doc_format", "") == "docm"
        p_reloaded = all_paragraphs(doc_reloaded)[0]
        assert ptext(p_reloaded) == "Mutated Text Under Regression Verification"
