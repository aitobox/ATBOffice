# Specification: DrawingML Vector Chart Rendering & Datasheet Synchronization

- **Parent Issue**: #46 ([Lectern] 幻灯片 DrawingML 矢量图表渲染与数据表联动)
- **Parent Epic**: #38 (Lectern PowerPoint 2003 Engine Porting)
- **Status**: Draft -> Accepted
- **Author**: Antigravity Agent
- **Target Files**:
  - `src/atboffice/modules/presentation/views/chart_item.py`
  - `src/atboffice/modules/presentation/dialogs/datasheet_dialog.py`
  - `src/atboffice/modules/presentation/chart/` (engine, scales, models, io)
  - `src/atboffice/modules/presentation/models/shape.py`
  - `src/atboffice/modules/presentation/io/writer_shapes.py`
  - `src/atboffice/modules/presentation/io/pptx_writer.py`
  - `src/atboffice/modules/presentation/io/pptx_reader.py`
  - `tests/unit/presentation/test_chart_draw.py`

---

## 1. Executive Summary & Goals

This specification defines the architecture, data models, rendering engine, and user interaction for DrawingML vector charts in Lectern (PowerPoint 2003/2007+ compatible).

Key capabilities:
1. **17 Chart Types**:
   - Column: `col` (Clustered Column), `colStacked` (Stacked Column), `colPct` (100% Stacked Column)
   - Bar: `bar` (Clustered Bar), `barStacked` (Stacked Bar), `barPct` (100% Stacked Bar)
   - Line: `line` (Line), `lineMarkers` (Line with Markers)
   - Area: `area` (Area), `areaStacked` (Stacked Area), `areaPct` (100% Stacked Area)
   - Pie & Doughnut: `pie` (Pie), `doughnut` (Doughnut)
   - Scatter & Bubble: `scatter` (XY Scatter), `bubble` (Bubble)
   - Radar: `radar` (Radar), `radarFilled` (Filled Radar)
2. **Axis & Auto-scaling Engine**:
   - Office-compliant automatic interval scale algorithm (`scale()`).
   - Major/minor gridlines, logarithmic scale (`logBase`), reversed axes (`maxMin`), secondary axes.
   - Category axis (`catAx`) and Value axis (`valAx`).
3. **Datasheet Editor Dialog (`DatasheetDialog`)**:
   - Interactive modal with real-time live preview.
   - Edit categories and series names, values, colors.
   - Dynamic Add/Remove Rows and Columns.
   - Chart type selection and legend positioning.
   - 100% i18n support with `safe_tr()` and `retranslate_ui()`.
4. **DrawingML / OpenXML Persistence**:
   - Roundtrip fidelity: serialize to `<c:chartSpace>`, `<c:plotArea>`, `<p:graphicFrame>`.
   - Preserve embedded Excel worksheet binary / XML stream (`ppt/embeddings/`).

---

## 2. Architecture & Module Structure

```
src/atboffice/modules/presentation/
├── chart/
│   ├── __init__.py           # Export chart types, models, render helper
│   ├── model.py              # ChartData, SeriesData, AxisConfig dataclasses
│   ├── scale.py              # Office auto-scaling, niceStep, log scale algorithms
│   ├── painter.py            # QPainter DrawingML 17-type vector renderer
│   └── io.py                 # <c:chartSpace> XML generation & reader helper
├── dialogs/
│   ├── __init__.py
│   └── datasheet_dialog.py   # Datasheet Editor Dialog with live ChartPreviewWidget
└── views/
    ├── chart_item.py         # ChartGraphicsItem (subclass of ShapeGraphicsItem)
    └── slide_canvas.py       # Integration hook for chart items
```

---

## 3. Data Model

A chart is stored on a `Shape` via `shape.chart` (and `shape.type == "chart"`):

