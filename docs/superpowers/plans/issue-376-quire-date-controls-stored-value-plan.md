# Plan: Issue #376

1. Write `tests/test_quire_fields.py` (fails first):
   - load fixture, paginate → texts `12 April 2026`, `12 квітня 2026 р.`; result run colour is None.
   - save + reload + paginate → same stored text.
   - DATE in header story keeps cached text after pagination; PAGE still evaluates.
   - explicit `update_fields(doc)` still re-evaluates DATE.
   - replaced PAGE result keeps the result run's r_pr, not the begin run's.
   - SDT with `w:date` + fullDate shows stored content; without fullDate shows placeholder content.
   Verify: `pytest tests/test_quire_fields.py` → fails.
2. `models/field.py`: constants + `types` param + result r_pr selection.
3. `layout/pagination.py`: pass `types=LAYOUT_FIELD_TYPES`; gate `_evaluate_hf_paragraph`.
   Verify: `pytest tests/test_quire_fields.py` → passes.
4. Update `tests/gui/test_phase9_ruler_and_field_convergence.py` DATE assertion; run full suite.
