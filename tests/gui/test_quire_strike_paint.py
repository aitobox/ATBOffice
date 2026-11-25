"""Paint regressions for strikethrough on the Quire editing canvas (issue #411)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFontMetricsF, QImage, QPainter
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.io import read_docx
from atboffice.modules.writer.layout.pagination import paginate_document
from atboffice.modules.writer.layout.portions import LayoutLine, Portion, PortionType
from atboffice.modules.writer.models.document import Document
from atboffice.modules.writer.views.canvas_view import WriterCanvasView

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "word"
    / "docx"
    / "libreoffice__tdf154751_dualStrikethrough.docx"
)
CANVAS_W, CANVAS_H = 700, 120
START_X_PT = 10.0


def _portion(text: str, kind: PortionType = PortionType.TEXT, **flags: bool) -> Portion:
    return Portion(
        type=kind,
        text=text,
        width=18.0 * len(text),
        ascent=28.0,
        descent=8.0,
        font_size=36.0,
        font_family="Arial",
        **flags,
    )


def _line(portions: list[Portion], **attrs: object) -> LayoutLine:
    line = LayoutLine(portions=portions, top=0.0, baseline=40.0, height=50.0, width=500.0)
    for name, value in attrs.items():
        setattr(line, name, value)
    return line


def _render(view: WriterCanvasView, line: LayoutLine) -> QImage:
    image = QImage(CANVAS_W, CANVAS_H, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    try:
        view._paint_line_portions(
            painter,
            QRectF(0, 0, CANVAS_W, CANVAS_H),
            line,
            START_X_PT,
            0.0,
            check_spell=False,
        )
    finally:
        painter.end()
    return image


def _diff_pixels(a: QImage, b: QImage) -> list[tuple[int, int]]:
    return [
        (x, y) for y in range(CANVAS_H) for x in range(CANVAS_W) if a.pixel(x, y) != b.pixel(x, y)
    ]


def _bands(pixels: list[tuple[int, int]]) -> int:
    """Count separate horizontal stroke bands among changed pixels."""
    rows = sorted({y for _, y in pixels})
    return sum(1 for i, y in enumerate(rows) if i == 0 or y != rows[i - 1] + 1)


@pytest.fixture
def view(qapp: QApplication) -> WriterCanvasView:
    return WriterCanvasView(doc=Document())


@pytest.mark.parametrize(
    ("flags", "expected_bands"),
    [
        ({"strikethrough": True}, 1),
        ({"dstrike": True}, 2),
        ({"strikethrough": True, "dstrike": True}, 2),
        ({"strikethrough": False, "dstrike": False}, 0),
    ],
)
def test_strike_kinds_paint_distinct_stroke_counts(
    view: WriterCanvasView, flags: dict[str, bool], expected_bands: int
) -> None:
    plain = _render(view, _line([_portion("Asdasdads")]))
    struck = _render(view, _line([_portion("Asdasdads", **flags)]))

    assert _bands(_diff_pixels(plain, struck)) == expected_bands


def test_strike_spans_complete_word(view: WriterCanvasView) -> None:
    plain = _render(view, _line([_portion("Asdasdads")]))
    struck = _render(view, _line([_portion("Asdasdads", strikethrough=True)]))
    font, _ = view._build_portion_font(_portion("Asdasdads"))
    advance = QFontMetricsF(font).horizontalAdvance("Asdasdads")
    xs = [x for x, _ in _diff_pixels(plain, struck)]
    left = view.pt_to_px(START_X_PT)

    assert min(xs) <= left + 3
    assert max(xs) >= left + advance - 3


def test_strike_is_continuous_across_interior_blank(view: WriterCanvasView) -> None:
    flags = {"strikethrough": True}
    words = [
        _portion("Ab", **flags),
        _portion("  ", PortionType.BLANK, **flags),
        _portion("Cd", **flags),
    ]
    plain = _render(
        view,
        _line([_portion("Ab"), _portion("  ", PortionType.BLANK), _portion("Cd")]),
    )
    struck = _render(view, _line(words))
    pixels = _diff_pixels(plain, struck)
    row = max({y for _, y in pixels}, key=lambda y: sum(1 for _, r in pixels if r == y))
    xs = sorted(x for x, y in pixels if y == row)
    font, _ = view._build_portion_font(words[0])
    fm = QFontMetricsF(font)
    gap_left = view.pt_to_px(START_X_PT) + fm.horizontalAdvance("Ab")
    gap_right = gap_left + fm.horizontalAdvance("  ")

    gap_xs = [x for x in xs if gap_left + 1 <= x <= gap_right - 1]
    assert len(gap_xs) >= int(gap_right - gap_left) - 3


def test_strike_skips_trailing_blank(view: WriterCanvasView) -> None:
    flags = {"strikethrough": True}
    plain = _render(view, _line([_portion("Ab", **flags)]))
    trailing = _render(
        view,
        _line([_portion("Ab", **flags), _portion("   ", PortionType.BLANK, **flags)]),
    )

    assert _diff_pixels(plain, trailing) == []


def test_strike_paints_on_justified_line(view: WriterCanvasView) -> None:
    flags = {"strikethrough": True}

    def words(**word_flags: bool) -> list[Portion]:
        return [
            _portion("Ab", **word_flags),
            _portion(" ", PortionType.BLANK, **word_flags),
            _portion("Cd", **word_flags),
        ]

    plain = _render(view, _line(words(), extra_space_per_blank=12.0))
    struck = _render(view, _line(words(**flags), extra_space_per_blank=12.0))

    assert _bands(_diff_pixels(plain, struck)) == 1


def test_strike_paints_on_rtl_line(view: WriterCanvasView) -> None:
    plain = _render(view, _line([_portion("שלום")], is_rtl=True))
    struck = _render(view, _line([_portion("שלום", strikethrough=True)], is_rtl=True))

    assert _bands(_diff_pixels(plain, struck)) == 1


def test_fixture_run_imports_as_single_strike_and_paints_once(
    view: WriterCanvasView,
) -> None:
    doc = read_docx(FIXTURE.read_bytes())
    pagination = paginate_document(doc)
    line = pagination.pages[0].regions[0].columns[0].fragments[0].lines[0]
    word = next(po for po in line.portions if po.type == PortionType.TEXT)

    assert word.text == "Asdasdads"
    assert word.strikethrough is True
    assert word.dstrike is False

    plain_po = _portion("Asdasdads")
    plain_po.font_family, plain_po.font_size = word.font_family, word.font_size
    plain_line = _line([plain_po], top=line.top, baseline=line.baseline)
    plain = _render(view, plain_line)
    struck = _render(view, line)

    assert _bands(_diff_pixels(plain, struck)) == 1
