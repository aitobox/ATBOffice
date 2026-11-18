# Issue #409 Implementation Plan

Spec: `docs/superpowers/specs/issue-409-ledger-chart-fills-titles-spec.md`

- [x] Add `tests/modules/spreadsheet/test_imported_chart_defaults.py` and confirm it fails.
- [x] Add `_apply_worksheet_defaults` and the `worksheet_defaults` flag in `chart/io.py`.
- [x] Enable the flag in `spreadsheet/io/xlsx_reader.py`.
- [x] Pass the full fill spec to `resolve_color` in `chart/painter.py` so alpha is painted.
- [x] Run the verification below and render both audited fixtures.

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/modules/spreadsheet tests/unit/presentation -q
```
