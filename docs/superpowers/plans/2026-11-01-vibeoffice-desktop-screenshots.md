# VibeOffice Desktop UI Screenshots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Run `.vibeoffice` in simulated desktop mode via Chromium CDP with `host-stub.js` and systematically capture exhaustive, categorized screenshots of Start Center, Quire, Ledger, and Lectern into `.vibeoffice/screenshots/`.

**Architecture:** A standalone Node.js automation script (`.vibeoffice/tools/crawl-screenshots.mjs`) leverages the local headless Chromium CDP session and `tools/serve.py`. It injects `tests/desktop/host-stub.js` to simulate the desktop host (`VO.host`), sets the default `classic` (Office 2003 Luna) look and English locale, and executes a 6-phase pipeline across all 4 modules: (1) Overview & views, (2) Task Panes, (3) Menus & Submenus, (4) Toolbars & Pickers, (5) Context Menus, and (6) Dialogs & Multi-Tab exploration. A central `resetUI()` protocol guarantees modal cleanup, and an index generator produces `.vibeoffice/screenshots/INDEX.md`.

**Tech Stack:** Node.js (v18+), Chromium CDP (WebSocket/JSON APIs), `tools/serve.py`, `tests/desktop/host-stub.js`.

**Spec:** `/Users/brainzhang/work/aitobox/ATBOffice/docs/superpowers/specs/2026-11-01-vibeoffice-desktop-screenshots-design.md`

## Global Constraints

- Output root must be strictly `.vibeoffice/screenshots/` with subdirectories `00_start_center/`, `01_quire/`, `02_ledger/`, `03_lectern/`.
- No modification of files in `.vibeoffice/public/` to maintain hash and test integrity.
- Viewport size fixed at 1280×800 with deviceScaleFactor=1 and `Emulation.setFocusEmulationEnabled: true`.
- Primary interaction mode is `classic` look and `lang=en`.
- Do not close any pre-existing user browser tabs on CDP port 9222.

## Review Focus

1. **Leftover open dialogs/menus cascading into subsequent screenshots**: Modal stack must be verified clean before every capture (`.dlg-overlay` and `.menu` absent).
2. **Context-dependent dialogs failing to open due to null selection**: Seeding objects (table, shape, chart, wordart, comment) must occur before calling object-specific dialogs (`tableProps`, `formatObject`, etc.).
3. **Blocking on native OS file choosers**: Import/open wizards (e.g., CSV Text Import Wizard) must be triggered via in-memory buffer APIs, not `<input type="file">`.
4. **Multi-tab dialogs only capturing the first active tab**: Detection logic must find all `.dlg .tabs-head .tab` buttons and click/capture every tab.
5. **Canvas and SVG diagram render settle timing**: A minimum 2-frame RAF + 80ms delay must precede every screenshot capture.

---

### Task 1: Core Automation Harness & Start Center Crawler

**Files:**
- Create: `.vibeoffice/tools/crawl-screenshots.mjs`
- Test: Manual execution of Start Center crawl generating `.vibeoffice/screenshots/00_start_center/*.png` and `INDEX.md`

**Interfaces:**
- Consumes: `.vibeoffice/tools/ooxml/cdp.mjs`, `.vibeoffice/tests/desktop/host-stub.js`, `.vibeoffice/tools/serve.py`
- Produces: `ensureBrowser()`, `openPage(url)`, `captureShot(dir, name, metadata)`, `resetUI()`, `crawlStartCenter()`, `generateIndexMarkdown()`

