# Spec: Issue #438 — Window close use-after-free, 0-byte saves, RecoveryService lifecycle

## Design
1. **Close lifecycle** — `BaseOfficeWindow.closeEvent` no longer calls `drain_event_loop` while
   Qt is inside `close_helper`. `WindowManager.unregister_window` keeps the closed window alive in
   `_closing_windows` and releases it on the next event-loop turn (`QTimer.singleShot(0, ...)`),
   so the Python wrapper (and its C++ object) is never destroyed during the close. The app's
   `_main_window` is retargeted to another live window (or the Start Center, or `None`) when the
   closed window was the main window.
2. **No 0-byte saves** — Quire writes `.rtf` (`write_rtf`), `.md/.markdown` (`write_markdown`),
   `.zip` (`write_markdown_zip`) and `.txt` (plain text from paragraphs/tables). Every editor raises
   `UnsupportedSaveFormatError` (localized message, surfaced by `save_file`'s error dialog) for
   formats it cannot write, instead of `path.touch()`.
3. **Compatibility losses** — the Quire loss prompt moves to
   `BaseOfficeWindow.confirm_compatibility_losses(losses)`, and Ledger/Lectern call it with their
   model's `losses` (no-op when the model has none). Autosave never shows the prompt.
4. **Encryption password** — the password typed while opening an encrypted package is kept in memory
   (committed only when the open succeeds, cleared by new/template/plain open). Saving to an OOXML
   format re-encrypts the staged file, and so do recovery drafts.
5. **RecoveryService** — editors declare `recovery_suffix` (`.docx`/`.xlsx`/`.pptx`) and start the
   service in `__init__`, using `save/auto_save_interval` minutes (default 10). Autosave skips unmodified
   documents (fixes the `is_modified` property check), writes drafts with the native suffix when untitled,
   suppresses prompts, and reports `do_save` failures. Drafts are cleared on successful manual save and
   on an accepted close. The service is stopped in `cleanup_resources()`.

## Edge cases
- Close cancelled by the user: the window stays registered and the service keeps running.
- Close called twice / during quit: unregistering is idempotent.
- Save failure: the staging file is removed and the target stays intact (existing behaviour).
- Wrong or cancelled password: the previous document keeps its own password state.

## Task list
- [x] Task 1: Safe close lifecycle (no drain in closeEvent, deferred release, main-window retarget)
- [x] Task 2: Quire RTF/Markdown/ZIP/TXT writers; explicit errors instead of 0-byte touch in all editors
- [x] Task 3: Shared compatibility-loss confirmation for Quire/Ledger/Lectern
- [x] Task 4: Preserve encryption password across open-edit-save
- [x] Task 5: Start RecoveryService cleanly with prompt-free, non-0-byte drafts
- [x] Task 6: Regression tests + full suite + grill audit
