"""Quire built-in document template system.

Provides template definitions, metadata, and builders for 10 canonical document formats
aligned with .vibeoffice/public/quire/js/templates.js.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from atboffice.modules.writer.models.document import Document, DocumentModel
from atboffice.modules.writer.templates.base import (
    add_num,
    date_field,
    define_style,
    format_word_date,
    make_bullet_abs,
    make_number_abs,
    placeholder,
    simple_table,
)
from atboffice.modules.writer.templates.letters import (
    build_fax_template,
    build_letter_template,
    build_memo_template,
)
from atboffice.modules.writer.templates.personal import (
    build_flyer_template,
    build_recipe_template,
    build_resume_template,
    build_todo_template,
)
from atboffice.modules.writer.templates.reports import (
    build_agenda_template,
    build_minutes_template,
    build_report_template,
)

if TYPE_CHECKING:
    from atboffice.core.templates import TemplateRegistry

QUIRE_TEMPLATE_IDS: list[str] = [
    "letter",
    "memo",
    "fax",
    "resume",
    "report",
    "agenda",
    "minutes",
    "todo",
    "flyer",
    "recipe",
]

BUILDERS: dict[str, Callable[[Document], None]] = {
    "letter": build_letter_template,
    "memo": build_memo_template,
    "fax": build_fax_template,
    "resume": build_resume_template,
    "report": build_report_template,
    "agenda": build_agenda_template,
    "minutes": build_minutes_template,
    "todo": build_todo_template,
    "flyer": build_flyer_template,
    "recipe": build_recipe_template,
}

TEMPLATE_NAMES: dict[str, str] = {
    "letter": "Contemporary Letter",
    "memo": "Professional Memo",
    "fax": "Elegant Fax",
    "resume": "Contemporary Résumé",
    "report": "Professional Report",
    "agenda": "Meeting Agenda",
    "minutes": "Meeting Minutes",
    "todo": "To-Do Checklist",
    "flyer": "Event Flyer",
    "recipe": "Recipe",
}


def build_quire_template(template_id: str) -> Document:
    """Build and return a fully structured Document for the specified template ID.

    Args:
        template_id: Identifier of the template (e.g. 'letter', 'memo', 'resume').

    Returns:
        Populated Document model ready for editing or rendering.

    Raises:
        KeyError: If template_id is not in QUIRE_TEMPLATE_IDS.
    """
    tid = template_id.lower()
    if tid not in BUILDERS:
        raise KeyError(f"Unknown Quire template identifier: {template_id!r}")

    doc = Document()
    BUILDERS[tid](doc)

    doc.props["title"] = ""
    doc.props["template"] = TEMPLATE_NAMES.get(tid, tid.capitalize())
    return doc


def register_quire_templates(registry: TemplateRegistry | None = None) -> None:
    """Register or update builder callbacks for Quire templates in TemplateRegistry."""
    from atboffice.core.templates import TemplateRegistry

    reg = registry or TemplateRegistry.get_instance()
    for tid in QUIRE_TEMPLATE_IDS:
        tpl = reg.get(tid, app="quire")
        if tpl is not None:
            # Lambda ignores optional window parameter and calls build_quire_template
            tpl.builder = lambda win=None, target_id=tid: build_quire_template(target_id)


__all__ = [
    "BUILDERS",
    "DocumentModel",
    "QUIRE_TEMPLATE_IDS",
    "TEMPLATE_NAMES",
    "add_num",
    "build_agenda_template",
    "build_fax_template",
    "build_flyer_template",
    "build_letter_template",
    "build_memo_template",
    "build_minutes_template",
    "build_quire_template",
    "build_recipe_template",
    "build_report_template",
    "build_resume_template",
    "build_todo_template",
    "date_field",
    "define_style",
    "format_word_date",
    "make_bullet_abs",
    "make_number_abs",
    "placeholder",
    "register_quire_templates",
    "simple_table",
]
