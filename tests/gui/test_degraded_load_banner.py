"""GUI tests for non-blocking DegradedLoadBanner in LecternWorkspace."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from atboffice.modules.presentation.models.presentation import LoadWarning, Presentation
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.views.workspace import DegradedLoadBanner, LecternWorkspace


def test_degraded_load_banner_shows_warning_count_details_and_retranslates(qtbot, monkeypatch):
    """DegradedLoadBanner displays count, opens details, and refreshes text on retranslate_ui."""
    banner = DegradedLoadBanner()
    qtbot.addWidget(banner)
    banner.show()

    warnings = [
        LoadWarning(scope="chart", location="ppt/charts/chart1.xml", message="malformed XML"),
        LoadWarning(scope="shape", location="slide 2 / shape 4", message="bad int attribute"),
    ]
    banner.set_warnings(warnings)

    assert not banner.isHidden()
    assert "2" in banner.summary_label.text()

    captured: list[tuple[str, str]] = []

    def fake_info(parent, title, text, *args, **kwargs):
        captured.append((title, text))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "information", fake_info)
    banner.details_btn.click()
    assert len(captured) == 1
    assert "ppt/charts/chart1.xml" in captured[0][1]
    assert "slide 2 / shape 4" in captured[0][1]

    banner.retranslate_ui()
    assert "2" in banner.summary_label.text()


def test_degraded_load_banner_hidden_when_zero_warnings_and_dismissible(qtbot):
    """LecternWorkspace hides banner when clean and shows/dismisses on warnings."""
    pres = Presentation.create_new(title="Clean", empty=True)
    pres.slides.append(Slide(id="s1", layout="blank"))

    ws = LecternWorkspace(presentation=pres)
    qtbot.addWidget(ws)
    ws.show()

    assert ws.degraded_banner.isHidden()

    degraded = Presentation.create_new(title="Degraded", empty=True)
    degraded.slides.append(Slide(id="s1", layout="blank"))
    degraded.load_warnings.append(
        LoadWarning(scope="slide", location="slide 1", message="fallback blank slide")
    )
    ws.load_presentation(degraded)

    assert not ws.degraded_banner.isHidden()
    assert "1" in ws.degraded_banner.summary_label.text()

    ws.degraded_banner.close_btn.click()
    assert ws.degraded_banner.isHidden()
