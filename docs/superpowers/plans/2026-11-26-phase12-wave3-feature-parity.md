# Phase 12 Wave 3: `.vibeoffice` Feature Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver the remaining four high-value `.vibeoffice` capabilities in clean, isolated modules with full Undo, i18n, theme, lossless OOXML round-trip, and test coverage—while keeping default Office 2003 visual rendering completely unchanged.

**Architecture:**
1. **Task 1 (`RB.follow`)**: `src/atboffice/ui/panes/context_tools_pane.py` + `TaskPaneFollowController` wired into `BaseOfficeWindow` and all three windows, with `"view/pane_follows_selection"` in `OptionsDialog`.
2. **Task 2 (Lazy Paper 2016 Ribbon)**: `src/atboffice/ui/components/ribbon_bar.py` + declarative app specs (`quire_ribbon.py`, `ledger_ribbon.py`, `lectern_ribbon.py`) instantiated strictly lazily only when `current_theme == "paper2016"`.
3. **Task 3 (Lectern Masters)**: `HandoutMasterSettings` / `NotesMasterSettings` in `presentation.py`, `HandoutMasterView` / `NotesMasterView` in `master_view.py`, `printing.py` integration, and `lxml`-based lossless PPTX round-trip.
4. **Task 4 (Ledger Parity)**: Conditional formatting (color scales, data bars, icon sets) E2E verification, interactive `FixedWidthRulerWidget` in `text_to_columns_wizard.py` + undoable execution, and `PivotChart` creation/auto-sync on PivotTable refresh.

**Spec:** [2026-11-26-phase12-robustness-and-parity-design.md](file:///Users/aitobox/work/aitobox/ATBOffice/docs/superpowers/specs/2026-11-26-phase12-robustness-and-parity-design.md)

## Global Constraints
- Run inside `WT3=/Users/aitobox/work/aitobox/ATBOffice/.worktrees/phase12-wave3-feature-parity` using `QT_QPA_PLATFORM=offscreen PYTHONPATH="$WT3/src:$WT3" conda run -n ATBOffice ...`.
- Visible UI strings use `safe_tr()` with Chinese source text + English entries in `src/atboffice/resources/locale/source/zh-CN_to_en.json`; widgets implement `retranslate_ui()`.
- Commands go through `ActionRegistry`; document edits go through `UndoService` / `PresentationHistory`.
- Colors come from `ThemeTokens` / `ui/styles/luna_2003.py`; fonts from `ui_font()`.
- Zero `PYTEST_CURRENT_TEST` code paths; errors visible or logged via `logger.exception`.

---

## Task 1 — Contextual Task Pane Auto-Follow (`RB.follow`)
- **Modify**: `src/atboffice/core/settings.py` (`view/pane_follows_selection: True`), `src/atboffice/ui/dialogs/options_dialog.py` (`chk_pane_follows`), `src/atboffice/ui/shell/base_window.py`, `src/atboffice/ui/shell/quire_window.py`, `src/atboffice/ui/shell/ledger_window.py`, `src/atboffice/ui/shell/lectern_window.py`, `src/atboffice/resources/locale/source/zh-CN_to_en.json`.
- **Create**: `src/atboffice/ui/panes/context_tools_pane.py`, `tests/ui/test_context_pane_follow.py`.
- **Verify**: `pytest tests/ui/test_context_pane_follow.py -v`

## Task 2 — Lazy Paper 2016 Ribbon Mode
- **Create**: `src/atboffice/ui/components/ribbon_bar.py`, `src/atboffice/ui/shell/quire_ribbon.py`, `src/atboffice/ui/shell/ledger_ribbon.py`, `src/atboffice/ui/shell/lectern_ribbon.py`, `tests/ui/test_ribbon_spec_parity.py`.
- **Modify**: `src/atboffice/ui/shell/base_window.py` (lazy host + classic toolbar save/restore), `src/atboffice/ui/shell/{quire,ledger,lectern}_window.py`, `src/atboffice/ui/dialogs/theme_dialog.py` (if needed), `src/atboffice/resources/locale/source/zh-CN_to_en.json`.
- **Verify**: `pytest tests/ui/test_ribbon_spec_parity.py -v`

## Task 3 — Lectern Handout Master & Notes Master
- **Modify**: `src/atboffice/modules/presentation/models/presentation.py`, `src/atboffice/modules/presentation/views/master_view.py`, `src/atboffice/modules/presentation/views/workspace.py`, `src/atboffice/ui/shell/lectern_commands.py`, `src/atboffice/ui/shell/lectern_window.py`, `src/atboffice/ui/shell/mac_menu.py`, `src/atboffice/modules/presentation/printing.py`, `src/atboffice/modules/presentation/io/pptx_reader.py`, `src/atboffice/modules/presentation/io/pptx_writer.py`, `src/atboffice/modules/presentation/io/writer_templates.py`, `src/atboffice/resources/locale/source/zh-CN_to_en.json`.
- **Create**: `tests/modules/presentation/test_handout_notes_master.py`.
- **Verify**: `pytest tests/modules/presentation/test_handout_notes_master.py -v` and `python scripts/run_corpus_audit.py --strict`.

## Task 4 — Ledger Conditional Formatting E2E + Fixed-Width Ruler + PivotChart
- **Modify**: `src/atboffice/modules/spreadsheet/dialogs/text_to_columns_wizard.py`, `src/atboffice/ui/shell/ledger_data.py`, `src/atboffice/ui/shell/ledger_objects.py`, `src/atboffice/ui/shell/ledger_window.py`, `src/atboffice/modules/spreadsheet/tools/chart_builder.py`, `src/atboffice/modules/spreadsheet/views/grid_data_commands.py`, `src/atboffice/modules/spreadsheet/panes/pivot_fields_pane.py` (plus any CF dialog/painter/IO fixes found), `src/atboffice/resources/locale/source/zh-CN_to_en.json`.
- **Create**: `tests/gui/test_phase12_ledger_cf_and_data.py`.
- **Verify**: `pytest tests/gui/test_phase12_ledger_cf_and_data.py -v`.

## Full Wave 3 Gate
- `ruff check .` && `ruff format --check .`
- `mypy src/atboffice/core`
- `python scripts/source_diff.py --check`
- `python scripts/run_corpus_audit.py --strict`
- `python scripts/run_office_diff.py --all --capture --strict`
- `QT_QPA_PLATFORM=offscreen pytest -n auto -q`
- Whole-branch Pro review on `main..HEAD`
