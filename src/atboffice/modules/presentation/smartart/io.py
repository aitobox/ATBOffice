"""ECMA-376 DrawingML SmartArt (IntelliArt) XML Part Generation."""

from __future__ import annotations

import html
from typing import Any

from atboffice.modules.presentation.smartart.layouts import LAYOUTS, get_layout
from atboffice.modules.presentation.smartart.palettes import color_spec, style_info

NS_DGM = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_DSP = "http://schemas.microsoft.com/office/drawing/2008/diagram"
HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
URN = "urn:vibeoffice.work/diagram/"


def fnv(s: str, seed: int) -> str:
    """32-bit FNV-1a hash algorithm returning 8-hex string."""
    h = seed & 0xFFFFFFFF
    for ch in s:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return f"{h:08x}"


def make_guid(key: str) -> str:
    """Generate deterministic UUID-like GUID for given key string."""
    x = fnv(key, 2166136261) + fnv(key, 0x9E3779B9) + fnv(key, 0x85EBCA6B) + fnv(key, 0xC2B2AE35)
    fourth_nibble = "89AB"[int(x[16], 16) % 4]
    return f"{{{x[0:8]}-{x[8:12]}-4{x[13:16]}-{fourth_nibble}{x[17:20]}-{x[20:32]}}}".upper()


def data_xml(
    sa: dict[str, Any],
    key: str = "diag",
    drawing_rel_id: str | None = None,
    fmt: Any = None,
    ctx: Any = None,
) -> str:
    """Generate dgm:dataModel XML document representing SmartArt data hierarchy."""
    layout_id = sa.get("layout", "process")
    style_id = sa.get("style", "moderate")
    colors_id = sa.get("colors", "ocean")
    doc_id = make_guid(f"{key}:doc")
    lo_id = f"{URN}layout/{layout_id}"
    qs_id = f"{URN}style/{style_id}"
    cs_id = f"{URN}colors/{colors_id}"

    pts: list[str] = [
        f'<dgm:pt modelId="{doc_id}" type="doc">'
        f'<dgm:prSet loTypeId="{lo_id}" loCatId="list" qsTypeId="{qs_id}" '
        f'qsCatId="simple" csTypeId="{cs_id}" csCatId="colorful" phldr="1"/>'
        f"<dgm:spPr/><dgm:t><a:bodyPr/><a:lstStyle/><a:p>"
        f'<a:endParaRPr lang="en-US" dirty="0"/></a:p></dgm:t></dgm:pt>'
    ]
    cxns: list[str] = []

    def _walk(item_list: list[dict[str, Any]], parent_id: str) -> None:
        for i, it in enumerate(item_list):
            it_id = str(it.get("id", f"n{i}"))
            m_id = make_guid(f"{key}:{it_id}")
            cx_id = make_guid(f"{key}:{it_id}:cxn")
            par_id = make_guid(f"{key}:{it_id}:par")
            sib_id = make_guid(f"{key}:{it_id}:sib")
            text = html.escape(str(it.get("text", "")))

            t_elem = (
                f'<dgm:t><a:bodyPr/><a:lstStyle/><a:p><a:r>'
                f'<a:rPr lang="en-US" dirty="0"/><a:t>{text}</a:t></a:r></a:p></dgm:t>'
                if text
                else (
                    '<dgm:t><a:bodyPr/><a:lstStyle/><a:p>'
                    '<a:endParaRPr lang="en-US" dirty="0"/></a:p></dgm:t>'
                )
            )

            pts.append(
                f'<dgm:pt modelId="{m_id}"><dgm:prSet phldrT="[Text]"/><dgm:spPr/>{t_elem}</dgm:pt>'
            )
            pts.append(
                f'<dgm:pt modelId="{par_id}" type="parTrans" cxnId="{cx_id}">'
                f"<dgm:prSet/><dgm:spPr/>"
                f'<dgm:t><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-US" dirty="0"/></a:p>'
                f"</dgm:t></dgm:pt>"
            )
            pts.append(
                f'<dgm:pt modelId="{sib_id}" type="sibTrans" cxnId="{cx_id}">'
                f"<dgm:prSet/><dgm:spPr/>"
                f'<dgm:t><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-US" dirty="0"/></a:p>'
                f"</dgm:t></dgm:pt>"
            )

            cxns.append(
                f'<dgm:cxn modelId="{cx_id}" srcId="{parent_id}" destId="{m_id}" '
                f'srcOrd="{i}" destOrd="0" parTransId="{par_id}" sibTransId="{sib_id}"/>'
            )
            if it.get("kids"):
                _walk(it["kids"], m_id)

    raw_items = sa.get("items", [])
    _walk(raw_items, doc_id)

    ext = (
        f'<dgm:extLst><a:ext uri="http://schemas.microsoft.com/office/drawing/2008/diagram">'
        f'<dsp:dataModelExt xmlns:dsp="{NS_DSP}" relId="{drawing_rel_id}" minVer="{NS_DGM}"/>'
        f"</a:ext></dgm:extLst>"
        if drawing_rel_id
        else ""
    )

    return (
        f'{HEAD}<dgm:dataModel xmlns:dgm="{NS_DGM}" xmlns:a="{NS_A}" xmlns:r="{NS_R}">'
        f"<dgm:ptLst>{''.join(pts)}</dgm:ptLst>"
        f"<dgm:cxnLst>{''.join(cxns)}</dgm:cxnLst>"
        f"<dgm:bg/><dgm:whole/>{ext}</dgm:dataModel>"
    )


