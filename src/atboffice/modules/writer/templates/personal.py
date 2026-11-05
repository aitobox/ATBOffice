"""Personal and general document templates: Resume, Todo, Flyer, and Recipe."""

from __future__ import annotations

from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TabItem,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    BorderProperties,
    IndentProperties,
    NumberingRef,
    ParagraphProperties,
    RunProperties,
    SpacingProperties,
    TabStop,
)
from atboffice.modules.writer.templates.base import (
    add_num,
    date_field,
    define_style,
    make_bullet_abs,
    make_number_abs,
    placeholder,
    simple_table,
)


def build_resume_template(doc: Document) -> None:
    """Build Contemporary Résumé template."""
    doc.sect.ml = 90.0
    doc.sect.mr = 90.0

    define_style(
        doc,
        "Name",
        "Name",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(after=6.0),
            borders={
                "bottom": BorderProperties(val="single", sz=1.5, color="000000", space=6.0)
            },
        ),
        r_pr=RunProperties(font="Arial", sz=22.0, b=True, spacing=-1.0),
    )
    define_style(
        doc,
        "Address1",
        "Address 1",
        p_pr=ParagraphProperties(jc="right"),
        r_pr=RunProperties(font="Arial", sz=8.0),
    )
    define_style(
        doc,
        "SectionTitle",
        "Section Title",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(before=18.0, after=6.0), keep_next=True
        ),
        r_pr=RunProperties(font="Arial", sz=10.0, b=True, caps=True, spacing=1.0),
    )
    define_style(
        doc,
        "Objective",
        "Objective",
        p_pr=ParagraphProperties(sp=SpacingProperties(after=12.0)),
        r_pr=RunProperties(font="Arial", sz=10.0),
    )
    define_style(
        doc,
        "CompanyNameRes",
        "Company Name (Résumé)",
        p_pr=ParagraphProperties(
            tabs=[TabStop(pos=160.0, align="left"), TabStop(pos=432.0, align="right")],
            sp=SpacingProperties(before=6.0),
        ),
        r_pr=RunProperties(font="Arial", sz=10.0),
    )
    define_style(
        doc,
        "JobTitle",
        "Job Title",
        p_pr=ParagraphProperties(sp=SpacingProperties(after=4.0)),
        r_pr=RunProperties(font="Arial Black", sz=9.0),
    )
    define_style(
        doc,
        "Achievement",
        "Achievement",
        p_pr=ParagraphProperties(
            ind=IndentProperties(left=18.0, first_line=-18.0),
            sp=SpacingProperties(after=3.0),
        ),
        r_pr=RunProperties(font="Arial", sz=10.0),
    )

    abs_id = add_num(doc, make_bullet_abs("•", "Symbol", ""))

    def ach(text: str) -> Paragraph:
        return Paragraph(
            runs=[TextItem(text=text)],
            p_pr=ParagraphProperties(
                style="Achievement", num=NumberingRef(id=abs_id, lvl=0)
            ),
        )

    doc.main.blocks = [
        Paragraph(
            runs=placeholder("Street Address • City, ST ZIP Code • Phone • E-mail"),
            p_pr=ParagraphProperties(style="Address1"),
        ),
        Paragraph(
            runs=placeholder("Your Name"),
            p_pr=ParagraphProperties(style="Name"),
        ),
        Paragraph(
            runs=[TextItem(text="Objective")],
            p_pr=ParagraphProperties(style="SectionTitle"),
        ),
        Paragraph(
            runs=placeholder("Type your objective here"),
            p_pr=ParagraphProperties(style="Objective"),
        ),
        Paragraph(
            runs=[TextItem(text="Experience")],
            p_pr=ParagraphProperties(style="SectionTitle"),
        ),
        Paragraph(
            runs=[
                *placeholder("Start – End"),
                TabItem(),
                *placeholder("Company Name", RunProperties(b=True)),
                TabItem(),
                *placeholder("City, State"),
            ],
            p_pr=ParagraphProperties(style="CompanyNameRes"),
        ),
        Paragraph(
            runs=placeholder("Job Title"),
            p_pr=ParagraphProperties(style="JobTitle"),
        ),
        ach("Describe a result you achieved, with a number if you can."),
        ach("Name a responsibility and what changed because of you."),
        ach("Add one line per achievement; keep each to a single sentence."),
        Paragraph(
            runs=[TextItem(text="Education")],
            p_pr=ParagraphProperties(style="SectionTitle"),
        ),
        Paragraph(
            runs=[
                *placeholder("Start – End"),
                TabItem(),
                *placeholder("School Name", RunProperties(b=True)),
                TabItem(),
                *placeholder("City, State"),
            ],
            p_pr=ParagraphProperties(style="CompanyNameRes"),
        ),
        Paragraph(
            runs=placeholder("Degree, major and honors"),
            p_pr=ParagraphProperties(style="Achievement"),
        ),
        Paragraph(
            runs=[TextItem(text="Interests")],
            p_pr=ParagraphProperties(style="SectionTitle"),
        ),
        Paragraph(
            runs=placeholder(
                "Clubs, volunteer work and interests that support your application"
            ),
            p_pr=ParagraphProperties(style="Objective"),
        ),
        Paragraph(
            runs=[TextItem(text="Tips")],
            p_pr=ParagraphProperties(style="SectionTitle"),
        ),
        Paragraph(
            runs=[
                TextItem(
                    text="Click any bracketed placeholder and type over it. The Section Title, "
                    "Job Title and Achievement styles in the Style box keep every entry lined up."
                )
            ],
            p_pr=ParagraphProperties(style="Objective"),
        ),
    ]


