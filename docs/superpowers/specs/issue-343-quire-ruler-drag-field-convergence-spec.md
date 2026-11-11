# Design Specification: Issue #343 — Quire Interactive Canvas Ruler & Dynamic Fields Convergence

## 1. Overview & Objectives
This specification designs the full desktop interactive authoring fidelity for Quire's canvas rulers and multi-pass dynamic field convergence in ATBOffice (Word 2003 port):
1. **Interactive Ruler Manipulation**:
   - First-line indent (`first`), hanging indent (`hang`), left indent (`left`), and right indent (`right`) drag-and-drop.
   - Left and right page margin dragging on horizontal ruler; top and bottom page margin dragging on vertical ruler.
   - Tab stop creation, moving, and deletion (drag off ruler > 18px).
   - Real-time dotted alignment guideline overlays on `WriterCanvasView` during dragging.
   - Double-clicking opens `TabsDialog` (on text area/tab stops) or `PageSetupDialog` (on margins).
2. **Transactional Undo/Redo**:
   - Wrap indent, tab stop, and margin mutations in undoable command records.
   - Maintain `_undo_stack` and `_redo_stack` on `WriterCanvasView` / `QuireView`.
   - Provide `undo()` and `redo()` actions connected to Quire's command registry and keyboard shortcuts (`Ctrl+Z`, `Ctrl+Y`).
3. **Multi-Pass Dynamic Field Convergence**:
   - In `paginate_document()`, execute iterative pagination passes (up to `max_passes = 4`) until dynamic fields (`PAGE`, `NUMPAGES`, `SECTIONPAGES`, `SECTION`, `DATE`, `TIME`, and `TOC` / `PAGEREF`) stabilize.
   - Guard against circular oscillation loops by recording pagination states `(total_pages, section_pages)`.

---

## 2. Architecture & Components

```
┌────────────────────────────────────────────────────────┐
│                      QuireView                         │
│  ┌──────────────┐ ┌──────────────────────────────────┐ │
│  │ TabSelector  │ │         HorizontalRuler          │ │
│  └──────────────┘ └──────────────────────────────────┘ │
│  ┌──────────────┐ ┌──────────────────────────────────┐ │
│  │VerticalRuler │ │         WriterCanvasView         │ │
│  │              │ │   ┌────────────────────────────┐ │ │
│  │              │ │   │       CaretController      │ │ │
│  │              │ │   │   - DocPos / Selection     │ │ │
│  │              │ │   └────────────────────────────┘ │ │
│  │              │ │   - _ruler_guide_x / y overlay  │ │ │
│  │              │ │   - _undo_stack / _redo_stack   │ │ │
│  └──────────────┘ └──────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
                            │
               paginate_document(doc, max_passes)
                            │
                            ▼
 ┌───────────────────────────────────────────────────────┐
 │       Multi-Pass Dynamic Field Convergence Loop       │
 │                                                       │
 │   Pass 1: _execute_single_pagination_pass(doc)        │
 │              │                                        │
 │              ▼                                        │
 │   update_fields(doc, res)  (PAGE/NUMPAGES/TOC/...)    │
 │              │                                        │
 │        Field Changed?                                 │
 │        ├─► No: Converged! Return res                  │
 │        └─► Yes: State in seen_states?                 │
 │             ├─► Yes: Break oscillation & return res   │
 │             └─► No: Pass 2..max_passes                │
 └───────────────────────────────────────────────────────┘
```

---

## 3. Detailed Design

### 3.1 Interactive Ruler Undo/Redo Transaction Integration
In `WriterCanvasView`:
- Fields:
  - `self._undo_stack: list[dict[str, Any]] = []`
  - `self._redo_stack: list[dict[str, Any]] = []`
- Methods:
  - `push_undo_command(cmd: dict[str, Any]) -> None`: clears redo stack, appends to undo stack.
  - `undo() -> bool`: pops command, reverses changes to paragraph/section, calls `controller.repaginate_and_refresh()`, pushes to redo stack, returns True.
  - `redo() -> bool`: pops command, reapplies changes to paragraph/section, calls `controller.repaginate_and_refresh()`, pushes to undo stack, returns True.
  - `can_undo() -> bool`, `can_redo() -> bool`.
