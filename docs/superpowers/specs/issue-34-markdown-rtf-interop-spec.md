# Design Spec - Issue #34: [Quire] GitHub Flavored Markdown (含图片 ZIP) 与 RTF 互转

## Overview & Background
Issue #34 focuses on porting the Markdown (GFM) and Rich Text Format (RTF 1.5) I/O subsystems from `.vibeoffice` (`.vibeoffice/public/quire/js/markdown.js`, `mdio.js`, and `rtf.js`) to Python 3.12+ in `src/atboffice/modules/writer/io/`.
This capability provides high-fidelity, bidirectional translation between modern developer-friendly formats (Markdown + Markdown Zip with images) and office clipboard formats (RTF 1.5) with Quire's core Document Object Model (`Document`, `Paragraph`, `Table`, `RunItem`, etc.).

---

## 90% Confidence Autonomous Decision Rationale
- Confidence: >= 95%.
- Reference implementation in `.vibeoffice/public/quire/js/markdown.js`, `mdio.js`, and `rtf.js` provides exact behavioral models.
- Python standard libraries (`zipfile`, `io`, `re`, `pathlib`, `typing`) combined with modular parser designs provide complete, portable, dependency-free implementations.
- No ambiguous requirements or breaking changes to existing Quire APIs.

---

## Architecture & Module Interfaces

### 1. Markdown I/O (`src/atboffice/modules/writer/io/markdown_io.py`)
Provides reading and writing of GitHub Flavored Markdown and Markdown ZIP packages.

#### Core Functions & Classes:
- `read_markdown(src: str | bytes, resolve_image: Callable[[str], bytes | None] | None = None) -> Document`
  - Parses GFM text into a `Document` with appropriate styles, paragraphs, tables, runs, and properties.
  - Supports:
    - YAML Front Matter (`--- ... ---` header preserved or skipped cleanly)
    - ATX Headings `#` to `######` mapped to `Heading1` .. `Heading6`
    - Paragraphs with inline styling: bold `**`, italic `*` / `_`, strikethrough `~~`, inline code `` `code` ``, links `[text](url)`
    - Blockquotes `>` and nested blockquotes with Quote formatting
    - GitHub Callout Alerts: `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`
    - Fenced Code Blocks (```` ```lang ... ``` ````) mapped to `HTMLPreformatted` paragraphs
    - Bullet lists (`-`, `*`, `+`), Ordered lists (`1.`), and Task Lists (`- [ ]`, `- [x]`)
    - Pipe Tables (`| col1 | col2 |` with delimiter row alignment `:---`, `:---:`, `---:`) mapped to `Table`, `Row`, `Cell`, column grid widths
    - Footnotes `[^1]` inline markers and definitions `[^1]: text`
    - Thematic breaks `---` / `***` mapped to paragraph with bottom border
- `write_markdown(doc: Document, keep_raw: bool = True) -> tuple[str, list[tuple[str, bytes]]]`
  - Converts `Document` into CommonMark/GFM string and extracts embedded images `[(image_path, image_bytes), ...]`.
  - Generates clean pipe tables, task lists, blockquotes, code blocks, alerts, and inline styles.
- `read_markdown_zip(zip_source: str | Path | bytes | io.BytesIO) -> Document`
  - Opens a `.zip` archive containing a Markdown file and bundled images.
  - Automatically locates the primary `.md` file in the archive and resolves relative image references.
- `write_markdown_zip(doc: Document, main_filename: str = "document.md") -> bytes`
  - Packages the Markdown document and all extracted images into an in-memory ZIP archive returning `bytes`.

---

### 2. RTF I/O (`src/atboffice/modules/writer/io/rtf_io.py`)
Provides parsing and serialization of Rich Text Format (RTF 1.5).

#### Core Functions & Classes:
- `read_rtf(src: str | bytes) -> Document`
  - Lexes and parses RTF token stream (`{`, `}`, `\control_word`, plaintext).
  - Handles:
    - Font table `\fonttbl` (`\f0`, `\f1`, ...)
    - Color table `\colortbl` (`\redN\greenN\blueN;`)
    - Character properties: `\b`, `\i`, `\ul`, `\strike`, `\fsN` (half-points to points), `\fN`, `\cfN`, `\highlightN`
    - Paragraph properties: `\pard`, `\plain`, alignment (`\qc`, `\qr`, `\qj`, `\ql`), spacing (`\sb`, `\sa`, `\sl`), indents (`\li`, `\ri`, `\fi`)
    - Tables: `\intbl`, `\cell`, `\row`, `\trowd`, `\cellxN`
    - Hyperlinks: `{\field{\*\fldinst {HYPERLINK "url"}}{\fldrslt text}}`
    - Images: `{\pict\pngblip ...}` or `{\pict\jpegblip ...}` hex decoding
    - Unicode & Escape codes: `\'xx`, `\uN?`, `\{`, `\}`, `\\`
    - Group stack pushing and popping with inheritance
- `write_rtf(doc: Document) -> bytes`
  - Generates valid RTF 1.5 document with header `{\rtf1\ansi\ansicpg1252\deff0`, font table, color table, stylesheet, paragraph and character runs, tables, hyperlinks, and images.

---

### 3. Package Integration (`src/atboffice/modules/writer/io/__init__.py`)
Export:
- `read_markdown`, `write_markdown`, `read_markdown_zip`, `write_markdown_zip`
- `read_rtf`, `write_rtf`
- `MarkdownReader`, `MarkdownWriter`, `RtfReader`, `RtfWriter`

---

## Edge Case Analysis & Robustness
1. **Empty Input**:
   - `read_markdown("")` and `read_rtf("")` return a valid `Document` with a single empty `Paragraph`.
2. **Missing Images in Markdown**:
   - Return clean document; do not crash on missing image file or unresolvable path.
3. **Escaped Markdown Characters**:
   - Properly unescape backslash-escaped characters (`\*`, `\_`, `\[`, etc.) in reader, and escape special characters when writing text.
4. **Nested Lists and Mixed Indentation**:
   - Correctly track indentation levels and numbering sequences.
5. **Non-ASCII & Unicode Characters**:
   - Full UTF-8 support in Markdown.
   - For RTF, characters outside ASCII range emitted as `\uN?` or hex code `\'xx` with 100% fidelity.
6. **Corrupt / Truncated RTF**:
   - Gracefully handle unmatched braces or unexpected EOF without uncaught exceptions.
7. **Roundtrip Fidelity**:
   - Formatted text (headings, bold, italic, lists, tables) roundtrips through Markdown and RTF cleanly.

---

## Verification Plan
1. Unit tests in `tests/unit/writer/test_markdown_rtf.py`:
   - `test_markdown_read_basic`: headings, paragraphs, bold, italic, code, links.
   - `test_markdown_tables`: pipe tables with column alignment.
   - `test_markdown_task_lists_and_alerts`: task lists `- [ ]`, `- [x]`, GitHub alerts `> [!NOTE]`.
   - `test_markdown_roundtrip`: read and write fidelity.
   - `test_markdown_zip_roundtrip`: create doc with image, write to zip, read back from zip.
   - `test_rtf_read_basic`: font table, color table, bold, italic, underline, alignment.
   - `test_rtf_tables`: table rows, cells, cell widths.
   - `test_rtf_hyperlinks`: field hyperlink reading and writing.
   - `test_rtf_roundtrip`: write doc to RTF and read back.
2. Full suite regression:
   - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/writer/ -v`
