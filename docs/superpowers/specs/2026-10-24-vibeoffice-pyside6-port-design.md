# Technical Design Spec: Porting VibeOffice to Python 3.12+ / PySide6 (ATBOffice)

- **Date**: 2026-10-24
- **Target Platform**: macOS (Primary / First Priority), Windows, Linux
- **Tech Stack**: Python 3.12+, PySide6 (Qt6), pytest, pytest-qt
- **Reference Codebase**: `.vibeoffice/` (~75k LOC vanilla JavaScript Office 2003 recreation suite)

---

## 1. Executive Summary & Vision

### 1.1 Objective
Port the `.vibeoffice` web office suite into a native, high-performance desktop application named **ATBOffice** using **Python 3.12+ and PySide6 (Qt6)**. The application brings back the beloved, distraction-free Office 2003 visual aesthetics ("Luna" blue/silver command bars and menus) while providing full modern file compatibility (Office Open XML `.docx`, `.xlsx`, `.pptx`).

### 1.2 Core Tenets
1. **Lossless Editing & Strict Roundtrip Compatibility**:
   When editing an existing document, any XML part, shape, media, VBA macro, or custom extension not modified by the user must be preserved byte-for-byte in the output package. Files saved by ATBOffice must open in Microsoft Office and LibreOffice with zero repair warnings or errors.
2. **macOS First-Class Experience**:
   Native macOS global unified menu bar (`QMenuBar`), native Apple HIG keyboard shortcuts (`⌘S`, `⌘Z`, `⌥`), Retina / HiDPI sharp rendering, Finder double-click and file drop associations via `QFileOpenEvent`.
3. **Pure Model / Pure Algorithm Separation**:
   All core engines (OPC packaging, spreadsheet calculation with 519 functions, word typesetting line portions, and presentation layouts) must be implemented in pure Python with zero Qt/GUI dependencies, making them 100% testable via pytest without starting a display server.
4. **100% i18n & Idiomatic Translation**:
   All user-facing UI strings must be wrapped in `tr()` / `safe_tr()`, providing natural Chinese and English translations with dynamic runtime locale switching (`retranslate_ui`).

---

## 2. System Architecture & Directory Layout

### 2.1 Layered Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   1. UI & Presentation Layer (PySide6)                 │
│  - macOS Unified Menu / Dock & Window Manager / Start Center           │
│  - Ledger Virtual Grid (QAbstractScrollArea) / Formula Bar             │
│  - Quire Paginated Canvas / Interactive Rulers / Outline Pane          │
│  - Lectern Slide Canvas (QGraphicsScene) / Slide Show Viewport         │
│  - Office 2003 Luna & 2016 Ribbon Modes / Format Brush / Scout Helper  │
├────────────────────────────────────────────────────────────────────────┤
│                   2. Domain Core Engines (Pure Python)                 │
│  - Ledger: DAG Dependency Recalculator + 519 Worksheet Functions       │
│  - Quire: Apache OpenOffice Line Portions & CJK Line Grid Pagination   │
│  - Lectern: IntelliArt 26-Layout Engine & Slide Show State Machine     │
├────────────────────────────────────────────────────────────────────────┤
│                   3. Document Object Models (DOM Tree)                 │
│  - Workbook / Worksheet / Cell / CellRange / StyleSheet                │
│  - Document / Section / Paragraph / Run / Table / Drawing / Field      │
│  - Presentation / SlideMaster / 21 Layouts / 15 Themes / Shape Tree    │
├────────────────────────────────────────────────────────────────────────┤
│            4. Infrastructure & Lossless Storage (Lossless VFS)         │
│  - Lossless OPC Package (opc.py / xml_tree.py / order.py)              │
│  - ECMA-376 Agile & Standard AES-256 Crypto Engine (crypto.py)         │
│  - DrawingML 92 AutoShapes / 54 Patterns / WMF-EMF Player (metafile.py)│
│  - Excel Number Formatter (numfmt.py) / i18n Bus (i18n.py)             │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Directory Layout

