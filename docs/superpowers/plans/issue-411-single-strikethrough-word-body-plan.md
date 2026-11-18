# Issue #411 Implementation Plan

1. Add `tests/gui/test_quire_strike_paint.py` and confirm the strike cases fail.
2. Add `_draw_strike_decoration` to `canvas_view.py` and call it from the normal, justified, and RTL paths.
3. Run the following and recapture the fixture:

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_quire_strike_paint.py tests/unit/writer tests/modules/writer -q
```
