"""Report, Agenda, and Meeting Minutes templates."""

from __future__ import annotations

from atboffice.modules.writer.models.document import (
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    Story,
    TabItem,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    BorderProperties,
    NumberingRef,
    ParagraphProperties,
    RunProperties,
    SpacingProperties,
    TabStop,
)
from atboffice.modules.writer.models.styles import builtin_styles
from atboffice.modules.writer.templates.base import (
    add_num,
    date_field,
    define_style,
    field_run,
    make_bullet_abs,
    placeholder,
    simple_table,
)


def build_report_template(doc: Document) -> None:
    """Build Professional Report template."""
    # Modify existing builtin styles or add customized styles
    if "Title" in doc.styles:
        doc.styles["Title"].r_pr = RunProperties(
            font="Arial Black", sz=32.0, b=False, kern=14.0
        )
        doc.styles["Title"].p_pr = ParagraphProperties(
            jc="left",
            sp=SpacingProperties(before=180.0, after=12.0),
            outline_level=0,
            borders={
                "bottom": BorderProperties(
                    val="single", sz=3.0, color="000000", space=6.0
                )
            },
        )

    if "Subtitle" in doc.styles:
        doc.styles["Subtitle"].r_pr = RunProperties(
            font="Arial", sz=14.0, i=False, color="595959"
        )
        doc.styles["Subtitle"].p_pr = ParagraphProperties(
            jc="left", sp=SpacingProperties(after=120.0)
        )

    if "Heading1" in doc.styles:
        doc.styles["Heading1"].r_pr = RunProperties(
            font="Arial Black", sz=16.0, b=False
        )
        doc.styles["Heading1"].p_pr.page_break_before = False
        doc.styles["Heading1"].p_pr.sp = SpacingProperties(before=24.0, after=6.0)

    if "Heading2" in doc.styles:
        doc.styles["Heading2"].r_pr = RunProperties(
            font="Arial", sz=13.0, b=True
        )

    if "Normal" in doc.styles:
        doc.styles["Normal"].r_pr = RunProperties(font="Garamond", sz=11.0)
        doc.styles["Normal"].p_pr = ParagraphProperties(
            sp=SpacingProperties(after=8.0, line=1.15, line_rule="auto")
        )

    if "TOCHeading" not in doc.styles:
        builtins = builtin_styles()
        if "TOCHeading" in builtins:
            doc.styles["TOCHeading"] = builtins["TOCHeading"]
        else:
            define_style(
                doc,
                "TOCHeading",
                "TOC Heading",
                p_pr=ParagraphProperties(sp=SpacingProperties(before=12.0, after=6.0)),
                r_pr=RunProperties(font="Arial", sz=14.0, b=True),
            )

    doc.main.blocks = [
        Paragraph(
            runs=placeholder("Company Name"),
            p_pr=ParagraphProperties(jc="left"),
            r_pr=RunProperties(font="Arial", sz=10.0, caps=True, b=True),
        ),
        Paragraph(
            runs=placeholder("Type Report Title Here"),
            p_pr=ParagraphProperties(style="Title"),
        ),
        Paragraph(
            runs=[TextItem(text="A Professional Report")],
            p_pr=ParagraphProperties(style="Subtitle"),
        ),
        Paragraph(runs=date_field("MMMM d, yyyy")),
        Paragraph(
            runs=[TextItem(text="Table of Contents")],
            p_pr=ParagraphProperties(style="TOCHeading", page_break_before=True),
        ),
        Paragraph(
            runs=[
                TextItem(
                    text="Press F9 in the table of contents below to bring it up to date.",
                    r_pr=RunProperties(i=True, color="7F7F7F"),
                )
            ]
        ),
        Paragraph(
            runs=[
                FieldBeginItem(instr=' TOC \\o "1-3" \\h \\z \\u '),
                FieldSeparateItem(),
                TextItem(
                    text="Right-click and choose Update Field to build the table of contents."
                ),
                FieldEndItem(),
            ]
        ),
        Paragraph(
            runs=[TextItem(text="Introduction")],
            p_pr=ParagraphProperties(style="Heading1", page_break_before=True),
        ),
        Paragraph(
            runs=[
                TextItem(
                    text="Replace this text with your own. Headings set in Heading 1 and "
                    "Heading 2 feed the table of contents, which rebuilds itself when "
                    "you update it."
                )
            ]
        ),
        Paragraph(
            runs=[TextItem(text="Using This Report")],
            p_pr=ParagraphProperties(style="Heading2"),
        ),
        Paragraph(
            runs=[
                TextItem(
                    text="Change the margins and paper size with File ▸ Page Setup. Add a "
                    "header or footer with View ▸ Header and Footer; page numbers come "
                    "from Insert ▸ Page Numbers."
                )
            ]
        ),
        Paragraph(
            runs=[TextItem(text="Findings")],
            p_pr=ParagraphProperties(style="Heading1"),
        ),
        Paragraph(
            runs=[
                TextItem(
                    text="Describe your findings here. Insert a chart with Insert ▸ Picture ▸ "
                    "Chart, and add a caption with Insert ▸ Reference ▸ Caption."
                )
            ]
        ),
        Paragraph(
            runs=[TextItem(text="Conclusion")],
            p_pr=ParagraphProperties(style="Heading1"),
        ),
        Paragraph(runs=[TextItem(text="Summarize your conclusions and recommendations.")]),
    ]

    # Setup footer story with page number
    ftr_para = Paragraph(
        runs=[
            TabItem(),
            TabItem(),
            TextItem(text="Page "),
            *field_run("PAGE", "1"),
        ],
        p_pr=ParagraphProperties(style="Footer"),
    )
    doc.hf["rf"] = Story(kind="ftr", blocks=[ftr_para])
    doc.sect.refs = {"hdr": {}, "ftr": {"default": "rf"}}


