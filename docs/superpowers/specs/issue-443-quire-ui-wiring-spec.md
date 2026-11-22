# Spec: Issue #443 — Quire dialogs, menu and toolbar wiring

## Design
- **Undoable document commands**: `WriterCanvasView.run_undoable(mutate)` snapshots the document
  parts a command may touch (body, section, headers/footers, notes, comments, settings, styles,
  numbering) into a `doc_snapshot` undo entry, then relayouts in place.
- **Dialogs** (`writer/views/doc_actions.py`): 28 openers apply accepted results (break, drop cap,
  text direction, watermark, page numbers, change case, theme, footnote, caption, cross-reference,
  index and tables/TOC, bookmarks, hyperlink, date/time, field, symbol, AutoCorrect, options,
  envelopes, letter wizard, AutoSummarize, hyphenation, insert/delete/split cells, table
  AutoFormat/sort/formula). Customize has no result to apply.
- **Menu bar**: Format Font/Paragraph/Borders/Tabs/Columns, Tools Language, Table
  Insert/Delete/Select/Properties, Insert page break/page numbers/date/symbol, column presets
  (1/2/3/left/right, real section `cols`), and the `docMap`/`viewReading` aliases. Outline commands
  dispatch to the outline pane in Outline view and to the canvas otherwise.
- **Toolbars** (`ui/shell/quire_commands.py`): Header & Footer (fields into the header/footer story,
  AutoText, switch/prev/next/close, show text, link previous); Reviewing (display modes, show
  comments/insertions/formatting, previous/next change); Outlining (first line, formatting, show
  level, update/go to TOC); Show/Hide ¶ (pilcrow overlay); Format Painter (applied on the next
  selection); Insert Picture; Tables and Borders (line style/weight/colour, shading, Draw Table,
  Eraser); Mail Merge to new document/printer; the record combo; Reading Layout page-count toggles.
  Drop-down containers are whitelisted. Picture, Drawing and WordArt object commands are disabled
  with a reason until on-canvas object selection exists (#447).
- **Fixes**: 15-colour Word highlight palette ("none" → no highlight, hex → `w:highlight` names),
  highlights painted on screen, paragraph border presets use `BorderProperties`, Zoom "页宽"/"整页",
  Style combo full style IDs, and the context-toolbar state persists. Layout: a tab stored inside a
  text run no longer hangs the portion scanner.

## Task list
- [x] Task 1: Undoable dialog application for the Quire dialog cluster
- [x] Task 2: Menu bindings, aliases, column presets, outline dispatch
- [x] Task 3: Header & Footer / Reviewing / Outlining / marks / painter / reading / mail merge commands
- [x] Task 4: Highlight palette, border presets, zoom & style combos
- [x] Task 5: Regression tests, no fallback toasts on wired actions, full suite
