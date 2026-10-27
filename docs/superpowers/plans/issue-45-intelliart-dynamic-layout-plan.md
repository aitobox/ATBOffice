# Implementation Plan: [Lectern] IntelliArt 26 种智能图示动态排版与文本大纲双向联动 (Issue #45)

## Overview
Implement the full IntelliArt (SmartArt compatible) diagramming system for Lectern in Python/PySide6, covering 26 layouts across 7 categories, adaptive text fitting, outline text pane with keyboard shortcuts, professional palettes and styles, and PPTX SmartArt XML export.

---

## Task Breakdown

### Task 1: Extend Shape Model for SmartArt Metadata
- **Files**: `src/atboffice/modules/presentation/models/shape.py`
- **Actions**:
  - Add `sa: dict[str, Any] | None = None` and `poly: list[list[float]] | None = None` to `Shape` dataclass.
  - Update `to_dict()` and `from_dict()` to serialize and restore `sa` and `poly`.
  - Add helper methods `is_diagram`, `diagram_root` if applicable.

### Task 2: Implement SmartArt Engine
- **Files**: `src/atboffice/modules/presentation/smartart/engine.py`
- **Actions**:
  - Implement text fitting (`measure`, `wrap_text`, `fit_text`) with binary search in `[6, 40]` pt.
  - Implement 26 layouts across 7 categories (`list`, `process`, `cycle`, `hierarchy`, `relationship`, `matrix`, `pyramid`).
  - Implement tree operations: `blank`, `outline`, `locate`, `add_after`, `add_before`, `add_above`, `add_below`, `promote`, `demote`, `move_up`, `move_down`, `remove_item`.
  - Implement 15 color palettes and 11 style textures with color mixing and opacity.
  - Implement `paint_shape` and `relayout(group_shape, design)`.
  - Implement `to_shapes(group_shape)` to convert diagrams to plain shape groups.

### Task 3: Implement SmartArt PPTX XML I/O
- **Files**:
  - `src/atboffice/modules/presentation/smartart/io.py`
  - `src/atboffice/modules/presentation/io/pptx_writer.py`
- **Actions**:
  - Implement DrawingML Diagram XML generation: `dataModel`, `layout`, `colors`, `quickStyle`.
  - In `pptx_writer.py`, when a slide contains group shapes with `sa`, generate corresponding `ppt/diagrams/data{N}.xml` and relationship entries.

### Task 4: Implement Text Outline Pane Widget
- **Files**: `src/atboffice/modules/presentation/smartart/text_pane.py`
- **Actions**:
  - Build `SmartArtTextPane(QWidget)` displaying tree-indented input fields for outline items.
  - Implement keyboard shortcuts: `Enter` (add after), `Tab` (demote), `Shift+Tab` (promote), `Alt+Shift+Up/Down` (reorder), `Backspace` (delete empty item).
  - Implement action buttons: Add Shape, Promote, Demote, Move Up, Move Down, Reset Graphic, Convert to Shapes.
  - Connect text changes to `engine.relayout()` and emit update signals for canvas synchronization.
  - Full i18n support with `safe_tr()` / `tr()` and `retranslate_ui()`.

### Task 5: Integrate with Presentation Workspace
- **Files**:
  - `src/atboffice/modules/presentation/views/workspace.py`
  - `src/atboffice/modules/presentation/views/slide_canvas.py`
- **Actions**:
  - Add Insert IntelliArt action and gallery trigger.
  - When a SmartArt group shape is selected, show/activate the SmartArt Text Pane.
  - When SmartArt is modified in the text pane, trigger scene update and repaint.

### Task 6: Unit Test Suite
- **Files**: `tests/unit/presentation/test_smartart.py`
- **Actions**:
  - Verify all 26 layouts for 1 to 7 items (bounds, finite coordinates, node count, uniform font size).
  - Verify adaptive font sizing with long vs short text.
  - Verify outline tree manipulation operations.
  - Verify color palettes and style generation.
  - Verify conversion to shapes.
  - Verify DrawingML Diagram XML structure generation.
  - Verify `SmartArtTextPane` keyboard interactions and signal emissions.

### Task 7: Full Test Suite Verification & Quality Audit
- **Command**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/test_smartart.py -v`
- Confirm all tests pass with zero errors.
