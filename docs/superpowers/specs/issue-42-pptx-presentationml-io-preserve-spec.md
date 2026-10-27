# Specification: Issue #42 - [Lectern] PPTX/PPSX/POTX PresentationML 核心读取与无损保存

## 1. Overview & Goals

This specification details the architecture and implementation of the ECMA-376 PresentationML read and write engine for Lectern (ATBOffice presentation editor).
The module supports:
1. Reading `.pptx`, `.ppsx` (slide show), and `.potx` (template) packages into `Presentation` model instances.
2. Writing `Presentation` instances into valid, compliant `.pptx`, `.ppsx`, and `.potx` files.
3. Lossless roundtripping and preservation: When editing an existing package, unmodified slides, slide masters, slide layouts, themes, media streams, and auxiliary parts (`presProps.xml`, `viewProps.xml`, `tableStyles.xml`, `docProps/`) are carried over byte-for-byte using `SourcePackage` and `PackageWriter`.
4. Strict OOXML schema conformance: XML node sequences strictly adhere to the ECMA-376 standard, ensuring zero repair warnings when opened in Microsoft PowerPoint.

---

## 2. Architecture & File Layout

```
src/atboffice/
├── vfs/
│   ├── opc.py             # Existing: SourcePackage & PackageWriter
│   └── order.py           # Add PresentationML schema ordering rules
└── modules/
    └── presentation/
        ├── io/
        │   ├── __init__.py        # Exposes PptxReader, PptxWriter, read_pptx, write_pptx
        │   ├── pptx_reader.py    # PresentationML parser and model builder
        │   └── pptx_writer.py    # PresentationML serializer and OPC packager
        └── models/
            ├── presentation.py   # Container, slide management, metadata
            ├── slide.py          # Slide, Transition, Animation
            ├── shape.py          # Shape, Fill, Line, Shadow, PlaceholderInfo
            └── text.py           # TextBody, Paragraph, Run, TextStyleLevel
```

---

## 3. Data Flow & Components

### 3.1 PptxReader
1. **OPC Inspection**: Opens file or byte stream using `SourcePackage.from_bytes()` or `SourcePackage.open()`.
2. **Package Entry Point**: Reads `_rels/.rels` to locate the `officeDocument` target (typically `ppt/presentation.xml`).
3. **Presentation Structure**:
   - Parses `<p:presentation>`: dimensions (`<p:sldSz cx="..." cy="..."/>`), first slide number (`<p:firstSlideNum>`), and slide references (`<p:sldIdLst>`).
   - Converts EMUs to points: `pt = emu / 12700.0`.
4. **Theme & Color Schemes**:
   - Resolves `ppt/theme/theme1.xml` from presentation relationships.
   - Extracts color scheme (`dk1, lt1, dk2, lt2, accent1..accent6, hlink, folHlink`) and font definitions (`majorFont`, `minorFont`).
5. **Slide Master & Layouts**:
   - Parses `ppt/slideMasters/slideMaster1.xml` and `ppt/slideLayouts/slideLayout*.xml`.
   - Maps master placeholders and background decorations.
6. **Slides Parsing**:
   - For each slide in `sldIdLst`:
     - Reads `ppt/slides/slide{N}.xml` and its relationships `_rels/slide{N}.xml.rels`.
     - Extracts background `<p:bg>`, shapes from `<p:spTree>`, transition `<p:transition>`, and notes from associated `notesSlide`.
     - Recursively parses shapes (`<p:sp>`), images (`<p:pic>`), tables (`<p:graphicFrame>` / `<a:tbl>`), and groups (`<p:grpSp>`).
     - Extracts text bodies (`<p:txBody>`), paragraphs (`<a:p>`), runs (`<a:r>`), bullet info, and run properties (`<a:rPr>`).
7. **Source Package Attachment**:
   - Attaches `source_package` to `pres.props["_source_package"]` and registers slide part mappings (`slide.id -> ppt/slides/slide{N}.xml`) for lossless carry-forward.

### 3.2 PptxWriter
1. **Format Handling**:
   - Sets appropriate Content-Type for main part based on format (`pptx`, `ppsx`, or `potx`):
     - `pptx`: `application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml`
     - `ppsx`: `application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml`
     - `potx`: `application/vnd.openxmlformats-officedocument.presentationml.template.main+xml`
2. **OPC Package Management**:
   - Uses `PackageWriter(source_package=pres.props.get("_source_package"))`.
3. **Lossless Carry-Forward**:
   - For slides flagged as unmodified (having an existing part name and not marked dirty), delegates to `PackageWriter` to preserve raw part bytes.
   - For new or modified slides, generates clean PresentationML XML conforming to schema order.
   - Preserves all unmodified external parts: `ppt/theme/`, `ppt/slideMasters/`, `ppt/tableStyles.xml`, `ppt/viewProps.xml`, `docProps/`, and media streams.
4. **Clean Presentation Generation from Scratch**:
   - If no source package exists (brand new presentation), synthesizes minimal required OOXML structures:
     - `[Content_Types].xml`
     - `_rels/.rels`
     - `ppt/presentation.xml` & `ppt/_rels/presentation.xml.rels`
     - `ppt/slideMasters/slideMaster1.xml` & rels
     - `ppt/slideLayouts/slideLayout1.xml` & rels
     - `ppt/theme/theme1.xml`
     - `ppt/slides/slide{N}.xml` & rels
     - `docProps/core.xml` & `docProps/app.xml`
5. **Schema Ordering**:
   - Enforces correct element sequences:
     - `p:sp`: `p:nvSpPr` ➔ `p:spPr` ➔ `p:style` ➔ `p:txBody`
     - `p:spPr`: `a:xfrm` ➔ `a:prstGeom` ➔ `a:solidFill`/`a:noFill`/`a:gradFill` ➔ `a:ln` ➔ `a:effectLst`
     - `p:sld`: `p:cSld` ➔ `p:clrMapOvr` ➔ `p:transition` ➔ `p:timing`

---

## 4. Verification Plan
- Unit tests in `tests/unit/presentation/test_pptx_io.py`:
  1. Module exports check (`read_pptx`, `write_pptx`, `PptxReader`, `PptxWriter`).
  2. Roundtrip of a newly created `Presentation`: title slide, text slide, shapes, text runs, formatting, slide dimensions.
  3. PPTX / PPSX / POTX content types and format flags.
  4. Table serialization and deserialization (`<p:graphicFrame>` / `<a:tbl>`).
  5. Image and media embedding with relationships.
  6. Slide notes extraction and generation.
  7. Slide transitions and timings roundtrip.
  8. Lossless preservation: Modify single slide, verify unmodified slide XML and media streams match byte-for-byte.
  9. Strict XML schema ordering checks using `SCHEMA_ORDERS`.
