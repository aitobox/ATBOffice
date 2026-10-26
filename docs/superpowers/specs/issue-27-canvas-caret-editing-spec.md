# Specification: Issue #27 [Quire] 分页纸张画布视口与原位光标编辑控制器 (Caret, Selection, Typing)

## 1. Overview & Context

### 1.1 Background
In ATBOffice Quire (the Word 2003 word processor port), the document layout engine (`portions.py`) and dynamic multi-page pagination engine (`pagination.py`) are implemented, generating physical `Page`, `ColumnFrame`, `PageFragment`, and `LayoutLine` structures.
The next critical step is to provide a high-fidelity visual editing canvas viewport (`WriterCanvasView`) and an in-place caret and selection controller (`CaretController`), matching Word 2003 user experience and `.vibeoffice` reference implementation (`render.js`, `editor.js`).

### 1.2 User Requirements & Acceptance Criteria
1. **Physical Paper Canvas View (`WriterCanvasView`)**:
   - High-fidelity visual appearance of Word 2003: neutral gray background, crisp white paper pages with classic drop shadow and 1px page boundary.
   - Support arbitrary zoom levels from 50% to 400% (e.g., 50%, 75%, 100%, 125%, 150%, 200%, 400%) or Fit to Width / Fit Page.
   - Multi-page layout: vertical sequential stacking with page spacing (default 24px) or dual-page side-by-side mode.
   - High DPI scaling awareness and clipped, virtualized rendering.
2. **In-place Caret & Selection Controller (`CaretController`)**:
   - Accurate cursor positioning: coordinates calculated from pagination data down to points and pixels.
   - Cursor blinking: 500ms toggle timer with instant-reset to visible on user interaction.
   - Keyboard navigation: Left/Right/Up/Down arrow keys, Home/End, PageUp/PageDown, with preferred horizontal column tracking during vertical navigation.
   - Mouse interaction:
     - Single click: binary search character hit-testing on the clicked line.
     - Mouse drag: smooth continuous text selection.
     - Double-click: word boundary selection.
     - Triple-click: whole paragraph selection.
   - Text editing operations:
     - Typing printable characters: inserts text at caret, auto-advances caret, triggers pagination and view update.
     - Backspace: deletes previous character, or deletes active selection. If at start of paragraph (offset 0), merges paragraph with previous paragraph.
     - Delete key: deletes next character, or deletes active selection. If at end of paragraph, merges next paragraph into current.
     - Enter / Return key: splits current paragraph into two paragraphs at caret position.
3. **i18n & Localization**:
   - 100% UI strings wrapped in `tr()` / `safe_tr()`.
   - Complete `retranslate_ui()` implementation.
4. **Verification**:
   - Comprehensive test suite in `tests/gui/test_writer_canvas.py` passing 100%.

---

## 2. Architecture & Components

```
┌─────────────────────────────────────────────────────────────┐
│                       WriterView                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   WriterCanvasView                    │  │
│  │   (QAbstractScrollArea with virtualized multi-page)   │  │
│  │                                                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │                CaretController                  │  │  │
│  │  │   - Caret blinking timer (500ms)                │  │  │
│  │  │   - Navigation (Arrow keys, Home, End)          │  │  │
│  │  │   - Hit-testing (Binary search in LayoutLine)   │  │  │
│  │  │   - Selection (Single, Double, Triple-click)    │  │  │
│  │  │   - Text insertion, Backspace, Split/Merge      │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                               ▲
                               │
            ┌──────────────────┴──────────────────┐
            │ Document Model & Pagination Engine  │
            │  - Document, Paragraph, TextItem    │
            │  - paginate_document()              │
            │  - Page, ColumnFrame, PageFragment  │
            └─────────────────────────────────────┘
```

### 2.1 Coordinate Systems
1. **Document Logical Points (pt)**:
   - 72 pt = 1 inch (e.g. A4: 595.3 pt x 841.9 pt; Letter: 612 pt x 792 pt).
   - All layout structures (`Page`, `LayoutLine`, `Portion`) use pt.
2. **Page-Relative Coordinates (pt)**:
   - (0, 0) is the top-left of the physical paper page.
