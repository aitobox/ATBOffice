"""Issue #376: DATE/TIME fields and date controls keep their stored value on load."""

from __future__ import annotations

import datetime
import io
import zipfile
from pathlib import Path

from atboffice.modules.writer.io.docx_reader import read_docx
from atboffice.modules.writer.io.docx_writer import write_docx
from atboffice.modules.writer.layout.pagination import (
    _evaluate_hf_paragraph,
    paginate_document,
)
from atboffice.modules.writer.models.document import (
    Document,
    FieldBeginItem,
    FieldEndItem,
    Paragraph,
    TextItem,
    plain_text,
)
from atboffice.modules.writer.models.field import insert_field, update_fields
from atboffice.modules.writer.models.properties import RunProperties

FIXTURE = (
    Path(__file__).parent / "docs" / "word" / "docx" / "libreoffice__tdf146973_signatureBlock.docx"
)
EN_DATE = "12 April 2026"
UK_DATE = "12 квітня 2026 р."


def _field_results(p: Paragraph) -> list[list[TextItem]]:
    """Return the result TextItems of each top-level field in the paragraph."""
    out: list[list[TextItem]] = []
    cur: list[TextItem] | None = None
    in_result = False
    for it in p.runs:
        if isinstance(it, FieldBeginItem):
            cur, in_result = [], False
        elif type(it).__name__ == "FieldSeparateItem" and cur is not None:
            in_result = True
        elif isinstance(it, FieldEndItem) and cur is not None:
            out.append(cur)
            cur = None
        elif isinstance(it, TextItem) and cur is not None and in_result:
            cur.append(it)
    return out


def _assert_stored_dates(doc: Document) -> None:
    p = doc.main.blocks[0]
    assert isinstance(p, Paragraph)
    results = _field_results(p)
    assert ["".join(t.text for t in r) for r in results] == [EN_DATE, UK_DATE]
    for res in results:
        for t in res:
            # cached result runs carry no colour; the blue lives only on the fldChar runs
            assert t.r_pr.color in ("auto", None, "")
            assert t.r_pr.color != "2B579A"


def test_fixture_dates_keep_stored_value_after_pagination():
    doc = read_docx(FIXTURE)
    paginate_document(doc)
    _assert_stored_dates(doc)
    assert plain_text(doc.main.blocks[0]).count(EN_DATE) == 1


def test_fixture_dates_survive_save_and_reload():
    doc = read_docx(FIXTURE)
    paginate_document(doc)
    doc2 = read_docx(write_docx(doc))
    paginate_document(doc2)
    _assert_stored_dates(doc2)


def test_explicit_update_fields_still_refreshes_date():
    doc = Document()
    p = Paragraph(runs=[TextItem(text="x")])
    doc.main.blocks = [p]
    insert_field(p, 1, "DATE", r'DATE \@ "yyyy-MM-dd"', cached_text="old-date")
    paginate_document(doc)
    assert "old-date" in plain_text(p)
    assert update_fields(doc) is True
    assert datetime.date.today().strftime("%Y-%m-%d") in plain_text(p)


def test_layout_fields_still_refresh_and_keep_result_formatting():
    doc = Document()
    p = Paragraph(runs=[TextItem(text="Page ")])
    doc.main.blocks = [p]
    insert_field(p, 5, "PAGE", "PAGE", cached_text="99", r_pr=RunProperties(color="2B579A"))
    res_rpr = RunProperties(color="FF0000")
    # result run has its own formatting distinct from the field-begin run
    for it in p.runs:
        if isinstance(it, TextItem) and it.text == "99":
            it.r_pr = res_rpr
    paginate_document(doc)
    res = _field_results(p)[0]
    assert "".join(t.text for t in res) == "1"
    assert res[0].r_pr.color == "FF0000"


def test_header_footer_date_keeps_cached_text_but_page_updates():
    doc = Document()
    p = Paragraph(runs=[])
    insert_field(p, 0, "DATE", r'DATE \@ "yyyy-MM-dd"', cached_text="stored")
    p.runs.append(TextItem(text=" / "))
    insert_field(p, len(plain_text(p)), "PAGE", "PAGE", cached_text="0")
    out = _evaluate_hf_paragraph(p, doc, page_number=3, total_pages=5)
    assert [("".join(t.text for t in r)) for r in _field_results(out)] == ["stored", "3"]


def _docx_with_body(body_xml: str) -> bytes:
    """Clone the fixture package, replacing the body of word/document.xml."""
    src = zipfile.ZipFile(FIXTURE)
    doc_xml = src.read("word/document.xml").decode("utf-8")
    head = doc_xml[: doc_xml.index("<w:body>") + len("<w:body>")]
    tail = doc_xml[doc_xml.index("<w:sectPr") :]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "word/document.xml":
                data = (head + body_xml + tail).encode("utf-8")
            dst.writestr(info, data)
    return buf.getvalue()


def _date_sdt(full_date: str, content_run: str, placeholder: bool) -> str:
    fd = f' w:fullDate="{full_date}"' if full_date else ""
    plc = "<w:showingPlcHdr/>" if placeholder else ""
    return (
        "<w:p><w:sdt><w:sdtPr>"
        '<w:placeholder><w:docPart w:val="DefaultPlaceholder"/></w:placeholder>'
        f"{plc}<w:date{fd}>"
        '<w:dateFormat w:val="d MMMM yyyy"/><w:lid w:val="en-US"/></w:date>'
        "</w:sdtPr><w:sdtContent>"
        f"<w:r><w:t>{content_run}</w:t></w:r>"
        "</w:sdtContent></w:sdt></w:p>"
    )


def test_date_sdt_shows_stored_value():
    data = _docx_with_body(_date_sdt("2026-04-12T00:00:00Z", EN_DATE, placeholder=False))
    doc = read_docx(data)
    paginate_document(doc)
    assert plain_text(doc.main.blocks[0]) == EN_DATE
    doc2 = read_docx(write_docx(doc))
    assert plain_text(doc2.main.blocks[0]) == EN_DATE


def test_date_sdt_without_full_date_shows_placeholder():
    prompt = "Click or tap to enter a date."
    doc = read_docx(_docx_with_body(_date_sdt("", prompt, placeholder=True)))
    paginate_document(doc)
    assert plain_text(doc.main.blocks[0]) == prompt
