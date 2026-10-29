"""Unit tests for advanced PPTX reader features:
1. Master and layout placeholder inheritance chain (transforms, fonts, colors).
2. DrawingML custom geometry (a:custGeom) guide evaluations and QPainterPath rendering.
3. Animation timing tree (p:timing) parsing into AnimationModel.
"""

from __future__ import annotations

import io
import zipfile

from PySide6.QtGui import QPainterPath

from atboffice.modules.presentation.io import PptxReader
from atboffice.modules.presentation.views.geometry_helper import create_shape_path


def _create_minimal_pptx_zip(
    slide_xml_content: str,
    slide_rels_content: str = "",
    layout_xml_content: str = "",
    layout_rels_content: str = "",
    master_xml_content: str = "",
    master_rels_content: str = "",
    theme_xml_content: str = "",
) -> bytes:
    """Helper to build an in-memory PPTX zip archive with specified XML parts."""
    buf = io.BytesIO()
    types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels"\n'
        '    ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        '  <Override PartName="/ppt/presentation.xml"\n'
        '    ContentType="application/vnd.openxmlformats-officedocument.'
        'presentationml.presentation.main+xml"/>\n'
        '  <Override PartName="/ppt/slides/slide1.xml"\n'
        '    ContentType="application/vnd.openxmlformats-officedocument.'
        'presentationml.slide+xml"/>\n'
        '  <Override PartName="/ppt/slideLayouts/slideLayout1.xml"\n'
        '    ContentType="application/vnd.openxmlformats-officedocument.'
        'presentationml.slideLayout+xml"/>\n'
        '  <Override PartName="/ppt/slideMasters/slideMaster1.xml"\n'
        '    ContentType="application/vnd.openxmlformats-officedocument.'
        'presentationml.slideMaster+xml"/>\n'
        '  <Override PartName="/ppt/theme/theme1.xml"\n'
        '    ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>\n'
        "</Types>"
    )

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1"\n'
        '    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument"\n'
        '    Target="ppt/presentation.xml"/>\n'
        "</Relationships>"
    )

    pres_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"\n'
        '                xmlns:r="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships">\n'
        '  <p:sldSz cx="9144000" cy="5143500"/>\n'
        "  <p:sldIdLst>\n"
        '    <p:sldId id="256" r:id="rId2"/>\n'
        "  </p:sldIdLst>\n"
        "</p:presentation>"
    )

    pres_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1"\n'
        '    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"\n'
        '    Target="theme/theme1.xml"/>\n'
        '  <Relationship Id="rId2"\n'
        '    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"\n'
        '    Target="slides/slide1.xml"/>\n'
        '  <Relationship Id="rId3"\n'
        '    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'slideMaster"\n'
        '    Target="slideMasters/slideMaster1.xml"/>\n'
        "</Relationships>"
    )

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", types_xml)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("ppt/presentation.xml", pres_xml)
        zf.writestr("ppt/_rels/presentation.xml.rels", pres_rels)
        zf.writestr("ppt/slides/slide1.xml", slide_xml_content)

        if slide_rels_content:
            zf.writestr("ppt/slides/_rels/slide1.xml.rels", slide_rels_content)
        if layout_xml_content:
            zf.writestr("ppt/slideLayouts/slideLayout1.xml", layout_xml_content)
        if layout_rels_content:
            zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", layout_rels_content)
        if master_xml_content:
            zf.writestr("ppt/slideMasters/slideMaster1.xml", master_xml_content)
        if master_rels_content:
            zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", master_rels_content)
        if theme_xml_content:
            zf.writestr("ppt/theme/theme1.xml", theme_xml_content)

    buf.seek(0)
    return buf.getvalue()