- [x] **Step 1: Write crawler scaffold and Start Center module**
  Create `.vibeoffice/tools/crawl-screenshots.mjs` with:
  - CDP connection and HTTP static server auto-detection (`tools/serve.py` port 8760).
  - Tab lifecycle: create tab, enable Page/Runtime/Network/DOM/Emulation, inject `tests/desktop/host-stub.js` on new document.
  - Snapshot helper `captureShot(moduleFolder, filename, meta)` writing PNG and logging to an in-memory index table.
  - Reset helper `resetUI()` closing any `.menu`, `.dlg-overlay`, active brush, or drag.
  - Crawl function for Start Center capturing:
    - `001_overview__Recent_Files_Populated.png` (with mock recent files)
    - `002_overview__Recent_Files_Empty_Welcome.png`
    - `003_overview__Create_File_Templates.png` (navigating to `#create`)
    - `004_dialog_settings__Settings.png` (clicking Settings link)
    - `005_dialog_themes__Themes_classic.png`
    - `006_dialog_themes__Themes_paper.png`
    - `007_dialog_themes__Themes_paper2016.png`
    - `008_dialog_about__About_VibeOffice.png`
    - `009_dialog_update__Update_VibeOffice.png`
    - `010_page_licenses__Open_Source_Licenses.png`

- [x] **Step 2: Run Start Center crawl**
  Run: `node .vibeoffice/tools/crawl-screenshots.mjs --only start_center`
  Expected: Clean completion; 10 PNG files created in `.vibeoffice/screenshots/00_start_center/`.

- [x] **Step 3: Verify outputs and manifest generation**
  Check image validity and verify that `.vibeoffice/screenshots/INDEX.md` is populated with Start Center rows.

- [x] **Step 4: Commit**
  ```bash
  git add .vibeoffice/tools/crawl-screenshots.mjs .vibeoffice/screenshots/00_start_center/ .vibeoffice/screenshots/INDEX.md
  git commit -m "feat(screenshots): add crawler harness and Start Center screenshots"
  ```

---

### Task 2: Quire (Word Processor) Exhaustive Crawler

**Files:**
- Modify: `.vibeoffice/tools/crawl-screenshots.mjs`
- Output: `.vibeoffice/screenshots/01_quire/*.png`

**Interfaces:**
- Consumes: `window.L`, `window.VO`, `L.ui`, `L.ed`, `L.dlg`, `L.app`
- Produces: `crawlQuire()` module pipeline

- [x] **Step 1: Implement Quire Overview & Views phase**
  Capture:
  - Sample document default view (`viewPrint`).
  - Blank document (`quire/?new`).
  - Views: `viewNormal`, `viewWeb`, `viewReading`, `viewOutline`, `printPreview`, `fullScreen`.
  - Look variants: `paper` overview and `paper2016` (Ribbon) overview, then reset back to `classic`.

- [x] **Step 2: Implement Quire Task Panes phase**
  Iterate through Task Panes: `getting-started`, `new`, `clipboard`, `research`, `styles`, `reveal-formatting`, `mail-merge`, `clipart`, `reviewing`, and `recovery`. Capture each pane docked on the right.

- [x] **Step 3: Implement Quire Menus & Cascading Submenus phase**
  Loop through `L.app.menuBar.menus` (`File`, `Edit`, `View`, `Insert`, `Format`, `Tools`, `Table`, `Window`, `Help`):
  - Open top-level menu via `menuBar.openIndex(i)` and capture.
  - Query all `.m-item.has-sub` within the menu.
  - Hover each to open cascading submenu, capture, then close back to root menu.

- [x] **Step 4: Implement Quire Toolbars & Pickers phase**
  - Enable all toolbars: `standard`, `formatting`, `drawing`, `tables`, `reviewing`, `picture`, `outlining`, `headerFooter`, `mailMerge`, `wordart`. Capture full toolbar layout.
  - Trigger all pickers/dropdowns: Style combo list, Font combo list, Font Size combo list, Zoom combo list, Undo/Redo split menus, Table grid picker, Columns picker, Line Spacing menu, Borders palette, Highlight color grid, Font color palette, Shading color palette, AutoShapes categories (`Lines`, `Basic Shapes`, `Block Arrows`, `Flowchart`, `Stars and Banners`, `Callouts`), Draw menu & submenus (`Order`, `Nudge`, `Align`, `Rotate`), Line Weight, Dash Style, Arrow Style, Shadow Style, LettersArt warp gallery, Text Wrapping menu.