def build_agenda_template(doc: Document) -> None:
    """Build Meeting Agenda template."""
    define_style(
        doc,
        "AgendaTitle",
        "Agenda Title",
        p_pr=ParagraphProperties(
            jc="center", sp=SpacingProperties(after=6.0)
        ),
        r_pr=RunProperties(
            font="Tahoma", sz=26.0, b=True, color="1F3864"
        ),
    )
    define_style(
        doc,
        "AgendaItem",
        "Agenda Item",
        p_pr=ParagraphProperties(
            tabs=[TabStop(pos=360.0, align="left")],
            sp=SpacingProperties(after=6.0),
        ),
        r_pr=RunProperties(font="Tahoma", sz=10.0),
    )

    p1 = Paragraph(
        runs=placeholder("Meeting Title"),
        p_pr=ParagraphProperties(style="AgendaTitle"),
    )
    p2 = Paragraph(
        runs=[
            *date_field("dddd, MMMM d, yyyy"),
            TextItem(text="  •  "),
            *placeholder("Time"),
            TextItem(text="  •  "),
            *placeholder("Location"),
        ],
        p_pr=ParagraphProperties(jc="center", sp=SpacingProperties(after=18.0)),
        r_pr=RunProperties(font="Tahoma", sz=10.0),
    )

    rows = [
        ["Time", "Item", "Owner"],
        ["9:00 am", "Welcome and introductions", "Chair"],
        ["9:15 am", "Review of last meeting", "Secretary"],
        ["9:30 am", "Project updates", "Team leads"],
        ["10:15 am", "Open discussion", "All"],
        ["10:45 am", "Action items and next steps", "Chair"],
    ]
    tb = simple_table(rows, [72.0, 252.0, 108.0], header_fill="1F3864", p_style="AgendaItem")

    p3 = Paragraph(
        runs=[TextItem(text="Additional Instructions:", r_pr=RunProperties(b=True))],
        p_pr=ParagraphProperties(style="AgendaItem", sp=SpacingProperties(before=18.0)),
    )
    p4 = Paragraph(
        runs=placeholder("Type any notes or preparation needed"),
        p_pr=ParagraphProperties(style="AgendaItem"),
    )

    doc.main.blocks = [p1, p2, tb, p3, p4]