```text
src/atboffice/
├── __init__.py
├── __main__.py              # Application entry point
├── core/                    # Cross-platform foundation services
│   ├── app.py               # QApp lifecycle, macOS Retina scaling, signals
│   ├── config.py            # User configuration (~/.atboffice/config.json)
│   ├── commands.py          # Central command registry (ui.cmd / ui.exec)
│   ├── events.py            # Event dispatcher (vo-command, vo-busy)
│   ├── recent.py            # Recent documents, previews, draft recovery
│   └── i18n.py              # Internationalization & retranslate_ui helpers
├── vfs/                     # Virtual File System & lossless OOXML packaging
│   ├── opc.py               # Immutable source package & byte-for-byte carry
│   ├── xml_tree.py          # Lightweight DOM tree with byte-span tracking
│   ├── crypto.py            # ECMA-376 Standard & Agile AES encryption
│   └── order.py             # Schema order enforcer (ECMA-376 conformance)
├── drawing/                 # Vector shapes & graphics engine
│   ├── geometry.py          # 92 AutoShape presets & adjustment handles
│   ├── patterns.py          # 54 preset pattern fills
│   ├── metafile.py          # WMF / EMF parser and QPainter renderer
│   └── charts/              # DrawingML 17 chart types & data model
├── ui/                      # Shared user interface components
│   ├── shell/               # Desktop shell & window manager
│   │   ├── main_window.py   # Top-level window hosting modules
│   │   ├── mac_menu.py      # macOS native menu bar binding
│   │   └── start_center.py  # LibreOffice-style start center & template gallery
│   ├── styles/              # Theme stylesheets
│   │   ├── luna_2003.py     # Classic Office 2003 Luna Blue/Silver palette
│   │   └── ribbon_2016.py   # Office 2016 Paper Ribbon tabbed bar
│   ├── components/          # Reusable widgets
│   │   ├── toolbar.py       # Classic toolbar & mnemonic buttons
│   │   ├── color_picker.py  # 40-color palette (theme + standard colors)
│   │   ├── brush.py         # Format painter state machine
│   │   └── scout.py         # Scout animated office assistant
├── modules/                 # Office core application modules
│   ├── spreadsheet/         # [Ledger - Excel 2003]
│   │   ├── models/          # Workbook, Worksheet, Cell, CellRange, Style
│   │   ├── calc/            # Formula parser, AST, DAG recalculator, 519 functions
│   │   ├── views/           # QAbstractScrollArea virtual grid, formula bar
│   │   ├── io/              # XLSX/XLSM/CSV/XMLSS readers & writers
│   │   └── dialogs/         # Format cells (6 tabs), Sort, Filter, Validation
│   ├── writer/              # [Quire - Word 2003]
│   │   ├── models/          # Document, Section, Paragraph, Run, Table, Field
│   │   ├── layout/          # Line portions, East Asian grid, pagination
│   │   ├── views/           # Canvas page view, dual rulers, outline pane
│   │   ├── io/              # DOCX/DOCM/Markdown/RTF/HTML/PDF I/O
│   │   └── dialogs/         # Font, Paragraph, Page Setup, Bullets & Numbering
│   └── presentation/        # [Lectern - PowerPoint 2003]
│       ├── models/          # Presentation, SlideMaster, Layouts, Shapes
│       ├── views/           # QGraphicsView canvas, notes pane, task panes
│       ├── smartart/        # IntelliArt 26 layouts layout engine
│       ├── slideshow/       # 58 transitions, 50+ animation effects viewport
│       ├── io/              # PPTX/PPSX/POTX readers & writers
│       └── dialogs/         # Format shape, Slide layout, Setup show
└── resources/               # Assets (icons, fonts, wordlists, templates)
```

---

## 3. Lossless OPC Packaging & Cryptography Engine

### 3.1 Lossless Carry Architecture (`vfs/opc.py` & `vfs/xml_tree.py`)
- **Immutable Source Package**:
  Upon opening a file (`.docx`, `.xlsx`, `.pptx`), the original ZIP stream is parsed into an immutable `SourcePackage`. Part relationships (`.rels`) and content types (`[Content_Types].xml`) are mapped into a relationship graph.
