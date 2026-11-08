# Specification: Dynamic Slide Layout and Master Placeholder Inheritance

- **Issue**: [#312](https://github.com/aitobox/ATBOffice/issues/312) - `[phase8] fix(lectern): Dynamic slide layout and master placeholder inheritance`
- **Component**: `src/atboffice/modules/presentation/` (`views/slide_canvas.py`, `models/placeholder_resolver.py`, `models/designs.py`, `io/pptx_reader.py`, `views/text_editor.py`)
- **Author**: Autonomous Agent
- **Date**: 2026-11-08
- **State**: Approved (90% Confidence Autonomous Decision Rule)

---

## 1. Problem Statement & Motivation

In PowerPoint / `.vibeoffice` presentations, slides rarely define every visual element from scratch. Instead, slides rely on a three-tier hierarchy:
1. **Slide**: Contains user-created shapes and custom overrides for specific placeholders.
2. **Slide Layout**: Defines placeholder types, bounding boxes (`xfrm`), and layout-specific prompt frames.
3. **Slide Master**: Defines document-wide background, decorative shapes, theme fonts/colors, default paragraph/run styles, and default header/footer frames (`dt`, `ftr`, `sldNum`).

Prior to this fix in ATBOffice:
- `slide_canvas.py` only rendered `slide.shapes` and static `design.decorations`.
- Unoverridden layout placeholders (such as the body placeholder when a slide only overrides the title, or date/footer/slide number placeholders) were completely omitted from the canvas.
- When slide number fields (`<p:fld type="slNum">` or `‹#›`) existed, they were not dynamically evaluated using the slide's position index and `presentation.first_num`.
- Placeholders on slides lacked cascading text style inheritance (font family, font size, color, bullet type) from Slide Layout and Slide Master.
- In `pptx_reader.py`, slide layouts and masters were loaded, but `slide.layout` was hardcoded to `"text"`, `<a:fld>` runs were ignored in paragraphs, and `DesignTemplate.placeholder_frames` was not populated from master placeholders.

---

## 2. Requirements & Acceptance Criteria

1. **Cascading Placeholder Resolver (`Slide -> Slide Layout -> Slide Master`)**:
   - Provide a centralized `PlaceholderResolver` module (`src/atboffice/modules/presentation/models/placeholder_resolver.py`).
   - For any slide in a presentation, compute the effective visual shapes by merging:
     a) Explicit slide shapes (`slide.shapes`).
     b) Unoverridden layout placeholders (`title`, `body`, `ctrTitle`, `subTitle`, `obj`, `tbl`, `chart`).
     c) Unoverridden footer placeholders (`dt`, `ftr`, `sldNum`) based on `presentation.hf` or master frames.
   - Respect `slide.hide_master`: if True, suppress master decorations and master placeholders while preserving explicit slide shapes.

2. **Dynamic Binding of Unoverridden Layout Placeholders to Canvas**:
   - In `SlideCanvas.load_slide(slide)`:
     - Detect placeholders already overridden on `slide.shapes`.
     - Use `PlaceholderResolver` to create synthetic placeholder shapes for unoverridden layout and footer frames.
     - Add them to the canvas graphics scene with appropriate Z-ordering and non-interfering flags (`is_inherited_placeholder = True`), ensuring they are visible, display localized prompt text or dynamic values, and render cleanly.

3. **Dynamic Slide Number and Date Field Evaluation**:
   - In `ShapeTextEditorItem.render_static_text` and `PlaceholderResolver`:
     - Recognize fields with `field in ("slNum", "slidenum", "sldNum")` or literal run text `‹#›` / `<#>`.
     - Dynamically substitute the slide number: `slide_index + getattr(presentation, "first_num", 1)`.
     - Recognize datetime fields (`datetime`, `dt`, etc.) and substitute formatted date/time strings.

4. **Master Text Styles Cascading for Placeholders**:
   - When a placeholder shape has text runs with missing or default formatting:
     - `font`: Inherit from `design.fonts["major"]` for titles, `design.fonts["minor"]` for body/footers.
     - `size`: Inherit from master title/body level styles (title: 36-40pt; subTitle: 24pt; body level 0: 24-28pt; footers: 10-12pt).
     - `color`: Inherit from `design.colors.dk2` or `design.colors.dk1` / footer style.
     - `algn`: Inherit `ctrTitle` -> "ctr", `subTitle` -> "ctr", `sldNum` -> "r", `ftr` -> "ctr", `dt` -> "l".
     - `bullet`: Inherit master level bullet formatting for body outlines.

5. **PPTX Reader Enhancements**:
   - Parse `<a:fld>` in `_parse_paragraph` so field runs have `field="slNum"` / `field="datetime"`.
   - Map `<p:sldLayout type="...">` to `slide.layout` using `LAYOUT_MAP` / `OX_TO_KEY`.
   - Populate `m_info.design.placeholder_frames` and `m_info.design.text_styles` from `m_info.placeholders` and master styles.

6. **Unit Test Suite**:
   - Add `tests/unit/presentation/test_layout_placeholders_inheritance.py` testing cascading resolution, unoverridden placeholder binding, dynamic slide number evaluation, master text style inheritance, and `hide_master` behavior.

---

## 3. Architecture & Module Design

```
+-------------------------------------------------------------+
| Presentation (w, h, first_num, hf, designs, slides)         |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
| PlaceholderResolver                                         |
| - resolve_effective_shapes(slide, presentation)             |
| - resolve_placeholder_text_styles(shape, design)            |
| - evaluate_fields(text_body, slide_idx, presentation)        |
+-------------------------------------------------------------+
       |                                          |
       v                                          v
+-------------------------------+  +--------------------------+
| SlideCanvas                   |  | ShapeTextEditorItem      |
| - load_slide()                |  | - render_static_text()   |
| - binds unoverridden items    |  | - evaluates slide numbers|
+-------------------------------+  +--------------------------+
```

---

## 4. Verification & Testing Strategy

- Headless Qt pytest suite:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/test_layout_placeholders_inheritance.py -v`
- Full repository presentation tests:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/ -v`
