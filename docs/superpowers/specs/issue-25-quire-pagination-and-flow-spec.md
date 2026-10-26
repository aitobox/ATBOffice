# Design Specification: Quire Dynamic Multi-Page Pagination & Flow Engine (Issue #25)

## 1. Overview & Objectives

This specification defines the architecture, data models, and pagination algorithm for the multi-page flow and pagination engine in Quire (Word 2003 port) under `src/atboffice/modules/writer/layout/pagination.py`.

The pagination engine takes a Quire `Document` (consisting of sections, paragraphs, tables, and runs) and decomposes the continuous content flow into discrete, physical `Page` objects matching Microsoft Word 2003 and LibreOffice layout semantics. It is decoupled from PySide6 GUI widgets, ensuring pure Python algorithmic determinism and high-speed execution for both interactive rendering and document conversion/printing.

### Key Capabilities:
1. **Physical Page Generation**: Computes exact page geometry (Letter, A4, custom), margins (top, bottom, left, right, gutter), and orientation.
2. **Break Types**:
   - Hard page break (`BreakItem(break_type='page')`).
   - Column break (`BreakItem(break_type='column')`).
   - Section breaks (`nextPage`, `oddPage`, `evenPage`, `continuous`).
3. **Orphan & Widow Control**: Enforces Word's widow/orphan rules (minimum 2 lines at the bottom of a page, minimum 2 lines carried over to the top of the next page).
4. **Keep Rules**:
   - `pageBreakBefore`: Forces break before paragraph.
   - `keepWithNext`: Keeps heading or paragraph on the same page as the succeeding paragraph, rolling back keep-chains when necessary.
   - `keepLines`: Keeps all lines of a paragraph on a single page.
5. **Header & Footer Management**:
   - Resolves First Page (`titlePg`), Odd/Even pages, and Default headers/footers.
   - Dynamic margin adjustment: when header/footer content height exceeds default margins (`hdr + hh > mt` or `ftr + fh > mb`), body area automatically shrinks.
6. **Dynamic Page Numbering & Multi-pass Fields**:
   - Evaluates `PAGE`, `NUMPAGES`, and `SECTIONPAGES` fields.
   - Two-pass pagination when field length changes affect layout line wraps.

---

## 2. Reference Source Analysis (`.vibeoffice/public/quire/js/layout.js`)

In the reference JavaScript implementation:
- `LY.paginate(fromPage, fieldPass)` orchestrates pagination loop through sections and blocks.
- `LY.flow(frame, blocks, st, end, ctx)` places paragraphs/tables into a frame until exhausted or filled.
- `lines = LY.lines(frag)` measures line boxes and splits paragraphs.
- Orphan/Widow control:
  ```js
  const widow = pPr.widow !== false;
  if (widow && nl > 1) {
    if (k === 1 && !frame.empty) k = 0;
    if (nl - k === 1 && k >= 2) k--;
    if (k === 1 && nl > 2 && !frame.empty) k = 0;
  }
  ```
- Keep with next chain:
  `if (pPr.keepNext && frame.kind === 'col') frame.chain.push({ bi, el, sub }); else frame.chain = [];`
  If subsequent block cannot fit, `keepChainBreak` drops the chained paragraphs and rolls back state to the head of the chain.
- Headers & Footers:
  `hh = renderHF(hdr, hdrStory); if (sect.mt >= 0 && hh && px(sect.hdr) + hh > top) top = px(sect.hdr) + hh;`

---

## 3. Data Structures & Models

### 3.1 `PageFragment`
Represents a rendered portion of a paragraph (or block) placed on a specific page:
```python
@dataclass
class PageFragment:
    paragraph: Paragraph
    line_start_idx: int       # Start line index within ParagraphLayout
    line_end_idx: int         # End line index (exclusive)
    lines: list[LayoutLine]
    top: float                # Y coordinate relative to column body top
    height: float             # Total height of these lines
    space_before: float       # Space before applied to top line
    space_after: float        # Space after applied to bottom line
    char_start: int           # Character offset start
    char_end: int             # Character offset end
```

### 3.2 `ColumnFrame`
Represents an individual column on a page region:
```python
@dataclass
class ColumnFrame:
    index: int
    left: float               # X offset relative to page left
    top: float                # Y offset relative to page top
    width: float              # Column width
    height: float             # Maximum available column height
    used_height: float = 0.0  # Height consumed by placed fragments
    fragments: list[PageFragment] = field(default_factory=list)
```

### 3.3 `PageRegion`
Represents a section region on a page (can hold 1 or more columns):
```python
@dataclass
class PageRegion:
    section_index: int
    section: SectionProperties
    top: float                # Y offset on page body
    height: float             # Region height
    columns: list[ColumnFrame]
```

### 3.4 `PageHeaderFooter`
Represents header or footer layout on a page:
```python
@dataclass
class PageHeaderFooter:
    kind: str                 # 'header' | 'footer'
    story: Story | None
    y: float                  # Y coordinate on page
    width: float
    height: float
    fragments: list[PageFragment] = field(default_factory=list)
```

