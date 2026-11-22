# Plan: Issue #444 — Ledger UI wiring

Spec: `docs/superpowers/specs/issue-444-ledger-ui-wiring-spec.md`

## Chunk A — Charts & pictures
1. `tools/chart_builder.py` (`build_chart_data`, `parse_sheet_range`); tests for column/row orientation and headers.
2. `ChartWizardDialog._on_finish`: attach `chart_data`, anchor at selection, new-sheet target via `workbook_model`.
3. `LedgerWindow.open_chart_wizard` passes the selection; `chartWizard`/`insertChart` call it; `insert_picture` loads bytes.

## Chunk B — Data tools
4. `tools/data_tools.py` functions + unit tests.
5. Dialog changes: DataTable delegates to `compute_data_table`, Scenario summary emits request, TextToColumns fixed width breaks.
6. Ledger openers connect signals and wrap in undo snapshot + recalc.

## Chunk C — Conditional formatting
7. ConditionRow gains Color Scale / Data Bar / Icon Set types and a font+fill format sub-dialog; `condFormat` opener stores the result in `sheet.conditional_formats`.

## Chunk D — Menus & toolbar
8. `mac_menu.py`: Ledger-only items, translations, app-specific visibility.
9. `ledger_commands.py`: bindings listed in the spec; whitelist container buttons.
10. Spelling tool + dialog.

## Verification
`QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase11_ledger_ui_wiring.py -v`, full suite, `ruff check .`.
