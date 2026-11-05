"""Correspondence templates: Letter, Memo, and Fax."""

from __future__ import annotations

from atboffice.modules.writer.models.document import (
    Cell,
    Document,
    Paragraph,
    Row,
    TabItem,
    Table,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    BorderProperties,
    CellProperties,
    IndentProperties,
    ParagraphProperties,
    RunProperties,
    SpacingProperties,
    TableProperties,
    TabStop,
)
from atboffice.modules.writer.templates.base import (
    date_field,
    define_style,
    placeholder,
)


def build_letter_template(doc: Document) -> None:
    """Build Contemporary Letter template."""
    doc.sect.mt = 72.0
    doc.sect.ml = 90.0
    doc.sect.mr = 90.0

    define_style(
        doc,
        "CompanyName",
        "Company Name",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(after=24.0),
            borders={
                "bottom": BorderProperties(
                    val="single", sz=0.75, color="808080", space=4.0
                )
            },
        ),
        r_pr=RunProperties(font="Arial Black", sz=16.0, spacing=-0.5),
    )
    define_style(
        doc,
        "ReturnAddress",
        "Return Address",
        p_pr=ParagraphProperties(jc="right"),
        r_pr=RunProperties(font="Arial", sz=8.0),
    )
    define_style(
        doc,
        "InsideAddress",
        "Inside Address",
        r_pr=RunProperties(font="Arial", sz=10.0),
    )
    define_style(
        doc,
        "BodyTextLetter",
        "Body Text Letter",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(after=12.0, line=1.15, line_rule="auto"),
            jc="both",
        ),
        r_pr=RunProperties(font="Arial", sz=10.0),
    )

    doc.main.blocks = [
        Paragraph(
            runs=placeholder("Type return address"),
            p_pr=ParagraphProperties(style="ReturnAddress"),
        ),
        Paragraph(
            runs=placeholder("Company Name Here", RunProperties(font="Arial Black")),
            p_pr=ParagraphProperties(style="CompanyName"),
        ),
        Paragraph(
            runs=date_field("MMMM d, yyyy"),
            p_pr=ParagraphProperties(
                style="InsideAddress", sp=SpacingProperties(after=24.0)
            ),
        ),
        Paragraph(
            runs=placeholder("Type recipient’s address"),
            p_pr=ParagraphProperties(
                style="InsideAddress", sp=SpacingProperties(after=24.0)
            ),
        ),
        Paragraph(
            runs=[
                TextItem(text="Dear "),
                *placeholder("Recipient"),
                TextItem(text=":"),
            ],
            p_pr=ParagraphProperties(style="BodyTextLetter"),
        ),
        Paragraph(
            runs=[
                TextItem(
                    text="Write the body of your letter here. To change the look of every "
                    "paragraph at once, open Format ▸ Styles and Formatting and modify the "
                    "style instead of formatting text by hand."
                )
            ],
            p_pr=ParagraphProperties(style="BodyTextLetter"),
        ),
        Paragraph(
            runs=[
                TextItem(
                    text="To return to the main view, simply keep typing. Placeholders like the "
                    "ones above disappear as soon as you click them and type."
                )
            ],
            p_pr=ParagraphProperties(style="BodyTextLetter"),
        ),
        Paragraph(
            runs=[TextItem(text="Sincerely,")],
            p_pr=ParagraphProperties(
                style="BodyTextLetter", sp=SpacingProperties(after=36.0)
            ),
        ),
        Paragraph(
            runs=placeholder("Type your name"),
            p_pr=ParagraphProperties(style="InsideAddress"),
        ),
        Paragraph(
            runs=placeholder("Type job title"),
            p_pr=ParagraphProperties(style="InsideAddress"),
        ),
    ]


