"""Theme fonts of a WordprocessingML package (port of quire/js/docx-read.js:155-182).

A run's ``w:rFonts`` may name a theme slot (``asciiTheme="minorHAnsi"``) instead of a face. The
slot is filled from the theme part's ``a:fontScheme``: ``major*``/``minor*`` pick the heading or
body font, and the suffix picks the script — ``Ascii``/``HAnsi`` the Latin face, ``EastAsia``
the East Asian face and ``Bidi`` the complex-script face.
"""

from __future__ import annotations

from dataclasses import dataclass

from atboffice.vfs import etree as ET

# East Asian / bidi language → the ``<a:font script=…>`` entry Word falls back to when the
# theme's own ``a:ea`` / ``a:cs`` face is empty (settings.xml ``w:themeFontLang``).
_EA_SCRIPTS = (("ja", "Jpan"), ("ko", "Hang"), ("zh-cn", "Hans"), ("zh-sg", "Hans"), ("zh", "Hant"))
_CS_SCRIPTS = (
    ("ar", "Arab"),
    ("fa", "Arab"),
    ("ur", "Arab"),
    ("he", "Hebr"),
    ("yi", "Hebr"),
    ("th", "Thai"),
)


def _script_for(lang: str, table: tuple[tuple[str, str], ...]) -> str:
    lang = (lang or "").lower()
    for prefix, script in table:
        if lang.startswith(prefix):
            return script
    return ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(elem: ET.Element | None, name: str) -> ET.Element | None:
    if elem is None:
        return None
    for c in elem:
        if _local(c.tag) == name:
            return c
    return None


@dataclass
class ThemeFonts:
    """Typefaces of a theme's font scheme ("" when the slot is empty)."""

    major: str = "Cambria"
    minor: str = "Calibri"
    major_ea: str = ""
    minor_ea: str = ""
    major_cs: str = ""
    minor_cs: str = ""

    def resolve(self, theme_value: str | None) -> str:
        """Face for a ``ST_Theme`` value such as ``minorHAnsi``; "" when unknown or empty."""
        v = theme_value or ""
        if v.startswith("major"):
            kind, rest = "major", v[5:]
        elif v.startswith("minor"):
            kind, rest = "minor", v[5:]
        else:
            return ""
        if rest in ("Ascii", "HAnsi"):
            return getattr(self, kind)
        if rest == "EastAsia":
            return getattr(self, f"{kind}_ea")
        if rest == "Bidi":
            return getattr(self, f"{kind}_cs")
        return ""


def parse_theme_fonts(
    theme_xml: bytes | str | None, ea_lang: str = "", bidi_lang: str = ""
) -> ThemeFonts:
    """Read ``a:fontScheme`` from a theme part; Office defaults when absent or unreadable.

    ``ea_lang`` / ``bidi_lang`` are settings.xml ``w:themeFontLang`` ``eastAsia`` / ``bidi``:
    they choose the ``<a:font script=…>`` face when the theme's own ``a:ea`` / ``a:cs`` is empty.
    """
    fonts = ThemeFonts()
    if not theme_xml:
        return fonts
    try:
        root = ET.fromstring(theme_xml)
    except ET.ParseError:
        return fonts
    scheme = next((e for e in root.iter() if _local(e.tag) == "fontScheme"), None)
    if scheme is None:
        return fonts

    ea_script = _script_for(ea_lang, _EA_SCRIPTS)
    cs_script = _script_for(bidi_lang, _CS_SCRIPTS)

    def slot(part: ET.Element | None, own_tag: str, script: str) -> str:
        own = _child(part, own_tag)
        face = own.get("typeface", "") if own is not None else ""
        if face or part is None or not script:
            return face
        for c in part:
            if _local(c.tag) == "font" and c.get("script") == script:
                return c.get("typeface", "")
        return ""

    for kind in ("major", "minor"):
        part = _child(scheme, f"{kind}Font")
        latin = _child(part, "latin")
        if latin is not None and latin.get("typeface"):
            setattr(fonts, kind, latin.get("typeface"))
        setattr(fonts, f"{kind}_ea", slot(part, "ea", ea_script))
        setattr(fonts, f"{kind}_cs", slot(part, "cs", cs_script))
    return fonts
