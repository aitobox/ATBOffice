"""Shape, picture, table, and group XML serialization for PresentationML."""

from __future__ import annotations

from collections.abc import Callable

from atboffice.modules.presentation.io.alternate_content import render_preserved
from atboffice.modules.presentation.io.writer_text import text_body_to_xml
from atboffice.modules.presentation.io.xml_utils import (
    color_to_xml,
    escape_xml,
    fill_to_xml,
    geometry_to_xml,
    line_to_xml,
    pt_to_emu,
    shadow_to_xml,
    transform_to_xml,
)
from atboffice.modules.presentation.models.designs import DesignTemplate
from atboffice.modules.presentation.models.shape import Shape


def non_visual_properties_to_xml(
    shape_id: str,
    shape: Shape,
    tag: str = "p:cNvPr",
) -> str:
    """Generate common non-visual drawing properties XML (<p:cNvPr>)."""
    name = escape_xml(shape.name or f"Shape {shape_id}")
    attrs = [f'id="{shape_id}"', f'name="{name}"']
    return f"<{tag} {' '.join(attrs)}/>"


def placeholder_nv_to_xml(shape: Shape) -> str:
    """Generate placeholder container XML (<p:nvPr><p:ph .../></p:nvPr>)."""
    if not shape.placeholder:
        return "<p:nvPr/>"
    ph = shape.placeholder
    ph_attrs = []
    if ph.type and ph.type != "obj":
        ph_attrs.append(f'type="{ph.type}"')
    if ph.idx:
        ph_attrs.append(f'idx="{ph.idx}"')
    attr_str = f" {' '.join(ph_attrs)}" if ph_attrs else ""
    return f"<p:nvPr><p:ph{attr_str}/></p:nvPr>"


def shape_properties_to_xml(
    shape: Shape,
    design: DesignTemplate | None = None,
    tag: str = "p:spPr",
) -> str:
    """Generate DrawingML shape properties element (<p:spPr>)."""
    # Strict schema order: xfrm -> prstGeom/custGeom -> fill -> ln -> effectLst
    xfrm_xml = transform_to_xml(shape, "a:xfrm")
    geom_xml = geometry_to_xml(shape)
    fill_xml = fill_to_xml(shape.fill, design=design)
    line_xml = line_to_xml(shape.line, design=design)
    shadow_xml = shadow_to_xml(shape.shadow, design=design)

    return f"<{tag}>{xfrm_xml}{geom_xml}{fill_xml}{line_xml}{shadow_xml}</{tag}>"


_TBL_FLAGS = ("firstRow", "firstCol", "lastRow", "lastCol", "bandRow", "bandCol")


def _cell_border_xml(tag: str, line: dict | None, design: DesignTemplate | None) -> str:
    if not isinstance(line, dict):
        return ""
    width = float(line.get("w") or 0.0)
    if width <= 0 or not line.get("c"):
        return f"<{tag}><a:noFill/></{tag}>"
    dash = line.get("dash") or "solid"
    dash_xml = f'<a:prstDash val="{escape_xml(dash)}"/>' if dash != "custom" else ""
    return (
        f'<{tag} w="{pt_to_emu(width)}">'
        f"<a:solidFill>{color_to_xml(line['c'], None, design)}</a:solidFill>"
        f"{dash_xml}</{tag}>"
    )


