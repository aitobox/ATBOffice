"""Unit and regression tests for Lectern slide canvas auto-fit and zoom controls."""

from pathlib import Path
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.views.slide_canvas import SlideCanvasView, SlideScene
from atboffice.modules.presentation.views.workspace import LecternWorkspace
from atboffice.ui.shell.lectern_window import LecternWindow


def test_slide_canvas_view_defensive_zoom_fit(qapp: QApplication) -> None:
    """Ensure SlideCanvasView does not compute negative or 0.1 clamped zoom on tiny/pre-layout viewports."""
    scene = SlideScene(slide_width=960.0, slide_height=540.0)
    view = SlideCanvasView(scene=scene)
    # Simulate pre-layout widget where viewport is tiny (< margin 32)
    view.viewport().resize(QSize(20, 20))
    initial_zoom = view.zoom

    view.zoom_fit()
    # Zoom should not have been set to a negative or clamped 0.1 value
    assert view.zoom == initial_zoom or view.zoom == 1.0
    assert view.is_auto_fit is True

    # Now resize to a real viewport and show
    view.resize(QSize(1000, 600))
    view.show()
    qapp.processEvents()
    view.zoom_fit()
    # (1000 - 32) / 960 = 1.008; (600 - 32) / 540 = 1.0518 -> min = ~1.008
    assert 0.95 <= view.zoom <= 1.05
    view.close()


def test_slide_canvas_view_auto_fit_mode_transitions(qapp: QApplication) -> None:
    """Verify that manual zoom overrides auto_fit, while zoom_fit restores it."""
    scene = SlideScene(slide_width=960.0, slide_height=540.0)
    view = SlideCanvasView(scene=scene)
    assert view.is_auto_fit is True

    view.set_zoom(1.5)
    assert view.is_auto_fit is False
    assert abs(view.zoom - 1.5) < 1e-4

    view.zoom_in()
    assert view.is_auto_fit is False
    assert abs(view.zoom - (1.5 * 1.25)) < 1e-4

    view.zoom_out()
    assert view.is_auto_fit is False

    view.zoom_fit()
    assert view.is_auto_fit is True


def test_lectern_workspace_zoom_methods(qapp: QApplication) -> None:
    """Verify zoom delegation methods on LecternWorkspace."""
    pres = Presentation.create_new()
    ws = LecternWorkspace(presentation=pres)
    ws.resize(1200, 800)

    assert ws.is_auto_fit is True

    ws.set_zoom(2.0)
    assert ws.is_auto_fit is False
    assert abs(ws.canvas_view.zoom - 2.0) < 1e-4

    ws.fit_to_window()
    assert ws.is_auto_fit is True

    ws.zoom_in()
    assert ws.is_auto_fit is False

    ws.zoom_out()
    assert ws.is_auto_fit is False


def test_slide_switching_preserves_zoom_setting(qapp: QApplication) -> None:
    """Verify slide switching respects manual zoom vs auto-fit."""
    pres = Presentation()
    pres.w = 960.0
    pres.h = 540.0
    s1 = Slide(id="s1")
    s2 = Slide(id="s2")
    pres.slides = [s1, s2]

    ws = LecternWorkspace(presentation=pres)
    ws.resize(1200, 800)

    # In auto-fit mode, switching slide maintains auto-fit
    ws.set_current_slide_index(1)
    assert ws.is_auto_fit is True

    # User manually zooms to 1.75
    ws.set_zoom(1.75)
    assert ws.is_auto_fit is False
    assert abs(ws.canvas_view.zoom - 1.75) < 1e-4

    # Switch back to first slide; manual zoom should be retained
    ws.set_current_slide_index(0)
    assert ws.is_auto_fit is False
    assert abs(ws.canvas_view.zoom - 1.75) < 1e-4


def test_aspect_ratios_fit(qapp: QApplication) -> None:
    """Verify that both 16:9 and 4:3 slide dimensions fit properly."""
    # 16:9
    scene_16_9 = SlideScene(slide_width=960.0, slide_height=540.0)
    view_16_9 = SlideCanvasView(scene=scene_16_9)
    view_16_9.resize(1000, 700)
    view_16_9.show()
    qapp.processEvents()
    view_16_9.zoom_fit()
    scale_16_9 = view_16_9.zoom
    assert 0.9 <= scale_16_9 <= 1.1
    view_16_9.close()

    # 4:3
    scene_4_3 = SlideScene(slide_width=720.0, slide_height=540.0)
    view_4_3 = SlideCanvasView(scene=scene_4_3)
    view_4_3.resize(1000, 700)
    view_4_3.show()
    qapp.processEvents()
    view_4_3.zoom_fit()
    scale_4_3 = view_4_3.zoom
    assert 1.1 <= scale_4_3 <= 1.35
    view_4_3.close()


def test_lectern_window_zoom_combo_integration(qapp: QApplication) -> None:
    """Verify zoom combo synchronization and window resize propagation in LecternWindow."""
    win = LecternWindow()
    win.resize(1200, 800)
    win.show()
    qapp.processEvents()

    ws = win.presentation_view.workspace
    cv = ws.canvas_view

    # After window is shown and resized, zoom should be well above 0.1
    assert cv.zoom > 0.4
    assert cv.is_auto_fit is True

    # Select manual zoom percentage via combo
    if hasattr(win, "zoom_combo") and win.zoom_combo:
        win.zoom_combo.setCurrentText("150%")
        qapp.processEvents()
        assert abs(cv.zoom - 1.5) < 1e-3
        assert cv.is_auto_fit is False

        # Select "适合比例" (fit to window)
        win.zoom_combo.setCurrentText("适合比例")
        qapp.processEvents()
        assert cv.is_auto_fit is True
        assert cv.zoom > 0.4

    win.close()
