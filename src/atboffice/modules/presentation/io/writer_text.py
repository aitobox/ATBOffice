"""Text and Typography XML serialization for PresentationML."""

from __future__ import annotations

from typing import Any

from atboffice.modules.presentation.io.xml_utils import (
    color_to_xml,
    escape_xml,
    pt_to_emu,
)
from atboffice.modules.presentation.models.designs import DesignTemplate
from atboffice.modules.presentation.models.text import (
    BulletInfo,
    Paragraph,
    TextBody,
    TextRun,
)


def run_props_to_xml(
    run: TextRun | dict[str, Any],
    tag: str = "a:rPr",
    design: DesignTemplate | None = None,
    lang: str = "en-US",
) -> str:
    """Generate run properties XML element (<a:rPr>, <a:endParaRPr>, etc.)."""
    attrs: list[str] = [f'lang="{lang}"', 'dirty="0"']

    sz = run.size if isinstance(run, TextRun) else run.get("sz")
    if sz:
        attrs.append(f'sz="{int(round(float(sz) * 100))}"')

    bold = run.bold if isinstance(run, TextRun) else run.get("b", False)
    if bold:
        attrs.append('b="1"')

    italic = run.italic if isinstance(run, TextRun) else run.get("i", False)
    if italic:
        attrs.append('i="1"')

    underline = run.underline if isinstance(run, TextRun) else run.get("u", False)
    if underline:
        attrs.append('u="sng"')

    strike = run.strike if isinstance(run, TextRun) else run.get("strike", False)
    if strike:
        attrs.append('strike="sngStrike"')

    baseline = run.baseline if isinstance(run, TextRun) else run.get("base", 0)
    if baseline:
        attrs.append(f'baseline="{int(round(float(baseline)))}"')

    inner_xml = ""
    color = run.color if isinstance(run, TextRun) else run.get("color")
    if color:
        c_xml = color_to_xml(color, design=design)
        inner_xml += f"<a:solidFill>{c_xml}</a:solidFill>"

    font = run.font if isinstance(run, TextRun) else run.get("font")
    if font:
        typeface = escape_xml(font)
        inner_xml += f'<a:latin typeface="{typeface}"/>'
        inner_xml += f'<a:cs typeface="{typeface}"/>'

    font_ea = run.font_ea if isinstance(run, TextRun) else run.get("fontEA")
    if font_ea:
        inner_xml += f'<a:ea typeface="{escape_xml(font_ea)}"/>'

    attr_str = f" {' '.join(attrs)}" if attrs else ""
    if inner_xml:
        return f"<{tag}{attr_str}>{inner_xml}</{tag}>"
    return f"<{tag}{attr_str}/>"


def bullet_to_xml(
    bullet: BulletInfo | dict[str, Any] | None,
    design: DesignTemplate | None = None,
) -> str:
    """Generate bullet formatting XML for paragraph properties."""
    if not bullet:
        return ""
    b_type = bullet.type if isinstance(bullet, BulletInfo) else bullet.get("t", "none")
    b_char = bullet.char if isinstance(bullet, BulletInfo) else bullet.get("ch", "•")
    b_clr = bullet.color if isinstance(bullet, BulletInfo) else bullet.get("c")

    xml = ""
    if b_clr:
        c_elem = color_to_xml(b_clr, design=design)
        xml += f"<a:buClr>{c_elem}</a:buClr>"

    if b_type == "none":
        return xml + "<a:buNone/>"
    if b_type == "char":
        return xml + f'<a:buFont typeface="Arial"/><a:buChar char="{escape_xml(b_char)}"/>'
    if b_type == "auto":
        return xml + '<a:buAutoNum type="arabicPeriod"/>'
    return xml


