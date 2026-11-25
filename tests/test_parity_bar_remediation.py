"""Regression tests for the three documents that fell below the 85% parity bar.

- ``libreoffice__totalsRowFunction.xlsx``: Century Gothic workbook columns were ~12% too narrow.
- ``openxml-sdk__sldsz-Slide Size-type-b4iso.pptx``: non-default slide sizes sat off-centre and
  clipped because the scene rect kept the 960x540 pasteboard.
- ``openxml-sdk__00d63cdd-…xlsx``: a documented limitation of the reference renderer, exempt from
  the single-document bar but still counted in the average.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.models.excel_units import (
    default_col_px,
    excel_mdw,
    width_to_px,
)
from scripts.office_diff.corpus import load_expectations, partition_corpus
from scripts.office_diff.models import DiffResult
from scripts.office_diff.reporter import generate_report

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "tests" / "docs"
TOTALS_XLSX = DOCS / "excel" / "xlsx" / "libreoffice__totalsRowFunction.xlsx"
B4_PPTX = DOCS / "powerpoint" / "pptx" / "openxml-sdk__sldsz-Slide Size-type-b4iso.pptx"
GROUP_XLSX_NAME = "openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx"


# ---------------------------------------------------------------------------
# Ledger: Century Gothic digit width
# ---------------------------------------------------------------------------


def test_century_gothic_digit_width_is_eight_pixels() -> None:
    assert excel_mdw("Century Gothic", 11) == 8
    assert excel_mdw("century gothic", 11) == 8
    # Unlisted faces keep the 7px fallback.
    assert excel_mdw("Some Unknown Face", 11) == 7


def test_century_gothic_default_column_is_seventy_two_pixels() -> None:
    assert default_col_px(excel_mdw("Century Gothic", 11), None, None) == 72


def test_totals_row_workbook_columns_match_reference() -> None:
    """B 15.625, C:F 19.625, G 24.875 chars at MDW 8 (ledger/js/model.js M.widthToPx)."""
    wb = read_xlsx(str(TOTALS_XLSX))
    sheet = wb[0]
    assert sheet.extra["excel_mdw"] == 8
    geo = sheet.geometry
    assert geo.col_size(0) == width_to_px(2.625, 8) == 21
    assert geo.col_size(1) == width_to_px(15.625, 8) == 125
    for c in range(2, 6):
        assert geo.col_size(c) == width_to_px(19.625, 8) == 157
    assert geo.col_size(6) == width_to_px(24.875, 8) == 199
    # The table (B2:G7) now spans the reference's 952px instead of 831px.
    assert sum(geo.col_size(c) for c in range(1, 7)) == 952


# ---------------------------------------------------------------------------
# Lectern: non-default slide sizes
# ---------------------------------------------------------------------------


def test_scene_rect_follows_slide_size(qapp) -> None:
    from atboffice.modules.presentation.views.slide_canvas import SlideScene

    scene = SlideScene()
    assert (scene.sceneRect().width(), scene.sceneRect().height()) == (1260.0, 740.0)
    scene.set_slide_size(852.5, 639.38)
    rect = scene.sceneRect()
    assert (rect.x(), rect.y()) == (-150.0, -100.0)
    assert rect.width() == pytest.approx(852.5 + 300.0)
    assert rect.height() == pytest.approx(639.38 + 200.0)


@pytest.mark.parametrize("bad", [(0, 540), (960, -1), ("x", 540), (None, None)])
def test_set_slide_size_ignores_invalid_sizes(qapp, bad) -> None:
    from atboffice.modules.presentation.views.slide_canvas import SlideScene

    scene = SlideScene()
    scene.set_slide_size(*bad)
    assert (scene.slide_width, scene.slide_height) == (960.0, 540.0)
    assert scene.sceneRect().height() == 740.0


def test_b4_slide_is_centred_and_unclipped(qtbot) -> None:
    from atboffice.modules.presentation.io.pptx_reader import read_pptx
    from atboffice.modules.presentation.views.workspace import LecternWorkspace

    pres = read_pptx(str(B4_PPTX))
    assert pres.w == pytest.approx(852.5)  # 10826750 EMU
    ws = LecternWorkspace(presentation=pres)
    qtbot.addWidget(ws)
    ws.load_presentation(pres)
    ws.resize(1200, 900)
    ws.show()
    qtbot.wait(50)
    view = ws.canvas_view
    view.zoom_fit()
    vp = view.viewport()
    top_left = view.mapFromScene(0.0, 0.0)
    bottom_right = view.mapFromScene(pres.w, pres.h)
    assert top_left.x() >= 0 and top_left.y() >= 0
    assert bottom_right.x() <= vp.width() and bottom_right.y() <= vp.height()
    # Equal margins above and below (within rounding).
    assert abs(top_left.y() - (vp.height() - bottom_right.y())) <= 4


# ---------------------------------------------------------------------------
# Parity tooling: documented reference limitations
# ---------------------------------------------------------------------------


def _result(name: str, score: float, limitation: str | None = None) -> DiffResult:
    return DiffResult(
        file=name,
        app="excel",
        similarity=0.95,
        mae=10.0,
        edge_similarity=0.9,
        roi_similarity=0.9,
        category="LAYOUT_DRIFT" if score < 0.85 else "PARITY_MATCH",
        orig_size=(1178, 798),
        target_size=(1178, 798),
        foreground_score=score,
        recall=score,
        precision=score,
        color_hist_similarity=score,
        reference_limitation=limitation,
    )


def test_expectations_record_group_shape_limitation() -> None:
    supported, _ = partition_corpus(load_expectations(DOCS / "expectations.json"), DOCS)
    by_name = {t.file: t for t in supported}
    assert "VibeOffice does not draw groups" in by_name[GROUP_XLSX_NAME].reference_limitation
    assert by_name[TOTALS_XLSX.name].reference_limitation == ""
    assert sum(1 for t in supported if t.reference_limitation) == 1


def test_reference_limitation_is_exempt_from_single_bar(tmp_path) -> None:
    results = [_result("a.xlsx", 0.99), _result("b.xlsx", 0.82, "reference cannot draw groups")]
    content = generate_report(results, tmp_path / "r.md")
    assert "✅ PASS" in content
    assert "## 5. Reference Limitations" in content
    assert "reference cannot draw groups" in content
    assert "TASK-DOC-01" not in content
    # Still counted in the average.
    assert "`90.50%`" in content


def test_unexplained_drift_still_fails_single_bar(tmp_path) -> None:
    results = [_result("a.xlsx", 0.99), _result("b.xlsx", 0.82)]
    content = generate_report(results, tmp_path / "r.md")
    assert "NEEDS_REMEDIATION" in content
    assert "TASK-DOC-01" in content
    assert "## 5. Reference Limitations" not in content


def test_diff_result_serializes_limitation() -> None:
    data = _result("b.xlsx", 0.82, "why").to_dict()
    assert json.loads(json.dumps(data))["reference_limitation"] == "why"
