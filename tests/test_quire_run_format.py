"""
tests/test_quire_run_format.py

Unit tests for Issue #366: fix(quire) run formatting bugs:
1. Strikethrough never drawn
2. Header/footer text always underlined
3. w:caps / w:smallCaps never applied
4. Footnote marks show wrong number
"""

from atboffice.modules.writer.layout.portions import (
    Portion,
    PortionType,
    decompose_paragraph_to_portions,
)
from atboffice.modules.writer.models.document import (
    NoteRefItem,
    Paragraph,
    TextItem,
)
from atboffice.modules.writer.models.properties import RunProperties


def _make_simple_para(text: str, r_pr: RunProperties | None = None) -> Paragraph:
    """Helper: construct a Paragraph with one TextItem run."""
    p = Paragraph()
    item = TextItem(text=text, r_pr=r_pr or RunProperties())
    p.runs = [item]
    return p


def _decompose(text: str, r_pr: RunProperties) -> list[Portion]:
    """Decompose a simple single-run paragraph into portions."""
    p = _make_simple_para(text, r_pr)
    return decompose_paragraph_to_portions(p)


# ---------------------------------------------------------------------------
# Bug 1: Strikethrough
# ---------------------------------------------------------------------------


def test_strikethrough_portion_field():
    """Portions from a run with strike=True must have strikethrough=True."""
    r_pr = RunProperties()
    r_pr.strike = True
    portions = _decompose("hello", r_pr)
    text_portions = [po for po in portions if po.type == PortionType.TEXT]
    assert text_portions, "Expected at least one TEXT portion"
    for po in text_portions:
        val = getattr(po, "strikethrough", "ATTR_MISSING")
        assert getattr(po, "strikethrough", False) is True, (
            f"Expected strikethrough=True on portion '{po.text}', got {val}"
        )


def test_no_strikethrough_when_strike_false():
    """Portions from a run with strike=False must NOT have strikethrough=True."""
    r_pr = RunProperties()
    r_pr.strike = False
    portions = _decompose("world", r_pr)
    text_portions = [po for po in portions if po.type == PortionType.TEXT]
    for po in text_portions:
        assert not getattr(po, "strikethrough", False), (
            f"Expected strikethrough=False on portion '{po.text}'"
        )


def test_dstrike_portion_field():
    """Portions from a run with dstrike=True must have dstrike=True."""
    r_pr = RunProperties()
    r_pr.dstrike = True
    portions = _decompose("double", r_pr)
    text_portions = [po for po in portions if po.type == PortionType.TEXT]
    assert text_portions, "Expected at least one TEXT portion"
    for po in text_portions:
        assert getattr(po, "dstrike", False) is True, (
            f"Expected dstrike=True on portion '{po.text}'"
        )


# ---------------------------------------------------------------------------
# Bug 2: Underline always-on
# ---------------------------------------------------------------------------


def test_underline_none_when_no_underline():
    """Portions from a run with u='none' must have underline=None (not truthy 'none')."""
    r_pr = RunProperties()
    r_pr.u = "none"
    portions = _decompose("Header.", r_pr)
    text_portions = [po for po in portions if po.type == PortionType.TEXT]
    assert text_portions, "Expected at least one TEXT portion"
    for po in text_portions:
        ul = getattr(po, "underline", "NOT_SET")
        assert ul is None, (
            f"Expected underline=None on portion '{po.text}', got {ul!r}. "
            "String 'none' is truthy and causes incorrect underline drawing."
        )


def test_underline_set_when_single():
    """Portions from a run with u='single' must have underline='single'."""
    r_pr = RunProperties()
    r_pr.u = "single"
    portions = _decompose("link", r_pr)
    text_portions = [po for po in portions if po.type == PortionType.TEXT]
    assert text_portions, "Expected at least one TEXT portion"
    for po in text_portions:
        ul = getattr(po, "underline", None)
        assert ul == "single", (
            f"Expected underline='single' on portion '{po.text}', got {ul!r}"
        )


