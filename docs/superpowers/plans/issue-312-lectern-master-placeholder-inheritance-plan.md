# Implementation Plan: Dynamic Slide Layout and Master Placeholder Inheritance

- **Issue**: [#312](https://github.com/aitobox/ATBOffice/issues/312) - `[phase8] fix(lectern): Dynamic slide layout and master placeholder inheritance`
- **Spec**: `docs/superpowers/specs/issue-312-lectern-master-placeholder-inheritance-spec.md`
- **Author**: Autonomous Agent
- **Date**: 2026-11-08

---

## Task Breakdown

### Task 1: Create Centralized Placeholder Resolver Module
- **Target File**: `src/atboffice/modules/presentation/models/placeholder_resolver.py`
- **Responsibilities**:
  - Implement `resolve_unoverridden_placeholders(slide: Slide, presentation: Presentation) -> list[Shape]`
  - Implement `apply_cascading_placeholder_styles(shape: Shape, design: DesignTemplate) -> None`
  - Implement `evaluate_field_text(run: TextRun, slide_index: int, presentation: Presentation | None = None) -> str`
  - Correctly evaluate slide numbers (`slide_index + first_num`) and formatted date strings.
  - Respect `slide.hide_master` and `presentation.hf` settings (including `not_on_title`).

### Task 2: PPTX Reader Field Parsing and Master Frame Extraction
- **Target File**: `src/atboffice/modules/presentation/io/pptx_reader.py`
- **Responsibilities**:
  - Parse `<a:fld>` elements alongside `<a:r>` in `_parse_paragraph`.
  - Extract `type` attribute from `<a:fld>` into `run.field` (e.g. `slNum`, `datetime`).
  - Extract placeholder frames into `m_info.design.placeholder_frames` from `m_info.placeholders`.
  - Map slide layout XML type to `slide.layout`.

### Task 3: Text Editor and Static Text Renderer Field Evaluation
- **Target File**: `src/atboffice/modules/presentation/views/text_editor.py`
- **Responsibilities**:
  - In `ShapeTextEditorItem.render_static_text`:
    - Support dynamic field evaluation (slide number, date) using context or field resolver.
    - If `run.field in ("slNum", "slidenum", "sldNum")` or `run.text in ("‹#›", "<#>")`:
      render current slide number.

### Task 4: Integrate Placeholder Resolver into SlideCanvas
- **Target File**: `src/atboffice/modules/presentation/views/slide_canvas.py`
- **Responsibilities**:
  - In `SlideCanvas.load_slide(slide)`:
    - Apply cascading style inheritance to explicit slide placeholder shapes.
    - Resolve unoverridden layout placeholders (`title`, `body`, `obj`, etc.) and footer placeholders (`dt`, `ftr`, `sldNum`).
    - Add unoverridden placeholder shapes as `ShapeGraphicsItem` with `_is_inherited_placeholder = True`.
    - Handle `title_decorations` for title slides.
    - Ensure scene items map and z-indices are cleanly managed.

### Task 5: Unit Tests and Verification
- **Target File**: `tests/unit/presentation/test_layout_placeholders_inheritance.py`
- **Responsibilities**:
  - Test cascading placeholder resolution (Slide -> Layout -> Master).
  - Test unoverridden placeholder generation for standard and title layouts.
  - Test dynamic slide number evaluation (`slNum`, `first_num` offsets).
  - Test `hide_master` suppresses unoverridden placeholders and decorations.
  - Test text style cascading (font family, size, color, bullet, alignment).
- **Verification Command**:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/test_layout_placeholders_inheritance.py -v`
