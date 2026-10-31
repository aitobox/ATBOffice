# Specification: Quire HTML Document Bidirectional Import and Semantic Export (html_io)

**Issue**: [#163](https://github.com/aitobox/ATBOffice/issues/163)  
**Parent Epic**: #151 (Phase 4 Final Polish & Parity)  
**Module**: `atboffice.modules.writer.io.html_io` & `atboffice.vfs.html_io`  

---

## 1. Overview & Objective

Quire currently supports DOCX, DOCM, Markdown (GFM/ZIP), and RTF formats. However, the original project (`.vibeoffice/public/quire/js/htmlio.js`, 502 lines) supported full bidirectional HTML import and export—including clipboard HTML, opening `.html`/`.htm` files, and saving as single self-contained Web Pages with embedded media and CSS styles.

This specification defines the pure Python port for Quire HTML I/O:
1. **HTML Import Engine (`HtmlReader` / `read_html`)**: Parses arbitrary HTML5 / HTML4 snippets or full documents into Quire's `Document` DOM tree. Correctly handles headings, paragraphs, formatted runs, hyperlinks, ordered/unordered lists with nesting, complex tables with colspan/rowspan, and inline/embedded images.
2. **HTML Export Engine (`HtmlWriter` / `write_html` / `web_page`)**: Serializes a Quire `Document` (or list of blocks) into clean, semantic, standalone HTML5 with embedded CSS styling, table formatting, and base64-encoded images.
3. **VFS Integration & Shell Routing**:
   - Creates `src/atboffice/vfs/html_io.py` as an alias/entry point for VFS file operations.
   - Registers `.html` and `.htm` in `WindowManager.QUIRE_EXTENSIONS`.
   - Adds HTML Web Page filters to Quire and Start Center file dialogs (`*.html *.htm`).
   - Ensures Quire window can open and save `.html`/`.htm` files seamlessly.
4. **Zero External Dependencies**: Implemented strictly using Python 3.12 standard library (`html.parser.HTMLParser`, `re`, `urllib`, `base64`) and existing Quire models.

---

## 2. Architecture & File Layout

```
src/atboffice/
├── modules/writer/io/
│   ├── __init__.py          # Export HtmlReader, HtmlWriter, read_html, write_html
│   └── html_io.py           # Core implementation of HTML Parser & Serializer
├── vfs/
│   └── html_io.py           # VFS bridge exposing read_html, write_html, HtmlReader, HtmlWriter
├── core/
│   └── window_manager.py    # Add .html, .htm to QUIRE_EXTENSIONS
└── ui/shell/
    ├── quire_window.py      # Update file filters & save handling for HTML
    └── start_center.py      # Update file filters
tests/modules/writer/
└── test_html_io.py          # Comprehensive test suite covering roundtrips, edge cases, tables, lists, styles
```

---

## 3. Detailed Data Mapping

### 3.1 Inline & Character Formatting Mapping

| HTML Element / Style | Quire `RunProperties` Attribute | Notes / Values |
|---|---|---|
| `<b>`, `<strong>`, `font-weight: bold` / `600+` | `r_pr.bold = True` | Case-insensitive |
| `<i>`, `<em>`, `font-style: italic` / `oblique` | `r_pr.italic = True` | |
| `<u>`, `<ins>`, `text-decoration: underline` | `r_pr.underline = "single"` | |
| `<s>`, `<strike>`, `<del>`, `text-decoration: line-through` | `r_pr.strike = True` | |
| `<sup>`, `vertical-align: super` | `r_pr.vert_align = "superscript"` | |
| `<sub>`, `vertical-align: sub` | `r_pr.vert_align = "subscript"` | |
| `<code>`, `<kbd>`, `<samp>`, `<tt>`, `<pre>` | `r_pr.font_family = "Courier New"` | Monospace default |
| `color: #RRGGBB` / `rgb(...)` / named | `r_pr.color = "RRGGBB"` | 6-char hex, auto for default |
| `background-color: ...`, `<mark>` | `r_pr.highlight` / `r_pr.shading` | Preset highlights or hex |
| `font-size: Npt/px/em` | `r_pr.font_size = float(pt)` | `1px = 0.75pt`, keyword mapping |
| `font-family: Arial, ...` | `r_pr.font_family = "Arial"` | Primary family extracted |
| `<a href="...">` | `r_pr.link = {"url": ...}` / `{"anchor": ...}` | Bookmark if starts with `#` |
| `<br>` | `BreakItem(break_type="line")` | |
| `&emsp;` / `\t` | `TabItem()` | |

### 3.2 Block & Paragraph Formatting Mapping

| HTML Element / Style | Quire `ParagraphProperties` Attribute | Notes |
|---|---|---|
| `<p>`, `<div>`, `<section>`, `<article>` | Standard `Paragraph` | Flushes preceding paragraph |
| `<h1>` - `<h6>` | `p_pr.style_id = "Heading1"` .. `"Heading6"` | `r_pr.bold = True`, appropriate size |
| `text-align: center` / `right` / `justify` | `p_pr.jc = "center"` / `"right"` / `"both"` | Left is default (None) |
| `margin-left: Npt`, `padding-left: Npt` | `p_pr.ind.left = float(pt)` | Indentation in points |
| `margin-right: Npt` | `p_pr.ind.right = float(pt)` | |
| `text-indent: Npt` | `p_pr.ind.first_line = float(pt)` | First-line indent |
| `margin-top: Npt`, `margin-bottom: Npt` | `p_pr.sp.space_before`, `p_pr.sp.space_after` | Spacing before/after |
| `line-height: N` | `p_pr.sp.line = N`, `line_rule = "auto"` | Multiplier or exact pt |
| `<hr>` | `Paragraph` with bottom border | Emulates horizontal divider |

### 3.3 List Mapping

- `<ul>`: Unordered bulleted list. Generates or reuses bullet numbering definition (`fmt="bullet"`, bullet symbol `'•'`).
- `<ol>`: Ordered numbered list. Supports `type` attribute (`"1"`, `"a"`, `"A"`, `"i"`, `"I"`) and `start` attribute.
- `<li>`: Creates `Paragraph` with `p_pr.num_id` and `p_pr.num_level`. Supports nesting depth up to 8 levels.

### 3.4 Table Mapping

- `<table>`: Generates Quire `Table`.
- `<tr>`: Generates Quire `Row`.
- `<th>`, `<td>`: Generates Quire `Cell`.
  - Parses `colspan` -> `cell.tc_pr.span`.
  - Parses `rowspan` -> Generates continuation cells (`v_merge="continue"`) across subsequent rows.
  - Parses `bgcolor` or `background-color` -> `cell.tc_pr.shd`.
  - Parses `valign` / `vertical-align` -> `cell.tc_pr.v_align`.
  - Computes `Table.grid` column widths from cell widths or divides available width (default 432pt) evenly.

### 3.5 Image Mapping

- `<img>`:
  - Parses `src`: if `data:image/...;base64,...`, decodes into bytes. If relative or file URL, reads file if accessible.
  - Parses `width` and `height` attributes or styles (converting `px` to points via `* 0.75`).
  - Creates `PictureItem` with `image_part` (path or identifier), `alt_text`, `width`, `height`.
  - On export: serializes pictures as embedded Base64 data URIs so that exported HTML files are 100% self-contained without broken external asset links.

---

## 4. Robustness & Edge Case Safeguards

1. **Unclosed / Malformed HTML**:
   - `html.parser.HTMLParser` handles missing closing tags without throwing syntax errors.
   - Stack-based tracking safely auto-closes dangling tags at the end of containers or document end.
2. **Empty Content**:
   - Input `""` or whitespace-only returns a valid `Document` containing a single empty `Paragraph`.
   - Never produces an empty `Story.blocks` list.
3. **HTML Character Entities**:
   - Correctly handles numeric (`&#65;`, `&#x41;`) and named (`&nbsp;`, `&quot;`, `&amp;`, `&lt;`, `&gt;`) entities.
4. **Complex Word/Office HTML Pastes**:
   - Ignores Office-specific garbage: `<!--[if ...]>...<![endif]-->`, `mso-list: Ignore`, conditional comments.
5. **Preformatted Text (`<pre>`)**:
   - Preserves explicit newlines and tabs (`\n` -> new paragraph or line breaks, `\t` -> 4 spaces or tab items).
6. **Roundtrip Fidelity**:
   - Document exported to HTML and imported back preserves text, bold/italic/underline/strike styles, colors, headings, links, list structures, and tables.

---

## 5. Verification Strategy

1. **Automated Unit Tests (`tests/modules/writer/test_html_io.py`)**:
   - Test basic paragraphs and inline styles (`<b>`, `<i>`, `<u>`, `<s>`, `<sup>`, `<sub>`, `<code>`).
   - Test CSS inline styles (font-family, font-size, color, background-color, text-align, margins).
   - Test headings (`h1` through `h6`) mapping to styles.
   - Test links (`<a href="...">`) with external URLs and internal anchors.
   - Test unordered lists (`<ul>`) and ordered lists (`<ol>`) with nesting.
   - Test tables (`<table>`, `<tr>`, `<td>`, `<th>`, colspan, rowspan, background colors).
   - Test images (`<img>` with data URIs, alt text, dimensions).
   - Test roundtrip: `write_html(read_html(html))` produces matching DOM.
   - Test VFS export `atboffice.vfs.html_io`.
   - Test Quire window file filter and extension routing in `WindowManager`.
2. **Full Test Suite Run**:
   - Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/writer/test_html_io.py -v`.
   - Run existing test suite to ensure 0 regressions.
