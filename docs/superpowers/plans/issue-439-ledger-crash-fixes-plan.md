# Plan: Issue #439

1. Tests: `tests/gui/test_phase11_ledger_crash_fixes.py` (focus, key forwarding, empty-cell formatting,
   format painter, multi-sheet status wiring, mouse-move hardening). Run → fail.
2. `object_layer.py`, `sheet_model.py`, `view.py`, `grid_viewport.py`, `ledger_window.py`, `main_window.py`.
3. Verify the targeted tests + `test_crash_replay_diagnostics.py`, then the full suite + ruff.