- **Byte-for-Byte Preservation**:
  When saving, parts corresponding to user modifications (e.g. `word/document.xml`, `xl/worksheets/sheet1.xml`) are serialized afresh. Unmodified parts (embedded VBA macros, custom XML parts, unedited charts, printer settings, embedded OLE objects) are copied directly from the source ZIP byte-for-byte.
- **Strict Schema Ordering (`vfs/order.py`)**:
  OOXML requires child elements in complex types to appear in strict sequence. The serializer uses predefined schema ordering tables extracted from ECMA-376 to sort child elements during generation.
- **Strict <-> Transitional Normalization**:
  Transparently maps Strict namespace URIs (`http://purl.oclc.org/ooxml/...`) to Transitional URIs (`http://schemas.openxmlformats.org/...`) to ensure compatibility across older and newer Office suites.

### 3.2 Cryptography (`vfs/crypto.py`)
- **Agile Encryption**:
  Implements AES-128/256 with CBC/ECB and SHA-512 key hashing using Python `hashlib` and `cryptography` library. Supports password-protected documents from Office 2010+.
- **Standard Encryption**:
  Supports legacy Office 2007 AES-128 + SHA-1 encryption.
- **Password Workflow**:
  Prompts user via a native modal dialog when opening encrypted files; automatically re-encrypts using the same password on save unless modified via `Tools > Options > Security`.

---

## 4. Ledger: Spreadsheet Module Design (Excel 2003)

### 4.1 Calculation Engine (`modules/spreadsheet/calc/`)
- **Formula Lexer & AST Parser**:
  Parses formulas containing A1/R1C1 references, range operators (`:`, `,`, space intersection), arithmetic operators (`+`, `-`, `*`, `/`, `^`), comparison operators (`=`, `<>`, `<`, `>`, `<=`, `>=`), string concatenation (`&`), and structured table references (`Table1[Amount]`).
- **DAG Dependency Graph & Topological Recalculation**:
  Maintains dependency pairs `Cell -> DependentCells`. When a cell's value or formula changes, downstream cells are flagged as dirty and evaluated strictly in topological order.
- **Circular Reference Handling**:
  Detects reference cycles. Returns `0` with a status bar alert by default; supports iterative calculation when enabled in options (max 100 iterations, tolerance 0.001).
- **519 Worksheet Functions**:
  Implements the full set of Excel 2003 functions (Math, Stats, Financial, Lookup, Text, Date/Time, Logic, Info) and modern dynamic array functions (`XLOOKUP`, `FILTER`, `UNIQUE`, `SORT`, `SEQUENCE`, `LET`, `LAMBDA`). Supports dynamic array spill bounds (`#`).

### 4.2 Virtualized Grid Viewport (`modules/spreadsheet/views/grid_view.py`)
- **Custom-Drawn Viewport (`QAbstractScrollArea`)**:
  Uses double-buffered `QPainter` rendering only cells inside the visible viewport rectangle. Achieves 60 FPS scrolling regardless of sheet size (up to 1,048,576 rows x 16,384 columns).
- **Selection State Machine**:
  Supports active single cell, rectangular ranges, non-contiguous multi-ranges (Cmd+click), whole rows, whole columns, and Select All.
- **AutoFill Handle**:
  Renders a 6x6 pixel bottom-right handle on the selection bounding box. Dragging computes arithmetic progressions, date series, and custom lists with visual drag preview.
- **In-Place Cell Editor & Formula Bar**:
  Overlay `QLineEdit` / `QTextEdit` positioned over the active cell. Colored cell reference borders appear on the grid when references are typed or clicked.
- **Text Overflow**:
  Unformatted text in a cell overflows into adjacent empty cells horizontally if column width is insufficient.

### 4.3 Data Analysis & Dialogs
- AutoFilter dropdowns with checklist items, Top 10, and custom filters.
- Multi-column Sorting (up to 3 keys) with custom order lists.
- Data Validation (list dropdown, integer, decimal, date, custom formula, input messages, error alerts).
- Conditional Formatting (data bars, color scales, icon sets, custom formula rules).
- 6-Tab Format Cells Dialog: Number, Alignment, Font, Border, Patterns/Fill, Protection.

---

## 5. Quire: Word Processing Module Design (Word 2003)

