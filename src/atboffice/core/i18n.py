"""Multi-language localization and translation catalog system for ATBOffice."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QObject, QTranslator, Signal

logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = [
    "zh-CN",
    "zh-Hant",
    "en",
    "ja",
    "ko",
    "fr",
    "de",
    "es",
    "ru",
]

LOCALE_DISPLAY_NAMES = {
    "zh-CN": "简体中文 (Simplified Chinese)",
    "zh-Hant": "繁體中文 (Traditional Chinese)",
    "en": "English",
    "ja": "日本語 (Japanese)",
    "ko": "한국어 (Korean)",
    "fr": "Français (French)",
    "de": "Deutsch (German)",
    "es": "Español (Spanish)",
    "ru": "Русский (Russian)",
}

# Regex for stripping trailing Asian mnemonic accelerator, e.g. "保存(&S)" -> "保存"
RE_ASIAN_MNEMONIC = re.compile(r"\(&[A-Za-z0-9]\)")
# Regex for context stripping, e.g. "Line|chart" -> "Line"
RE_CONTEXT = re.compile(r"(\S)\|[A-Za-z][A-Za-z -]*$")
# Regex for CJK characters
RE_CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def normalize_locale_name(locale_name: str | None) -> str:
    """Normalize input locale string to canonical ID (e.g. 'zh_CN' -> 'zh-CN')."""
    if not locale_name:
        return "zh-CN"

    tag = locale_name.strip().replace("_", "-").lower()

    # Traditional Chinese variants
    if tag in ("zh-tw", "zh-hk", "zh-mo", "zh-hant") or tag.startswith("zh-hant"):
        return "zh-Hant"

    # Simplified Chinese variants
    if (
        tag == "zh"
        or tag in ("zh-cn", "zh-sg", "zh-hans")
        or tag.startswith("zh-hans")
        or tag.startswith("zh-cn")
    ):
        return "zh-CN"

    # Base language codes
    base = tag.split("-")[0]
    if base in ("ja", "ko", "fr", "de", "es", "ru", "en"):
        return base

    # Fallback to English for other non-supported languages
    return "en"


def plain_key(key: str) -> str:
    """Return text without context suffix (e.g. 'Line|chart' -> 'Line')."""
    return RE_CONTEXT.sub(r"\1", key)


def clean_amp(s: str) -> str:
    """Strip ampersand accelerators (e.g. '&Save' -> 'Save', '&&' -> '&')."""
    return re.sub(r"(?<!&)&(?!&)", "", s).replace("&&", "&")


def clean_asian_mnemonic(s: str) -> str:
    """Strip trailing mnemonic accelerator (e.g. '保存(&S)' -> '保存')."""
    return RE_ASIAN_MNEMONIC.sub("", s)


_LOCALE_DIR = Path(__file__).resolve().parent.parent / "resources" / "locale"
_SOURCE_EN: dict[str, str] | None = None


def _source_en() -> dict[str, str]:
    """Chinese UI source text -> English text, loaded once.

    Most UI strings are written in Chinese in the source code, while the locale
    catalogs are keyed by English text. This map links the two so that other
    locales can translate Chinese source strings.
    """
    global _SOURCE_EN
    if _SOURCE_EN is None:
        try:
            with open(_LOCALE_DIR / "source" / "zh-CN_to_en.json", encoding="utf-8") as f:
                data = json.load(f)
            _SOURCE_EN = {k: v for k, v in data.items() if isinstance(v, str) and v}
        except Exception as e:
            logger.error("Failed to load the source text map: %s", e)
            _SOURCE_EN = {}
    return _SOURCE_EN


def source_to_english(text: str) -> str | None:
    """English text for a Chinese UI source string, or None when unknown.

    Accelerators survive only when the Chinese text has one, so a menu label
    "保存(&S)" becomes "&Save" while a message "保存" becomes "Save".
    """
    table = _source_en()
    english = table.get(text)
    if english is None:
        bare = clean_asian_mnemonic(text)
        if bare != text:
            english = table.get(bare)
    if english is None:
        return None
    if "&" not in text:
        english = clean_amp(english)
    return english


class TranslationCatalog:
    """High-performance translation dictionary loader and lookup engine."""

    def __init__(self, locale: str = "zh-CN") -> None:
        self.locale = normalize_locale_name(locale)
        self._raw_dict: dict[str, Any] = {}
        self._stripped_lookup: dict[str, str] = {}
        self._load_dictionary()

    def _get_locale_file_path(self, locale: str) -> Path:
        return _LOCALE_DIR / f"{locale}.json"

    def _load_dictionary(self) -> None:
        file_path = self._get_locale_file_path(self.locale)
        if not file_path.exists():
            logger.warning("Locale file %s does not exist; falling back to empty dict", file_path)
            self._raw_dict = {}
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._raw_dict = data
            else:
                self._raw_dict = {}
        except Exception as e:
            logger.error("Failed to load locale %s from %s: %s", self.locale, file_path, e)
            self._raw_dict = {}

        # Precompute stripped key lookup cache
        self._stripped_lookup = {}
        for k, v in self._raw_dict.items():
            if isinstance(v, str) and v:
                # Key without & accelerator
                c_key = clean_amp(k)
                if c_key not in self._stripped_lookup:
                    self._stripped_lookup[c_key] = v

    def translate(self, key: str | None, *args: Any) -> str:
        """Translate key into the active locale text with intelligent fallback."""
        if key is None:
            return ""
        if not isinstance(key, str):
            key = str(key)
        if not key:
            return ""

        # Chinese source text: Simplified Chinese shows it as written; other
        # locales go through its English text.
        if self.locale != "zh-CN" and RE_CJK.search(key):
            return self._translate_source(key, *args)

        # English locale returns plain key
        if self.locale == "en":
            out = plain_key(key)
            return self._format(out, *args)

        # 1. Exact match in catalog
        val = self._raw_dict.get(key)
        if isinstance(val, str) and val:
            return self._format(val, *args)

        # 2. Context-stripped match (e.g. 'Line|chart' fallback to 'Line')
        base_key = plain_key(key)
        if base_key != key:
            val = self._raw_dict.get(base_key)
            if isinstance(val, str) and val:
                return self._format(val, *args)

        # 3. Mnemonic matching
        # Case A: Caller gave stripped key 'Save', catalog has '&Save' -> '保存(&S)'
        if key in self._stripped_lookup:
            raw_target = self._stripped_lookup[key]
            # If target has trailing mnemonic like '保存(&S)', strip to '保存'
            clean_target = clean_asian_mnemonic(raw_target)
            return self._format(clean_target, *args)

        # Case B: Caller gave '&Save', catalog only has 'Save'
        c_k = clean_amp(key)
        if c_k != key:
            val = self._raw_dict.get(c_k)
            if isinstance(val, str) and val:
                return self._format(val, *args)
            if c_k in self._stripped_lookup:
                val = self._stripped_lookup[c_k]
                return self._format(clean_asian_mnemonic(val), *args)

        # 4. If text contains CJK characters, it is already localized Chinese
        if RE_CJK.search(key):
            return self._format(key, *args)

        # 5. Untranslated fallback: return plain base key
        return self._format(base_key, *args)

    def _translate_source(self, key: str, *args: Any) -> str:
        english = source_to_english(key)
        if english is None:
            return self._format(key, *args)
        if self.locale == "en":
            return self._format(english, *args)
        if self._lookup(english) is not None:
            return self.translate(english, *args)
        # Not in this locale's catalog: Traditional Chinese readers are better
        # served by the Simplified source text, everyone else by English.
        return self._format(key if self.locale == "zh-Hant" else english, *args)

    def _lookup(self, key: str) -> str | None:
        """The catalog's own entry for ``key`` (with or without accelerators)."""
        for candidate in (key, plain_key(key), clean_amp(key)):
            val = self._raw_dict.get(candidate)
            if isinstance(val, str) and val:
                return val
        return self._stripped_lookup.get(clean_amp(key))

    def _format(self, template: str, *args: Any) -> str:
        """Safely format string using positional args ({0}, {1}, etc.)."""
        if not args:
            return template
        try:
            for idx, arg in enumerate(args):
                template = template.replace(f"{{{idx}}}", str(arg))
            return template
        except Exception:
            return template


