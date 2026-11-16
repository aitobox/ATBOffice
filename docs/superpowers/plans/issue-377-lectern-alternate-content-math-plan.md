# Plan: Issue #377

Spec: `docs/superpowers/specs/issue-377-lectern-alternate-content-math-spec.md`

1. Write `tests/test_lectern_alternate_content.py` (fails first):
   branch selection, tdf129372 shape + `∂` + center position, group-nested AC, paragraph
   `a14:m`, unsupported-Choice fallback picture, save/reload AC count, edited-shape fallback.
2. Add `src/atboffice/modules/presentation/io/alternate_content.py` (select_branch,
   collect_rel_refs, AltContentSource, render_preserved).
3. Reader: `_parse_shape` + `_parse_group_element` AC handling; `_parse_paragraph` math;
   post-load fingerprint pass.
4. Models: `Shape.alt_content`, `TextRun.math` (excluded from to_dict).
5. Writer: `shape_to_xml` preserved-AC branch; namespace registration.
6. Run `pytest tests/test_lectern_alternate_content.py` then the full presentation suite.