def test_custom_geometry_guide_evaluation_and_paths():
    """Verify DrawingML a:custGeom parsing, guide formula evaluation, and QPainterPath."""
    slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="10" name="CustomShape1"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm>
            <a:off x="1270000" y="1270000"/>
            <a:ext cx="2540000" cy="1270000"/>
          </a:xfrm>
          <a:custGeom>
            <a:avLst/>
            <a:gdLst>
              <a:gd name="midX" fmla="*/ w 1 2"/>
              <a:gd name="midY" fmla="*/ h 1 2"/>
              <a:gd name="qX" fmla="*/ w 1 4"/>
            </a:gdLst>
            <a:pathLst>
              <a:path w="2540000" h="1270000">
                <a:moveTo>
                  <a:pt x="0" y="0"/>
                </a:moveTo>
                <a:lnTo>
                  <a:pt x="midX" y="0"/>
                </a:lnTo>
                <a:cubicBezTo>
                  <a:pt x="midX" y="midY"/>
                  <a:pt x="qX" y="midY"/>
                  <a:pt x="w" y="h"/>
                </a:cubicBezTo>
                <a:close/>
              </a:path>
            </a:pathLst>
          </a:custGeom>
          <a:solidFill>
            <a:srgbClr val="FF0000"/>
          </a:solidFill>
        </p:spPr>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""

    data = _create_minimal_pptx_zip(slide_xml)
    pres = PptxReader.from_bytes(data)
    assert len(pres.slides) == 1
    slide = pres.slides[0]
    assert len(slide.shapes) == 1

    shape = slide.shapes[0]
    assert shape.id == "10"
    assert shape.geom == "custom"
    assert shape.custom_path is not None
    assert "paths" in shape.custom_path
    assert len(shape.custom_path["paths"]) == 1

    path_data = shape.custom_path["paths"][0]
    assert len(path_data["cmds"]) == 4
    assert path_data["cmds"][0][0] == "M"
    assert path_data["cmds"][1][0] == "L"
    assert path_data["cmds"][2][0] == "C"
    assert path_data["cmds"][3][0] == "Z"

    # Verify QPainterPath generation
    painter_path = create_shape_path("custom", shape.w, shape.h, custom_path=shape.custom_path)
    assert isinstance(painter_path, QPainterPath)
    assert not painter_path.isEmpty()
    assert painter_path.elementCount() >= 4


def test_master_placeholder_inheritance_chain():
    """Verify placeholder transforms, fonts, sizes, and colors inherit through master."""
    slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="2" name="Title Placeholder"/>
          <p:cNvSpPr/>
          <p:nvPr>
            <p:ph type="title"/>
          </p:nvPr>
        </p:nvSpPr>
        <p:spPr/>
        <p:txBody>
          <a:bodyPr/>
          <a:p>
            <a:r>
              <a:t>Inherited Slide Title</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""

    slide_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1"\n'
        '    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'slideLayout"\n'
        '    Target="../slideLayouts/slideLayout1.xml"/>\n'
        "</Relationships>"
    )

    layout_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
             xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="3" name="Title Frame in Layout"/>
          <p:cNvSpPr/>
          <p:nvPr>
            <p:ph type="title"/>
          </p:nvPr>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm>
            <a:off x="1270000" y="635000"/>
            <a:ext cx="6350000" cy="1270000"/>
          </a:xfrm>
        </p:spPr>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sldLayout>"""

    layout_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1"\n'
        '    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'slideMaster"\n'
        '    Target="../slideMasters/slideMaster1.xml"/>\n'
        "</Relationships>"
    )

    master_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="4" name="Master Title Shape"/>
          <p:cNvSpPr/>
          <p:nvPr>
            <p:ph type="title"/>
          </p:nvPr>
        </p:nvSpPr>
        <p:spPr/>
        <p:txBody>
          <a:bodyPr/>
          <a:p>
            <a:pPr algn="ctr"/>
            <a:r>
              <a:rPr sz="4400" b="1">
                <a:solidFill>
                  <a:srgbClr val="003366"/>
                </a:solidFill>
                <a:latin typeface="Arial Black"/>
              </a:rPr>
              <a:t>Master Title Style</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
  <p:txStyles>
    <p:titleStyle>
      <a:lvl1pPr algn="ctr">
        <a:defRPr sz="4400" b="1">
          <a:solidFill>
            <a:srgbClr val="003366"/>
          </a:solidFill>
          <a:latin typeface="Arial Black"/>
        </a:defRPr>
      </a:lvl1pPr>
    </p:titleStyle>
  </p:txStyles>
</p:sldMaster>"""

    data = _create_minimal_pptx_zip(
        slide_xml_content=slide_xml,
        slide_rels_content=slide_rels,
        layout_xml_content=layout_xml,
        layout_rels_content=layout_rels,
        master_xml_content=master_xml,
    )

    pres = PptxReader.from_bytes(data)
    assert len(pres.slides) == 1
    slide = pres.slides[0]
    assert len(slide.shapes) == 1
    sh = slide.shapes[0]

    # Transform inherited from slideLayout
    assert sh.x == 100.0  # 1270000 / 12700
    assert sh.y == 50.0   # 635000 / 12700
    assert sh.w == 500.0  # 6350000 / 12700
    assert sh.h == 100.0  # 1270000 / 12700

    # Text style inherited from slideMaster
    assert sh.text is not None
    assert len(sh.text.paragraphs) == 1
    p = sh.text.paragraphs[0]
    assert p.props.get("algn") == "ctr"

    assert len(p.runs) == 1
    run = p.runs[0]
    assert run.text == "Inherited Slide Title"
    assert run.size == 44.0
    assert run.color == "#003366"
    assert run.bold is True
    assert run.font == "Arial Black"


