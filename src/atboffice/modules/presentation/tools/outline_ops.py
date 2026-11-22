"""Outlining helpers: Summary Slide and Move Up / Move Down for paragraphs."""

from __future__ import annotations

from typing import Any

from atboffice.modules.presentation.models.slide import Slide, create_slide
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun

TITLE_TYPES = ("title", "ctrTitle")
BODY_TYPES = ("body", "obj", "subTitle")


def _placeholder(slide: Slide, types: tuple[str, ...]) -> Any | None:
    for sh in slide.shapes:
        ph = getattr(sh, "placeholder", None)
        if ph is not None and ph.type in types:
            return sh
    return None


def slide_title(slide: Slide) -> str:
    sh = _placeholder(slide, TITLE_TYPES)
    text = sh.text.plain_text if sh is not None and sh.text else ""
    return " ".join(text.split())


def build_summary_slide(
    presentation: Any, indices: list[int], title: str
) -> tuple[Slide, int] | None:
    """PowerPoint "Summary Slide": a bulleted list of the chosen slides' titles.

    The new slide is inserted before the first chosen slide. Slides without a title are
    skipped; returns None when none of the chosen slides has one.
    Returns ``(slide, index)``.
    """
    chosen = sorted({i for i in indices if 0 <= i < len(presentation.slides)})
    titles = [t for t in (slide_title(presentation.slides[i]) for i in chosen) if t]
    if not titles:
        return None
    first = chosen[0]
    design = presentation.get_design_for_slide(presentation.slides[first])
    slide = create_slide(layout="text", design=design)
    t_shape = _placeholder(slide, TITLE_TYPES)
    b_shape = _placeholder(slide, BODY_TYPES)
    if t_shape is not None:
        t_shape.text = TextBody.from_plain_text(title)
    if b_shape is not None:
        body = b_shape.text or TextBody.create_empty()
        body.paragraphs = [Paragraph(level=0, runs=[TextRun(text=t)]) for t in titles]
        b_shape.text = body
    presentation.insert_slide(first, slide)
    return slide, first


def move_paragraph(body: TextBody, index: int, direction: int) -> int | None:
    """Swap paragraph ``index`` with its neighbour; returns its new index or None."""
    target = index + (1 if direction > 0 else -1)
    if not (0 <= index < len(body.paragraphs)) or not (0 <= target < len(body.paragraphs)):
        return None
    paras = body.paragraphs
    paras[index], paras[target] = paras[target], paras[index]
    return target