def build_todo_template(doc: Document) -> None:
    """Build To-Do Checklist template."""
    define_style(
        doc,
        "ListTitle",
        "List Title",
        p_pr=ParagraphProperties(sp=SpacingProperties(after=0.0)),
        r_pr=RunProperties(
            font="Trebuchet MS", sz=28.0, b=True, color="2A64C8"
        ),
    )
    define_style(
        doc,
        "ListHeading",
        "List Heading",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(before=18.0, after=6.0),
            keep_next=True,
            borders={
                "bottom": BorderProperties(
                    val="single", sz=1.5, color="2A64C8", space=2.0
                )
            },
        ),
        r_pr=RunProperties(
            font="Trebuchet MS", sz=13.0, b=True, color="2A64C8"
        ),
    )
    define_style(
        doc,
        "Checklist",
        "Checklist",
        p_pr=ParagraphProperties(
            ind=IndentProperties(left=24.0, first_line=-24.0),
            tabs=[TabStop(pos=24.0, align="left")],
            sp=SpacingProperties(after=7.0),
        ),
        r_pr=RunProperties(font="Trebuchet MS", sz=11.0),
    )

    def head(text: str) -> Paragraph:
        return Paragraph(
            runs=[TextItem(text=text)],
            p_pr=ParagraphProperties(style="ListHeading"),
        )

    def box(label: str) -> Paragraph:
        return Paragraph(
            runs=[
                TextItem(
                    text="☐",
                    r_pr=RunProperties(font="Segoe UI Symbol", sz=13.0),
                ),
                TabItem(),
                *placeholder(label),
            ],
            p_pr=ParagraphProperties(style="Checklist"),
        )

    doc.main.blocks = [
        Paragraph(
            runs=[TextItem(text="To-Do List")],
            p_pr=ParagraphProperties(style="ListTitle"),
        ),
        Paragraph(
            runs=date_field(
                "dddd, MMMM d, yyyy",
                RunProperties(font="Trebuchet MS", sz=11.0, color="595959"),
            ),
            p_pr=ParagraphProperties(sp=SpacingProperties(after=6.0)),
        ),
        head("Today"),
        box("Most important task"),
        box("Task"),
        box("Task"),
        box("Task"),
        head("This Week"),
        box("Task"),
        box("Task"),
        box("Task"),
        head("Calls and Errands"),
        box("Call or errand"),
        box("Call or errand"),
        head("Notes"),
        Paragraph(
            runs=placeholder(
                "Anything to remember",
                RunProperties(font="Trebuchet MS", sz=11.0),
            ),
            p_pr=ParagraphProperties(sp=SpacingProperties(after=6.0)),
        ),
        Paragraph(
            runs=[
                TextItem(
                    text="Tip: select a ☐ and type ☒ (Insert ▸ Symbol) to tick it off, "
                    "or strike the line through with Format ▸ Font.",
                    r_pr=RunProperties(
                        i=True, color="7F7F7F", sz=9.0, font="Trebuchet MS"
                    ),
                )
            ],
            p_pr=ParagraphProperties(sp=SpacingProperties(before=18.0)),
        ),
    ]


