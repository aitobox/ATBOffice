# Implementation Plan: Issue #186 - Fix Presentation crash caused by ShapeGraphicsItem.shape attribute shadowing QGraphicsObject::shape()

## Overview
Rename the model attribute on `ShapeGraphicsItem` from `self.shape` to `self.model`, preserving `QGraphicsObject::shape()` as a callable method returning `QPainterPath`. Update all presentation view callers and tests, and add regression tests.

## Tasks

### Task 1: Write Reproduction / Regression Test
- **File**: `tests/gui/test_shape_graphics_item.py`
- **Actions**:
  - Test that `ShapeGraphicsItem` provides `.model` as the `Shape` dataclass.
  - Test that `item.shape` is callable and returns a `QPainterPath`.
  - Test that simulated `mouseMoveEvent` over `SlideCanvas` containing shapes triggers `shape()` hit-testing without `TypeError: 'Shape' object is not callable` or segfault.
- **Verification**: Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_shape_graphics_item.py` (initially fails on unpatched code).

### Task 2: Refactor `shape_item.py`
- **File**: `src/atboffice/modules/presentation/views/shape_item.py`
- **Actions**:
  - In `ShapeGraphicsItem.__init__`: change `self.shape = shape` to `self.model = shape`.
  - Update all internal usages from `self.shape` to `self.model`.
  - Verify `def shape(self) -> QPainterPath` uses `self.model.w` and `self.model.h`.

### Task 3: Update Callers in Presentation Views
- **Files**:
  - `src/atboffice/modules/presentation/views/chart_item.py`: change `self.shape` to `self.model`.
  - `src/atboffice/modules/presentation/views/slide_canvas.py`: change `item.shape` and `self._dragged_item.shape` to `.model`.
  - `src/atboffice/modules/presentation/views/text_editor.py`: change `shape_item.shape` to `shape_item.model`.

### Task 4: Update Existing Tests Accessing `.shape` as Model
- **Files**:
  - `tests/gui/test_lectern_pyramid_interactions.py`
  - `tests/gui/test_slide_canvas.py`
  - `tests/gui/test_textedit.py`
  - `tests/unit/presentation/test_chart_draw.py`
- **Actions**: Update references of `item.shape` to `item.model`.

### Task 5: Full Verification & Transition
- **Actions**:
  - Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_shape_graphics_item.py`
  - Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_slide_canvas.py`
  - Run full test suite: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
  - Transition state to `reviewing` and trigger `atb-github-code-reviewer`.
