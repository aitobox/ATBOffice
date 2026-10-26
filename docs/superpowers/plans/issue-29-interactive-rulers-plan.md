# Implementation Plan: Issue #29 - Quire 交互式双向标尺 (水平/垂直标尺、页边距、缩进游标与制表位)

## Task Breakdown & Execution Steps

### Task 1: Paragraph Model Indent Property Wrappers
- **Files**: `src/atboffice/modules/writer/models/document.py`
- **Changes**: Add property getters and setters on `Paragraph`:
  - `indent_left` <-> `p_pr.ind.left`
  - `indent_right` <-> `p_pr.ind.right`
  - `indent_first` <-> `p_pr.ind.first_line`
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_dmodel.py -v`

### Task 2: Ruler Guide Line Support in `WriterCanvasView`
- **Files**: `src/atboffice/modules/writer/views/canvas_view.py`
- **Changes**:
  - Add fields `_ruler_guide_x: float | None = None` and `_ruler_guide_y: float | None = None`.
  - Add `set_ruler_guide(x: float | None = None, y: float | None = None) -> None` and `clear_ruler_guide() -> None`.
  - Update `paintEvent` to draw vertical/horizontal dashed guide line across the canvas when guide coordinates are set.
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_writer_canvas.py -v`

### Task 3: Implement `src/atboffice/modules/writer/views/ruler.py`
- **Files**: `src/atboffice/modules/writer/views/ruler.py`
- **Changes**:
  - `RulerUnit`: Enum (`CM`, `INCH`, `PT`).
  - `TabType`: Enum (`LEFT`, `CENTER`, `RIGHT`, `DECIMAL`, `BAR`, `FIRST_LINE`, `HANGING`).
  - `TabSelectorWidget`: Cycle through tab types, draw vector icons, emit signal.
  - `HorizontalRuler`:
    - Draw page boundary, margins, and text white area.
    - Draw ticks and numbers based on active unit (`cm`, `inch`, `pt`).
    - Markers: First Line Indent (downward triangle), Hanging Indent (upward triangle), Left Indent (rectangle bottom), Right Indent (upward triangle), Custom Tab Stops.
    - Drag interaction: updates marker position, emits guide line on canvas, snaps to grid (Alt key disables snap).
    - Drag tab stop outside vertical ruler area (> 18px) flags deletion.
    - On mouse release: commits indent / tab stop changes to active `Paragraph` and triggers repagination.
    - Double click: emits tab settings or page setup signal.
  - `VerticalRuler`:
    - Draw vertical page margins and body height.
    - Draggable top and bottom margin dividers.
    - Emits horizontal guide line on canvas.
    - On mouse release: updates Section margin (`mt`, `mb`) and repaginates.
  - Full `safe_tr()` and `retranslate_ui()` support.

### Task 4: Integrate Rulers into `WriterView`
- **Files**: `src/atboffice/modules/writer/view.py`
- **Changes**:
  - Replace simple layout with `QGridLayout`:
    - (0, 0): `TabSelectorWidget`
    - (0, 1): `HorizontalRuler`
    - (1, 0): `VerticalRuler`
    - (1, 1): `WriterCanvasView`
  - Connect signals:
    - Canvas scrollbar changes -> update ruler offsets.
    - Canvas zoom changes -> update ruler zoom.
    - Canvas caret / selection changes -> update ruler paragraph & section metrics.
    - Ruler guide line signals -> `canvas_view.set_ruler_guide` / `clear_ruler_guide`.
  - Retranslate UI support.

### Task 5: Comprehensive GUI Test Suite
- **Files**: `tests/gui/test_ruler.py`
- **Changes**:
  - Test unit conversion and tick calculations (`cm`, `inch`, `pt`).
  - Test `TabSelectorWidget` cycling.
  - Test `HorizontalRuler` marker geometry and drag handling (first, left, hang, right).
  - Test adding and deleting tab stops.
  - Test guide line projection on canvas.
  - Test `VerticalRuler` margin dragging.
  - Test `WriterView` integration and synchronized scrolling.
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_ruler.py -v`

### Task 6: Full Regression Verification
- **Verification**: Run entire test suite `PYTHONPATH=src conda run -n ATBOffice pytest tests/` to confirm 0 failures and zero regressions.
