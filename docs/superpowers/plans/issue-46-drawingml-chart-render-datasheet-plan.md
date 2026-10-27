# Implementation Plan: DrawingML Vector Chart Rendering & Datasheet Synchronization

- **Issue**: #46 ([Lectern] 幻灯片 DrawingML 矢量图表渲染与数据表联动)
- **Branch**: `agent/issue-46-drawingml-chart-render-datasheet`
- **Spec**: `docs/superpowers/specs/issue-46-drawingml-chart-render-datasheet-spec.md`

---

## Task Breakdown

### Task 1: Chart Data Models & Scaling Algorithms
- **Files**:
  - `src/atboffice/modules/presentation/chart/model.py`
  - `src/atboffice/modules/presentation/chart/scale.py`
  - `src/atboffice/modules/presentation/chart/__init__.py`
  - `tests/unit/presentation/test_chart_draw.py` (scale tests)
- **Details**:
  - Data structures: `ChartData`, `SeriesData`, `CH_KINDS`, `CH_PALETTE`, default sample chart.
  - Scale engine: `scale(lo, hi, ax, len, label_sz, opts)`, `nice_step(raw)`, `format_val(v, code)`.
  - Handle zero spans, logarithmic scales, negative numbers, custom min/max.

### Task 2: DrawingML 17-Type Vector Renderer (`ChartPainter`)
- **Files**:
  - `src/atboffice/modules/presentation/chart/painter.py`
- **Details**:
  - Pure PySide6 `QPainter` drawing logic:
    - Background, borders, title with multiline wrapping.
    - Legend layout (Right, Bottom, Top, Left) with swatches and labels.
    - Plot area coordinates computation.
    - Gridlines (major value gridlines) and axis lines/ticks.
    - 17 Chart Types:
      - Column (`col`, `colStacked`, `colPct`)
      - Bar (`bar`, `barStacked`, `barPct`)
      - Line (`line`, `lineMarkers`) with straight/smooth Bézier curves & markers
      - Area (`area`, `areaStacked`, `areaPct`)
      - Pie (`pie`) and Doughnut (`doughnut`)
      - Scatter (`scatter`) and Bubble (`bubble`)
      - Radar (`radar`, `radarFilled`)
    - Theme color resolution & fallback palette.

### Task 3: DrawingML XML Serialization & PPTX Roundtrip
- **Files**:
  - `src/atboffice/modules/presentation/chart/io.py`
  - `src/atboffice/modules/presentation/models/shape.py`
  - `src/atboffice/modules/presentation/io/writer_shapes.py`
  - `src/atboffice/modules/presentation/io/pptx_writer.py`
  - `src/atboffice/modules/presentation/io/pptx_reader.py`
- **Details**:
  - `chart_to_xml(chart_dict, design)` -> `<c:chartSpace>` according to DrawingML chart specs.
  - `parse_chart_xml(xml_content)` -> chart dictionary.
  - Shape model: support `chart` attribute on `Shape`.
  - In `writer_shapes.py`: serialize chart shapes to `<p:graphicFrame>` referencing chart `rId`.
  - In `pptx_writer.py`: write `ppt/charts/chart{n}.xml` and embedded workbook data `ppt/embeddings/`.
  - In `pptx_reader.py`: parse `<p:graphicFrame>` with chart `graphicData` into `Shape(type="chart", chart=...)`.

### Task 4: Datasheet Editor Dialog (`DatasheetDialog`)
- **Files**:
  - `src/atboffice/modules/presentation/dialogs/__init__.py`
  - `src/atboffice/modules/presentation/dialogs/datasheet_dialog.py`
- **Details**:
  - `ChartPreviewWidget`: QWidget displaying live preview of the chart.
  - Controls: Type dropdown (17 types), Title editor, Legend position, Grid/Labels checkboxes.
  - Datasheet Table (`QTableWidget`):
    - Columns: categories.
    - Rows: series names, colors, cell values.
    - Toolbar: Add Column, Delete Column, Add Row, Delete Row.
    - Color swatch button per series with `QColorDialog`.
  - Full i18n support with `safe_tr()` and `retranslate_ui()`.

### Task 5: Interactive Canvas Item (`ChartGraphicsItem`) & Canvas Integration
- **Files**:
  - `src/atboffice/modules/presentation/views/chart_item.py`
  - `src/atboffice/modules/presentation/views/slide_canvas.py`
  - `src/atboffice/modules/presentation/views/__init__.py`
- **Details**:
  - `ChartGraphicsItem` inherits `ShapeGraphicsItem`.
  - Custom `paint()` invoking `ChartPainter`.
  - `mouseDoubleClickEvent()` launches `DatasheetDialog`.
  - Updates shape model and triggers canvas repaint upon dialog accept.
  - Wire into `SlideCanvas` shape instantiation.

### Task 6: Unit Testing & Verification
- **Files**:
  - `tests/unit/presentation/test_chart_draw.py`
- **Details**:
  - Unit tests covering scale calculations, all 17 layout kinds, XML serialization, and UI dialog instantiation.
  - Run `ruff check .` to guarantee 0 lint/formatting errors.
  - Run `pytest` to guarantee 100% pass rate.