def build_flyer_template(doc: Document) -> None:
    """Build Event Flyer template."""
    doc.sect.mt = 54.0
    doc.sect.mb = 54.0

    define_style(
        doc,
        "FlyerKicker",
        "Flyer Kicker",
        p_pr=ParagraphProperties(
            jc="center", sp=SpacingProperties(before=36.0, after=6.0)
        ),
        r_pr=RunProperties(
            font="Trebuchet MS",
            sz=16.0,
            caps=True,
            spacing=3.0,
            color="E0682D",
            b=True,
        ),
    )
    define_style(
        doc,
        "FlyerTitle",
        "Flyer Title",
        p_pr=ParagraphProperties(jc="center", sp=SpacingProperties(after=12.0)),
        r_pr=RunProperties(
            font="Arial Black", sz=48.0, color="1F3864", spacing=-1.0
        ),
    )
    define_style(
        doc,
        "FlyerTagline",
        "Flyer Tagline",
        p_pr=ParagraphProperties(jc="center", sp=SpacingProperties(after=30.0)),
        r_pr=RunProperties(font="Georgia", sz=18.0, i=True, color="595959"),
    )
    define_style(
        doc,
        "FlyerWhen",
        "Flyer When",
        p_pr=ParagraphProperties(
            jc="center", sp=SpacingProperties(before=6.0, after=6.0)
        ),
        r_pr=RunProperties(
            font="Trebuchet MS", sz=22.0, b=True, color="1F3864"
        ),
    )
    define_style(
        doc,
        "FlyerText",
        "Flyer Text",
        p_pr=ParagraphProperties(
            jc="center",
            sp=SpacingProperties(after=10.0, line=1.2, line_rule="auto"),
            ind=IndentProperties(left=36.0, right=36.0),
        ),
        r_pr=RunProperties(font="Georgia", sz=13.0),
    )

    rule = BorderProperties(val="single", sz=3.0, color="E0682D", space=12.0)

    doc.main.blocks = [
        Paragraph(
            runs=placeholder("You are invited"),
            p_pr=ParagraphProperties(style="FlyerKicker"),
        ),
        Paragraph(
            runs=placeholder("Event Name"),
            p_pr=ParagraphProperties(style="FlyerTitle"),
        ),
        Paragraph(
            runs=placeholder("A short line that makes people want to come"),
            p_pr=ParagraphProperties(style="FlyerTagline"),
        ),
        Paragraph(
            runs=placeholder("Saturday, June 6"),
            p_pr=ParagraphProperties(style="FlyerWhen", borders={"top": rule}),
        ),
        Paragraph(
            runs=placeholder("2:00 pm – 6:00 pm"),
            p_pr=ParagraphProperties(style="FlyerWhen"),
        ),
        Paragraph(
            runs=placeholder(
                "Place name, street address, city",
                RunProperties(sz=16.0, b=False),
            ),
            p_pr=ParagraphProperties(
                style="FlyerWhen",
                borders={"bottom": rule},
                sp=SpacingProperties(after=30.0),
            ),
        ),
        Paragraph(
            runs=placeholder(
                "Describe the event: what will happen, who it is for, and what to bring. "
                "Two or three sentences are enough."
            ),
            p_pr=ParagraphProperties(style="FlyerText"),
        ),
        Paragraph(
            runs=placeholder(
                "Food • Music • Games for the kids",
                RunProperties(b=True, color="E0682D"),
            ),
            p_pr=ParagraphProperties(
                style="FlyerText", sp=SpacingProperties(after=36.0)
            ),
        ),
        Paragraph(
            runs=[
                TextItem(text="RSVP: ", r_pr=RunProperties(b=True)),
                *placeholder("name, phone or e-mail, by a date"),
            ],
            p_pr=ParagraphProperties(style="FlyerText"),
        ),
        Paragraph(
            runs=placeholder(
                "Free entry · Everyone welcome",
                RunProperties(sz=11.0, color="7F7F7F"),
            ),
            p_pr=ParagraphProperties(style="FlyerText"),
        ),
    ]


