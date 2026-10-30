"""Tests for i18n translation system and safe_tr catalog loader."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from PySide6.QtCore import QCoreApplication

from atboffice.core.i18n import (
    TranslationCatalog,
    I18nManager,
    get_i18n_manager,
    load_locale,
    safe_tr,
    tr,
    get_available_locales,
    normalize_locale_name,
)


@pytest.fixture(autouse=True)
def reset_locale():
    """Ensure i18n manager resets to default zh-CN before each test."""
    manager = get_i18n_manager()
    manager.set_locale("zh-CN")
    yield
    manager.set_locale("zh-CN")


def test_locale_files_exist_and_valid_json():
    """Verify all 7 locale JSON files exist in resources/locale and are valid."""
    locales_dir = Path(__file__).resolve().parent.parent.parent / "src" / "atboffice" / "resources" / "locale"
    assert locales_dir.exists(), f"Directory {locales_dir} does not exist"

    expected = ["zh-CN", "zh-Hant", "en", "ja", "ko", "fr", "de"]
    for loc in expected:
        file_path = locales_dir / f"{loc}.json"
        assert file_path.exists(), f"Locale file {file_path} missing"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert len(data) > 5000, f"Locale {loc} has only {len(data)} entries"


def test_normalize_locale_name():
    """Verify standard and non-standard locale names are correctly normalized."""
    assert normalize_locale_name("zh_CN") == "zh-CN"
    assert normalize_locale_name("zh-cn") == "zh-CN"
    assert normalize_locale_name("zh") == "zh-CN"
    assert normalize_locale_name("zh_TW") == "zh-Hant"
    assert normalize_locale_name("zh-HK") == "zh-Hant"
    assert normalize_locale_name("zh-Hant") == "zh-Hant"
    assert normalize_locale_name("en_US") == "en"
    assert normalize_locale_name("en") == "en"
    assert normalize_locale_name("ja_JP") == "ja"
    assert normalize_locale_name("ko_KR") == "ko"
    assert normalize_locale_name("fr_FR") == "fr"
    assert normalize_locale_name("de_DE") == "de"
    # Unknown fallback
    assert normalize_locale_name("es") == "en"


def test_translation_catalog_7_languages():
    """Test translation across all 7 supported languages."""
    # zh-CN
    cat_zh = TranslationCatalog("zh-CN")
    assert "保存" in cat_zh.translate("&Save")
    assert "打开" in cat_zh.translate("&Open...")
    assert "文件" in cat_zh.translate("&File")

    # zh-Hant
    cat_hant = TranslationCatalog("zh-Hant")
    assert "儲存" in cat_hant.translate("&Save")
    assert "開啟" in cat_hant.translate("&Open...") or "打開" in cat_hant.translate("&Open...")

    # en
    cat_en = TranslationCatalog("en")
    assert cat_en.translate("&Save") == "&Save"
    assert cat_en.translate("&File") == "&File"

    # ja
    cat_ja = TranslationCatalog("ja")
    assert "保存" in cat_ja.translate("&Save")
    assert "ファイル" in cat_ja.translate("&File")

    # ko
    cat_ko = TranslationCatalog("ko")
    assert "저장" in cat_ko.translate("&Save")
    assert "파일" in cat_ko.translate("&File")

    # fr
    cat_fr = TranslationCatalog("fr")
    assert "Enregi" in cat_fr.translate("&Save")
    assert "Fichier" in cat_fr.translate("&File")

    # de
    cat_de = TranslationCatalog("de")
    assert "Speichern" in cat_de.translate("&Save")
    assert "Datei" in cat_de.translate("&File")


def test_context_stripping():
    """Test text with context suffix like 'Line|chart'."""
    cat = TranslationCatalog("zh-CN")
    # 'Line|chart' in zh-CN is 折线图
    res_context = cat.translate("Line|chart")
    assert res_context == "折线图"

    # Context that does not exist should strip context and lookup plain text
    res_fallback = cat.translate("&File|shell")
    assert "文件" in res_fallback


def test_mnemonic_matching_and_stripping():
    """Test mnemonic handling with and without ampersand."""
    cat = TranslationCatalog("zh-CN")
    # Exact key with &
    assert cat.translate("&Save") == "保存(&S)"

    # Stripped lookup: caller passes 'Save', catalog has '&Save': '保存(&S)'
    # Stripped of (&S) should yield '保存'
    assert cat.translate("Save") == "保存"

    # Exact key without &
    assert cat.translate("&Paste") == "粘贴(&P)"
    assert cat.translate("Paste") == "粘贴"


def test_cjk_and_untranslated_passthrough():
    """Verify CJK text and unknown keys pass through safely."""
    cat = TranslationCatalog("zh-CN")
    assert cat.translate("自定义文本") == "自定义文本"
    assert cat.translate("未翻译的新功能模块 XYZ") == "未翻译的新功能模块 XYZ"
    assert cat.translate("NonExistentSpecialKey123") == "NonExistentSpecialKey123"


def test_placeholder_substitution():
    """Test positional placeholder replacement {0}, {1}."""
    cat = TranslationCatalog("zh-CN")
    # Exact sentence from catalog
    res = cat.translate("Do you want to save the changes to {0}?", "Document1.docx")
    assert "Document1.docx" in res
    assert "保存" in res

    # Missing arg safety: {1} should remain intact without error
    partial = cat.translate("Preview: Page {0} of {1}", 5)
    assert "5" in partial
    assert "{1}" in partial


def test_i18n_manager_singleton_and_signals(qapp):
    """Test I18nManager signal emission and global safe_tr / tr functions."""
    manager = get_i18n_manager()
    signals_received = []

    def on_locale_changed(loc: str):
        signals_received.append(loc)

    manager.locale_changed.connect(on_locale_changed)

    # Change to Japanese
    load_locale("ja")
    assert manager.current_locale == "ja"
    assert signals_received == ["ja"]
    assert "ファイル" in safe_tr("&File")
    assert "ファイル" in tr("&File")

    # Change to French
    load_locale("fr")
    assert manager.current_locale == "fr"
    assert signals_received == ["ja", "fr"]
    assert "Fichier" in safe_tr("&File")

    # Change back to Simplified Chinese
    load_locale("zh-CN")
    assert manager.current_locale == "zh-CN"
    assert "文件" in safe_tr("&File")


def test_edge_cases():
    """Test edge cases: empty strings, None, non-string, unknown locale."""
    cat = TranslationCatalog("zh-CN")
    assert cat.translate("") == ""
    assert cat.translate(None) == ""

    # Global safe_tr edge cases
    assert safe_tr("") == ""
    assert safe_tr(None) == ""

    # Unknown locale safely defaults
    bad_cat = TranslationCatalog("nonexistent_lang")
    assert bad_cat.locale == "en"
    assert bad_cat.translate("&File") == "&File"


def test_window_retranslate_on_locale_change(qapp):
    """Test that BaseOfficeWindow and MainWindow respond to locale_changed signal."""
    from atboffice.ui.shell.base_window import BaseOfficeWindow
    from atboffice.ui.shell.main_window import MainWindow

    win = BaseOfficeWindow()
    called = []
    win.retranslate_ui = lambda: called.append("base")

    main_win = MainWindow()
    main_called = []
    main_win.retranslate_ui = lambda: main_called.append("main")

    load_locale("en")
    assert "base" in called
    assert "main" in main_called

    load_locale("zh-CN")
    win.close()
    main_win.close()
