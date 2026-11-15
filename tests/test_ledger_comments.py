"""Tests for Ledger comment callouts: color, author de-duplication, indicator, flipping."""

from __future__ import annotations

from PySide6.QtGui import QColor, QImage, QPainter, QPalette
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.io.xlsx_reader import _strip_author_prefix, read_xlsx
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport

FIXTURE = "tests/docs/excel/xlsx/poi__SimpleWithComments.xlsx"


class _RecordingPainter(QPainter):
    """QPainter that records every string passed to drawText."""

    def __init__(self, device) -> None:
        super().__init__(device)
        self.texts: list[str] = []

    def drawText(self, *args):  # noqa: N802 - Qt naming
        for a in args:
            if isinstance(a, str):
                self.texts.append(a)
        return super().drawText(*args)


def _render(viewport: GridViewport, painter_cls=QPainter) -> tuple[QImage, QPainter]:
    img = QImage(viewport.viewport().size(), QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    painter = painter_cls(img)
    try:
        viewport._render_paint_event(painter, None)
    finally:
        if painter.isActive():
            painter.end()
    return img, painter


def _viewport(sheet: SheetDataModel, qtbot, w: int = 600, h: int = 300) -> GridViewport:
    vp = GridViewport(model=sheet)
    vp.resize(w, h)
    qtbot.addWidget(vp)
    return vp


def _close(c: QColor, ref: QColor, tol: int = 10) -> bool:
    return (
        abs(c.red() - ref.red()) <= tol
        and abs(c.green() - ref.green()) <= tol
        and abs(c.blue() - ref.blue()) <= tol
    )


# ---------------------------------------------------------------- reader


def test_reader_strips_stored_author_prefix():
    wb = read_xlsx(FIXTURE)
    cm = wb.sheets[0].get_comment(2, 1)  # B3
    assert cm is not None
    assert cm.author == "Yegor Kozlov"
    assert cm.text == "third cell"


def test_strip_author_prefix_edge_cases():
    assert _strip_author_prefix("Ann:\nbody", "Ann") == "body"
    assert _strip_author_prefix("Ann:\r\nbody", "Ann") == "body"
    assert _strip_author_prefix("Ann: body", "Ann") == "body"
    # No prefix -> unchanged
    assert _strip_author_prefix("plain note", "Ann") == "plain note"
    # Author name not followed by a colon is real content
    assert _strip_author_prefix("Annabel said hi", "Ann") == "Annabel said hi"
    # Empty author -> unchanged
    assert _strip_author_prefix(":\nx", "") == ":\nx"
    # Body made only of the prefix -> empty body
    assert _strip_author_prefix("Ann:", "Ann") == ""


# ---------------------------------------------------------------- painter


def _commented_sheet(r: int = 2, c: int = 1) -> SheetDataModel:
    sheet = SheetDataModel("Comments")
    sheet.set_cell(r, c, CellData(value="three"))
    sheet.set_comment(r, c, "third cell", author="Yegor Kozlov", visible=True)
    return sheet


def _callout_center_color(vp: GridViewport, img: QImage, r: int, c: int) -> QColor:
    rect = vp._comment_callout_rect(r, c, vp.model.get_comment(r, c))
    assert rect is not None
    # Sample bottom-right area of the box where no text is laid out
    return img.pixelColor(rect.right() - 6, rect.bottom() - 6)


def test_callout_is_pale_yellow_in_light_and_dark_palettes(qtbot):
    app = QApplication.instance()
    original = app.palette()
    try:
        for window, text in ((QColor("#FFFFFF"), QColor("#000000")),
                             (QColor("#202020"), QColor("#F0F0F0"))):
            pal = QPalette(original)
            pal.setColor(QPalette.ColorRole.Window, window)
            pal.setColor(QPalette.ColorRole.Base, window)
            pal.setColor(QPalette.ColorRole.ToolTipBase, window)
            pal.setColor(QPalette.ColorRole.WindowText, text)
            pal.setColor(QPalette.ColorRole.Text, text)
            app.setPalette(pal)
            vp = _viewport(_commented_sheet(), qtbot)
            img, _ = _render(vp)
            assert _close(_callout_center_color(vp, img, 2, 1), QColor("#FFFFE1"))
    finally:
        app.setPalette(original)


def test_callout_text_is_black(qtbot):
    vp = _viewport(_commented_sheet(), qtbot)
    img, _ = _render(vp)
    rect = vp._comment_callout_rect(2, 1, vp.model.get_comment(2, 1))
    darkest = min(
        (img.pixelColor(x, y) for y in range(rect.top() + 2, rect.top() + 30)
         for x in range(rect.left() + 4, rect.right() - 4)),
        key=lambda c: c.red() + c.green() + c.blue(),
    )
    assert darkest.red() < 60 and darkest.green() < 60 and darkest.blue() < 60


def test_author_laid_out_exactly_once_for_fixture(qtbot):
    wb = read_xlsx(FIXTURE)
    sheet = wb.sheets[0]
    sheet.get_comment(2, 1).visible = True
    vp = _viewport(sheet, qtbot)
    _, painter = _render(vp, _RecordingPainter)
    joined = "\n".join(painter.texts)
    assert joined.count("Yegor Kozlov:") == 1
    assert "third cell" in joined


def test_red_triangle_indicator_in_top_right_corner(qtbot):
    sheet = _commented_sheet()
    sheet.get_comment(2, 1).visible = False
    vp = _viewport(sheet, qtbot)
    img, _ = _render(vp)
    cell = vp.cell_rect(2, 1)
    px = img.pixelColor(cell.left() + cell.width() - 2, cell.top() + 1)
    assert px.red() > 200 and px.green() < 60 and px.blue() < 60


def test_callout_flips_left_at_right_edge(qtbot):
    sheet = SheetDataModel("Edge")
    sheet.set_comment(1, 4, "near the edge", author="A", visible=True)
    vp = _viewport(sheet, qtbot, w=500, h=300)
    # Size columns so E (col 4) ends ~40px before the viewport's right edge
    col_w = (vp.viewport().width() - vp.row_header_width - 40) // 5
    for c in range(6):
        sheet.geometry.set_col_width(c, col_w)
    cell = vp.cell_rect(1, 4)
    rect = vp._comment_callout_rect(1, 4, sheet.get_comment(1, 4))
    assert rect.right() <= vp.viewport().width()
    assert rect.right() < cell.left()


def test_callout_stays_inside_bottom_edge(qtbot):
    sheet = SheetDataModel("Bottom")
    sheet.set_comment(8, 1, "near the bottom", author="A", visible=True)
    vp = _viewport(sheet, qtbot, w=500, h=200)
    rect = vp._comment_callout_rect(8, 1, sheet.get_comment(8, 1))
    assert rect is not None
    assert rect.bottom() <= vp.viewport().height()


def test_hover_does_not_show_system_tooltip_for_comment(qtbot, monkeypatch):
    from atboffice.modules.spreadsheet.views import grid_viewport as gv

    shown: list[str] = []
    monkeypatch.setattr(gv.QToolTip, "showText", lambda *a, **k: shown.append(a[1]))
    vp = _viewport(_commented_sheet(), qtbot)
    vp.show()
    cell = vp.cell_rect(2, 1)
    from PySide6.QtCore import QPoint
    qtbot.mouseMove(vp.viewport(), QPoint(cell.center().x(), cell.center().y()))
    assert not any("third cell" in s for s in shown)
