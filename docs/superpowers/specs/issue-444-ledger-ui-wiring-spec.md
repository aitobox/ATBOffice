# Spec: Issue #444 — Ledger UI wiring (charts, pictures, data tools, menus)

Parent Epic: #436 (Step 8 of 12). Scope is limited to #444; object multi-select/grouping belongs to #447.

## Design

New focused modules (no monolithic growth of `ledger_window.py`):

| Module | Responsibility |
|---|---|
| `modules/spreadsheet/tools/chart_builder.py` | Turn a wizard spec (range, series orientation, type/subtype, titles, legend) into a `ChartData` dict read from live cells. |
| `modules/spreadsheet/tools/data_tools.py` | Pure sheet operations: subtotals (apply/remove), consolidate, advanced filter (in place / copy to, unique), Data Table (real substitution + DAG recalc), scenario summary sheet, fixed-width split. |
| `modules/spreadsheet/tools/sheet_spelling.py` | Scan text cells with `SpellEngine`, apply replacements. |
| `modules/spreadsheet/dialogs/sheet_spelling_dialog.py` | Excel-style spelling dialog (ignore / ignore all / add / change / change all). |
| `ui/shell/ledger_commands.py` | Ledger menu/toolbar command bindings: menu ID reconciliation, Edit->Clear, Insert->Name/Symbol/Page Break, Format->Conditional/AutoFormat, header/footer, zoom-to-selection, draw border, ungroup, spelling. |

Every operation that mutates cells runs through the grid's `_snapshot_state()` / `_commit_undo()` so it is undoable, then recalculates the workbook DAG.

## Behaviour decisions
- Chart wizard: `_on_finish` fills `chart_obj.chart_data` from the range; first text row/column become series names/categories; "As new sheet" creates a worksheet holding a full-page chart. Toolbar `chartWizard` opens the wizard.
- Picture: file bytes + MIME stored in `image_data`/`image_mime`; anchor sized from the image aspect; unreadable files show an error.
- Data Table: Excel semantics for one-input row/column and two-input tables; input cells restored after evaluation.
- Subtotal: groups by column change, inserts `=SUBTOTAL(fn, range)` rows plus a grand total; "Remove All" strips rows containing `SUBTOTAL(`.
- Consolidate: by position or by top-row/left-column labels into the active cell.
- Conditional formatting: Cell value / Formula / Color Scale (2 & 3 colour) / Data Bar / Icon Set, plus font colour, bold, italic, fill. Cell borders are not supported by the CF renderer and stay out of scope.
- Menu: Quire-only items (paragraph, bullets, tabs, page number, date/time, language, ruler) hidden in Ledger; Ledger-only items added; `data_filter`, `data_validation`, `insert_page_break`, `insert_symbol`, `insert_shape`, `format_font`, `format_borders`, `selectAll` bound.
- Header/footer text stored in `sheet.extra["header_footer"]` (print rendering is #442).
- `draw_group` disabled until multi-object selection (#447); `draw_ungroup` lifts a selected group's children.

## Task list
- [ ] Chart builder + wizard data binding + new-sheet charts + toolbar wiring
- [ ] Picture insertion with bytes/MIME
- [ ] Data tools (subtotal, consolidate, advanced filter, data table, scenario summary, fixed width)
- [ ] Conditional format dialog rule types
- [ ] Ledger menu/toolbar reconciliation, zoom selection, draw border, ungroup, spelling
- [ ] GUI tests `tests/gui/test_phase11_ledger_ui_wiring.py` + full suite + ruff
