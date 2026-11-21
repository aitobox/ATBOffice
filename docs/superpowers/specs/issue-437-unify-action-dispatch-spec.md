# Spec: Issue #437 — Unify ActionRegistry & MacMenuBar dispatch

## Problem
1. `MacMenuBar._bind_window_slots` connects extra `triggered` lambdas onto QActions that
   `ActionRegistry` already dispatches, so handlers run 2–3x per trigger.
2. `_reg_act` registers aliases only in `_actions`, so `set_handler(alias, ...)` silently drops.
3. Actions wired only via `connect_if` keep `spec.handler = None` and flash the
   "正在联调中" fallback toast; `insert_*` picture actions appear twice; app-specific items
   show in every app; Start Center exposes editor actions it cannot run.

## Design
- `ActionRegistry` gains an alias table (`register_alias`, `resolve_id`). Every public lookup
  (`get_action`, `get_spec`, `has_action`, `set_handler`, `set_enabled`, `set_checked`,
  `is_enabled`, `is_checked`, `trigger_action`, `register_action`) resolves aliases to the
  canonical id first. Handlers set on an alias before the alias exists are migrated.
- The registry's single `triggered` connection stays the **only** dispatch path. `connect_if`
  becomes "bind a default handler via `set_handler` only if the canonical spec is unbound";
  window `set_handler` calls later override (replace, never stack). Ledger's `print_workbook`
  is preferred over `print_document`.
- Duplicate `insert_clipart/picture/wordart/shape` entries in the Insert menu are removed (kept
  in the Picture submenu).
- App-specific items are shown only for their apps (`_APP_SPECIFIC_ACTIONS`), refreshed by
  `set_app_type`/`retranslate_ui`:
  quire: view_web, view_print, view_reading, view_outline, view_doc_map, view_thumbnails,
  wordCount, stylesPane; ledger: view_page_break, insert_function; lectern: background.
- `StartCenterWindow` binds new (template gallery), open, close, about, help, theme_*, options,
  and disables every other editor action with a localized `disabled_reason`.
- `_show_getting_started_pane`/`switch_pane` no longer exists on `main` (verified by grep), so
  nothing changes there.

## Edge cases
- Handler exceptions stay logged, not raised. Re-registering a spec under an alias id updates
  the canonical spec and keeps its handler. A disabled action never dispatches.
- Retranslation must not re-show hidden app-specific items.

## Task list
- [ ] Task 1: Alias-aware ActionRegistry + unit tests
- [ ] Task 2: Single-dispatch MacMenuBar binding (no extra triggered connections)
- [ ] Task 3: Remove duplicate insert actions; gate app-specific items by app_type
- [ ] Task 4: Start Center handlers + clean disabling of unsupported actions
- [ ] Task 5: Regression tests (1x execution, alias binding, no fallback toast)
- [ ] Task 6: Full suite pass + grill audit
