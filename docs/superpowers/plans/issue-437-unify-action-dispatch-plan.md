# Plan: Issue #437 — Unify action dispatch

1. Write `tests/gui/test_phase11_action_dispatch.py` (registry alias + menu single-dispatch +
   gating + start center). Run → fail.
2. `core/action_registry.py`: add `_aliases`, `register_alias`, `resolve_id`; resolve in all
   lookups; migrate pending alias handlers.
3. `ui/shell/mac_menu.py`: `_reg_act` → `register_alias`; `connect_if` → `bind_default`
   (set_handler if unbound); themes via handlers; drop duplicate insert entries; add
   `_update_app_specific_visibility`.
4. `ui/shell/start_center.py`: `_bind_start_center_actions()`.
5. Verify: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase11_action_dispatch.py -v`, then the full suite.
