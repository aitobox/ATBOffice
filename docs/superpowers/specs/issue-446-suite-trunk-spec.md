# Issue #446 — Suite trunk: Clip Art / WordArt, Office Clipboard, Undo history, Start Center

## Findings
- `prompt_insert_clipart` / `prompt_insert_wordart` probe for `add_shape`, `current_slide`,
  `insert_image`, `insert_drawing_object`; Quire and Ledger have none (silent no-op) and the
  clip-art Lectern branch builds `Shape(svg_content=…)` (TypeError). WordArt never carries its text.
- `ClipboardTaskPane.paste_item` restores text/HTML only; nothing opens the pane from the menu;
  the New Document pane's "Blank Web page" action is ignored by `_on_task_pane_action`.
- Undo/Redo split menus hold one fixed disabled item. Quire (`canvas._undo_stack`) and Ledger
  (`grid._undo_stack`) keep dict entries; Lectern has no undo stack.
- Start Center shows emoji icons for recents and 8 of the 22 registered templates; no recovery
  list. `CommandSearchBox` has no recents, breadcrumbs or typo tolerance. `ScoutWidget` runs a
  permanent 25 fps timer.
- `confirm_compatibility_losses` exists but no reader records losses, so it never fires.
- The Paper 2016 card promises a ribbon; the style maps it to the classic Paper toolbars.

## Design
- **Insertion adapter**: every editor implements `insert_image_bytes(data, ext, name)`
  (Quire inline picture, Ledger floating image, Lectern picture). `insert_clip_art` /
  `insert_wordart` in the common modules render to PNG (WordArt via `render_wordart`, warp kept)
  and call it. Lectern keeps the WordArt spec on the shape so toolbar warp changes re-render.
- **Office Clipboard**: image clips restore `imageData`; Quire copy also places HTML;
  Edit > Office Clipboard (`officeClipboard`); `new_web` opens a new document (Quire switches
  to Web Layout).
- **Undo history**: `ui/components/undo_history.py` fills the `undo`/`redo` split menus on
  `aboutToShow` from `window.undo_history("undo"|"redo")`; choosing item *n* undoes/redoes
  *n* steps. Quire and Ledger label their stack entries; Lectern reports no history.
- **Start Center**: editors cache a page-1 / grid / slide-1 PNG thumbnail on open and save
  (`core/thumbnails.py`); recent rows show it. Templates come from `TemplateRegistry` (all 22).
  Orphaned recovery drafts are listed with Open / Discard.
- **Command search**: shared MRU of executed commands shown on empty focus, menu breadcrumbs,
  edit-distance-1 token matching.
- **Scout**: animation runs in short bursts (show, speak, command, periodic blink single-shot)
  and is fully idle otherwise; reacts to `ActionRegistry.action_triggered`; balloon buttons.
- **Compatibility checker**: `core/compat.py` computes save losses per target format
  (macros dropped, CSV single sheet / values only, plain-text and Markdown formatting, legacy
  binary formats) plus model `losses`; only `notify: True` items are shown in a structured
  dialog (feature, where, count).
- **Theme**: Paper 2016 card text states what it is (Paper colours, classic toolbars).

## Task list
- [ ] Clip Art / WordArt insertion in all three editors
- [ ] Office Clipboard image paste, Quire rich copy, Edit > Office Clipboard, new_web
- [ ] Dynamic Undo/Redo history menus
- [ ] Start Center thumbnails, 22 templates, recovery list; command search; Scout
- [ ] Compatibility checker dialog; Paper 2016 description
- [ ] Tests `tests/gui/test_phase11_suite_trunk.py`, suites, ruff