def test_underline_none_when_default():
    """Portions from a run with no explicit underline must have underline=None."""
    r_pr = RunProperties()
    # r_pr.u defaults to "none" in RunProperties
    portions = _decompose("plain text", r_pr)
    text_portions = [po for po in portions if po.type == PortionType.TEXT]
    for po in text_portions:
        ul = getattr(po, "underline", "NOT_SET")
        assert ul is None, (
            f"Expected underline=None on portion '{po.text}', got {ul!r}"
        )


# ---------------------------------------------------------------------------
# Bug 3: Caps / SmallCaps
# ---------------------------------------------------------------------------


def test_caps_uppercase_display_text():
    """Portions from a run with caps=True must have uppercase text."""
    r_pr = RunProperties()
    r_pr.caps = True
    portions = _decompose("objective", r_pr)
    text_portions = [po for po in portions if po.type == PortionType.TEXT and po.text.strip()]
    assert text_portions, "Expected at least one TEXT portion"
    for po in text_portions:
        assert po.text == po.text.upper(), (
            f"Expected uppercase text '{po.text.upper()}', got '{po.text}'"
        )


def test_small_caps_uppercase_and_reduced_font():
    """Portions from a run with small_caps=True must have uppercase text and reduced font size."""
    r_pr = RunProperties()
    r_pr.sz = 12.0
    r_pr.small_caps = True
    portions = _decompose("smallcaps", r_pr)
    text_portions = [po for po in portions if po.type == PortionType.TEXT and po.text.strip()]
    assert text_portions, "Expected at least one TEXT portion"
    for po in text_portions:
        assert po.text == po.text.upper(), (
            f"Expected uppercase text '{po.text.upper()}', got '{po.text}'"
        )
        assert po.font_size < 12.0, (
            f"Expected reduced font size for small_caps, got {po.font_size}"
        )


def test_no_caps_when_caps_false():
    """Portions from a run with caps=False must NOT have their text uppercased."""
    r_pr = RunProperties()
    r_pr.caps = False
    portions = _decompose("Mixed Case", r_pr)
    text_portions = [po for po in portions if po.type == PortionType.TEXT and po.text.strip()]
    # At least one portion should preserve mixed case
    any_mixed = any(po.text != po.text.upper() for po in text_portions)
    assert any_mixed, "Expected at least one portion to retain mixed-case text"


# ---------------------------------------------------------------------------
# Bug 4: Footnote marks show wrong number
# ---------------------------------------------------------------------------


def test_footnote_ref_nonzero_note_id():
    """NoteRefItem with note_id='1' should produce portion text '1', not '0'."""
    p = Paragraph()
    item = NoteRefItem(kind="fn", note_id="1", custom_mark="")
    p.runs = [item]
    portions = decompose_paragraph_to_portions(p)
    text_portions = [po for po in portions if po.type == PortionType.TEXT]
    assert text_portions, "Expected TEXT portion for footnote reference"
    ref_text = text_portions[0].text
    assert ref_text == "1", (
        f"Expected footnote mark '1', got '{ref_text}'"
    )


def test_footnote_ref_zero_note_id_uses_counter():
    """NoteRefItem with note_id='0' should NOT show '0' — should show a valid marker."""
    p = Paragraph()
    item = NoteRefItem(kind="fn", note_id="0", custom_mark="")
    p.runs = [item]
    portions = decompose_paragraph_to_portions(p)
    text_portions = [po for po in portions if po.type == PortionType.TEXT]
    assert text_portions, "Expected TEXT portion for footnote reference"
    ref_text = text_portions[0].text
    assert ref_text != "0", (
        f"Footnote mark should NOT be '0', got '{ref_text}'"
    )
    assert ref_text, "Footnote mark should not be empty"


def test_footnote_ref_custom_mark():
    """NoteRefItem with custom_mark should use the custom mark."""
    p = Paragraph()
    item = NoteRefItem(kind="fn", note_id="1", custom_mark="†")
    p.runs = [item]
    portions = decompose_paragraph_to_portions(p)
    text_portions = [po for po in portions if po.type == PortionType.TEXT]
    assert text_portions, "Expected TEXT portion for footnote reference"
    ref_text = text_portions[0].text
    assert ref_text == "†", (
        f"Expected custom mark '†', got '{ref_text}'"
    )
