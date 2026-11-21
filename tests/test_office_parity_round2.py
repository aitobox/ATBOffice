"""Regression tests for the 2026-11-21 VibeOffice parity pass (screenshots/atbffice_docs).

Word: docDefaults size fallback, superscript/subscript, paragraph spacing (space after,
Auto spacing, contextual spacing). Excel: column widths and default row height from the
default font. PowerPoint: stored normAutofit, theme chart colours, lProcess SmartArt.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.writer.io.docx_reader import read_docx
from atboffice.modules.writer.layout.portions import (
    AUTO_SPACING_PT,
    ParagraphLayout,
    PortionType,
    decompose_paragraph_to_portions,
    resolved_paragraph_spacing,
    spacing_between,
)
from atboffice.modules.writer.models.document import Paragraph, TextItem
from atboffice.modules.writer.models.properties import (
    RunProperties,
    SpacingProperties,
)
from atboffice.modules.writer.models.styles import merge_r_props, resolve_r_props

DOCS = Path(__file__).parent / "docs"
DOCX = DOCS / "word" / "docx"
XLSX = DOCS / "excel" / "xlsx"
PPTX = DOCS / "powerpoint" / "pptx"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx_bytes(styles_xml: str | None, body_xml: str) -> bytes:
    """A minimal package; styles_xml=None leaves word/styles.xml out."""
    buf = io.BytesIO()
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + (
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/styles" Target="styles.xml"/>'
            if styles_xml is not None
            else ""
        )
        + "</Relationships>"
    )
    ct = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    )
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{W}"><w:body>{body_xml}</w:body></w:document>',
        )
        if styles_xml is not None:
            z.writestr("word/styles.xml", f'<w:styles xmlns:w="{W}">{styles_xml}</w:styles>')
    return buf.getvalue()


def _first_para(doc) -> Paragraph:
    return next(b for b in doc.main.blocks if isinstance(b, Paragraph))


# --- Word: default run size ---------------------------------------------------------


def test_docdefaults_without_size_fall_back_to_10pt() -> None:
    styles = (
        '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial"/></w:rPr>'
        "</w:rPrDefault></w:docDefaults>"
    )
    doc = read_docx(io.BytesIO(_docx_bytes(styles, "<w:p><w:r><w:t>x</w:t></w:r></w:p>")))
    para = _first_para(doc)
    rp = resolve_r_props(doc, para, para.runs[0])
    assert rp.sz == 10.0
    assert rp.font == "Arial"


def test_missing_styles_part_falls_back_to_10pt() -> None:
    doc = read_docx(io.BytesIO(_docx_bytes(None, "<w:p><w:r><w:t>x</w:t></w:r></w:p>")))
    para = _first_para(doc)
    assert resolve_r_props(doc, para, para.runs[0]).sz == 10.0


def test_explicit_12pt_run_overrides_smaller_default() -> None:
    styles = (
        '<w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="20"/></w:rPr>'
        "</w:rPrDefault></w:docDefaults>"
    )
    body = '<w:p><w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>x</w:t></w:r></w:p>'
    doc = read_docx(io.BytesIO(_docx_bytes(styles, body)))
    para = _first_para(doc)
    assert resolve_r_props(doc, para, para.runs[0]).sz == 12.0


def test_size_set_after_construction_is_explicit() -> None:
    rp = RunProperties()
    assert not rp.sz_explicit
    rp.sz = 12.0
    assert rp.sz_explicit
    assert merge_r_props(RunProperties(sz=10.0), rp).sz == 12.0
    assert not RunProperties(sz=12.0).sz_explicit


def test_default_size_survives_save(tmp_path) -> None:
    from atboffice.modules.writer.io.docx_writer import write_docx

    doc = read_docx(DOCX / "libreoffice__tdf105035_framePrB.docx")
    out = tmp_path / "out.docx"
    write_docx(doc, out)
    again = read_docx(out)
    assert again.defaults["r_pr"].sz == 10.0


def test_liberation_serif_has_a_serif_substitute(qapp) -> None:
    from PySide6.QtGui import QFont

    from atboffice.utils.font_registry import register_bundled_fonts

    register_bundled_fonts()
    subs = [s.lower() for s in QFont.substitutes("Liberation Serif")]
    assert subs, "Liberation Serif should map to Times New Roman / Tinos"
    assert any(s in ("times new roman", "tinos", "times") for s in subs)


# --- Word: superscript / subscript ----------------------------------------------------


@pytest.mark.parametrize(("vert", "sign"), [("superscript", 1), ("subscript", -1)])
def test_vert_align_shrinks_and_shifts(vert: str, sign: int) -> None:
    rp = RunProperties(sz=12.0)
    rp.vert = vert
    p = Paragraph()
    p.runs = [TextItem(text="x2", r_pr=rp)]
    portions = [po for po in decompose_paragraph_to_portions(p) if po.type == PortionType.TEXT]
    assert portions
    for po in portions:
        assert po.font_size == pytest.approx(12.0 * 0.65)
        assert po.baseline_shift * sign > 0


def test_baseline_text_is_not_shifted() -> None:
    p = Paragraph()
    p.runs = [TextItem(text="plain", r_pr=RunProperties(sz=12.0))]
    portions = decompose_paragraph_to_portions(p)
    assert all(po.baseline_shift == 0.0 for po in portions)


def test_footnote_mark_is_raised_and_not_shrunk_twice() -> None:
    doc = read_docx(DOCX / "libreoffice__tdf153255.docx")
    para = _first_para(doc)
    portions = decompose_paragraph_to_portions(para, doc)
    marks = [po for po in portions if po.text == "1" and po.baseline_shift > 0]
    assert marks, "footnote reference should be drawn above the baseline"
    assert marks[0].font_size == pytest.approx(max(6.0, 10.0 * 0.65))


# --- Word: paragraph spacing ----------------------------------------------------------


def test_auto_spacing_is_14pt() -> None:
    sp = SpacingProperties(before=5.0, after=5.0, before_auto=True, after_auto=False)
    assert resolved_paragraph_spacing(sp) == (AUTO_SPACING_PT, 5.0)


def test_spacing_between_takes_the_larger_and_honors_contextual() -> None:
    a = ParagraphLayout(space_after=10.0, style_id="List")
    b = ParagraphLayout(space_before=4.0, style_id="List")
    assert spacing_between(a, b) == 10.0
    a.contextual = True
    b.contextual = True
    assert spacing_between(a, b) == 0.0
    b.style_id = "Normal"
    assert spacing_between(a, b) == 10.0


def _body_fragments(doc):
    from atboffice.modules.writer.layout.pagination import paginate_document

    page = paginate_document(doc).pages[0]
    return [fr for r in page.regions for c in r.columns for fr in c.fragments]


def test_space_after_separates_body_paragraphs() -> None:
    styles = (
        '<w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="20"/></w:rPr></w:rPrDefault>'
        "</w:docDefaults>"
    )
    p = '<w:p><w:pPr><w:spacing w:before="0" w:after="400"/></w:pPr><w:r><w:t>{}</w:t></w:r></w:p>'
    doc = read_docx(io.BytesIO(_docx_bytes(styles, p.format("a") + p.format("b"))))
    first, second = [fr for fr in _body_fragments(doc) if fr.paragraph is not None][:2]
    gap = second.top - (first.top + first.height)
    assert gap == pytest.approx(20.0, abs=0.01)


def test_contextual_list_paragraphs_have_no_gap() -> None:
    styles = (
        '<w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="20"/></w:rPr></w:rPrDefault>'
        "</w:docDefaults>"
        '<w:style w:type="paragraph" w:styleId="List"><w:pPr><w:spacing w:after="400"/>'
        "<w:contextualSpacing/></w:pPr></w:style>"
    )
    p = '<w:p><w:pPr><w:pStyle w:val="List"/></w:pPr><w:r><w:t>{}</w:t></w:r></w:p>'
    doc = read_docx(io.BytesIO(_docx_bytes(styles, p.format("a") + p.format("b"))))
    first, second = [fr for fr in _body_fragments(doc) if fr.paragraph is not None][:2]
    assert second.top == pytest.approx(first.top + first.height, abs=0.01)


def test_contextual_spacing_round_trips(tmp_path) -> None:
    from atboffice.modules.writer.io.docx_writer import write_docx
    from atboffice.modules.writer.models.styles import resolve_p_props

    doc = read_docx(DOCX / "poi__60316.docx")
    out = tmp_path / "out.docx"
    write_docx(doc, out)
    styles = zipfile.ZipFile(out).read("word/styles.xml").decode("utf-8")
    assert "contextualSpacing" in styles
    again = read_docx(out)
    paras = [b for b in again.main.blocks if isinstance(b, Paragraph)]
    assert again.styles["ListBullet"].p_pr.contextual is True
    assert any(resolve_p_props(again, p).contextual for p in paras)


def test_tdf132802_list_spacing_matches_auto_spacing() -> None:
    doc = read_docx(DOCX / "libreoffice__tdf132802.docx")
    frags = [fr for fr in _body_fragments(doc) if fr.paragraph is not None]
    first, second = frags[0], frags[1]
    gap = second.top - (first.top + first.height)
    assert gap == pytest.approx(AUTO_SPACING_PT, abs=0.01)


# --- Excel: column widths and default row height ---------------------------------------


def test_excel_units_match_the_original() -> None:
    from atboffice.modules.spreadsheet.models.excel_units import (
        default_col_px,
        excel_mdw,
        font_row_pt,
        px_to_width,
        width_to_px,
    )

    assert excel_mdw("Calibri", 11) == 7
    assert excel_mdw("Arial", 10) == 7
    assert width_to_px(11.6745098039216, 7) == 82
    assert default_col_px(7, None, None) == 64
    assert default_col_px(7, 11.5703125, None) == 81
    for px in (20, 64, 81, 82, 137):
        assert width_to_px(px_to_width(px, 7), 7) == px
    assert font_row_pt("Arial", 10) == 12.75
    assert font_row_pt("Calibri", 11) == 15.0


def test_xlsx_column_width_uses_max_digit_width() -> None:
    from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx

    sh = read_xlsx(XLSX / "libreoffice__cell-value.xlsx")[0]
    assert sh.geometry.col_size(0) == 82
    # No <sheetFormatPr>: rows follow the Arial 10 default font (12.75pt = 17px)
    assert sh.geometry.default_row_height == 17


def test_xlsx_default_col_width_is_applied() -> None:
    from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx

    sh = read_xlsx(XLSX / "libreoffice__Pivot2_Row.xlsx")[0]
    assert sh.geometry.default_col_width == 81


def test_xlsx_column_width_round_trips(tmp_path) -> None:
    from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
    from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx

    wb = read_xlsx(XLSX / "libreoffice__cell-value.xlsx")
    out = tmp_path / "out.xlsx"
    write_xlsx(wb, out)
    assert read_xlsx(out)[0].geometry.col_size(0) == 82


# --- PowerPoint -----------------------------------------------------------------------


def test_stored_norm_autofit_renders_at_100_percent() -> None:
    from atboffice.modules.presentation.io.pptx_reader import read_pptx

    pres = read_pptx(PPTX / "libreoffice__TextFittingComparisonWithMSO_3.pptx")
    bodies = [s.text for s in pres.slides[0].shapes if s.text and s.text.autofit == "norm"]
    assert bodies
    plain = [t for t in bodies if t.font_scale == pytest.approx(1.0)]
    assert plain and all(t.has_explicit_font_scale for t in plain)


def test_chart_series_use_theme_accents_and_auto_title() -> None:
    from atboffice.modules.presentation.chart.io import parse_chart_xml

    xml = zipfile.ZipFile(PPTX / "libreoffice__tdf112089.pptx").read("ppt/charts/chart1.xml")
    accents = ["#5B9BD5", "#ED7D31", "#A5A5A5", "#FFC000", "#4472C4", "#70AD47"]
    chart = parse_chart_xml(xml, theme_accents=accents, auto_title=True)
    assert [s.color for s in chart.series] == accents[:3]
    assert chart.title == "Chart Title"


def test_chart_without_theme_keeps_previous_behaviour() -> None:
    from atboffice.modules.presentation.chart.io import parse_chart_xml

    xml = zipfile.ZipFile(PPTX / "libreoffice__tdf112089.pptx").read("ppt/charts/chart1.xml")
    chart = parse_chart_xml(xml)
    assert all(s.color == "" for s in chart.series)
    assert chart.title == ""


def test_pptx_chart_reads_slide_theme() -> None:
    from atboffice.modules.presentation.io.pptx_reader import read_pptx

    pres = read_pptx(PPTX / "libreoffice__tdf112089.pptx")
    charts = [s for s in pres.slides[0].shapes if getattr(s, "chart", None)]
    assert charts
    colors = [
        str(se.get("color") if isinstance(se, dict) else se.color).upper()
        for se in (
            charts[0].chart.get("series")
            if isinstance(charts[0].chart, dict)
            else charts[0].chart.series
        )
    ]
    assert colors[:3] == ["#5B9BD5", "#ED7D31", "#A5A5A5"]


def test_lprocess_smartart_without_children_is_one_container() -> None:
    from atboffice.modules.presentation.smartart.engine import SmartArtEngine
    from atboffice.modules.presentation.smartart.layouts import LAYOUTS, get_layout

    urn = "urn:microsoft.com/office/officeart/2005/8/layout/lProcess2"
    assert get_layout(urn)["id"] == "groupedList"
    assert all(lay["id"] != "groupedList" for lay in LAYOUTS), "not offered in the gallery"
    box = {"x": 0, "y": 0, "w": 400, "h": 300}
    res = SmartArtEngine().layout("lProcess2", [{"text": "test"}], box)
    assert res["layout"] == "groupedList"
    assert len(res["shapes"]) == 1
    assert res["shapes"][0]["text"]["anchor"] == "t"


def test_lprocess_smartart_children_become_boxes() -> None:
    from atboffice.modules.presentation.smartart.engine import SmartArtEngine

    items = [{"text": "A", "kids": [{"text": "a1"}, {"text": "a2"}]}, {"text": "B"}]
    shapes = SmartArtEngine().layout("lProcess2", items, {"x": 0, "y": 0, "w": 400, "h": 300})[
        "shapes"
    ]
    assert len(shapes) == 4
    container = shapes[0]
    for kid in shapes[1:3]:
        assert container["x"] < kid["x"] < container["x"] + container["w"]
        assert container["y"] < kid["y"] < container["y"] + container["h"]


# --- Round 3: lists, tabs, complex script, PowerPoint theme fonts/colours -----------------


def _first_para_with(doc, prefix: str) -> Paragraph:
    return next(
        b
        for b in doc.main.blocks
        if isinstance(b, Paragraph)
        and "".join(getattr(r, "text", "") or "" for r in b.runs).startswith(prefix)
    )


def test_list_level_indent_beats_style_and_direct_chars_zero_wins() -> None:
    from atboffice.modules.writer.models.styles import resolve_p_props

    doc = read_docx(DOCX / "openxml-sdk__bullet-complex.docx")
    pp = resolve_p_props(doc, _first_para_with(doc, "Without access"))
    # level: left 420 hanging 420; style: firstLine 420; direct: firstLineChars="0"
    assert pp.ind.left == pytest.approx(21.0)
    assert pp.ind.first_line == pytest.approx(0.0)


def test_list_number_takes_paragraph_mark_formatting() -> None:
    doc = read_docx(DOCX / "libreoffice__tdf125881.docx")
    para = next(b for b in doc.main.blocks if isinstance(b, Paragraph))
    label = decompose_paragraph_to_portions(para, doc)[0]
    assert label.text == "I."
    assert label.bold is True
    assert label.font_family == "Times New Roman"


def test_tab_after_bullet_goes_to_default_stop_from_margin() -> None:
    from atboffice.modules.writer.layout.portions import layout_paragraph

    doc = read_docx(DOCX / "openxml-sdk__bullet-complex.docx")
    layout = layout_paragraph(_first_para_with(doc, "Without access"), 432.0, doc=doc)
    line = layout.lines[0]
    x = line.indent_left
    for po in line.portions:
        if po.type == PortionType.TEXT and po.text.startswith("Without"):
            break
        x += po.width
    # bullet at 21pt; the next default stop (defaultTabStop 720 = 36pt) from the margin
    assert x == pytest.approx(36.0, abs=0.5)


def test_default_stops_follow_last_custom_stop() -> None:
    from atboffice.modules.writer.layout.portions import find_next_tab_stop
    from atboffice.modules.writer.models.properties import TabStop

    tabs = [TabStop(pos=50.0, align="left")]
    assert find_next_tab_stop(10.0, 0.0, tabs, 36.0)[0] == pytest.approx(50.0)
    assert find_next_tab_stop(55.0, 0.0, tabs, 36.0)[0] == pytest.approx(72.0)


def test_wingdings_b2_is_a_four_pointed_star() -> None:
    from atboffice.modules.writer.layout.portions import map_symbol_char

    assert map_symbol_char("", "Wingdings") == "✧"


def test_explicit_zero_indent_round_trips(tmp_path) -> None:
    from atboffice.modules.writer.io.docx_writer import write_docx
    from atboffice.modules.writer.models.styles import resolve_p_props

    doc = read_docx(DOCX / "openxml-sdk__bullet-complex.docx")
    out = tmp_path / "out.docx"
    write_docx(doc, out)
    again = read_docx(out)
    pp = resolve_p_props(again, _first_para_with(again, "Without access"))
    assert pp.ind.first_line == pytest.approx(0.0)
    assert pp.ind.left == pytest.approx(21.0)


def test_rtl_runs_use_complex_script_font() -> None:
    doc = read_docx(DOCX / "openxml-sdk__Comment066.docx")
    para = next(b for b in doc.main.blocks if isinstance(b, Paragraph))
    first = next(po for po in decompose_paragraph_to_portions(para, doc) if po.text.strip())
    assert first.font_family == "Times New Roman"  # w:cs, not the Cambria Latin face


def test_page_break_split_keeps_paragraph_mark() -> None:
    from atboffice.modules.writer.layout.pagination import _split_paragraph_by_hard_breaks

    p = Paragraph(runs=[TextItem(text="x", r_pr=RunProperties())], r_pr=RunProperties(b=True))
    ((sub, _),) = _split_paragraph_by_hard_breaks(p)
    assert sub.r_pr.b is True


def test_pptx_theme_font_references_resolve() -> None:
    from atboffice.modules.presentation.io.pptx_reader import read_pptx

    pres = read_pptx(PPTX / "openxml-sdk__Text_withShadow_200chars.pptx")
    fonts = {
        r.font for s in pres.slides[0].shapes if s.text for p in s.text.paragraphs for r in p.runs
    }
    assert fonts == {"Calibri"}


def test_pptx_scheme_color_keeps_its_tint() -> None:
    from atboffice.modules.presentation.io.pptx_reader import read_pptx
    from atboffice.modules.presentation.io.xml_utils import color_to_xml
    from atboffice.modules.presentation.models.designs import resolve_color

    pres = read_pptx(PPTX / "openxml-sdk__sldsz-Slide Size-type-b4iso.pptx")
    sub = next(s for s in pres.slides[0].shapes if s.name.startswith("Subtitle"))
    color = sub.text.prompt_run.color
    assert color == "tx1|tint=75000"
    hex_c = resolve_color(color)
    assert hex_c.upper() not in ("#000000", "")  # lighter than plain tx1
    xml = color_to_xml(color)
    assert xml == '<a:schemeClr val="tx1"><a:tint val="75000"/></a:schemeClr>'


def test_subtitle_inherits_layout_lststyle_not_sample_paragraph() -> None:
    from atboffice.modules.presentation.io.pptx_reader import read_pptx

    pres = read_pptx(PPTX / "libreoffice__tdf143129.pptx")
    sub = next(s for s in pres.slides[0].shapes if s.name.startswith("Subtitle"))
    props = sub.text.paragraphs[0].props
    assert props["algn"] == "l"  # the layout sample's algn="ctr" stays on the layout
    assert props["bu"].get("ch") == "•"