def _cell_properties_xml(cell: dict, design: DesignTemplate | None) -> str:
    """Serialize the cell's own <a:tcPr> (style-derived values are not baked in)."""
    own = cell.get("own")
    if own is None:
        # Cells created in-app: every fill/border on them is their own.
        own = {"fill": bool(cell.get("fill")), "bd": list((cell.get("bd") or {}).keys())}
    parts: list[str] = []
    bd = cell.get("bd") or {}
    for side, tag in (("l", "a:lnL"), ("r", "a:lnR"), ("t", "a:lnT"), ("b", "a:lnB")):
        if side in own.get("bd", []):
            parts.append(_cell_border_xml(tag, bd.get(side), design))
    fill = cell.get("fill")
    if own.get("fill") and isinstance(fill, dict):
        if fill.get("t") == "solid" and fill.get("c"):
            parts.append(
                f"<a:solidFill>{color_to_xml(fill['c'], fill.get('a'), design)}</a:solidFill>"
            )
        elif fill.get("t") == "none":
            parts.append("<a:noFill/>")
    return f"<a:tcPr>{''.join(parts)}</a:tcPr>" if parts else "<a:tcPr/>"


def _cell_attrs(cell: dict) -> str:
    attrs: list[str] = []
    for key, attr in (("gs", "gridSpan"), ("rs", "rowSpan")):
        try:
            span = int(cell.get(key) or 1)
        except (TypeError, ValueError):
            span = 1
        if span > 1:
            attrs.append(f'{attr}="{span}"')
    for key, attr in (("hm", "hMerge"), ("vm", "vMerge")):
        if cell.get(key):
            attrs.append(f'{attr}="1"')
    return (" " + " ".join(attrs)) if attrs else ""


def _table_properties_xml(tbl_data: dict) -> str:
    if not any(flag in tbl_data for flag in _TBL_FLAGS):
        flags = {"firstRow": True, "bandRow": True}  # defaults for tables created in-app
    else:
        flags = {flag: bool(tbl_data.get(flag)) for flag in _TBL_FLAGS}
    attrs = "".join(f' {flag}="1"' for flag in _TBL_FLAGS if flags.get(flag))
    style_id = tbl_data.get("style_id")
    if style_id:
        sid = escape_xml(str(style_id))
        return f"<a:tblPr{attrs}><a:tableStyleId>{sid}</a:tableStyleId></a:tblPr>"
    return f"<a:tblPr{attrs}/>"


def table_to_xml(
    shape: Shape,
    shape_id: str,
    design: DesignTemplate | None = None,
    lang: str = "en-US",
) -> str:
    """Serialize Table shape to PresentationML <p:graphicFrame>."""
    c_nv_pr = non_visual_properties_to_xml(shape_id, shape)
    c_nv_gframe = '<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr>'
    nv_pr = placeholder_nv_to_xml(shape)
    nv_graphic_frame = f"<p:nvGraphicFramePr>{c_nv_pr}{c_nv_gframe}{nv_pr}</p:nvGraphicFramePr>"
    xfrm_xml = transform_to_xml(shape, "p:xfrm")

    tbl_data = shape.tbl or {}
    cols = tbl_data.get("cols", [shape.w / 2, shape.w / 2])
    grid_xml = "".join(f'<a:gridCol w="{pt_to_emu(w)}"/>' for w in cols)

    rows_xml: list[str] = []
    for r in tbl_data.get("rows", []):
        h_emu = pt_to_emu(r.get("h", 30.0))
        cells_xml: list[str] = []
        for c in r.get("cells", []):
            tx_xml = text_body_to_xml(c.get("tx"), design=design, tag="a:txBody", lang=lang)
            if not tx_xml:
                tx_xml = (
                    "<a:txBody><a:bodyPr/><a:lstStyle/>"
                    '<a:p><a:endParaRPr lang="en-US"/></a:p></a:txBody>'
                )
            tc_pr = _cell_properties_xml(c, design)
            cells_xml.append(f"<a:tc{_cell_attrs(c)}>{tx_xml}{tc_pr}</a:tc>")
        rows_xml.append(f'<a:tr h="{h_emu}">{"".join(cells_xml)}</a:tr>')

    tbl_pr = _table_properties_xml(tbl_data)
    tbl_grid = f"<a:tblGrid>{grid_xml}</a:tblGrid>"
    table_content = f"<a:tbl>{tbl_pr}{tbl_grid}{''.join(rows_xml)}</a:tbl>"
    graphic = (
        "<a:graphic>"
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
        f"{table_content}"
        "</a:graphicData>"
        "</a:graphic>"
    )

    # Strict schema order: nvGraphicFramePr -> xfrm -> graphic -> extLst
    return f"<p:graphicFrame>{nv_graphic_frame}{xfrm_xml}{graphic}</p:graphicFrame>"