- [x] **Step 5: Implement Quire Context Menus & Seeding phase**
  - Seed table, floating shape, image, hyperlink, and comment into the document.
  - Dispatch `contextmenu` events on: paragraph text, misspelled word, hyperlink, table cell, floating shape, image, and ruler. Capture each context menu.

- [x] **Step 6: Implement Quire Dialogs & Multi-Tab phase**
  Iterate through all Quire dialog commands:
  - `pageSetup` (Tab 1 Margins, Tab 2 Paper, Tab 3 Layout)
  - `fontDlg` (Tab 1 Font, Tab 2 Character Spacing)
  - `paragraphDlg` (Tab 1 Indents and Spacing, Tab 2 Line and Page Breaks)
  - `bulletsDlg` (Tab 1 Bulleted, Tab 2 Numbered, Tab 3 Outline Numbered)
  - `bordersDlg` (Tab 1 Borders, Tab 2 Page Border, Tab 3 Shading)
  - `columnsDlg`, `tabsDlg`, `dropCap`, `themeDlg`, `autoFormat`, `spelling`, `wordCount`, `trackChanges`, `protectDoc`
  - `autocorrectDlg` (Tab 1 AutoCorrect, Tab 2 AutoFormat As You Type)
  - `optionsDlg` (Tab 1 General, Tab 2 View, Tab 3 Edit, Tab 4 Print, Tab 5 Save, Tab 6 Spelling & Grammar, Tab 7 User Information)
  - `tableProps` (Tab 1 Table, Tab 2 Row, Tab 3 Column, Tab 4 Cell), `insertTable`, `tableAutoFormat`, `sortDlg`, `formulaDlg`
  - `bookmark`, `hyperlink`, `insertSymbol`, `dateTime`, `insertBreak`, `find`, `replace`, `goTo`, `mailMergeWizard`, `wordartGallery`, `moreColors` (Standard, Custom), `fillEffects` (Gradient, Texture, Pattern, Picture)
  - For each dialog, if `.dlg .tabs-head .tab` exists, cycle through every tab and capture.

- [x] **Step 7: Run Quire crawl and verify**
  Run: `node .vibeoffice/tools/crawl-screenshots.mjs --only quire`
  Expected: Clean execution without hanging; all Quire screenshots saved under `.vibeoffice/screenshots/01_quire/`.

- [x] **Step 8: Commit**
  ```bash
  git add .vibeoffice/tools/crawl-screenshots.mjs .vibeoffice/screenshots/01_quire/ .vibeoffice/screenshots/INDEX.md
  git commit -m "feat(screenshots): add Quire exhaustive screenshot suite"
  ```

---

### Task 3: Ledger (Spreadsheet) Exhaustive Crawler

**Files:**
- Modify: `.vibeoffice/tools/crawl-screenshots.mjs`
- Output: `.vibeoffice/screenshots/02_ledger/*.png`

**Interfaces:**
- Consumes: `window.L`, `L.ui`, `L.grid`, `L.dlg`, `L.app`, `L.ops`, `L.csv`
- Produces: `crawlLedger()` module pipeline

- [x] **Step 1: Implement Ledger Overview & Views phase**
  Capture:
  - Sample workbook default view.
  - Blank workbook (`ledger/?new`).
  - View modes: `viewNormal`, `viewPageBreak`, `printPreview`, `fullScreen`.
  - Look variants: `paper` overview, `paper2016` Ribbon overview.

- [x] **Step 2: Implement Ledger Task Panes phase**
  Capture right-side Task Panes: `getting-started`, `new`, `clipboard`, `research`, `clipart`, `recovery`.

- [x] **Step 3: Implement Ledger Menus & Cascading Submenus phase**
  Iterate `L.app.menuBar.menus` (`File`, `Edit`, `View`, `Insert`, `Format`, `Tools`, `Data`, `Window`, `Help`):
  - Capture top-level menu.
  - Hover and capture all cascading submenus (`.m-item.has-sub`).

