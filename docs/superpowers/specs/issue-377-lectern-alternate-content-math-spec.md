# Spec: Issue #377 — Lectern honors mc:AlternateContent and draws OMML math

## Problem
`PptxReader._parse_shape` only accepts `sp`, `cxnSp`, `pic`, `graphicFrame`, `grpSp`.
`mc:AlternateContent` (AC) wrappers in `p:spTree` / `p:grpSp` are silently skipped,
so PowerPoint math slides (e.g. `libreoffice__tdf129372.pptx`) load with zero shapes.
`a14:m` math inside `a:p` is also ignored by `_parse_paragraph`.

## Design
1. **Branch selection** (`io/alternate_content.py`, new):
   - `select_branch(ac)` returns the first `mc:Choice` whose `Requires` prefixes are all in
     `SUPPORTED_REQUIRES = {"a14"}` (DrawingML 2010 — math + ignorable extensions), else the
     `mc:Fallback`, else `None`.
   - Deviation from the JS original (which always prefers Fallback): the issue asks for the
     Choice so math is real text, not a picture. Unsupported Choices (`p14` ink, etc.) still
     fall back.
2. **Shape trees**: `_parse_shape` handles tag `AlternateContent`: parse every element of the
   selected branch; one result → that shape; several → wrap in a `group` shape; none → `None`.
   Groups (`_parse_group_element`) route AC children through the same path.
3. **Round trip**: the resolved top-level shape stores `alt_content = AltContentSource(xml,
   rels, fingerprint)`:
   - `xml`: raw AC serialized from the source part.
   - `rels`: `rId -> media part path` for every `r:*` attribute inside the AC; preservation is
     disabled if any reference is not an internal image part (hyperlinks, OLE, external).
   - `fingerprint`: `json.dumps(shape.to_dict())` taken after load completes.
   - Writer (`shape_to_xml`): if `alt_content` is present and the fingerprint still matches,
     emit the raw AC with rIds remapped through `media_resolver` and `cNvPr/@id` values
     remapped through `id_resolver` (consistent between Choice and Fallback). Otherwise
     serialize the model normally (the edit wins, AC is dropped).
   - Namespace prefixes used by `Requires` (and in the AC content) are registered with
     ElementTree so `Requires="a14"` stays resolvable after re-serialization.
4. **Math in text**: `_parse_paragraph` handles `a14:m` (via `omml.parse_omml`) and AC
   children inside `a:p` (resolved with the same `select_branch`). Each math zone becomes a
   `TextRun` with `text = item.plain_text()`, font from the first `m:r/a:rPr` (default
   `Cambria Math`), and a new `TextRun.math` field holding the `OfficeMathItem`. Display
   math (`m:oMathPara`, `jc` center/centerGroup) centers the paragraph when it has no `algn`.
   Rendering goes through the existing text pipeline (linearized math).

## Edge cases
- AC with empty branches → no shape, no crash.
- AC whose Fallback is a `p:pic` → picture shape (media registered via existing pic parsing).
- Nested AC (AC in a group in an AC) → recursive.
- Shape edited after load → fingerprint mismatch → normal serialization.
- Shape cloned/duplicated → raw AC written with fresh ids per slide via `id_resolver`.
- Parse errors inside AC → existing per-shape `LoadWarning` handling.

## Limitations (documented)
Structured OMML (fractions, radicals) is drawn linearized through the text pipeline; full
`math_layout.paint_math` integration into the Lectern text layout is follow-up work.

## Task list
- [ ] Task 1: AC branch-selection helper + unit tests
- [ ] Task 2: Shape-tree AC parsing (spTree + groups) + tests on tdf129372
- [ ] Task 3: `a14:m` / AC-in-paragraph math runs + tests
- [ ] Task 4: Raw AC capture and verbatim write-back with rId/id remapping + round-trip test
- [ ] Task 5: Fallback-only path (unsupported Choice) test
- [ ] Task 6: Full test suite + grill-me audit
