# Plan: Issue #440

1. Tests: `tests/gui/test_phase11_quire_lectern_stability.py`.
2. Quire: `canvas_view.py` (refresh_layout), `caret_controller.py` (single caret_changed),
   `view.py` (lazy review pane), `quire_window.py` (coalesced caret sync).
3. Lectern: `slide_canvas.py`, `text_editor.py`, `workspace.py`, `lectern_window.py` (save sync).
4. Verify the targeted tests, the toolbar/canvas suites, the full suite and ruff.