def chart_frame_to_xml(
    shape: Shape,
    shape_id: str,
    chart_rid: str,
) -> str:
    """Serialize Chart shape to PresentationML <p:graphicFrame>."""
    c_nv_pr = non_visual_properties_to_xml(shape_id, shape)
    c_nv_gframe = '<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr>'
    nv_pr = placeholder_nv_to_xml(shape)
    nv_graphic_frame = f"<p:nvGraphicFramePr>{c_nv_pr}{c_nv_gframe}{nv_pr}</p:nvGraphicFramePr>"
    xfrm_xml = transform_to_xml(shape, "p:xfrm")
    graphic = (
        "<a:graphic>"
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
        f'<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
        f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        f'r:id="{chart_rid}"/>'
        "</a:graphicData>"
        "</a:graphic>"
    )
    return f"<p:graphicFrame>{nv_graphic_frame}{xfrm_xml}{graphic}</p:graphicFrame>"


def _src_rect_xml(shape: Shape) -> str:
    """Serialize a picture's crop fractions as <a:srcRect> (1/1000 percent)."""
    crop = shape.crop if isinstance(shape.crop, dict) else None
    if not crop:
        return ""
    attrs = ""
    for key in ("l", "t", "r", "b"):
        val = int(round(float(crop.get(key, 0.0) or 0.0) * 100000))
        if val:
            attrs += f' {key}="{val}"'
    return f"<a:srcRect{attrs}/>" if attrs else ""


def picture_to_xml(
    shape: Shape,
    shape_id: str,
    embed_rid: str,
    design: DesignTemplate | None = None,
) -> str:
    """Serialize Image shape to PresentationML <p:pic>."""
    c_nv_pr = non_visual_properties_to_xml(shape_id, shape)
    c_nv_pic = '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>'
    nv_pr = placeholder_nv_to_xml(shape)
    nv_pic_pr = f"<p:nvPicPr>{c_nv_pr}{c_nv_pic}{nv_pr}</p:nvPicPr>"

    blip_fill = (
        f'<p:blipFill><a:blip r:embed="{embed_rid}"/>{_src_rect_xml(shape)}'
        "<a:stretch><a:fillRect/></a:stretch></p:blipFill>"
    )
    sp_pr = shape_properties_to_xml(shape, design=design, tag="p:spPr")

    # Strict schema order: nvPicPr -> blipFill -> spPr -> style -> extLst
    return f"<p:pic>{nv_pic_pr}{blip_fill}{sp_pr}</p:pic>"


def media_picture_to_xml(
    shape: Shape,
    shape_id: str,
    poster_rid: str,
    media_rid: str,
    file_rid: str,
    design: DesignTemplate | None = None,
) -> str:
    """Serialize Multimedia Video/Audio Shape to PresentationML <p:pic>."""
    c_nv_name = escape_xml(shape.name or f"Media {shape_id}")
    c_nv_pr = (
        f'<p:cNvPr id="{shape_id}" name="{c_nv_name}">'
        '<a:hlinkClick r:action="ppaction://media"/>'
        '<p:extLst>'
        '<p:ext uri="{DAA4B390-3183-40C9-BE18-7BFA0C31F651}">'
        '<p14:media xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" '
        f'r:embed="{media_rid}"/>'
        '</p:ext>'
        '</p:extLst>'
        '</p:cNvPr>'
    )
    c_nv_pic = '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>'
    media_tag = "p:audioFile" if (shape.media_item and shape.media_item.is_audio) else "p:videoFile"
    nv_pr = f'<{media_tag} r:link="{file_rid}"/>' if file_rid else ""
    nv_pic_pr = f"<p:nvPicPr>{c_nv_pr}{c_nv_pic}<p:nvPr>{nv_pr}</p:nvPr></p:nvPicPr>"

    blip_fill = (
        f'<p:blipFill><a:blip r:embed="{poster_rid}"/>'
        "<a:stretch><a:fillRect/></a:stretch></p:blipFill>"
    )
    sp_pr = shape_properties_to_xml(shape, design=design, tag="p:spPr")
    return f"<p:pic>{nv_pic_pr}{blip_fill}{sp_pr}</p:pic>"