- [x] **Step 4: Implement Ledger Toolbars & Pickers phase**
  - Enable toolbars: `standard`, `formatting`, `borders`, `auditing`, `reviewing`, `list`, `chart`, `drawing`. Capture complete toolbars bar.
  - Trigger all pickers/dropdowns: Font combo, Font Size combo, Zoom combo, AutoSum split menu, Fill Color palette, Font Color palette, Borders palette, Drawing draw menu, Chart Type menu, List actions menu.

- [x] **Step 5: Implement Ledger Context Menus & Seeding phase**
  - Seed workbook with cell values, formula, cell comment, conditional formatting, chart, and second sheet tab.
  - Dispatch `contextmenu` on: normal cell, cell with comment, table/list cell, column header, row header, sheet tab, sheet tab navigation buttons (`#tabnav`), status bar auto-calculate area (`#statusbar .calc`), and chart object. Capture each.

- [x] **Step 6: Implement Ledger Dialogs & Multi-Tab phase**
  Iterate all Ledger dialogs:
  - `formatCells` (Tab 1 Number, Tab 2 Alignment, Tab 3 Font, Tab 4 Border, Tab 5 Patterns, Tab 6 Protection)
  - `pageSetup` (Tab 1 Page, Tab 2 Margins, Tab 3 Header/Footer, Tab 4 Sheet)
  - `styleDlg`, `conditionalFormat`, `sortDlg`, `autoFilter`, `advancedFilter`, `dataForm`, `subtotals`
  - `validation` (Tab 1 Settings, Tab 2 Input Message, Tab 3 Error Alert)
  - Text Import Wizard (`L.csv.importDialog` Step 1, Step 2, Step 3)
  - `consolidate`, `dataTable`, `pivotTable` (Wizard steps)
  - `goalSeek`, `scenarios`, `evaluateFormula`, `watchWindow`, `protectSheet`, `protectWorkbook`, `allowEditRanges`
  - `insertFunction`, `insertCells`, `deleteCells`, `nameDefine`, `tabColor`, `moveCopySheet`
  - `options` (Tab 1 View, Tab 2 Calculation, Tab 3 Edit, Tab 4 General, Tab 5 Color)
  - `chartWizard` (Step 1 Chart Type, Step 2 Source Data, Step 3 Chart Options, Step 4 Location)
  - `moreColors` (Standard, Custom)

- [x] **Step 7: Run Ledger crawl and verify**
  Run: `node .vibeoffice/tools/crawl-screenshots.mjs --only ledger`
  Expected: Clean execution without hanging; all Ledger screenshots saved under `.vibeoffice/screenshots/02_ledger/`.

- [x] **Step 8: Commit**
  ```bash
  git add .vibeoffice/tools/crawl-screenshots.mjs .vibeoffice/screenshots/02_ledger/ .vibeoffice/screenshots/INDEX.md
  git commit -m "feat(screenshots): add Ledger exhaustive screenshot suite"
  ```

---

### Task 4: Lectern (Presentations) Exhaustive Crawler

**Files:**
- Modify: `.vibeoffice/tools/crawl-screenshots.mjs`
- Output: `.vibeoffice/screenshots/03_lectern/*.png`

**Interfaces:**
- Consumes: `window.L`, `L.ui`, `L.ed`, `L.dlg`, `L.app`, `L.panes`
- Produces: `crawlLectern()` module pipeline

- [x] **Step 1: Implement Lectern Overview & Views phase**
  Capture:
  - Sample presentation default view (`viewNormal`).
  - Blank presentation (`lectern/?new`).
  - View modes: `viewSorter`, `viewNotes`, `viewMaster`, `preview`, `slideShow` (first slide presentation mode).
  - Look variants: `paper` overview, `paper2016` Ribbon overview.