### 5.1 Typesetting & Pagination Engine (`modules/writer/layout/`)
- **Apache OpenOffice Line Portions Model**:
  Splits paragraph runs into measurable portions (text chunks, tabs, inline images, math blocks). Determines line height using exact font ascent/descent and line spacing rules (single, 1.5, double, exact, multiple).
- **Word-Compatible Typographic Rules**:
  - Spacing Collapse: `max(paragraph[i].space_after, paragraph[i+1].space_before)`.
  - Margin Suppression: Space before is omitted at the top of a page (unless triggered by manual page break).
  - Justification Squeeze: Justified lines may squeeze inter-word spaces by up to 20% to avoid premature wrapping.
  - East Asian Line Grid: Snaps lines to document grid intervals (15.6pt / 18pt pitch) for CJK documents.
- **Dynamic Pagination & Flow**:
  - Breaks content into A4 / Letter pages taking into account headers, footers, and margins.
  - Orphan and Widow control (minimum 2 lines of a paragraph per page).
  - Table row splitting and repeating header rows across pages.
  - Two-pass pagination to update dynamic fields (`PAGE`, `NUMPAGES`, `TOC`).

### 5.2 Interactive Page Canvas & Tools (`modules/writer/views/`)
- **Paginated Canvas View**:
  Renders pages vertically or in multi-page book view with paper drop-shadows.
- **Dual Interactive Rulers (Horizontal & Vertical)**:
  Direct mouse manipulation of left/right margins, first-line indent, hanging indent, and tab stops (left, center, right, decimal).
- **Rich Text & Table Editing**:
  In-place caret placement, mouse selection, word/line/paragraph selection, table row/column resizing, cell merging (`gridSpan`, `vMerge`).
- **File Interoperability**:
  Complete import/export for `.docx`, `.docm`, `.rtf`, GitHub Flavored Markdown (with embedded images ZIP), HTML, and vector PDF.

---

## 6. Lectern: Presentation Module Design (PowerPoint 2003)

### 6.1 Slide Canvas Architecture (`modules/presentation/views/`)
- **`QGraphicsScene` / `QGraphicsView` Canvas**:
  Slide dimensions mapped in logical points (16:9 widescreen 13.33 x 7.5 in, or 4:3 10 x 7.5 in). Shapes inherit from custom `QGraphicsItem`.
- **Shape Manipulation Handles**:
  8 resizing handles (Shift for aspect ratio lock, Alt for center scaling), top rotation handle (Shift for 15-degree increments), yellow diamond adjustment handles for 92 AutoShape presets.
- **Smart Guides (Magnetic Snapping)**:
  Automatic magnetic snapping to sibling shape centers, edges, and slide centerlines with dynamic visual guide lines.

### 6.2 IntelliArt (SmartArt) Layout Engine (`modules/presentation/smartart/`)
- **26 Layout Topologies**:
  Lists, Processes, Cycles, Hierarchies, Relationships, Matrices, Pyramids.
- **Two-Way Synchronization**:
  Outline dock text editing dynamically regenerates diagram shapes; modifying shape attributes updates the outline model.
- **Optimal Unified Font Sizing**:
  Calculates the maximal common font size such that all child shape texts fit within their respective bounds.

### 6.3 Slide Show & Animation Engine (`modules/presentation/slideshow/`)
- **Fullscreen Presentation Viewport**:
  Double-buffered rendering on dedicated presentation screen.
- **58 Slide Transitions & 50+ Custom Animations**:
  Entrance, Emphasis, Exit, and Motion Paths driven by `QVariantAnimation` / `QTimeLine` ensuring smooth 60 FPS transitions.
- **Presenter Console & Annotation**:
  Dual-screen presenter console displaying current slide, next slide preview, timer, and notes. Real-time laser pointer and pen ink annotations.

---

## 7. macOS Native Integration (macOS First)

1. **System Top Menu Bar (`setNativeMenuBar(True)`)**:
   Standard macOS menu hierarchy: App Menu (`About ATBOffice`, `Preferences`, `Quit`), File, Edit, View, Insert, Format, Tools, Window, Help.
