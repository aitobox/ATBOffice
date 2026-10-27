"""DrawingML Chart XML serialization (<c:chartSpace>) and embedded workbook generation."""

from __future__ import annotations

import html
import io
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from atboffice.modules.presentation.chart.model import ChartData, SeriesData
from atboffice.modules.presentation.io.xml_utils import NS_A, NS_R, XML_DECL

NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"


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

    # Plot area according to kind
    if kind in ("bar", "barStacked", "barPct"):
        grp = (
            "percentStacked"
            if kind == "barPct"
            else "stacked"
            if kind == "barStacked"
            else "clustered"
        )
        plot_type = (
            f'<c:barChart><c:barDir val="bar"/><c:grouping val="{grp}"/>'
            f"{all_ser}{ax_ids}</c:barChart>"
        )
        plot_area = f"<c:plotArea><c:layout/>{plot_type}{cat_ax}{val_ax}</c:plotArea>"
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
            else "clustered"
        )
        plot_type = (
            f'<c:barChart><c:barDir val="col"/><c:grouping val="{grp}"/>'
            f"{all_ser}{ax_ids}</c:barChart>"
        )
        plot_area = f"<c:plotArea><c:layout/>{plot_type}{cat_ax}{val_ax}</c:plotArea>"

    return (
        f"{XML_DECL}"
        f'<c:chartSpace xmlns:c="{NS_C}" xmlns:a="{NS_A}" xmlns:r="{NS_R}">'
        f'<c:date1904 val="0"/><c:lang val="en-US"/><c:roundedCorners val="0"/>'
        f"<c:chart>{title_xml}{plot_area}{legend_xml}"
        f'<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
        f"</c:chartSpace>"
    )


def parse_chart_xml(xml_content: str | bytes) -> ChartData:
    """Parse a DrawingML <c:chartSpace> XML string or bytes into ChartData."""
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
        return ChartData(title=title, legend=legend)

    # Determine kind from plot children
    kind = "col"
    chart_type_elem = None
    for child in plot_elem:
        tag_name = child.tag.split("}")[-1]
        if tag_name.endswith("Chart"):
            chart_type_elem = child
            if tag_name == "barChart":
                bar_dir = child.find("c:barDir", ns)
                grouping = child.find("c:grouping", ns)
                grp_val = grouping.get("val") if grouping is not None else "clustered"
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
            elif tag_name == "lineChart":
                marker_elem = child.find("c:marker", ns)
                kind = "lineMarkers" if marker_elem is not None else "line"
            elif tag_name == "areaChart":
                grouping = child.find("c:grouping", ns)
                grp_val = grouping.get("val") if grouping is not None else "standard"
                kind = (
                    "areaPct" if grp_val == "percentStacked"
                    else "areaStacked" if grp_val == "stacked"
                    else "area"
                )
            elif tag_name == "pieChart":
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
        cats = [f"Category {i + 1}" for i in range(max_vals)]

    # Major gridlines
    grid_y = bool(plot_elem.find(".//c:valAx//c:majorGridlines", ns) is not None)

    return ChartData(
        v=2,
        kind=kind,
        title=title,
        legend=legend,
        grid_y=grid_y,
        cats=cats,
        series=series_list,
    )


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
