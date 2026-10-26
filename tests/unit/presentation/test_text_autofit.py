"""Unit tests for Text AutoFit and outline level indent logic."""

from __future__ import annotations

from atboffice.modules.presentation.models.text import (
    BODY_BULLETS,
    BODY_SIZES,
    TextBody,
)
from atboffice.modules.presentation.views.text_editor import (
    calculate_autofit_scale,
    calculate_shape_autofit_size,
    clamp_outline_level,
)


class TestTextAutoFit:
    """Test PowerPoint-style AutoFit scaling and calculation."""

    def test_autofit_scale_no_overflow(self) -> None:
        # When content height <= available height, scale is 1.0
        scale = calculate_autofit_scale(need_height=80.0, avail_height=150.0, current_scale=1.0)
        assert scale == 1.0

    def test_autofit_scale_exact_fit(self) -> None:
        scale = calculate_autofit_scale(need_height=100.0, avail_height=100.0, current_scale=1.0)
        assert scale == 1.0

    def test_autofit_scale_moderate_overflow(self) -> None:
        # Need 200pt, but only 180pt available -> 180/200 = 0.90 -> 90%
        scale = calculate_autofit_scale(need_height=200.0, avail_height=180.0, current_scale=1.0)
        assert 0.85 <= scale <= 0.95
        assert scale == 0.9

    def test_autofit_scale_large_overflow(self) -> None:
        # Need 400pt, but only 200pt available -> 200/400 = 0.50 -> 50%
        scale = calculate_autofit_scale(need_height=400.0, avail_height=200.0, current_scale=1.0)
        assert scale == 0.5

    def test_autofit_scale_extreme_overflow_floor(self) -> None:
        # Need 2000pt, but only 100pt available -> 100/2000 = 0.05, but min is 0.25
        scale = calculate_autofit_scale(need_height=2000.0, avail_height=100.0, current_scale=1.0)
        assert scale == 0.25

    def test_autofit_scale_invalid_dimensions(self) -> None:
        assert calculate_autofit_scale(need_height=0.0, avail_height=100.0) == 1.0
        assert calculate_autofit_scale(need_height=100.0, avail_height=-10.0) == 1.0

    def test_autofit_re_expand(self) -> None:
        # Currently scaled down to 0.5, but user deleted text so need is only 50pt with 100pt avail
        scale = calculate_autofit_scale(need_height=50.0, avail_height=100.0, current_scale=0.5)
        # Should expand back up
        assert scale == 1.0

    def test_shape_autofit_size(self) -> None:
        w, h = calculate_shape_autofit_size(
            content_width=200.0,
            content_height=80.0,
            insets=(7.2, 3.6, 7.2, 3.6),
        )
        assert w >= 200.0 + 14.4
        assert h >= 80.0 + 7.2


class TestOutlineLevelClamping:
    """Test outline level boundary conditions."""

    def test_level_clamping(self) -> None:
        assert clamp_outline_level(0) == 0
        assert clamp_outline_level(4) == 4
        assert clamp_outline_level(8) == 8
        assert clamp_outline_level(-1) == 0
        assert clamp_outline_level(9) == 8
        assert clamp_outline_level(100) == 8

    def test_master_bullet_and_size_lookups(self) -> None:
        # Check that we have styles defined for 5+ levels (0 to 8 = 9 levels)
        assert len(BODY_BULLETS) >= 5
        assert len(BODY_SIZES) >= 5
        assert BODY_BULLETS[0] == "•"
        assert BODY_BULLETS[1] == "–"
        assert BODY_SIZES[0] > BODY_SIZES[1]


class TestTextBodyFontScaleSerialization:
    """Test font_scale field on TextBody."""

    def test_font_scale_defaults(self) -> None:
        tb = TextBody()
        assert tb.font_scale == 1.0
        d = tb.to_dict()
        assert "fontScale" not in d

    def test_font_scale_roundtrip(self) -> None:
        tb = TextBody(font_scale=0.85)
        d = tb.to_dict()
        assert d["fontScale"] == 0.85
        restored = TextBody.from_dict(d)
        assert restored.font_scale == 0.85
