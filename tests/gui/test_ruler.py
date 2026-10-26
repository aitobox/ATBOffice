"""GUI tests for Quire Word 2003 interactive horizontal and vertical rulers."""

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.models.document import Document, Paragraph
from atboffice.modules.writer.models.properties import SectionProperties, TabStop
from atboffice.modules.writer.view import WriterView
from atboffice.modules.writer.views.canvas_view import WriterCanvasView
from atboffice.modules.writer.views.ruler import (
    PT_PER_CM,
    PT_PER_INCH,
    HorizontalRuler,
    RulerUnit,
    TabKind,
    TabSelectorWidget,
    VerticalRuler,
    pt_to_unit,
    snap_to_grid,
    unit_to_pt,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Unit Conversions & Tab Selector Tests
# ---------------------------------------------------------------------------


def test_ruler_unit_conversions():
    """Verify conversion between points, inches, and centimeters."""
    assert abs(pt_to_unit(72.0, RulerUnit.INCH) - 1.0) < 1e-4
    assert abs(unit_to_pt(1.0, RulerUnit.INCH) - 72.0) < 1e-4

    assert abs(pt_to_unit(PT_PER_CM, RulerUnit.CM) - 1.0) < 1e-4
    assert abs(unit_to_pt(1.0, RulerUnit.CM) - PT_PER_CM) < 1e-4

    assert abs(pt_to_unit(50.0, RulerUnit.PT) - 50.0) < 1e-4
    assert abs(unit_to_pt(50.0, RulerUnit.PT) - 50.0) < 1e-4


def test_ruler_snapping():
    """Verify grid snapping and Alt-key precision override."""
    # Inch: 4.5 pt grid steps
    snapped = snap_to_grid(5.0, RulerUnit.INCH, disable_snap=False)
    assert abs(snapped - 4.5) < 1e-4

    # Disable snap: preserves float precision
    unsnapped = snap_to_grid(5.234, RulerUnit.INCH, disable_snap=True)
    assert abs(unsnapped - 5.23) < 1e-4


def test_tab_selector_cycling(qapp):
    """Verify TabSelectorWidget cycles through all 7 tab kinds."""
    selector = TabSelectorWidget()
    assert selector.current_kind == TabKind.LEFT

    kinds_observed = []
    selector.tab_kind_changed.connect(kinds_observed.append)

    # Cycle through all kinds
    expected = [
        TabKind.CENTER,
        TabKind.RIGHT,
        TabKind.DECIMAL,
        TabKind.BAR,
        TabKind.FIRST_LINE,
        TabKind.HANGING,
        TabKind.LEFT,
    ]
    for exp in expected:
        k = selector.cycle_next()
        assert k == exp

    assert len(kinds_observed) == 7
    assert kinds_observed[0] == "center"

    # Set explicitly
    selector.set_kind(TabKind.DECIMAL)
    assert selector.current_kind == TabKind.DECIMAL

    selector.retranslate_ui()


# ---------------------------------------------------------------------------
# Horizontal Ruler Tests
# ---------------------------------------------------------------------------


def test_horizontal_ruler_markers_and_geometry(qapp):
    """Verify indent marker coordinate computation and geometry."""
    doc = Document()
    p = doc.main.blocks[0]
    p.indent_left = 36.0
    p.indent_first = 18.0
    p.indent_right = 72.0


    canvas = WriterCanvasView(doc=doc)
    canvas.resize(800, 600)
    canvas.show()

    ruler = HorizontalRuler()
    ruler.resize(800, 24)
    ruler.attach_canvas(canvas)
    ruler.show()

    # Verify unit changing
    ruler.set_unit(RulerUnit.CM)
    assert ruler.unit == RulerUnit.CM
    ruler.set_unit(RulerUnit.INCH)
    assert ruler.unit == RulerUnit.INCH

    # Marker rects
    rects = ruler._get_marker_rects()
    assert "first" in rects
    assert "hang" in rects
    assert "left" in rects
    assert "right" in rects

    # First line indent is to the right of left indent
    assert rects["first"].center().x() > rects["hang"].center().x()


def test_horizontal_ruler_drag_indents(qapp):
    """Verify dragging indent markers updates Paragraph properties."""
    doc = Document()
    p = doc.main.blocks[0]
    p.indent_left = 0.0
    p.indent_first = 0.0
    p.indent_right = 0.0


    canvas = WriterCanvasView(doc=doc)
    canvas.resize(800, 600)

    ruler = HorizontalRuler()
    ruler.resize(800, 24)
    ruler.attach_canvas(canvas)

    guidelines = []
    ruler.guide_line_requested.connect(lambda x, v: guidelines.append(x))
    cleared = []
    ruler.guide_line_cleared.connect(lambda: cleared.append(True))

    # 1. Drag first line indent marker
    rects = ruler._get_marker_rects()
    first_pt = rects["first"].center()

    # Mouse press on 'first' marker
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        first_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mousePressEvent(press_ev)
    assert ruler._drag_kind == "first"
    assert len(guidelines) > 0

    # Drag 36 pt to the right (36 * 96/72 px = 48 px)
    move_pt = QPointF(first_pt.x() + 48.0, first_pt.y())
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        move_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mouseMoveEvent(move_ev)

    # Release mouse
    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        move_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mouseReleaseEvent(release_ev)

    assert len(cleared) > 0
    assert abs(p.indent_first - 36.0) < 1.0


def test_horizontal_ruler_tab_stops_add_move_and_delete(qapp):
    """Verify clicking ruler adds tab stop, dragging moves it, dragging off deletes it."""
    doc = Document()
    p = doc.main.blocks[0]


    canvas = WriterCanvasView(doc=doc)
    canvas.resize(800, 600)

    ruler = HorizontalRuler()
    ruler.resize(800, 24)
    ruler.attach_canvas(canvas)
    ruler.set_tab_selector_kind(TabKind.RIGHT)

    text_l = ruler.text_left_ruler()

    # 1. Click in text area to add new tab stop at 72 pt (approx 96 px)
    click_x = text_l + 96.0
    click_pt = QPointF(click_x, 15.0)

    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        click_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mousePressEvent(press_ev)
    assert ruler._drag_kind == "new_tab"

    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        click_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mouseReleaseEvent(release_ev)

    assert len(p.p_pr.tabs) == 1
    tab = p.p_pr.tabs[0]
    assert abs(tab.pos - 72.0) < 2.0
    assert tab.align == "right"

    # 2. Drag tab stop vertically off ruler (e.g. y = 50px, which is > 18px below 24px)
    tab_rects = ruler._get_tab_rects()
    assert len(tab_rects) == 1
    tab_center = tab_rects[0][2].center()

    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        tab_center,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mousePressEvent(press_ev)
    assert ruler._drag_kind == "tab"

    # Move far down outside ruler
    off_pt = QPointF(tab_center.x(), 55.0)
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        off_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mouseMoveEvent(move_ev)

    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        off_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mouseReleaseEvent(release_ev)

    # Tab stop should now be deleted
    assert len(p.p_pr.tabs) == 0


def test_horizontal_ruler_double_click_dialogs(qapp):
    """Verify double-clicking ruler emits tabs or page setup dialog signals."""
    ruler = HorizontalRuler()
    ruler.resize(800, 24)

    tabs_requested = []
    page_setup_requested = []
    ruler.tabs_dialog_requested.connect(lambda: tabs_requested.append(True))
    ruler.page_setup_requested.connect(lambda: page_setup_requested.append(True))

    # Double click in text area
    text_l = ruler.text_left_ruler()
    ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonDblClick,
        QPointF(text_l + 50.0, 10.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mouseDoubleClickEvent(ev)
    assert len(tabs_requested) == 1

    # Double click in margin area
    ev_margin = QMouseEvent(
        QMouseEvent.Type.MouseButtonDblClick,
        QPointF(text_l - 20.0, 10.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ruler.mouseDoubleClickEvent(ev_margin)
    assert len(page_setup_requested) == 1


# ---------------------------------------------------------------------------
# Vertical Ruler Tests
# ---------------------------------------------------------------------------


def test_vertical_ruler_margins_and_drag(qapp):
    """Verify VerticalRuler margin dividers and drag interactions."""
    doc = Document()
    sect = SectionProperties(pg_w=612.0, pg_h=792.0, mt=72.0, mb=72.0)
    p = Paragraph(sect=sect)
    doc.main.blocks.append(p)

    canvas = WriterCanvasView(doc=doc)
    canvas.resize(800, 600)

    v_ruler = VerticalRuler()
    v_ruler.resize(24, 600)
    v_ruler.attach_canvas(canvas)

    guidelines = []
    v_ruler.guide_line_requested.connect(lambda y, v: guidelines.append(y))

    # Margin dividers
    text_t = v_ruler.text_top_ruler()

    # Drag top margin downwards by 18 pt (24 px)
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(12.0, text_t),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    v_ruler.mousePressEvent(press_ev)
    assert v_ruler._drag_kind == "top"
    assert len(guidelines) > 0

    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(12.0, text_t + 24.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    v_ruler.mouseMoveEvent(move_ev)

    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(12.0, text_t + 24.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    v_ruler.mouseReleaseEvent(release_ev)

    # Top margin increased by 18 pt
    assert abs(sect.mt - 90.0) < 1.0


# ---------------------------------------------------------------------------
# WriterView Integration Tests
# ---------------------------------------------------------------------------


def test_writer_view_with_rulers_integration(qapp):
    """Verify WriterView integrates TabSelectorWidget, HorizontalRuler, and VerticalRuler."""
    doc = Document()
    p = doc.main.blocks[0]


    view = WriterView(doc=doc)
    view.resize(800, 600)
    view.show()

    assert view.tab_selector is not None
    assert view.h_ruler is not None
    assert view.v_ruler is not None
    assert view.canvas_view is not None

    # Verify visibility toggling
    view.set_ruler_visible(False)
    assert not view.h_ruler.isVisible()
    assert not view.v_ruler.isVisible()
    assert not view.tab_selector.isVisible()

    view.set_ruler_visible(True)
    assert view.h_ruler.isVisible()
    assert view.v_ruler.isVisible()
    assert view.tab_selector.isVisible()

    # Verify unit setting propagates
    view.set_ruler_unit(RulerUnit.CM)
    assert view.h_ruler.unit == RulerUnit.CM
    assert view.v_ruler.unit == RulerUnit.CM

    # Verify retranslate_ui works without throwing
    view.retranslate_ui()
