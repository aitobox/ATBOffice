"""Shape, picture, table, and group XML serialization for PresentationML."""

from __future__ import annotations

from collections.abc import Callable

from atboffice.modules.presentation.io.writer_text import text_body_to_xml
from atboffice.modules.presentation.io.xml_utils import (
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
            tc_pr = "<a:tcPr/>"
            cells_xml.append(f"<a:tc>{tx_xml}{tc_pr}</a:tc>")
        rows_xml.append(f'<a:tr h="{h_emu}">{"".join(cells_xml)}</a:tr>')

    tbl_pr = '<a:tblPr firstRow="1" bandRow="1"/>'
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
        f'<p:blipFill><a:blip r:embed="{embed_rid}"/>'
        "<a:stretch><a:fillRect/></a:stretch></p:blipFill>"
    )
    sp_pr = shape_properties_to_xml(shape, design=design, tag="p:spPr")

    # Strict schema order: nvPicPr -> blipFill -> spPr -> style -> extLst
    return f"<p:pic>{nv_pic_pr}{blip_fill}{sp_pr}</p:pic>"


def shape_to_xml(
    shape: Shape,
    id_resolver: Callable[[str], str],
    design: DesignTemplate | None = None,
    media_resolver: Callable[[str], str] | None = None,
    lang: str = "en-US",
) -> str:
    """Serialize any Shape model into compliant PresentationML XML."""
    shape_id = id_resolver(shape.id)

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

    # 2. Table Frames
    if shape.type == "table":
        return table_to_xml(shape, shape_id, design=design, lang=lang)

    # 3. Pictures / Images
    if shape.type == "image":
        embed_rid = ""
        if media_resolver and shape.media:
            embed_rid = media_resolver(shape.media)
        if embed_rid:
            return picture_to_xml(shape, shape_id, embed_rid, design=design)

    # 4. Standard Shapes & Text Boxes
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