def build_memo_template(doc: Document) -> None:
    """Build Professional Memo template."""
    define_style(
        doc,
        "MemoTitle",
        "Memo Title",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(after=24.0),
            borders={
                "bottom": BorderProperties(val="single", sz=3.0, color="000000", space=6.0)
            },
        ),
        r_pr=RunProperties(font="Arial Black", sz=36.0, spacing=-1.5),
    )
    define_style(
        doc,
        "MessageHeader",
        "Message Header",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(after=6.0),
            ind=IndentProperties(left=72.0, first_line=-72.0),
            tabs=[TabStop(pos=72.0, align="left")],
        ),
        r_pr=RunProperties(font="Arial", sz=10.0),
    )
    define_style(
        doc,
        "MemoBody",
        "Memo Body",
        p_pr=ParagraphProperties(sp=SpacingProperties(after=12.0)),
        r_pr=RunProperties(font="Arial", sz=10.0),
    )

    def lbl(text: str) -> TextItem:
        return TextItem(text=text, r_pr=RunProperties(b=True, caps=True))

    doc.main.blocks = [
        Paragraph(
            runs=placeholder("Company Name Here"),
            p_pr=ParagraphProperties(style="MemoBody", jc="right"),
        ),
        Paragraph(
            runs=[TextItem(text="Memo")],
            p_pr=ParagraphProperties(style="MemoTitle"),
        ),
        Paragraph(
            runs=[lbl("To:"), TabItem(), *placeholder("Type name")],
            p_pr=ParagraphProperties(style="MessageHeader"),
        ),
        Paragraph(
            runs=[lbl("From:"), TabItem(), *placeholder("Type name")],
            p_pr=ParagraphProperties(style="MessageHeader"),
        ),
        Paragraph(
            runs=[lbl("CC:"), TabItem(), *placeholder("Type name")],
            p_pr=ParagraphProperties(style="MessageHeader"),
        ),
        Paragraph(
            runs=[lbl("Date:"), TabItem(), *date_field("M/d/yyyy")],
            p_pr=ParagraphProperties(style="MessageHeader"),
        ),
        Paragraph(
            runs=[lbl("Re:"), TabItem(), *placeholder("Type subject")],
            p_pr=ParagraphProperties(
                style="MessageHeader",
                borders={
                    "bottom": BorderProperties(
                        val="single", sz=0.75, color="000000", space=8.0
                    )
                },
                sp=SpacingProperties(after=18.0),
            ),
        ),
        Paragraph(
            runs=[TextItem(text="How to Use This Memo Template", r_pr=RunProperties(b=True))],
            p_pr=ParagraphProperties(style="MemoBody"),
        ),
        Paragraph(
            runs=[
                TextItem(
                    text="Start the memo with the point you need the reader to act on. "
                    "Keep the headings short; the Style box on the Formatting toolbar has "
                    "Heading 1–3 for structure."
                )
            ],
            p_pr=ParagraphProperties(style="MemoBody"),
        ),
        Paragraph(
            runs=[
                TextItem(
                    text="The decorative shapes are ordinary drawing objects: click one and "
                    "press Delete to remove it, or drag it somewhere else."
                )
            ],
            p_pr=ParagraphProperties(style="MemoBody"),
        ),
    ]


def build_fax_template(doc: Document) -> None:
    """Build Elegant Fax template."""
    define_style(
        doc,
        "FaxTitle",
        "Fax Title",
        p_pr=ParagraphProperties(
            jc="center", sp=SpacingProperties(before=24.0, after=24.0)
        ),
        r_pr=RunProperties(font="Garamond", sz=36.0, caps=True, spacing=6.0),
    )
    define_style(
        doc,
        "FaxLabel",
        "Fax Label",
        r_pr=RunProperties(font="Garamond", sz=10.0, caps=True, b=True),
    )

    p1 = Paragraph(
        runs=placeholder("Company Name", RunProperties(font="Garamond", sz=14.0, small_caps=True)),
        p_pr=ParagraphProperties(jc="center"),
    )
    p2 = Paragraph(
        runs=[TextItem(text="Facsimile Transmittal")],
        p_pr=ParagraphProperties(style="FaxTitle"),
    )

    tb = Table(
        grid=[60.0, 156.0, 60.0, 156.0],
        tbl_pr=TableProperties(w=432.0, w_type="dxa", style="TableNormal"),
    )
    cells_data = [
        [
            ("To:", True),
            ("Click here and type name", False),
            ("From:", True),
            ("Click here and type name", False),
        ],
        [
            ("Fax:", True),
            ("Click here and type fax number", False),
            ("Pages:", True),
            ("Click here and type number of pages", False),
        ],
        [
            ("Phone:", True),
            ("Click here and type phone number", False),
            ("Date:", True),
            (None, False),
        ],
        [
            ("Re:", True),
            ("Click here and type subject of fax", False),
            ("CC:", True),
            ("Click here and type name", False),
        ],
    ]

    for row_idx, row_items in enumerate(cells_data):
        row_cells: list[Cell] = []
        for col_idx, (text, is_label) in enumerate(row_items):
            c_props = CellProperties(w=tb.grid[col_idx], w_type="dxa")
            p_props = ParagraphProperties()
            runs = []
            if is_label:
                p_props.style = "FaxLabel"
                runs = [TextItem(text=text or "")]
            elif text is not None:
                runs = placeholder(text, RunProperties(font="Garamond"))
            else:
                runs = date_field("MMMM d, yyyy", RunProperties(font="Garamond"))

            cell = Cell(tc_pr=c_props, blocks=[Paragraph(runs=runs, p_pr=p_props)])
            row_cells.append(cell)
        tb.rows.append(Row(cells=row_cells))

    rule = BorderProperties(val="single", sz=0.75, color="000000", space=6.0)
    p3 = Paragraph(
        runs=[
            TextItem(
                text=(
                    "☐ Urgent   ☐ For Review   ☐ Please Comment   "
                    "☐ Please Reply   ☐ Please Recycle"
                ),
                r_pr=RunProperties(font="Garamond", sz=10.0),
            )
        ],
        p_pr=ParagraphProperties(
            sp=SpacingProperties(before=18.0, after=18.0),
            borders={"top": rule, "bottom": rule},
        ),
    )
    p4 = Paragraph(
        runs=[
            TextItem(
                text="Comments: ",
                r_pr=RunProperties(b=True, caps=True, font="Garamond"),
            ),
            *placeholder("Type any comments", RunProperties(font="Garamond")),
        ],
        p_pr=ParagraphProperties(sp=SpacingProperties(before=12.0)),
    )

    doc.main.blocks = [p1, p2, tb, p3, p4]
