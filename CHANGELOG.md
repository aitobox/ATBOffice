# Changelog

All notable changes to ATBOffice are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-11-28

This release delivers Phase 12 robustness and parity waves, the lazy Paper 2016 Ribbon engine, and Phase 13 features including the constrained Solver engine, offline WordNet thesaurus/Research task pane, Draw Table/Eraser tools, and floating object formatting.

### Added

#### Suite and UI
- Lazy Paper 2016 Ribbon engine with declarative specs for Quire, Ledger, and Lectern (`13d816a`), plus contextual task pane auto-follow (`RB.follow`) across editors (`f9ad84f`).
- Shared `SuiteResearchPane` for Ledger and Lectern with offline WordNet thesaurus engine and i18n support (`ff61980`, `a8f1c0b`).
- Unified Qt `fault_guard` and owned timer teardown in core (`df5641f`).

#### Quire (documents)
- Floating object commands and `FormatObjectDialog` (`83b2bbe`).
- Interactive Draw Table pencil and Eraser canvas tools (`c853ca5`).

#### Ledger (spreadsheets)
- Constrained Solver engine (`6962bc1`), Luna 2003 Solver dialogs (`d288bcb`), menu/ribbon/undo/i18n wiring (`b7d68b9`), Sensitivity and Limits reports, multi-report UI, and XLSX `definedNames` persistence (`295949d`).
- `ENCODEURL`, offline `FILTERXML`/`EUROCONVERT`, and 520-function parity gate (`4a06adc`).
- Fixed-Width split ruler, PivotChart sync, and conditional formatting E2E verification (`c0b2dd4`).

#### Lectern (presentations)
- Handout Master and Notes Master views, printing, and PPTX round-trip support (`2de2c7f`).

### Fixed
- **Quire**: Undoable `insert_shape`, cached numbering lookup on keystrokes (`e224b13`), document-wide undo and unique shape IDs for floating object operations (`40c3c46`), serialization of newly added shapes, pictures, and comments, `_em_char_cache` key fix (`0c9b10b`), and `insertComment` tooltip (`40ee35c`).
- **Ledger**: Undoable object layer and comments, event guards, XLSX comment round-trip (`7c6732e`), stale comment VML/`legacyDrawing` cleanup on delete (`99b4feb`), scrollbar/scroll-range/SheetTabBar alignment (`6be98bb`, `638ecd7`), and Solver dialog state/worker/reference parsing fixes (`83262b1`, `55871c5`, `b89973c`).
- **Lectern**: `PresentationHistory` timer guards, `SlideScene` mouse lifecycle (`c5a0ad4`), and timer stop exception logging (`fd1b215`).
- **Stability & Robustness**: Repaired 4 broken lazy imports with AST import integrity test (`2a35bb4`), completed undo snapshots, `fault_guard` coverage, timer logging, i18n (`246bc48`), and hardened ribbon toolbar-mode guard and `safe_single_shot` (`c582f2d`).
- **Audit & Testing**: Exempted `reference_limitation` in strict diff gate (`40ee35c`), isolated `QSettings` per pytest xdist worker (`556ddc6`, `de9cf80`), and added cross-editor robustness/roundtrip gates (`cba6c48`, `70ab305`, `64fc82b`).

### Changed
- Addressed Phase 12 Wave 2 review findings on scroll extent, theme tokens, and gate deduplication (`481f509`), plus Phase 12/13A/13B/13C design specs, plans, and audit reports.

## [0.2.0] - 2026-11-25

First tagged release of ATBOffice, a Python 3.12 / PySide6 office suite with three
Office 2003-style applications: **Quire** (documents), **Ledger** (spreadsheets) and
**Lectern** (presentations), launched from a shared Start Center. This release covers
all work from the initial scaffold through Phase 11.

### Added

#### Suite and shell
- Start Center with recent files, drag-and-drop opening, template gallery, themed
  cards, document previews and licence notices.
- Window manager with per-module windows, launcher lifecycle and CLI subcommands
  (`atboffice`, `atboffice-quire`, `atboffice-ledger`, `atboffice-lectern`).
- macOS native menu bar with Finder double-click opening, and the full Office 2003
  menu set (Insert, Format, Tools, Table, Data, Slide Show).
- Office 2003 Luna blue/silver themes, a native 16×16 vector icon engine, declarative
  toolbars with split and drop-down buttons, toolbar customization.
- `ActionRegistry` command bus shared by toolbars, menus and shortcuts.
- Right-hand task panes, 24-item Office Clipboard (including images), Tell Me command
  palette, Find & Replace, Options dialog with live theme preview, undo drop-downs.
- Shared Clipart library, WordArt gallery (30 styles with Bézier warping), Scout
  desktop assistant and a background update checker backed by GitHub Releases.
- Print preview with unified page geometry for all three modules, and vector PDF export.
- Localization into 7 languages with dynamic retranslation.
- Template registry with 10 Quire, 8 Ledger and 4 Lectern built-in templates.

