"""DrawingML Chart XML serialization (<c:chartSpace>) and embedded workbook generation."""

from __future__ import annotations

import html
import io
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Sequence
from typing import Any

from atboffice.modules.presentation.chart.model import ChartData, SeriesData
from atboffice.modules.presentation.io.xml_utils import NS_A, NS_R, XML_DECL

NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
WORKSHEET_CHART_FILL = "#FFFFFF"
WORKSHEET_CHART_BORDER = "#868686"


def chart_to_xml(chart: ChartData | dict[str, Any]) -> str:
    """Serialize ChartData or dict into OpenXML DrawingML <c:chartSpace>."""
    if isinstance(chart, dict):
        chart_obj = ChartData.from_dict(chart)
    else:
        chart_obj = chart

    c = chart_obj
    kind = c.kind
    cats = c.cats or ["1st Qtr", "2nd Qtr", "3rd Qtr", "4th Qtr"]
    series = c.series or []

    # Title XML
    title_xml = ""
    if c.title:
        title_lines = c.title.split("\n")
        para_xmls = []
        for line in title_lines:
            escaped = html.escape(line)
            para_xmls.append(
                f"<a:p><a:pPr><a:defRPr sz=\"{int(c.fsz * 120)}\" b=\"1\"/></a:pPr>"
                f'<a:r><a:rPr lang="en-US" sz="{int(c.fsz * 120)}" b="1"/>'
                f"<a:t>{escaped}</a:t></a:r></a:p>"
            )
        title_xml = (
            f"<c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/>"
            f"{''.join(para_xmls)}</c:rich></c:tx><c:overlay val=\"0\"/></c:title>"
            f'<c:autoTitleDeleted val="0"/>'
        )
    else:
        title_xml = '<c:autoTitleDeleted val="1"/>'

    # Legend XML
    legend_xml = ""
    if c.legend and c.legend != "none":
        legend_xml = (
            f'<c:legend><c:legendPos val="{c.legend}"/><c:overlay val="0"/></c:legend>'
        )

    # Categories XML for a series
    def cat_xml() -> str:
        pt_xmls = "".join(
            f'<c:pt idx="{i}"><c:v>{html.escape(cat)}</c:v></c:pt>'
            for i, cat in enumerate(cats)
        )
        return (
            f"<c:cat><c:strLit><c:ptCount val=\"{len(cats)}\"/>"
            f"{pt_xmls}</c:strLit></c:cat>"
        )

    # Values XML for a series
    def val_xml(vals: list[float], tag: str = "c:val") -> str:
        pt_xmls = "".join(
            f'<c:pt idx="{i}"><c:v>{v}</c:v></c:pt>'
            for i, v in enumerate(vals)
        )
        return (
            f"<{tag}><c:numLit><c:formatCode>General</c:formatCode>"
            f'<c:ptCount val="{len(vals)}"/>{pt_xmls}</c:numLit></{tag}>'
        )

    # Series XML list
    ser_xmls: list[str] = []
    for i, s in enumerate(series):
        s_name = html.escape(s.name or f"Series {i + 1}")
        tx_xml = f"<c:tx><c:v>{s_name}</c:v></c:tx>"
        sp_pr = ""
        if s.color:
            hex_c = s.color.lstrip("#")
            sp_pr = (
                f"<c:spPr><a:solidFill><a:srgbClr val=\"{hex_c}\"/>"
                f"</a:solidFill></c:spPr>"
            )

        if kind in ("scatter", "bubble"):
            xs = s.xs or [float(k + 1) for k in range(len(s.vals))]
            x_xml = val_xml(xs, tag="c:xVal")
            y_xml = val_xml(s.vals, tag="c:yVal")
            bubble_sz = (
                val_xml(s.sizes or s.vals, tag="c:bubbleSize")
                if kind == "bubble"
                else ""
            )
            ser_body = f"{tx_xml}{sp_pr}{x_xml}{y_xml}{bubble_sz}"
        else:
            ser_body = f"{tx_xml}{sp_pr}{cat_xml()}{val_xml(s.vals)}"

        ser_xmls.append(
            f"<c:ser><c:idx val=\"{i}\"/><c:order val=\"{i}\"/>"
            f"{ser_body}</c:ser>"
        )

    all_ser = "".join(ser_xmls)
    ax1 = 50010001
    ax2 = 50010002
    ax_ids = f'<c:axId val="{ax1}"/><c:axId val="{ax2}"/>'

    cat_ax = (
        f'<c:catAx><c:axId val="{ax1}"/><c:scaling><c:orientation val="minMax"/>'
        f'</c:scaling><c:delete val="0"/><c:axPos val="b"/><c:majorTickMark val="out"/>'
        f'<c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
        f'<c:crossAx val="{ax2}"/><c:crosses val="autoZero"/></c:catAx>'
    )
    grid_xml = (
        "<c:majorGridlines/>" if c.grid_y else ""
    )
    val_ax = (
        f'<c:valAx><c:axId val="{ax2}"/><c:scaling><c:orientation val="minMax"/>'
        f'</c:scaling><c:delete val="0"/><c:axPos val="l"/>{grid_xml}'
        f'<c:numFmt formatCode="General" sourceLinked="1"/>'
        f'<c:majorTickMark val="out"/><c:minorTickMark val="none"/>'
        f'<c:tickLblPos val="nextTo"/><c:crossAx val="{ax1}"/><c:crosses val="autoZero"/>'
        f"</c:valAx>"
    )

    bar_kinds = ("col", "colStacked", "colPct", "bar", "barStacked", "barPct")
    v3 = c.view3d if kind in bar_kinds else None
    bar_tag = "bar3DChart" if v3 else "barChart"
    deep = bool(v3 and v3.get("deep") and kind in ("col", "bar"))
    view3d_xml = ""
    if v3:
        view3d_xml = (
            f'<c:view3D><c:rotX val="{int(round(float(v3.get("rotX", 15))))}"/>'
            f'<c:rotY val="{int(round(float(v3.get("rotY", 20))))}"/>'
            f'<c:depthPercent val="{int(round(float(v3.get("depth", 100))))}"/>'
            f'<c:rAngAx val="0"/></c:view3D>'
        )
    ax3 = 50010003
    if deep:
        ax_ids += f'<c:axId val="{ax3}"/>'
    ser_ax = (
        f'<c:serAx><c:axId val="{ax3}"/><c:scaling><c:orientation val="minMax"/>'
        f'</c:scaling><c:delete val="1"/><c:axPos val="b"/>'
        f'<c:tickLblPos val="nextTo"/><c:crossAx val="{ax2}"/>'
        f'<c:crosses val="autoZero"/></c:serAx>'
        if deep
        else ""
    )

    # Plot area according to kind
    if kind in ("bar", "barStacked", "barPct"):
        grp = (
            "percentStacked"
            if kind == "barPct"
            else "stacked"
            if kind == "barStacked"
            else "standard"
            if deep
            else "clustered"
        )
        plot_type = (
            f'<c:{bar_tag}><c:barDir val="bar"/><c:grouping val="{grp}"/>'
            f"{all_ser}{ax_ids}</c:{bar_tag}>"
        )
        plot_area = (
            f"<c:plotArea><c:layout/>{plot_type}{cat_ax}{val_ax}{ser_ax}</c:plotArea>"
        )
    elif kind in ("line", "lineMarkers"):
        plot_type = (
            f'<c:lineChart><c:grouping val="standard"/>'
            f"{all_ser}<c:marker val=\"1\"/>{ax_ids}</c:lineChart>"
        )
        plot_area = f"<c:plotArea><c:layout/>{plot_type}{cat_ax}{val_ax}</c:plotArea>"
    elif kind in ("area", "areaStacked", "areaPct"):
        grp = (
            "percentStacked"
            if kind == "areaPct"
            else "stacked"
            if kind == "areaStacked"
            else "standard"
        )
        plot_type = f'<c:areaChart><c:grouping val="{grp}"/>{all_ser}{ax_ids}</c:areaChart>'
        plot_area = f"<c:plotArea><c:layout/>{plot_type}{cat_ax}{val_ax}</c:plotArea>"
    elif kind == "pie":
        plot_type = f'<c:pieChart><c:varyColors val="1"/>{all_ser}</c:pieChart>'
        plot_area = f"<c:plotArea><c:layout/>{plot_type}</c:plotArea>"
    elif kind == "doughnut":
        plot_type = (
            f'<c:doughnutChart><c:varyColors val="1"/>'
            f'{all_ser}<c:holeSize val="50"/></c:doughnutChart>'
        )
        plot_area = f"<c:plotArea><c:layout/>{plot_type}</c:plotArea>"
    elif kind == "scatter":
        plot_type = (
            f'<c:scatterChart><c:scatterStyle val="lineMarker"/>'
            f"{all_ser}{ax_ids}</c:scatterChart>"
        )
        plot_area = f"<c:plotArea><c:layout/>{plot_type}{cat_ax}{val_ax}</c:plotArea>"
    elif kind == "bubble":
        plot_type = f'<c:bubbleChart>{all_ser}{ax_ids}</c:bubbleChart>'
        plot_area = f"<c:plotArea><c:layout/>{plot_type}{cat_ax}{val_ax}</c:plotArea>"
    elif kind in ("radar", "radarFilled"):
        style_val = "filled" if kind == "radarFilled" else "marker"
        plot_type = (
            f'<c:radarChart><c:radarStyle val="{style_val}"/>'
            f"{all_ser}{ax_ids}</c:radarChart>"
        )
        plot_area = f"<c:plotArea><c:layout/>{plot_type}{cat_ax}{val_ax}</c:plotArea>"
    else:  # col, colStacked, colPct default
        grp = (
            "percentStacked"
            if kind == "colPct"
            else "stacked"
            if kind == "colStacked"
            else "standard"
            if deep
            else "clustered"
        )
        plot_type = (
            f'<c:{bar_tag}><c:barDir val="col"/><c:grouping val="{grp}"/>'
            f"{all_ser}{ax_ids}</c:{bar_tag}>"
        )
        plot_area = (
            f"<c:plotArea><c:layout/>{plot_type}{cat_ax}{val_ax}{ser_ax}</c:plotArea>"
        )

    return (
        f"{XML_DECL}"
        f'<c:chartSpace xmlns:c="{NS_C}" xmlns:a="{NS_A}" xmlns:r="{NS_R}">'
        f'<c:date1904 val="0"/><c:lang val="en-US"/><c:roundedCorners val="0"/>'
        f"<c:chart>{title_xml}{view3d_xml}{plot_area}{legend_xml}"
        f'<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
        f"</c:chartSpace>"
    )