3. **Canvas Virtual Coordinates (px)**:
   - `px = pt * (DPI / 72.0) * zoom_factor`.
   - Standard 96 DPI: 1 pt = 4/3 px (~1.3333 px).
   - Pages are positioned vertically with `page_gap` (e.g. 24 px).
4. **Viewport Coordinates (px)**:
   - `viewport_x = canvas_x - horizontalScrollBar().value()`
   - `viewport_y = canvas_y - verticalScrollBar().value()`

---

## 3. Data Models & API Contracts

### 3.1 `DocPos` & `Selection`
```python
@dataclass(frozen=True)
class DocPos:
    para_id: int
    offset: int

@dataclass
class Selection:
    anchor: DocPos
    focus: DocPos

    @property
    def is_collapsed(self) -> bool:
        return self.anchor.para_id == self.focus.para_id and self.anchor.offset == self.focus.offset
```

### 3.2 `CaretController`
- `pos: DocPos` (caret location)
- `selection: Selection`
- `preferred_x: float | None` (persisted horizontal coordinate during vertical line navigation)
- `pos_to_canvas(pos: DocPos) -> tuple[int, QPointF, float]`:
  Finds the page index, point on page, and line height for `pos`.
- `canvas_to_pos(page_idx: int, point_pt: QPointF) -> DocPos`:
  Performs binary search within `LayoutLine` portions to find closest character offset.
- `handle_key_event(event: QKeyEvent) -> bool`:
  Dispatches typing, backspace, enter, arrows, selection extensions.
- `handle_mouse_press(page_idx: int, point_pt: QPointF, button: Qt.MouseButton, modifiers: Qt.KeyboardModifiers, click_count: int)`
- `handle_mouse_move(page_idx: int, point_pt: QPointF)`

### 3.3 `WriterCanvasView`
- `set_document(doc: Document)`
- `set_zoom(factor: float)` (clamped between 0.5 and 4.0)
- `paintEvent(event: QPaintEvent)`:
  - Paints viewport background.
  - Loops over visible pages (viewport clipping).
  - Paints drop shadow and paper white background.
  - Paints text runs, underlines, text highlights.
  - Paints selection highlight rects.
  - Paints blinking caret.
- `retranslate_ui()`: Localizes status strings and tooltips.

---

## 4. Edge Cases & Pre-Implementation Reflection

1. **Empty Paragraphs**:
   - Paragraph has no runs or only empty TextItem.
   - `LayoutLine` has height = single line height of paragraph font (e.g. 15.6pt for 12pt font). Caret must appear at `(body_left, col_top)` with correct line height.
2. **Clicking in Margins / Page Gaps**:
   - If user clicks in left/right margin: caret snaps to start of line or end of nearest line.
   - If user clicks below last paragraph: caret snaps to end of last paragraph.
   - If user clicks above first page: snaps to beginning of first paragraph.
3. **Paragraph Merging & Splitting**:
   - When hitting Return: split text and runs at caret offset into a new Paragraph, insert into story, reindex, repaginate.
   - When hitting Backspace at offset 0: if previous block is a Paragraph, append all runs of current paragraph to previous paragraph, remove current paragraph, repaginate.
4. **Selection Rects**:
   - Multi-line selection: line 1 highlights from `offset` to line end; middle lines highlight full width; last line highlights from line start to `end_offset`.
   - Multi-paragraph selection: highlights all fragments across paragraphs.
5. **Zoom & Window Resizing**:
   - Zoom changes scroll ranges and cursor pixel positions dynamically.
   - Canvas centers pages horizontally when viewport is wider than page width.

---

## 5. Verification Plan
- Unit and GUI test file: `tests/gui/test_writer_canvas.py`
- Test cases:
  1. Canvas initialization, default zoom (100%), zoom limits (50%~400%), fit width.
  2. Multi-page layout geometry and visible page calculation.
  3. Caret coordinate conversion and hit-testing with binary search.
  4. Cursor blinking timer and reset on movement.
  5. Arrow key navigation (Left, Right, Up, Down, Home, End).
  6. Double-click word selection, triple-click paragraph selection.
  7. Typing characters and backspace / delete handling.
  8. Paragraph splitting (Enter) and paragraph merging (Backspace at index 0).
  9. Selection highlight bounding rect calculations.
  10. i18n retranslation and safe_tr verification.