def diagram_frame_to_xml(
    shape: Shape,
    shape_id: str,
    dm_rid: str,
    lo_rid: str,
    qs_rid: str,
    cs_rid: str,
) -> str:
    """Serialize SmartArt Diagram shape to PresentationML <p:graphicFrame>."""
    c_nv_pr = non_visual_properties_to_xml(shape_id, shape)
    c_nv_gframe = '<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr>'
    nv_pr = placeholder_nv_to_xml(shape)
    nv_graphic_frame = f"<p:nvGraphicFramePr>{c_nv_pr}{c_nv_gframe}{nv_pr}</p:nvGraphicFramePr>"
    xfrm_xml = transform_to_xml(shape, "p:xfrm")
    graphic = (
        "<a:graphic>"
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/diagram">'
        f'<dgm:relIds xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
        f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        f'r:dm="{dm_rid}" r:lo="{lo_rid}" r:qs="{qs_rid}" r:cs="{cs_rid}"/>'
        "</a:graphicData>"
        "</a:graphic>"
    )
    return f"<p:graphicFrame>{nv_graphic_frame}{xfrm_xml}{graphic}</p:graphicFrame>"


def shape_to_xml(
    shape: Shape,
    id_resolver: Callable[[str], str],
    design: DesignTemplate | None = None,
    media_resolver: Callable[[str], str] | None = None,
    lang: str = "en-US",
) -> str:
    """Serialize any Shape model into compliant PresentationML XML."""
    # Unedited shape loaded from mc:AlternateContent: write the original block back.
    preserved = render_preserved(shape, id_resolver, media_resolver)
    if preserved is not None:
        return preserved

    shape_id = id_resolver(shape.id)

    # 0. SmartArt Diagram GraphicFrame
    if (shape.is_diagram or bool(shape.sa)) and media_resolver:
        dm_rid = media_resolver(f"diagram_dm:{shape.id}")
        lo_rid = media_resolver(f"diagram_lo:{shape.id}")
        qs_rid = media_resolver(f"diagram_qs:{shape.id}")
        cs_rid = media_resolver(f"diagram_cs:{shape.id}")
        if dm_rid and lo_rid:
            return diagram_frame_to_xml(shape, shape_id, dm_rid, lo_rid, qs_rid, cs_rid)

    # 1. Group Shapes
    if shape.type == "group":
        c_nv_pr = non_visual_properties_to_xml(shape_id, shape)
        nv_grp_sp_pr = f"<p:nvGrpSpPr>{c_nv_pr}<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        ext_xml = (
            f'<a:chOff x="{pt_to_emu(shape.x)}" y="{pt_to_emu(shape.y)}"/>'
            f'<a:chExt cx="{pt_to_emu(shape.w)}" cy="{pt_to_emu(shape.h)}"/>'
        )
        grp_sp_pr = f"<p:grpSpPr>{transform_to_xml(shape, 'a:xfrm', ext_xml)}</p:grpSpPr>"
        kids_xml = "".join(
            shape_to_xml(
                k,
                id_resolver=id_resolver,
                design=design,
                media_resolver=media_resolver,
                lang=lang,
            )
            for k in shape.kids
        )
        return f"<p:grpSp>{nv_grp_sp_pr}{grp_sp_pr}{kids_xml}</p:grpSp>"

    # 2. Table & Chart Frames
    if shape.is_chart:
        chart_rid = ""
        if media_resolver:
            chart_rid = media_resolver(f"chart:{shape.id}")
        if chart_rid:
            return chart_frame_to_xml(shape, shape_id, chart_rid)

    if shape.type == "table":
        return table_to_xml(shape, shape_id, design=design, lang=lang)

    # 3. Multimedia Video/Audio
    if shape.media_item:
        poster_rid = ""
        media_rid = ""
        file_rid = ""
        if media_resolver:
            poster_rid = media_resolver(f"media_poster:{shape.id}")
            media_rid = media_resolver(f"media_p14:{shape.id}")
            file_rid = media_resolver(f"media_file:{shape.id}")
        if poster_rid or media_rid:
            return media_picture_to_xml(
                shape,
                shape_id,
                poster_rid=poster_rid or media_rid,
                media_rid=media_rid or poster_rid,
                file_rid=file_rid or media_rid or poster_rid,
                design=design,
            )

    # 4. Pictures / Images
    if shape.type == "image":
        embed_rid = ""
        if media_resolver and shape.media:
            embed_rid = media_resolver(shape.media)
        if embed_rid:
            return picture_to_xml(shape, shape_id, embed_rid, design=design)

    # 4.1 Connectors (<p:cxnSp>)
    is_named_conn = (
        shape.geom.startswith("straightConnector")
        or "bentConnector" in shape.geom
        or "curvedConnector" in shape.geom
    )
    if shape.is_connector and (shape.cxn_start or shape.cxn_end or is_named_conn):
        c_nv_pr = non_visual_properties_to_xml(shape_id, shape)
        cxn_tags = []
        if shape.cxn_start:
            s_id = escape_xml(str(shape.cxn_start.get("id", "")))
            s_idx = shape.cxn_start.get("idx", 0)
            cxn_tags.append(f'<a:stCxn id="{s_id}" idx="{s_idx}"/>')
        if shape.cxn_end:
            e_id = escape_xml(str(shape.cxn_end.get("id", "")))
            e_idx = shape.cxn_end.get("idx", 0)
            cxn_tags.append(f'<a:endCxn id="{e_id}" idx="{e_idx}"/>')
        c_nv_cxn_pr = f"<p:cNvCxnSpPr>{''.join(cxn_tags)}</p:cNvCxnSpPr>"
        nv_cxn_sp_pr = f"<p:nvCxnSpPr>{c_nv_pr}{c_nv_cxn_pr}<p:nvPr/></p:nvCxnSpPr>"
        sp_pr = shape_properties_to_xml(shape, design=design, tag="p:spPr")
        return f"<p:cxnSp>{nv_cxn_sp_pr}{sp_pr}</p:cxnSp>"

    # 4.2 Standard Shapes & Text Boxes
    is_tx_box = shape.type == "text" and not shape.placeholder
    sp_locks = (
        '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        if shape.placeholder
        else '<p:cNvSpPr txBox="1"/>'
        if is_tx_box
        else "<p:cNvSpPr/>"
    )
    c_nv_pr = non_visual_properties_to_xml(shape_id, shape)
    nv_pr = placeholder_nv_to_xml(shape)
    nv_sp_pr = f"<p:nvSpPr>{c_nv_pr}{sp_locks}{nv_pr}</p:nvSpPr>"

    sp_pr = shape_properties_to_xml(shape, design=design, tag="p:spPr")
    tx_body = (
        text_body_to_xml(shape.text, design=design, tag="p:txBody", lang=lang) if shape.text else ""
    )

    # Strict schema order: nvSpPr -> spPr -> style -> txBody -> extLst
    return f"<p:sp>{nv_sp_pr}{sp_pr}{tx_body}</p:sp>"
