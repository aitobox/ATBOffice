"""Unit tests verifying 7-language (and 9-locale) i18n translation completeness."""

from __future__ import annotations

import json
from pathlib import Path

from atboffice.core.i18n import (
    LOCALE_DISPLAY_NAMES,
    SUPPORTED_LOCALES,
    get_i18n_manager,
    safe_tr,
)


def test_supported_locales_registered():
    """Verify all required locales are registered in SUPPORTED_LOCALES and LOCALE_DISPLAY_NAMES."""
    required = ["zh-CN", "zh-Hant", "en", "ja", "ko", "fr", "de", "es", "ru"]
    for loc in required:
        assert loc in SUPPORTED_LOCALES, f"Missing locale {loc} in SUPPORTED_LOCALES"
        assert loc in LOCALE_DISPLAY_NAMES, f"Missing display name for {loc}"


def test_locale_json_catalogs_exist_and_valid():
    """Verify JSON files for all supported locales exist, are valid JSON, and have content."""
    root = Path(__file__).resolve().parent.parent
    locale_dir = root / "src" / "atboffice" / "resources" / "locale"
    assert locale_dir.exists() and locale_dir.is_dir()

    for loc in SUPPORTED_LOCALES:
        json_file = locale_dir / f"{loc}.json"
        assert json_file.exists(), f"Catalog file {json_file} does not exist"
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, dict), f"Catalog {loc} must be a dictionary"
            assert len(data) > 0, f"Catalog {loc} cannot be empty"


def test_safe_tr_translations():
    """Verify that safe_tr translates core controls across all locales."""
    mgr = get_i18n_manager()
    expected_cancel = {
        "zh-CN": "取消",
        "zh-Hant": "取消",
        "en": "Cancel",
        "ja": "キャンセル",
        "ko": "취소",
        "fr": "Annuler",
        "de": "Abbrechen",
        "es": "Cancelar",
        "ru": "Отмена",
    }

    for loc, expected in expected_cancel.items():
        mgr.set_locale(loc)
        translated = safe_tr("Cancel")
        assert translated == expected, f"Failed for {loc}: got {translated}, expected {expected}"
