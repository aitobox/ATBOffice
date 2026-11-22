# Issue #445 — Lectern toast-only stubs, ID collisions and broken insertion

## Findings (survey)
- 83 user-reachable Lectern actions (visible menus + mounted toolbars) have no handler;
  27 bound handlers only show a status-bar toast.
- `save_as_dialog()` calls `save_file()` (silent overwrite).
- `insert_chart` inserts a rectangle; `insert_picture_from_file` never prompts and inserts
  an empty frame; `insertClipArt` is routed to the picture stub.
- WordArt/Clipart insertion helpers call `window.add_shape`, which `LecternWindow` lacks
  (silent no-op). The clipart helper also passes an unknown `svg_content` kwarg to `Shape`.
- `_create_photo_album_slides` calls the nonexistent `Shape.create_picture` (crash).
- Draw > Align Left/Center/Right reuse the checkable paragraph actions (`alignLeft`…).
- `open_action_settings_dialog` reads `item.shape` (always missing) and discards settings.
- Table ops write dummy flags (`merged`, `split`, `border_type`, `valign`) and never repaint;
  double-click on a table edits the table shape's own text body.
- Arrowheads (`Line.head/tail`) are modelled but never painted.
- Master view: `set_view_mode("master")` edits on the normal canvas while `SlideMasterView`
  keeps a second, unused scene; the workspace's embedded task pane duplicates the window dock.
- Lectern has no undo stack (out of scope; noted in PR).

## Design
New focused modules (no monolith growth):
- `modules/presentation/tools/table_ops.py` — pure ops on the `tbl` dict: cell geometry and
  hit-testing, merge/split (gs/rs/hm/vm), insert/delete row/col at the active cell,
  distribute, per-side borders (`bd`), shading (`fill`), vertical anchor (`tx.anchor`).
- `modules/presentation/tools/pictures.py` — picture shape factory: embeds bytes in
  `presentation.props["_media_map"]`, aspect-fit sizing, unique media keys.
- `modules/presentation/tools/text_search.py` — `PresentationSearchAdapter` for the shared
  `FindReplaceDialog` (shapes, groups, table cells, notes); run-preserving range replace.
- `modules/presentation/tools/spelling.py` — `PresentationSpellChecker` (same protocol as
  `SheetSpellChecker`) reused by the shared spelling dialog via `describe_issue`.
- `modules/presentation/tools/outline_ops.py` — summary slide, paragraph move up/down.
- `modules/presentation/tools/shape_styles.py` — dash/arrow/shadow/weight presets.
- `modules/presentation/views/table_cell_editor.py` — in-place cell editor subclassing
  `ShapeTextEditorItem` that commits into the cell's `tx`.
- `ui/shell/lectern_commands.py` — `LecternCommands`: real handlers + `bind()` for all
  wired IDs (Find/Replace, Spelling, Hyperlink, Format Painter, Masters, Summary Slide,
  Speaker Notes, Transition pane, table pen state, diagram layout/colours/style, WordArt
  spacing/shape/justify, picture weight & transparent colour, drawing dash/arrow/shadow,
  view/slideshow/insert/format menu IDs).

Window/view edits: Save As, real chart/picture/clipart insertion, `add_shape`, action
settings on `item.model`, inherited `show_help`, distinct `draw_align_*` IDs, master view on
`SlideMasterView` sharing the workspace scene, embedded task pane disabled in favour of the
dock, arrowhead painting, table active-cell highlight, canvas rulers for View > Ruler.

Menu items with no PowerPoint 2003 equivalent (Insert > Page Break, Format > Tabs,
Format > Borders) are hidden in Lectern instead of being stubbed.

## Task list
- [ ] Save As, chart, picture, clipart, add_shape, photo album
- [ ] Draw align ID split + menu/toolbar ID alignment
- [ ] Table ops module, cell editor, repaint
- [ ] Find/Replace, Spelling, Hyperlink, Format Painter
- [ ] Masters, master view, task pane dedupe, transition pane
- [ ] Summary slide, paragraph move, speaker notes, outline toggles
- [ ] Drawing/picture/WordArt/diagram style handlers, arrowheads, ruler
- [ ] Tests `tests/gui/test_phase11_lectern_ui_wiring.py`, full suite, ruff
