# Implementation Plan: Issue #27 [Quire] 分页纸张画布视口与原位光标编辑控制器

## Overview
Implement the Word 2003 high-fidelity paper canvas viewport (`WriterCanvasView`) and in-place caret/selection controller (`CaretController`), with character-level binary search hit-testing, typing, backspace, paragraph splitting/merging, and smooth multi-page virtualized rendering.

---

## Tasks

### Task 1: Caret & Selection Data Models & CaretController Base
- **Files**:
  - `src/atboffice/modules/writer/views/__init__.py`
  - `src/atboffice/modules/writer/views/caret_controller.py`
  - `tests/gui/test_writer_canvas.py`
- **Details**:
  - Define `DocPos(para_id: int, offset: int)`.
  - Define `Selection(anchor: DocPos, focus: DocPos)`.
  - Implement `CaretController` with blink timer, document reference, pagination reference.
  - Implement tests verifying `DocPos` comparison, `Selection` order and collapsed status.

### Task 2: Binary Search Hit-Testing & Coordinate Conversions
- **Files**:
  - `src/atboffice/modules/writer/views/caret_controller.py`
- **Details**:
  - Implement `pos_to_canvas(pos: DocPos) -> tuple[int, QPointF, float]`:
    - Traverses `Page`, `PageRegion`, `ColumnFrame`, `PageFragment`, `LayoutLine`, and `Portion`.
    - Returns physical page index, page-relative `QPointF(x, y)` in points, and caret height in points.
  - Implement `canvas_to_pos(page_idx: int, point_pt: QPointF) -> DocPos`:
    - Locates nearest `Page`, `ColumnFrame`, `PageFragment`, and `LayoutLine`.
    - Binary search on character widths within text portions on the line to find closest character offset.
  - Boundary snapping for clicks outside margins or beyond text edges.

### Task 3: Caret Navigation & Selection Modes
- **Files**:
  - `src/atboffice/modules/writer/views/caret_controller.py`
- **Details**:
  - Left / Right navigation with run/line/paragraph boundary crossing.
  - Up / Down navigation with preferred x column tracking across lines.
  - Home / End navigation (line start / line end).
  - Mouse click, drag selection.
  - Double-click word selection: regex word boundaries `\w+`.
  - Triple-click paragraph selection: `[0, plen(p)]`.

### Task 4: In-Place Typing, Backspace, Split & Merge Editing Operations
- **Files**:
  - `src/atboffice/modules/writer/views/caret_controller.py`
  - `src/atboffice/modules/writer/models/document.py` (if helpers needed)
- **Details**:
  - `insert_text(text: str)`: inserts text into the active paragraph run, advances caret offset, requests repagination.
  - `delete_backspace()`:
    - If selection active: deletes selected range.
    - If collapsed: deletes character before caret.
    - If offset == 0: merges current paragraph with previous paragraph.
  - `delete_forward()`:
    - If selection active: deletes selected range.
    - If collapsed: deletes character after caret.
    - If offset == plen(p): merges next paragraph into current.
  - `insert_paragraph_break()`: splits paragraph into two at caret offset.

### Task 5: Word 2003 High-Fidelity Canvas View (`WriterCanvasView`)
- **Files**:
  - `src/atboffice/modules/writer/views/canvas_view.py`
  - `src/atboffice/modules/writer/view.py`
- **Details**:
  - Inherit from `QAbstractScrollArea`.
  - Classic Word 2003 palette: neutral gray workspace background (`#8A8A8A`), paper white (`#FFFFFF`), drop shadow (`#3A3A3A` with blur/layered offsets), 1px border.
  - Support zoom levels 50% to 400% (`set_zoom`), fit width, fit page.
  - Paint visible pages clipped to viewport.
  - Paint text portions with proper fonts, sizes, decorations (bold, italic, underline, highlight).
  - Paint selection highlights spanning lines and paragraphs.
  - Paint blinking caret at exact sub-pixel position.
  - Event dispatching: `paintEvent`, `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`, `mouseDoubleClickEvent`, `keyPressEvent`, `resizeEvent`, `focusInEvent`, `focusOutEvent`.
  - Implement `retranslate_ui()` with `safe_tr()`.

### Task 6: Integration & Comprehensive GUI Tests
- **Files**:
  - `tests/gui/test_writer_canvas.py`
- **Details**:
  - Test canvas initialization, zoom scaling, page layout.
  - Test hit testing, binary search character accuracy.
  - Test arrow navigation and preferred-x behavior.
  - Test typing, backspace, paragraph splitting and merging.
  - Test double-click and triple-click selection.
  - Test selection rectangle calculation.
  - Test full suite verification.

---

## Verification
- Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_writer_canvas.py -v`
- Run full repository pytest suite: `PYTHONPATH=src conda run -n ATBOffice pytest tests/`
