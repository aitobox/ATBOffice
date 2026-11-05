"""Template builders for Lectern's 4 canonical presentation templates."""

from __future__ import annotations

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.templates.base import (
    add_template_slide,
    insert_diagram_placeholder,
    insert_table_placeholder,
)


def _init_presentation(design: str, size: tuple[float, float] = (960.0, 540.0)) -> Presentation:
    """Create a new presentation with the specified design, 16:9 widescreen dimensions, and blank slides."""
    w, h = size
    pres = Presentation.create_new(design_key=design, w=w, h=h, empty=True)
    pres.props["title"] = ""
    pres.hf.num = True
    pres.hf.not_on_title = True
    return pres


def build_status_template(size: tuple[float, float] = (960.0, 540.0)) -> Presentation:
    """Build the 'status' (Project Status Report) template on the blueprint design."""
    pres = _init_presentation("blueprint", size)

    # Slide 1: Title
    add_template_slide(
        pres,
        "title",
        "Project Name",
        ["Status report · Reporting period", "Presented by your name"],
    )

    # Slide 2: Summary
    add_template_slide(
        pres,
        "text",
        "Summary",
        [
            "Overall status: On track / At risk / Off track",
            "One sentence on progress since the last report",
            "One sentence on what needs attention",
        ],
    )

    # Slide 3: Project Phases (Chevron SmartArt)
    s3 = add_template_slide(pres, "text", "Project Phases")
    insert_diagram_placeholder(
        pres, s3, "chevron", ["Discover", "Design", "Build", "Launch"]
    )

    # Slide 4: Milestones Table
    s4 = add_template_slide(pres, "table", "Milestones")
    milestone_rows = [
        ["Milestone", "Owner", "Due", "Status"],
        ["Requirements signed off", "Name", "Date", "Done"],
        ["Design complete", "Name", "Date", "On track"],
        ["First release", "Name", "Date", "At risk"],
        ["Launch", "Name", "Date", "Not started"],
    ]
    milestone_widths = [0.42, 0.20, 0.16, 0.22]
    insert_table_placeholder(pres, s4, milestone_rows, milestone_widths)

    # Slide 5: Done and Next (2 Columns)
    add_template_slide(
        pres,
        "twoText",
        "Done and Next",
        ["Done this period", "\tWhat was finished", "\tWhat was delivered"],
        ["Next period", "\tWhat comes next", "\tWho does it"],
    )

    # Slide 6: Risks and Issues
    add_template_slide(
        pres,
        "text",
        "Risks and Issues",
        [
            "Risk: what could go wrong",
            "\tImpact and what we are doing about it",
            "Issue: what is already wrong",
            "\tWhat it blocks and who is fixing it",
        ],
    )

    # Slide 7: Decisions Needed
    add_template_slide(
        pres,
        "text",
        "Decisions Needed",
        [
            "What you need from the audience",
            "By when, and what happens if it slips",
        ],
    )

    return pres


def build_meeting_template(size: tuple[float, float] = (960.0, 540.0)) -> Presentation:
    """Build the 'meeting' (Team Meeting) template on the meadow design."""
    pres = _init_presentation("meadow", size)

    # Slide 1: Title
    add_template_slide(
        pres,
        "title",
        "Team Meeting",
        ["Date · Time · Room or video link"],
    )

    # Slide 2: Agenda (vProcess SmartArt)
    s2 = add_template_slide(pres, "text", "Agenda")
    insert_diagram_placeholder(
        pres,
        s2,
        "vProcess",
        [
            "Welcome and check-in",
            "Updates from last week",
            "Topic for discussion",
            "Action items and next steps",
        ],
    )

    # Slide 3: Updates (2 Columns)
    add_template_slide(
        pres,
        "twoText",
        "Updates",
        ["Wins", "\tWhat went well", "\tWho to thank"],
        ["Blockers", "\tWhat is in the way", "\tWhat help is needed"],
    )

    # Slide 4: Discussion
    add_template_slide(
        pres,
        "text",
        "Discussion",
        [
            "The question to decide today",
            "\tOption A",
            "\tOption B",
        ],
    )

    # Slide 5: Action Items
    add_template_slide(
        pres,
        "text",
        "Action Items",
        [
            "Action — owner — due date",
            "Action — owner — due date",
            "Action — owner — due date",
        ],
    )

    # Slide 6: Thank You
    add_template_slide(
        pres,
        "title",
        "Thank You",
        ["Next meeting: date and time"],
    )

    return pres


def build_lesson_template(size: tuple[float, float] = (960.0, 540.0)) -> Presentation:
    """Build the 'lesson' (Lesson) template on the parchment design."""
    pres = _init_presentation("parchment", size)

    # Slide 1: Title
    add_template_slide(
        pres,
        "title",
        "Lesson Title",
        ["Course name · Teacher name"],
    )

    # Slide 2: Today We Will
    add_template_slide(
        pres,
        "text",
        "Today We Will",
        [
            "Learn what …",
            "Practise how to …",
            "Be able to explain …",
        ],
    )

    # Slide 3: Key Idea (Radial SmartArt)
    s3 = add_template_slide(pres, "text", "Key Idea")
    insert_diagram_placeholder(
        pres,
        s3,
        "radial",
        [
            "The idea",
            "\tExample",
            "\tWhy it matters",
            "\tCounter-example",
            "\tWhere it is used",
        ],
    )

    # Slide 4: Compare (2 Columns)
    add_template_slide(
        pres,
        "twoText",
        "Compare",
        ["First thing", "\tFeature", "\tFeature"],
        ["Second thing", "\tFeature", "\tFeature"],
    )

    # Slide 5: Your Turn
    add_template_slide(
        pres,
        "text",
        "Your Turn",
        [
            "A question or exercise for the class",
            "How long they have, and in pairs or alone",
        ],
    )

    # Slide 6: Summary and Homework
    add_template_slide(
        pres,
        "text",
        "Summary and Homework",
        [
            "Three things to remember",
            "Homework: what to do, due when",
        ],
    )

    return pres


def build_event_template(size: tuple[float, float] = (960.0, 540.0)) -> Presentation:
    """Build the 'event' (Event Announcement) template on the night design."""
    pres = _init_presentation("night", size)

    # Slide 1: Title
    add_template_slide(
        pres,
        "title",
        "Event Name",
        ["Day, date · Time", "Place"],
    )

    # Slide 2: What to Expect
    add_template_slide(
        pres,
        "text",
        "What to Expect",
        [
            "The highlight of the event",
            "Who is speaking or performing",
            "Food, drinks and activities",
        ],
    )

    # Slide 3: Programme (Timeline SmartArt)
    s3 = add_template_slide(pres, "text", "Programme")
    insert_diagram_placeholder(
        pres,
        s3,
        "timeline",
        [
            "Time — opening",
            "Time — main part",
            "Time — break",
            "Time — closing",
        ],
    )

    # Slide 4: Getting There
    add_template_slide(
        pres,
        "text",
        "Getting There",
        [
            "Address",
            "Public transport and parking",
            "Accessibility",
        ],
    )

    # Slide 5: See You There
    add_template_slide(
        pres,
        "title",
        "See You There",
        ["RSVP by date · contact"],
    )

    return pres
