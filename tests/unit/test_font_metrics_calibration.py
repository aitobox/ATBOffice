"""Unit test suite for Global Font Metrics Calibration and Western/CJK Baseline Alignment."""

from __future__ import annotations

import pytest

from atboffice.modules.writer.layout.portions import (
    LayoutLine,
    PortionType,
    compute_font_metrics,
    compute_grid_line_height,
    get_font_key,
    get_line_factor,
    get_space_em,
    layout_paragraph,
)
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    DocGridProperties,
    ParagraphProperties,
    RunProperties,
    SectionProperties,
    SpacingProperties,
)
from atboffice.utils.font_metrics import (
    DEFAULT_FONT_METRIC,
    FONT_METRICS_CALIBRATION,
    FontMetricData,
    get_font_metric,
    is_cjk_font,
    normalize_font_key,
)


def test_standin_fonts_calibration_parameters():
    """Verify that Calibri, Cambria, Georgia, TNR, and Arial match stand-in font parameters."""
    # Calibri -> Carlito parameters
    m_calibri = get_font_metric("Calibri")
    assert m_calibri.substitute_family == "Carlito"
    assert pytest.approx(m_calibri.ascent_ratio, 0.0001) == 0.9521
    assert pytest.approx(m_calibri.descent_ratio, 0.0001) == 0.2686
    assert pytest.approx(m_calibri.line_factor, 0.0001) == 1.2207
    assert pytest.approx(m_calibri.space_em, 0.0001) == 0.2261

    # Cambria -> Caladea parameters
    m_cambria = get_font_metric("Cambria")
    assert m_cambria.substitute_family == "Caladea"
    assert pytest.approx(m_cambria.ascent_ratio, 0.0001) == 0.9000
    assert pytest.approx(m_cambria.descent_ratio, 0.0001) == 0.2500
    assert pytest.approx(m_cambria.line_factor, 0.0001) == 1.1724

    # Georgia -> Gelasio parameters
    m_georgia = get_font_metric("Georgia")
    assert m_georgia.substitute_family == "Gelasio"
    assert pytest.approx(m_georgia.ascent_ratio, 0.0001) == 0.9277
    assert pytest.approx(m_georgia.descent_ratio, 0.0001) == 0.3418
    assert pytest.approx(m_georgia.line_factor, 0.0001) == 1.1362

    # Times New Roman -> Tinos
    m_tnr = get_font_metric("Times New Roman")
    assert m_tnr.substitute_family == "Tinos"
    assert pytest.approx(m_tnr.ascent_ratio, 0.0001) == 0.8916
    assert pytest.approx(m_tnr.descent_ratio, 0.0001) == 0.2163
    assert pytest.approx(m_tnr.line_factor, 0.0001) == 1.1490

    # Arial -> Arimo
    m_arial = get_font_metric("Arial")
    assert m_arial.substitute_family == "Arimo"
    assert pytest.approx(m_arial.ascent_ratio, 0.0001) == 0.9053
    assert pytest.approx(m_arial.descent_ratio, 0.0001) == 0.2119
    assert pytest.approx(m_arial.line_factor, 0.0001) == 1.1490


def test_cjk_aliases_and_metrics():
    """Verify normalization and classification of Chinese, Japanese, and Korean fonts."""
    # Chinese aliases
    assert normalize_font_key("宋体") == "simsun"
    assert normalize_font_key("新宋体") == "nsimsun"
    assert normalize_font_key("微软雅黑") == "microsoft yahei"
    assert normalize_font_key("等线") == "dengxian"
    assert normalize_font_key("苹方") == "pingfang sc"

    assert is_cjk_font("宋体") is True
    assert is_cjk_font("SimSun") is True
    assert is_cjk_font("Microsoft YaHei") is True
    assert is_cjk_font("Times New Roman") is False

    # Japanese aliases
    assert normalize_font_key("ｍｓ 明朝") == "ms mincho"
    assert normalize_font_key("游ゴシック") == "yu gothic"
    assert normalize_font_key("メイリオ") == "meiryo"
    assert is_cjk_font("MS Gothic") is True
    assert is_cjk_font("Yu Mincho") is True

    # Korean aliases
    assert normalize_font_key("맑은 고딕") == "malgun gothic"
    assert normalize_font_key("바탕") == "batang"
    assert is_cjk_font("Malgun Gothic") is True