def test_animation_timing_tree_parsing():
    """Verify parsing p:timing node into AnimationModel with triggers, delays, and presets."""
    slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="101" name="AnimatedShape1"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></a:xfrm>
        </p:spPr>
      </p:sp>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="102" name="AnimatedShape2"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="100" y="100"/><a:ext cx="100" cy="100"/></a:xfrm>
        </p:spPr>
      </p:sp>
    </p:spTree>
  </p:cSld>
  <p:timing>
    <p:tnLst>
      <p:par>
        <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
          <p:childTnLst>
            <p:seq concurrent="1" nextAc="seek">
              <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
                <p:childTnLst>
                  <p:par>
                    <p:cTn id="3" fill="hold">
                      <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
                      <p:childTnLst>
                        <p:par>
                          <p:cTn id="4" presetID="10" presetClass="entr" presetSubtype="0"
                                 dur="800" nodeType="clickEffect">
                            <p:stCondLst><p:cond delay="250"/></p:stCondLst>
                            <p:childTnLst>
                              <p:animEffect transition="in" filter="fade">
                                <p:cBhvr>
                                  <p:cTn id="5" dur="800"/>
                                  <p:tgtEl><p:spTgt spid="101"/></p:tgtEl>
                                </p:cBhvr>
                              </p:animEffect>
                            </p:childTnLst>
                          </p:cTn>
                        </p:par>
                        <p:par>
                          <p:cTn id="6" presetID="2" presetClass="entr" presetSubtype="8"
                                 dur="600" nodeType="afterEffect">
                            <p:childTnLst>
                              <p:set>
                                <p:cBhvr>
                                  <p:cTn id="7" dur="600"/>
                                  <p:tgtEl><p:spTgt spid="102"/></p:tgtEl>
                                </p:cBhvr>
                              </p:set>
                            </p:childTnLst>
                          </p:cTn>
                        </p:par>
                      </p:childTnLst>
                    </p:cTn>
                  </p:par>
                </p:childTnLst>
              </p:cTn>
            </p:seq>
          </p:childTnLst>
        </p:cTn>
      </p:par>
    </p:tnLst>
  </p:timing>
</p:sld>"""

    data = _create_minimal_pptx_zip(slide_xml)
    pres = PptxReader.from_bytes(data)
    assert len(pres.slides) == 1
    slide = pres.slides[0]

    assert len(slide.animations) == 2

    a1 = slide.animations[0]
    assert a1.sid == "101"
    assert a1.cls == "entr"
    assert a1.eff == "fade"
    assert a1.start == "click"
    assert a1.dur == 800
    assert a1.delay == 250

    a2 = slide.animations[1]
    assert a2.sid == "102"
    assert a2.cls == "entr"
    assert a2.eff == "flyIn"
    assert a2.start == "after"
    assert a2.dur == 600
    assert a2.dir == "t"


def test_custom_geometry_arc_and_quad_bezier():
    """Verify arcTo, quadBezTo, and guide formula math evaluations."""
    slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="15" name="ArcQuadShape"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="0" y="0"/><a:ext cx="1270000" cy="1270000"/></a:xfrm>
          <a:custGeom>
            <a:avLst/>
            <a:gdLst>
              <a:gd name="rx" fmla="*/ w 1 4"/>
              <a:gd name="ry" fmla="*/ h 1 4"/>
            </a:gdLst>
            <a:pathLst>
              <a:path w="1270000" h="1270000">
                <a:moveTo><a:pt x="0" y="0"/></a:moveTo>
                <a:quadBezTo>
                  <a:pt x="rx" y="ry"/>
                  <a:pt x="w" y="0"/>
                </a:quadBezTo>
                <a:arcTo wR="rx" hR="ry" stAng="0" swAng="5400000"/>
                <a:close/>
              </a:path>
            </a:pathLst>
          </a:custGeom>
        </p:spPr>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""

    data = _create_minimal_pptx_zip(slide_xml)
    pres = PptxReader.from_bytes(data)
    assert len(pres.slides) == 1
    sh = pres.slides[0].shapes[0]
    assert sh.geom == "custom"
    assert sh.custom_path is not None
    p_info = sh.custom_path["paths"][0]
    assert any(cmd[0] == "Q" for cmd in p_info["cmds"])
    assert any(cmd[0] == "A" for cmd in p_info["cmds"])

    painter_path = create_shape_path("custom", 100.0, 100.0, custom_path=sh.custom_path)
    assert isinstance(painter_path, QPainterPath)
    assert not painter_path.isEmpty()


def test_placeholder_penetration_when_layout_omits_placeholder():
    """Verify slide placeholder inherits from master when layout omits that placeholder."""
    slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="2" name="Body Placeholder"/>
          <p:cNvSpPr/>
          <p:nvPr><p:ph type="body"/></p:nvPr>
        </p:nvSpPr>
        <p:spPr/>
        <p:txBody>
          <a:bodyPr/>
          <a:p><a:r><a:t>Direct Master Inherited Body</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""

    slide_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1"\n'
        '    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'slideLayout"\n'
        '    Target="../slideLayouts/slideLayout1.xml"/>\n'
        "</Relationships>"
    )

    layout_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
             xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
    </p:spTree>
  </p:cSld>
</p:sldLayout>"""

    layout_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1"\n'
        '    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'slideMaster"\n'
        '    Target="../slideMasters/slideMaster1.xml"/>\n'
        "</Relationships>"
    )

    master_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="4" name="Master Body"/>
          <p:cNvSpPr/>
          <p:nvPr><p:ph type="body"/></p:nvPr>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="635000" y="1905000"/><a:ext cx="7620000" cy="2540000"/></a:xfrm>
        </p:spPr>
        <p:txBody>
          <a:bodyPr/>
          <a:p>
            <a:r>
              <a:rPr sz="2400">
                <a:solidFill><a:srgbClr val="333333"/></a:solidFill>
                <a:latin typeface="Georgia"/>
              </a:rPr>
              <a:t>Master Body Template</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
  <p:txStyles>
    <p:bodyStyle>
      <a:lvl1pPr>
        <a:defRPr sz="2400">
          <a:solidFill><a:srgbClr val="333333"/></a:solidFill>
          <a:latin typeface="Georgia"/>
        </a:defRPr>
      </a:lvl1pPr>
    </p:bodyStyle>
  </p:txStyles>