def _color_of(fill: ET.Element, ns: dict[str, str]) -> dict[str, Any] | None:
    """Read the colour of an <a:solidFill> as a chart colour spec."""
    node = next(iter(fill), None)
    if node is None:
        return None
    tag = node.tag.split("}")[-1]
    if tag == "sysClr":
        value = node.get("lastClr")
    else:
        value = node.get("val")
    if not value:
        return None
    spec: dict[str, Any] = {"c": value if tag == "schemeClr" else f"#{value}"}
    alpha = node.find("a:alpha", ns)
    if alpha is not None:
        try:
            spec["a"] = int(alpha.get("val", "100000")) / 100000
        except ValueError:
            pass
    return spec


def _apply_worksheet_defaults(
    chart: ChartData,
    root: ET.Element,
    chart_elem: ET.Element,
    ns: dict[str, str],
) -> None:
    """Fill in what Excel draws for a worksheet chart when the file leaves it implicit."""
    sp_pr = root.find("c:spPr", ns)

    chart.bg = {"c": WORKSHEET_CHART_FILL}
    if sp_pr is not None:
        solid = sp_pr.find("a:solidFill", ns)
        if sp_pr.find("a:noFill", ns) is not None:
            chart.bg = None
        elif solid is not None:
            chart.bg = _color_of(solid, ns) or chart.bg

    chart.border = {"c": WORKSHEET_CHART_BORDER}
    line = sp_pr.find("a:ln", ns) if sp_pr is not None else None
    if line is not None:
        solid = line.find("a:solidFill", ns)
        if line.find("a:noFill", ns) is not None:
            chart.border = {"t": "none"}
        elif solid is not None:
            chart.border = _color_of(solid, ns) or chart.border

    _resolve_auto_title(chart, chart_elem, ns)


