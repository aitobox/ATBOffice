"""Issue #372: theme fonts, explicit run fonts and bundled metric-compatible typefaces."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo

from atboffice.modules.writer.io.docx_fonts import ThemeFonts, parse_theme_fonts
from atboffice.modules.writer.io.docx_reader import read_docx
from atboffice.modules.writer.models.properties import RunProperties
from atboffice.modules.writer.models.styles import merge_r_props, resolve_r_props
from atboffice.utils.font_registry import FONTS_DIR, register_bundled_fonts

DOCX = Path(__file__).parent / "docs" / "word" / "docx"

THEME = b"""<?xml version="1.0"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:themeElements>
<a:fontScheme name="Office">
 <a:majorFont><a:latin typeface="Cambria"/><a:ea typeface=""/>
  <a:cs typeface="Times New Roman"/>
  <a:font script="Jpan" typeface="MS Gothic"/></a:majorFont>
 <a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface="Arial"/>
  <a:font script="Jpan" typeface="MS Mincho"/>
  <a:font script="Hans" typeface="SimSun"/></a:minorFont>
</a:fontScheme></a:themeElements></a:theme>"""


def _first_text_run(doc, needle: str):
    for block in doc.main.blocks:
        for item in getattr(block, "runs", []) or []:
            if needle in (getattr(item, "text", "") or ""):
                return block, item
    raise AssertionError(f"run containing {needle!r} not found")


# --- theme parsing & resolution -------------------------------------------------------


def test_parse_theme_fonts_latin_cs_and_script_ea() -> None:
    tf = parse_theme_fonts(THEME, "ja-JP")
    assert (tf.major, tf.minor) == ("Cambria", "Calibri")
    assert (tf.major_cs, tf.minor_cs) == ("Times New Roman", "Arial")
    assert (tf.major_ea, tf.minor_ea) == ("MS Gothic", "MS Mincho")
    assert parse_theme_fonts(THEME, "zh-CN").minor_ea == "SimSun"
    assert parse_theme_fonts(THEME, "").minor_ea == ""


def test_parse_theme_fonts_cs_falls_back_to_bidi_script() -> None:
    data = THEME.replace(
        b'<a:cs typeface="Arial"/>', b'<a:cs typeface=""/><a:font script="Arab" typeface="Tahoma"/>'
    )
    assert parse_theme_fonts(data, "", "ar-SA").minor_cs == "Tahoma"
    assert parse_theme_fonts(data, "", "").minor_cs == ""


def test_parse_theme_fonts_missing_or_corrupt_uses_office_defaults() -> None:
    for data in (None, b"", b"<not xml"):
        tf = parse_theme_fonts(data)
        assert (tf.major, tf.minor) == ("Cambria", "Calibri")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("minorHAnsi", "Calibri"),
        ("minorAscii", "Calibri"),
        ("majorHAnsi", "Cambria"),
        ("majorAscii", "Cambria"),
        ("minorBidi", "Arial"),
        ("majorBidi", "Times New Roman"),
        ("minorEastAsia", "MS Mincho"),
        ("bogus", ""),
        ("", ""),
    ],
)
def test_theme_value_resolution(value: str, expected: str) -> None:
    assert parse_theme_fonts(THEME, "ja-JP").resolve(value) == expected


def test_theme_fonts_defaults() -> None:
    assert ThemeFonts().resolve("minorHAnsi") == "Calibri"


# --- explicit fonts in the cascade -------------------------------------------------------


def test_explicit_times_new_roman_overrides_default() -> None:
    base = RunProperties(font="Aptos")
    over = RunProperties(font="Times New Roman", font_explicit=True)
    assert merge_r_props(base, over).font == "Times New Roman"
    # An untouched RunProperties still inherits.
    assert merge_r_props(base, RunProperties()).font == "Aptos"


def test_font_cs_merges() -> None:
    base = RunProperties(font_cs="Arial")
    assert merge_r_props(base, RunProperties()).font_cs == "Arial"
    assert merge_r_props(base, RunProperties(font_cs="David")).font_cs == "David"


# --- fixtures (acceptance criteria) -------------------------------------------------------


def test_fdo52208_body_resolves_to_theme_minor_font() -> None:
    doc = read_docx(DOCX / "libreoffice__fdo52208.docx")
    assert doc.defaults["r_pr"].font == "Calibri"
    # Any paragraph without its own face resolves to the theme minor font.
    fonts = {
        resolve_r_props(doc, b, it).font
        for b in doc.main.blocks
        for it in getattr(b, "runs", []) or []
        if getattr(it, "text", "")
    }
    assert "Calibri" in fonts


def test_tdf43100_theme_attribute_wins_over_explicit_face() -> None:
    doc = read_docx(DOCX / "libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx")
    rp = doc.defaults["r_pr"]
    assert rp.font == "Calibri"  # asciiTheme=minorHAnsi
    assert rp.font_cs == "Arial"  # cstheme=minorBidi: empty a:cs → theme Arab font (bidi ar-SA)
    assert rp.font_ea == "Calibri"  # eastAsiaTheme=minorHAnsi → minor latin


def test_a019_hello_keeps_explicit_serif_face() -> None:
    doc = read_docx(DOCX / "libreoffice__A019_min.docx")
    para, run = _first_text_run(doc, "Hello")
    assert resolve_r_props(doc, para, run).font == "Times New Roman"


# --- bundled fonts ---------------------------------------------------------------------------


def test_ofl_license_present() -> None:
    assert (FONTS_DIR / "OFL.txt").is_file()
    assert "SIL Open Font License" in (FONTS_DIR / "OFL.txt").read_text(encoding="utf-8")


def test_bundled_fonts_registered(qapp) -> None:
    register_bundled_fonts()
    register_bundled_fonts()  # idempotent
    families = QFontDatabase.families()
    assert "Carlito" in families
    assert "Caladea" in families
    styles = QFontDatabase.styles("Carlito")
    assert {"Regular", "Bold", "Italic", "Bold Italic"} <= set(styles)


def test_office_faces_map_to_metric_compatible_substitutes(qapp) -> None:
    register_bundled_fonts()
    families = set(QFontDatabase.families())
    for office, sub in (("Calibri", "Carlito"), ("Cambria", "Caladea")):
        resolved = QFontInfo(QFont(office)).family()
        if office in families:
            assert resolved == office
        else:
            assert resolved == sub, f"{office} drew as {resolved}"


# --- layout uses the drawn face's metrics ---------------------------------------------------


def test_widths_follow_the_substituted_face(qapp) -> None:
    from PySide6.QtGui import QFontMetricsF

    from atboffice.modules.writer.layout.portions import measure_text_width

    register_bundled_fonts()
    f = QFont("Carlito")
    f.setPixelSize(1000)
    expected = QFontMetricsF(f).horizontalAdvance("m") * 11 / 1000
    assert measure_text_width("m", 11, "Calibri") == pytest.approx(expected, rel=0.02)
    assert measure_text_width("\t", 11, "Calibri") == 0.0
    # Faces without a bundled stand-in keep the machine-independent estimates.
    assert measure_text_width("m", 10, "Times New Roman") == pytest.approx(8.5)


def test_tdf43100_two_row_paragraphs_take_two_lines(qapp) -> None:
    """Acceptance 4: Carlito widths + spaces hanging over the margin → 2 lines, as in Word."""
    from atboffice.modules.writer.layout.pagination import paginate_document

    register_bundled_fonts()
    doc = read_docx(DOCX / "libreoffice__tdf43100_tdf120715_cursorOnSpacesOverMargin.docx")
    page = paginate_document(doc).pages[0]
    frags = [fr for r in page.regions for c in r.columns for fr in c.fragments]
    two_rows = [
        fr
        for fr in frags
        if fr.paragraph is not None
        and "".join(getattr(r, "text", "") or "" for r in fr.paragraph.runs).startswith("2rows")
    ]
    assert len(two_rows) == 4
    for fr in two_rows:
        assert len(fr.lines) == 2
        assert "".join(getattr(p, "text", "") or "" for p in fr.lines[1].portions).startswith(
            "mollis"
        )


def test_explicit_times_new_roman_survives_save(tmp_path) -> None:
    from atboffice.modules.writer.io.docx_writer import write_docx

    doc = read_docx(DOCX / "libreoffice__A019_min.docx")
    para, run = _first_text_run(doc, "Hello")
    doc.styles[para.p_pr.style or "Normal"].r_pr.font = "Arial"
    out = tmp_path / "a019.docx"
    write_docx(doc, out)
    again = read_docx(out)
    para2, run2 = _first_text_run(again, "Hello")
    assert run2.r_pr.font_explicit
    assert resolve_r_props(again, para2, run2).font == "Times New Roman"
