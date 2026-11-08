"""Cascading placeholder resolver for Lectern presentation slides.

Resolves visual shapes, frames, and text styles following the hierarchy:
Slide (explicit shapes) -> Slide Layout -> Slide Master (design template).
"""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

from atboffice.modules.presentation.models.layouts import PROMPTS, _ph_name, layout_frames
from atboffice.modules.presentation.models.shape import Fill, Line, PlaceholderInfo, Shape
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.designs import DesignTemplate
    from atboffice.modules.presentation.models.presentation import Presentation
    from atboffice.modules.presentation.models.slide import Slide


def evaluate_field_text(
    run: TextRun,
    slide_index: int = 0,
    presentation: Presentation | None = None,
) -> str:
    """Evaluate dynamic fields (slide number, date) for a text run."""
    field_type = (run.field or "").lower()
    t = run.text or ""

    first_num = getattr(presentation, "first_num", 1) if presentation else 1

    # 1. Slide number fields
    if field_type in ("slnum", "slidenum", "sldnum") or t in ("‹#›", "<#>"):
        return str(slide_index + first_num)

    # 2. Date / Time fields
    if field_type.startswith("datetime") or field_type in ("date", "dt"):
        # Format current date
        now = datetime.date.today()
        if field_type in ("datetime1", "datetime", "date", "dt"):
            return now.strftime("%Y-%m-%d")
        elif field_type == "datetime2":
            return now.strftime("%B %d, %Y")
        elif field_type == "datetime3":
            return now.strftime("%d %B %Y")
        return now.strftime("%Y-%m-%d")

    return t


def apply_cascading_placeholder_styles(
    shape: Shape,
    design: DesignTemplate,
) -> None:
    """Cascade missing font family, font size, color, bullet, and alignment from master to shape."""
    ph = shape.placeholder
    if ph is None or shape.text is None:
        return

    ph_type = ph.type or "body"
    is_title = ph_type in ("title", "ctrTitle")
    is_footer = ph_type in ("dt", "ftr", "sldNum")
    is_body = ph_type in ("body", "obj")

    major_font = design.fonts.get("major", "Arial")
    minor_font = design.fonts.get("minor", "Calibri")
    target_font = major_font if is_title else minor_font

    # Color
    if is_title:
        target_color = (
            getattr(design.colors, "dk2", None) or getattr(design.colors, "dk1", "#000000")
        )
    elif is_footer:
        target_color = getattr(design.colors, "dk1", "#000000")
    else:
        target_color = getattr(design.colors, "dk1", "#000000")

    # Alignment
    if ph_type == "ctrTitle":
        def_algn = getattr(design, "ctr_title_algn", "ctr")
    elif ph_type == "subTitle":
        def_algn = getattr(design, "sub_title_algn", "ctr")
    elif ph_type == "sldNum":
        def_algn = "r"
    elif ph_type == "ftr":
        def_algn = "ctr"
    elif ph_type == "dt":
        def_algn = "l"
    else:
        def_algn = "l"

    # Sizes per outline level
    def _size_for_level(lvl: int) -> float:
        if ph_type == "ctrTitle":
            return 40.0
        if ph_type == "title":
            return 36.0
        if ph_type == "subTitle":
            return 24.0
        if is_footer:
            return 12.0
        # Body sizes: 28, 24, 20, 16, 14
        body_sizes = [28.0, 24.0, 20.0, 16.0, 14.0]
        return body_sizes[min(lvl, len(body_sizes) - 1)]

    # Bullets for body
    body_bullets = ["•", "–", "▪", "▫", "•"]

    for para in shape.text.paragraphs:
        lvl = para.level
        if "algn" not in para.props:
            para.props["algn"] = def_algn

        if is_body and "bu" not in para.props:
            b_char = body_bullets[min(lvl, len(body_bullets) - 1)]
            para.props["bu"] = {"t": "char", "ch": b_char}

        for r in para.runs:
            if r.font is None:
                r.font = target_font
            if r.size is None:
                r.size = _size_for_level(lvl)
            if r.color is None:
                r.color = target_color


def _create_footer_placeholder(
    ph_type: str,
    box: tuple[float, float, float, float],
    design: DesignTemplate,
    slide_idx: int = 0,
    presentation: Presentation | None = None,
    text: str = "",
    is_auto: bool = False,
    fmt: str = "datetime1",
) -> Shape:
    """Create a synthesized footer placeholder shape (dt, ftr, sldNum)."""
    x, y, w, h = box
    run = TextRun(text=text)

    if ph_type == "sldNum":
        first_num = getattr(presentation, "first_num", 1) if presentation else 1
        num_str = str(slide_idx + first_num)
        run = TextRun(text=num_str, field="slNum")
    elif ph_type == "dt":
        if is_auto:
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            run = TextRun(text=today_str, field=fmt or "datetime1")
        else:
            run = TextRun(text=text)

    tb = TextBody(
        anchor="t",
        wrap=True,
        autofit="none",
        paragraphs=[
            Paragraph(
                level=0,
                props={
                    "algn": "r" if ph_type == "sldNum" else ("ctr" if ph_type == "ftr" else "l")
                },
                runs=[run],
            )
        ],
    )

    sh = Shape(
        id=f"hf_{ph_type}_{uuid.uuid4().hex[:6]}",
        type="text",
        name=_ph_name(ph_type, 0),
        geom="rect",
        x=float(x),
        y=float(y),
        w=float(w),
        h=float(h),
        rot=0.0,
        fill=Fill.none(),
        line=Line.none(),
        placeholder=PlaceholderInfo(type=ph_type, idx=0),
        text=tb,
    )
    apply_cascading_placeholder_styles(sh, design)
    return sh


