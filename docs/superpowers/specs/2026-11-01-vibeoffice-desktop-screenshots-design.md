# VibeOffice Desktop UI Exhaustive Screenshot Crawler Design

## 1. Intent & Why

We are porting `.vibeoffice` (a ~200k-line Office 2003-inspired suite comprising Start Center, Quire word processor, Ledger spreadsheet, and Lectern presentation editor) to Python 3.12+ / PySide6 (`ATBOffice`). To achieve 1:1 visual and interactive fidelity and support visual regression/parity audits, we need an exhaustive, systematically named reference library of screenshots from the original `.vibeoffice` desktop app stored in `.vibeoffice/screenshots/`.

Every user-reachable surface in the default desktop mode (`classic` Office 2003 Luna look, English UI `lang=en`) must be captured by simulating human interactions step by step: overall interfaces, view modes, task panes, menu bar dropdowns and cascading submenus, every toolbar (including contextual/hidden toolbars) and its dropdowns/pickers/combos, context menus across different selection states, and every associated GUI dialog (including every tab inside multi-tabbed dialogs).

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
- **Complete Module Coverage**: Capture all 4 modules into module-specific subdirectories under `.vibeoffice/screenshots/`:
  - `00_start_center/`
  - `01_quire/`
  - `02_ledger/`
  - `03_lectern/`
