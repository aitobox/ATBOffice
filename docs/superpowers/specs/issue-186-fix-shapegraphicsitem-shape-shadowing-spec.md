# Specification: Issue #186 - Fix Presentation crash caused by ShapeGraphicsItem.shape attribute shadowing QGraphicsObject::shape()

## Problem Summary
When opening the Presentation (Lectern) module and hovering or moving the mouse across the slide canvas or over shapes, PySide6 triggers `QGraphicsObject::shape()` for scene graph hit-testing.
In `ShapeGraphicsItem.__init__`, `self.shape = shape` assigns the `Shape` dataclass model instance directly to `self.shape`. Because Python instance attributes shadow class methods, this replaces the virtual method `shape(self) -> QPainterPath` with a non-callable `Shape` instance.
When PySide6/Qt attempts to invoke `shape()` during mouse movement, it raises:
```text
TypeError: Error calling Python override of QGraphicsObject::shape(): 'Shape' object is not callable
```
leading to an unhandled exception inside the Qt C++ event loop and an immediate segmentation fault (SIGSEGV / exit code 139).

## Design & Architecture

### 1. Attribute Separation on `ShapeGraphicsItem`
- Rename `self.shape` to `self.model` (type `Shape`) on `ShapeGraphicsItem`.
- Retain the class method `shape(self) -> QPainterPath`:
  ```python
  def shape(self) -> QPainterPath:
      path = QPainterPath()
      path.addRect(0.0, 0.0, max(1.0, self.model.w), max(1.0, self.model.h))
      return path
  ```
- Ensure `callable(item.shape)` is True and `item.shape()` returns a valid `QPainterPath`.

### 2. Affected Presentation Components
- `src/atboffice/modules/presentation/views/shape_item.py`:
  - Update all internal usages of `self.shape` to `self.model`.
- `src/atboffice/modules/presentation/views/chart_item.py`:
  - Update `self.shape` references to `self.model`.
- `src/atboffice/modules/presentation/views/slide_canvas.py`:
  - Update all `item.shape` and `self._dragged_item.shape` references to `item.model` (e.g. z-order reordering, bounding rect calculations, alignment guides).
- `src/atboffice/modules/presentation/views/text_editor.py`:
  - Update `self.shape = shape_item.shape` to `self.shape = shape_item.model`.

### 3. Affected Test Suites
- Update test files that inspected `item.shape` to inspect `item.model`:
  - `tests/gui/test_lectern_pyramid_interactions.py`
  - `tests/gui/test_slide_canvas.py`
  - `tests/gui/test_textedit.py`
  - `tests/unit/presentation/test_chart_draw.py`

### 4. Regression Verification
- Add regression unit and GUI tests verifying:
  - `item.shape` is callable and returns a `QPainterPath`.
  - Calling `item.shape()` does not raise `TypeError`.
  - Dispatching `mouseMoveEvent` across a `SlideCanvas` containing `ShapeGraphicsItem` items executes cleanly with no exceptions or segfaults.

## Acceptance Criteria
- [x] `ShapeGraphicsItem.shape` is a callable virtual method returning `QPainterPath`.
- [x] `ShapeGraphicsItem.model` holds the `Shape` dataclass instance.
- [x] All presentation view callers (`slide_canvas.py`, `chart_item.py`, `text_editor.py`, `shape_item.py`) use `.model`.
- [x] Hovering and mouse move events on `SlideCanvas` do not crash or log `TypeError`.
- [x] Full existing test suite passes without regressions.