def build_recipe_template(doc: Document) -> None:
    """Build Recipe Card template."""
    define_style(
        doc,
        "RecipeTitle",
        "Recipe Title",
        p_pr=ParagraphProperties(sp=SpacingProperties(after=4.0)),
        r_pr=RunProperties(font="Georgia", sz=28.0, b=True, color="7A3B10"),
    )
    define_style(
        doc,
        "RecipeHeading",
        "Recipe Heading",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(before=16.0, after=6.0), keep_next=True
        ),
        r_pr=RunProperties(font="Georgia", sz=14.0, b=True, color="7A3B10"),
    )
    define_style(
        doc,
        "RecipeText",
        "Recipe Text",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(after=4.0, line=1.15, line_rule="auto")
        ),
        r_pr=RunProperties(font="Georgia", sz=11.0),
    )

    bullets = add_num(doc, make_bullet_abs("•", "Symbol", ""))
    steps = add_num(doc, make_number_abs("decimal", "%1."))

    def ing(text: str) -> Paragraph:
        return Paragraph(
            runs=placeholder(text),
            p_pr=ParagraphProperties(
                style="RecipeText", num=NumberingRef(id=bullets, lvl=0)
            ),
        )

    def step(text: str) -> Paragraph:
        return Paragraph(
            runs=placeholder(text),
            p_pr=ParagraphProperties(
                style="RecipeText",
                num=NumberingRef(id=steps, lvl=0),
                sp=SpacingProperties(after=6.0),
            ),
        )

    def head(text: str) -> Paragraph:
        return Paragraph(
            runs=[TextItem(text=text)],
            p_pr=ParagraphProperties(style="RecipeHeading"),
        )

    servings_table = simple_table(
        [
            ["Serves", "Prep time", "Cook time", "Oven"],
            ["4", "15 min", "30 min", "180 °C / 350 °F"],
        ],
        [108.0, 108.0, 108.0, 108.0],
        header_fill="7A3B10",
        p_style="RecipeText",
    )

    doc.main.blocks = [
        Paragraph(
            runs=placeholder("Recipe Name"),
            p_pr=ParagraphProperties(style="RecipeTitle"),
        ),
        Paragraph(
            runs=placeholder(
                "One line about the dish: where it comes from, when you make it",
                RunProperties(i=True, color="595959"),
            ),
            p_pr=ParagraphProperties(
                style="RecipeText", sp=SpacingProperties(after=10.0)
            ),
        ),
        servings_table,
        head("Ingredients"),
        ing("Quantity and ingredient"),
        ing("Quantity and ingredient"),
        ing("Quantity and ingredient"),
        ing("Quantity and ingredient"),
        ing("Quantity and ingredient"),
        head("Method"),
        step("First step"),
        step("Next step"),
        step("Next step"),
        step("Serve"),
        head("Notes"),
        Paragraph(
            runs=placeholder(
                "Variations, what to serve it with, how long it keeps"
            ),
            p_pr=ParagraphProperties(style="RecipeText"),
        ),
    ]