- **Desktop Environment Fidelity**: Run `.vibeoffice/public/` through local Chromium over CDP (`127.0.0.1:9222`) with `.vibeoffice/tests/desktop/host-stub.js` injected via `Page.addScriptToEvaluateOnNewDocument` so `window.__VO_HOST__` and `window.__TAURI_INTERNALS__` behave identically to the native Tauri desktop build (desktop file/recent-file bindings, UI scale, desktop settings, update checks, and window menu items).
- **Target Look & Language**: Default to `classic` look (`VO.look.set('classic')`, matching `ATBOffice`'s `luna_2003.py` target) and English UI (`lang=en`). Also capture theme-switching previews (`paper`, `paper2016` Ribbon overview) in Start Center and app overview shots for completeness.
- **Reflective & Context-Seeded Crawling**:
  - Automatically discover and open all top-level menus (`L.ui.menus`) and hover-expand all cascading `.has-sub` submenus.
  - Force-enable and capture all hidden/contextual toolbars (`tables`, `reviewing`, `picture`, `outlining`, `headerFooter`, `mailMerge`, `wordart`, `borders`, `auditing`, `list`, `chart`, `drawing`, `diagram`, `master`, `sorter`).
  - Trigger every toolbar split-button arrow (`.tb-dd`), dropdown button (`.tb-drop`), and combo box arrow (`.combo-btn`) to capture color palettes, border grids, table grids, font/size/style/zoom lists, and AutoShapes menus.
  - Seed rich document states (text paragraphs, tables, shapes, WordArt/LettersArt, charts, SmartArt/IntelliArt diagrams, comments, pivot tables) so context-dependent commands and dialogs are enabled and populated.
  - Trigger every GUI dialog (`L.dlg` / `L.ui.cmds`), detect internal tab strips (`.dlg .tabs-head .tab`), and step through **every tab** of every multi-tab dialog, taking a screenshot per tab.
- **Descriptive Action- & Dialog-Based Naming**: Name every screenshot using `<seq>_<category>_<action_or_trigger>__<gui_target_or_dialog>.png` (e.g., `042_dialog_cmd_pageSetup__Page_Setup_tab1_Margins.png`, `015_menu_Insert_sub_Picture.png`, `028_toolbar_Formatting_dropdown_Font_Color.png`), accompanied by a generated `.vibeoffice/screenshots/INDEX.md` catalog mapping each filename to its module, trigger action, command ID, and GUI dialog/tab title.

### Non-Goals
- Compiling the Rust Tauri wrapper (`cargo` is not installed on this machine, and OS-level window screenshots cannot reliably introspect internal DOM menus/tabs without focus races).
- Capturing every permutation of non-English translations (`ja`, `ko`, `fr`, `de`, etc.).
- Modifying any production source files inside `.vibeoffice/public/` or `src/atboffice/`.

### Anti-Goals (What Would Make This a Failure)
- **Blank, half-rendered, or stacked overlapping modals**: Failing to wait for layout/repaint (`requestAnimationFrame` + settle pause) or failing to close a previous menu/dialog before opening the next one.
- **Skipped context-sensitive dialogs**: Invoking commands like `tableProps`, `formatObject`, `wordartEdit`, or `diagramLayout` when no table/shape/WordArt/diagram is selected, resulting in a no-op instead of capturing the dialog.
- **Hitting native OS file pickers (`<input type="file">`) that block or show nothing in headless/CDP screenshots**: File open/import wizards (e.g., CSV Text Import Wizard, Insert Picture) must be triggered with synthetic in-memory `File`/`Uint8Array` payloads where applicable so their actual in-app GUI dialogs are captured.
- **Closing user's other Chromium tabs**: Per `.vibeoffice/AGENTS.md`, never close existing browser tabs; open and close only the crawler's dedicated CDP target tab.

## 3. Constraints

- **No Production Code Mutation in `.vibeoffice/public/`**: `.vibeoffice` checks `public/` content hashes for UI test records. The crawler script will live at `.vibeoffice/tools/crawl-screenshots.mjs` (or run from scratch/tools) and output strictly to `.vibeoffice/screenshots/` (plus documentation/index inside `.vibeoffice/screenshots/`).
- **Viewport & Format**: Standard desktop viewport `1280×800` (with `deviceScaleFactor: 1`, `Emulation.setFocusEmulationEnabled: true`) saved as crisp lossless `.png` files.
- **CSP Compliance**: `.vibeoffice` pages enforce strict Content-Security-Policy (`script-src 'self'`). All in-page inspection and triggers must run via CDP `Runtime.evaluate` and `Input.dispatchMouseEvent` / `Input.dispatchKeyEvent`, never by injecting inline `<script>` tags into the DOM.

## 4. Approaches Considered

### Approach A (Selected): Single-Session Reflective Crawler over CDP + `host-stub.js`
A dedicated Node.js script (`.vibeoffice/tools/crawl-screenshots.mjs`) reuses `.vibeoffice/tools/ooxml/cdp.mjs` and `.vibeoffice/tests/lib/input.mjs` primitives, preloads `tests/desktop/host-stub.js`, keeps a single tab open per module, seeds document objects (tables, shapes, charts, etc.), and reflectively walks the live UI registries (`L.ui.menus`, `L.app.toolbarsEl` / `TB`, `L.panes`, `L.dlg`, `L.ui.cmds`), automatically iterating over submenus and dialog tabs.
- **Pros**: Fast (no tab recreation per shot), 100% coverage of hidden toolbars, context-dependent dialogs, and multi-tab dialogs; deterministic cleanup between shots.
- **Cons**: Requires carefully resetting modal stacks (`L.ui.closeMenus()`, closing `.dlg-overlay`) between steps.

### Approach B: Batch `tools/shot.mjs` JSON Invocations
Generate static `steps.json` files and invoke `node tools/shot.mjs` repeatedly.
- **Pros**: Zero new runner code.
- **Cons**: Spawns a new tab and reloads the app for every batch; cannot dynamically inspect dialog tabs or submenu bounding boxes without hardcoding hundreds of selectors.

### Approach C: Pure Coordinate-Based DOM Monkey
Click every `<button>` by coordinates without consulting `L.ui` or seeding document state.
- **Pros**: Pure blackbox.
- **Cons**: Misses disabled context commands, hidden toolbars, and deep dialog constructors.

**Decision**: Partner selected **Approach A**.

## 5. Architecture & Crawling Pipeline

### 5.1 Directory & Naming Convention
Output root: `.vibeoffice/screenshots/`
```
.vibeoffice/screenshots/
├── INDEX.md                                      # Full manifest table of all screenshots
├── 00_start_center/
│   ├── 001_overview_recent_files_populated.png
│   ├── 002_overview_recent_files_empty_welcome.png
│   ├── 003_overview_create_file_templates.png
│   ├── 004_dialog_settings__Settings.png
│   ├── 005_dialog_themes__Themes_classic.png
│   ├── 006_dialog_themes__Themes_paper.png
│   ├── 007_dialog_themes__Themes_paper2016.png
│   ├── 008_dialog_about__About_VibeOffice.png
│   ├── 009_dialog_update__Update_VibeOffice.png
│   └── 010_window_oss_licenses__Open_Source_Licenses.png
├── 01_quire/
├── 02_ledger/
└── 03_lectern/
```

Within each app folder (`01_quire`, `02_ledger`, `03_lectern`), filenames follow a strict, sortable schema:
`<NNN>_<category>_<action_or_control>__<associated_gui_or_dialog>.png`

Categories in execution order:
1. `overview`: Default sample document, blank document, all view modes (e.g., Normal, Web Layout, Print Layout, Reading Layout, Outline, Page Break Preview, Slide Sorter, Notes Page, Slide Master, Slide Show, Print Preview), plus a reference shot in `paper` and `paper2016` (Ribbon) looks.
2. `pane`: Every right-hand Task Pane (Getting Started, New Document/Workbook/Presentation, Clipboard, Search/Research, Styles and Formatting, Reveal Formatting, Mail Merge, Clip Art, Document Recovery, Slide Layout, Slide Design, Color Schemes, Animation Schemes, Custom Animation, Slide Transition, Document Map, Thumbnails, Reviewing Pane).
3. `menu`: Every top-level menu bar item (`File`, `Edit`, `View`, `Insert`, `Format`, `Tools`, `Table`/`Data`/`Slide Show`, `Window`, `Help`) opened via `A.menuBar.openIndex(i)`, followed immediately by hovering every `.m-item.has-sub` item in that menu to capture each cascading submenu (`023_menu_Insert_sub_Picture.png`, `024_menu_Table_sub_Insert.png`, etc.).
4. `toolbar`:
   - Full visibility shots of all toolbars (Standard, Formatting, Drawing, and all auxiliary toolbars toggled on).
   - Every dropdown/split/combo control on every toolbar: Style combo, Font combo, Font Size combo, Zoom combo, Undo/Redo history stacks, Insert Table grid, Columns grid, Line Spacing menu, Borders palette, Highlight color palette, Font Color palette, Fill Color palette, Line Color palette, AutoSum menu, Chart Type menu, AutoShapes menu and each of its shape category sub-grids (`Lines`, `Connectors`, `Basic Shapes`, `Block Arrows`, `Flowchart`, `Stars and Banners`, `Callouts`, `Action Buttons`), Draw menu and its submenus (`Order`, `Nudge`, `Align or Distribute`, `Rotate or Flip`), Line Weight, Dash Style, Arrow Style, Shadow Style, LettersArt (WordArt) Shape warps, Picture Color mode, Text Wrapping menu, Reviewing markup/show menus, Header & Footer AutoText menu, Diagram (IntelliArt) Layout/Colors/Styles menus, and Status Bar AutoCalculate menu.
5. `context`: Context menus (`contextmenu` event) dispatched on distinct document targets:
   - **Quire**: Body text, misspelled word, hyperlink, table cell, floating shape/image, comment/tracked change, header/footer area, ruler.
   - **Ledger**: Standard cell, cell with comment, filtered table cell, column header, row header, sheet tab (`#tabs .stab`), sheet tab navigation arrows (`#tabnav`), status bar AutoCalculate (`#statusbar .calc`), floating chart, floating shape.
   - **Lectern**: Slide background, text box (editing vs selected), shape, table cell, chart, SmartArt diagram, slide thumbnail in left pane, Slide Sorter tile, Slide Show screen.
6. `dialog`: Every modal and modeless dialog in the module, triggered via `L.dlg.*`, `L.ui.exec(cmd)`, or `L.ui.*` helpers (`ui.moreColors`, `ui.linkDialog`, `ui.password`, `ui.compatibility`, `L.assistant.show()`).
   - **Multi-Tab Dialog Expansion**: Whenever `.dlg` is open, the crawler queries `.dlg .tabs-head .tab`. If 2+ tabs exist, it clicks each tab `k` (`0..N-1`), waits for repaint, and saves `<NNN>_dialog_<trigger>__<Dialog_Title>_tab<k+1>_<Tab_Label>.png`.
   - **Sub-Dialogs**: Dialogs launched from inside another dialog (e.g., `Fill Effects...` with Gradient/Texture/Pattern/Picture tabs, `More Colors...` with Standard/Custom tabs, `Page Setup -> Options`, `Paragraph -> Tabs`, `Table Properties -> Borders and Shading`, `Custom AutoFilter`) are also triggered and captured across all their tabs.

### 5.2 State Seeding & Modal Reset Protocol
To guarantee that no dialog fails to open due to missing selection state and no modal leaks into subsequent screenshots:
- **Helper `resetUI()`** run before every single capture:
  1. Close any open menus: `if (window.L && L.ui) L.ui.closeMenus();`
  2. Close any open dialogs: while `document.querySelector('.dlg-overlay')`, click `.dlg-x` or dispatch `Escape` and remove leftover `.dlg-overlay`.
  3. Cancel any active brush or drag: `if (L.ui && L.ui.brushOn()) L.ui.brushOn().stop(); if (L.ui && L.ui.dragCancel) L.ui.dragCancel();`
  4. Wait 2 animation frames + 80ms for layout/canvas settle.
- **Context Seeder per App**:
  - Before running context-dependent toolbar/context-menu/dialog phases, programmatically insert and select the required object (e.g. `L.tables.insert(3, 3)` in Quire; `O.setCell` + chart/shape/pivot creation in Ledger; shape/table/chart/wordart/diagram insertion on a slide in Lectern), capture all dialogs/menus for that context, and then restore clean state.

### 5.3 Builder Decisions (Left to the Builder)
- Exact sequence numbering padding (`001`..`999` per module folder).
- Handling browser-native `<input type="file">` commands by invoking the underlying dialog function directly with sample bytes (e.g., calling `L.csv.importDialog(sampleBytes, 'Sample.csv', { wizard: true })` for Ledger's Text Import Wizard).
- Automatically generating `.vibeoffice/screenshots/INDEX.md` at the end of the run with total counts per module and category.