def build_minutes_template(doc: Document) -> None:
    """Build Meeting Minutes template."""
    define_style(
        doc,
        "MinutesTitle",
        "Minutes Title",
        p_pr=ParagraphProperties(sp=SpacingProperties(after=2.0)),
        r_pr=RunProperties(font="Tahoma", sz=24.0, b=True, color="1F3864"),
    )
    define_style(
        doc,
        "MinutesHeading",
        "Minutes Heading",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(before=16.0, after=6.0),
            keep_next=True,
            borders={
                "bottom": BorderProperties(
                    val="single", sz=0.75, color="8EAADB", space=2.0
                )
            },
        ),
        r_pr=RunProperties(font="Tahoma", sz=11.0, b=True, color="1F3864"),
    )
    define_style(
        doc,
        "MinutesText",
        "Minutes Text",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(after=4.0),
            tabs=[TabStop(pos=90.0, align="left")],
        ),
        r_pr=RunProperties(font="Tahoma", sz=10.0),
    )

    abs_id = add_num(doc, make_bullet_abs("•", "Symbol", ""))

    def head(text: str) -> Paragraph:
        return Paragraph(
            runs=[TextItem(text=text)],
            p_pr=ParagraphProperties(style="MinutesHeading"),
        )

    def line(lbl_text: str, item_runs: list) -> Paragraph:
        return Paragraph(
            runs=[
                TextItem(text=lbl_text, r_pr=RunProperties(b=True)),
                TabItem(),
                *item_runs,
            ],
            p_pr=ParagraphProperties(style="MinutesText"),
        )

    def topic(num_val: int) -> Paragraph:
        return Paragraph(
            runs=[
                TextItem(text=f"{num_val}.  ", r_pr=RunProperties(b=True)),
                *placeholder("Topic", RunProperties(b=True)),
            ],
            p_pr=ParagraphProperties(
                style="MinutesText", sp=SpacingProperties(before=8.0, after=2.0)
            ),
        )

    def point(txt: str) -> Paragraph:
        return Paragraph(
            runs=placeholder(txt),
            p_pr=ParagraphProperties(
                style="MinutesText", num=NumberingRef(id=abs_id, lvl=0)
            ),
        )

    action_table = simple_table(
        [
            ["Action", "Owner", "Due"],
            ["", "", ""],
            ["", "", ""],
            ["", "", ""],
            ["", "", ""],
        ],
        [276.0, 96.0, 72.0],
        header_fill="1F3864",
        p_style="MinutesText",
    )

    doc.main.blocks = [
        Paragraph(
            runs=placeholder("Meeting Name"),
            p_pr=ParagraphProperties(style="MinutesTitle"),
        ),
        Paragraph(
            runs=[
                TextItem(
                    text="Minutes of the meeting",
                    r_pr=RunProperties(color="595959"),
                )
            ],
            p_pr=ParagraphProperties(
                style="MinutesText", sp=SpacingProperties(after=12.0)
            ),
        ),
        line("Date:", date_field("dddd, MMMM d, yyyy")),
        line("Time:", placeholder("Start – End")),
        line("Location:", placeholder("Room or video link")),
        line("Chair:", placeholder("Name")),
        line("Minutes by:", placeholder("Name")),
        head("Attendees"),
        Paragraph(
            runs=placeholder("Names of everyone present"),
            p_pr=ParagraphProperties(style="MinutesText"),
        ),
        line("Apologies:", placeholder("Names")),
        head("Discussion"),
        topic(1),
        point("What was discussed"),
        point("What was decided"),
        topic(2),
        point("What was discussed"),
        point("What was decided"),
        head("Action Items"),
        action_table,
        head("Next Meeting"),
        line("Date:", placeholder("Date and time")),
        line("Location:", placeholder("Room or video link")),
    ]