def paragraph_to_xml(
    para: Paragraph,
    design: DesignTemplate | None = None,
    lang: str = "en-US",
) -> str:
    """Generate paragraph XML (<a:p>) with runs and end-run properties."""
    p_attrs: list[str] = []
    if para.level > 0:
        p_attrs.append(f'lvl="{para.level}"')

    props = para.props or {}
    algn = props.get("algn", "l")
    if algn and algn != "l":
        p_attrs.append(f'algn="{algn}"')
    if "marL" in props:
        p_attrs.append(f'marL="{pt_to_emu(props["marL"])}"')
    if "indent" in props:
        p_attrs.append(f'indent="{pt_to_emu(props["indent"])}"')

    p_attr_str = f" {' '.join(p_attrs)}" if p_attrs else ""
    bu_xml = bullet_to_xml(props.get("bu"), design=design)

    p_pr_xml = ""
    if p_attr_str or bu_xml:
        p_pr_xml = f"<a:pPr{p_attr_str}>{bu_xml}</a:pPr>"

    runs_xml: list[str] = []
    for r in para.runs:
        if r.field:
            fld_id = "{8B94F3C4-F6DF-4E38-A3BA-50E06A911CD2}"
            fld_type = escape_xml(r.field)
            r_pr = run_props_to_xml(r, tag="a:rPr", design=design, lang=lang)
            runs_xml.append(
                f'<a:fld id="{fld_id}" type="{fld_type}">'
                f"{r_pr}<a:t>{escape_xml(r.text)}</a:t></a:fld>"
            )
            continue

        parts = r.text.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                r_pr = run_props_to_xml(r, tag="a:rPr", design=design, lang=lang)
                runs_xml.append(f"<a:br>{r_pr}</a:br>")
            if part:
                r_pr = run_props_to_xml(r, tag="a:rPr", design=design, lang=lang)
                runs_xml.append(f"<a:r>{r_pr}<a:t>{escape_xml(part)}</a:t></a:r>")

    end_r_pr = run_props_to_xml(
        para.end_props or (para.runs[-1] if para.runs else {}),
        tag="a:endParaRPr",
        design=design,
        lang=lang,
    )
    content_xml = "".join(runs_xml) + end_r_pr
    return f"<a:p>{p_pr_xml}{content_xml}</a:p>"


def body_properties_to_xml(text_body: TextBody) -> str:
    """Generate text body properties XML (<a:bodyPr>)."""
    ins = text_body.insets
    l_ins = pt_to_emu(ins[0], default=91440)
    t_ins = pt_to_emu(ins[1], default=45720)
    r_ins = pt_to_emu(ins[2], default=91440)
    b_ins = pt_to_emu(ins[3], default=45720)

    wrap_str = "square" if text_body.wrap else "none"
    anchor_str = text_body.anchor or "t"

    attrs = [
        f'wrap="{wrap_str}"',
        f'lIns="{l_ins}"',
        f'tIns="{t_ins}"',
        f'rIns="{r_ins}"',
        f'bIns="{b_ins}"',
        f'anchor="{anchor_str}"',
        'rtlCol="0"',
    ]
    if getattr(text_body, "anchor_ctr", False):
        attrs.append('anchorCtr="1"')
    cols = getattr(text_body, "columns", 1)
    if cols > 1:
        attrs.append(f'numCol="{cols}"')
        attrs.append(f'spcCol="{pt_to_emu(getattr(text_body, "col_gap", 0))}"')

    inner = ""
    if text_body.autofit == "shape":
        inner = "<a:spAutoFit/>"
    elif text_body.autofit == "norm":
        inner = "<a:normAutofit/>"

    return f"<a:bodyPr {' '.join(attrs)}>{inner}</a:bodyPr>"


def text_body_to_xml(
    text_body: TextBody | None,
    design: DesignTemplate | None = None,
    tag: str = "p:txBody",
    lang: str = "en-US",
) -> str:
    """Serialize complete TextBody model to XML element (<p:txBody>)."""
    if not text_body:
        return ""
    body_pr = body_properties_to_xml(text_body)
    lst_style = "<a:lstStyle/>"
    paras = [
        paragraph_to_xml(p, design=design, lang=lang)
        for p in (text_body.paragraphs or [Paragraph()])
    ]
    return f"<{tag}>{body_pr}{lst_style}{''.join(paras)}</{tag}>"