2. **Keyboard Shortcuts**:
   Native mapping: Save (`⌘S`), Save As (`⇧⌘S`), Undo (`⌘Z`), Redo (`⇧⌘Z`), Cut (`⌘X`), Copy (`⌘C`), Paste (`⌘V`), Close (`⌘W`), Quit (`⌘Q`).
3. **Retina / HiDPI Crispness**:
   `QGuiApplication.setHighDpiScaleFactorRoundingPolicy(PassThrough)`. Vector geometry and text rendered to physical device pixels with anti-aliasing.
4. **File Association & Drag & Drop**:
   Subclass `QApplication` to handle `QEvent.Type.FileOpen` (`QFileOpenEvent`). Double-clicking `.docx`, `.xlsx`, `.pptx` in Finder opens the file immediately in a dedicated window.
5. **Native macOS Dialogs**:
   `QFileDialog` uses native Cocoa sheets (`NSOpenPanel` / `NSSavePanel`).

---

## 8. Robustness & Error Handling

1. **Atomic File Saving**:
   All saves write to a temporary file in the target directory, invoke `flush()` and `os.fsync()`, and perform an atomic rename (`os.replace()`), preventing file truncation on unexpected termination.
2. **Read-Only & Lock Detection**:
   Verifies write permissions prior to saving. Prompts user to "Save As" if the destination is read-only or locked.
3. **Graceful Corruption Recovery**:
   When reading damaged packages, repairs missing non-critical relationships and displays a non-blocking informational notification rather than crashing.
4. **Asynchronous I/O & Threading**:
   Large package decompression and calculation tasks run via `QThreadPool` / `QRunnable`, keeping the UI responsive with a cancellable progress bar.
5. **100% i18n Guard**:
   All UI strings wrapped in `tr()`. Non-translated strings fallback gracefully to English.

---

## 9. Phased Implementation Roadmap

- **Phase 0: Infrastructure Foundation & macOS Shell**
  - Setup core architecture, macOS unified menu, window manager, start center.
  - Implement lossless OPC engine, XML parser, crypto, and 92 AutoShape geometries.
- **Phase 1: Ledger Spreadsheet Module**
  - Implement Workbook/Sheet models, AST formula parser, DAG recalculator, 519 functions.
  - Implement virtualized grid viewport (`QAbstractScrollArea`), selection, AutoFill, in-place editor.
  - Implement XLSX I/O, CSV import wizard, formatting dialogs, and autofilter.
- **Phase 2: Quire Word Processing Module**
  - Implement Document DOM tree, Line Portions layout engine, CJK grid, pagination.
  - Implement paginated canvas viewport, dual rulers, text selection/caret, tables.
  - Implement DOCX I/O, Markdown/RTF/HTML, dynamic fields, and TOC generation.
- **Phase 3: Lectern Presentation Module**
  - Implement Presentation/Master/Layout models, 15 themes.
  - Implement `QGraphicsScene` canvas, shape handles, smart guides, text AutoFit.
  - Implement IntelliArt 26 layouts, 58 transitions, 50+ animations, and fullscreen slide show.
- **Phase 4: Polish, Cross-Platform Packaging & Release**
  - Office 2003 Luna & 2016 Ribbon theme polish, format brush, Scout assistant.
  - macOS DMG packaging with code signing support; Windows & Linux installers.
  - Automated corpus regression test suite execution.

---

## 10. Automated Testing Strategy

1. **Level 1: Pure Logic Unit Tests (`tests/unit/`)**:
   - `test_opc.py`: ZIP read, part reservation, byte-for-byte carry verification.
   - `test_calc.py`: Formula parser AST, 519 function unit tests, circular reference detection.
   - `test_crypto.py`: Agile & Standard encryption test vectors.
   - `test_layout.py`: Line portions, spacing collapse, and CJK line grid breaking.
2. **Level 2: GUI Interaction Tests (`tests/gui/`)**:
   - Powered by `pytest-qt` (`qtbot`): window lifecycles, mouse grid dragging, AutoFill handle, shortcut routing, dialog modal tests.
3. **Level 3: Corpus Roundtrip Regression Tests (`tests/corpus/`)**:
   - Automated testing on thousands of real public OOXML documents from the `.vibeoffice` corpus, asserting byte-identical preservation for unedited parts and zero validation errors.
