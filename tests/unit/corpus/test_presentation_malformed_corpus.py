"""Corpus regression tests for malformed and degenerate .pptx files."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from atboffice.modules.presentation.io import read_pptx, write_pptx
from atboffice.modules.presentation.views.workspace import LecternWorkspace
from atboffice.ui.shell.lectern_window import LecternWindow

MALFORMED_DIR = Path(__file__).resolve().parents[2] / "docs" / "powerpoint" / "malformed"


@pytest.mark.parametrize(
    "pptx_name,min_warnings",
    [
        ("malformed_numeric_attrs.pptx", 1),
        ("broken_chart_and_rels.pptx", 1),
        ("degenerate_shapes_and_cycles.pptx", 0),
        ("partial_corrupt_slide.pptx", 1),
    ],
)
def test_malformed_pptx_opens_renders_and_shows_warning_banner(
    qtbot, tmp_path, pptx_name: str, min_warnings: int
):
    """Malformed fixtures open cleanly, render, roundtrip, and show banner UI."""
    pptx_path = MALFORMED_DIR / pptx_name
    assert pptx_path.is_file(), f"Missing malformed fixture: {pptx_path}"

    pres = read_pptx(pptx_path)
    assert len(pres.slides) >= 1
    assert len(pres.load_warnings) >= min_warnings

    ws = LecternWorkspace(presentation=pres)
    qtbot.addWidget(ws)
    ws.resize(1024, 720)
    ws.show()

    if min_warnings > 0:
        assert not ws.degraded_banner.isHidden()
    else:
        assert ws.degraded_banner.isHidden()

    # Walk every slide in scene and paint canvas offscreen
    img = QImage(640, 360, QImage.Format.Format_ARGB32_Premultiplied)
    for idx in range(len(pres.slides)):
        ws.set_current_slide_index(idx)
        painter = QPainter(img)
        try:
            ws.scene.render(painter, QRectF(0, 0, 640, 360))
        finally:
            painter.end()

    # Full shell open_file lifecycle must succeed without raising or marking modified
    win = LecternWindow()
    qtbot.addWidget(win)
    win.show()
    win.open_file(str(pptx_path))
    assert not win.is_modified
    if min_warnings > 0:
        assert not win.presentation_view.workspace.degraded_banner.isHidden()

    # Safe save roundtrip back to bytes
    roundtrip_bytes = write_pptx(pres)
    assert len(roundtrip_bytes) > 0