def test_fallback_unknown_font():
    """Verify that unlisted or custom font families fall back to standard metrics."""
    m = get_font_metric("SomeCompletelyUnknownFontFamilyName_12345")
    assert m == DEFAULT_FONT_METRIC
    assert m.line_factor == 1.17
    assert m.ascent_ratio == 0.80
    assert m.descent_ratio == 0.20


def test_compute_font_metrics_scaling():
    """Verify ascent and descent scaling calculations for various font sizes."""
    # 12pt Calibri (Carlito params: ascent ~ 0.9521, descent ~ 0.2686)
    asc_c, desc_c = compute_font_metrics(12.0, "Calibri")
    assert pytest.approx(asc_c, 0.05) == 11.43
    assert pytest.approx(desc_c, 0.05) == 3.22

    # 10.5pt SimSun (East Asian: ascent ~ 0.88, descent ~ 0.14)
    asc_s, desc_s = compute_font_metrics(10.5, "SimSun")
    assert pytest.approx(asc_s, 0.05) == 9.24
    assert pytest.approx(desc_s, 0.05) == 1.47


def test_line_layout_half_leading_baseline():
    """Verify that normal non-grid lines distribute half-leading evenly above and below."""
    p = Paragraph(
        runs=[
            TextItem(
                text="Hello World with Calibrated Metrics",
                r_pr=RunProperties(sz=12.0, font="Calibri"),
            )
        ],
        p_pr=ParagraphProperties(
            sp=SpacingProperties(line=1.0, line_rule="auto")
        ),
    )
    layout = layout_paragraph(p, container_width=500.0)
    assert len(layout.lines) == 1
    line = layout.lines[0]

    # Total height should match natural line height (12 * 1.2207 = 14.6484 pt)
    expected_natural_height = 12.0 * 1.2207
    assert pytest.approx(line.height, 0.1) == expected_natural_height

    # Baseline should include top half-leading:
    # half_leading = (height - (ascent + descent)) / 2.0
    # baseline = ascent + half_leading
    ascent, descent = compute_font_metrics(12.0, "Calibri")
    half_leading = max(0.0, (line.height - (ascent + descent)) / 2.0)
    expected_baseline = ascent + half_leading
    assert pytest.approx(line.baseline, 0.05) == expected_baseline
    assert line.baseline > ascent  # Crucial: prevents text from clinging to line top!


def test_mixed_western_cjk_baseline_coherence():
    """Verify that mixed English and Chinese text portions in a line share a single baseline."""
    p = Paragraph(
        runs=[
            TextItem(
                text="English Heading ",
                r_pr=RunProperties(sz=14.0, font="Times New Roman"),
            ),
            TextItem(
                text="中文标题混合排版",
                r_pr=RunProperties(sz=14.0, font="Times New Roman", font_ea="SimSun"),
            ),
        ],
        p_pr=ParagraphProperties(
            sp=SpacingProperties(line=1.0, line_rule="auto")
        ),
    )
    layout = layout_paragraph(p, container_width=600.0)
    assert len(layout.lines) == 1
    line = layout.lines[0]

    # Verify portions exist
    text_portions = [po for po in line.portions if po.type == PortionType.TEXT]
    assert len(text_portions) >= 2

    # The line's baseline is unified across all portions
    assert line.baseline > 0.0
    assert line.height > line.baseline


def test_east_asian_line_grid_snapping_15_6_and_18():
    """Verify line grid pitch snapping on 15.6pt and 18pt grids."""
    sect_15_6 = SectionProperties(
        doc_grid=DocGridProperties(type="lines", line_pitch=15.6)
    )
    p = Paragraph(
        runs=[
            TextItem(
                text="Grid Line Snapping Test",
                r_pr=RunProperties(sz=10.5, font="SimSun"),
            )
        ],
        p_pr=ParagraphProperties(
            sp=SpacingProperties(line=1.5, line_rule="auto")
        ),
    )
    layout = layout_paragraph(p, container_width=500.0, section_props=sect_15_6)
    assert len(layout.lines) == 1
    # 1.5 lines on 15.6pt grid = 23.4pt
    assert pytest.approx(layout.lines[0].height, 0.05) == 23.4

    sect_18 = SectionProperties(
        doc_grid=DocGridProperties(type="lines", line_pitch=18.0)
    )
    layout_18 = layout_paragraph(p, container_width=500.0, section_props=sect_18)
    assert len(layout_18.lines) == 1
    # 1.5 lines on 18.0pt grid = 27.0pt
    assert pytest.approx(layout_18.lines[0].height, 0.05) == 27.0