#### File formats
- Lossless OPC package engine with strict schema ordering and part-level byte fidelity.
- ECMA-376 Agile and Standard AES encryption and decryption.
- DOCX/DOCM, XLSX/XLSM and PPTX/PPSX/POTX reading and lossless saving.
- Excel 97-2003 (`.xls`) read-only import, XML Spreadsheet 2003 read/write, CSV import
  wizard with encoding detection.
- Markdown (with image ZIP), RTF and HTML import/export for Quire.
- Pure-Python WMF/EMF parser and renderer.
- OLE compound document detection with clear guidance for encrypted and legacy files.

#### Quire (documents)
- Document object model, line-portion layout with East Asian grid snapping, multi-page
  pagination with widow/orphan control, and caret/selection editing on a page canvas.
- Complex tables with merged cells, nested tables, cell margins and borders.
- Floating pictures and shapes with text wrapping, linked text boxes, DrawingML shapes,
  charts and SmartArt on the page.
- Fields and table of contents, footnotes, headers and footers, multi-level numbering.
- Track changes and comments, Office Math (OMML), mail merge wizard, AutoCorrect and
  spell checking, Word Count.
- Interactive rulers, view modes (Outline, Web, Reading, Full Screen) and navigation pane.
- Classic Font, Paragraph, Page Setup, Bullets and Numbering, Table Properties, Borders
  and Shading, Columns and Tabs dialogs.

#### Ledger (spreadsheets)
- Formula lexer and Pratt parser, dependency graph recalculation with cycle detection
  and iterative calculation, cross-sheet references, 519 worksheet functions including
  dynamic arrays and structured references.
- Virtualized self-drawn grid, in-cell editing with formula bar, AutoFill, frozen panes,
  split windows, outlining, zoom and page-break preview.
- Format Cells dialog, number formats, in-cell rich text, conditional formatting (data
  bars, color scales, icon sets) and data validation with invalid-data circles.
- AutoFilter with searchable checkbox lists, custom filters, multi-column sort, Excel
  tables and table styles, Paste Special with operations and transpose.
- Chart Wizard and chart rendering, PivotTables with a field list task pane, Goal Seek,
  formula auditing arrows, Evaluate Formula and Watch Window, Text to Columns.
- Floating object layer for drawings, pictures and comments.

#### Lectern (presentations)
- Presentation model with masters, 21 layouts and 15 design themes, and placeholder
  inheritance.
- Interactive vector canvas with transform handles, in-place rich text editing and
  AutoFit, connectors, custom geometry and PowerPoint table styles.
- Normal, Slide Sorter, Notes and Master views; slide comments.
- Slide show engine with 58 transitions, 50+ custom animations, presenter view, ink
  and laser pointer, rehearsal timings and live previews.
- IntelliArt (26 SmartArt layouts) with outline pane sync, DrawingML charts including
  3D column charts, media placeholders, background formatting dialog.

#### Tooling
- Cross-platform Nuitka packaging scripts and a tag-driven GitHub Actions release
  workflow producing a macOS ARM64 DMG, a Linux x86_64 AppImage and a Windows x64
  portable ZIP.
- Real-world document corpora, round-trip and loss-audit regression suites, and a
  dual-engine visual rendering comparison against the reference implementation.

### Fixed
- Many rendering parity fixes across all three modules against real Word, Excel and
  PowerPoint documents (fonts and metrics, list numbering, table geometry, chart fills,
  theme colors, picture cropping, text wrapping and column flow).
- Stability fixes for window close use-after-free crashes, event loop re-entrancy,
  macOS cursor crashes, focus theft and null-cell formatting crashes.
- Data safety fixes for 0-byte saves, failed saves on close, XLSX/XLSM save loss and
  false-success file opens; the crash recovery service now starts reliably.
- Wired previously disconnected dialogs and toolbar actions in Quire, Ledger and Lectern,
  and removed double-firing between the menu bar and the action registry.
- Lossless saving: XLSX keeps shared formulas, styles, hidden sheets and workbook
  settings; DOCX keeps comments, footnotes, endnotes and style definitions; PPTX keeps
  slide ids so sections and custom shows still resolve.
- One bounded undo history per document in Quire, Ledger and Lectern.
- The English interface now works throughout, the Luna palette is applied
  consistently, and a round of visible UI bugs is fixed.
- Saves and background threads are hardened, and test-only code paths are removed
  from the shipped application.
- Hardened package handling: a safe XML parser (no network access or entity
  expansion) and refusal of zip bombs.

### Changed
- All OOXML code now uses lxml, and file encryption uses `msoffcrypto-tool`.
- Release builds install the project's declared dependencies, so `.xls` import and
  the update checker work in packaged apps. `packaging` is now a declared runtime
  dependency.
- Release artifact names drop the tag's `v` prefix (`ATBOffice-0.2.0-…`).

[Unreleased]: https://github.com/aitobox/ATBOffice/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/aitobox/ATBOffice/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/aitobox/ATBOffice/releases/tag/v0.2.0