#: Qt's own catalog name for each locale (for standard dialogs and buttons).
_QT_LOCALE_NAMES = {"zh-CN": "zh_CN", "zh-Hant": "zh_TW"}


def _qt_translator(locale: str) -> QTranslator | None:
    """Qt's translation of its standard dialogs and buttons for ``locale``."""
    name = _QT_LOCALE_NAMES.get(locale, locale)
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    translator = QTranslator()
    if translator.load(f"qtbase_{name}", folder):
        return translator
    return None


class I18nManager(QObject):
    """Global manager for application locale state and dynamic switching."""

    locale_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._current_locale = "zh-CN"
        self._catalog = TranslationCatalog(self._current_locale)
        self._qt_translator: QTranslator | None = None
        self._qt_translator_locale: str | None = None

    @property
    def current_locale(self) -> str:
        """Return the active normalized locale ID."""
        return self._current_locale

    def set_locale(self, locale_name: str) -> None:
        """Switch active locale, reload catalog, and emit locale_changed."""
        norm = normalize_locale_name(locale_name)
        self._install_qt_translator(norm)
        if norm != self._current_locale or self._catalog.locale != norm:
            self._current_locale = norm
            self._catalog = TranslationCatalog(norm)
            self.locale_changed.emit(norm)

    def _install_qt_translator(self, locale: str) -> None:
        """Translate Qt's own texts (standard buttons, file dialogs) too."""
        app = QCoreApplication.instance()
        if app is None or self._qt_translator_locale == locale:
            return
        if self._qt_translator is not None:
            app.removeTranslator(self._qt_translator)
            self._qt_translator = None
        translator = _qt_translator(locale)
        if translator is not None and app.installTranslator(translator):
            self._qt_translator = translator
        self._qt_translator_locale = locale

    def load_locale(self, locale_name: str) -> None:
        """Alias for set_locale."""
        self.set_locale(locale_name)

    def translate(self, key: str | None, *args: Any) -> str:
        """Translate key using current active catalog."""
        return self._catalog.translate(key, *args)


_GLOBAL_I18N_MANAGER: I18nManager | None = None


def get_i18n_manager() -> I18nManager:
    """Return the global I18nManager singleton."""
    global _GLOBAL_I18N_MANAGER
    if _GLOBAL_I18N_MANAGER is None:
        _GLOBAL_I18N_MANAGER = I18nManager()
    return _GLOBAL_I18N_MANAGER


def load_locale(locale_name: str) -> None:
    """Switch global active locale to locale_name."""
    get_i18n_manager().set_locale(locale_name)


def safe_tr(key: str | None, *args: Any) -> str:
    """Translate UI text safely using the active locale catalog."""
    return get_i18n_manager().translate(key, *args)


tr = safe_tr


def get_available_locales() -> list[str]:
    """Return list of supported locale IDs."""
    return list(SUPPORTED_LOCALES)


def get_locale_display_name(locale_name: str) -> str:
    """Return user-facing display name for a locale."""
    norm = normalize_locale_name(locale_name)
    return LOCALE_DISPLAY_NAMES.get(norm, norm)
