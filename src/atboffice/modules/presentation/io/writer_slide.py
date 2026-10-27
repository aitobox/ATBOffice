"""Slide and speaker notes XML serialization for PresentationML."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable

from atboffice.modules.presentation.io.writer_shapes import shape_to_xml
from atboffice.modules.presentation.io.xml_utils import (
    NS_A,
    NS_P,
    NS_R,
    XML_DECL,
    escape_xml,
)
from atboffice.modules.presentation.models.designs import DesignTemplate
from atboffice.modules.presentation.models.slide import Slide, Transition
from atboffice.vfs.order import enforce_schema_order


def transition_to_xml(trans: Transition | None) -> str:
    """Generate transition element (<p:transition>)."""
    if not trans or (trans.type == "none" and trans.click and trans.after is None):
        return ""

    attrs: list[str] = [f'spd="{trans.speed or "fast"}"']
    if not trans.click:
        attrs.append('advClick="0"')
    if trans.after is not None:
        attrs.append(f'advTm="{int(round(trans.after * 1000))}"')

    t_type = trans.type
    child = ""
    if t_type in ("fade", "circle", "diamond", "dissolve", "newsflash", "plus", "wedge"):
        child = f"<p:{t_type}/>"
    elif t_type in ("wipe", "push", "cover", "pull"):
        child = f'<p:{t_type} dir="l"/>'
    elif t_type in ("blinds", "checker", "randomBar", "comb"):
        child = f'<p:{t_type} dir="horz"/>'
    elif t_type == "split":
        child = '<p:split orient="horz" dir="out"/>'
    elif t_type == "wheel":
        child = '<p:wheel spokes="4"/>'
    elif t_type == "zoom":
        child = '<p:zoom dir="in"/>'

    return f"<p:transition {' '.join(attrs)}>{child}</p:transition>"


def slide_to_xml(
    slide: Slide,
    design: DesignTemplate | None = None,
    media_resolver: Callable[[str], str] | None = None,
    lang: str = "en-US",
) -> str:
    """Serialize Slide model into a complete PresentationML <p:sld> XML document."""
    next_id_val = 2

    def id_resolver(sid: str) -> str:
        nonlocal next_id_val
        val = str(next_id_val)
        next_id_val += 1
        return val

    # Root group non-visual container
    grp_root = (
        "<p:nvGrpSpPr>"
        '<p:cNvPr id="1" name=""/>'
        "<p:cNvGrpSpPr/>"
        "<p:nvPr/>"
        "</p:nvGrpSpPr>"
        "<p:grpSpPr>"
        "<a:xfrm>"
        '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/>'
        "</a:xfrm>"
        "</p:grpSpPr>"
    )

    shapes_xml = "".join(
        shape_to_xml(
            sh,
            id_resolver=id_resolver,
            design=design,
            media_resolver=media_resolver,
            lang=lang,
        )
        for sh in slide.shapes
    )

    sp_tree = f"<p:spTree>{grp_root}{shapes_xml}</p:spTree>"
    c_sld = f"<p:cSld>{sp_tree}</p:cSld>"
    clr_map = "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
    trans_xml = transition_to_xml(slide.transition)

    attrs = [
        f'xmlns:a="{NS_A}"',
        f'xmlns:r="{NS_R}"',
        f'xmlns:p="{NS_P}"',
    ]
    if slide.hidden:
        attrs.append('show="0"')

    raw_xml = f"<p:sld {' '.join(attrs)}>{c_sld}{clr_map}{trans_xml}</p:sld>"
    elem = ET.fromstring(raw_xml)
    enforce_schema_order(elem, "slide")

    xml_body = ET.tostring(elem, encoding="unicode")
    return f"{XML_DECL}{xml_body}"


def notes_slide_to_xml(
    notes_text: str,
    lang: str = "en-US",
) -> str:
    """Serialize speaker notes into a PresentationML <p:notes> document."""
    lines = notes_text.split("\n")
    paras: list[str] = []
    for line in lines:
        if line:
            r_pr = f'<a:rPr lang="{lang}" dirty="0"/>'
            t_xml = f"<a:t>{escape_xml(line)}</a:t>"
            paras.append(f"<a:p><a:r>{r_pr}{t_xml}</a:r></a:p>")
        else:
            paras.append(f'<a:p><a:endParaRPr lang="{lang}" dirty="0"/></a:p>')

    paras_xml = "".join(paras) or f'<a:p><a:endParaRPr lang="{lang}"/></a:p>'

    grp_root = (
        "<p:nvGrpSpPr>"
        '<p:cNvPr id="1" name=""/>'
        "<p:cNvGrpSpPr/>"
        "<p:nvPr/>"
        "</p:nvGrpSpPr>"
        "<p:grpSpPr>"
        "<a:xfrm>"
        '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/>'
        "</a:xfrm>"
        "</p:grpSpPr>"
    )

    sld_img_sp = (
        "<p:sp>"
        "<p:nvSpPr>"
        '<p:cNvPr id="2" name="Slide Image Placeholder 1"/>'
        '<p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr>'
        '<p:nvPr><p:ph type="sldImg"/></p:nvPr>'
        "</p:nvSpPr>"
        "<p:spPr/>"
        "</p:sp>"
    )
    notes_sp = (
        "<p:sp>"
        "<p:nvSpPr>"
        '<p:cNvPr id="3" name="Notes Placeholder 2"/>'
        '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        '<p:nvPr><p:ph type="body" idx="1"/></p:nvPr>'
        "</p:nvSpPr>"
        "<p:spPr/>"
        f"<p:txBody><a:bodyPr/><a:lstStyle/>{paras_xml}</p:txBody>"
        "</p:sp>"
    )

    sp_tree = f"<p:spTree>{grp_root}{sld_img_sp}{notes_sp}</p:spTree>"
    c_sld = f"<p:cSld>{sp_tree}</p:cSld>"
    clr_map = "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"

    root_xml = (
        f'<p:notes xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">{c_sld}{clr_map}</p:notes>'
    )
    return f"{XML_DECL}{root_xml}"
