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


ENTR_TO_PID = {
    "appear": 1,
    "flyIn": 2,
    "blinds": 3,
    "box": 4,
    "checkerboard": 5,
    "circle": 6,
    "diamond": 8,
    "dissolve": 9,
    "fade": 10,
    "peekIn": 12,
    "plus": 13,
    "randomBars": 14,
    "split": 16,
    "strips": 18,
    "wedge": 20,
    "wheel": 21,
    "wipe": 22,
    "zoom": 23,
    "ascend": 42,
    "descend": 47,
    "spinner": 49,
    "expand": 55,
}

EXIT_TO_PID = {
    "disappear": 1,
    "flyOut": 2,
    "descend": 47,
    "fade": 10,
    "zoom": 23,
}

EMPH_TO_PID = {
    "growShrink": 6,
    "spin": 8,
    "transparency": 9,
    "teeter": 32,
    "blink": 35,
}

DIR_TO_SUB = {
    "b": 1,
    "l": 2,
    "r": 4,
    "t": 8,
    "rb": 5,
    "rt": 9,
    "lb": 6,
    "lt": 10,
}


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
        d = trans.dir or "l"
        child = f'<p:{t_type} dir="{d}"/>'
    elif t_type in ("blinds", "checker", "randomBar", "comb"):
        d = trans.dir or "horz"
        child = f'<p:{t_type} dir="{d}"/>'
    elif t_type == "split":
        o = trans.orient or "horz"
        d = trans.dir or "out"
        child = f'<p:split orient="{o}" dir="{d}"/>'
    elif t_type == "wheel":
        spokes = trans.spokes or 4
        child = f'<p:wheel spokes="{spokes}"/>'
    elif t_type == "zoom":
        d = trans.dir or "in"
        child = f'<p:zoom dir="{d}"/>'
    elif t_type == "cut":
        thru = ' thruBlk="1"' if trans.thruBlk else ""
        child = f"<p:cut{thru}/>"
    elif t_type == "strips":
        d = trans.dir or "ld"
        child = f'<p:strips dir="{d}"/>'
    elif t_type == "random":
        child = "<p:random/>"
    else:
        child = f"<p:{t_type}/>"

    return f"<p:transition {' '.join(attrs)}>{child}</p:transition>"


def timing_to_xml(slide: Slide, resolved_ids: dict[str, str]) -> str:
    """Generate PresentationML <p:timing> node for media playback and animations."""
    media_shapes = [sh for sh in slide.shapes if sh.media_item]
    animations = getattr(slide, "animations", []) or []

    if not media_shapes and not animations:
        return ""

    nodes = []
    c_tn_id = 3

    # 1. Media nodes
    for sh in media_shapes:
        sh_id = resolved_ids.get(sh.id, "2")
        pb = sh.media_item.playback if sh.media_item else None
        vol = int((pb.volume if pb else 0.8) * 100000)
        show_when_stopped = "0" if (pb and pb.hide_while_not_playing) else "1"
        repeat_attr = ' repeatCount="indefinite"' if (pb and pb.loop) else ""

        nodes.append(
            f'<p:cMediaNode vol="{vol}" showWhenStopped="{show_when_stopped}">'
            f'<p:cTn id="{c_tn_id}" fill="hold"{repeat_attr}>'
            f'<p:stCondLst><p:cond delay="0"/></p:stCondLst>'
            f'</p:cTn>'
            f'<p:tgtEl><p:spTgt spid="{sh_id}"/></p:tgtEl>'
            f'</p:cMediaNode>'
        )
        c_tn_id += 1

    # 2. Animation nodes
    for a in animations:
        sh_id = resolved_ids.get(a.sid, a.sid)
        if a.cls == "entr":
            pid = ENTR_TO_PID.get(a.eff, 10)
        elif a.cls == "exit":
            pid = EXIT_TO_PID.get(a.eff, ENTR_TO_PID.get(a.eff, 10))
        elif a.cls == "emph":
            pid = EMPH_TO_PID.get(a.eff, 6)
        else:
            pid = 10

        sub = DIR_TO_SUB.get(a.dir, 0)
        node_type = "clickEffect" if a.start == "click" else ("afterEffect" if a.start == "after" else "withEffect")
        dur = a.dur if a.dur is not None else 500
        delay = a.delay or 0

        para_xml = f'<p:pRg st="{a.para}"/>' if a.para is not None else ""

        nodes.append(
            f'<p:cTn id="{c_tn_id}" presetClass="{a.cls}" presetID="{pid}" presetSubtype="{sub}" nodeType="{node_type}" dur="{dur}">'
            f'<p:stCondLst><p:cond delay="{delay}"/></p:stCondLst>'
            f'<p:tgtEl><p:spTgt spid="{sh_id}">{para_xml}</p:spTgt></p:tgtEl>'
            f'</p:cTn>'
        )
        c_tn_id += 1

    children_xml = "".join(nodes)
    return (
        "<p:timing><p:tnLst><p:par>"
        '<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">'
        "<p:childTnLst>"
        '<p:seq concurrent="1" nextAc="seek">'
        '<p:cTn id="2" dur="indefinite" nodeType="mainSeq">'
        f"<p:childTnLst>{children_xml}</p:childTnLst>"
        "</p:cTn>"
        "</p:seq>"
        "</p:childTnLst>"
        "</p:cTn>"
        "</p:par></p:tnLst></p:timing>"
    )


def slide_to_xml(
    slide: Slide,
    design: DesignTemplate | None = None,
    media_resolver: Callable[[str], str] | None = None,
    lang: str = "en-US",
) -> str:
    """Serialize Slide model into a complete PresentationML <p:sld> XML document."""
    next_id_val = 2
    resolved_ids: dict[str, str] = {}

    def id_resolver(sid: str) -> str:
        nonlocal next_id_val
        if sid in resolved_ids:
            return resolved_ids[sid]
        val = str(next_id_val)
        next_id_val += 1
        resolved_ids[sid] = val
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
    timing_xml = timing_to_xml(slide, resolved_ids)

    attrs = [
        f'xmlns:a="{NS_A}"',
        f'xmlns:r="{NS_R}"',
        f'xmlns:p="{NS_P}"',
    ]
    if slide.hidden:
        attrs.append('show="0"')

    raw_xml = f"<p:sld {' '.join(attrs)}>{c_sld}{clr_map}{trans_xml}{timing_xml}</p:sld>"
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