- [x] **Step 2: Implement Lectern Task Panes phase**
  Capture Task Panes: `getting-started`, `new`, `slideLayout`, `slideDesign`, `colorSchemes`, `animSchemes`, `customAnim`, `transitionPane`, `clipboard`, `clipart`, `recovery`.

- [x] **Step 3: Implement Lectern Menus & Cascading Submenus phase**
  Iterate `L.app.menuBar.menus` (`File`, `Edit`, `View`, `Insert`, `Format`, `Tools`, `Slide Show`, `Window`, `Help`):
  - Capture top-level menu.
  - Hover and capture all cascading submenus (`.m-item.has-sub`).

- [x] **Step 4: Implement Lectern Toolbars & Pickers phase**
  - Enable toolbars: `standard`, `formatting`, `drawing`, `outlining`, `picture`, `tables`, `wordart`, `diagram`, `master`, `sorter`. Capture toolbars.
  - Trigger all pickers/dropdowns: Font combo, Size combo, Zoom combo, Color dropdowns (Fill, Line, Font), AutoShapes categories and grids, Line Style, Dash Style, Arrow Style, Shadow Style, Picture Color mode, Table Borders picker, Table Fill color, LettersArt warp menu, Diagram layout/color/style menus.

- [x] **Step 5: Implement Lectern Context Menus & Seeding phase**
  - Seed slide with text box, shape, table, chart, and SmartArt diagram.
  - Dispatch `contextmenu` on: slide background, text box, shape, table cell, chart, SmartArt diagram, left slide thumbnail, sorter tile, and slide show screen. Capture each.

- [x] **Step 6: Implement Lectern Dialogs & Multi-Tab phase**
  Iterate all Lectern dialogs:
  - `pageSetup`, `fontDlg`, `bulletsDlg`, `lineSpacing`, `replaceFonts`, `background`
  - `formatObject` (Tab 1 Colors and Lines, Tab 2 Size, Tab 3 Position, Tab 4 Picture, Tab 5 Text Box)
  - `setupShow`, `actionSettings`, `customAnim` timing/effects, `insertTable`, `tableBordersFill`
  - `insertChart`, `photoAlbum`, `autocorrectDlg`
  - `optionsDlg` (Tab 1 View, Tab 2 General, Tab 3 Edit, Tab 4 Print, Tab 5 Save)
  - `moreColors`, `fillEffects`

- [x] **Step 7: Run Lectern crawl and verify**
  Run: `node .vibeoffice/tools/crawl-screenshots.mjs --only lectern`
  Expected: Clean execution without hanging; all Lectern screenshots saved under `.vibeoffice/screenshots/03_lectern/`.

- [x] **Step 8: Commit**
  ```bash
  git add .vibeoffice/tools/crawl-screenshots.mjs .vibeoffice/screenshots/03_lectern/ .vibeoffice/screenshots/INDEX.md
  git commit -m "feat(screenshots): add Lectern exhaustive screenshot suite"
  ```

---

### Task 5: End-to-End Execution, Artifact Generation & Verification

**Files:**
- Output: Full suite of screenshots in `.vibeoffice/screenshots/`
- Output: Final `.vibeoffice/screenshots/INDEX.md`

- [x] **Step 1: Execute full crawl across all 4 modules**
  Run: `node .vibeoffice/tools/crawl-screenshots.mjs`
  Expected: Sequential completion of Start Center, Quire, Ledger, and Lectern.

- [x] **Step 2: Verify screenshot file integrity and non-emptiness**
  Run automated check verifying:
  - All PNG files > 10KB.
  - Total screenshots count exceeds 250+.
  - All four subfolders are populated.

- [x] **Step 3: Verify and format `.vibeoffice/screenshots/INDEX.md`**
  Check that `INDEX.md` contains accurate links, module badges, sequence numbers, action names, and GUI targets.

- [x] **Step 4: Commit final index and artifacts**
  ```bash
  git add .vibeoffice/screenshots/
  git commit -m "chore(screenshots): complete exhaustive VibeOffice UI screenshot suite and index"
  ```
