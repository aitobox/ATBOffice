"""Paint regressions for body underlines on the Quire editing canvas."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.io import read_docx
from atboffice.modules.writer.layout.pagination import paginate_document
from atboffice.modules.writer.layout.portions import LayoutLine, Portion, PortionType
from atboffice.modules.writer.models.document import Document
from atboffice.modules.writer.views.canvas_view import WriterCanvasView

FIXTURE = (
    Path(__file__).resolve().parents[1] / "docs" / "word" / "docx" / "libreoffice__tdf125881.docx"
)
CANVAS_W, CANVAS_H = 700, 120
START_X_PT = 10.0


def _portion(
    text: str,
    kind: PortionType = PortionType.TEXT,
    underline: str | None = None,
    color: str | None = None,
) -> Portion:
    return Portion(
        type=kind,
        text=text,
        width=18.0 * len(text),
        ascent=28.0,
        descent=8.0,
        font_size=36.0,
        font_family="Arial",
        underline=underline,
        color=color,
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


def _diff(
    view: WriterCanvasView, style: str | None, text: str = "Aaaaaaaa"
) -> set[tuple[int, int]]:
    plain = _render(view, _line([_portion(text)]))
    marked = _render(view, _line([_portion(text, underline=style)]))
    return {
        (x, y)
        for y in range(CANVAS_H)
        for x in range(CANVAS_W)
        if plain.pixel(x, y) != marked.pixel(x, y)
    }


def _bands(pixels: set[tuple[int, int]]) -> int:
    rows = sorted({y for _, y in pixels})
    return sum(1 for i, y in enumerate(rows) if i == 0 or y != rows[i - 1] + 1)


def _segments(pixels: set[tuple[int, int]]) -> int:
    """Count separate horizontal segments across all changed columns."""
    columns = sorted({x for x, _ in pixels})
    return sum(1 for i, x in enumerate(columns) if i == 0 or x != columns[i - 1] + 1)


@pytest.fixture
def view(qapp: QApplication) -> WriterCanvasView:
    return WriterCanvasView(doc=Document())


@pytest.mark.parametrize(("style", "bands"), [("single", 1), ("double", 2), ("thick", 1)])
def test_solid_underlines_paint_expected_stroke_count(
    view: WriterCanvasView, style: str, bands: int
) -> None:
    assert _bands(_diff(view, style)) == bands


@pytest.mark.parametrize("style", [None, "none"])
def test_no_underline_paints_nothing(view: WriterCanvasView, style: str | None) -> None:
    assert _diff(view, style) == set()


def test_underline_sits_below_baseline_and_spans_word(view: WriterCanvasView) -> None:
    pixels = _diff(view, "single")
    font, _ = view._build_portion_font(_portion("Aaaaaaaa"))
    advance = QFontMetricsF(font).horizontalAdvance("Aaaaaaaa")
    left = view.pt_to_px(START_X_PT)
    baseline = view.pt_to_px(40.0)

    assert min(y for _, y in pixels) > baseline
    assert min(x for x, _ in pixels) <= left + 2
    assert max(x for x, _ in pixels) >= left + advance - 2


def test_thick_underline_is_heavier_than_single(view: WriterCanvasView) -> None:
    single_rows = {y for _, y in _diff(view, "single")}
    thick_rows = {y for _, y in _diff(view, "thick")}

    assert len(thick_rows) > len(single_rows)


@pytest.mark.parametrize("style", ["dotted", "dash", "dashed", "dotDash", "dotDotDash"])
def test_broken_underlines_have_gaps(view: WriterCanvasView, style: str) -> None:
    assert _segments(_diff(view, style)) > 3


def test_dotted_breaks_more_often_than_dashed(view: WriterCanvasView) -> None:
    assert _segments(_diff(view, "dotted")) > _segments(_diff(view, "dashed"))


def test_wave_underline_varies_vertically(view: WriterCanvasView) -> None:
    wave_rows = {y for _, y in _diff(view, "wave")}
    single_rows = {y for _, y in _diff(view, "single")}

    assert len(wave_rows) > len(single_rows)


def test_unknown_style_falls_back_to_single(view: WriterCanvasView) -> None:
    assert _diff(view, "futureStyle") == _diff(view, "single")


def test_underline_uses_text_color(view: WriterCanvasView) -> None:
    image = _render(view, _line([_portion("Aaaa", underline="single", color="#FF0000")]))
    colors = {
        QColor(image.pixel(x, y)).name()
        for y in range(int(view.pt_to_px(40.0)) + 1, CANVAS_H)
        for x in range(CANVAS_W)
    }

    assert "#ff0000" in colors
    assert "#000000" not in colors


def _word_line(style: str | None, **attrs: object) -> LayoutLine:
    return _line(
        [
            _portion("Ab", underline=style),
            _portion("    ", PortionType.BLANK, underline=style),
            _portion("Cd", underline=style),
        ],
        **attrs,
    )


def _gap_is_marked(view: WriterCanvasView, style: str) -> bool:
    plain = _render(view, _word_line(None))
    marked = _render(view, _word_line(style))
    font, _ = view._build_portion_font(_portion("Ab"))
    fm = QFontMetricsF(font)
    middle = view.pt_to_px(START_X_PT) + fm.horizontalAdvance("Ab") + fm.horizontalAdvance("  ")
    return any(plain.pixel(int(middle), y) != marked.pixel(int(middle), y) for y in range(CANVAS_H))


def test_single_underline_continues_across_interior_blank(view: WriterCanvasView) -> None:
    assert _gap_is_marked(view, "single")


def test_words_underline_skips_interior_blank(view: WriterCanvasView) -> None:
    assert not _gap_is_marked(view, "words")
    assert _bands(_diff(view, "words")) == 1


def test_underline_skips_trailing_blank(view: WriterCanvasView) -> None:
    without = _render(view, _line([_portion("Ab", underline="single")]))
    trailing = _render(
        view,
        _line(
            [
                _portion("Ab", underline="single"),
                _portion("   ", PortionType.BLANK, underline="single"),
            ]
        ),
    )

    assert without == trailing


def test_underline_paints_on_justified_line(view: WriterCanvasView) -> None:
    plain = _render(view, _word_line(None, extra_space_per_blank=12.0))
    marked = _render(view, _word_line("single", extra_space_per_blank=12.0))

    assert plain != marked


def test_underline_paints_on_rtl_line(view: WriterCanvasView) -> None:
    plain = _render(view, _line([_portion("שלום")], is_rtl=True))
    marked = _render(view, _line([_portion("שלום", underline="single")], is_rtl=True))

    assert plain != marked


def test_imported_underlined_run_paints(view: WriterCanvasView) -> None:
    doc = read_docx(FIXTURE.read_bytes())
    pagination = paginate_document(doc)
    lines = [
        line
        for page in pagination.pages
        for region in page.regions
        for column in region.columns
        for fragment in column.fragments
        for line in fragment.lines
    ]
    line = next(
        ln for ln in lines if any(po.underline and po.text.strip() for po in ln.portions)
    )
    plain_portions = [
        Portion(**{**po.__dict__, "underline": None}) for po in line.portions
    ]
    plain = _line(plain_portions, top=line.top, baseline=line.baseline, jc=line.jc)
    plain.width = line.width

    assert _render(view, plain) != _render(view, line)