def _resolve_auto_title(chart: ChartData, chart_elem: ET.Element, ns: dict[str, str]) -> None:
    """Office's automatic title: a text-less <c:title> or an undeleted auto title."""
    if chart.title:
        return
    title_elem = chart_elem.find("c:title", ns)
    if title_elem is not None:
        linked = title_elem.find("c:tx//c:v", ns)
        if linked is not None and linked.text:
            chart.title = linked.text
        elif len(chart.series) == 1:
            chart.title = chart.series[0].name
        else:
            chart.title = "Chart Title"
        return
    deleted = chart_elem.find("c:autoTitleDeleted", ns)
    is_deleted = deleted is not None and deleted.get("val", "1") in ("1", "true")
    if not is_deleted and len(chart.series) == 1:
        chart.title = chart.series[0].name


def _parse_view3d(v3: ET.Element | None, ns: dict[str, str]) -> dict[str, Any]:
    """Read c:view3D with Office's defaults for column/bar charts."""

    def num(tag: str, default: float) -> float:
        node = v3.find(f"c:{tag}", ns) if v3 is not None else None
        try:
            return float(node.get("val")) if node is not None else default
        except (TypeError, ValueError):
            return default

    return {
        "rotX": num("rotX", 15.0),
        "rotY": num("rotY", 20.0),
        "depth": num("depthPercent", 100.0),
    }