### 3.5 `Page`
Represents an entire physical page:
```python
@dataclass
class Page:
    index: int                # 0-based sequential page index
    page_number: int          # Page number (taking section restart into account)
    page_number_format: str   # 'decimal', 'lowerRoman', 'upperRoman', etc.
    section_index: int
    section: SectionProperties
    width: float              # Page width (pt)
    height: float             # Page height (pt)
    body_left: float          # Left margin (+ gutter)
    body_right: float         # Right margin
    body_top: float           # Top margin (adjusted by header)
    body_bottom_gap: float    # Bottom margin (adjusted by footer)
    body_width: float         # Available body width
    body_height: float        # Available body height
    header: PageHeaderFooter | None = None
    footer: PageHeaderFooter | None = None
    regions: list[PageRegion] = field(default_factory=list)
    is_blank: bool = False    # True if inserted for parity padding
```

### 3.6 `PaginationResult`
```python
@dataclass
class PaginationResult:
    pages: list[Page]
    total_pages: int
    section_pages: list[int]  # Total pages per section
    duration_ms: float = 0.0
```

---

## 4. Detailed Pagination Workflow

### Step 1: Section Traversal & Page Initialization
- Iterate through sections in the document.
- Determine starting page number (custom start or continuation).
- Calculate parity (`first`, `even`, `odd`, `default`).
- Layout header and footer:
  - If header height `hh + sect.hdr > sect.mt`, body top expands.
  - If footer height `fh + sect.ftr > sect.mb`, bottom margin gap expands.
- Create initial `Page` and `PageRegion`.

### Step 2: Content Flow Loop
- For each paragraph in the current section:
  1. **Page Break Before**: If `p_pr.page_break_before` and frame is not empty, start a new page.
  2. **Hard Breaks**: If paragraph contains `BreakItem(break_type='page')`, break paragraph into segments before and after the break.
  3. **Paragraph Layout**: Use `layout_paragraph()` from `portions.py` to get `ParagraphLayout` with lines and metrics.
  4. **Fitting Check**:
     - Check available vertical height in current `ColumnFrame`: `space_left = frame.height - frame.used_height`.
     - Collapse spacing before: if at top of page, drop spacing before.
     - If entire paragraph fits: add fragment to column, update `used_height`, and continue.
  5. **Splitting & Widow / Orphan Control**:
     - If paragraph doesn't fit and `p_pr.keep_lines`: entire paragraph must move to next page.
     - Find line cutoff `k` that fits within `space_left`.
     - Apply widow/orphan logic:
       - If `k == 1` and lines > 1: orphan! Set `k = 0` (move whole paragraph to next page, unless frame is empty and line is taller than frame).
       - If `total_lines - k == 1`: widow! Reduce `k = k - 1` (leave at least 2 lines on next page).
       - If `k == 1` and `total_lines > 2`: `k = 0`.
     - If `k > 0`: place lines `[0..k]` on current page, place remaining lines on next page.
  6. **Keep With Next Handling**:
     - If `p_pr.keep_next`: record keep-chain `[(p, fragment, frame)]`.
     - If the subsequent paragraph cannot fit even its first allowable lines, pop the keep-chain from current frame and move the chained paragraphs to the next page.
     - If subsequent paragraph fits, clear keep-chain.

### Step 3: Section Breaks
- When end of section is reached:
  - `nextPage`: start new page with new section properties.
  - `oddPage`: if current page number is even, add blank page, start new page.
  - `evenPage`: if current page number is odd, add blank page, start new page.
  - `continuous`: if remaining height in current page is >= 24 pt, create new `PageRegion` on the same page; otherwise start new page.

### Step 4: Two-Pass Dynamic Field Resolution
- Count total pages (`NUMPAGES`) and section pages (`SECTIONPAGES`).
- Check if header/footer or body paragraphs contains `NUMPAGES` / `SECTIONPAGES`.
- If dynamic text lengths change and cause lines to re-wrap, perform second pass.

---

## 5. Verification Plan

Test file: `tests/unit/writer/test_pagination.py`
1. **Single Page Flow**: Short document fits on 1 page with correct body bounds and line placements.
2. **Multi-Page Overflow**: Long multi-paragraph text accurately breaks across multiple pages.
3. **Hard Page & Column Breaks**: Manual `BreakItem(break_type='page')` and `column` trigger immediate breaks.
4. **Section Breaks**: Verify `nextPage`, `oddPage`, `evenPage`, and `continuous` breaks and page parities.
5. **Orphan & Widow Control**: Verify 1-line orphan prevention at page bottom, and 1-line widow prevention at page top.
6. **Keep Rules**: Verify `pageBreakBefore`, `keepWithNext` chains, and `keepLines`.
7. **Headers & Footers**: Verify first page, odd/even page headers, and margin expansion when header/footer is tall.
8. **Dynamic Page Numbers**: Verify `PAGE`, `NUMPAGES`, and `SECTIONPAGES` field formatting.
