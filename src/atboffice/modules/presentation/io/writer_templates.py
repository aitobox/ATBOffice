"""Theme, master, layout, and document properties templates for PresentationML."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from atboffice.modules.presentation.io.xml_utils import (
    ATB_HANDOUT_EXT_URI,
    NS_A,
    NS_ATB,
    NS_P,
    NS_R,
    XML_DECL,
    escape_xml,
)
from atboffice.modules.presentation.models.designs import DesignTemplate
from atboffice.modules.presentation.models.presentation import (
    HandoutMasterSettings,
    NotesMasterSettings,
)
from atboffice.vfs import etree as ET
from atboffice.vfs.order import enforce_schema_order

CLR_MAP = (
    '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" '
    'accent1="accent1" accent2="accent2" accent3="accent3" '
    'accent4="accent4" accent5="accent6" accent6="accent6" '
    'hlink="hlink" folHlink="folHlink"/>'
)


def build_theme_xml(design: DesignTemplate, name: str = "Office Theme") -> str:
    """Generate ECMA-376 DrawingML theme document (<a:theme>)."""
    c = design.colors
    keys = [
        "dk1",
        "lt1",
        "dk2",
        "lt2",
        "accent1",
        "accent2",
        "accent3",
        "accent4",
        "accent5",
        "accent6",
        "hlink",
        "folHlink",
    ]
    clr_items = []
    for k in keys:
        hex_val = getattr(c, k, "#000000").replace("#", "").upper()
        if len(hex_val) != 6:
            hex_val = "000000"
        clr_items.append(f'<a:{k}><a:srgbClr val="{hex_val}"/></a:{k}>')
    clr_scheme = f'<a:clrScheme name="{escape_xml(name)}">{"".join(clr_items)}</a:clrScheme>'

    major = escape_xml(design.fonts.get("major", "Arial"))
    minor = escape_xml(design.fonts.get("minor", "Arial"))
    font_scheme = (
        f'<a:fontScheme name="{escape_xml(name)}">'
        f'<a:majorFont><a:latin typeface="{major}"/>'
        '<a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
        f'<a:minorFont><a:latin typeface="{minor}"/>'
        '<a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
        "</a:fontScheme>"
    )

    fmt_scheme = (
        '<a:fmtScheme name="Office">'
        "<a:fillStyleLst>"
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:gradFill rotWithShape="1">'
        '<a:gsLst><a:gs pos="0"><a:schemeClr val="phClr"/></a:gs>'
        '<a:gs pos="100000"><a:schemeClr val="phClr"/></a:gs></a:gsLst>'
        '<a:lin ang="5400000" scaled="0"/></a:gradFill>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        "</a:fillStyleLst>"
        "<a:lnStyleLst>"
        '<a:ln w="9525" cap="flat" cmpd="sng" algn="ctr">'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>'
        '<a:ln w="25400" cap="flat" cmpd="sng" algn="ctr">'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>'
        '<a:ln w="38100" cap="flat" cmpd="sng" algn="ctr">'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>'
        "</a:lnStyleLst>"
        "<a:effectStyleLst>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "<a:effectStyle><a:effectLst/></a:effectStyle>"
        "</a:effectStyleLst>"
        "<a:bgFillStyleLst>"
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        "</a:bgFillStyleLst>"
        "</a:fmtScheme>"
    )

    root_xml = (
        f'<a:theme xmlns:a="{NS_A}" name="{escape_xml(name)}">'
        f"<a:themeElements>{clr_scheme}{font_scheme}{fmt_scheme}</a:themeElements>"
        "<a:objectDefaults/><a:extraClrSchemeLst/>"
        "</a:theme>"
    )
    return f"{XML_DECL}{root_xml}"


def build_slide_master_xml(
    design: DesignTemplate,
    layout_entries: list[tuple[int, str]],  # (layout_id, rel_id)
) -> str:
    """Generate PresentationML Slide Master document (<p:sldMaster>)."""
    lids = "".join(f'<p:sldLayoutId id="{lid}" r:id="{rid}"/>' for lid, rid in layout_entries)
    layout_lst = f"<p:sldLayoutIdLst>{lids}</p:sldLayoutIdLst>"

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
    title_ph = (
        "<p:sp>"
        "<p:nvSpPr>"
        '<p:cNvPr id="2" name="Title Placeholder 1"/>'
        '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        '<p:nvPr><p:ph type="title"/></p:nvPr>'
        "</p:nvSpPr>"
        "<p:spPr>"
        '<a:xfrm><a:off x="685800" y="457200"/><a:ext cx="7772400" cy="1143000"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        "</p:spPr>"
        "<p:txBody><a:bodyPr/><a:lstStyle/>"
        '<a:p><a:r><a:rPr lang="en-US"/><a:t>Master Title Style</a:t></a:r></a:p>'
        "</p:txBody>"
        "</p:sp>"
    )
    body_ph = (
        "<p:sp>"
        "<p:nvSpPr>"
        '<p:cNvPr id="3" name="Text Placeholder 2"/>'
        '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        '<p:nvPr><p:ph type="body" idx="1"/></p:nvPr>'
        "</p:nvSpPr>"
        "<p:spPr>"
        '<a:xfrm><a:off x="685800" y="1828800"/><a:ext cx="7772400" cy="4572000"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        "</p:spPr>"
        "<p:txBody><a:bodyPr/><a:lstStyle/>"
        '<a:p><a:r><a:rPr lang="en-US"/><a:t>Master Text Styles</a:t></a:r></a:p>'
        "</p:txBody>"
        "</p:sp>"
    )

    tx_styles = (
        "<p:txStyles>"
        '<p:titleStyle><a:lvl1pPr algn="ctr"><a:defRPr sz="4400" b="1"/></a:lvl1pPr></p:titleStyle>'
        '<p:bodyStyle><a:lvl1pPr algn="l"><a:defRPr sz="3200"/></a:lvl1pPr></p:bodyStyle>'
        '<p:otherStyle><a:lvl1pPr algn="l"><a:defRPr sz="1800"/></a:lvl1pPr></p:otherStyle>'
        "</p:txStyles>"
    )

    root_xml = (
        f'<p:sldMaster xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
        f"<p:cSld><p:spTree>{grp_root}{title_ph}{body_ph}</p:spTree></p:cSld>"
        f"{CLR_MAP}"
        f"{layout_lst}"
        f"{tx_styles}"
        "</p:sldMaster>"
    )
    return f"{XML_DECL}{root_xml}"


def build_slide_layout_xml(layout_type: str = "title") -> str:
    """Generate PresentationML Slide Layout document (<p:sldLayout>)."""
    ox_type = "title" if layout_type == "title" else "blank" if layout_type == "blank" else "obj"
    name = (
        "Title Slide"
        if layout_type == "title"
        else "Blank"
        if layout_type == "blank"
        else "Title and Content"
    )

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

    phs = ""
    if layout_type != "blank":
        phs = (
            "<p:sp>"
            "<p:nvSpPr>"
            '<p:cNvPr id="2" name="Title 1"/>'
            '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
            '<p:nvPr><p:ph type="title"/></p:nvPr>'
            "</p:nvSpPr>"
            "<p:spPr/>"
            "<p:txBody><a:bodyPr/><a:lstStyle/>"
            '<a:p><a:r><a:rPr lang="en-US"/><a:t>Click to add title</a:t></a:r></a:p>'
            "</p:txBody>"
            "</p:sp>"
        )

    root_xml = (
        f'<p:sldLayout xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}" '
        f'type="{ox_type}" preserve="1">'
        f'<p:cSld name="{escape_xml(name)}"><p:spTree>{grp_root}{phs}</p:spTree></p:cSld>'
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sldLayout>"
    )
    return f"{XML_DECL}{root_xml}"


def _master_grp_root() -> str:
    return (
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


def _master_hf_sp_xml(
    sp_id: int,
    name: str,
    ph_type: str,
    idx: int,
    x: int,
    y: int,
    cx: int,
    cy: int,
    text: str = "",
    align: str = "l",
    anchor_b: bool = False,
) -> str:
    anchor_attr = ' anchor="b"' if anchor_b else ""
    if ph_type == "sldNum":
        p_inner = (
            f'<a:fld id="{{{uuid.uuid4()}}}" type="slidenum">'
            '<a:rPr lang="en-US" smtClean="0"/><a:t>‹Nº›</a:t></a:fld>'
            '<a:endParaRPr lang="en-US"/>'
        )
    elif text:
        p_inner = f'<a:r><a:rPr lang="en-US"/><a:t>{escape_xml(text)}</a:t></a:r>'
    else:
        p_inner = '<a:endParaRPr lang="en-US"/>'
    idx_attr = f' idx="{idx}"' if idx > 0 else ""
    return (
        "<p:sp>"
        "<p:nvSpPr>"
        f'<p:cNvPr id="{sp_id}" name="{escape_xml(name)}"/>'
        '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        f'<p:nvPr><p:ph type="{ph_type}" sz="quarter"{idx_attr}/></p:nvPr>'
        "</p:nvSpPr>"
        "<p:spPr>"
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        "</p:spPr>"
        "<p:txBody>"
        '<a:bodyPr vert="horz" lIns="91440" tIns="45720" rIns="91440" '
        f'bIns="45720" rtlCol="0"{anchor_attr}/>'
        f'<a:lstStyle><a:lvl1pPr algn="{align}"><a:defRPr sz="1200"/></a:lvl1pPr></a:lstStyle>'
        f"<a:p>{p_inner}</a:p>"
        "</p:txBody>"
        "</p:sp>"
    )


_MASTER_PH_SPECS: dict[str, tuple[int, str, int, int, int, int, int, str, bool]] = {
    "hdr": (2, "Header Placeholder 1", 0, 0, 0, 2971800, 458788, "l", False),
    "dt": (3, "Date Placeholder 2", 1, 3884613, 0, 2971800, 458788, "r", False),
    "ftr": (6, "Footer Placeholder 5", 4, 0, 8685213, 2971800, 458787, "l", True),
    "sldNum": (7, "Slide Number Placeholder 6", 5, 3884613, 8685213, 2971800, 458787, "r", True),
}


def build_handout_master_xml(settings: HandoutMasterSettings | None = None) -> str:
    """Generate PresentationML Handout Master document (<p:handoutMaster>)."""
    hm = settings or HandoutMasterSettings()
    parts: list[str] = [_master_grp_root()]
    checks = [
        ("hdr", hm.show_header, hm.header_text),
        ("dt", hm.show_date, hm.date_text),
        ("ftr", hm.show_footer, hm.footer_text),
        ("sldNum", hm.show_page_number, ""),
    ]
    for ph_type, enabled, text in checks:
        if enabled:
            sp_id, name, idx, x, y, cx, cy, align, anchor_b = _MASTER_PH_SPECS[ph_type]
            parts.append(
                _master_hf_sp_xml(sp_id, name, ph_type, idx, x, y, cx, cy, text, align, anchor_b)
            )
    ext_xml = (
        "<p:extLst>"
        f'<p:ext uri="{ATB_HANDOUT_EXT_URI}">'
        f'<atb:handoutPr xmlns:atb="{NS_ATB}" slidesPerPage="{hm.slides_per_page}" '
        f'orientation="{escape_xml(hm.orientation)}"/>'
        "</p:ext>"
        "</p:extLst>"
    )
    root_xml = (
        f'<p:handoutMaster xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
        f"<p:cSld><p:spTree>{''.join(parts)}</p:spTree></p:cSld>"
        f"{CLR_MAP}"
        f"{ext_xml}"
        "</p:handoutMaster>"
    )
    return f"{XML_DECL}{root_xml}"


def build_notes_master_xml(settings: NotesMasterSettings | None = None) -> str:
    """Generate PresentationML Notes Master document (<p:notesMaster>)."""
    nm = settings or NotesMasterSettings()
    parts: list[str] = [_master_grp_root()]
    if nm.show_header:
        sp_id, name, idx, x, y, cx, cy, align, anchor_b = _MASTER_PH_SPECS["hdr"]
        parts.append(
            _master_hf_sp_xml(
                sp_id, name, "hdr", idx, x, y, cx, cy, nm.header_text, align, anchor_b
            )
        )
    if nm.show_date:
        sp_id, name, idx, x, y, cx, cy, align, anchor_b = _MASTER_PH_SPECS["dt"]
        parts.append(
            _master_hf_sp_xml(sp_id, name, "dt", idx, x, y, cx, cy, nm.date_text, align, anchor_b)
        )

    slide_ln = (
        '<a:ln w="12700"><a:solidFill><a:prstClr val="black"/></a:solidFill></a:ln>'
        if nm.show_slide_border
        else "<a:ln><a:noFill/></a:ln>"
    )
    parts.append(
        "<p:sp>"
        "<p:nvSpPr>"
        '<p:cNvPr id="4" name="Slide Image Placeholder 3"/>'
        '<p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr>'
        '<p:nvPr><p:ph type="sldImg" idx="2"/></p:nvPr>'
        "</p:nvSpPr>"
        "<p:spPr>"
        '<a:xfrm><a:off x="685800" y="1143000"/><a:ext cx="5486400" cy="3086100"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f"<a:noFill/>{slide_ln}"
        "</p:spPr>"
        '<p:txBody><a:bodyPr vert="horz" rtlCol="0" anchor="ctr"/><a:lstStyle/>'
        '<a:p><a:endParaRPr lang="en-US"/></a:p></p:txBody>'
        "</p:sp>"
    )

    notes_ln = (
        '<a:ln w="12700"><a:solidFill><a:prstClr val="black"/></a:solidFill></a:ln>'
        if nm.show_notes_border
        else "<a:ln><a:noFill/></a:ln>"
    )
    parts.append(
        "<p:sp>"
        "<p:nvSpPr>"
        '<p:cNvPr id="5" name="Notes Placeholder 4"/>'
        '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        '<p:nvPr><p:ph type="body" sz="quarter" idx="3"/></p:nvPr>'
        "</p:nvSpPr>"
        "<p:spPr>"
        '<a:xfrm><a:off x="685800" y="4400550"/><a:ext cx="5486400" cy="3600450"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f"{notes_ln}"
        "</p:spPr>"
        '<p:txBody><a:bodyPr vert="horz" lIns="91440" tIns="45720" '
        'rIns="91440" bIns="45720" rtlCol="0"/>'
        '<a:lstStyle/><a:p><a:endParaRPr lang="en-US"/></a:p></p:txBody>'
        "</p:sp>"
    )

    if nm.show_footer:
        sp_id, name, idx, x, y, cx, cy, align, anchor_b = _MASTER_PH_SPECS["ftr"]
        parts.append(
            _master_hf_sp_xml(
                sp_id, name, "ftr", idx, x, y, cx, cy, nm.footer_text, align, anchor_b
            )
        )
    if nm.show_page_number:
        sp_id, name, idx, x, y, cx, cy, align, anchor_b = _MASTER_PH_SPECS["sldNum"]
        parts.append(
            _master_hf_sp_xml(sp_id, name, "sldNum", idx, x, y, cx, cy, "", align, anchor_b)
        )

    sz_val = max(600, int(round(float(nm.notes_font_size or 12.0) * 100)))
    face = escape_xml(nm.notes_font_family or "Arial")
    root_xml = (
        f'<p:notesMaster xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
        f"<p:cSld><p:spTree>{''.join(parts)}</p:spTree></p:cSld>"
        f"{CLR_MAP}"
        f'<p:notesStyle><a:lvl1pPr algn="l"><a:defRPr sz="{sz_val}">'
        f'<a:latin typeface="{face}"/></a:defRPr></a:lvl1pPr></p:notesStyle>'
        "</p:notesMaster>"
    )
    return f"{XML_DECL}{root_xml}"


def _find_ph_sp(sp_tree: ET.Element, ph_type: str) -> ET.Element | None:
    for sp in sp_tree.findall(f"{{{NS_P}}}sp"):
        nv_sp = sp.find(f"{{{NS_P}}}nvSpPr")
        nv_pr = nv_sp.find(f"{{{NS_P}}}nvPr") if nv_sp is not None else None
        ph = nv_pr.find(f"{{{NS_P}}}ph") if nv_pr is not None else None
        if ph is not None and ph.get("type") == ph_type:
            return sp
    return None


def _set_sp_plain_text(sp: ET.Element, text: str) -> None:
    tx_body = sp.find(f"{{{NS_P}}}txBody")
    if tx_body is None:
        tx_body = ET.SubElement(sp, f"{{{NS_P}}}txBody")
        ET.SubElement(tx_body, f"{{{NS_A}}}bodyPr")
        ET.SubElement(tx_body, f"{{{NS_A}}}lstStyle")
    for p_el in list(tx_body.findall(f"{{{NS_A}}}p")):
        tx_body.remove(p_el)
    lines = text.split("\n") if text else [""]
    for line in lines:
        p_el = ET.SubElement(tx_body, f"{{{NS_A}}}p")
        if line:
            r_el = ET.SubElement(p_el, f"{{{NS_A}}}r")
            ET.SubElement(r_el, f"{{{NS_A}}}rPr", lang="en-US")
            t_el = ET.SubElement(r_el, f"{{{NS_A}}}t")
            t_el.text = line
        else:
            ET.SubElement(p_el, f"{{{NS_A}}}endParaRPr", lang="en-US")


def _sync_master_hf_placeholders(sp_tree: ET.Element, master: Any) -> None:
    checks = [
        ("hdr", bool(master.show_header), str(master.header_text or "")),
        ("dt", bool(master.show_date), str(master.date_text or "")),
        ("ftr", bool(master.show_footer), str(master.footer_text or "")),
        ("sldNum", bool(master.show_page_number), None),
    ]
    for ph_type, enabled, text in checks:
        existing = _find_ph_sp(sp_tree, ph_type)
        if not enabled:
            if existing is not None:
                sp_tree.remove(existing)
            continue
        if existing is not None:
            if text is not None:
                _set_sp_plain_text(existing, text)
        else:
            sp_id, name, idx, x, y, cx, cy, align, anchor_b = _MASTER_PH_SPECS[ph_type]
            frag = _master_hf_sp_xml(
                sp_id, name, ph_type, idx, x, y, cx, cy, text or "", align, anchor_b
            )
            sp_tree.append(
                ET.fromstring(
                    f'<p:root xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">{frag}</p:root>'
                )[0]
            )


def _set_sp_border(sp: ET.Element, show_border: bool) -> None:
    sp_pr = sp.find(f"{{{NS_P}}}spPr")
    if sp_pr is None:
        sp_pr = ET.SubElement(sp, f"{{{NS_P}}}spPr")
    for ln in list(sp_pr.findall(f"{{{NS_A}}}ln")):
        sp_pr.remove(ln)
    if show_border:
        ln = ET.SubElement(sp_pr, f"{{{NS_A}}}ln", w="12700")
        sf = ET.SubElement(ln, f"{{{NS_A}}}solidFill")
        ET.SubElement(sf, f"{{{NS_A}}}prstClr", val="black")
    else:
        ln = ET.SubElement(sp_pr, f"{{{NS_A}}}ln")
        ET.SubElement(ln, f"{{{NS_A}}}noFill")
    enforce_schema_order(sp_pr, "presentationml_sppr")


def patch_handout_master_xml(xml_bytes: bytes, settings: HandoutMasterSettings) -> bytes:
    """Patch existing ``handoutMaster1.xml`` in-place while preserving untouched parts."""
    root = ET.fromstring(xml_bytes)
    c_sld = root.find(f"{{{NS_P}}}cSld")
    if c_sld is None:
        return build_handout_master_xml(settings).encode("utf-8")
    sp_tree = c_sld.find(f"{{{NS_P}}}spTree")
    if sp_tree is None:
        return build_handout_master_xml(settings).encode("utf-8")

    _sync_master_hf_placeholders(sp_tree, settings)

    ext_lst = root.find(f"{{{NS_P}}}extLst")
    if ext_lst is None:
        ext_lst = ET.SubElement(root, f"{{{NS_P}}}extLst")
    for ext in list(ext_lst.findall(f"{{{NS_P}}}ext")):
        if ext.get("uri") == ATB_HANDOUT_EXT_URI:
            ext_lst.remove(ext)
    ext = ET.SubElement(ext_lst, f"{{{NS_P}}}ext", uri=ATB_HANDOUT_EXT_URI)
    ET.SubElement(
        ext,
        f"{{{NS_ATB}}}handoutPr",
        slidesPerPage=str(settings.slides_per_page),
        orientation=settings.orientation,
    )
    return f"{XML_DECL}{ET.tostring(root, encoding='unicode')}".encode()


def patch_notes_master_xml(xml_bytes: bytes, settings: NotesMasterSettings) -> bytes:
    """Patch existing ``notesMaster1.xml`` in-place while preserving untouched parts."""
    root = ET.fromstring(xml_bytes)
    c_sld = root.find(f"{{{NS_P}}}cSld")
    if c_sld is None:
        return build_notes_master_xml(settings).encode("utf-8")
    sp_tree = c_sld.find(f"{{{NS_P}}}spTree")
    if sp_tree is None:
        return build_notes_master_xml(settings).encode("utf-8")

    _sync_master_hf_placeholders(sp_tree, settings)

    sld_img = _find_ph_sp(sp_tree, "sldImg")
    if sld_img is not None:
        _set_sp_border(sld_img, settings.show_slide_border)
    body_sp = _find_ph_sp(sp_tree, "body")
    if body_sp is not None:
        _set_sp_border(body_sp, settings.show_notes_border)

    notes_style = root.find(f"{{{NS_P}}}notesStyle")
    if notes_style is None:
        notes_style = ET.SubElement(root, f"{{{NS_P}}}notesStyle")
    lvl1 = notes_style.find(f"{{{NS_A}}}lvl1pPr")
    if lvl1 is None:
        lvl1 = ET.SubElement(notes_style, f"{{{NS_A}}}lvl1pPr", algn="l")
    def_rpr = lvl1.find(f"{{{NS_A}}}defRPr")
    if def_rpr is None:
        def_rpr = ET.SubElement(lvl1, f"{{{NS_A}}}defRPr")
    def_rpr.set("sz", str(max(600, int(round(float(settings.notes_font_size or 12.0) * 100)))))
    latin = def_rpr.find(f"{{{NS_A}}}latin")
    if latin is None:
        latin = ET.SubElement(def_rpr, f"{{{NS_A}}}latin")
    latin.set("typeface", settings.notes_font_family or "Arial")

    return f"{XML_DECL}{ET.tostring(root, encoding='unicode')}".encode()


def build_core_properties_xml(title: str = "", author: str = "") -> str:
    """Generate Dublin Core metadata (docProps/core.xml)."""
    now_iso = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"{XML_DECL}"
        "<cp:coreProperties "
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escape_xml(title)}</dc:title>"
        f"<dc:creator>{escape_xml(author)}</dc:creator>"
        f"<cp:lastModifiedBy>{escape_xml(author)}</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def build_app_properties_xml(total_slides: int = 1) -> str:
    """Generate extended application metadata (docProps/app.xml)."""
    return (
        f"{XML_DECL}"
        "<Properties "
        'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>ATBOffice Lectern</Application>"
        f"<Slides>{total_slides}</Slides>"
        "</Properties>"
    )


def build_pres_props_xml() -> str:
    """Generate default presentation properties (ppt/presProps.xml)."""
    return (
        f"{XML_DECL}"
        f'<p:presentationPr xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
        "<p:showPr><p:present/><p:sldAll/></p:showPr>"
        "</p:presentationPr>"
    )


def build_view_props_xml() -> str:
    """Generate default view properties (ppt/viewProps.xml)."""
    return (
        f"{XML_DECL}"
        f'<p:viewPr xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
        '<p:normalViewPr><p:restoredLeft sz="15620"/><p:restoredTop sz="94660"/></p:normalViewPr>'
        "</p:viewPr>"
    )


def build_table_styles_xml() -> str:
    """Generate default table styles container (ppt/tableStyles.xml)."""
    return (
        f"{XML_DECL}"
        f'<a:tblStyleLst xmlns:a="{NS_A}" def="{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}"/>'
    )