```python
chart_dict = {
    "v": 2,                           # DrawingML v2 model
    "kind": "col",                    # 17 chart types
    "title": "Quarterly Sales",
    "titleTx": {"sz": 14.0, "b": True, "color": "tx1"},
    "legend": "r",                    # 'r', 'b', 't', 'l', 'none'
    "gridY": True,                    # Show major value gridlines
    "labels": False,                  # Show data values or percentages
    "cats": ["1st Qtr", "2nd Qtr", "3rd Qtr", "4th Qtr"],
    "series": [
        {"name": "East", "vals": [20.4, 27.4, 90.0, 20.4], "color": "#4472C4"},
        {"name": "West", "vals": [30.6, 38.6, 34.6, 31.6], "color": "#ED7D31"},
        {"name": "North", "vals": [45.9, 46.9, 45.0, 43.9], "color": "#A5A5A5"},
    ],
    "ax": {
        "c": {"tick": "out", "rev": False},
        "v": {"grid": {"c": "#D9D9D9", "w": 0.75}, "min": None, "max": None, "log": None}
    },
    "embedded_workbook": b"...",      # Optional embedded XLSX data
}
```

---

## 4. Vector Renderer Specification (`painter.py`)

The `ChartPainter` uses `QPainter` to draw directly inside bounds `(w, h)`:
1. **Layout Allocations**:
   - Padding: 4% of dimension.
   - Title Box: top, center-aligned, measuring text height and advancing plot area.
   - Legend Box: right, bottom, top, or left. Swatches + labels.
   - Plot Area: remaining viewport bounded by `(plot_x, plot_y, plot_w, plot_h)`.
2. **Axis Tick & Label Rendering**:
   - `scale()` computes `{min, max, ticks, step}`.
   - Draw horizontal / vertical major gridlines in `#D9D9D9`.
   - Draw axis lines in `#868686`.
   - Draw tick marks and format tick values using `numfmt`.
3. **Series Geometry**:
   - **Column/Bar**: clustered bars with `gapWidth = 150`, stacked bars normalized or cumulative, 100% stacked normalized to 100%.
   - **Line/LineMarkers**: QPainterPath connecting data points with straight lines or cubic Bézier curves (smooth), plus distinct markers (Circle, Square, Diamond, Triangle).
   - **Area**: closed polygons with alpha fill.
   - **Pie/Doughnut**: `drawPie` / `drawPath` with slice angles, optional doughnut center hole (10%-90%).
   - **Scatter/Bubble**: cartesian X/Y mapping with proportional bubble circles.
   - **Radar**: concentric polygonal spider-webs with radial axes.
4. **Data Labels**:
   - Optional value labels rendered above bars or beside markers.

---

## 5. UI Interaction & Dialog (`datasheet_dialog.py`)

- **Trigger**: Double-clicking a `ChartGraphicsItem` on `SlideCanvas`.
- **Layout**:
  - Left panel: Type selector dropdown, Title text, Legend position combo, Grid/Labels checkboxes, Datasheet `QTableWidget`.
  - Right panel: `ChartPreviewWidget` live interactive preview.
- **Datasheet Table**:
  - Horizontal headers: Category names (editable).
  - Vertical headers: Series color swatch + Series names (editable).
  - Cells: Numerical values with validator.
  - Buttons: "Add Column", "Delete Column", "Add Row", "Delete Row".
  - Color Swatch: Click opens `QColorDialog` to customize series color.
- **i18n**: Full Chinese/English localized UI controls with `safe_tr()` and `retranslate_ui()`.

---

## 6. PPTX OpenXML Roundtrip

- **Reading**: `<p:graphicFrame>` with `<a:graphicData uri=".../chart">` reads `ppt/charts/chart{n}.xml` and parses `<c:chartSpace>` into `shape.chart`.
- **Writing**:
  - Slide XML emits `<p:graphicFrame>` referencing `rId` for chart.
  - Packager writes `ppt/charts/chart{n}.xml` with `<c:chartSpace>` and relationships.
  - Preserves or generates `Microsoft_Excel_Worksheet{n}.xlsx` in `ppt/embeddings/`.

---

## 7. Edge Cases Handled

1. All values zero or negative -> Scale algorithm guarantees non-zero span and positive headroom.
2. Single category or empty series -> Graceful fallback rendering with empty plot box.
3. Log scale with zero or negative values -> Clamped to min positive value.
4. 100% stacked series with zero sum -> Defaults to equal 0 height without `ZeroDivisionError`.
5. Non-numeric text entered in datasheet cells -> Sanitized to 0.0 with warnings.
6. Extreme aspect ratios (e.g. 50x500 or 1000x50) -> Clamped bounds and minimum label sizes.
