# Plan: Issue #438

1. Write `tests/gui/test_phase11_lifecycle_and_save_safety.py` (close stress, main-window retarget,
   no 0-byte exports, unsupported formats, password round-trip, recovery start/stop/draft). Run → fail.
2. `base_window.py`: closeEvent (no drain, clear draft), `UnsupportedSaveFormatError`,
   `confirm_compatibility_losses`, password state + re-encrypt in `save_file`, recovery start helper.
3. `window_manager.py`: `_closing_windows` deferred release; `_main_window` retarget.
4. `recovery_service.py`: property-aware modified check, native suffix, autosave flag, encryption, failure.
5. Quire/Ledger/Lectern `do_save` + `recovery_suffix`.
6. Verify the targeted tests, then `tests/gui/test_file_safety_regression.py`, then the full suite + ruff.