def parse_chart_xml(
    xml_content: str | bytes,
    *,
    worksheet_defaults: bool = False,
    theme_accents: Sequence[str] | None = None,
    auto_title: bool = False,
) -> ChartData:
    """Parse a DrawingML <c:chartSpace> XML string or bytes into ChartData.

    With ``worksheet_defaults``, implicit chart-area and automatic-title
    properties resolve the way Excel draws them on a worksheet; ``auto_title``
    applies only the automatic title (PowerPoint). ``theme_accents`` (accent1..
    accent6 as "#RRGGBB") resolve series scheme colours and colour series that
    set none.
    """
    if isinstance(xml_content, str):
        root = ET.fromstring(xml_content)
    else:
        root = ET.fromstring(xml_content.decode("utf-8", errors="ignore"))

    # Namespaces
    ns = {"c": NS_C, "a": NS_A}

    chart_elem = root.find("c:chart", ns)
    if chart_elem is None:
        return ChartData.create_sample()

    # Title
    title = ""
    title_elem = chart_elem.find("c:title", ns)
    if title_elem is not None:
        t_nodes = title_elem.findall(".//a:t", ns)
        title = "".join(t.text or "" for t in t_nodes)

    # Legend
    legend = "none"
    legend_elem = chart_elem.find("c:legend", ns)
    if legend_elem is not None:
        pos_elem = legend_elem.find("c:legendPos", ns)
        legend = pos_elem.get("val", "r") if pos_elem is not None else "r"

    plot_elem = chart_elem.find("c:plotArea", ns)
    if plot_elem is None:
        empty_chart = ChartData(title=title, legend=legend)
        if worksheet_defaults:
            _apply_worksheet_defaults(empty_chart, root, chart_elem, ns)
        return empty_chart

    # Determine kind from plot children
    kind = "col"
    view3d: dict[str, Any] | None = None
    chart_type_elem = None
    for child in plot_elem:
        tag_name = child.tag.split("}")[-1]
        if tag_name.endswith("Chart"):
            chart_type_elem = child
            if tag_name in ("barChart", "bar3DChart"):
                bar_dir = child.find("c:barDir", ns)
                grouping = child.find("c:grouping", ns)
                grp_val = grouping.get("val") if grouping is not None else "clustered"
                if tag_name == "bar3DChart":
                    view3d = _parse_view3d(chart_elem.find("c:view3D", ns), ns)
                    view3d["deep"] = grp_val == "standard"
                is_h_bar = bar_dir is not None and bar_dir.get("val") == "bar"
                if is_h_bar:
                    kind = (
                        "barPct" if grp_val == "percentStacked"
                        else "barStacked" if grp_val == "stacked"
                        else "bar"
                    )
                else:
                    kind = (
                        "colPct" if grp_val == "percentStacked"
                        else "colStacked" if grp_val == "stacked"
                        else "col"
                    )
            elif tag_name in ("lineChart", "line3DChart"):
                marker_elem = child.find("c:marker", ns)
                kind = "lineMarkers" if marker_elem is not None else "line"
            elif tag_name in ("areaChart", "area3DChart"):
                grouping = child.find("c:grouping", ns)
                grp_val = grouping.get("val") if grouping is not None else "standard"
                kind = (
                    "areaPct" if grp_val == "percentStacked"
                    else "areaStacked" if grp_val == "stacked"
                    else "area"
                )
            elif tag_name in ("pieChart", "pie3DChart", "ofPieChart"):
                kind = "pie"
            elif tag_name == "doughnutChart":
                kind = "doughnut"
            elif tag_name == "scatterChart":
                kind = "scatter"
            elif tag_name == "bubbleChart":
                kind = "bubble"
            elif tag_name == "radarChart":
                radar_style = child.find("c:radarStyle", ns)
                is_filled = (
                    radar_style is not None
                    and radar_style.get("val") == "filled"
                )
                kind = "radarFilled" if is_filled else "radar"
            break

    # Parse categories and series
    cats: list[str] = []
    series_list: list[SeriesData] = []

    if chart_type_elem is not None:
        ser_elems = chart_type_elem.findall("c:ser", ns)
        for s_idx, ser in enumerate(ser_elems):
            # Name
            name_node = ser.find(".//c:tx//c:v", ns)
            if name_node is None:
                name_node = ser.find(".//c:tx//a:t", ns)
            ser_name = (
                name_node.text
                if name_node is not None and name_node.text
                else f"Series {s_idx + 1}"
            )

            # Color
            col_hex = ""
            clr_node = ser.find(".//c:spPr//a:srgbClr", ns)
            if clr_node is not None and clr_node.get("val"):
                col_hex = f"#{clr_node.get('val')}"
            elif theme_accents:
                scheme_node = ser.find("c:spPr/a:solidFill/a:schemeClr", ns)
                slot = scheme_node.get("val", "") if scheme_node is not None else ""
                if slot.startswith("accent") and slot[6:].isdigit():
                    a_idx = int(slot[6:]) - 1
                    if 0 <= a_idx < len(theme_accents):
                        col_hex = theme_accents[a_idx]
                elif scheme_node is None:
                    # Office's automatic series colours cycle through the theme accents
                    col_hex = theme_accents[s_idx % len(theme_accents)]

            # Categories (from first series if available)
            if not cats:
                cat_nodes = ser.findall(".//c:cat//c:pt//c:v", ns)
                cats = [c.text or "" for c in cat_nodes]

            # Values
            val_nodes = ser.findall(".//c:val//c:pt//c:v", ns)
            vals = []
            for v_node in val_nodes:
                try:
                    vals.append(float(v_node.text or "0"))
                except ValueError:
                    vals.append(0.0)

            series_list.append(SeriesData(name=ser_name, vals=vals, color=col_hex))

    if not cats:
        max_vals = max((len(s.vals) for s in series_list), default=4)
        cats = [str(i + 1) for i in range(max_vals)]

    # Major gridlines
    grid_y = bool(plot_elem.find(".//c:valAx//c:majorGridlines", ns) is not None)

    chart = ChartData(
        v=2,
        kind=kind,
        title=title,
        legend=legend,
        grid_y=grid_y,
        cats=cats,
        series=series_list,
        view3d=view3d,
    )
    if worksheet_defaults:
        _apply_worksheet_defaults(chart, root, chart_elem, ns)
    elif auto_title:
        _resolve_auto_title(chart, chart_elem, ns)
    return chart