def layout_xml(layout_id: str, ctx: dict[str, Any] | None = None) -> str:
    """Generate dgm:layoutDef XML definition for specified layout."""
    lay = get_layout(layout_id) or LAYOUTS[0]
    uid = f"{URN}layout/{lay['id']}"
    name = html.escape(str(lay.get("name", "Diagram")))
    desc = html.escape(str(lay.get("desc", "")))
    cat = str(lay.get("cat", "list"))

    sample = (
        '<dgm:sampData useDef="1"><dgm:dataModel>'
        '<dgm:ptLst/><dgm:bg/><dgm:whole/></dgm:dataModel></dgm:sampData>'
        '<dgm:styleData useDef="1"><dgm:dataModel>'
        '<dgm:ptLst/><dgm:bg/><dgm:whole/></dgm:dataModel></dgm:styleData>'
        '<dgm:clrData useDef="1"><dgm:dataModel>'
        '<dgm:ptLst/><dgm:bg/><dgm:whole/></dgm:dataModel></dgm:clrData>'
    )
    body = (
        '<dgm:layoutNode name="diagram"><dgm:varLst><dgm:dir/>'
        '<dgm:resizeHandles val="exact"/></dgm:varLst>'
        '<dgm:alg type="lin"><dgm:param type="linDir" val="fromL"/></dgm:alg>'
        '<dgm:shape xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'r:blip=""><dgm:adjLst/></dgm:shape>'
        "<dgm:presOf/><dgm:constrLst/><dgm:ruleLst/>"
        '<dgm:forEach name="nodes" axis="ch" ptType="node">'
        '<dgm:layoutNode name="node" styleLbl="node1">'
        '<dgm:varLst><dgm:bulletEnabled val="1"/></dgm:varLst>'
        '<dgm:alg type="tx"/><dgm:shape type="roundRect" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'r:blip=""><dgm:adjLst/></dgm:shape>'
        '<dgm:presOf axis="desOrSelf" ptType="node"/><dgm:constrLst/><dgm:ruleLst/>'
        "</dgm:layoutNode></dgm:forEach></dgm:layoutNode>"
    )

    return (
        f'{HEAD}<dgm:layoutDef xmlns:dgm="{NS_DGM}" xmlns:a="{NS_A}" uniqueId="{uid}">'
        f'<dgm:title val="{name}"/><dgm:desc val="{desc}"/>'
        f'<dgm:catLst><dgm:cat type="{cat}" pri="10000"/></dgm:catLst>'
        f"{sample}{body}</dgm:layoutDef>"
    )


def colors_xml(colors_id: str, pal: Any = None, lang: str = "fill") -> str:
    """Generate dgm:colorsDef XML definition."""
    spec = color_spec(colors_id, pal)
    cols = spec["cols"]
    uid = f"{URN}colors/{colors_id}"
    name = html.escape(str(spec.get("name", "Colors")))

    fill_clrs = "".join(f'<a:srgbClr val="{c.lstrip("#").upper()}"/>' for c in cols)
    lbl = (
        f'<dgm:styleLbl name="node1">'
        f'<dgm:fillClrLst meth="{spec["meth"]}">{fill_clrs}</dgm:fillClrLst>'
        f'<dgm:linClrLst meth="repeat"><a:schemeClr val="lt1"/></dgm:linClrLst>'
        f"<dgm:effectClrLst/><dgm:txLinClrLst/>"
        f'<dgm:txFillClrLst meth="repeat"><a:schemeClr val="lt1"/></dgm:txFillClrLst>'
        f"<dgm:txEffectClrLst/>"
        f"</dgm:styleLbl>"
    )

    return (
        f'{HEAD}<dgm:colorsDef xmlns:dgm="{NS_DGM}" xmlns:a="{NS_A}" uniqueId="{uid}">'
        f'<dgm:title val="{name}"/><dgm:desc val=""/>'
        f'<dgm:catLst><dgm:cat type="colorful" pri="10000"/></dgm:catLst>'
        f"{lbl}</dgm:colorsDef>"
    )


def style_xml(style_id: str) -> str:
    """Generate dgm:styleDef XML definition."""
    s_info = style_info(style_id)
    uid = f"{URN}style/{s_info[0]}"
    name = html.escape(str(s_info[1]))

    labels = [
        "node0",
        "node1",
        "lnNode1",
        "vennNode1",
        "alignNode1",
        "alignAcc1",
        "trAlignAcc1",
        "revTx",
        "sibTrans2D1",
        "parChTrans1D2",
        "bgShp",
    ]
    lbl_xmls = []
    for lbl_name in labels:
        lbl_xmls.append(
            f'<dgm:styleLbl name="{lbl_name}">'
            f'<dgm:scene3d><a:camera prst="orthographicFront"/>'
            f'<a:lightRig rig="threePt" dir="t"/></dgm:scene3d>'
            f"<dgm:sp3d/><dgm:txPr/>"
            f'<dgm:style><a:lnRef idx="1"><a:scrgbClr r="0" g="0" b="0"/></a:lnRef>'
            f'<a:fillRef idx="1"><a:scrgbClr r="0" g="0" b="0"/></a:fillRef>'
            f'<a:effectRef idx="0"><a:scrgbClr r="0" g="0" b="0"/></a:effectRef>'
            f'<a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef></dgm:style>'
            f"</dgm:styleLbl>"
        )

    return (
        f'{HEAD}<dgm:styleDef xmlns:dgm="{NS_DGM}" xmlns:a="{NS_A}" uniqueId="{uid}">'
        f'<dgm:title val="{name}"/><dgm:desc val=""/>'
        f'<dgm:catLst><dgm:cat type="simple" pri="10000"/></dgm:catLst>'
        f'<dgm:scene3d><a:camera prst="orthographicFront"/>'
        f'<a:lightRig rig="threePt" dir="t"/></dgm:scene3d>'
        f"{''.join(lbl_xmls)}</dgm:styleDef>"
    )