def resolve_unoverridden_placeholders(
    slide: Slide,
    presentation: Presentation | None = None,
) -> list[Shape]:
    """Calculate and return unoverridden placeholder shapes from Slide Layout and Master."""
    if presentation:
        design = presentation.get_design_for_slide(slide)
    else:
        from atboffice.modules.presentation.models.designs import build_design

        design = build_design("default", 960.0, 540.0)

    unoverridden: list[Shape] = []

    # Map existing placeholders on the slide
    existing_ph_keys = {
        (s.placeholder.type, s.placeholder.idx) for s in slide.shapes if s.placeholder
    }
    existing_types = {s.placeholder.type for s in slide.shapes if s.placeholder}

    slide_idx = (
        presentation.slides.index(slide)
        if (presentation and slide in presentation.slides)
        else 0
    )

    # 1. Unoverridden Layout Placeholders (title, body, subTitle, obj, etc.)
    frames = layout_frames(slide.layout, design)
    for fr in frames:
        fr_type = fr["type"]
        fr_idx = fr.get("idx", 0)
        if (fr_type, fr_idx) not in existing_ph_keys and fr_type not in existing_types:
            from atboffice.modules.presentation.models.layouts import make_placeholder

            sh = make_placeholder(fr, design)
            # Set prompt text if empty
            prompt = PROMPTS.get(fr_type, "")
            if prompt and (not sh.text or sh.text.is_empty()):
                sh.text = TextBody(
                    anchor="ctr" if fr_type in ("title", "ctrTitle") else "t",
                    wrap=True,
                    paragraphs=[
                        Paragraph(
                            level=0,
                            runs=[
                                TextRun(
                                    text=prompt,
                                    color=getattr(design.colors, "lt2", "#808080"),
                                )
                            ],
                        )
                    ],
                )
            apply_cascading_placeholder_styles(sh, design)
            unoverridden.append(sh)

    # 2. Master Header / Footer Placeholders (dt, ftr, sldNum)
    if not getattr(slide, "hide_master", False):
        hf = getattr(presentation, "hf", None) if presentation else None
        is_title = slide.layout == "title"
        suppress_on_title = is_title and bool(hf and getattr(hf, "not_on_title", False))

        if not suppress_on_title:
            # sldNum
            show_num = bool(hf and getattr(hf, "num", False))
            if show_num and "sldNum" not in existing_types:
                box = design.placeholder_frames.get(
                    "sldNum", (round(design.colors.lt1 and 688.0, 2), 491.6, 224.0, 37.5)
                )
                unoverridden.append(
                    _create_footer_placeholder(
                        "sldNum", box, design, slide_idx=slide_idx, presentation=presentation
                    )
                )

            # ftr
            show_ftr = bool(hf and getattr(hf, "ftr", False) and getattr(hf, "ftr_text", ""))
            if show_ftr and "ftr" not in existing_types:
                box = design.placeholder_frames.get("ftr", (328.0, 491.6, 304.0, 37.5))
                unoverridden.append(
                    _create_footer_placeholder(
                        "ftr",
                        box,
                        design,
                        slide_idx=slide_idx,
                        presentation=presentation,
                        text=hf.ftr_text if hf else "",
                    )
                )

            # dt
            show_dt = bool(hf and getattr(hf, "dt", False))
            if show_dt and "dt" not in existing_types:
                box = design.placeholder_frames.get("dt", (48.0, 491.6, 224.0, 37.5))
                is_auto = bool(hf and getattr(hf, "dt_auto", True))
                fmt = getattr(hf, "dt_fmt", "datetime1") if hf else "datetime1"
                dt_txt = getattr(hf, "dt_text", "") if hf else ""
                unoverridden.append(
                    _create_footer_placeholder(
                        "dt",
                        box,
                        design,
                        slide_idx=slide_idx,
                        presentation=presentation,
                        text=dt_txt,
                        is_auto=is_auto,
                        fmt=fmt,
                    )
                )

    return unoverridden


class PlaceholderResolver:
    """Helper service class for resolving cascading placeholders."""

    @staticmethod
    def evaluate_field_text(
        run: TextRun,
        slide_index: int = 0,
        presentation: Presentation | None = None,
    ) -> str:
        return evaluate_field_text(run, slide_index, presentation)

    @staticmethod
    def apply_cascading_placeholder_styles(
        shape: Shape,
        design: DesignTemplate,
    ) -> None:
        apply_cascading_placeholder_styles(shape, design)

    @staticmethod
    def resolve_unoverridden_placeholders(
        slide: Slide,
        presentation: Presentation | None = None,
    ) -> list[Shape]:
        return resolve_unoverridden_placeholders(slide, presentation)