def create_embedded_workbook(chart: ChartData) -> bytes:
    """Generate a minimal valid XLSX workbook byte string reflecting chart data."""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml
        ct_rels = (
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        )
        ct_wb = (
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        )
        ct_ws = (
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        z.writestr(
            "[Content_Types].xml",
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            f'{ct_rels}<Default Extension="xml" ContentType="application/xml"/>'
            f"{ct_wb}{ct_ws}</Types>",
        )
        # _rels/.rels
        rel_office = (
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
        )
        z.writestr(
            "_rels/.rels",
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{rel_office}</Relationships>",
        )
        # xl/_rels/workbook.xml.rels
        rel_ws = (
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{rel_ws}</Relationships>",
        )
        # xl/workbook.xml
        z.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>",
        )
        # xl/worksheets/sheet1.xml
        cats = chart.cats or []
        series = chart.series or []

        # Row 1: Header (Empty A1, Category names in B1, C1...)
        rows_xml: list[str] = []
        r1_cells = ['<c r="A1" t="s"><v>0</v></c>']
        for ci, cat in enumerate(cats):
            col_letter = chr(ord("B") + ci)
            escaped = html.escape(cat)
            r1_cells.append(f'<c r="{col_letter}1" t="inlineStr"><is><t>{escaped}</t></is></c>')
        rows_xml.append(f'<row r="1">{"".join(r1_cells)}</row>')

        # Subsequent rows for each series
        for si, s in enumerate(series):
            r_idx = si + 2
            s_name = html.escape(s.name or f"Series {si + 1}")
            r_cells = [f'<c r="A{r_idx}" t="inlineStr"><is><t>{s_name}</t></is></c>']
            for ci, val in enumerate(s.vals):
                col_letter = chr(ord("B") + ci)
                r_cells.append(f'<c r="{col_letter}{r_idx}"><v>{val}</v></c>')
            rows_xml.append(f'<row r="{r_idx}">{"".join(r_cells)}</row>')

        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(rows_xml)}</sheetData>'
            "</worksheet>"
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    return bio.getvalue()
