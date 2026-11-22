# Spec: Issue #440 — Quire undo/caret retention and Lectern editor and scene lifecycle

## Design
### Quire
- `WriterCanvasView.refresh_layout()` repaginates in place. Formatting (`_on_formatting_applied`), the
  table resize release and `insert_table` use it instead of `set_document(self.doc)`, so undo/redo,
  the image cache, the caret and the selection survive.
- `CaretController.repaginate_and_refresh` restarts the blink without a second `caret_changed`.
  `QuireWindow` refreshes immediately on caret moves, collapses identical refreshes within one
  event-loop turn (keyed by document revision, caret and selection), and coalesces selection-only
  changes into one deferred refresh. Result: one toolbar sync per keystroke instead of 3.
- The review pane rebuilds only while visible and refreshes lazily when shown. The Document Map and
  Thumbnails panes already refresh only on demand, and no per-keystroke full-document deepcopy exists
  in the current code.

### Lectern
- `SlideScene.mousePressEvent` commits the active editor (`commit_and_finish`) on an outside click.
- `ShapeTextEditorItem.focusOutEvent` keeps the session when focus goes to a popup or a toolbar
  control, so font, size and colour pickers act on the live editor. Any other focus loss still commits.
- `load_slide` commits pending text before rebuilding (with a re-entrancy guard). `do_save` and
  autosave sync editor text to the model through `sync_active_text_editing()` without ending the session.
- `SlideCanvasView.keyPressEvent` sends every key to the active text editor, so Delete/Backspace/arrows
  never delete or nudge the shape, or rebuild the scene under the focused editor.
- `OutlineEditorWidget` defers caret-driven slide switches to the event loop, and `_on_text_changed`
  now writes titles and body bullets back while reusing the existing paragraph and run formatting.

## Task list
- [x] Task 1: In-place layout refresh for formatting/table edits (undo, caret, selection kept)
- [x] Task 2: Coalesce caret/selection UI refreshes; lazy review pane
- [x] Task 3: Lectern click-outside commit, toolbar-safe focus handling, commit on slide switch/save
- [x] Task 4: Editor-first key routing; deferred outline slide switches; outline body bullet sync
- [x] Task 5: Regression tests + full suite + review
