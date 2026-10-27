"""Theme, master, layout, and document properties templates for PresentationML."""

from __future__ import annotations

import datetime

from atboffice.modules.presentation.io.xml_utils import (
    NS_A,
    NS_P,
    NS_R,
    XML_DECL,
    escape_xml,
)
from atboffice.modules.presentation.models.designs import DesignTemplate

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


def build_notes_master_xml() -> str:
    """Generate minimal PresentationML Notes Master document (<p:notesMaster>)."""
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
    root_xml = (
        f'<p:notesMaster xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
        f"<p:cSld><p:spTree>{grp_root}</p:spTree></p:cSld>"
        f"{CLR_MAP}"
        '<p:notesStyle><a:lvl1pPr algn="l"><a:defRPr sz="1200"/></a:lvl1pPr></p:notesStyle>'
        "</p:notesMaster>"
    )
    return f"{XML_DECL}{root_xml}"


def build_core_properties_xml(title: str = "", author: str = "") -> str:
    """Generate Dublin Core metadata (docProps/core.xml)."""
    now_iso = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"{XML_DECL}"
        '<cp:coreProperties '
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
        '<Properties '
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
