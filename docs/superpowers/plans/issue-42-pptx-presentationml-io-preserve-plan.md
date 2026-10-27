# Implementation Plan: Issue #42 - [Lectern] PPTX/PPSX/POTX PresentationML 核心读取与无损保存

## Task Breakdown & Execution Sequence

### Task 1: Update Schema Ordering in `src/atboffice/vfs/order.py`
- Add PresentationML element ordering tables:
  - `presentationml_sp`: `["nvSpPr", "spPr", "style", "txBody", "extLst"]`
  - `presentationml_sppr`: `["xfrm", "custGeom", "prstGeom", "noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill", "ln", "effectLst", "effectDag", "scene3d", "sp3d", "extLst"]`
  - `presentationml_pic`: `["nvPicPr", "blipFill", "spPr", "style", "extLst"]`
  - `presentationml_graphicframe`: `["nvGraphicFramePr", "xfrm", "graphic", "extLst"]`
  - `presentationml_slide`: `["cSld", "clrMapOvr", "transition", "timing", "extLst"]`
  - `presentationml_presentation`: `["sldMasterIdLst", "notesMasterIdLst", "handoutMasterIdLst", "sldIdLst", "sldSz", "notesSz", "smartTags", "embeddedFontLst", "custShowLst", "photoAlbum", "custDataLst", "kinsoku", "defaultTextStyle", "modifyVerifier", "extLst"]`
- Ensure `enforce_schema_order` recognizes PresentationML aliases.

### Task 2: Implement `src/atboffice/modules/presentation/io/pptx_reader.py`
- Create `PptxReader` class and `read_pptx(source, ...) -> Presentation`.
- Handle reading from file path, `bytes`, or `io.BytesIO`.
- Parse:
  - Main presentation XML: slide dimensions (EMUs to points), slide ordering (`sldIdLst`).
  - Themes: parse color scheme (`srgbClr`, `sysClr`, `schemeClr`) and fonts.
  - Slide XML:
    - `<p:spTree>` shapes: rectangles, text boxes, shapes, placeholder tags.
    - Text bodies: paragraphs, runs, fonts, font size (hundredths of pt to pt), colors, bullets, alignments, bold, italic.
    - Transforms (`<a:xfrm>`): x, y, w, h (EMUs to pt), rotation.
    - Fills: solid, gradient, none.
    - Lines: width, color, dash.
    - Pictures (`<p:pic>`): blip references, image data extraction.
    - Tables (`<p:graphicFrame>`): rows, cells, text in cells.
    - Groups (`<p:grpSp>`): nested shapes.
    - Transitions: type, speed, click, duration.
    - Notes: extract text from corresponding `notesSlide`.
- Store `_source_package` and slide part map for preservation.

### Task 3: Implement `src/atboffice/modules/presentation/io/pptx_writer.py`
- Create `PptxWriter` class and `write_pptx(presentation, target, format="pptx", ...) -> bytes`.
- Support formats: `pptx`, `ppsx`, `potx`.
- Packaging:
  - Use `PackageWriter` with `source_package` if available.
  - Unmodified slides: retained byte-for-byte.
  - Modified / new slides: generated conforming to PresentationML.
  - New presentation from scratch: synthesizes complete minimal valid package structure (themes, masters, layouts, presentation, slides, content types, rels).
- Slide XML generator:
  - `<p:sld>` with `cSld`, `spTree`, `transition`.
  - Strict schema ordering for all shapes.
  - Tables and pictures serialization with proper relationships.
  - Slide notes writer: creates `notesSlide` and attaches relationship.

### Task 4: Expose APIs in `src/atboffice/modules/presentation/io/__init__.py`
- Export `PptxReader`, `PptxWriter`, `read_pptx`, `write_pptx`.

### Task 5: Comprehensive Unit Tests in `tests/unit/presentation/test_pptx_io.py`
- Test cases:
  1. Module exports.
  2. Roundtrip from scratch: create `Presentation`, add slides with shapes, write, read back, assert equality.
  3. PPTX vs PPSX vs POTX content-type verification.
  4. Rich text formatting: bold, italic, colors, font sizes, alignment.
  5. Shapes and geometries: rect, ellipse, roundRect, line styling, fill types.
  6. Table reading and writing.
  7. Pictures / media embedding and byte extraction.
  8. Slide transitions and speaker notes roundtrip.
  9. Lossless roundtrip verification: modify 1 slide out of 3, assert the other 2 slides retain identical XML bytes.
  10. Schema order validation on generated XML.

### Task 6: Run Full Test Suite & Verify 100% Pass
- Run `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/presentation/test_pptx_io.py -v`.
- Run full suite: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`.
