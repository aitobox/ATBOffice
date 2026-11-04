# Specification: Issue #242 (TASK-708) — Fix Lectern PPTX Rendering and Roundtrip

## 1. Overview & Objective
Issue #242 addresses high-fidelity rendering, placeholder inheritance, and lossless roundtrip preservation for Microsoft PowerPoint (`.pptx`) presentations in Lectern, aligned with the original implementation in `.vibeoffice/public/lectern/js/` (`pptx-read.js`, `render.js`, `textedit.js`, `preserve.js`).

The scope encompasses:
1. **Master & Layout Inheritance & Decorations**: Slide masters and slide layouts define placeholders and decorative/background shapes (e.g. `TextBox 19` copyright notice in `master-slides.pptx`). Slides inherit missing transforms, fills, lines, and text properties from layout and master, while non-placeholder master/layout shapes are rendered behind slide shapes.
2. **Text Autofit (`normAutofit`)**: Real-world decks (e.g. `TextFittingComparisonWithMSO_3.pptx`) store dynamic `fontScale` and `lnSpcReduction` attributes on `<a:normAutofit>` (e.g., 92500 for 92.5%, 77500 for 77.5%). The parser, renderer, and writer must read, scale typography, and preserve these attributes losslessly.
3. **DrawingML Diagram / SmartArt Extraction & Rendering**: In `smartart-text.pptx`, `<p:graphicFrame>` references `ppt/diagrams/data1.xml` through `dgm:relIds`. The reader must extract the diagram text and layout, rendering diagram elements on canvas/thumbnail/slideshow rather than mistaking them for empty tables.
4. **DrawingML Table Rendering & Individual Cell Font Colors**: In `table-with-different-font-colors.pptx`, table cells have runs with distinct colors (`#00B050`, `#FF0000`). `ShapeGraphicsItem`, `render_slide_thumbnail`, and `render_slide_to_image` must all render tables with cell geometry, borders, backgrounds, and per-run font colors.
5. **Group Shape Recursive Transforms**: Group shapes (`<p:grpSp>`) with `chOff`/`chExt` must apply coordinate mapping `(x + (kid.x - chx) * (w / chw), y + (kid.y - chy) * (h / chh))` and render child shapes recursively.
6. **Robustness & Safe Media Fallback**: If external media cannot be loaded, show an idiomatic non-blocking placeholder with `safe_tr()`, never hanging on network calls or throwing unhandled Qt exceptions.

---

## 2. Deep Module Architecture & Changes

### 2.1 Reader (`src/atboffice/modules/presentation/io/pptx_reader.py`)
- **Master & Layout Decorations & Background**:
  - In `_load_master` and `_load_layout`: in addition to placeholders, parse non-placeholder shapes into `master.decorations` / `layout.decorations`.
  - Parse background `<p:bg>` from master, layout, and slide.
  - Link `slide.design_id` to the loaded master's design so `pres.get_design_for_slide(slide)` accurately yields the master's colors, fonts, background, and decorations.
- **`normAutofit` Attributes**:
  - In `_parse_text_body`: when `<a:normAutofit>` is present, extract `fontScale` (`float(val) / 100000.0`) and `lnSpcReduction` (`float(val) / 100000.0`) into `TextBody.font_scale` and `TextBody.ln_spc_reduction`.
- **SmartArt / Diagram Recognition**:
  - In `_parse_graphic_frame`: detect `uri="http://schemas.openxmlformats.org/drawingml/2006/diagram"` or `<dgm:relIds>`.
  - Resolve relationship `dm` (`r:dm`) pointing to `ppt/diagrams/data1.xml`.
  - Parse `<dgm:pt>` text nodes, constructing a diagram shape with `sh.sa` and `sh.text = TextBody.from_text(...)`.
- **Group Transform Mapping**:
  - In `_parse_group_element`: parse `<a:chOff>` and `<a:chExt>`, scaling and translating child shape positions so nested shapes are placed accurately in slide space.
- **External Media Fallback**:
  - When media is an external URI or unsupported, set `media_item.missing_label = safe_tr("外部媒体")` without initiating network requests.

### 2.2 Writer (`src/atboffice/modules/presentation/io/writer_text.py`, `writer_shapes.py`, `pptx_writer.py`)
- **`writer_text.py`**:
  - When writing `<a:normAutofit>`, write `fontScale="{int(tb.font_scale * 100000)}"` and `lnSpcReduction="{int(tb.ln_spc_reduction * 100000)}"` if present.
- **OPC Part Carry**:
  - Ensure all diagram parts (`ppt/diagrams/`), theme parts, master parts, and media parts remain intact via OPC lossless carry.

### 2.3 Unified Rendering (`views/shape_item.py`, `views/slide_canvas.py`, `views/workspace.py`, `slideshow/transitions.py`)
- **Table Rendering in `ShapeGraphicsItem`**:
  - Implement `_paint_table(painter, w, h)`: draws table cell rectangles, background fills, borders, and each cell's `tx` runs using per-run colors.
- **Group Rendering in `ShapeGraphicsItem`**:
  - Implement recursive child painting when `sh.type == "group"`.
- **SmartArt Rendering in `ShapeGraphicsItem`**:
  - When `sh.is_diagram` or `sh.sa`: draw diagram background, node boxes, and diagram text with theme colors.
- **Master Decorations on Canvas**:
  - In `SlideScene.drawBackground` or `load_slide`: if `not slide.hide_master`, render master/layout background and decorations behind slide shapes.
- **Consistency in Thumbnail (`workspace.py`) and Slideshow (`transitions.py`)**:
  - Update `render_slide_thumbnail` and `render_slide_to_image` to support tables, group shapes, SmartArt text, and master decorations, ensuring visual consistency across all view modes.

---

## 3. Acceptance Verification & Evidence
1. **Curated Corpus Tests**:
   `tests/docs/powerpoint/pptx/libreoffice__master-slides.pptx`
   `tests/docs/powerpoint/pptx/libreoffice__TextFittingComparisonWithMSO_3.pptx`
   `tests/docs/powerpoint/pptx/libreoffice__smartart-text.pptx`
   `tests/docs/powerpoint/pptx/poi__table-with-different-font-colors.pptx`
2. **Phase 7 GUI Test Suite**:
   Create `tests/gui/test_phase7_pptx_render.py` verifying:
   - Offscreen and native Qt painting without exceptions.
   - Master decorations and copyright notice visible in rendered image.
   - `fontScale` applied to font point size in text fitting.
   - SmartArt text rendered from `data1.xml`.
   - Table cells rendered with distinct green (`#00B050`) and red (`#FF0000`) text colors.
   - Consistency between normal view, thumbnail, and slideshow images.
   - Roundtrip preservation of master, media, and unknown relations.
3. **Execution Command**:
   `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_pptx_render.py tests/unit/corpus/test_presentation_corpus.py -ra` (exit code 0).
4. **Evidence Update**:
   Update `docs/clone/phase7_features.csv` marking items verified with evidence.
