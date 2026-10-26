"""Unit tests for Quire Mail Merge engine, data sources, and wizard dialogs."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.models.document import (
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    TextItem,
)
from atboffice.modules.writer.models.field import (
    insert_field,
    update_fields,
)
from atboffice.modules.writer.models.mailmerge import (
    ADDRESS_FIELDS,
    MailMergeDataSource,
    MailMergeEngine,
    parse_delimited,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# 1. Delimited Parsing Tests
# ---------------------------------------------------------------------------


def test_parse_delimited_csv() -> None:
    csv_text = "Name,Age,City\nAlice,30,New York\nBob,25,\"San Francisco, CA\"\n"
    rows = parse_delimited(csv_text)
    assert len(rows) == 3
    assert rows[0] == ["Name", "Age", "City"]
    assert rows[1] == ["Alice", "30", "New York"]
    assert rows[2] == ["Bob", "25", "San Francisco, CA"]


def test_parse_delimited_tsv_and_bom() -> None:
    tsv_text = "\ufeffFirst\tLast\tCompany\nJohn\tDoe\tAcme Corp\n"
    rows = parse_delimited(tsv_text)
    assert len(rows) == 2
    assert rows[0] == ["First", "Last", "Company"]
    assert rows[1] == ["John", "Doe", "Acme Corp"]


def test_parse_delimited_semicolon_and_escaped_quotes() -> None:
    semi_text = 'Product;Description;Price\nWidget;"Top ""Quality"" Tool";$9.99\n'
    rows = parse_delimited(semi_text)
    assert len(rows) == 2
    assert rows[0] == ["Product", "Description", "Price"]
    assert rows[1] == ["Widget", 'Top "Quality" Tool', "$9.99"]


# ---------------------------------------------------------------------------
# 2. DataSource Model & Alias Tests
# ---------------------------------------------------------------------------


def test_data_source_creation_and_aliases() -> None:
    headers = ["First Name", "Last Name", "ZIP Code", "CustomField"]
    rows = [
        ["Alice", "Smith", "94102", "Val1"],
        ["Bob", "Jones", "10001", "Val2"],
        ["Charlie", "Brown", "60601", "Val3"],
    ]
    ds = MailMergeDataSource(name="Contacts", fields=headers, rows=rows)
    assert len(ds.rows) == 3
    assert len(ds.active_records()) == 3

    # Direct match
    assert ds.get_value(0, "First Name") == "Alice"
    assert ds.get_value(0, "CustomField") == "Val1"

    # Normalized case-insensitive
    assert ds.get_value(1, "first_name") == "Bob"
    assert ds.get_value(1, "lastname") == "Jones"

    # Standard Word alias matching
    assert ds.get_value(0, "fname") == "Alice"
    assert ds.get_value(0, "zip") == "94102"
    assert ds.get_value(1, "postalcode") == "10001"
    assert ds.get_value(2, "familyname") == "Brown"

    # Missing field returns empty string without error
    assert ds.get_value(0, "NonExistentField") == ""


def test_data_source_filtering_and_sorting() -> None:
    headers = ["Name", "Score"]
    rows = [
        ["Charlie", "85"],
        ["Alice", "95"],
        ["Bob", "90"],
    ]
    ds = MailMergeDataSource(name="Scores", fields=headers, rows=rows)

    # Exclude record index 1 (Alice)
    ds.included.remove(1)
    assert ds.active_records() == [0, 2]

    # Sort by Name ascending
    ds.sort_by(column_index=0, descending=False)
    # Charlie was 0, Bob was 2. Sorted: Bob, Charlie (plus Alice at index 1)
    assert [ds.rows[i][0] for i in ds.active_records()] == ["Bob", "Charlie"]


# ---------------------------------------------------------------------------
# 3. MERGEFIELD Field Evaluation Tests
# ---------------------------------------------------------------------------


def test_mergefield_evaluation() -> None:
    headers = ["First Name", "Last Name", "Company", "Title"]
    rows = [
        ["Alice", "Smith", "Acme Inc", "Dr."],
        ["Bob", "Brown", "", ""],
    ]
    ds = MailMergeDataSource(name="Recipients", fields=headers, rows=rows)
    engine = MailMergeEngine(data_source=ds)

    # Design mode (no preview): returns placeholder «FieldName»
    engine.preview = False
    assert engine.evaluate_merge_instruction("MERGEFIELD First_Name") == "«First_Name»"

    # Preview mode: evaluates to data value
    engine.preview = True
    assert engine.evaluate_merge_instruction("MERGEFIELD First_Name", 0) == "Alice"
    assert engine.evaluate_merge_instruction("MERGEFIELD First_Name", 1) == "Bob"

    # Formatting switch (\* Upper)
    assert engine.evaluate_merge_instruction('MERGEFIELD First_Name \\* Upper', 0) == "ALICE"

    # Prefix switch (\b) and suffix switch (\f)
    assert (
        engine.evaluate_merge_instruction('MERGEFIELD Title \\b "Dear " \\f " "', 0)
        == "Dear Dr. "
    )
    # When field value is empty, \b and \f are not output
    assert engine.evaluate_merge_instruction('MERGEFIELD Title \\b "Dear " \\f " "', 1) == ""

    # MERGEREC and MERGESEQ
    assert engine.evaluate_merge_instruction("MERGEREC", 0) == "1"
    assert engine.evaluate_merge_instruction("MERGEREC", 1) == "2"


def test_document_field_update_with_mailmerge() -> None:
    doc = Document()
    p = Paragraph(runs=[TextItem("Hello ")])
    doc.main.paras = [p]

    insert_field(
        p,
        offset=6,
        field_type="MERGEFIELD",
        instr="MERGEFIELD CustomerName",
        cached_text="«CustomerName»",
    )

    headers = ["CustomerName"]
    rows = [["Acme Corp"], ["Global Industries"]]
    ds = MailMergeDataSource(name="Customers", fields=headers, rows=rows)
    engine = MailMergeEngine(data_source=ds)

    # Link engine to document
    doc.mailmerge_engine = engine  # type: ignore[attr-defined]

    # Without preview
    engine.preview = False
    update_fields(doc)
    text_runs = [r.text for r in p.runs if isinstance(r, TextItem)]
    assert "«CustomerName»" in text_runs

    # With preview enabled for record 1
    engine.preview = True
    engine.current_record = 1
    update_fields(doc)
    text_runs = [r.text for r in p.runs if isinstance(r, TextItem)]
    assert "Global Industries" in text_runs


# ---------------------------------------------------------------------------
# 4. Batch Document Merging Tests
# ---------------------------------------------------------------------------


def test_batch_build_merged_document() -> None:
    doc = Document()
    doc.props["title"] = "Offer Letter"

    p1 = Paragraph(runs=[TextItem("Dear "), TextItem("Mr. Smith"), TextItem(",")])
    # Replace second item with a field
    p1.runs = [
        TextItem("Dear "),
        FieldBeginItem(field_type="MERGEFIELD", instr="MERGEFIELD FullName"),
        FieldSeparateItem(),
        TextItem("«FullName»"),
        FieldEndItem(),
        TextItem(","),
    ]

    p2 = Paragraph(runs=[
        TextItem("Welcome to "),
        FieldBeginItem(field_type="MERGEFIELD", instr="MERGEFIELD Company"),
        FieldSeparateItem(),
        TextItem("«Company»"),
        FieldEndItem(),
        TextItem("!"),
    ])

    doc.main.paras = [p1, p2]

    headers = ["FullName", "Company"]
    rows = [
        ["Alice Wonder", "Wonderland Co"],
        ["Bob Builder", "Construction Ltd"],
    ]
    ds = MailMergeDataSource(name="Staff", fields=headers, rows=rows)
    engine = MailMergeEngine(data_source=ds)

    merged_doc = engine.build_merged_document(doc)
    assert merged_doc is not None
    assert "merged" in merged_doc.props.get("title", "").lower()

    # Two records -> main.paras should have blocks for record 1 and record 2
    # In letters mode, each record gets section break with nextPage
    paras = merged_doc.main.paras
    assert len(paras) >= 4

    p_texts = ["".join(r.text for r in p.runs if isinstance(r, TextItem)) for p in paras]
    all_text = " ".join(p_texts)
    assert "Dear Alice Wonder," in all_text
    assert "Welcome to Wonderland Co!" in all_text
    assert "Dear Bob Builder," in all_text
    assert "Welcome to Construction Ltd!" in all_text


def test_blank_line_suppression_in_merge() -> None:
    doc = Document()
    # Paragraph flagged as address block line
    p_addr2 = Paragraph(runs=[
        FieldBeginItem(field_type="MERGEFIELD", instr="MERGEFIELD AddressLine2"),
        FieldSeparateItem(),
        TextItem("«AddressLine2»"),
        FieldEndItem(),
    ])
    p_addr2._was_address_block = True  # type: ignore[attr-defined]

    p_city = Paragraph(runs=[
        FieldBeginItem(field_type="MERGEFIELD", instr="MERGEFIELD City"),
        FieldSeparateItem(),
        TextItem("«City»"),
        FieldEndItem(),
    ])

    doc.main.paras = [p_addr2, p_city]

    headers = ["AddressLine2", "City"]
    rows = [
        ["Suite 400", "Chicago"],
        ["", "Seattle"],  # Empty AddressLine2 -> Should suppress p_addr2
    ]
    ds = MailMergeDataSource(name="Addresses", fields=headers, rows=rows)
    engine = MailMergeEngine(data_source=ds)

    merged_doc = engine.build_merged_document(doc)
    assert merged_doc is not None

    # Seattle's section should NOT contain an empty paragraph for AddressLine2
    recs_text = [
        "".join(r.text for r in p.runs if isinstance(r, TextItem))
        for p in merged_doc.main.paras
    ]
    # Check that Suite 400 is in the text
    assert "Suite 400" in recs_text
    # And empty string paragraph from AddressLine2 is suppressed
    assert "" not in recs_text


# ---------------------------------------------------------------------------
# 5. UI Dialog Tests
# ---------------------------------------------------------------------------


def test_mailmerge_dialogs(qapp) -> None:
    from atboffice.modules.writer.dialogs.mailmerge_wizard import (
        AddressListDialog,
        InsertMergeFieldDialog,
        MailMergeRecipientsDialog,
        MailMergeWizardDialog,
    )

    doc = Document()
    headers = ["First Name", "Last Name", "Email"]
    rows = [
        ["Alice", "Smith", "alice@example.com"],
        ["Bob", "Jones", "bob@example.com"],
    ]
    ds = MailMergeDataSource(name="TestRecipients", fields=headers, rows=rows)
    engine = MailMergeEngine(data_source=ds)

    # 1. Insert Merge Field Dialog
    insert_dlg = InsertMergeFieldDialog(engine=engine)
    assert insert_dlg.field_list.count() == 3
    insert_dlg.close()

    # 2. Recipients Dialog
    recip_dlg = MailMergeRecipientsDialog(engine=engine)
    assert recip_dlg.table.rowCount() == 2
    assert recip_dlg.table.columnCount() == 4  # Checkbox + 3 fields
    recip_dlg.close()

    # 3. Address List Dialog
    addr_dlg = AddressListDialog()
    assert len(addr_dlg.fields) == len(ADDRESS_FIELDS)
    addr_dlg.close()

    # 4. Wizard Dialog
    wizard = MailMergeWizardDialog(doc=doc, engine=engine)
    assert wizard.current_step == 1
    wizard.next_step()
    assert wizard.current_step == 2
    wizard.prev_step()
    assert wizard.current_step == 1
    wizard.close()


def test_load_data_source_from_csv_disk(tmp_path: Path) -> None:
    from atboffice.modules.writer.models.mailmerge import load_data_source_from_csv

    csv_file = tmp_path / "test_contacts.csv"
    csv_content = (
        "First Name,Last Name,City\nAlice,Wonder,London\nBob,Marley,Kingston\n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    ds = load_data_source_from_csv(csv_file)
    assert ds.name == "test_contacts.csv"
    assert ds.fields == ["First Name", "Last Name", "City"]
    assert len(ds.rows) == 2
    assert ds.get_value(0, "first_name") == "Alice"
    assert ds.get_value(1, "last_name") == "Marley"

    # Missing file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        load_data_source_from_csv(tmp_path / "non_existent.csv")

    # Empty file raises ValueError
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        load_data_source_from_csv(empty_file)


def test_insert_address_block_and_greeting_line() -> None:
    doc = Document()
    p = Paragraph(runs=[TextItem("Header")])
    doc.main.paras = [p]

    headers = ["Title", "First Name", "Last Name", "Address Line 1", "City", "State", "ZIP Code"]
    rows = [["Mr.", "John", "Doe", "123 Main St", "Springfield", "IL", "62701"]]
    ds = MailMergeDataSource(name="Contacts", fields=headers, rows=rows)
    engine = MailMergeEngine(data_source=ds)

    # Insert greeting line
    greeting_p = Paragraph()
    doc.main.paras.append(greeting_p)
    engine.insert_greeting_line(greeting_p, 0, greeting="Dear", salutation=":")
    p_text = "".join(r.text for r in greeting_p.runs if isinstance(r, TextItem))
    assert "Dear" in p_text
    assert "«First_Name»" in p_text or "«Title»" in p_text

    # Insert address block
    created_paras = engine.insert_address_block(doc, insert_after_p=p)
    assert len(created_paras) > 0
    all_addr_text = " ".join(
        "".join(r.text for r in cp.runs if isinstance(r, TextItem))
        for cp in created_paras
    )
    assert "«City»" in all_addr_text or "«State»" in all_addr_text


def test_writer_view_mailmerge_integration(qapp) -> None:
    from atboffice.modules.writer.view import WriterView

    view = WriterView()
    headers = ["FullName", "Title"]
    rows = [["Ada Lovelace", "Countess"], ["Charles Babbage", "Professor"]]
    ds = MailMergeDataSource(name="Pioneers", fields=headers, rows=rows)
    view.mailmerge_engine.set_data_source(ds)

    # Toggle preview
    assert view.toggle_mail_merge_preview() is True
    assert view.mailmerge_engine.preview is True

    # Step record
    next_rec = view.step_mail_merge_record(1)
    assert next_rec == 1
    assert view.mailmerge_engine.current_record == 1

    view.close()


def test_export_merged_pdf(tmp_path: Path) -> None:
    doc = Document()
    p = Paragraph(runs=[
        TextItem("Hello "),
        FieldBeginItem(field_type="MERGEFIELD", instr="MERGEFIELD Recipient"),
        FieldSeparateItem(),
        TextItem("«Recipient»"),
        FieldEndItem(),
        TextItem("!"),
    ])
    doc.main.paras = [p]

    headers = ["Recipient"]
    rows = [["Alice"], ["Bob"]]
    ds = MailMergeDataSource(name="Recipients", fields=headers, rows=rows)
    engine = MailMergeEngine(data_source=ds)

    pdf_out = tmp_path / "output_test.pdf"
    success = engine.export_merged_pdf(doc, pdf_out)
    assert success is True
    assert pdf_out.exists()
    assert pdf_out.stat().st_size > 0

