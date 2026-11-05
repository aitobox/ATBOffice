"""Lectern built-in presentation templates subsystem.

Provides template definitions, metadata, and builders for 4 canonical presentation formats
aligned with .vibeoffice/public/lectern/js/templates.js.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.templates.builders import (
    build_event_template,
    build_lesson_template,
    build_meeting_template,
    build_status_template,
)

if TYPE_CHECKING:
    from atboffice.core.templates import TemplateRegistry

LECTERN_TEMPLATE_IDS: list[str] = [
    "status",
    "meeting",
    "lesson",
    "event",
]

BUILDERS: dict[str, Callable[..., Presentation]] = {
    "status": build_status_template,
    "meeting": build_meeting_template,
    "lesson": build_lesson_template,
    "event": build_event_template,
}

LECTERN_TEMPLATE_NAMES: dict[str, str] = {
    "status": "Project Status Report",
    "meeting": "Team Meeting",
    "lesson": "Lesson",
    "event": "Event Announcement",
}


def build_lectern_template(
    template_id: str,
    size: tuple[float, float] = (960.0, 540.0),
) -> Presentation:
    """Build and return a fully populated Presentation model for the specified template ID.

    Args:
        template_id: Identifier of the template ('status', 'meeting', 'lesson', 'event').
        size: Optional (width, height) tuple, defaults to widescreen 16:9 (960.0, 540.0).

    Returns:
        Populated Presentation model ready for editing or rendering.

    Raises:
        KeyError: If template_id is not in LECTERN_TEMPLATE_IDS.
    """
    tid = template_id.lower()
    if tid not in BUILDERS:
        raise KeyError(f"Unknown Lectern template identifier: {template_id!r}")

    builder_fn = BUILDERS[tid]
    pres = builder_fn(size=size)
    pres.props["template"] = tid
    return pres


def register_lectern_templates(registry: TemplateRegistry | None = None) -> None:
    """Bind builder functions for all Lectern templates into TemplateRegistry."""
    from atboffice.core.templates import TemplateRegistry

    target_reg = registry or TemplateRegistry.get_instance()
    for tid in LECTERN_TEMPLATE_IDS:
        tpl = target_reg.get(tid, app="lectern")
        if tpl is not None:
            tpl.builder = lambda win=None, target_id=tid: build_lectern_template(target_id)