- Supported Actions:
  1. `"paragraph_indent"`: stores `para_id`, `before={"indent_left", "indent_first", "indent_right"}`, `after={...}`.
  2. `"paragraph_tabs"`: stores `para_id`, `before=list[TabStop]`, `after=list[TabStop]`.
  3. `"section_margins"`: stores `sect`, `before={"ml", "mr", "mt", "mb"}`, `after={...}`.

### 3.2 Ruler Handle Release & Guide Lines
In `HorizontalRuler`:
- `mousePressEvent`:
  - Store initial values of `indent_left`, `indent_first`, `indent_right`, `p.p_pr.tabs`, and `sect.ml`, `sect.mr`.
  - Request vertical guide line: `self.guide_line_requested.emit(canvas_x, True)`.
- `mouseMoveEvent`:
  - Update guide line position dynamically with snapping grid (or Alt-override).
- `mouseReleaseEvent`:
  - Clear guide line: `self.guide_line_cleared.emit()`.
  - If indents changed, push `"paragraph_indent"` command to `canvas_view._undo_stack`.
  - If tabs changed or added/removed, push `"paragraph_tabs"` command.
  - If margins changed, push `"section_margins"` command.
  - Repaginate and refresh canvas and rulers.

In `VerticalRuler`:
- `mousePressEvent`: store initial `sect.mt`, `sect.mb`. Request horizontal guide line.
- `mouseMoveEvent`: update guide line.
- `mouseReleaseEvent`: clear guide line, apply margins, push `"section_margins"` command, repaginate and refresh.

### 3.3 Double-Click Dialog Integration
In `QuireView` (`src/atboffice/modules/writer/view.py`):
- Connect:
  - `self.h_ruler.tabs_dialog_requested.connect(self._on_tabs_dialog_requested)`
  - `self.h_ruler.page_setup_requested.connect(self._on_page_setup_requested)`
  - `self.v_ruler.page_setup_requested.connect(self._on_page_setup_requested)`
- Implementation:
  - `_on_tabs_dialog_requested`:
    - Reads active paragraph and default tab stop.
    - Launches `TabsDialog(parent=self, tabs=..., default_tab=...)`.
    - On accept: commits tab changes with undo transaction and repaginates.
  - `_on_page_setup_requested`:
    - Reads active section.
    - Launches `PageSetupDialog(sect=..., parent=self)`.
    - On accept: commits margins/orientation changes with undo transaction and repaginates.

### 3.4 Multi-Pass Dynamic Field Convergence
In `src/atboffice/modules/writer/layout/pagination.py`:
- Function `paginate_document(doc: Document, max_passes: int = 4) -> PaginationResult`:
  - Loop up to `max_passes`:
    1. `res = _execute_single_pagination_pass(doc)`
    2. `doc._last_pagination = res`
    3. `changed = update_fields(doc, res)`
    4. Signature: `sig = (res.total_pages, tuple(res.section_pages))`
    5. If not `changed` and (not doc.hf or pass_idx > 1):
       - Layout converged. Break.
    6. If `sig in seen_signatures`:
       - Circular oscillation detected. Break to prevent infinite loop.
    7. `seen_signatures.add(sig)`
  - Ensure duration and final pagination result are returned.

---

## 4. Verification Plan
- Unit tests for undo/redo stack on indent/tab/margin manipulations.
- Unit tests for `paginate_document` multi-pass convergence across single-to-multi-page transitions and oscillation prevention.
- GUI tests in `tests/gui/test_phase9_ruler_and_field_convergence.py`:
  - Dragging first/hanging/left/right indents with guideline emissions and transactional undo/redo.
  - Dragging tabs (adding, moving, dragging off ruler >18px to delete) with undo/redo.
  - Margin dragging on H and V rulers with undo/redo.
  - Double-click triggers for `TabsDialog` and `PageSetupDialog`.
  - Multi-pass dynamic field convergence testing `PAGE`, `NUMPAGES`, `DATE`, `TIME`, and `TOC`/`PAGEREF`.
- Verify full test suite passes under `QT_QPA_PLATFORM=offscreen`.
