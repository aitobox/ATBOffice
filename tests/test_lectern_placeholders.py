"""Prompt text for empty placeholders in the Lectern edit view (issue #369)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage, QPainter

from atboffice.core.i18n import safe_tr
from atboffice.modules.presentation.io.pptx_reader import read_pptx
from atboffice.modules.presentation.models.layouts import PROMPTS
from atboffice.modules.presentation.models.placeholder_resolver import (
    resolve_unoverridden_placeholders,
)
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.views.shape_item import (
    ShapeGraphicsItem,
    build_prompt_body,
)
from atboffice.modules.presentation.views.slide_canvas import SlideScene

ROOT = Path(__file__).resolve().parent.parent
PPTX_DIR = ROOT / "tests" / "docs" / "powerpoint" / "pptx"
LOCALE_DIR = ROOT / "src" / "atboffice" / "resources" / "locale"


def _fixture(name: str) -> Path:
    path = PPTX_DIR / name
    if not path.exists():
        pytest.skip(f"fixture missing: {name}")
    return path


def _ph_shape(slide: Slide, ph_type: str, idx: int | None = None):
    for sh in slide.shapes:
        ph = sh.placeholder
        if ph and ph.type == ph_type and (idx is None or ph.idx == idx):
            return sh
    raise AssertionError(f"no {ph_type} placeholder on slide")


def _prompt_item(scene: SlideScene, ph_type: str) -> ShapeGraphicsItem:
    for item in scene.items():
        if isinstance(item, ShapeGraphicsItem):
            ph = item.model.placeholder
            if ph and ph.type == ph_type:
                return item
    raise AssertionError(f"no {ph_type} item in scene")


def _render_item(item: ShapeGraphicsItem) -> QImage:
    w, h = int(item.model.w) + 2, int(item.model.h) + 2
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    painter = QPainter(img)
    item.paint(painter, None, None)
    painter.end()
    return img


def _non_white_pixels(img: QImage) -> int:
    count = 0
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            if img.pixelColor(x, y).lightness() < 240:
                count += 1
    return count


def test_ctr_title_prompt_uses_inherited_red(qapp) -> None:
    pres = read_pptx(_fixture("libreoffice__tdf103876.pptx"))
    sh = _ph_shape(pres.slides[0], "ctrTitle")
    assert sh.text.is_empty()

    body = build_prompt_body(sh.text, "ctrTitle")
    assert body is not None
    assert body.plain_text == safe_tr("Click to add title")
    run = body.paragraphs[0].runs[0]
    assert run.size and run.size > 20
    color = QColor(run.color) if run.color and run.color.startswith("#") else None
    assert color is not None and color.red() > 150 and color.green() < 100


def test_subtitle_prompt_keeps_bullet(qapp) -> None:
    pres = read_pptx(_fixture("libreoffice__tdf143129.pptx"))
    sh = _ph_shape(pres.slides[0], "subTitle")
    body = build_prompt_body(sh.text, "subTitle")
    assert body is not None
    assert body.plain_text == safe_tr("Click to add subtitle")
    assert body.paragraphs[0].props.get("bu", {}).get("t") == "char"


def test_custom_layout_prompt_text_wins(qapp) -> None:
    pres = read_pptx(_fixture("libreoffice__master-slides.pptx"))
    sh = _ph_shape(pres.slides[0], "body", 14)
    assert sh.text.is_empty()
    body = build_prompt_body(sh.text, "body")
    assert body is not None
    assert body.plain_text == "00 MONTH 2022"


def test_footer_placeholders_have_no_prompt() -> None:
    from atboffice.modules.presentation.models.text import TextBody

    for ph_type in ("dt", "ftr", "sldNum"):
        assert build_prompt_body(TextBody.create_empty(), ph_type) is None


def test_unknown_placeholder_type_falls_back_to_text_prompt() -> None:
    from atboffice.modules.presentation.models.text import TextBody

    body = build_prompt_body(TextBody.create_empty(), "media")
    assert body is not None and body.plain_text == safe_tr("Click to add text")


def test_non_empty_text_has_no_prompt() -> None:
    from atboffice.modules.presentation.models.text import TextBody

    assert build_prompt_body(TextBody.from_plain_text("Hello"), "title") is None


def test_prompt_run_not_serialized() -> None:
    pres = read_pptx(_fixture("libreoffice__tdf103876.pptx"))
    sh = _ph_shape(pres.slides[0], "ctrTitle")
    assert sh.text.prompt_run is not None
    d = sh.text.to_dict()
    assert "prompt_run" not in json.dumps(d)


def test_prompt_drawn_in_edit_scene_only(qapp) -> None:
    pres = read_pptx(_fixture("libreoffice__tdf103876.pptx"))
    slide = pres.slides[0]

    edit_scene = SlideScene(slide=slide, presentation=pres)
    edit_img = _render_item(_prompt_item(edit_scene, "ctrTitle"))
    assert _non_white_pixels(edit_img) > 50

    print_scene = SlideScene(slide=slide, presentation=pres)
    print_scene.show_placeholder_prompts = False
    print_img = _render_item(_prompt_item(print_scene, "ctrTitle"))
    assert _non_white_pixels(print_img) == 0


def test_prompt_hidden_while_editing(qapp) -> None:
    pres = read_pptx(_fixture("libreoffice__tdf103876.pptx"))
    scene = SlideScene(slide=pres.slides[0], presentation=pres)
    item = _prompt_item(scene, "ctrTitle")
    item.is_editing_text = True
    # Only the dashed outline remains: far fewer inked pixels than with the prompt.
    editing = _non_white_pixels(_render_item(item))
    item.is_editing_text = False
    idle = _non_white_pixels(_render_item(item))
    assert editing < idle


def test_synthesized_placeholders_do_not_bake_prompt_text() -> None:
    pres = Presentation()
    slide = Slide(id="s1", layout="title")
    pres.slides.append(slide)
    shapes = resolve_unoverridden_placeholders(slide, pres)
    titled = [s for s in shapes if s.placeholder and s.placeholder.type in PROMPTS]
    assert titled, "layout should synthesize placeholders"
    for sh in titled:
        if sh.placeholder.type in ("dt", "ftr", "sldNum"):
            continue
        assert sh.text is None or sh.text.is_empty()
        if sh.text is not None:
            assert build_prompt_body(sh.text, sh.placeholder.type) is not None


@pytest.mark.parametrize(
    "key",
    [
        "Click to add title",
        "Click to add subtitle",
        "Click to add text",
        "Double click to add table",
        "Double click to add chart",
        "Click icon to add picture",
    ],
)
def test_prompt_strings_translated_in_every_locale(key: str) -> None:
    for path in sorted(LOCALE_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert key in data, f"{path.name} lacks {key!r}"
        if path.stem == "en":
            continue
        assert data[key] != key, f"{path.name} leaves {key!r} untranslated"
