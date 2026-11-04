# Implementation Plan: Issue #242 (TASK-708) — Fix Lectern PPTX Rendering and Roundtrip

## Task 1: Model & Writer Support for Text Autofit & Dimensions
- **Files**:
  - `src/atboffice/modules/presentation/models/text.py`
  - `src/atboffice/modules/presentation/io/writer_text.py`
- **Actions**:
  1. Ensure `TextBody` has `ln_spc_reduction: float = 0.0` alongside `font_scale: float = 1.0`, with proper serialization in `to_dict()` and `from_dict()`.
  2. In `writer_text.py`, when `autofit == "norm"`, write `<a:normAutofit fontScale="..." lnSpcReduction="..."/>` preserving non-default scales.
- **Verification**: Run unit tests on text model serialization and XML writing.

## Task 2: Parser Enhancements in `pptx_reader.py`
- **Files**:
  - `src/atboffice/modules/presentation/io/pptx_reader.py`
- **Actions**:
  1. **`normAutofit`**: Read `fontScale` and `lnSpcReduction` from `<a:normAutofit>` into `TextBody`.
  2. **SmartArt / Diagram**: In `_parse_graphic_frame`, check for `uri="http://schemas.openxmlformats.org/drawingml/2006/diagram"` or `<dgm:relIds>`. Read target `data1.xml` through relationship `dm`, parse `<dgm:pt>` nodes, and populate `Shape.sa` and `Shape.text = TextBody.from_text(...)`.
  3. **Master & Layout Decorations & Backgrounds**: In `_load_master` and `_load_layout`, parse non-placeholder shapes into `decorations`. Parse `<p:bg>` / `<p:bgPr>` into `design.bg` and `slide.bg`. Associate `slide.design_id` with master design.
  4. **Group Shapes**: Read `chOff` and `chExt` from `grpSpPr/xfrm`, applying proportional coordinate transforms to nested children.
  5. **External Media**: Avoid network blocking by marking missing/external media gracefully.
- **Verification**: Diagnostic run on the 4 corpus files to confirm all shapes, text, colors, and master decorations are parsed.

## Task 3: Table, Group, and SmartArt Rendering in `ShapeGraphicsItem`
- **Files**:
  - `src/atboffice/modules/presentation/views/shape_item.py`
  - `src/atboffice/modules/presentation/views/slide_canvas.py`
- **Actions**:
  1. In `ShapeGraphicsItem.paint`:
     - If `self.model.type == "table"` or `self.model.tbl`: Call `_paint_table(painter, w, h)`, rendering cell backgrounds, grid lines, and each cell's `tx` runs with their individual colors.
     - If `self.model.type == "group"`: Call `_paint_group(painter, w, h)`, recursively painting child shapes.
     - If `self.model.is_diagram` or `self.model.sa`: Call `_paint_diagram(painter, w, h)`, rendering boxes and extracted diagram text.
     - If `self.model.media_item` is missing/unsupported: Paint a clean placeholder with `safe_tr("外部媒体")`.
  2. In `SlideScene`: Render master decorations behind slide shapes when `not slide.hide_master`.
- **Verification**: Render `SlideCanvasView` to `QImage` offscreen and inspect pixels.

## Task 4: Thumbnail & Slideshow Rendering Synchronization
- **Files**:
  - `src/atboffice/modules/presentation/views/workspace.py` (`render_slide_thumbnail`)
  - `src/atboffice/modules/presentation/slideshow/transitions.py` (`render_slide_to_image`)
- **Actions**:
  1. Support tables, groups, SmartArt, and master decorations in `render_slide_thumbnail`.
  2. Support tables, groups, SmartArt, and master decorations in `render_slide_to_image`.
  3. Guarantee identical content rendering across normal canvas view, thumbnail, and slideshow.
- **Verification**: Compare rendered outputs from normal canvas view, thumbnail, and slideshow for all 4 corpus files.

## Task 5: Comprehensive Test Suite & Acceptance Verification
- **Files**:
  - `tests/gui/test_phase7_pptx_render.py` (new)
- **Actions**:
  1. Implement tests for:
     - `master-slides.pptx`: Master background color, master decoration `TextBox 19` ("Copyright © SUSE"), and slide placeholders.
     - `TextFittingComparisonWithMSO_3.pptx`: `fontScale` parsed (92.5%, 77.5%) and applied to text rendering without overflow.
     - `smartart-text.pptx`: Diagram parsed and text `'test'` rendered.
     - `table-with-different-font-colors.pptx`: Table rendered with green (`#00B050`) and red (`#FF0000`) runs.
     - View consistency: Normal view, thumbnail, and slideshow images all match content expectations.
     - Lossless roundtrip: Edit ordinary text, save, re-read, and verify master, animations, and relationships are preserved.
  2. Run:
     `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_pptx_render.py tests/unit/corpus/test_presentation_corpus.py -ra`
- **Verification**: Zero failures, exit code 0, no unhandled Qt exceptions.

## Task 6: Documentation & Evidence Update
- **Files**:
  - `docs/clone/phase7_features.csv`
- **Actions**:
  Update lines for PPTX reader, writer, and rendering with `verified` status and evidence pointing to `tests/gui/test_phase7_pptx_render.py`.
