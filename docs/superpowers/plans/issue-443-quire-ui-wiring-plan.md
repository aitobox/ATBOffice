# Plan: Issue #443

1. `canvas_view.py`: `run_undoable` + `doc_snapshot` undo; formatting marks; Format Painter; highlights.
2. `writer/views/doc_actions.py`: document operations for every dialog result.
3. `quire_window.py`: rewrite openers, add Format/Table/Tools dialog openers, menu bindings,
   outline dispatch, border/zoom/style fixes, persistent toolbar context.
4. `ui/shell/quire_commands.py`: contextual-toolbar commands and the disabled object commands.
5. `color_picker.py`: highlight mode. 6. Tests: `tests/gui/test_phase11_quire_ui_wiring.py`.