</p:sldMaster>"""

    data = _create_minimal_pptx_zip(
        slide_xml_content=slide_xml,
        slide_rels_content=slide_rels,
        layout_xml_content=layout_xml,
        layout_rels_content=layout_rels,
        master_xml_content=master_xml,
    )
    pres = PptxReader.from_bytes(data)
    assert len(pres.slides) == 1
    sh = pres.slides[0].shapes[0]
    # Transform directly inherited from master
    assert sh.x == 50.0   # 635000 / 12700
    assert sh.y == 150.0  # 1905000 / 12700
    assert sh.w == 600.0  # 7620000 / 12700
    assert sh.h == 200.0  # 2540000 / 12700

    run = sh.text.paragraphs[0].runs[0]
    assert run.size == 24.0
    assert run.color == "#333333"
    assert run.font == "Georgia"


def test_animation_timing_paragraph_and_emphasis():
    """Verify emphasis animations and paragraph-level animation targeting."""
    slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="55" name="TextBoxShape"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></a:xfrm></p:spPr>
      </p:sp>
    </p:spTree>
  </p:cSld>
  <p:timing>
    <p:tnLst>
      <p:par>
        <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
          <p:childTnLst>
            <p:seq concurrent="1" nextAc="seek">
              <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
                <p:childTnLst>
                  <p:par>
                    <p:cTn id="3" fill="hold">
                      <p:childTnLst>
                        <p:par>
                          <p:cTn id="4" presetID="8" presetClass="emph" dur="1000"
                                 nodeType="clickEffect">
                            <p:childTnLst>
                              <p:set>
                                <p:cBhvr>
                                  <p:cTn id="5" dur="1000"/>
                                  <p:tgtEl>
                                    <p:spTgt spid="55">
                                      <p:pRg st="2" end="2"/>
                                    </p:spTgt>
                                  </p:tgtEl>
                                </p:cBhvr>
                              </p:set>
                            </p:childTnLst>
                          </p:cTn>
                        </p:par>
                      </p:childTnLst>
                    </p:cTn>
                  </p:par>
                </p:childTnLst>
              </p:cTn>
            </p:seq>
          </p:childTnLst>
        </p:cTn>
      </p:par>
    </p:tnLst>
  </p:timing>
</p:sld>"""

    data = _create_minimal_pptx_zip(slide_xml)
    pres = PptxReader.from_bytes(data)
    slide = pres.slides[0]
    assert len(slide.animations) == 1
    anim = slide.animations[0]
    assert anim.sid == "55"
    assert anim.cls == "emph"
    assert anim.eff == "spin"  # presetID 8 in EMPH
    assert anim.by == "para"
    assert anim.para == 2
